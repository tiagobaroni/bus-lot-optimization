from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    FitnessEvaluator,
    ProblemInstance,
    RepairBudgetExhausted,
    RunConfig,
    evaluate_solution,
)
from metaheuristica.canonical import canonicalize_solution
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.evaluator import _viable_key
from metaheuristica.metrics import ConvergenceRecorder
from metaheuristica.repair import (
    repair_empty_lots,
    repair_empty_lots_with_evaluation,
)


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")
EVALUATION_FIELDS = (
    "total_cost",
    "c_demand",
    "c_production",
    "c_territorial",
    "c_affinity",
    "cv_demand",
    "cv_production",
)


def equal_instance(n_units: int) -> ProblemInstance:
    zero = np.zeros((n_units, n_units))
    return ProblemInstance(
        name="empates",
        unit_ids=tuple(chr(ord("A") + index) for index in range(n_units)),
        demand=np.ones(n_units),
        production=np.ones(n_units),
        s_territorial=zero,
        t_terminal=zero,
        i_integration=zero,
        o_market=zero,
    )


def test_feasible_solution_is_only_canonicalized_without_evaluation() -> None:
    evaluator = FitnessEvaluator(TINY, k=2, budget=1)
    repaired = repair_empty_lots([1, 1, 0, 0], evaluator)
    assert repaired.tolist() == [0, 0, 1, 1]
    assert evaluator.evaluations == 0


def test_single_empty_lot_evaluates_every_eligible_donor() -> None:
    evaluator = FitnessEvaluator(TINY, k=2, budget=4)
    repaired = repair_empty_lots([0, 0, 0, 0], evaluator)
    assert len(set(repaired.tolist())) == 2
    assert evaluator.evaluations == 4
    assert not repaired.flags.writeable


def test_multiple_empty_lots_are_repaired_in_order() -> None:
    evaluator = FitnessEvaluator(equal_instance(4), k=3, budget=7)
    repaired = repair_empty_lots([0, 0, 0, 0], evaluator)
    assert repaired.tolist() == [0, 1, 2, 2]
    assert evaluator.evaluations == 7


def test_tie_is_broken_by_lowest_unit_index() -> None:
    evaluator = FitnessEvaluator(equal_instance(3), k=2, budget=3)
    repaired = repair_empty_lots([0, 0, 0], evaluator)
    assert repaired.tolist() == [0, 1, 1]


def test_budget_exhaustion_discards_partial_repair() -> None:
    evaluator = FitnessEvaluator(TINY, k=2, budget=2)
    with pytest.raises(RepairBudgetExhausted, match="durante o reparo"):
        repair_empty_lots([0, 0, 0, 0], evaluator)
    assert evaluator.evaluations == 2


def unbalanced_instance() -> ProblemInstance:
    """Instância de quatro unidades cujo reparo tem vencedor único.

    Demanda e produção proporcionais e distintas fazem as quatro candidaturas
    de reparo terem custos estritamente diferentes, o que remove os empates de
    `tiny_manual`, onde a simetria da produção faz duas doadoras empatarem.
    """

    zero = np.zeros((4, 4))
    sizes = np.array([1.0, 2.0, 4.0, 8.0])
    return ProblemInstance(
        name="desequilibrada",
        unit_ids=("A", "B", "C", "D"),
        demand=sizes,
        production=sizes,
        s_territorial=zero,
        t_terminal=zero,
        i_integration=zero,
        o_market=zero,
    )


