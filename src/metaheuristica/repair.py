"""Reparo determinístico e contabilizado de lotes vazios."""

from __future__ import annotations

from typing import Any

import numpy as np

from metaheuristica.canonical import canonicalize_solution, validate_k
from metaheuristica.errors import (
    BudgetExhausted,
    RepairBudgetExhausted,
    SolutionValidationError,
)
from metaheuristica.evaluator import FitnessEvaluator


def _repairable_labels(solution: Any, *, n_units: int, k: int) -> np.ndarray:
    validate_k(k, n_units)
    labels = np.asarray(solution)
    if labels.ndim != 1 or labels.shape != (n_units,):
        raise SolutionValidationError(f"solução para reparo deve ter dimensão ({n_units},)")
    if not np.issubdtype(labels.dtype, np.integer) or np.issubdtype(labels.dtype, np.bool_):
        raise SolutionValidationError("solução para reparo deve conter rótulos inteiros")
    result = np.array(labels, dtype=np.int64, copy=True)
    if np.any(result < 0) or np.any(result >= k):
        raise SolutionValidationError(f"rótulos devem estar no intervalo de 0 a {k - 1}")
    return result


def repair_empty_lots(solution: Any, evaluator: FitnessEvaluator) -> np.ndarray:
    """Preenche lotes vazios pelo menor custo provisório e devolve forma canônica."""

    labels = _repairable_labels(
        solution,
        n_units=evaluator.instance.n_units,
        k=evaluator.k,
    )
    while True:
        counts = np.bincount(labels, minlength=evaluator.k)
        empty_lots = np.flatnonzero(counts == 0)
        if not empty_lots.size:
            return canonicalize_solution(
                labels,
                n_units=evaluator.instance.n_units,
                k=evaluator.k,
            )

        target = int(empty_lots[0])
        candidates = [
            index for index, source in enumerate(labels) if counts[int(source)] >= 2
        ]
        if not candidates:
            raise SolutionValidationError("não existe unidade doadora para reparar lote vazio")

        best_choice: tuple[float, int, int] | None = None
        for unit_index in candidates:
            source = int(labels[unit_index])
            candidate = labels.copy()
            candidate[unit_index] = target
            try:
                result = evaluator.evaluate_provisional_for_repair(candidate)
            except BudgetExhausted as error:
                raise RepairBudgetExhausted(
                    "orçamento esgotado durante o reparo de lotes vazios"
                ) from error
            choice = (result.total_cost, unit_index, source)
            if best_choice is None or choice < best_choice:
                best_choice = choice

        assert best_choice is not None
        labels[best_choice[1]] = target
