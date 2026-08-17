"""Ant Colony Optimization para partições canônicas de linhas."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np
from numpy.typing import NDArray

from metaheuristica.canonical import canonicalize_solution, validate_k, validate_solution
from metaheuristica.errors import (
    ConfigurationError,
    EvaluationLimitReached,
    SolutionValidationError,
)
from metaheuristica.metrics import COST_TOLERANCE, OptimizationResult, RunConfig
from metaheuristica.objective import _evaluate_aggregates
from metaheuristica.optimizer import OptimizationContext, execute_optimizer
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class AcoConfig:
    """Hiperparâmetros específicos do ACO."""

    alpha: float
    beta: float
    rho: float
    n_ants: int

    def __post_init__(self) -> None:
        for name, value in (("alpha", self.alpha), ("beta", self.beta)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigurationError(f"{name} deve ser numérico")
            if not isfinite(float(value)) or value <= 0:
                raise ConfigurationError(f"{name} deve ser finito e positivo")
            object.__setattr__(self, name, float(value))
        if (
            isinstance(self.rho, bool)
            or not isinstance(self.rho, (int, float))
            or not isfinite(float(self.rho))
            or not 0 < self.rho < 1
        ):
            raise ConfigurationError("rho deve ser finito e estar entre zero e um")
        object.__setattr__(self, "rho", float(self.rho))
        if (
            isinstance(self.n_ants, bool)
            or not isinstance(self.n_ants, int)
            or self.n_ants <= 0
        ):
            raise ConfigurationError("n_ants deve ser um inteiro positivo")


@dataclass(frozen=True, slots=True)
class _ConstructionChoices:
    allowed: tuple[int, ...]
    forced: bool


@dataclass(frozen=True, slots=True)
class _ConstructedAnt:
    solution: IntArray
    forced_assignments: int
    probabilistic_assignments: int


@dataclass(frozen=True, slots=True)
class _EvaluatedAnt:
    solution: IntArray
    evaluation: EvaluationResult


class _PartialConstructionState:
    """Agregados incrementais equivalentes ao subproblema induzido."""

    __slots__ = (
        "affinity_cut",
        "affinity_total",
        "demand_totals",
        "instance",
        "k",
        "labels",
        "production_totals",
        "territorial_cut",
        "territorial_total",
        "weights",
    )

    def __init__(
        self, instance: ProblemInstance, *, k: int, weights: ObjectiveWeights
    ) -> None:
        self.instance = instance
        self.k = k
        self.weights = weights
        self.labels: list[int] = []
        self.demand_totals = np.zeros(k, dtype=np.float64)
        self.production_totals = np.zeros(k, dtype=np.float64)
        self.territorial_cut = 0.0
        self.territorial_total = 0.0
        self.affinity_cut = 0.0
        self.affinity_total = 0.0

    def evaluate_choice(self, lot: int) -> EvaluationResult:
        unit_index = len(self.labels)
        demand = self.demand_totals.copy()
        production = self.production_totals.copy()
        demand[lot] += self.instance.demand[unit_index]
        production[lot] += self.instance.production[unit_index]
        previous = np.asarray(self.labels, dtype=np.int64)
        territorial_edges = self.instance.s_territorial[unit_index, :unit_index]
        affinity_edges = self.instance.w_affinity[unit_index, :unit_index]
        separated = previous != lot
        return _evaluate_aggregates(
            demand_totals=demand,
            production_totals=production,
            territorial_cut=self.territorial_cut
            + float(np.sum(territorial_edges[separated])),
            territorial_total=self.territorial_total + float(np.sum(territorial_edges)),
            affinity_cut=self.affinity_cut + float(np.sum(affinity_edges[separated])),
            affinity_total=self.affinity_total + float(np.sum(affinity_edges)),
            weights=self.weights,
        )

    def append(self, lot: int) -> None:
        unit_index = len(self.labels)
        previous = np.asarray(self.labels, dtype=np.int64)
        territorial_edges = self.instance.s_territorial[unit_index, :unit_index]
        affinity_edges = self.instance.w_affinity[unit_index, :unit_index]
        separated = previous != lot
        self.demand_totals[lot] += self.instance.demand[unit_index]
        self.production_totals[lot] += self.instance.production[unit_index]
        self.territorial_cut += float(np.sum(territorial_edges[separated]))
        self.territorial_total += float(np.sum(territorial_edges))
        self.affinity_cut += float(np.sum(affinity_edges[separated]))
        self.affinity_total += float(np.sum(affinity_edges))
        self.labels.append(lot)


def _validate_prefix(prefix: Any, *, n_units: int, k: int) -> tuple[int, ...]:
    validate_k(k, n_units)
    array = np.asarray(prefix)
    if array.ndim != 1 or len(array) >= n_units:
        raise SolutionValidationError("prefixo deve ser vetor incompleto da instância")
    if array.size and (not np.issubdtype(array.dtype, np.integer) or np.issubdtype(
        array.dtype, np.bool_
    )):
        raise SolutionValidationError("prefixo deve conter rótulos inteiros")
    labels = tuple(int(value) for value in array)
    if labels and labels[0] != 0:
        raise SolutionValidationError("primeiro rótulo do prefixo deve ser zero")
    maximum = -1
    for label in labels:
        if label < 0 or label >= k:
            raise SolutionValidationError("rótulo do prefixo fora do intervalo")
        if label > maximum + 1:
            raise SolutionValidationError("prefixo pula rótulo canônico")
        maximum = max(maximum, label)
    opened = maximum + 1
    remaining = n_units - len(labels)
    unopened = k - opened
    if remaining < unopened:
        raise SolutionValidationError("prefixo não pode mais abrir todos os lotes")
    return labels


def _construction_choices(prefix: Any, *, n_units: int, k: int) -> _ConstructionChoices:
    labels = _validate_prefix(prefix, n_units=n_units, k=k)
    opened = max(labels, default=-1) + 1
    remaining = n_units - len(labels)
    unopened = k - opened
    if not labels:
        return _ConstructionChoices((0,), True)
    if remaining == unopened:
        if opened >= k:
            raise SolutionValidationError("estado de construção sem escolha válida")
        return _ConstructionChoices((opened,), True)
    allowed = tuple(range(opened + (1 if opened < k else 0)))
    if not allowed:
        raise SolutionValidationError("estado de construção sem escolha válida")
    return _ConstructionChoices(allowed, False)


def _heuristic_values(
    instance: ProblemInstance,
    prefix: tuple[int, ...],
    choices: tuple[int, ...],
    *,
    k: int,
    weights: ObjectiveWeights,
) -> FloatArray:
    if not choices:
        raise ConfigurationError("heurística requer ao menos uma escolha")
    state = _PartialConstructionState(instance, k=k, weights=weights)
    for lot in prefix:
        state.append(lot)
    return _heuristic_from_state(state, choices)


def _heuristic_from_state(
    state: _PartialConstructionState, choices: tuple[int, ...]
) -> FloatArray:
    if len(state.labels) >= state.instance.n_units:
        raise ConfigurationError("prefixo completo não possui próxima escolha")
    costs = np.empty(len(choices), dtype=np.float64)
    for position, lot in enumerate(choices):
        costs[position] = state.evaluate_choice(lot).total_cost
    if not np.isfinite(costs).all():
        raise ConfigurationError("custo parcial não finito")
    minimum = float(np.min(costs))
    maximum = float(np.max(costs))
    amplitude = maximum - minimum
    if amplitude <= COST_TOLERANCE:
        return np.ones(len(choices), dtype=np.float64)
    eta = 1.0 + (maximum - costs) / amplitude
    if not np.isfinite(eta).all() or np.any(eta < 1.0) or np.any(eta > 2.0):
        raise ConfigurationError("informação heurística fora do intervalo [1, 2]")
    return eta


def _choice_probabilities(
    tau: Any,
    eta: Any,
    *,
    alpha: float,
    beta: float,
) -> FloatArray:
    tau_values = np.asarray(tau, dtype=np.float64)
    eta_values = np.asarray(eta, dtype=np.float64)
    if tau_values.ndim != 1 or eta_values.shape != tau_values.shape or not tau_values.size:
        raise ConfigurationError("tau e eta devem ser vetores não vazios alinhados")
    if (
        not np.isfinite(tau_values).all()
        or not np.isfinite(eta_values).all()
        or np.any(tau_values <= 0.0)
        or np.any(eta_values <= 0.0)
    ):
        raise ConfigurationError("tau e eta devem ser positivos e finitos")
    log_weights = alpha * np.log(tau_values) + beta * np.log(eta_values)
    log_weights -= float(np.max(log_weights))
    raw = np.exp(log_weights)
    denominator = float(np.sum(raw))
    if not isfinite(denominator) or denominator <= 0.0:
        raise ConfigurationError("probabilidades não podem ser normalizadas")
    probabilities = raw / denominator
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities < 0.0)
        or not np.isclose(np.sum(probabilities), 1.0, rtol=0.0, atol=1e-12)
    ):
        raise ConfigurationError("probabilidades inválidas")
    return probabilities


def _initial_pheromone(n_units: int, k: int) -> FloatArray:
    validate_k(k, n_units)
    return np.ones((n_units, k), dtype=np.float64)


def _construct_ant(
    instance: ProblemInstance,
    *,
    k: int,
    weights: ObjectiveWeights,
    tau: FloatArray,
    config: AcoConfig,
    rng: np.random.Generator,
) -> _ConstructedAnt:
    if tau.shape != (instance.n_units, k):
        raise ConfigurationError("tau possui dimensão incompatível com a instância")
    if not np.isfinite(tau).all() or np.any(tau <= 0.0):
        raise ConfigurationError("tau deve ser positivo e finito")
    prefix: list[int] = []
    state = _PartialConstructionState(instance, k=k, weights=weights)
    forced = 0
    probabilistic = 0
    for unit_index in range(instance.n_units):
        available = _construction_choices(
            prefix, n_units=instance.n_units, k=k
        )
        if available.forced:
            selected = available.allowed[0]
            forced += 1
        else:
            eta = _heuristic_from_state(state, available.allowed)
            tau_values = tau[unit_index, list(available.allowed)]
            probabilities = _choice_probabilities(
                tau_values,
                eta,
                alpha=config.alpha,
                beta=config.beta,
            )
            selected = int(rng.choice(available.allowed, p=probabilities))
            probabilistic += 1
        prefix.append(selected)
        state.append(selected)
    solution = validate_solution(prefix, n_units=instance.n_units, k=k)
    canonical = canonicalize_solution(solution, n_units=instance.n_units, k=k)
    if not np.array_equal(solution, canonical):
        raise SolutionValidationError("formiga produziu solução não canônica")
    return _ConstructedAnt(canonical, forced, probabilistic)


def _deposit_amount(cost: float) -> float:
    if not isfinite(cost) or cost < -COST_TOLERANCE or cost > 1.0 + COST_TOLERANCE:
        raise ConfigurationError("custo total fora do intervalo normalizado [0, 1]")
    bounded = min(1.0, max(0.0, cost))
    return 1.0 - bounded


def _update_pheromone(
    tau: FloatArray,
    ants: tuple[_EvaluatedAnt, ...],
    *,
    rho: float,
) -> FloatArray:
    if tau.ndim != 2 or not np.isfinite(tau).all() or np.any(tau <= 0.0):
        raise ConfigurationError("tau deve ser matriz positiva e finita")
    if not ants:
        raise ConfigurationError("atualização requer ao menos uma formiga")
    updated = np.array(tau * (1.0 - rho), dtype=np.float64, copy=True)
    rows = np.arange(tau.shape[0], dtype=np.int64)
    for ant in ants:
        solution = validate_solution(
            ant.solution, n_units=tau.shape[0], k=tau.shape[1]
        )
        updated[rows, solution] += _deposit_amount(ant.evaluation.total_cost)
    if not np.isfinite(updated).all() or np.any(updated <= 0.0):
        raise ConfigurationError("atualização produziu feromônio inválido")
    return updated


@dataclass(slots=True)
class _AcoDiagnostics:
    generations_completed: int = 0
    ants_evaluated: int = 0
    pheromone_updates: int = 0
    forced_assignments: int = 0
    probabilistic_assignments: int = 0
    global_improvements: int = 0

    def publish(self, context: OptimizationContext, tau: FloatArray) -> None:
        context.update_diagnostics(
            generations_completed=self.generations_completed,
            ants_evaluated=self.ants_evaluated,
            pheromone_updates=self.pheromone_updates,
            forced_assignments=self.forced_assignments,
            probabilistic_assignments=self.probabilistic_assignments,
            global_improvements=self.global_improvements,
            final_tau_min=float(np.min(tau)),
            final_tau_max=float(np.max(tau)),
        )


def _incumbent_cost(context: OptimizationContext) -> float | None:
    incumbent = context.incumbent_evaluation
    return None if incumbent is None else incumbent.total_cost


def _aco_search(
    context: OptimizationContext,
    config: AcoConfig,
    *,
    instance: ProblemInstance,
    run_config: RunConfig,
) -> None:
    tau = _initial_pheromone(instance.n_units, run_config.k)
    diagnostics = _AcoDiagnostics()
    diagnostics.publish(context, tau)

    while True:
        generation: list[_EvaluatedAnt] = []
        for _ in range(config.n_ants):
            constructed = _construct_ant(
                instance,
                k=run_config.k,
                weights=run_config.weights,
                tau=tau,
                config=config,
                rng=context.rng,
            )
            before = _incumbent_cost(context)
            try:
                evaluation = context.evaluate(constructed.solution)
            except EvaluationLimitReached as exhausted:
                if not isinstance(exhausted.result, EvaluationResult):
                    raise ConfigurationError("avaliação final não contém decomposição")
                evaluation = exhausted.result
                diagnostics.ants_evaluated += 1
                diagnostics.forced_assignments += constructed.forced_assignments
                diagnostics.probabilistic_assignments += (
                    constructed.probabilistic_assignments
                )
                after = _incumbent_cost(context)
                if before is not None and after is not None and after < before - COST_TOLERANCE:
                    diagnostics.global_improvements += 1
                generation.append(_EvaluatedAnt(constructed.solution, evaluation))
                if len(generation) == config.n_ants:
                    tau = _update_pheromone(tau, tuple(generation), rho=config.rho)
                    diagnostics.generations_completed += 1
                    diagnostics.pheromone_updates += 1
                diagnostics.publish(context, tau)
                raise
            diagnostics.ants_evaluated += 1
            diagnostics.forced_assignments += constructed.forced_assignments
            diagnostics.probabilistic_assignments += constructed.probabilistic_assignments
            after = _incumbent_cost(context)
            if before is not None and after is not None and after < before - COST_TOLERANCE:
                diagnostics.global_improvements += 1
            generation.append(_EvaluatedAnt(constructed.solution, evaluation))
            diagnostics.publish(context, tau)

        tau = _update_pheromone(tau, tuple(generation), rho=config.rho)
        diagnostics.generations_completed += 1
        diagnostics.pheromone_updates += 1
        diagnostics.publish(context, tau)


def run_aco(
    instance: ProblemInstance,
    run_config: RunConfig,
    aco_config: AcoConfig,
) -> OptimizationResult:
    """Executa ACO pelo contrato comum dos otimizadores."""

    if not isinstance(aco_config, AcoConfig):
        raise ConfigurationError("aco_config deve ser AcoConfig")

    def search(context: OptimizationContext, config: AcoConfig) -> None:
        _aco_search(context, config, instance=instance, run_config=run_config)

    return execute_optimizer(
        instance,
        run_config,
        aco_config,
        algorithm="aco",
        search=search,
    )
