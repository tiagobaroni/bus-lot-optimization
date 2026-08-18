"""Diário e regras operacionais da execução posterior da B11-E."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_batches import BenchmarkSelection, select_benchmark
from experiments.config import CampaignConfig
from experiments.execution import ExecutionSummary, execute_campaign
from experiments.provenance import capture_provenance, utc_now
from experiments.resource_monitor import ResourceMonitor, read_samples, summarize_samples
from experiments.storage import ScenarioState, artifact_paths, atomic_write_json, classify, read_json


def operational_root(config: CampaignConfig) -> Path:
    return config.repository_root / config.output_root / "operational" / config.name


def operation_path(
    config: CampaignConfig, selection: BenchmarkSelection, *, round_name: str
) -> Path:
    return operational_root(config) / "operations" / f"{selection.name}_{round_name}.json"


def resource_paths(
    config: CampaignConfig, selection: BenchmarkSelection, *, round_name: str
) -> tuple[Path, Path]:
    base = operational_root(config) / "resources" / f"{selection.name}_{round_name}"
    return base.with_suffix(".csv"), base.with_suffix(".json")


def _states(config: CampaignConfig, selection: BenchmarkSelection) -> dict[str, str]:
    root = config.repository_root / config.output_root
    return {
        scenario.scenario_id: classify(
            artifact_paths(root, config.purpose, scenario), scenario
        ).value
        for scenario in selection.scenarios
    }


def _failure_attempts(config: CampaignConfig, selection: BenchmarkSelection) -> dict[str, int]:
    root = config.repository_root / config.output_root
    values: dict[str, int] = {}
    for scenario in selection.scenarios:
        path = artifact_paths(root, config.purpose, scenario).failure
        values[scenario.scenario_id] = (
            len(read_json(path).get("attempts", [])) if path.exists() else 0
        )
    return values


def initial_coverage(config: CampaignConfig, *, batch: int) -> bool:
    selection = select_benchmark(config, batch=batch)
    return all(value != ScenarioState.PENDING.value for value in _states(config, selection).values())


def execute_operation(
    config: CampaignConfig,
    selection: BenchmarkSelection,
    *,
    workers: int,
    round_name: str,
    allow_dirty: bool = False,
    allow_unversioned: bool = False,
) -> tuple[ExecutionSummary, dict[str, Any]]:
    if round_name not in {"initial", "retry"}:
        raise ConfigurationError("rodada deve ser initial ou retry")
    before = _states(config, selection)
    attempts_before = _failure_attempts(config, selection)
    selected = selection.scenarios
    if round_name == "initial":
        # Falhas aguardam a rodada de retry; uma retomada inicial processa
        # somente IDs ausentes ou interrompidos.
        selected = tuple(
            item for item in selected
            if before[item.scenario_id] != ScenarioState.FAILED.value
        )
    else:
        if not initial_coverage(config, batch=selection.batch):
            raise ConfigurationError("nova tentativa exige cobertura inicial integral do lote")
        failed_ids = {
            identifier for identifier, state in before.items()
            if state == ScenarioState.FAILED.value
        }
        if any(attempts_before[identifier] != 1 for identifier in failed_ids):
            raise ConfigurationError("ID não é elegível para única nova tentativa")
        selected = tuple(item for item in selected if item.scenario_id in failed_ids)
        if not selected:
            raise ConfigurationError("nenhum ID elegível para nova tentativa")
    provenance = capture_provenance(
        config.repository_root,
        allow_dirty=allow_dirty,
        allow_unversioned=allow_unversioned,
    )
    started_at = utc_now()
    csv_path, summary_path = resource_paths(config, selection, round_name=round_name)
    with ResourceMonitor(csv_path, workers=workers):
        summary = execute_campaign(
            config,
            workers=workers,
            selected_scenarios=selected,
            allow_dirty=allow_dirty,
            allow_unversioned=allow_unversioned,
        )
    resource_summary = summarize_samples(read_samples(csv_path), workers=workers)
    atomic_write_json(summary_path, resource_summary)
    after = _states(config, selection)
    attempts_after = _failure_attempts(config, selection)
    path = operation_path(config, selection, round_name=round_name)
    previous_sessions = []
    previous_ids: set[str] = set()
    if path.exists():
        previous = read_json(path)
        previous_sessions = list(previous.get("sessions", []))
        previous_ids = set(previous.get("scenario_ids", []))
    session = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "states_before": before,
        "states_after": after,
        "attempts_before": attempts_before,
        "attempts_after": attempts_after,
        "summary": asdict(summary),
        "resource_summary": str(summary_path.relative_to(config.repository_root)),
    }
    document = {
        "schema_version": 1,
        "campaign": config.name,
        "batch": selection.batch,
        "selection": selection.name,
        "round": round_name,
        "workers": workers,
        "scenario_ids": sorted(previous_ids | {item.scenario_id for item in selected}),
        "scenario_ids_sha256": selection.ids_sha256,
        "resource_summary": session["resource_summary"],
        "sessions": [*previous_sessions, session],
        "provenance": provenance,
    }
    atomic_write_json(path, document)
    return summary, document


def blocked_failures(config: CampaignConfig, *, batch: int) -> tuple[str, ...]:
    selection = select_benchmark(config, batch=batch)
    states = _states(config, selection)
    attempts = _failure_attempts(config, selection)
    return tuple(sorted(
        identifier for identifier, state in states.items()
        if state == ScenarioState.FAILED.value and attempts[identifier] >= 2
    ))
