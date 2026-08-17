from __future__ import annotations

from pathlib import Path

import numpy as np

from metaheuristica import ObjectiveWeights, ProblemInstance
from metaheuristica.greedy import COST_TOLERANCE, _candidate_is_better, run_greedy
from metaheuristica.instances import load_tiny_instance
from metaheuristica.objective import evaluate_solution


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


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


def test_costs_inside_tolerance_are_treated_as_tied() -> None:
    accumulated = np.array([10.0, 5.0])
    assert _candidate_is_better(
        cost=1.0 + COST_TOLERANCE / 2.0,
        lot=1,
        best_cost=1.0,
        best_lot=0,
        accumulated_production=accumulated,
    )


def test_repeated_runs_are_identical_and_instance_stays_immutable() -> None:
    demand_before = TINY.demand.copy()
    first = run_greedy(TINY, k=2)
    second = run_greedy(TINY, k=2)
    assert first == second
    assert np.array_equal(TINY.demand, demand_before)
