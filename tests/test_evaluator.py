from __future__ import annotations

from pathlib import Path

import pytest

from metaheuristica import BudgetExhausted, ConfigurationError
from metaheuristica.evaluator import FitnessEvaluator
from metaheuristica.instances import load_tiny_instance


INSTANCE = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


def test_evaluator_counts_until_exact_budget_and_never_exceeds_it() -> None:
    evaluator = FitnessEvaluator(INSTANCE, k=2, budget=2)
    evaluator.evaluate([0, 0, 1, 1])
    evaluator.evaluate([0, 1, 0, 1])
    assert evaluator.evaluations == 2
    assert evaluator.remaining == 0
    with pytest.raises(BudgetExhausted, match="2/2"):
        evaluator.evaluate([0, 0, 1, 1])
    assert evaluator.evaluations == 2


def test_cache_uses_canonical_partition_and_hits_still_count() -> None:
    evaluator = FitnessEvaluator(INSTANCE, k=2, budget=3, cache_enabled=True)
    first = evaluator.evaluate([0, 0, 1, 1])
    second = evaluator.evaluate([1, 1, 0, 0])
    assert first is second
    assert evaluator.evaluations == 2
    assert evaluator.cache_hits == 1


def test_cache_disabled_recalculates_without_hits() -> None:
    evaluator = FitnessEvaluator(INSTANCE, k=2, budget=2, cache_enabled=False)
    first = evaluator.evaluate([0, 0, 1, 1])
    second = evaluator.evaluate([0, 0, 1, 1])
    assert first == second
    assert first is not second
    assert evaluator.cache_hits == 0


def test_provisional_repair_evaluation_consumes_budget_without_cache() -> None:
    evaluator = FitnessEvaluator(INSTANCE, k=2, budget=2, cache_enabled=True)
    evaluator.evaluate_provisional_for_repair([0, 0, 0, 0])
    evaluator.evaluate_provisional_for_repair([0, 0, 0, 0])
    assert evaluator.evaluations == 2
    assert evaluator.cache_hits == 0


def test_evaluators_do_not_share_state() -> None:
    first = FitnessEvaluator(INSTANCE, k=2, budget=2, cache_enabled=True)
    second = FitnessEvaluator(INSTANCE, k=2, budget=2, cache_enabled=True)
    first.evaluate([0, 0, 1, 1])
    assert first.evaluations == 1
    assert second.evaluations == 0
    assert second.cache_hits == 0


@pytest.mark.parametrize("budget", [0, -1, 1.5, True])
def test_invalid_budget_is_rejected(budget: object) -> None:
    with pytest.raises(ConfigurationError):
        FitnessEvaluator(INSTANCE, k=2, budget=budget)  # type: ignore[arg-type]
