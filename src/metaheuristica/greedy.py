"""Heurística gulosa determinística de referência."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from metaheuristica.canonical import solution_key, validate_k
from metaheuristica.errors import ConfigurationError
from metaheuristica.evaluator import FitnessEvaluator
from metaheuristica.objective import evaluate_solution
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance


COST_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class GreedyTraceStep:
    unit_id: str
    unit_index: int
    lot: int
    partial_cost: float
    evaluations: int


@dataclass(frozen=True, slots=True)
class GreedyResult:
    solution: tuple[int, ...]
    evaluation: EvaluationResult
    evaluations: int
    k: int
    weights: ObjectiveWeights
    processing_order: tuple[str, ...]
    trace: tuple[GreedyTraceStep, ...]


def _processing_indices(instance: ProblemInstance) -> tuple[int, ...]:
    return tuple(
        sorted(
            range(instance.n_units),
            key=lambda index: (-float(instance.production[index]), instance.unit_ids[index]),
        )
    )


def _candidate_is_better(
    *,
    cost: float,
    lot: int,
    best_cost: float,
    best_lot: int,
    accumulated_production: np.ndarray,
) -> bool:
    if cost < best_cost - COST_TOLERANCE:
        return True
    if abs(cost - best_cost) <= COST_TOLERANCE:
        return (float(accumulated_production[lot]), lot) < (
            float(accumulated_production[best_lot]),
            best_lot,
        )
    return False


def run_greedy(
    instance: ProblemInstance,
    *,
    k: int,
    weights: ObjectiveWeights | None = None,
) -> GreedyResult:
    """Constrói uma partição determinística por menor custo parcial."""

    validate_k(k, instance.n_units)
    scenario_weights = weights or ObjectiveWeights()
    order = _processing_indices(instance)
    labels = np.full(instance.n_units, -1, dtype=np.int64)
    accumulated_production = np.zeros(k, dtype=np.float64)

    for lot, unit_index in enumerate(order[:k]):
        labels[unit_index] = lot
        accumulated_production[lot] = instance.production[unit_index]

    budget = k * (instance.n_units - k)
    trace: list[GreedyTraceStep] = []

    if budget == 0:
        evaluations = 0
    else:
        evaluator = FitnessEvaluator(
            instance,
            k=k,
            budget=budget,
            weights=scenario_weights,
            cache_enabled=False,
        )
        processed = list(order[:k])
        for unit_index in order[k:]:
            partial_indices = [*processed, unit_index]
            best_lot: int | None = None
            best_result: EvaluationResult | None = None
            for lot in range(k):
                partial_labels = [int(labels[index]) for index in processed]
                partial_labels.append(lot)
                candidate_result = evaluator.evaluate_partial_for_greedy(
                    partial_indices, partial_labels
                )
                if best_result is None or best_lot is None or _candidate_is_better(
                    cost=candidate_result.total_cost,
                    lot=lot,
                    best_cost=best_result.total_cost,
                    best_lot=best_lot,
                    accumulated_production=accumulated_production,
                ):
                    best_lot = lot
                    best_result = candidate_result

            assert best_lot is not None and best_result is not None
            labels[unit_index] = best_lot
            accumulated_production[best_lot] += instance.production[unit_index]
            processed.append(unit_index)
            trace.append(
                GreedyTraceStep(
                    unit_id=instance.unit_ids[unit_index],
                    unit_index=unit_index,
                    lot=best_lot,
                    # F1-01: este `partial_cost` é, de propósito, o custo na ordem
                    # de construção, isto é o do conjunto induzido permutado pela
                    # ordem decrescente de PU·km. Ele é o valor que decidiu a
                    # escolha do lote e por isso tem de continuar sendo o
                    # registrado aqui. No último passo ele difere em bits da
                    # avaliação publicada, que é calculada na ordem natural da
                    # instância; essa diferença é esperada e não é defeito.
                    partial_cost=best_result.total_cost,
                    evaluations=evaluator.evaluations,
                )
            )

        evaluations = evaluator.evaluations
        if evaluations != budget:
            raise ConfigurationError(
                f"contador guloso divergente: esperado {budget}, obtido {evaluations}"
            )

    canonical_solution = solution_key(labels, n_units=instance.n_units, k=k)
    if len(trace) != instance.n_units - k:
        raise ConfigurationError("rastreio guloso possui tamanho divergente")
    # F1-01: a avaliação publicada é a da solução canônica, na ordem natural da
    # instância, pelo mesmo caminho de `evaluate_solution`. A última avaliação
    # parcial da construção avaliava a instância inteira permutada pela ordem de
    # processamento, e `np.bincount` e `np.triu_indices` acumulam na ordem do
    # vetor e da matriz recebidos, de modo que o par publicado não era
    # autoconsistente em 18 de 18 combinações oficiais. Esta chamada não passa
    # pelo `FitnessEvaluator` e por isso não debita unidade alguma de orçamento,
    # como exige a seção 13.3 da formulação ao dizer que a última avaliação é
    # "reutilizada sem nova avaliação": o contador segue exatamente K(N-K).
    final_evaluation = evaluate_solution(
        instance, canonical_solution, k=k, weights=scenario_weights
    )
    return GreedyResult(
        solution=canonical_solution,
        evaluation=final_evaluation,
        evaluations=evaluations,
        k=k,
        weights=scenario_weights,
        processing_order=tuple(instance.unit_ids[index] for index in order),
        trace=tuple(trace),
    )
