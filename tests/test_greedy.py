from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import ObjectiveWeights, ProblemInstance
from metaheuristica import greedy as greedy_module
from metaheuristica.greedy import (
    _candidate_is_better,
    _processing_indices,
    run_greedy,
)
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.objective import _evaluate_partial_assignment, evaluate_solution
from metaheuristica.problem import EvaluationResult


INSTANCES_DIR = Path(__file__).parents[1] / "data/instances"
TINY = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")

# As 18 combinações oficiais da campanha, conforme experiments/configs/benchmark.toml:
# três instâncias ARTESP por seis valores de K.
OFFICIAL_SIZES = (20, 60, 150)
OFFICIAL_K_VALUES = (3, 4, 5, 6, 7, 8)
EVALUATION_FIELDS = (
    "total_cost",
    "c_demand",
    "c_production",
    "c_territorial",
    "c_affinity",
    "cv_demand",
    "cv_production",
)


@lru_cache(maxsize=None)
def official_instance(size: int) -> ProblemInstance:
    """Carrega uma instância ARTESP uma única vez por sessão de teste."""

    return load_artesp_instance(INSTANCES_DIR, size)


def zero_relation_instance(
    *, unit_ids: tuple[str, ...], production: list[float]
) -> ProblemInstance:
    n_units = len(unit_ids)
    zero = np.zeros((n_units, n_units))
    return ProblemInstance(
        name="desempates",
        unit_ids=unit_ids,
        demand=np.ones(n_units),
        production=production,
        s_territorial=zero,
        t_terminal=zero,
        i_integration=zero,
        o_market=zero,
    )


def test_tiny_greedy_finds_documented_optimum() -> None:
    result = run_greedy(TINY, k=2)
    assert result.processing_order == ("A", "C", "B", "D")
    assert result.solution == (0, 0, 1, 1)
    assert result.evaluation.total_cost == 0.0
    assert result.evaluations == 4
    assert len(result.trace) == 2
    assert result.trace[0].unit_id == "B"
    assert result.trace[0].lot == 0
    assert result.trace[0].evaluations == 2
    assert result.trace[1].unit_id == "D"
    assert result.trace[1].lot == 1
    assert result.trace[1].evaluations == 4


def test_final_partial_result_equals_public_objective() -> None:
    result = run_greedy(TINY, k=2)
    assert result.evaluation == evaluate_solution(TINY, result.solution, k=2)


def _construction_order_evaluation(
    instance: ProblemInstance,
    solution: tuple[int, ...],
    *,
    k: int,
    weights: ObjectiveWeights | None = None,
) -> EvaluationResult:
    """Reproduz a avaliação permutada pela ordem de processamento, que é o defeito F1-01.

    O conjunto induzido do último passo do guloso é a instância inteira, mas
    permutada pela ordem decrescente de PU·km. `np.bincount` acumula na ordem do
    vetor recebido e `np.triu_indices` percorre os pares na ordem da matriz
    recebida, logo a mesma partição avaliada nessa permutação difere em bits da
    avaliação na ordem natural. Esta função existe apenas para o caso negativo,
    que injeta a permutação antiga e confere que a autoconsistência se quebra.
    Ela chama `_evaluate_partial_assignment` diretamente, sem passar pelo
    `FitnessEvaluator`, para não debitar unidade alguma de orçamento.
    """

    order = _processing_indices(instance)
    labels = [int(solution[index]) for index in order]
    return _evaluate_partial_assignment(
        instance, order, labels, k=k, weights=weights or ObjectiveWeights()
    )


@pytest.mark.parametrize("k", OFFICIAL_K_VALUES)
@pytest.mark.parametrize("size", OFFICIAL_SIZES)
def test_published_evaluation_is_self_consistent_on_official_combinations(
    size: int, k: int
) -> None:
    """F1-01 e F1-07: o par publicado tem de ser autoconsistente nas 18 oficiais.

    A cobertura anterior exercitava só `tiny_manual`, com `N=4` e ordem de
    processamento `(0, 2, 1, 3)`, em que a permutação coincide com a ordem
    natural e o defeito não aparece. Sobre as 18 combinações oficiais a
    asserção falhava em 18 de 18, com 1 a 6 campos divergentes por combinação.

    A primeira asserção é quase tautológica depois da correção, porque a
    avaliação publicada passa a vir do mesmo caminho de `evaluate_solution`. O
    conteúdo que discrimina está nas outras duas, na contagem de avaliações e na
    igualdade por `float.hex()`, e sobretudo no caso negativo abaixo.
    """

    instance = official_instance(size)
    result = run_greedy(instance, k=k)
    public = evaluate_solution(instance, result.solution, k=k)
    assert result.evaluation == public
    # A correção reaproveita a avaliação sem debitar orçamento, como manda a
    # seção 13.3 da formulação: o contador continua exatamente K(N-K).
    assert result.evaluations == k * (size - k)
    for field in EVALUATION_FIELDS:
        assert getattr(result.evaluation, field).hex() == getattr(public, field).hex(), field


