"""Orquestração comum e independente das metaheurísticas concretas."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any, Protocol, TypeVar

import numpy as np

from metaheuristica.canonical import canonicalize_solution
from metaheuristica.errors import BudgetExhausted, ConfigurationError
from metaheuristica.evaluator import FitnessEvaluator
from metaheuristica.metrics import (
    ConvergenceRecorder,
    OptimizationResult,
    RunConfig,
    TerminationReason,
)
from metaheuristica.problem import EvaluationResult, ProblemInstance


AlgorithmConfig = TypeVar("AlgorithmConfig")


class SearchRoutine(Protocol[AlgorithmConfig]):
    """Forma estrutural da rotina interna de uma metaheurística."""

    def __call__(
        self, context: OptimizationContext, config: AlgorithmConfig
    ) -> Mapping[str, Any] | None: ...


class OptimizationContext:
    """Capacidades controladas oferecidas a uma rotina de busca."""

    __slots__ = ("_diagnostics", "_evaluator", "_rng")

    def __init__(self, evaluator: FitnessEvaluator, rng: np.random.Generator) -> None:
        self._evaluator = evaluator
        self._rng = rng
        self._diagnostics: dict[str, Any] = {}

    @property
    def rng(self) -> np.random.Generator:
        return self._rng

    @property
    def evaluations(self) -> int:
        return self._evaluator.evaluations

    @property
    def remaining(self) -> int:
        return self._evaluator.remaining

    def evaluate(self, solution: Any) -> EvaluationResult:
        result = self._evaluator.evaluate(solution)
        self._stop_at_limit()
        return result

    def evaluate_provisional_for_repair(self, solution: Any) -> EvaluationResult:
        result = self._evaluator.evaluate_provisional_for_repair(solution)
        self._stop_at_limit()
        return result

    def update_diagnostics(self, **values: Any) -> None:
        self._diagnostics.update(values)

    @property
    def diagnostics(self) -> Mapping[str, Any]:
        return dict(self._diagnostics)

    def _stop_at_limit(self) -> None:
        if self._evaluator.remaining == 0:
            raise BudgetExhausted(
                f"orçamento esgotado: {self.evaluations}/{self.evaluations} avaliações"
            )


def execute_optimizer(
    instance: ProblemInstance,
    run_config: RunConfig,
    algorithm_config: AlgorithmConfig,
    *,
    algorithm: str,
    search: SearchRoutine[AlgorithmConfig],
    clock: Callable[[], float] = perf_counter,
) -> OptimizationResult:
    """Executa uma busca sob o contrato uniforme de orçamento e métricas."""

    if not isinstance(run_config, RunConfig):
        raise ConfigurationError("run_config deve ser RunConfig")
    if not isinstance(algorithm, str) or not algorithm.strip():
        raise ConfigurationError("algoritmo deve ser um texto não vazio")
    if not callable(search):
        raise ConfigurationError("search deve ser chamável")

    start = clock()
    rng = np.random.Generator(np.random.PCG64(run_config.seed))
    recorder = ConvergenceRecorder(run_config.thresholds)
    evaluator = FitnessEvaluator(
        instance,
        k=run_config.k,
        budget=run_config.budget,
        weights=run_config.weights,
        cache_enabled=run_config.cache_enabled,
        observer=recorder.observe,
    )
    context = OptimizationContext(evaluator, rng)
    returned_diagnostics: Mapping[str, Any] | None = None
    try:
        returned_diagnostics = search(context, algorithm_config)
    except BudgetExhausted:
        reason = TerminationReason.BUDGET_EXHAUSTED
    else:
        raise ConfigurationError("algoritmo encerrou antes de esgotar o orçamento")
    end = clock()

    if recorder.incumbent_solution is None or recorder.incumbent_evaluation is None:
        raise ConfigurationError("orçamento esgotado sem incumbente viável")
    if len(recorder.checkpoints) != run_config.checkpoint_count:
        raise ConfigurationError("execução terminou sem os 100 checkpoints")
    canonical = canonicalize_solution(
        recorder.incumbent_solution,
        n_units=instance.n_units,
        k=run_config.k,
    )
    diagnostics = dict(context.diagnostics)
    if returned_diagnostics:
        diagnostics.update(returned_diagnostics)
    return OptimizationResult(
        algorithm=algorithm,
        k=run_config.k,
        seed=run_config.seed,
        budget=run_config.budget,
        weights=run_config.weights,
        solution=canonical,
        evaluation=recorder.incumbent_evaluation,
        evaluations=evaluator.evaluations,
        cache_hits=evaluator.cache_hits,
        checkpoints=recorder.checkpoints,
        runtime_seconds=end - start,
        termination_reason=reason,
        diagnostics=diagnostics,
    )
