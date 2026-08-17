from __future__ import annotations

from dataclasses import FrozenInstanceError
from inspect import signature
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import PsoConfig, RunConfig, run_pso
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_tiny_instance
from metaheuristica.pso import (
    _Best,
    _best_comparison,
    _initial_particle,
    _project_position,
    decode_position,
)
from metaheuristica.problem import EvaluationResult


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


def evaluation(cost: float) -> EvaluationResult:
    return EvaluationResult(cost, cost, 0.0, 0.0, 0.0, cost, 0.0)


def test_pso_config_is_frozen_and_has_no_defaults() -> None:
    config = PsoConfig(4, 0.7, 1.5, 2.0)
    assert all(parameter.default is parameter.empty for parameter in signature(PsoConfig).parameters.values())
    with pytest.raises(FrozenInstanceError):
        config.inertia = 0.4  # type: ignore[misc]


@pytest.mark.parametrize(
    "arguments",
    [
        (0, 0.7, 1.5, 1.5),
        (True, 0.7, 1.5, 1.5),
        (2, -0.1, 1.5, 1.5),
        (2, 1.1, 1.5, 1.5),
        (2, 0.7, 0.0, 1.5),
        (2, 0.7, 1.5, float("inf")),
    ],
)
def test_pso_config_rejects_invalid_values(arguments: tuple[object, ...]) -> None:
    with pytest.raises(ConfigurationError):
        PsoConfig(*arguments)  # type: ignore[arg-type]


def test_decode_position_covers_boundaries_and_one() -> None:
    position = np.array([0.0, 0.249999, 0.25, 0.5, 0.999, 1.0], dtype=np.float64)
    assert decode_position(position, n_units=6, k=4).tolist() == [0, 0, 1, 2, 3, 3]


@pytest.mark.parametrize(
    "position",
    [
        np.array([0.0, 1.0], dtype=np.float32),
        np.array([[0.0, 1.0]], dtype=np.float64),
        np.array([0.0, np.nan], dtype=np.float64),
        np.array([-0.1, 1.0], dtype=np.float64),
    ],
)
def test_decode_position_rejects_invalid_position(position: np.ndarray) -> None:
    with pytest.raises(SolutionValidationError):
        decode_position(position, n_units=2, k=2)


def test_initial_population_is_balanced_viable_and_reproducible() -> None:
    first_rng = np.random.Generator(np.random.PCG64(17))
    second_rng = np.random.Generator(np.random.PCG64(17))
    first = [_initial_particle(11, 4, first_rng) for _ in range(3)]
    second = [_initial_particle(11, 4, second_rng) for _ in range(3)]
    for left, right in zip(first, second):
        labels = decode_position(left.position, n_units=11, k=4)
        counts = np.bincount(labels, minlength=4)
        assert counts.max() - counts.min() <= 1
        assert np.array_equal(left.position, right.position)
        assert np.array_equal(left.velocity, right.velocity)
        assert np.all((-0.5 <= left.velocity) & (left.velocity <= 0.5))
    assert not np.shares_memory(first[0].position, first[1].position)


def test_projection_preserves_internal_fraction_and_decodes_repair() -> None:
    position = np.array([0.1, 0.4, 0.8, 1.0], dtype=np.float64)
    original = decode_position(position, n_units=4, k=3)
    repaired = np.array([0, 1, 2, 2], dtype=np.int64)
    projected = _project_position(position, original, repaired, k=3)
    assert np.array_equal(decode_position(projected, n_units=4, k=3), repaired)
    original_fraction = np.clip(3 * position - original, 0.0, np.nextafter(1.0, 0.0))
    projected_fraction = 3 * projected - repaired
    assert np.allclose(projected_fraction, original_fraction, rtol=0.0, atol=5e-16)


def test_best_comparison_uses_cost_solution_and_position() -> None:
    incumbent = _Best(
        np.array([0.2, 0.8]), np.array([0, 1]), evaluation(1.0)
    )
    cheaper = _Best(np.array([0.9, 0.1]), np.array([0, 1]), evaluation(0.5))
    assert _best_comparison(cheaper, incumbent) == (True, True)
    lower_solution = _Best(
        np.array([0.9, 0.1]), np.array([0, 0]), evaluation(1.0 + 5e-13)
    )
    assert _best_comparison(lower_solution, incumbent) == (True, False)
    lower_position = _Best(
        np.array([0.1, 0.9]), np.array([0, 1]), evaluation(1.0)
    )
    assert _best_comparison(lower_position, incumbent) == (True, False)


def test_run_pso_exhausts_budget_and_produces_consistent_diagnostics() -> None:
    result = run_pso(
        TINY,
        RunConfig(k=2, seed=23, budget=100),
        PsoConfig(4, 0.7, 1.5, 1.5),
    )
    diagnostics = result.diagnostics
    assert result.algorithm == "pso"
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert len(set(result.solution.tolist())) == 2
    assert diagnostics["particles_evaluated"] + diagnostics["repair_evaluations"] == 100
    assert diagnostics["iterations_completed"] >= 0


def test_run_pso_is_reproducible() -> None:
    arguments = (
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        PsoConfig(3, 0.4, 2.0, 1.5),
    )
    first = run_pso(*arguments)
    second = run_pso(*arguments)
    assert first.reproducible_data() == second.reproducible_data()


def test_population_cannot_exceed_budget() -> None:
    with pytest.raises(ConfigurationError, match="exceder"):
        run_pso(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            PsoConfig(101, 0.7, 1.5, 1.5),
        )
