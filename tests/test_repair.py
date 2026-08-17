from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    FitnessEvaluator,
    ProblemInstance,
    RepairBudgetExhausted,
)
from metaheuristica.instances import load_tiny_instance
from metaheuristica.repair import repair_empty_lots


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


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