def test_viable_repair_evaluation_becomes_the_incumbent() -> None:
    """Achado A3: a avaliação de reparo integralmente viável compete pelo incumbente.

    O estado `[0, 0, 0, 0]` com `K=2` tem um lote vazio, logo cada candidata do
    reparo já é uma solução completa e viável. A vencedora, `[0, 0, 0, 1]`, é
    mais barata que o incumbente estabelecido antes do reparo, e nenhuma das
    outras três candidatas é. Sob a forma anterior, que notificava toda
    avaliação de reparo como inelegível, o incumbente não se movia.
    """

    instance = unbalanced_instance()
    recorder = ConvergenceRecorder(RunConfig(k=2, seed=1, budget=100).thresholds)
    evaluator = FitnessEvaluator(instance, k=2, budget=100, observer=recorder.observe)
    evaluator.evaluate([0, 1, 0, 1])
    assert recorder.incumbent_solution == (0, 1, 0, 1)
    initial_cost = recorder.incumbent_evaluation.total_cost

    repaired = repair_empty_lots([0, 0, 0, 0], evaluator)

    assert repaired.tolist() == [0, 0, 0, 1]
    assert recorder.incumbent_solution == (0, 0, 0, 1)
    assert recorder.incumbent_evaluation.total_cost < initial_cost
    expected = evaluate_solution(instance, [0, 0, 0, 1], k=2)
    assert recorder.incumbent_evaluation.total_cost == expected.total_cost


def test_repair_state_with_an_empty_lot_stays_ineligible() -> None:
    """O lado negativo do achado A3: estado incompleto não pode virar incumbente.

    Com `K=3` e quatro unidades, `[0, 0, 0, 0]` tem dois lotes vazios, e cada
    candidata da primeira rodada ainda deixa um lote vazio. Nenhuma delas é
    solução, então nenhuma pode ser notificada com chave nem disputar o
    incumbente. Sem este caso, a asserção do teste acima seria compatível com
    tornar elegível toda avaliação de reparo.
    """

    instance = unbalanced_instance()
    observed: list[tuple[tuple[int, ...] | None, bool]] = []

    def spy(
        evaluations: int,
        solution: tuple[int, ...] | None,
        result: object,
        eligible: bool,
    ) -> None:
        observed.append((solution, eligible))

    evaluator = FitnessEvaluator(instance, k=3, budget=100, observer=spy)
    repaired = repair_empty_lots([0, 0, 0, 0], evaluator)

    assert len(set(repaired.tolist())) == 3
    first_round = observed[:4]
    assert len(first_round) == 4
    assert all(key is None and not eligible for key, eligible in first_round)


def test_viable_key_separates_complete_states_from_states_with_empty_lots() -> None:
    """Os dois lados da guarda nova do achado A3.

    O estado completo produz chave canônica, e o estado com lote vazio produz
    `None`. Sem o segundo caso, a guarda seria compatível com produzir chave
    para qualquer estado; sem o primeiro, seria compatível com nunca produzir
    chave, que é a forma anterior ao pacote.
    """

    instance = unbalanced_instance()
    assert _viable_key(instance, [1, 0, 0, 0], k=2) == (0, 1, 1, 1)
    assert _viable_key(instance, [0, 0, 0, 0], k=2) is None
    assert _viable_key(instance, [0, 1, 2, 0], k=3) == (0, 1, 2, 0)
    assert _viable_key(instance, [0, 1, 1, 0], k=3) is None


def test_repair_returns_the_winning_provisional_evaluation() -> None:
    """A avaliação devolvida é a do estado final, e não a de outra candidata."""

    instance = unbalanced_instance()
    evaluator = FitnessEvaluator(instance, k=2, budget=4)
    repaired, winner = repair_empty_lots_with_evaluation([0, 0, 0, 0], evaluator)

    assert repaired.tolist() == [0, 0, 0, 1]
    assert winner is not None
    expected = evaluate_solution(instance, [0, 0, 0, 1], k=2)
    # Igualdade bit a bit nos sete campos, e não só no custo total: o
    # reaproveitamento publica esta avaliação ao lado da solução canônica, logo
    # o par precisa ser exatamente o que a reavaliação da solução publicada
    # produz. Comparar apenas `total_cost` deixaria passar divergência de
    # último bit nos componentes.
    assert all(
        getattr(winner, field).hex() == getattr(expected, field).hex()
        for field in EVALUATION_FIELDS
    )
    assert evaluator.evaluations == 4


