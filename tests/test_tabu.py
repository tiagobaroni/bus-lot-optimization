from __future__ import annotations

from dataclasses import FrozenInstanceError
from itertools import permutations
from pathlib import Path

import numpy as np
import pytest

from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.metrics import COST_TOLERANCE, RunConfig, TerminationReason
from metaheuristica.problem import EvaluationResult
import metaheuristica.tabu as tabu_module
from metaheuristica.tabu import (
    TabuConfig,
    TabuMove,
    _EvaluatedCandidate,
    _TabuMemory,
    _apply_move,
    _aspiration_applies,
    _balanced_random_solution,
    _enumerate_valid_moves,
    _sample_moves,
    _select_best_admissible,
    run_tabu,
)


ROOT = Path(__file__).parents[1]
TINY = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
ARTESP_20 = load_artesp_instance(ROOT / "data/instances", 20)


def _evaluation(cost: float) -> EvaluationResult:
    return EvaluationResult(cost, cost, 0.0, 0.0, 0.0, cost, 0.0)


def _candidate(
    move: TabuMove,
    cost: float,
    key: tuple[int, ...],
    *,
    was_tabu: bool = False,
    aspiration: bool = False,
) -> _EvaluatedCandidate:
    return _EvaluatedCandidate(
        move=move,
        solution=np.array(key, dtype=np.int64),
        canonical_key=key,
        evaluation=_evaluation(cost),
        was_tabu=was_tabu,
        aspiration=aspiration,
    )


def test_tabu_config_is_immutable_and_has_no_defaults() -> None:
    config = TabuConfig(5, 20, 50)
    with pytest.raises(FrozenInstanceError):
        config.tabu_tenure = 10  # type: ignore[misc]
    with pytest.raises(TypeError):
        TabuConfig()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tabu_tenure", 0),
        ("tabu_tenure", True),
        ("neighborhood_size", -1),
        ("neighborhood_size", 1.5),
        ("stagnation_limit", 0),
        ("stagnation_limit", False),
    ],
)
def test_tabu_config_rejects_invalid_values(field: str, value: object) -> None:
    values: dict[str, object] = {
        "tabu_tenure": 5,
        "neighborhood_size": 20,
        "stagnation_limit": 50,
    }
    values[field] = value
    with pytest.raises(ConfigurationError):
        TabuConfig(**values)  # type: ignore[arg-type]


def test_balanced_solution_is_reproducible_viable_and_balanced() -> None:
    first = _balanced_random_solution(20, 3, np.random.default_rng(17))
    second = _balanced_random_solution(20, 3, np.random.default_rng(17))
    other = _balanced_random_solution(20, 3, np.random.default_rng(18))
    assert np.array_equal(first, second)
    assert not np.array_equal(first, other)
    sizes = np.bincount(first, minlength=3)
    assert sizes.max() - sizes.min() == 1
    assert np.all(sizes > 0)


def test_move_enumeration_is_complete_ordered_and_protects_singletons() -> None:
    moves = _enumerate_valid_moves(np.array([0, 0, 1, 2]), k=3)
    assert moves == (
        TabuMove(0, 0, 1),
        TabuMove(0, 0, 2),
        TabuMove(1, 0, 1),
        TabuMove(1, 0, 2),
    )


def test_apply_move_returns_copy_and_rejects_invalid_move() -> None:
    original = np.array([0, 0, 1, 1])
    moved = _apply_move(original, TabuMove(0, 0, 1), k=2)
    assert moved.tolist() == [1, 0, 1, 1]
    assert original.tolist() == [0, 0, 1, 1]
    with pytest.raises(SolutionValidationError, match="origem"):
        _apply_move(original, TabuMove(2, 0, 1), k=2)
    with pytest.raises(SolutionValidationError, match="esvaziaria"):
        _apply_move([0, 1, 1, 1], TabuMove(0, 0, 1), k=2)


def test_sampling_is_reproducible_without_replacement_and_bounded() -> None:
    moves = _enumerate_valid_moves(np.array([0, 0, 1, 1]), k=2)
    first = _sample_moves(moves, 3, np.random.default_rng(9))
    second = _sample_moves(moves, 3, np.random.default_rng(9))
    assert first == second
    assert len(first) == len(set(first)) == 3
    assert set(first) <= set(moves)


