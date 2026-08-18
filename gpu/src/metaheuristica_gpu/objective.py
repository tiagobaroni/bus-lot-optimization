"""Função objetivo comum calculada em lotes pela GPU."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import cupy as cp
import numpy as np

from metaheuristica import EvaluationResult, ObjectiveWeights, ProblemInstance, validate_solution

from metaheuristica_gpu.timing import GpuTiming


class GpuObjectiveError(RuntimeError):
    pass


class GpuBatchObjective:
    """Mantém dados invariantes da instância residentes no dispositivo."""

    def __init__(
        self,
        instance: ProblemInstance,
        *,
        k: int,
        weights: ObjectiveWeights | None = None,
    ) -> None:
        self.instance = instance
        self.k = k
        self.weights = weights or ObjectiveWeights()
        row, column = np.triu_indices(instance.n_units, k=1)
        self._row = cp.asarray(row, dtype=cp.int64)
        self._column = cp.asarray(column, dtype=cp.int64)
        self._demand = cp.asarray(instance.demand, dtype=cp.float64)
        self._production = cp.asarray(instance.production, dtype=cp.float64)
        self._territorial = cp.asarray(instance.s_territorial[row, column], dtype=cp.float64)
        self._affinity = cp.asarray(instance.w_affinity[row, column], dtype=cp.float64)
        self._territorial_total = cp.sum(self._territorial, dtype=cp.float64)
        self._affinity_total = cp.sum(self._affinity, dtype=cp.float64)
        self._lots = cp.arange(k, dtype=cp.int64)
        cp.cuda.get_current_stream().synchronize()

    def evaluate(self, solutions: Any, *, timing: GpuTiming | None = None) -> tuple[EvaluationResult, ...]:
        host = np.asarray(solutions)
        if host.ndim != 2 or host.shape[1] != self.instance.n_units:
            raise GpuObjectiveError(
                f"lote deve ter dimensão (B, {self.instance.n_units})"
            )
        if not 1 <= host.shape[0] <= 40:
            raise GpuObjectiveError("lote deve conter entre 1 e 40 candidatos")
        if not np.issubdtype(host.dtype, np.integer) or np.issubdtype(host.dtype, np.bool_):
            raise GpuObjectiveError("soluções GPU devem conter rótulos inteiros")
        canonical = np.stack([
            validate_solution(item, n_units=self.instance.n_units, k=self.k)
            for item in host
        ]).astype(np.int64, copy=False)
        tracker = timing or GpuTiming()
        start = perf_counter()
        labels = cp.asarray(canonical, dtype=cp.int64)
        cp.cuda.get_current_stream().synchronize()
        tracker.host_to_device_seconds += perf_counter() - start

        start = perf_counter()
        membership = labels[:, :, None] == self._lots[None, None, :]
        demand_totals = cp.sum(
            membership * self._demand[None, :, None], axis=1, dtype=cp.float64
        )
        production_totals = cp.sum(
            membership * self._production[None, :, None], axis=1, dtype=cp.float64
        )
        demand_mean = cp.mean(demand_totals, axis=1)
        production_mean = cp.mean(production_totals, axis=1)
        cv_demand = cp.std(demand_totals, axis=1, ddof=0) / demand_mean
        cv_production = cp.std(production_totals, axis=1, ddof=0) / production_mean
        c_demand = cv_demand / (1.0 + cv_demand)
        c_production = cv_production / (1.0 + cv_production)
        cut = labels[:, self._row] != labels[:, self._column]
        territorial_cut = cp.sum(cut * self._territorial[None, :], axis=1, dtype=cp.float64)
        affinity_cut = cp.sum(cut * self._affinity[None, :], axis=1, dtype=cp.float64)
        c_territorial = cp.where(
            self._territorial_total == 0.0, 0.0, territorial_cut / self._territorial_total
        )
        c_affinity = cp.where(
            self._affinity_total == 0.0, 0.0, affinity_cut / self._affinity_total
        )
        total = (
            self.weights.demand * c_demand
            + self.weights.production * c_production
            + self.weights.territorial * c_territorial
            + self.weights.affinity * c_affinity
        )
        matrix = cp.stack(
            (total, c_demand, c_production, c_territorial, c_affinity, cv_demand, cv_production),
            axis=1,
        )
        cp.cuda.get_current_stream().synchronize()
        tracker.kernel_seconds += perf_counter() - start

        start = perf_counter()
        values = cp.asnumpy(matrix)
        cp.cuda.get_current_stream().synchronize()
        tracker.device_to_host_seconds += perf_counter() - start
        tracker.batches += 1
        tracker.candidates += len(canonical)
        return tuple(EvaluationResult(*map(float, row_values)) for row_values in values)

    def close(self) -> None:
        for name in (
            "_row", "_column", "_demand", "_production", "_territorial",
            "_affinity", "_territorial_total", "_affinity_total", "_lots",
        ):
            setattr(self, name, None)
        cp.get_default_memory_pool().free_all_blocks()
        cp.get_default_pinned_memory_pool().free_all_blocks()

    def __enter__(self) -> "GpuBatchObjective":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def evaluate_provisional_cpu(
    instance: ProblemInstance,
    solution: Any,
    *,
    k: int,
    weights: ObjectiveWeights,
) -> EvaluationResult:
    labels = np.asarray(solution)
    if labels.shape != (instance.n_units,) or not np.issubdtype(labels.dtype, np.integer):
        raise GpuObjectiveError("solução provisória inválida")
    labels = labels.astype(np.int64, copy=False)
    if np.any(labels < 0) or np.any(labels >= k):
        raise GpuObjectiveError("rótulo provisório fora do intervalo")
    demand = np.bincount(labels, weights=instance.demand, minlength=k)
    production = np.bincount(labels, weights=instance.production, minlength=k)
    demand_mean = float(np.mean(demand))
    production_mean = float(np.mean(production))
    cv_demand = float(np.std(demand, ddof=0) / demand_mean)
    cv_production = float(np.std(production, ddof=0) / production_mean)
    c_demand = cv_demand / (1.0 + cv_demand)
    c_production = cv_production / (1.0 + cv_production)
    row, column = np.triu_indices(instance.n_units, k=1)
    separated = labels[row] != labels[column]
    territorial_values = instance.s_territorial[row, column]
    affinity_values = instance.w_affinity[row, column]
    territorial_total = float(np.sum(territorial_values))
    affinity_total = float(np.sum(affinity_values))
    c_territorial = (
        0.0 if territorial_total == 0.0
        else float(np.sum(territorial_values[separated])) / territorial_total
    )
    c_affinity = (
        0.0 if affinity_total == 0.0
        else float(np.sum(affinity_values[separated])) / affinity_total
    )
    total = (
        weights.demand * c_demand + weights.production * c_production
        + weights.territorial * c_territorial + weights.affinity * c_affinity
    )
    return EvaluationResult(
        total, c_demand, c_production, c_territorial, c_affinity,
        cv_demand, cv_production,
    )
