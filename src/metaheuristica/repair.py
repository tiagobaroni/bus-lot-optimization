"""Reparo determinístico e contabilizado de lotes vazios."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np

from metaheuristica.canonical import canonicalize_solution, validate_k
from metaheuristica.errors import (
    BudgetExhausted,
    EvaluationLimitReached,
    RepairBudgetExhausted,
    SolutionValidationError,
)
from metaheuristica.problem import EvaluationResult, ProblemInstance


class RepairEvaluator(Protocol):
    """Interface mínima necessária para executar o reparo comum."""

    @property
    def instance(self) -> ProblemInstance: ...

    @property
    def k(self) -> int: ...

    def evaluate_provisional_for_repair(self, solution: Any) -> EvaluationResult: ...


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


def repair_empty_lots(solution: Any, evaluator: RepairEvaluator) -> np.ndarray:
    """Preenche lotes vazios pelo menor custo provisório e devolve forma canônica."""

    repaired, _ = repair_empty_lots_with_evaluation(solution, evaluator)
    return repaired


def repair_empty_lots_with_evaluation(
    solution: Any, evaluator: RepairEvaluator
) -> tuple[np.ndarray, EvaluationResult | None]:
    """Repara e devolve também a avaliação vencedora da última rodada.

    A4: o estado final do reparo é exatamente o candidato vencedor da última
    rodada, que já foi avaliado por `evaluate_provisional_for_repair` pela mesma
    `_evaluate_labels` da função objetivo. Devolver essa avaliação permite ao
    chamador reaproveitá-la em vez de pagar uma segunda unidade de orçamento
    pela mesma solução. A avaliação é `None` quando o estado recebido já é
    viável e nenhuma unidade de orçamento foi consumida.
    """

    labels = _repairable_labels(
        solution,
        n_units=evaluator.instance.n_units,
        k=evaluator.k,
    )
    winner: EvaluationResult | None = None
    while True:
        counts = np.bincount(labels, minlength=evaluator.k)
        empty_lots = np.flatnonzero(counts == 0)
        if not empty_lots.size:
            return (
                canonicalize_solution(
                    labels,
                    n_units=evaluator.instance.n_units,
                    k=evaluator.k,
                ),
                winner,
            )

        target = int(empty_lots[0])
        candidates = [
            index for index, source in enumerate(labels) if counts[int(source)] >= 2
        ]
        if not candidates:
            raise SolutionValidationError("não existe unidade doadora para reparar lote vazio")

        best_choice: tuple[float, int, int] | None = None
        best_evaluation: EvaluationResult | None = None
        for candidate_index, unit_index in enumerate(candidates):
            source = int(labels[unit_index])
            candidate = labels.copy()
            candidate[unit_index] = target
            try:
                result = evaluator.evaluate_provisional_for_repair(candidate)
            except EvaluationLimitReached as error:
                if not isinstance(error.result, EvaluationResult):
                    raise RepairBudgetExhausted(
                        "orçamento esgotado durante o reparo de lotes vazios"
                    ) from error
                result = error.result
                exhausted_after_candidate = True
            except BudgetExhausted as error:
                raise RepairBudgetExhausted(
                    "orçamento esgotado durante o reparo de lotes vazios"
                ) from error
            else:
                exhausted_after_candidate = False
            choice = (result.total_cost, unit_index, source)
            if best_choice is None or choice < best_choice:
                best_choice = choice
                best_evaluation = result
            if exhausted_after_candidate and candidate_index < len(candidates) - 1:
                raise RepairBudgetExhausted(
                    "orçamento esgotado durante o reparo de lotes vazios"
                )

        assert best_choice is not None
        labels[best_choice[1]] = target
        winner = best_evaluation
        if exhausted_after_candidate:
            counts = np.bincount(labels, minlength=evaluator.k)
            if np.any(counts == 0):
                raise RepairBudgetExhausted(
                    "orçamento esgotado durante o reparo de lotes vazios"
                )
            return (
                canonicalize_solution(
                    labels,
                    n_units=evaluator.instance.n_units,
                    k=evaluator.k,
                ),
                winner,
            )
