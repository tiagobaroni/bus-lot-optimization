from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from metaheuristica import (
    EvaluationResult,
    ObjectiveWeights,
    ProblemInstance,
    SolutionValidationError,
)
from metaheuristica import objective
from metaheuristica.instances import load_tiny_instance
from metaheuristica.objective import (
    _cut_fraction,
    _cut_fractions,
    _evaluate_partial_assignment,
    _evaluate_provisional_solution,
    _evaluate_total_costs,
    _triangular_indices,
    evaluate_solution,
)


INSTANCES_DIR = Path(__file__).parents[1] / "data" / "instances"


def test_tiny_documented_optimum_has_zero_cost() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    result = evaluate_solution(instance, [0, 0, 1, 1], k=2)
    assert result.total_cost == 0.0
    assert result.c_demand == result.c_production == 0.0
    assert result.c_territorial == result.c_affinity == 0.0


def test_tiny_crossed_partition_cuts_all_relationships() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    result = evaluate_solution(instance, [0, 1, 0, 1], k=2)
    assert result.c_demand == 0.0
    assert result.c_production == 0.25
    assert result.c_territorial == result.c_affinity == 1.0
    assert result.total_cost == 0.5625


def test_balance_uses_population_standard_deviation() -> None:
    zero = np.zeros((2, 2))
    instance = ProblemInstance(
        name="populacional",
        unit_ids=("A", "B"),
        demand=[10.0, 30.0],
        production=[100.0, 300.0],
        s_territorial=zero,
        t_terminal=zero,
        i_integration=zero,
        o_market=zero,
    )
    result = evaluate_solution(instance, [0, 1], k=2)
    assert result.cv_demand == pytest.approx(0.5, rel=1e-12, abs=1e-12)
    assert result.cv_production == pytest.approx(0.5, rel=1e-12, abs=1e-12)
    assert result.c_demand == pytest.approx(1.0 / 3.0, rel=1e-12, abs=1e-12)
    assert result.c_production == pytest.approx(1.0 / 3.0, rel=1e-12, abs=1e-12)
    assert result.c_territorial == result.c_affinity == 0.0


def test_equivalent_labelings_have_identical_decomposition() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    first = evaluate_solution(instance, [0, 0, 1, 1], k=2)
    second = evaluate_solution(instance, [1, 1, 0, 0], k=2)
    assert first == second


def test_nonuniform_weights_are_applied_without_changing_components() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    weights = ObjectiveWeights(0.0, 0.0, 0.75, 0.25)
    result = evaluate_solution(instance, [0, 1, 0, 1], k=2, weights=weights)
    assert result.total_cost == 1.0


def test_public_evaluation_rejects_empty_lot_but_provisional_allows_it() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    with pytest.raises(SolutionValidationError, match="vazios"):
        evaluate_solution(instance, [0, 0, 0, 0], k=2)
    provisional = _evaluate_provisional_solution(
        instance, [0, 0, 0, 0], k=2, weights=ObjectiveWeights()
    )
    assert np.isfinite(provisional.total_cost)