def test_construction_order_evaluation_breaks_self_consistency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caso negativo de F1-07: com a permutação antiga a autoconsistência falha.

    Sem esta verificação a asserção principal do teste acima não teria poder
    discriminante, porque a correção a torna quase tautológica. Aqui a avaliação
    publicada volta a ser calculada na ordem de construção, e a igualdade exata
    deixa de valer em `N=20` com `K=3`, onde o `total_cost` publicado é
    `0x1.139ef3308520dp-4` contra `0x1.139ef3308520cp-4` da ordem natural.

    A contagem de chamadas é o marcador que prova que a injeção foi de fato
    percorrida: sem ela, uma correção futura que deixasse de publicar por
    `evaluate_solution` faria este teste passar sem exercitar coisa alguma.
    """

    instance = official_instance(20)
    k = 3
    calls: list[int] = []

    def injected(
        target: ProblemInstance,
        solution: tuple[int, ...],
        *,
        k: int,
        weights: ObjectiveWeights | None = None,
    ) -> EvaluationResult:
        calls.append(1)
        return _construction_order_evaluation(target, solution, k=k, weights=weights)

    monkeypatch.setattr(greedy_module, "evaluate_solution", injected)
    result = run_greedy(instance, k=k)

    assert calls == [1]
    assert result.evaluations == k * (instance.n_units - k)
    public = evaluate_solution(instance, result.solution, k=k)
    assert result.evaluation != public
    assert result.evaluation.total_cost.hex() == "0x1.139ef3308520dp-4"
    assert public.total_cost.hex() == "0x1.139ef3308520cp-4"


def test_public_evaluation_is_self_consistent_when_k_equals_n() -> None:
    """O ramo sem orçamento publica pelo mesmo caminho, e antes ninguém o cobria.

    Com `K = N` o guloso não avalia nada, `budget` é zero e o rastreio fica
    vazio. Esse ramo avaliava os rótulos crus da construção, e não a solução
    canônica, o que o deixava sujeito ao mesmo defeito de F1-01, porque a
    recanonização permuta as posições dos totais e a redução sobre os totais
    permutados pode arredondar diferente. A correção unifica o ponto de
    publicação e fecha o ramo junto; nenhum teste o exercitava antes.
    """

    result = run_greedy(TINY, k=TINY.n_units)
    assert result.evaluations == 0
    assert result.trace == ()
    public = evaluate_solution(TINY, result.solution, k=TINY.n_units)
    assert result.evaluation == public
    for field in EVALUATION_FIELDS:
        assert getattr(result.evaluation, field).hex() == getattr(public, field).hex(), field


def test_processing_order_breaks_production_tie_by_unit_id() -> None:
    instance = zero_relation_instance(
        unit_ids=("C", "A", "B"), production=[1.0, 1.0, 1.0]
    )
    result = run_greedy(instance, k=2)
    assert result.processing_order == ("A", "B", "C")


def test_cost_tie_uses_lower_accumulated_production() -> None:
    instance = zero_relation_instance(
        unit_ids=("A", "B", "C"), production=[3.0, 2.0, 1.0]
    )
    weights = ObjectiveWeights(0.0, 0.0, 1.0, 0.0)
    result = run_greedy(instance, k=2, weights=weights)
    assert result.trace[0].lot == 1


def test_cost_tie_uses_lower_lot_when_accumulated_production_is_equal() -> None:
    instance = zero_relation_instance(
        unit_ids=("A", "B", "C"), production=[1.0, 1.0, 1.0]
    )
    weights = ObjectiveWeights(0.0, 0.0, 1.0, 0.0)
    result = run_greedy(instance, k=2, weights=weights)
    assert result.trace[0].lot == 0


@pytest.mark.parametrize(
    "delta,empatam",
    [(5e-13, True), (2e-12, False), (5e-7, False)],
    ids=["dentro", "logo_acima", "muito_acima"],
)
def test_cost_tie_band_is_pinned_by_independent_literals(
    delta: float, empatam: bool
) -> None:
    """Achado F2-02: a sonda saía da própria constante que devia verificar.

    A forma anterior montava o custo como `1.0 + COST_TOLERANCE / 2.0`, isto é a
    partir do valor sob verificação, e por isso respondia "empatado" para
    qualquer tolerância positiva. Os três deltas abaixo são literais fixados pela
    seção 13.3 de `docs/formulation.md`, que declara empate até `1e-12`: `5e-13`
    cai dentro da faixa, `2e-12` e `5e-7` caem fora. O par prende a constante
    entre `5e-13` e `2e-12`, logo trocá-la por `1e-6`, ou por `1e-11`, derruba
    este caso.
    """

    accumulated = np.array([10.0, 5.0])
    # Propriedade que torna o caso discriminante, asseverada aqui dentro para que
    # ela não se perca numa edição futura: o lote candidato tem produção
    # acumulada estritamente menor, logo o ramo de empate responde "melhor"
    # sempre que a faixa cobrir o delta, e só o ramo estrito o recusa.
    assert accumulated[1] < accumulated[0]
    cost = 1.0 + delta
    assert cost > 1.0

    assert (
        _candidate_is_better(
            cost=cost,
            lot=1,
            best_cost=1.0,
            best_lot=0,
            accumulated_production=accumulated,
        )
        is empatam
    )


def test_repeated_runs_are_identical_and_instance_stays_immutable() -> None:
    demand_before = TINY.demand.copy()
    first = run_greedy(TINY, k=2)
    second = run_greedy(TINY, k=2)
    assert first == second
    assert np.array_equal(TINY.demand, demand_before)
