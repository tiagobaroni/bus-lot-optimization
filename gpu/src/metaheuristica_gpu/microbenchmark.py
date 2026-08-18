"""Microbenchmark diagnóstico da avaliação em lote CPU x GPU."""

from __future__ import annotations

from statistics import median
from time import perf_counter

import cupy as cp
import numpy as np

from metaheuristica import ObjectiveWeights, ProblemInstance, evaluate_solution

from metaheuristica_gpu.numerics import verify_batch
from metaheuristica_gpu.objective import GpuBatchObjective
from metaheuristica_gpu.timing import GpuTiming, warmup_gpu


def run_microbenchmark(
    instance: ProblemInstance,
    solutions: np.ndarray,
    *,
    k: int,
    repetitions: int = 10,
) -> dict[str, object]:
    if repetitions <= 0:
        raise ValueError("repetições devem ser positivas")
    weights = ObjectiveWeights()
    warmup = warmup_gpu()
    objective = GpuBatchObjective(instance, k=k, weights=weights)
    cpu_times = []; gpu_times = []; differences = []; timing = GpuTiming()
    try:
        for _ in range(repetitions):
            start = perf_counter()
            cpu = tuple(evaluate_solution(instance, item, k=k, weights=weights) for item in solutions)
            cpu_times.append(perf_counter() - start)
            cp.cuda.get_current_stream().synchronize(); start = perf_counter()
            gpu = objective.evaluate(solutions, timing=timing)
            cp.cuda.get_current_stream().synchronize(); gpu_times.append(perf_counter() - start)
            differences.append(verify_batch(instance, solutions, gpu, k=k, weights=weights))
            assert len(cpu) == len(gpu)
    finally:
        objective.close()
    cpu_median = median(cpu_times); gpu_median = median(gpu_times)
    return {
        "schema_version": 1, "batch_size": len(solutions), "repetitions": repetitions,
        "cpu_seconds": cpu_times, "gpu_seconds": gpu_times,
        "cpu_median_seconds": cpu_median, "gpu_median_seconds": gpu_median,
        "diagnostic_speedup": cpu_median / gpu_median,
        "maximum_difference": max(differences), "warmup": warmup,
        "gpu_timing": timing.to_dict(),
    }
