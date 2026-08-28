"""PSO híbrido Random Keys com avaliações finais em lotes GPU."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from time import perf_counter

import cupy as cp
import numpy as np

from metaheuristica import (
    EvaluationResult, OptimizationResult, ProblemInstance, PsoConfig, RunConfig,
    TerminationReason, canonicalize_solution, evaluate_solution,
    validate_solution,
)
from metaheuristica.errors import RepairBudgetExhausted, SolutionValidationError
from metaheuristica.repair import repair_empty_lots_with_evaluation
from metaheuristica.metrics import COST_TOLERANCE

from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.numerics import require_equivalent
from metaheuristica_gpu.objective import GpuBatchObjective


VELOCITY_LIMIT = 0.5


@dataclass(slots=True)
class _Best:
    position: np.ndarray
    solution: np.ndarray
    evaluation: EvaluationResult


@dataclass(slots=True)
class _Particle:
    position: np.ndarray
    velocity: np.ndarray
    pbest: _Best | None = None


@dataclass(frozen=True, slots=True)
class _Trial:
    position: np.ndarray
    velocity: np.ndarray
    position_clips: int
    velocity_clips: int


def _decode(position: np.ndarray, n: int, k: int) -> np.ndarray:
    labels = np.minimum(np.floor(position * k).astype(np.int64), k - 1)
    if labels.shape != (n,):
        raise SolutionValidationError("posição GPU com dimensão inválida")
    return labels


def _initial_particle(n: int, k: int, rng: np.random.Generator) -> _Particle:
    permutation = rng.permutation(n)
    labels = np.empty(n, dtype=np.int64)
    labels[permutation] = np.arange(n, dtype=np.int64) % k
    position = (labels.astype(np.float64) + rng.random(n)) / k
    velocity = rng.uniform(-VELOCITY_LIMIT, VELOCITY_LIMIT, size=n)
    return _Particle(position.copy(), velocity.astype(np.float64, copy=False).copy())


def _copy_best(position: np.ndarray, solution: np.ndarray, evaluation: EvaluationResult) -> _Best:
    return _Best(position.copy(), solution.copy(), evaluation)


def _better(candidate: _Best, incumbent: _Best) -> bool:
    difference = candidate.evaluation.total_cost - incumbent.evaluation.total_cost
    if difference < -COST_TOLERANCE:
        return True
    if abs(difference) > COST_TOLERANCE:
        return False
    candidate_solution = tuple(int(value) for value in candidate.solution)
    incumbent_solution = tuple(int(value) for value in incumbent.solution)
    if candidate_solution != incumbent_solution:
        return candidate_solution < incumbent_solution
    return tuple(candidate.position) < tuple(incumbent.position)


def _trial(
    particle: _Particle, gbest: np.ndarray, config: PsoConfig,
    rng: np.random.Generator,
) -> _Trial:
    assert particle.pbest is not None
    r1 = rng.random(particle.position.shape)
    r2 = rng.random(particle.position.shape)
    raw_velocity = (
        config.inertia * particle.velocity
        + config.cognitive * r1 * (particle.pbest.position - particle.position)
        + config.social * r2 * (gbest - particle.position)
    )
    velocity_clips = int(
        np.count_nonzero((raw_velocity < -VELOCITY_LIMIT) | (raw_velocity > VELOCITY_LIMIT))
    )
    # A velocidade saturada é a que se aplica à posição: o limite da seção 16 é do
    # passo, não apenas do estado herdado pelo termo de inércia da iteração
    # seguinte. Espelha `metaheuristica.pso._trial_state`, corrigida no pacote A1.
    velocity = np.clip(raw_velocity, -VELOCITY_LIMIT, VELOCITY_LIMIT)
    raw_position = particle.position + velocity
    position_clips = int(np.count_nonzero((raw_position < 0.0) | (raw_position > 1.0)))
    return _Trial(
        np.clip(raw_position, 0.0, 1.0),
        velocity,
        position_clips,
        velocity_clips,
    )


def _project(
    position: np.ndarray, original: np.ndarray, repaired: np.ndarray, k: int
) -> np.ndarray:
    fractions = np.clip(k * position - original, 0.0, np.nextafter(1.0, 0.0))
    projected = (repaired.astype(np.float64) + fractions) / k
    for index, label_value in enumerate(repaired):
        label = int(label_value); midpoint = (label + 0.5) / k
        for _ in range(16):
            if min(int(np.floor(k * projected[index])), k - 1) == label:
                break
            projected[index] = np.nextafter(projected[index], midpoint)
        else:
            projected[index] = midpoint
    if not np.array_equal(_decode(projected, len(projected), k), repaired):
        raise SolutionValidationError("projeção GPU incoerente")
    return projected


def _canonical(position: np.ndarray, labels: np.ndarray, n: int, k: int) -> tuple[np.ndarray, np.ndarray]:
    canonical = canonicalize_solution(labels, n_units=n, k=k)
    if np.array_equal(labels, canonical):
        return position.copy(), canonical
    return _project(position, labels, canonical, k), canonical


def run_pso_gpu(
    instance: ProblemInstance,
    run_config: RunConfig,
    config: PsoConfig,
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
    particles = [_initial_particle(instance.n_units, run_config.k, rng) for _ in range(config.n_particles)]
    gbest: _Best | None = None
    iterations = particles_evaluated = repair_attempts = repair_evaluations = 0
    position_clips = velocity_clips = 0

    def commit(
        particle: _Particle, position: np.ndarray, velocity: np.ndarray,
        solution: np.ndarray, evaluation: EvaluationResult,
    ) -> None:
        nonlocal gbest, particles_evaluated
        particle.position = position.copy(); particle.velocity = velocity.copy()
        candidate = _copy_best(position, solution, evaluation)
        if particle.pbest is None or _better(candidate, particle.pbest):
            particle.pbest = candidate
        assert particle.pbest is not None
        if gbest is None or _better(particle.pbest, gbest):
            gbest = _copy_best(
                particle.pbest.position, particle.pbest.solution, particle.pbest.evaluation
            )
        particles_evaluated += 1

    def flush(items: list[tuple[_Particle, np.ndarray, np.ndarray, np.ndarray]]) -> bool:
        if not items or evaluator.remaining <= 0:
            return evaluator.remaining == 0
        batch = evaluator.evaluate_batch([item[3] for item in items])
        for item, solution, evaluation in zip(items, batch.solutions, batch.results):
            particle, position, velocity, _ = item
            commit(particle, position, velocity, solution, evaluation)
        items.clear()
        return batch.exhausted

    try:
        initial: list[tuple[_Particle, np.ndarray, np.ndarray, np.ndarray]] = []
        for particle in particles:
            labels = _decode(particle.position, instance.n_units, run_config.k)
            position, solution = _canonical(particle.position, labels, instance.n_units, run_config.k)
            initial.append((particle, position, particle.velocity, solution))
        if flush(initial):
            raise StopIteration
        assert gbest is not None

        while evaluator.remaining:
            snapshot = gbest.position.copy()
            trials = [_trial(particle, snapshot, config, rng) for particle in particles]
            position_clips += sum(item.position_clips for item in trials)
            velocity_clips += sum(item.velocity_clips for item in trials)
            pending: list[tuple[_Particle, np.ndarray, np.ndarray, np.ndarray]] = []
            for particle, trial in zip(particles, trials):
                decoded = _decode(trial.position, instance.n_units, run_config.k)
                if np.count_nonzero(np.bincount(decoded, minlength=run_config.k)) < run_config.k:
                    if flush(pending):
                        raise StopIteration
                    repair_attempts += 1
                    before = evaluator.evaluations
                    try:
                        repaired, reused = repair_empty_lots_with_evaluation(
                            decoded, evaluator
                        )
                    except RepairBudgetExhausted:
                        repair_evaluations += evaluator.evaluations - before
                        raise StopIteration
                    # A4, espelho da CPU: a unidade reaproveitada muda da coluna
                    # de reparo para a de partículas, e a partícula reparada é
                    # comprometida direto, sem entrar no lote da GPU, porque sua
                    # avaliação já existe.
                    repair_evaluations += (
                        evaluator.evaluations - before - int(reused is not None)
                    )
                    position = _project(trial.position, decoded, repaired, run_config.k)
                    if reused is not None:
                        commit(particle, position, trial.velocity, repaired, reused)
                        if evaluator.remaining == 0:
                            raise StopIteration
                    else:
                        pending.append((particle, position, trial.velocity, repaired))
                        if flush(pending):
                            raise StopIteration
                else:
                    position, solution = _canonical(
                        trial.position, decoded, instance.n_units, run_config.k
                    )
                    validate_solution(solution, n_units=instance.n_units, k=run_config.k)
                    pending.append((particle, position, trial.velocity, solution))
            if flush(pending):
                raise StopIteration
            iterations += 1
    except StopIteration:
        pass
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
        algorithm="pso_gpu", k=run_config.k, seed=run_config.seed,
        budget=run_config.budget, weights=run_config.weights,
        solution=np.asarray(evaluator.incumbent_solution, dtype=np.int64),
        # Publica o mesmo objeto que a tabela de checkpoints carrega. A
        # conferência de conformidade contra a CPU continua sendo feita acima,
        # por `require_equivalent`, que é contrato do projeto.
        evaluation=evaluator.incumbent_evaluation,
        evaluations=evaluator.evaluations, cache_hits=0,
        checkpoints=evaluator.checkpoints, runtime_seconds=runtime,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={
            "iterations_completed": iterations, "particles_evaluated": particles_evaluated,
            "repair_attempts": repair_attempts, "repair_evaluations": repair_evaluations,
            "position_clips": position_clips, "velocity_clips": velocity_clips,
            "gpu_timing": evaluator.timing.to_dict(),
            "max_numerical_difference": evaluator.max_numerical_difference,
        },
    )
