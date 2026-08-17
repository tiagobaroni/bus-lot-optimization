from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_tiny_instance
from metaheuristica.metrics import RunConfig, TerminationReason
from metaheuristica.problem import EvaluationResult
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


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


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
    larger_key = _candidate(TabuMove(0, 0, 1), 0.2, (0, 1, 0, 1))
    smaller_key = _candidate(TabuMove(2, 1, 0), 0.2 + 5e-13, (0, 0, 1, 1))
    assert _select_best_admissible([larger_key, smaller_key]) is smaller_key

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
