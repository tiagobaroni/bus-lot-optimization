from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_tiny_instance
from metaheuristica.metrics import RunConfig, TerminationReason
from metaheuristica.optimizer import OptimizationContext, execute_optimizer


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


@dataclass(frozen=True)
class DummyConfig:
    cycle_size: int = 7


def _search(context: OptimizationContext, config: DummyConfig) -> None:
    solutions = ([0, 0, 1, 1], [0, 1, 0, 1], [0, 1, 1, 0])
    cycle_position = 0
    context.update_diagnostics(
        rng_fingerprint=int(context.rng.bit_generator.random_raw())
    )
    while True:
        context.update_diagnostics(cycle_position=cycle_position)
        index = int(context.rng.integers(0, len(solutions)))
        context.evaluate(solutions[index])
        cycle_position = (cycle_position + 1) % config.cycle_size


def test_execute_optimizer_exhausts_budget_and_builds_all_checkpoints() -> None:
    result = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=7, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert result.solution.flags.writeable is False
    assert result.diagnostics["cycle_position"] == 1


def test_same_seed_reproduces_all_deterministic_fields() -> None:
    arguments = (TINY, RunConfig(k=2, seed=9, budget=100), DummyConfig())
    first = execute_optimizer(*arguments, algorithm="dummy", search=_search)
    second = execute_optimizer(*arguments, algorithm="dummy", search=_search)
    assert first.reproducible_data() == second.reproducible_data()


def test_different_seeds_produce_different_local_rng_streams() -> None:
    first = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    second = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=6, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert first.diagnostics["rng_fingerprint"] != second.diagnostics["rng_fingerprint"]


def test_optimizer_does_not_change_numpy_global_rng_state() -> None:
    np.random.seed(123)
    expected = np.random.random(3)
    np.random.seed(123)
    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert np.array_equal(np.random.random(3), expected)


def test_clock_excludes_final_validation_and_serialization() -> None:
    ticks = iter((10.0, 12.5))
    result = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
        clock=lambda: next(ticks),
    )
    assert result.runtime_seconds == 2.5


def test_algorithm_ending_early_is_rejected() -> None:
    def early(context: OptimizationContext, config: None) -> None:
        context.evaluate([0, 0, 1, 1])

    with pytest.raises(ConfigurationError, match="antes de esgotar"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="early",
            search=early,
        )


def test_nonbudget_algorithm_error_is_propagated() -> None:
    def broken(context: OptimizationContext, config: None) -> None:
        raise SolutionValidationError("erro real")

    with pytest.raises(SolutionValidationError, match="erro real"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="broken",
            search=broken,
        )


def test_budget_without_viable_incumbent_is_explicit_error() -> None:
    def provisional(context: OptimizationContext, config: None) -> None:
        while True:
            context.evaluate_provisional_for_repair([0, 0, 0, 0])

    with pytest.raises(ConfigurationError, match="incumbente"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="provisional",
            search=provisional,
        )