def test_sampling_uses_entire_small_neighborhood_in_random_order() -> None:
    moves = _enumerate_valid_moves(np.array([0, 0, 1, 1]), k=2)
    sampled = _sample_moves(moves, 20, np.random.default_rng(3))
    assert len(sampled) == len(moves)
    assert set(sampled) == set(moves)


def test_tabu_memory_stores_reverse_for_exact_tenure() -> None:
    memory = _TabuMemory()
    accepted = TabuMove(0, 0, 1)
    reverse = accepted.reversed()
    memory.register(accepted, accepted_moves=1, tenure=3)
    assert memory.entries == ((reverse, 4),)
    for accepted_moves in (1, 2, 3):
        assert memory.is_tabu(reverse, accepted_moves=accepted_moves)
    memory.purge(accepted_moves=4)
    assert not memory.is_tabu(reverse, accepted_moves=4)
    assert memory.entries == ()


def test_candidate_selection_ignores_tabu_without_aspiration() -> None:
    blocked = _candidate(TabuMove(0, 0, 1), 0.1, (0, 1, 0, 1), was_tabu=True)
    allowed = _candidate(TabuMove(1, 0, 1), 0.4, (0, 0, 1, 1))
    assert _select_best_admissible([blocked, allowed]) is allowed
    assert _select_best_admissible([blocked]) is None


def test_aspiration_requires_strict_improvement_beyond_tolerance() -> None:
    assert _aspiration_applies(
        was_tabu=True, candidate_cost=0.4, global_best_cost=0.5
    )
    assert not _aspiration_applies(
        was_tabu=True, candidate_cost=0.5 - 5e-13, global_best_cost=0.5
    )
    assert not _aspiration_applies(
        was_tabu=False, candidate_cost=0.4, global_best_cost=0.5
    )


def test_candidate_selection_accepts_aspiration_and_uses_tie_breaks() -> None:
    """A chave canônica desempata na igualdade exata, e só nela.

    O caso original desta asserção usava `0,2` contra `0,2 + 5e-13` e esperava
    que a chave menor vencesse, isto é registrava como correto o descarte de uma
    melhora real de `5e-13`. Isso é o defeito de F5-2, não o contrato da seção
    14: o melhor movimento admissível é sempre aceito. O desempate por chave
    canônica passa a valer apenas onde não há valor a deslocar.
    """

    larger_key = _candidate(TabuMove(0, 0, 1), 0.2, (0, 1, 0, 1))
    smaller_key = _candidate(TabuMove(2, 1, 0), 0.2, (0, 0, 1, 1))
    assert _select_best_admissible([larger_key, smaller_key]) is smaller_key

    cheaper = _candidate(TabuMove(0, 0, 1), 0.2, (0, 1, 0, 1))
    dearer_but_smaller_key = _candidate(TabuMove(2, 1, 0), 0.2 + 5e-13, (0, 0, 1, 1))
    assert _select_best_admissible([cheaper, dearer_but_smaller_key]) is cheaper
    assert _select_best_admissible([dearer_but_smaller_key, cheaper]) is cheaper

    aspirated = _candidate(
        TabuMove(3, 1, 0),
        0.1,
        (0, 0, 1, 1),
        was_tabu=True,
        aspiration=True,
    )
    assert _select_best_admissible([larger_key, aspirated]) is aspirated


def test_move_tuple_is_final_tie_break() -> None:
    first = _candidate(TabuMove(1, 0, 1), 0.2, (0, 0, 1, 1))
    second = _candidate(TabuMove(0, 0, 1), 0.2, (0, 0, 1, 1))
    assert _select_best_admissible([first, second]) is second


def test_tabu_runs_to_exact_budget_with_coherent_diagnostics() -> None:
    result = run_tabu(
        TINY,
        RunConfig(k=2, seed=7, budget=100),
        TabuConfig(tabu_tenure=5, neighborhood_size=4, stagnation_limit=10),
    )
    assert result.algorithm == "tabu"
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert len(set(result.solution)) == 2
    assert result.diagnostics["iterations_completed"] == (
        result.diagnostics["accepted_moves"] + result.diagnostics["restarts"]
    )


