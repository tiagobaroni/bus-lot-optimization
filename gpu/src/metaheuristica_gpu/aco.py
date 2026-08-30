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
from metaheuristica.aco import (
    _choice_probabilities, _EvaluatedAnt, _heuristic_from_state,
    _PartialConstructionState, _update_pheromone,
)
from metaheuristica.errors import SolutionValidationError

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
            # F8-10: a normalização passa a ser a do caminho normativo. A cópia
            # local tomava o logaritmo sem conferir que `tau` e `eta` são
            # positivos e finitos, e publicava as probabilidades sem conferir
            # que somam um: célula nula produzia peso `-inf` em silêncio. A
            # sequência aritmética do caminho feliz é a mesma, e a identidade
            # bit a bit da construção espelhada foi reconferida contra a saída
            # gravada antes da mudança.
            probabilities = _choice_probabilities(
                tau[index, list(choices)], eta,
                alpha=config.alpha, beta=config.beta,
            )
            selected = int(rng.choice(choices, p=probabilities)); probabilistic += 1
        prefix.append(selected); state.append(selected)
    # F8-10: a pós-condição de canonicidade que `_construct_ant` confere faltava
    # aqui, e `canonicalize_solution` renomeava em silêncio. Sob crescimento
    # restrito o prefixo já é canônico, logo a conferência é guarda-corpo, e a
    # formiga publicada passa a ser conferidamente a formiga construída.
    solution = validate_solution(prefix, n_units=instance.n_units, k=k)
    canonical = canonicalize_solution(solution, n_units=instance.n_units, k=k)
    if not np.array_equal(solution, canonical):
        raise SolutionValidationError("formiga produziu solução não canônica")
    return _Ant(canonical, forced, probabilistic)


def _update(tau: np.ndarray, ants: list[tuple[np.ndarray, EvaluationResult]], rho: float) -> np.ndarray:
    # F8-10: a atualização passa a ser a do caminho normativo. A cópia local
    # clipava o custo total por `min(1.0, max(0.0, ...))` em vez de recusar
    # custo fora do intervalo normalizado, não conferia `tau` na entrada nem a
    # positividade da matriz depois do depósito, e não punha piso na
    # evaporação, de modo que com `rho = 0,5` a célula que só evapora chega a
    # zero exato e reaparece na construção seguinte como logaritmo de zero. A
    # aritmética do caminho feliz é a mesma, célula a célula.
    return _update_pheromone(
        tau,
        tuple(_EvaluatedAnt(solution, evaluation) for solution, evaluation in ants),
        rho=rho,
    )


def _reachable_mask(shape: tuple[int, int]) -> np.ndarray:
    """Células que a construção de crescimento restrito pode depositar.

    Espelha `metaheuristica.aco._aco_search`, corrigida no pacote B11 pelo
    defeito `F4-4`: `tau[i, j]` com `j > i` nunca recebe depósito e vale
    `(1-rho)^G` para todas, o que fazia `final_tau_min` medir evaporação pura
    em vez do piso real do feromônio. A equivalência entre triângulo inferior e
    alcançabilidade vale para `K < n_units`, que é o escopo em que a correção
    foi prescrita. A fronteira `K == n_units`, em que só a diagonal é alcançável
    e o triângulo volta a incluir células que nunca recebem depósito, está
    asseverada em `tests/test_aco.py`, e a asserção vale igualmente aqui porque a
    expressão da máscara é literalmente a mesma. Nenhum dos 60 cenários usa essa
    configuração, e tratá-la pertence a um pacote que a declare.
    """

    return np.tril(np.ones(shape, dtype=bool))


def run_aco_gpu(
    instance: ProblemInstance,
    run_config: RunConfig,
    config: AcoConfig,
    *,
    verify_every_batch: bool = False,
    guard: Callable[[], None] | None = None,
) -> OptimizationResult:
    rng = np.random.Generator(np.random.PCG64(run_config.seed))
    # F8-14: a construção do objetivo em lote faz trabalho de CPU e cinco
    # transferências para o dispositivo, e ficava fora de todo campo publicado.
    # O cronômetro oficial **não** se move, porque a comparabilidade com as
    # execuções já medidas depende de o campo principal manter a definição; o
    # custo de preparação passa a ter campo próprio.
    preparation_start = perf_counter()
    objective = GpuBatchObjective(instance, k=run_config.k, weights=run_config.weights)
    cp.cuda.get_current_stream().synchronize()
    start = perf_counter()
    device_preparation = start - preparation_start
    evaluator = HybridEvaluator(
        instance, run_config, objective, verify_every_batch=verify_every_batch,
        guard=guard,
    )
    tau = np.ones((instance.n_units, run_config.k), dtype=np.float64)
    reachable = _reachable_mask(tau.shape)
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
        # Publica o mesmo objeto que a tabela de checkpoints carrega. A
        # conferência de conformidade contra a CPU continua sendo feita acima,
        # por `require_equivalent`, que é contrato do projeto.
        evaluation=evaluator.incumbent_evaluation,
        evaluations=evaluator.evaluations, cache_hits=0,
        checkpoints=evaluator.checkpoints, runtime_seconds=runtime,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={
            "generations_completed": generations, "ants_evaluated": ants_evaluated,
            "pheromone_updates": pheromone_updates, "forced_assignments": forced,
            "probabilistic_assignments": probabilistic,
            # Somente células alcançáveis no mínimo; o máximo permanece
            # tomado sobre a matriz inteira, por ser informativo.
            "final_tau_min": float(np.min(tau[reachable])),
            "final_tau_max": float(np.max(tau)),
            "device_preparation_seconds": device_preparation,
            "gpu_timing": evaluator.timing.to_dict(),
            "max_numerical_difference": evaluator.max_numerical_difference,
        },
    )
