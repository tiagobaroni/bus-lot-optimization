"""Conformidade numérica e arbitragem normativa pela CPU."""

from __future__ import annotations

from dataclasses import fields
from math import isclose
from time import perf_counter
from typing import Iterable

import numpy as np

from metaheuristica import EvaluationResult, ObjectiveWeights, ProblemInstance, evaluate_solution

from metaheuristica_gpu.timing import GpuTiming


ABS_TOL = 1e-12
REL_TOL = 1e-12


class NumericalDivergenceError(RuntimeError):
    pass


def maximum_difference(left: EvaluationResult, right: EvaluationResult) -> float:
    return max(abs(getattr(left, item.name) - getattr(right, item.name)) for item in fields(EvaluationResult))


def require_equivalent(left: EvaluationResult, right: EvaluationResult) -> float:
    for item in fields(EvaluationResult):
        first = getattr(left, item.name)
        second = getattr(right, item.name)
        if not isclose(first, second, abs_tol=ABS_TOL, rel_tol=REL_TOL):
            raise NumericalDivergenceError(
                f"{item.name} diverge: GPU={first!r}, CPU={second!r}"
            )
    return maximum_difference(left, right)


def verify_batch(
    instance: ProblemInstance,
    solutions: np.ndarray,
    gpu_results: Iterable[EvaluationResult],
    *,
    k: int,
    weights: ObjectiveWeights,
) -> float:
    maximum = 0.0
    results = tuple(gpu_results)
    if len(results) != len(solutions):
        raise NumericalDivergenceError("quantidade de avaliações GPU divergente")
    for solution, gpu in zip(solutions, results):
        cpu = evaluate_solution(instance, solution, k=k, weights=weights)
        maximum = max(maximum, require_equivalent(gpu, cpu))
    return maximum


def arbitrate_best(
    instance: ProblemInstance,
    solutions: np.ndarray,
    gpu_results: tuple[EvaluationResult, ...],
    *,
    k: int,
    weights: ObjectiveWeights,
    timing: GpuTiming | None = None,
) -> tuple[int, EvaluationResult]:
    minimum = min(result.total_cost for result in gpu_results)
    candidates = [
        index for index, result in enumerate(gpu_results)
        if isclose(result.total_cost, minimum, abs_tol=ABS_TOL, rel_tol=REL_TOL)
    ]
    start = perf_counter()
    cpu_results = {
        index: evaluate_solution(instance, solutions[index], k=k, weights=weights)
        for index in candidates
    }
    if timing is not None:
        timing.arbitration_cpu_seconds += perf_counter() - start
    for index, cpu in cpu_results.items():
        require_equivalent(gpu_results[index], cpu)
    winner = min(
        candidates,
        key=lambda index: (
            cpu_results[index].total_cost,
            tuple(int(value) for value in solutions[index]),
        ),
    )
    return winner, cpu_results[winner]