def test_repair_without_empty_lots_returns_no_evaluation() -> None:
    """O lado negativo: sem reparo não há avaliação a reaproveitar."""

    evaluator = FitnessEvaluator(TINY, k=2, budget=1)
    repaired, winner = repair_empty_lots_with_evaluation([1, 1, 0, 0], evaluator)

    assert repaired.tolist() == [0, 0, 1, 1]
    assert winner is None
    assert evaluator.evaluations == 0


def test_multiple_rounds_return_the_evaluation_of_the_last_round() -> None:
    """Com mais de uma rodada, a vencedora devolvida é a da última.

    Sem esta asserção, devolver a vencedora da primeira rodada passaria
    despercebido, e o reaproveitamento publicaria a avaliação de um estado que
    ainda tinha lote vazio.
    """

    instance = unbalanced_instance()
    evaluator = FitnessEvaluator(instance, k=3, budget=100)
    repaired, winner = repair_empty_lots_with_evaluation([0, 0, 0, 0], evaluator)

    assert len(set(repaired.tolist())) == 3
    assert evaluator.evaluations == 7
    assert winner is not None
    expected = evaluate_solution(instance, repaired, k=3)
    assert all(
        getattr(winner, field).hex() == getattr(expected, field).hex()
        for field in EVALUATION_FIELDS
    )


ARTESP_20_RAW_LABELS = (
    2, 1, 1, 0, 0, 0, 0, 0, 0, 2, 1, 2, 1, 1, 2, 2, 1, 1, 1, 2,
)
ARTESP_20_K = 3


def test_repair_evaluation_uses_the_canonical_vector_where_the_bits_move() -> None:
    """Caso negativo da escolha do A3, num estado onde renomear lotes move bits.

    Os demais casos deste arquivo usam fixtures de quatro unidades com as quatro
    matrizes zeradas, e neles renomear os lotes **não move bit algum**: a
    asserção por `float.hex()` passa igual com a avaliação sobre rótulos crus e
    com a avaliação sobre o vetor canônico, isto é ela não guarda a escolha que o
    pacote fez. Este caso fecha essa lacuna sobre a instância real de vinte
    unidades, que é versionada e protegida pelo congelamento.

    A rotulação abaixo é viável, ocupa os três lotes e **não** é canônica. Sobre
    ela, `c_production`, `cv_demand` e `cv_production` diferem entre a avaliação
    dos rótulos crus e a do vetor canônico, porque `np.bincount` devolve os
    totais em outra ordem e as somas acumulam nessa ordem.
    """

    instance = load_artesp_instance(
        Path(__file__).parents[1] / "data/instances", 20
    )
    raw = np.array(ARTESP_20_RAW_LABELS, dtype=np.int64)
    canonical = np.array(
        canonicalize_solution(raw, n_units=len(instance.unit_ids), k=ARTESP_20_K),
        dtype=np.int64,
    )

    assert canonical.tolist() != raw.tolist(), "a rotulação escolhida já é canônica"

    on_raw = evaluate_solution(instance, raw, k=ARTESP_20_K)
    on_canonical = evaluate_solution(instance, canonical, k=ARTESP_20_K)
    moved = [
        field
        for field in EVALUATION_FIELDS
        if getattr(on_raw, field).hex() != getattr(on_canonical, field).hex()
    ]
    assert moved, (
        "o caso perdeu poder discriminante: as duas avaliações coincidem bit a "
        "bit, e então esta asserção passaria por vácuo, que é o padrão F2-02"
    )

    events: list[tuple[tuple[int, ...] | None, bool]] = []

    def observe(evaluations, solution, result, eligible) -> None:
        events.append((solution, eligible))

    evaluator = FitnessEvaluator(
        instance, k=ARTESP_20_K, budget=1, observer=observe, cache_enabled=False
    )
    published = evaluator.evaluate_provisional_for_repair(raw)

    assert events == [(tuple(canonical.tolist()), True)]
    assert evaluator.evaluations == 1, "a avaliação canônica não custa unidade a mais"

    for field in EVALUATION_FIELDS:
        assert getattr(published, field).hex() == getattr(on_canonical, field).hex()
    for field in moved:
        assert getattr(published, field).hex() != getattr(on_raw, field).hex()
