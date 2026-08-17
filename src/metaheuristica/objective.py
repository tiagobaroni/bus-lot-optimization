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
    c_demand, cv_demand = _balance_component(instance.demand, labels, k)
    c_production, cv_production = _balance_component(instance.production, labels, k)
    c_territorial = _cut_component(instance.s_territorial, labels)
    c_affinity = _cut_component(instance.w_affinity, labels)
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
