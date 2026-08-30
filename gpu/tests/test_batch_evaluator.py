from pathlib import Path

import numpy as np
import pytest

from metaheuristica import RunConfig, load_tiny_instance
from metaheuristica.errors import BudgetExhausted
from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.objective import GpuBatchObjective


ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("remaining,expected", [(1, 1), (39, 39), (40, 40), (41, 40)])
def test_lote_respeita_orcamento_sem_padding(remaining, expected):
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    solutions = [np.array([0, 0, 1, 1], dtype=np.int64)] * 40
    with GpuBatchObjective(instance, k=2) as objective:
        evaluator = HybridEvaluator(instance, RunConfig(k=2, seed=0, budget=100), objective)
        evaluator.evaluations = 100 - remaining
        batch = evaluator.evaluate_batch(solutions)
        assert len(batch.results) == expected
        assert evaluator.evaluations == 100 - remaining + expected
        if remaining <= 40:
            assert batch.exhausted
            with pytest.raises(BudgetExhausted):
                evaluator.evaluate_batch(solutions)
