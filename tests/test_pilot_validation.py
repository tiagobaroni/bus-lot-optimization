from __future__ import annotations

from experiments.pilot_validation import _deterministic_result


def test_reproduction_comparison_excludes_only_runtime() -> None:
    left = {"solution": [0, 1], "evaluation": {"total_cost": 0.0}, "runtime_seconds": 1.0}
    right = {"solution": [0, 1], "evaluation": {"total_cost": 0.0}, "runtime_seconds": 2.0}
    assert _deterministic_result(left) == _deterministic_result(right)
    right["solution"] = [1, 0]
    assert _deterministic_result(left) != _deterministic_result(right)