def test_tabu_is_reproducible_except_for_runtime() -> None:
    run = RunConfig(k=2, seed=11, budget=100)
    config = TabuConfig(3, 4, 5)
    first = run_tabu(TINY, run, config)
    second = run_tabu(TINY, run, config)
    assert first.reproducible_data() == second.reproducible_data()


def test_stagnation_limit_one_forces_restarts() -> None:
    result = run_tabu(
        TINY,
        RunConfig(k=2, seed=3, budget=100),
        TabuConfig(tabu_tenure=3, neighborhood_size=4, stagnation_limit=1),
    )
    assert result.diagnostics["restarts"] > 0
    assert result.diagnostics["iterations_completed"] == (
        result.diagnostics["accepted_moves"] + result.diagnostics["restarts"]
    )


def test_budget_ending_mid_sample_does_not_complete_partial_iteration() -> None:
    partial = run_tabu(
        TINY,
        RunConfig(k=2, seed=4, budget=103),
        TabuConfig(tabu_tenure=2, neighborhood_size=4, stagnation_limit=1000),
    )
    completed = run_tabu(
        TINY,
        RunConfig(k=2, seed=4, budget=104),
        TabuConfig(tabu_tenure=2, neighborhood_size=4, stagnation_limit=1000),
    )
    assert partial.evaluations == 103
    assert partial.diagnostics["iterations_completed"] == 28
    assert completed.diagnostics["iterations_completed"] == 29


_ORDER_DEPENDENT = (
    (TabuMove(0, 0, 1), 0.0, (0, 1, 1, 1)),
    (TabuMove(1, 0, 1), 0.7e-12, (0, 1, 1, 0)),
    (TabuMove(2, 1, 0), 1.4e-12, (0, 1, 0, 1)),
)


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_best_admissible_is_invariant_to_the_order_of_the_sample(
    order: tuple[int, ...],
) -> None:
    """A seleção do melhor movimento admissível é ordem total.

    `_candidate_is_better` tratava como empate qualquer diferença até
    `COST_TOLERANCE`, relação não transitiva, e `_select_best_admissible` é
    redução sequencial na ordem da amostra. Com estes três candidatos e chaves
    canônicas decrescentes, `[A,B,C]` elegia `C`, `[C,B,A]` elegia `A` e
    `[A,C,B]` elegia `B`: três vencedores para a mesma amostra. Pior, em
    `[A,B,C]` o vencedor `C` era estritamente pior que `A` pelo próprio
    comparador, contra a seção 14, que manda aceitar sempre o melhor movimento
    admissível.
    """

    candidates = [_candidate(*_ORDER_DEPENDENT[index]) for index in order]
    winner = _select_best_admissible(candidates)
    assert winner is not None
    assert winner.evaluation.total_cost == 0.0
    assert winner.canonical_key == (0, 1, 1, 1)


