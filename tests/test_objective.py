from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import ObjectiveWeights, ProblemInstance, SolutionValidationError
from metaheuristica.instances import load_tiny_instance
from metaheuristica.objective import _evaluate_provisional_solution, evaluate_solution


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
    assert result.c_demand == result.c_production == 0.0
    assert result.c_territorial == result.c_affinity == 1.0
    assert result.total_cost == 0.5


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
