from pathlib import Path

import numpy as np

from metaheuristica import load_tiny_instance
from metaheuristica_gpu.microbenchmark import run_microbenchmark


ROOT = Path(__file__).parents[2]


def test_microbenchmark_valida_e_separa_tempos():
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    solutions = np.array([[0, 0, 1, 1], [0, 1, 0, 1]], dtype=np.int64)
    report = run_microbenchmark(instance, solutions, k=2, repetitions=2)
    assert report["maximum_difference"] <= 1e-12
    assert report["cpu_median_seconds"] > 0
    assert report["gpu_median_seconds"] > 0
    assert report["warmup"]["warmup_seconds"] >= 0
