from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import ObjectiveWeights, evaluate_solution, load_tiny_instance
from metaheuristica_gpu.numerics import NumericalDivergenceError, require_equivalent


ROOT = Path(__file__).parents[2]


def test_tolerance_accepts_roundoff_and_rejects_material_difference() -> None:
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    result = evaluate_solution(instance, np.array([0, 0, 1, 1]), k=2, weights=ObjectiveWeights())
    assert require_equivalent(result, replace(result, total_cost=result.total_cost + 5e-13)) <= 1e-12
    with pytest.raises(NumericalDivergenceError, match="total_cost"):
        require_equivalent(result, replace(result, total_cost=result.total_cost + 1e-8))
