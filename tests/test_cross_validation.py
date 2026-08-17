from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from metaheuristica import (
    AcoConfig,
    OptimizationResult,
    ProblemInstance,
    PsoConfig,
    RunConfig,
    TabuConfig,
    TerminationReason,
    canonicalize_solution,
    checkpoint_thresholds,
    evaluate_solution,
    load_artesp_instance,
    load_tiny_instance,
    run_aco,
    run_pso,
    run_tabu,
)
from metaheuristica.metrics import COST_TOLERANCE
from metaheuristica.problem import EvaluationResult


INSTANCES_DIR = Path(__file__).parents[1] / "data" / "instances"
TINY = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
Runner = Callable[[ProblemInstance, RunConfig, Any], OptimizationResult]


@dataclass(frozen=True, slots=True)
class AlgorithmCase:
    name: str
    runner: Runner
    config: Any


ALGORITHMS = (
    AlgorithmCase(
        "tabu",
        run_tabu,
        TabuConfig(tabu_tenure=5, neighborhood_size=20, stagnation_limit=50),
    ),
    AlgorithmCase(
        "aco",
        run_aco,
        AcoConfig(alpha=1.0, beta=1.0, rho=0.1, n_ants=20),
    ),
    AlgorithmCase(
        "pso",
        run_pso,
        PsoConfig(n_particles=20, inertia=0.7, cognitive=1.5, social=1.5),
    ),
)


def _evaluation_values(result: EvaluationResult) -> tuple[float, ...]:
    return (
        result.total_cost,
        result.c_demand,
        result.c_production,
        result.c_territorial,
        result.c_affinity,
        result.cv_demand,
        result.cv_production,
    )


def _assert_same_evaluation(
    observed: EvaluationResult, expected: EvaluationResult
) -> None:
    assert np.allclose(
        _evaluation_values(observed),
        _evaluation_values(expected),
        rtol=COST_TOLERANCE,
        atol=COST_TOLERANCE,
    )


def _run(
    case: AlgorithmCase,
    instance: ProblemInstance,
    *,
    k: int,
    seed: int,
    budget: int = 100,
) -> OptimizationResult:
    return case.runner(
        instance,
        RunConfig(k=k, seed=seed, budget=budget, cache_enabled=False),
        case.config,
    )


def _assert_common_contract(
    result: OptimizationResult,
    case: AlgorithmCase,
    instance: ProblemInstance,
    *,
    k: int,
    seed: int,
    budget: int = 100,
) -> None:
    expected_config = RunConfig(
        k=k,
        seed=seed,
        budget=budget,
        cache_enabled=False,
    )
    assert result.algorithm == case.name
    assert result.k == k
    assert result.seed == seed
    assert result.budget == budget
    assert result.weights == expected_config.weights
    assert result.evaluations == budget
    assert result.cache_hits == 0
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert np.isfinite(result.runtime_seconds)
    assert result.runtime_seconds >= 0.0

    assert len(result.checkpoints) == 100
    assert tuple(item.evaluations for item in result.checkpoints) == (
        checkpoint_thresholds(budget)
    )
    checkpoint_costs = [item.evaluation.total_cost for item in result.checkpoints]
    assert all(
        right <= left + COST_TOLERANCE
        for left, right in zip(checkpoint_costs, checkpoint_costs[1:])
    )
    _assert_same_evaluation(result.checkpoints[-1].evaluation, result.evaluation)

    canonical = canonicalize_solution(
        result.solution,
        n_units=instance.n_units,
        k=k,
    )
    assert np.array_equal(result.solution, canonical)
    assert len(set(int(label) for label in result.solution)) == k
    recomputed = evaluate_solution(instance, result.solution, k=k, weights=result.weights)
    _assert_same_evaluation(result.evaluation, recomputed)
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("case", ALGORITHMS, ids=lambda case: case.name)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_tiny_optimum_and_common_contract(case: AlgorithmCase, seed: int) -> None:
    result = _run(case, TINY, k=2, seed=seed)
    _assert_common_contract(result, case, TINY, k=2, seed=seed)
    assert result.evaluation.total_cost == pytest.approx(0.0, abs=COST_TOLERANCE)


@pytest.mark.parametrize("case", ALGORITHMS, ids=lambda case: case.name)
@pytest.mark.parametrize("size", [20, 60, 150])
def test_artesp_pilot_all_k(case: AlgorithmCase, size: int) -> None:
    instance = load_artesp_instance(INSTANCES_DIR, size)
    executed = 0
    for k in range(3, 9):
        result = _run(case, instance, k=k, seed=20260817)
        _assert_common_contract(
            result,
            case,
            instance,
            k=k,
            seed=20260817,
        )
        executed += 1
    assert executed == 6


@pytest.mark.parametrize("case", ALGORITHMS, ids=lambda case: case.name)
@pytest.mark.parametrize("size,k", [(20, 3), (60, 5), (150, 8)])
def test_reproducibility_after_intermediate_run(
    case: AlgorithmCase, size: int, k: int
) -> None:
    instance = load_artesp_instance(INSTANCES_DIR, size)
    first = _run(case, instance, k=k, seed=20260817)
    _run(case, TINY, k=2, seed=99)
    second = _run(case, instance, k=k, seed=20260817)
    assert first.reproducible_data() == second.reproducible_data()


def _global_rng_state() -> tuple[Any, ...]:
    name, keys, position, has_gauss, cached_gaussian = np.random.get_state()
    return name, keys.copy(), position, has_gauss, cached_gaussian


def _assert_rng_states_equal(left: tuple[Any, ...], right: tuple[Any, ...]) -> None:
    assert left[0] == right[0]
    assert np.array_equal(left[1], right[1])
    assert left[2:] == right[2:]


@pytest.mark.parametrize("case", ALGORITHMS, ids=lambda case: case.name)
def test_algorithm_isolation_preserves_global_rng_config_and_instance(
    case: AlgorithmCase,
) -> None:
    np.random.seed(123456)
    rng_before = _global_rng_state()
    config_before = repr(case.config)
    instance_arrays = {
        name: value.copy()
        for name, value in (
            ("demand", TINY.demand),
            ("production", TINY.production),
            ("s_territorial", TINY.s_territorial),
            ("t_terminal", TINY.t_terminal),
            ("i_integration", TINY.i_integration),
            ("o_market", TINY.o_market),
            ("w_affinity", TINY.w_affinity),
        )
    }

    _run(case, TINY, k=2, seed=7)

    _assert_rng_states_equal(rng_before, _global_rng_state())
    assert repr(case.config) == config_before
    assert all(
        np.array_equal(getattr(TINY, name), expected)
        for name, expected in instance_arrays.items()
    )
    assert all(not getattr(TINY, name).flags.writeable for name in instance_arrays)


def test_algorithm_results_do_not_depend_on_execution_order() -> None:
    forward = {
        case.name: _run(case, TINY, k=2, seed=31).reproducible_data()
        for case in ALGORITHMS
    }
    reverse = {
        case.name: _run(case, TINY, k=2, seed=31).reproducible_data()
        for case in reversed(ALGORITHMS)
    }
    assert forward == reverse
