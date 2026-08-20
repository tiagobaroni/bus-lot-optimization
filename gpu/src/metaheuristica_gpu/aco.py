"""ACO híbrido: controle CPU e avaliações finais em lote na GPU."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from time import perf_counter

import cupy as cp
import numpy as np

from metaheuristica import (
    AcoConfig, EvaluationResult, ObjectiveWeights, OptimizationResult,
    ProblemInstance, RunConfig, TerminationReason, canonicalize_solution,
    evaluate_solution, validate_solution,
)
from metaheuristica.aco import _heuristic_from_state, _PartialConstructionState

from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.numerics import require_equivalent
from metaheuristica_gpu.objective import GpuBatchObjective


@dataclass(frozen=True, slots=True)
class _Ant:
    solution: np.ndarray
    forced: int
    probabilistic: int


# O estado parcial e a informação heurística vêm da CPU, e não de uma cópia
# local. A cópia anterior reimplementava a mesma aritmética, o que já custou a
# esta árvore uma divergência silenciosa: o espelho de `_trial` no PSO reteve a
# ordem anterior ao pacote A1 e passou a divergir da CPU em custo total. Ao
# delegar, a variante O4 do achado F4-1, com a asserção de contiguidade em ordem
# C, vale aqui por construção, `require_equivalent` continua válido e uma futura
# alteração da aritmética não pode atingir só um dos dois lados.
_PartialState = _PartialConstructionState


def _choices(prefix: list[int], n: int, k: int) -> tuple[tuple[int, ...], bool]:
    opened = max(prefix, default=-1) + 1
    remaining = n - len(prefix)
    unopened = k - opened
    if not prefix:
        return (0,), True
    if remaining == unopened:
        return (opened,), True
    return tuple(range(opened + (1 if opened < k else 0))), False


def _construct(
    instance: ProblemInstance, k: int, weights: ObjectiveWeights,
    tau: np.ndarray, config: AcoConfig, rng: np.random.Generator,
) -> _Ant:
    prefix: list[int] = []
    state = _PartialState(instance, k=k, weights=weights)
    forced = probabilistic = 0
    for index in range(instance.n_units):
        choices, is_forced = _choices(prefix, instance.n_units, k)
        if is_forced:
            selected = choices[0]; forced += 1
        else:
            eta = _heuristic_from_state(state, choices)
            log_weights = config.alpha * np.log(tau[index, list(choices)]) + config.beta * np.log(eta)
            log_weights -= float(np.max(log_weights))
            raw = np.exp(log_weights)
            probabilities = raw / float(np.sum(raw))
            selected = int(rng.choice(choices, p=probabilities)); probabilistic += 1
        prefix.append(selected); state.append(selected)
    solution = canonicalize_solution(prefix, n_units=instance.n_units, k=k)
    return _Ant(solution, forced, probabilistic)


def _update(tau: np.ndarray, ants: list[tuple[np.ndarray, EvaluationResult]], rho: float) -> np.ndarray:
    updated = np.array(tau * (1.0 - rho), dtype=np.float64, copy=True)
    rows = np.arange(tau.shape[0], dtype=np.int64)
    for solution, evaluation in ants:
        updated[rows, solution] += 1.0 - min(1.0, max(0.0, evaluation.total_cost))
    return updated


def run_aco_gpu(
    instance: ProblemInstance,
    run_config: RunConfig,
    config: AcoConfig,
    *,
    verify_every_batch: bool = False,
    guard: Callable[[], None] | None = None,
) -> OptimizationResult:
    rng = np.random.Generator(np.random.PCG64(run_config.seed))
    objective = GpuBatchObjective(instance, k=run_config.k, weights=run_config.weights)
    cp.cuda.get_current_stream().synchronize()
    start = perf_counter()
    evaluator = HybridEvaluator(
        instance, run_config, objective, verify_every_batch=verify_every_batch,
        guard=guard,
    )
    tau = np.ones((instance.n_units, run_config.k), dtype=np.float64)
    generations = pheromone_updates = ants_evaluated = forced = probabilistic = 0
    try:
        while evaluator.remaining:
            count = min(config.n_ants, evaluator.remaining)
            constructed = [
                _construct(instance, run_config.k, run_config.weights, tau, config, rng)
                for _ in range(count)
            ]
            batch = evaluator.evaluate_batch([ant.solution for ant in constructed])
            evaluated = list(zip((ant.solution for ant in constructed), batch.results))
            ants_evaluated += len(evaluated)
            forced += sum(ant.forced for ant in constructed)
            probabilistic += sum(ant.probabilistic for ant in constructed)
            if len(evaluated) == config.n_ants:
                tau = _update(tau, evaluated, config.rho)
                generations += 1; pheromone_updates += 1
    finally:
        cp.cuda.get_current_stream().synchronize()
        runtime = perf_counter() - start
        objective.close()
    assert evaluator.incumbent_solution is not None and evaluator.incumbent_evaluation is not None
    final_cpu = evaluate_solution(
        instance, evaluator.incumbent_solution, k=run_config.k, weights=run_config.weights
    )
    require_equivalent(evaluator.incumbent_evaluation, final_cpu)
    return OptimizationResult(
        algorithm="aco_gpu", k=run_config.k, seed=run_config.seed,
        budget=run_config.budget, weights=run_config.weights,
        solution=np.asarray(evaluator.incumbent_solution, dtype=np.int64),
        evaluation=final_cpu, evaluations=evaluator.evaluations, cache_hits=0,
        checkpoints=evaluator.checkpoints, runtime_seconds=runtime,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={
            "generations_completed": generations, "ants_evaluated": ants_evaluated,
            "pheromone_updates": pheromone_updates, "forced_assignments": forced,
            "probabilistic_assignments": probabilistic,
            "final_tau_min": float(np.min(tau)), "final_tau_max": float(np.max(tau)),
            "gpu_timing": evaluator.timing.to_dict(),
            "max_numerical_difference": evaluator.max_numerical_difference,
        },
    )
