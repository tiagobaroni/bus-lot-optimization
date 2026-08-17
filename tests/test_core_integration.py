from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import FitnessEvaluator, load_artesp_instance


INSTANCES_DIR = Path(__file__).parents[1] / "data" / "instances"


@pytest.mark.parametrize("size", [20, 60, 150])
def test_every_artesp_scenario_accepts_a_feasible_round_robin_solution(size: int) -> None:
    instance = load_artesp_instance(INSTANCES_DIR, size)
    for k in range(3, 9):
        evaluator = FitnessEvaluator(instance, k=k, budget=1)
        solution = np.arange(size, dtype=np.int64) % k
        result = evaluator.evaluate(solution)
        assert np.isfinite(result.total_cost)
        assert 0.0 <= result.total_cost <= 1.0
        assert evaluator.evaluations == 1
