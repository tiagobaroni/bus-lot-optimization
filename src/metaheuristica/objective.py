"""Função objetivo única e compartilhada por todos os métodos."""

from __future__ import annotations

from functools import lru_cache
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


@lru_cache(maxsize=None)
def _triangular_indices(size: int) -> tuple[np.ndarray, np.ndarray]:
    """Pares do triângulo superior, memorizados por tamanho.

    F1-06: `_evaluate_arrays` recomputava `np.triu_indices` a cada avaliação, o
    que em `N=150` são 11.175 pares e dois vetores `int64` de 11.175 posições
    alocados por chamada, em cada uma das 150.000 avaliações da execução. A
    memorização é por **tamanho** e não por instância porque o caminho parcial
    do guloso avalia submatrizes induzidas de todos os tamanhos de 1 a `N`, e
    uma pré-computação presa à instância quebraria esse caminho.

    A ordem dos pares é exatamente a de `np.triu_indices`, logo a ordem dos
    somatórios não muda e a identidade bit a bit é preservada. Os vetores saem
    somente-leitura porque são compartilhados por todos os chamadores; nenhum
    deles os altera hoje, e a marcação impede que uma refatoração futura passe
    a alterá-los em silêncio.
    """

    row, column = np.triu_indices(size, k=1)
    row.flags.writeable = False
    column.flags.writeable = False
    return row, column


def _balance_totals_component(totals: np.ndarray) -> tuple[float, float]:
    mean = float(np.mean(totals))
    cv = float(np.std(totals, ddof=0) / mean)
    return cv / (1.0 + cv), cv


def _balance_totals_matrix(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Réplica vetorizada de `_balance_totals_component`, uma linha por alternativa.

    Variante O4 do achado F4-1. Reproduz a ordem de operações de
    `numpy._core._methods._mean` e `._var` com `ddof=0`, em vez de trocar
    `np.mean` e `np.std` por aritmética `float` ingênua: soma por
    `np.add.reduce`, divisão pelo número de lotes, subtração da média,
    quadrado no lugar, segunda soma por `np.add.reduce`, divisão e raiz. O
    resultado é bit a bit igual ao de `_balance_totals_component` aplicado a
    cada linha isoladamente, e é isso que
    `tests/test_aco.py::test_batched_choice_costs_reproduce_the_reference_bit_by_bit`
    fixa contra a implementação de referência.
    """

    # A identidade bit a bit com np.mean/np.std depende da ordem de memória: em
    # ordem Fortran a redução diverge em até 44% das linhas com K=8. Sem esta
    # asserção, uma refatoração futura que mude a ordem quebra a identidade em
    # silêncio, sem que teste algum reclame.
    assert matrix.flags["C_CONTIGUOUS"], "a redução exige matriz contígua em ordem C"
    count = matrix.shape[1]
    means = np.add.reduce(matrix, axis=1) / count
    deviations = np.subtract(matrix, means[:, np.newaxis])
    np.square(deviations, out=deviations)
    # A segunda redução corre sobre os desvios, e não sobre a matriz de entrada:
    # a mesma exigência de ordem C vale para ela, e por isso é conferida aqui.
    assert deviations.flags["C_CONTIGUOUS"], "a redução exige matriz contígua em ordem C"
    variances = np.add.reduce(deviations, axis=1) / count
    cv = np.sqrt(variances) / means
    return cv / (1.0 + cv), cv


def _cut_fractions(numerators: np.ndarray, denominator: float) -> np.ndarray:
    """Versão em lote de `_cut_fraction`, com o mesmo desvio de denominador nulo."""

    if denominator == 0.0:
        return np.zeros(len(numerators), dtype=np.float64)
    return numerators / denominator


def _evaluate_total_costs(
    *,
    totals_matrix: np.ndarray,
    territorial_cuts: np.ndarray,
    territorial_total: float,
    affinity_cuts: np.ndarray,
    affinity_total: float,
    weights: ObjectiveWeights,
) -> np.ndarray:
    """Custos totais de várias alternativas de uma só vez, sem `EvaluationResult`.

    `totals_matrix` tem `2m` linhas de `K` colunas: as `m` primeiras são os
    totais de demanda de cada alternativa e as `m` seguintes os de produção. As
    duas metades entram na mesma matriz para que as reduções de demanda e de
    produção custem um único despacho de NumPy em vez de dois. As linhas são
    independentes entre si e cada uma é reduzida sobre as suas próprias `K`
    posições contíguas, de modo que empilhá-las não altera nenhuma soma.

    Contrato: para cada alternativa `i`, o valor devolvido é bit a bit igual ao
    `total_cost` que `_evaluate_aggregates` produziria com os agregados dessa
    alternativa. Os denominadores de corte não dependem do lote escolhido e por
    isso entram como escalares, calculados uma única vez por posição da
    construção. O consumidor, a informação heurística do ACO, usa apenas
    `total_cost`, de modo que os sete campos de `EvaluationResult` e a
    verificação de finitude do seu `__post_init__` não são construídos aqui; a
    finitude continua conferida por `_heuristic_from_state`.
    """

    count = len(territorial_cuts)
    if totals_matrix.shape[0] != 2 * count:
        raise SolutionValidationError("matriz de totais desalinhada com as alternativas")
    balance, _ = _balance_totals_matrix(totals_matrix)
    return (
        weights.demand * balance[:count]
        + weights.production * balance[count:]
        + weights.territorial * _cut_fractions(territorial_cuts, territorial_total)
        + weights.affinity * _cut_fractions(affinity_cuts, affinity_total)
    )


def _cut_fraction(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _evaluate_aggregates(
    *,
    demand_totals: np.ndarray,
    production_totals: np.ndarray,
    territorial_cut: float,
    territorial_total: float,
    affinity_cut: float,
    affinity_total: float,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    """Avalia agregados equivalentes, usados na construção incremental do ACO."""

    c_demand, cv_demand = _balance_totals_component(demand_totals)
    c_production, cv_production = _balance_totals_component(production_totals)
    c_territorial = _cut_fraction(territorial_cut, territorial_total)
    c_affinity = _cut_fraction(affinity_cut, affinity_total)
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
    row, column = _triangular_indices(len(labels))
    territorial_values = s_territorial[row, column]
    affinity_values = w_affinity[row, column]
    cut = labels[row] != labels[column]
    return _evaluate_aggregates(
        demand_totals=np.bincount(labels, weights=demand, minlength=k),
        production_totals=np.bincount(labels, weights=production, minlength=k),
        territorial_cut=float(np.sum(territorial_values[cut])),
        territorial_total=float(np.sum(territorial_values)),
        affinity_cut=float(np.sum(affinity_values[cut])),
        affinity_total=float(np.sum(affinity_values)),
        weights=weights,
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