def test_tabu_memory_is_fed_by_accepted_moves_and_not_by_iterations(monkeypatch) -> None:
    """O contador do prazo é `accepted_moves` ao longo de `_tabu_search` inteira.

    A seção 14 diz que o retorno permanece tabu pelos próximos `L_tabu`
    **movimentos aceitos**. A única asserção que existia sobre o prazo exercitava
    `_TabuMemory` isolada, com o contador fornecido pelo próprio teste, de modo
    que nenhum teste verificava qual contador chega de fato a `purge`, `is_tabu`
    e `register`. Trocar `accepted_moves` por `iterations_completed` nos três
    pontos altera o custo do algoritmo de referência em cerca de 7 por cento sem
    quebrar teste algum, e este teste é o que fecha esse canal.

    A execução tem reinícios, e é isso que separa as duas séries: com reinícios,
    `iterations_completed` é estritamente maior que `accepted_moves`.
    """

    registrations: list[int] = []
    queries: list[tuple[int, int]] = []
    purges: list[tuple[int, int]] = []
    original_purge = _TabuMemory.purge
    original_is_tabu = _TabuMemory.is_tabu
    original_register = _TabuMemory.register

    def spy_purge(self: _TabuMemory, *, accepted_moves: int) -> None:
        purges.append((accepted_moves, len(registrations)))
        original_purge(self, accepted_moves=accepted_moves)

    def spy_is_tabu(self: _TabuMemory, move: TabuMove, *, accepted_moves: int) -> bool:
        queries.append((accepted_moves, len(registrations)))
        return original_is_tabu(self, move, accepted_moves=accepted_moves)

    def spy_register(
        self: _TabuMemory, move: TabuMove, *, accepted_moves: int, tenure: int
    ) -> None:
        registrations.append(accepted_moves)
        original_register(self, move, accepted_moves=accepted_moves, tenure=tenure)

    monkeypatch.setattr(_TabuMemory, "purge", spy_purge)
    monkeypatch.setattr(_TabuMemory, "is_tabu", spy_is_tabu)
    monkeypatch.setattr(_TabuMemory, "register", spy_register)

    result = run_tabu(TINY, RunConfig(k=2, seed=3, budget=200), TabuConfig(5, 2, 5))
    accepted = result.diagnostics["accepted_moves"]
    restarts = result.diagnostics["restarts"]
    iterations = result.diagnostics["iterations_completed"]

    assert accepted > 0 and restarts > 0
    assert iterations == accepted + restarts
    assert iterations > accepted, "sem reinícios as duas séries não se separam"

    # `register` é chamado logo depois de `accepted_moves += 1`, logo a série que
    # ele recebe é exatamente 1, 2, ..., total de movimentos aceitos.
    assert registrations == list(range(1, accepted + 1))
    # Toda consulta e toda expurga recebem o número de movimentos aceitos até ali,
    # que é o número de registros já feitos.
    assert all(seen == done for seen, done in queries)
    assert all(seen == done for seen, done in purges)
    assert queries and purges


def test_restart_clears_the_tabu_memory_seen_through_the_restart(monkeypatch) -> None:
    """A limpeza da memória é observada **através** do reinício.

    A seção 14 manda o reinício limpar a memória. A cobertura existente conferia
    apenas que houve reinício e que a identidade entre os contadores se mantinha,
    e a remoção de `memory.clear()` sobrevivia à suíte inteira. Aqui a memória é
    observada antes e depois de cada limpeza, e a consulta que respondia "tabu"
    passa a responder "não tabu".
    """

    observations: list[tuple[tuple[tuple[TabuMove, int], ...], tuple[bool, ...]]] = []
    original_clear = _TabuMemory.clear

    def spy_clear(self: _TabuMemory) -> None:
        before = self.entries
        original_clear(self)
        assert self.entries == (), "a memória não ficou vazia depois da limpeza"
        observations.append((
            before,
            tuple(
                self.is_tabu(move, accepted_moves=expiration - 1)
                for move, expiration in before
            ),
        ))

    monkeypatch.setattr(_TabuMemory, "clear", spy_clear)
    result = run_tabu(TINY, RunConfig(k=2, seed=3, budget=200), TabuConfig(5, 2, 5))

    assert result.diagnostics["restarts"] > 0
    assert len(observations) == result.diagnostics["restarts"]
    populated = [entry for entry in observations if entry[0]]
    assert populated, "nenhum reinício encontrou a memória povoada"
    for before, still_tabu in populated:
        # Antes da limpeza cada uma destas consultas responderia "tabu", porque
        # `accepted_moves` é estritamente menor que a expiração registrada.
        assert all(expiration - 1 < expiration for _, expiration in before)
        assert not any(still_tabu)


def test_aspiration_boundary_is_strict_at_exactly_one_tolerance() -> None:
    """A fronteira onde a estritez do `<` decide, e que não era exercitada.

    A cobertura existente usa `5e-13`, dentro da tolerância, e `0,4` contra
    `0,5`, muito fora. O ponto onde trocar `<` por `<=` muda a resposta é a
    melhora de **exatamente** `1e-12`, e é só ele que separa as duas formas. A
    seção 14 libera a reversão somente quando a melhora é **maior** que `1e-12`.
    """

    global_best = 0.5
    exactly_at_the_limit = global_best - 1e-12
    assert exactly_at_the_limit == global_best - COST_TOLERANCE
    assert not _aspiration_applies(
        was_tabu=True,
        candidate_cost=exactly_at_the_limit,
        global_best_cost=global_best,
    )
    assert _aspiration_applies(
        was_tabu=True,
        candidate_cost=global_best - 2e-12,
        global_best_cost=global_best,
    )


