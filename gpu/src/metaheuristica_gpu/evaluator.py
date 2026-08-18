"""Contador, recorder e avaliação híbrida com orçamento estrito."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

import numpy as np

from metaheuristica import (
    ConvergenceCheckpoint, EvaluationResult, ObjectiveWeights, ProblemInstance,
    RunConfig, evaluate_solution, validate_solution,
)
from metaheuristica.errors import BudgetExhausted, EvaluationLimitReached
from metaheuristica.metrics import ConvergenceRecorder

from metaheuristica_gpu.numerics import verify_batch
from metaheuristica_gpu.objective import GpuBatchObjective, evaluate_provisional_cpu
from metaheuristica_gpu.timing import GpuTiming


@dataclass(frozen=True, slots=True)
class BatchEvaluation:
    solutions: tuple[np.ndarray, ...]
    results: tuple[EvaluationResult, ...]
    exhausted: bool


class HybridEvaluator:
    __slots__ = (
        "instance", "k", "budget", "weights", "evaluations", "recorder",
        "objective", "timing", "verify_every_batch", "max_numerical_difference",
        "guard",
    )

    def __init__(
        self,
        instance: ProblemInstance,
        run_config: RunConfig,
        objective: GpuBatchObjective,
        *,
        verify_every_batch: bool = False,
        guard: Callable[[], None] | None = None,
    ) -> None:
        self.instance = instance
        self.k = run_config.k
        self.budget = run_config.budget
        self.weights = run_config.weights
        self.evaluations = 0
        self.recorder = ConvergenceRecorder(run_config.thresholds)
        self.objective = objective
        self.timing = GpuTiming()
        self.verify_every_batch = verify_every_batch
        self.max_numerical_difference = 0.0
        self.guard = guard

    @property
    def remaining(self) -> int:
        return self.budget - self.evaluations

    @property
    def checkpoints(self) -> tuple[ConvergenceCheckpoint, ...]:
        return self.recorder.checkpoints

    @property
    def incumbent_solution(self) -> tuple[int, ...] | None:
        return self.recorder.incumbent_solution

    @property
    def incumbent_evaluation(self) -> EvaluationResult | None:
        return self.recorder.incumbent_evaluation

    def evaluate_batch(self, solutions: list[np.ndarray] | tuple[np.ndarray, ...]) -> BatchEvaluation:
        if self.guard is not None:
            self.guard()
        if self.remaining <= 0:
            raise BudgetExhausted("orçamento híbrido esgotado")
        accepted = tuple(
            validate_solution(item, n_units=self.instance.n_units, k=self.k)
            for item in solutions[: self.remaining]
        )
        if not accepted:
            raise ValueError("lote híbrido vazio")
        matrix = np.stack(accepted)
        results = self.objective.evaluate(matrix, timing=self.timing)
        if self.verify_every_batch:
            difference = verify_batch(
                self.instance, matrix, results, k=self.k, weights=self.weights
            )
            self.max_numerical_difference = max(self.max_numerical_difference, difference)
            # O modo de conformidade usa os valores normativos para permitir
            # comparação bit a bit do histórico, sem ser usado no speedup.
            results = tuple(
                evaluate_solution(self.instance, item, k=self.k, weights=self.weights)
                for item in matrix
            )
        for solution, result in zip(accepted, results):
            self.evaluations += 1
            self.recorder.observe(
                self.evaluations,
                tuple(int(value) for value in solution),
                result,
                True,
            )
        return BatchEvaluation(accepted, results, self.remaining == 0)

    def evaluate_provisional_for_repair(self, solution: Any) -> EvaluationResult:
        if self.guard is not None:
            self.guard()
        if self.remaining <= 0:
            raise BudgetExhausted("orçamento híbrido esgotado durante reparo")
        result = evaluate_provisional_cpu(
            self.instance, solution, k=self.k, weights=self.weights
        )
        self.evaluations += 1
        self.recorder.observe(self.evaluations, None, result, False)
        if self.remaining == 0:
            raise EvaluationLimitReached(result, "orçamento esgotado durante reparo")
        return result