def test_lote_vazio_de_rotulo_alto_mantem_os_totais_com_k_posicoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F2-08: o lote vazio de rótulo alto continua ocupando posição nos totais.

    `docs/formulation.md` seção 13.2 exige que o equilíbrio mantenha os `K` lotes
    nos vetores de totais. Quem garante isso é o `minlength=k` das duas chamadas
    de `np.bincount` em `_evaluate_arrays`: sem ele o vetor encurta até o maior
    rótulo presente e o lote vazio some da média e do desvio padrão.

    A configuração escolhida torna a diferença máxima. Com `K=3` e o rótulo 2
    ausente, os totais são `[20, 20, 0]` e `[300, 300, 0]`, cujo coeficiente de
    variação populacional é `1/raiz(2)`; truncados para duas posições, os dois
    ficam perfeitamente equilibrados e o coeficiente cai a zero, o que faria a
    avaliação provisória do reparo anunciar custo zero, isto é o ótimo
    documentado, para uma solução que deixa um lote inteiro vazio.
    """

    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    capturados: list[tuple[np.ndarray, np.ndarray]] = []
    original = objective._evaluate_aggregates

    def registrando(**agregados: Any) -> EvaluationResult:
        capturados.append((agregados["demand_totals"], agregados["production_totals"]))
        return original(**agregados)

    monkeypatch.setattr(objective, "_evaluate_aggregates", registrando)
    result = _evaluate_provisional_solution(
        instance, [0, 0, 1, 1], k=3, weights=ObjectiveWeights()
    )

    # A captura é conferida antes de ser lida: um caminho que deixasse de passar
    # por `_evaluate_aggregates` esvaziaria a lista e o caso passaria por vácuo.
    assert len(capturados) == 1
    demand_totals, production_totals = capturados[0]
    assert demand_totals.shape == (3,)
    assert production_totals.shape == (3,)
    assert list(demand_totals) == [20.0, 20.0, 0.0]
    assert list(production_totals) == [300.0, 300.0, 0.0]

    # O equilíbrio é calculado sobre as três posições, e não sobre as duas
    # ocupadas: com duas o coeficiente de variação seria exatamente zero.
    esperado_cv = float(np.sqrt(0.5))
    esperado_componente = float(np.sqrt(2.0) - 1.0)
    assert result.cv_demand == pytest.approx(esperado_cv, rel=1e-12, abs=1e-12)
    assert result.cv_production == pytest.approx(esperado_cv, rel=1e-12, abs=1e-12)
    assert result.c_demand == pytest.approx(esperado_componente, rel=1e-12, abs=1e-12)
    assert result.c_production == pytest.approx(esperado_componente, rel=1e-12, abs=1e-12)
    assert result.c_territorial == result.c_affinity == 0.0
    assert result.total_cost == pytest.approx(
        0.5 * esperado_componente, rel=1e-12, abs=1e-12
    )


def test_partial_assignment_uses_only_the_induced_subproblem() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    partial = _evaluate_partial_assignment(
        instance,
        [0, 2],
        [0, 1],
        k=2,
        weights=ObjectiveWeights(),
    )
    assert partial.c_demand == partial.c_production == 0.0
    assert partial.c_territorial == partial.c_affinity == 0.0
    assert partial.total_cost == 0.0


def test_partial_assignment_equals_public_result_when_complete() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    solution = [0, 0, 1, 1]
    partial = _evaluate_partial_assignment(
        instance,
        [0, 1, 2, 3],
        solution,
        k=2,
        weights=ObjectiveWeights(),
    )
    assert partial == evaluate_solution(instance, solution, k=2)


@pytest.mark.parametrize(
    ("indices", "labels", "message"),
    [
        ([0, 0], [0, 1], "duplicatas"),
        ([0, 4], [0, 1], "fora do intervalo"),
        ([0, 1], [0], "alinhados"),
    ],
)
def test_invalid_partial_assignment_is_rejected(
    indices: list[int], labels: list[int], message: str
) -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    with pytest.raises(SolutionValidationError, match=message):
        _evaluate_partial_assignment(
            instance,
            indices,
            labels,
            k=2,
            weights=ObjectiveWeights(),
        )


def test_triangular_indices_are_shared_and_read_only() -> None:
    """O cache memorizado de F1-06 devolve o mesmo objeto, e ele é imutável.

    `_triangular_indices` é memorizado por tamanho e os dois vetores são
    entregues a todos os chamadores. Sem a marcação somente-leitura, uma
    alteração no lugar feita por um chamador contaminaria em silêncio todos os
    demais, e a ordem dos pares, que sustenta a identidade bit a bit dos
    somatórios, mudaria sem que teste algum reclamasse.
    """

    first_row, first_column = _triangular_indices(7)
    second_row, second_column = _triangular_indices(7)
    assert first_row is second_row
    assert first_column is second_column
    assert first_row.flags.writeable is False
    assert first_column.flags.writeable is False
    with pytest.raises(ValueError):
        first_row[0] = 99
    expected_row, expected_column = np.triu_indices(7, k=1)
    assert first_row.tolist() == expected_row.tolist()
    assert first_column.tolist() == expected_column.tolist()


def test_cut_fractions_reproduces_the_scalar_deviation_for_a_null_denominator() -> None:
    """O desvio de denominador nulo da versão em lote é o mesmo do escalar.

    O ramo `denominator == 0.0` de `_cut_fractions` não é percorrido pelas
    quatro instâncias congeladas, porque o denominador é o total acumulado e a
    primeira linha de `s_territorial` e de `w_affinity` já é não nula. O oráculo
    de identidade bit a bit da construção, portanto, nunca o exercita, e sem
    este teste a igualdade com `_cut_fraction` seria afirmada por leitura.
    """

    numerators = np.array([0.0, 1.5, -2.25, 1e300], dtype=np.float64)
    obtained = _cut_fractions(numerators, 0.0)
    expected = [_cut_fraction(float(value), 0.0) for value in numerators]
    assert obtained.dtype == np.float64
    assert [float(value).hex() for value in obtained] == [value.hex() for value in expected]
    positive = _cut_fractions(numerators, 4.0)
    expected_positive = [_cut_fraction(float(value), 4.0) for value in numerators]
    assert [float(value).hex() for value in positive] == [
        value.hex() for value in expected_positive
    ]


def test_total_costs_reject_a_totals_matrix_that_is_not_twice_the_alternatives() -> None:
    """A guarda de contrato interno de `_evaluate_total_costs` recusa desalinhamento.

    `totals_matrix` tem de trazer `2m` linhas, as `m` de demanda seguidas das
    `m` de produção. Um número ímpar de linhas, ou qualquer contagem que não
    seja o dobro das alternativas, faria as duas metades se sobreporem e o
    resultado sairia errado em silêncio.
    """

    cuts = np.array([0.25, 0.5], dtype=np.float64)
    matrix = np.ones((3, 4), dtype=np.float64, order="C")
    with pytest.raises(SolutionValidationError, match="desalinhada"):
        _evaluate_total_costs(
            totals_matrix=matrix,
            territorial_cuts=cuts,
            territorial_total=1.0,
            affinity_cuts=cuts,
            affinity_total=1.0,
            weights=ObjectiveWeights(),
        )