def test_aspiration_acceptance_happens_in_an_integrated_run() -> None:
    """`aspiration_acceptances` asseverado em execução completa, não em unidade.

    A sonda da auditoria mostrou que nenhuma execução de Busca Tabu da suíte,
    incluindo os dezoito cenários ARTESP do piloto, aceitava um candidato tabu
    por aspiração: o diagnóstico não era asseverado em arquivo algum. O prazo
    longo somado à amostra estreita torna a aspiração frequente nesta instância
    real, e o ramo passa a ser percorrido de ponta a ponta.
    """

    result = run_tabu(
        ARTESP_20,
        RunConfig(k=5, seed=1, budget=600),
        TabuConfig(tabu_tenure=40, neighborhood_size=5, stagnation_limit=100),
    )
    assert result.diagnostics["aspiration_acceptances"] == 7
    assert result.diagnostics["tabu_candidates_evaluated"] > 0
    assert result.evaluations == 600


def test_restart_when_the_sample_has_no_valid_move(monkeypatch) -> None:
    """Ramo de reinício por amostra vazia, que nenhum teste percorria.

    Com `K` igual ao número de unidades cada lote fica com uma única unidade, e
    todo movimento esvaziaria o lote de origem, logo não existe movimento válido
    e a amostra sai vazia em toda iteração.
    """

    empty = 0
    populated = 0
    original_sample = tabu_module._sample_moves

    def spy_sample(moves, size, rng):  # type: ignore[no-untyped-def]
        nonlocal empty, populated
        sampled = original_sample(moves, size, rng)
        if sampled:
            populated += 1
        else:
            empty += 1
        return sampled

    monkeypatch.setattr(tabu_module, "_sample_moves", spy_sample)
    result = run_tabu(TINY, RunConfig(k=4, seed=1, budget=100), TabuConfig(3, 4, 5))

    assert empty > 0, "o ramo de amostra vazia não foi percorrido"
    assert populated == 0
    assert result.diagnostics["accepted_moves"] == 0
    # Toda amostra vazia leva a um reinício, e não há outra fonte de reinício
    # aqui, porque nenhum movimento é aceito. A folga de uma unidade é o achado
    # F5-3, ainda aberto: o reinício que consome a última avaliação do orçamento
    # não é contabilizado, porque `restarts` é incrementado depois do
    # `try/finally` que envolve a avaliação. Este teste não fixa essa folga, para
    # não impedir a correção de F5-3.
    assert empty - 1 <= result.diagnostics["restarts"] <= empty


def test_restart_when_the_entire_sample_is_tabu(monkeypatch) -> None:
    """Ramo de reinício por amostra inteiramente tabu, que nenhum teste percorria.

    A seção 14 manda reiniciar também quando toda a amostra está tabu sem
    aspiração. Com os parâmetros congelados a condição é inalcançável, porque a
    memória guarda no máximo `L_tabu` entradas vivas contra vinte movimentos na
    amostra; aqui a amostra é estreitada até que o bloqueio total ocorra.
    """

    blocked: list[int] = []
    original_select = tabu_module._select_best_admissible

    def spy_select(candidates):  # type: ignore[no-untyped-def]
        winner = original_select(candidates)
        if winner is None and candidates:
            blocked.append(len(candidates))
        return winner

    monkeypatch.setattr(tabu_module, "_select_best_admissible", spy_select)
    result = run_tabu(TINY, RunConfig(k=2, seed=0, budget=100), TabuConfig(5, 4, 100))

    assert blocked, "nenhuma amostra ficou inteiramente tabu"
    assert max(blocked) >= 2, "o bloqueio total precisa valer para amostra não trivial"
    assert result.diagnostics["restarts"] == len(blocked)
