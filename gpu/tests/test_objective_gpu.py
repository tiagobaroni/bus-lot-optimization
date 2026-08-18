from pathlib import Path

import numpy as np

from metaheuristica import ObjectiveWeights, load_artesp_instance, load_tiny_instance
from metaheuristica_gpu.numerics import verify_batch
from metaheuristica_gpu.objective import GpuBatchObjective


ROOT = Path(__file__).parents[2]


def _solutions(n: int, k: int, count: int) -> np.ndarray:
    return np.stack([
        np.roll(np.arange(n, dtype=np.int64) % k, shift)
        for shift in range(count)
    ])


def test_gpu_objective_matches_cpu_on_all_instances() -> None:
    instances = [
        load_tiny_instance(ROOT / "data/instances/tiny_manual.json"),
        *(load_artesp_instance(ROOT / "data/instances", size) for size in (20, 60, 150)),
    ]
    for instance in instances:
        k = 2 if instance.n_units < 20 else 5
        solutions = _solutions(instance.n_units, k, 2)
        with GpuBatchObjective(instance, k=k) as objective:
            results = objective.evaluate(solutions)
        assert verify_batch(
            instance, solutions, results, k=k, weights=ObjectiveWeights()
        ) <= 1e-12


def test_gpu_objective_preserves_batch_order_and_size_40() -> None:
    instance = load_artesp_instance(ROOT / "data/instances", 20)
    solutions = _solutions(20, 5, 40)
    with GpuBatchObjective(instance, k=5) as objective:
        results = objective.evaluate(solutions)
    assert len(results) == 40
    assert verify_batch(instance, solutions, results, k=5, weights=ObjectiveWeights()) <= 1e-12
