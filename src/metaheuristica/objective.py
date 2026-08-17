"""Função objetivo única e compartilhada por todos os métodos."""

from __future__ import annotations

from typing import Any

import numpy as np

from metaheuristica.canonical import validate_k, validate_solution
from metaheuristica.errors import SolutionValidationError
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance


def _provisional_labels(solution: Any, *, n_units: int, k: int) -> np.ndarray:
    """Valida rótulos e intervalo, permitindo lotes vazios somente internamente."""

    validate_k(k, n_units)
    labels = np.asarray(solution)
    if labels.ndim != 1 or labels.shape != (n_units,):
        raise SolutionValidationError(f"solução provisória deve ter dimensão ({n_units},)")
    if not np.issubdtype(labels.dtype, np.integer) or np.issubdtype(labels.dtype, np.bool_):
        raise SolutionValidationError("solução provisória deve conter rótulos inteiros")
    result = np.array(labels, dtype=np.int64, copy=True)
    if np.any(result < 0) or np.any(result >= k):
        raise SolutionValidationError(f"rótulos devem estar no intervalo de 0 a {k - 1}")
    return result


def _balance_component(values: np.ndarray, labels: np.ndarray, k: int) -> tuple[float, float]:
    totals = np.bincount(labels, weights=values, minlength=k)
    mean = float(np.mean(totals))
    cv = float(np.std(totals, ddof=0) / mean)
    return cv / (1.0 + cv), cv


def _cut_component(matrix: np.ndarray, labels: np.ndarray) -> float:
    row, column = np.triu_indices(len(labels), k=1)
    weights = matrix[row, column]
    denominator = float(np.sum(weights))
    if denominator == 0.0:
        return 0.0
    cut = labels[row] != labels[column]
    return float(np.sum(weights[cut]) / denominator)


def _evaluate_labels(
    instance: ProblemInstance,
    labels: np.ndarray,
    *,
    k: int,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    return _evaluate_arrays(
        demand=instance.demand,
        production=instance.production,
        s_territorial=instance.s_territorial,
        w_affinity=instance.w_affinity,
        labels=labels,
        k=k,
        weights=weights,
    )


def _evaluate_arrays(
    *,
    demand: np.ndarray,
    production: np.ndarray,
    s_territorial: np.ndarray,
    w_affinity: np.ndarray,
    labels: np.ndarray,
    k: int,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    c_demand, cv_demand = _balance_component(demand, labels, k)
    c_production, cv_production = _balance_component(production, labels, k)
    c_territorial = _cut_component(s_territorial, labels)
    c_affinity = _cut_component(w_affinity, labels)
    total_cost = (
        weights.demand * c_demand
        + weights.production * c_production
        + weights.territorial * c_territorial
        + weights.affinity * c_affinity
    )
    return EvaluationResult(
        total_cost=total_cost,
        c_demand=c_demand,
        c_production=c_production,
        c_territorial=c_territorial,
        c_affinity=c_affinity,
        cv_demand=cv_demand,
        cv_production=cv_production,
    )


def _partial_inputs(
    instance: ProblemInstance,
    processed_indices: Any,
    labels: Any,
    *,
    k: int,
) -> tuple[np.ndarray, np.ndarray]:
    validate_k(k, instance.n_units)
    indices = np.asarray(processed_indices)
    partial_labels = np.asarray(labels)
    if indices.ndim != 1 or not indices.size:
        raise SolutionValidationError("índices parciais devem formar um vetor não vazio")
    if not np.issubdtype(indices.dtype, np.integer) or np.issubdtype(
        indices.dtype, np.bool_
    ):
        raise SolutionValidationError("índices parciais devem ser inteiros")
    indices = np.array(indices, dtype=np.int64, copy=True)
    if np.any(indices < 0) or np.any(indices >= instance.n_units):
        raise SolutionValidationError("índice parcial fora do intervalo da instância")
    if len(np.unique(indices)) != len(indices):
        raise SolutionValidationError("índices parciais contêm duplicatas")
    if partial_labels.ndim != 1 or partial_labels.shape != indices.shape:
        raise SolutionValidationError("rótulos parciais devem estar alinhados aos índices")
    if not np.issubdtype(partial_labels.dtype, np.integer) or np.issubdtype(
        partial_labels.dtype, np.bool_
    ):
        raise SolutionValidationError("rótulos parciais devem ser inteiros")
    partial_labels = np.array(partial_labels, dtype=np.int64, copy=True)
    if np.any(partial_labels < 0) or np.any(partial_labels >= k):
        raise SolutionValidationError(f"rótulos devem estar no intervalo de 0 a {k - 1}")
    return indices, partial_labels


def _evaluate_partial_assignment(
    instance: ProblemInstance,
    processed_indices: Any,
    labels: Any,
    *,
    k: int,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    """Avalia o subproblema induzido, exclusivamente para o baseline guloso."""

    indices, partial_labels = _partial_inputs(
        instance, processed_indices, labels, k=k
    )
    induced = np.ix_(indices, indices)
    return _evaluate_arrays(
        demand=instance.demand[indices],
        production=instance.production[indices],
        s_territorial=instance.s_territorial[induced],
        w_affinity=instance.w_affinity[induced],
        labels=partial_labels,
        k=k,
        weights=weights,
    )


def evaluate_solution(
    instance: ProblemInstance,
    solution: Any,
    *,
    k: int,
    weights: ObjectiveWeights | None = None,
) -> EvaluationResult:
    """Valida uma solução viável e calcula todos os componentes numa chamada."""

    labels = validate_solution(solution, n_units=instance.n_units, k=k)
    return _evaluate_labels(instance, labels, k=k, weights=weights or ObjectiveWeights())


def _evaluate_provisional_solution(
    instance: ProblemInstance,
    solution: Any,
    *,
    k: int,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    """Calcula custo com lotes vazios, exclusivamente para o reparador."""

    labels = _provisional_labels(solution, n_units=instance.n_units, k=k)
    return _evaluate_labels(instance, labels, k=k, weights=weights)
