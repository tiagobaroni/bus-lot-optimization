from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    FitnessEvaluator,
    OptimizationContext,
    RunConfig,
    evaluate_solution,
    execute_optimizer,
    load_artesp_instance,
    run_greedy,
)


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


@pytest.mark.parametrize("size", [20, 60, 150])
def test_greedy_runs_for_every_artesp_k_with_exact_budget(size: int) -> None:
    instance = load_artesp_instance(INSTANCES_DIR, size)
    for k in range(3, 9):
        result = run_greedy(instance, k=k)
        assert result.evaluations == k * (size - k)
        assert len(result.trace) == size - k
        assert len(set(result.solution)) == k
        public = evaluate_solution(instance, result.solution, k=k)
        assert np.allclose(
            (
                result.evaluation.total_cost,
                result.evaluation.c_demand,
                result.evaluation.c_production,
                result.evaluation.c_territorial,
                result.evaluation.c_affinity,
                result.evaluation.cv_demand,
                result.evaluation.cv_production,
            ),
            (
                public.total_cost,
                public.c_demand,
                public.c_production,
                public.c_territorial,
                public.c_affinity,
                public.cv_demand,
                public.cv_production,
            ),
            rtol=1e-12,
            atol=1e-12,
        )


def test_common_optimizer_contract_runs_on_artesp_instance() -> None:
    instance = load_artesp_instance(INSTANCES_DIR, 20)

    def search(context: OptimizationContext, config: None) -> None:
        base = np.arange(instance.n_units, dtype=np.int64) % 3
        shift = 0
        while True:
            context.evaluate(np.roll(base, shift))
            shift = (shift + 1) % instance.n_units

    result = execute_optimizer(
        instance,
        RunConfig(k=3, seed=20260817, budget=100),
        None,
        algorithm="integration_test",
        search=search,
    )
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert len(set(result.solution)) == 3
    assert np.isfinite(result.evaluation.total_cost)
