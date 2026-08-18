"""Escalonamento determinístico da B11 baseado exclusivamente no piloto."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_batches import BenchmarkSelection, benchmark_subgroups, order_selection
from experiments.config import CampaignConfig
from experiments.scenarios import Scenario


@dataclass(frozen=True, slots=True)
class ScheduledSubgroup:
    selection: BenchmarkSelection
    estimated_seconds_per_run: float
    estimated_seconds_total: float
    rank: int


def load_pilot_estimates(path: Path) -> dict[tuple[str, str, int], float]:
    if not path.is_file():
        raise ConfigurationError(f"tempos do piloto ausentes: {path}")
    frame = pd.read_parquet(path)
    required = {"algorithm", "instance", "k", "runtime_seconds"}
    if not required <= set(frame.columns):
        raise ConfigurationError("tabela do piloto não contém colunas de tempo exigidas")
    anchors: dict[tuple[str, str, int], float] = {}
    for row in frame[list(required)].to_dict("records"):
        key = (str(row["algorithm"]), str(row["instance"]), int(row["k"]))
        value = float(row["runtime_seconds"])
        if key in anchors:
            raise ConfigurationError(f"tempo duplicado no piloto: {key}")
        if key[2] not in (3, 8) or not math.isfinite(value) or value <= 0:
            raise ConfigurationError(f"tempo inválido no piloto: {key}")
        anchors[key] = value
    pairs = {(algorithm, instance) for algorithm, instance, _ in anchors}
    if len(anchors) != 18 or len(pairs) != 9 or any(
        (algorithm, instance, k) not in anchors
        for algorithm, instance in pairs for k in (3, 8)
    ):
        raise ConfigurationError("piloto deve conter exatamente 18 âncoras K=3 e K=8")
    estimates: dict[tuple[str, str, int], float] = {}
    for algorithm, instance in pairs:
        lower = anchors[(algorithm, instance, 3)]
        upper = anchors[(algorithm, instance, 8)]
        for k in range(3, 9):
            estimates[(algorithm, instance, k)] = lower + (upper - lower) * (k - 3) / 5
    return estimates


def schedule_batch(
    config: CampaignConfig, *, batch: int, pilot_runs: Path
) -> tuple[ScheduledSubgroup, ...]:
    estimates = load_pilot_estimates(pilot_runs)
    pending: list[tuple[float, str, BenchmarkSelection]] = []
    for subgroup in benchmark_subgroups(config, batch):
        assert subgroup.algorithm is not None and subgroup.instance is not None and subgroup.k is not None
        key = (subgroup.algorithm, subgroup.instance, subgroup.k)
        if key not in estimates:
            raise ConfigurationError(f"estimativa ausente para {key}")
        estimate = estimates[key]
        ordered_scenarios = tuple(sorted(subgroup.scenarios, key=lambda item: item.scenario_id))
        ordered = order_selection(subgroup, ordered_scenarios)
        pending.append((-estimate, ordered.name, ordered))
    pending.sort(key=lambda item: (item[0], item[1]))
    return tuple(
        ScheduledSubgroup(selection, -negative, -negative * len(selection.scenarios), rank)
        for rank, (negative, _, selection) in enumerate(pending, start=1)
    )


def ordered_batch_scenarios(
    config: CampaignConfig, *, batch: int, pilot_runs: Path
) -> tuple[Scenario, ...]:
    return tuple(
        scenario
        for subgroup in schedule_batch(config, batch=batch, pilot_runs=pilot_runs)
        for scenario in subgroup.selection.scenarios
    )
