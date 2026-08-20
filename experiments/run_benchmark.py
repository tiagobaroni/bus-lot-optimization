"""Interface operacional pronta para a execução controlada da B11-E."""

from __future__ import annotations

import os

for _thread_variable in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "ARROW_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_batches import (
    BenchmarkSelection, select_benchmark, validate_benchmark_partition,
)
from experiments.benchmark_freeze import verify_freeze_manifest
from experiments.benchmark_operations import execute_operation
from experiments.benchmark_schedule import ordered_batch_scenarios, schedule_batch
from experiments.benchmark_validation import finalize_benchmark, validate_batch
from experiments.config import CampaignConfig, load_campaign
from experiments.execution import build_plan
from experiments.provenance import capture_provenance
from experiments.scenarios import Scenario, canonical_json
from experiments.storage import read_json, validate_document


DEFAULT_CONFIG = Path("experiments/configs/benchmark.toml")
DEFAULT_PILOT = Path("results/tables/pilot_runs.parquet")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orquestra o benchmark CPU da B11-E")
    parser.add_argument("operation", choices=("readiness", "schedule", "plan", "execute", "retry", "barrier", "finalize"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--pilot-runs", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--batch", type=int)
    parser.add_argument("--algorithm")
    parser.add_argument("--instance")
    parser.add_argument("--k", type=int)
    parser.add_argument("--workers", type=int, default=16)
    return parser


def _selection(arguments: argparse.Namespace, config: CampaignConfig) -> BenchmarkSelection:
    if arguments.batch is None:
        raise ConfigurationError("operação exige --batch")
    return select_benchmark(
        config, batch=arguments.batch, algorithm=arguments.algorithm,
        instance=arguments.instance, k=arguments.k,
    )


def _ordered_selection(
    arguments: argparse.Namespace, config: CampaignConfig
) -> BenchmarkSelection:
    selection = _selection(arguments, config)
    pilot = config.repository_root / arguments.pilot_runs
    ordered = ordered_batch_scenarios(config, batch=selection.batch, pilot_runs=pilot)
    allowed = {item.scenario_id for item in selection.scenarios}
    scenarios = tuple(item for item in ordered if item.scenario_id in allowed)
    return BenchmarkSelection(
        selection.batch, selection.seeds, scenarios,
        selection.algorithm, selection.instance, selection.k,
    )


def inspect_existing_results(
    config: CampaignConfig, known: dict[str, Scenario]
) -> dict[str, list[str]]:
    """Inspeciona, e não apenas conta, o que já existe em resultados.

    Contar deixava passar resultado não oficial, isto é gerado com
    ``--allow-dirty`` ou sem versionamento, que a retomada adotava em silêncio
    como concluído.
    """

    raw = config.repository_root / config.output_root / "raw" / config.purpose
    if not raw.exists():
        return {"existing": [], "unexpected": [], "nonofficial": []}
    existing = sorted(path.name for path in raw.glob("*.json"))
    return {
        "existing": existing,
        "unexpected": [name for name in existing if name not in known],
        "nonofficial": [
            name for name in existing if name in known
            and validate_document(
                read_json(raw / name), known[name]
            ).get("official") is not True
        ],
    }


def readiness(config: CampaignConfig, *, workers: int, pilot_runs: Path) -> dict[str, object]:
    freeze = verify_freeze_manifest(config.repository_root, workers=workers)
    partition = validate_benchmark_partition(config)
    schedules = [schedule_batch(config, batch=batch, pilot_runs=pilot_runs) for batch in range(1, 6)]
    known = {
        item.filename: item
        for batch in schedules for group in batch for item in group.selection.scenarios
    }
    inspection = inspect_existing_results(config, known)
    unexpected = inspection["unexpected"]
    if unexpected:
        raise ConfigurationError(f"resultados inesperados: {unexpected}")
    if inspection["nonofficial"]:
        raise ConfigurationError(
            f"resultados não oficiais: {inspection['nonofficial']}"
        )
    provenance = capture_provenance(config.repository_root, allow_dirty=True)
    if provenance["git_dirty"]:
        raise ConfigurationError("prontidão exige worktree limpa")
    schedule_path = config.repository_root / "results/tables/benchmark_execution_schedule.json"
    if not schedule_path.is_file():
        raise ConfigurationError("roteiro versionado do benchmark ausente")
    expected_schedule = schedule_document(config, pilot_runs=pilot_runs)
    if canonical_json(read_json(schedule_path)) != canonical_json(expected_schedule):
        raise ConfigurationError("roteiro versionado diverge do escalonamento recalculado")
    return {
        "schema_version": 1,
        "ready": True,
        "campaign": config.name,
        "workers": workers,
        "partition": partition,
        "scheduled_subgroups": sum(len(items) for items in schedules),
        "estimated_seconds": sum(
            item.estimated_seconds_total for items in schedules for item in items
        ),
        "freeze_schema_version": freeze["schema_version"],
        "git_commit": provenance["git_commit"],
        "git_dirty": provenance["git_dirty"],
        "existing_results": len(inspection["existing"]),
        "unexpected_results": unexpected,
        "nonofficial_results": inspection["nonofficial"],
    }


def schedule_document(config: CampaignConfig, *, pilot_runs: Path) -> dict[str, object]:
    batches = []
    for batch in range(1, 6):
        groups = schedule_batch(config, batch=batch, pilot_runs=pilot_runs)
        batches.append({
            "batch": batch,
            "seeds": list(groups[0].selection.seeds),
            "estimated_seconds": sum(item.estimated_seconds_total for item in groups),
            "subgroups": [{
                "rank": item.rank,
                "name": item.selection.name,
                "algorithm": item.selection.algorithm,
                "instance": item.selection.instance,
                "k": item.selection.k,
                "scenario_ids": [scenario.scenario_id for scenario in item.selection.scenarios],
                "estimated_seconds_per_run": item.estimated_seconds_per_run,
                "estimated_seconds_total": item.estimated_seconds_total,
            } for item in groups],
        })
    return {"schema_version": 1, "campaign": config.name, "batches": batches}


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = load_campaign(arguments.config)
        if config.purpose != "benchmark":
            raise ConfigurationError("CLI da B11 exige finalidade benchmark")
        if arguments.workers != 16:
            raise ConfigurationError("benchmark oficial exige exatamente 16 workers")
        pilot = config.repository_root / arguments.pilot_runs
        if arguments.operation in {"readiness", "schedule", "plan"}:
            # Também impede planejar silenciosamente uma infraestrutura divergente.
            verify_freeze_manifest(config.repository_root, workers=arguments.workers)
        if arguments.operation == "readiness":
            if arguments.batch is not None or any((arguments.algorithm, arguments.instance, arguments.k)):
                raise ConfigurationError("readiness não aceita filtros")
            output = readiness(config, workers=arguments.workers, pilot_runs=pilot)
        elif arguments.operation == "schedule":
            if arguments.batch is not None or any((arguments.algorithm, arguments.instance, arguments.k)):
                raise ConfigurationError("schedule não aceita filtros")
            output = schedule_document(config, pilot_runs=pilot)
        elif arguments.operation == "plan":
            selection = _ordered_selection(arguments, config)
            plan = build_plan(config, selected_scenarios=selection.scenarios)
            output = {
                "campaign": config.name, "batch": selection.batch,
                "selection": selection.name, "seeds": list(selection.seeds),
                "expected": len(selection.scenarios), "selected": len(plan.selected),
                "completed_total": plan.completed, "failed_total": plan.failed,
                "pending_total": plan.pending, "scenario_ids_sha256": selection.ids_sha256,
            }
        elif arguments.operation == "execute":
            verify_freeze_manifest(config.repository_root, workers=arguments.workers)
            selection = _ordered_selection(arguments, config)
            summary, operation = execute_operation(
                config, selection, workers=arguments.workers, round_name="initial"
            )
            output = {"summary": asdict(summary), "operation": operation}
            print(json.dumps(output, ensure_ascii=False, sort_keys=True))
            return 130 if summary.interrupted else (3 if summary.failed else 0)
        elif arguments.operation == "retry":
            if any((arguments.algorithm, arguments.instance, arguments.k)):
                raise ConfigurationError("retry opera sobre todas as falhas do lote")
            verify_freeze_manifest(config.repository_root, workers=arguments.workers)
            selection = _ordered_selection(arguments, config)
            summary, operation = execute_operation(
                config, selection, workers=arguments.workers, round_name="retry"
            )
            output = {"summary": asdict(summary), "operation": operation}
            print(json.dumps(output, ensure_ascii=False, sort_keys=True))
            return 3 if summary.failed else 0
        elif arguments.operation == "barrier":
            if arguments.batch is None or any((arguments.algorithm, arguments.instance, arguments.k)):
                raise ConfigurationError("barrier exige somente --batch")
            # O congelamento e a proveniência são conferidos dentro da barreira,
            # que também os registra no relatório do lote.
            output = validate_batch(
                config, batch=arguments.batch, workers=arguments.workers
            )
        else:
            if arguments.batch is not None or any((arguments.algorithm, arguments.instance, arguments.k)):
                raise ConfigurationError("finalize não aceita filtros")
            verify_freeze_manifest(config.repository_root, workers=arguments.workers)
            output = finalize_benchmark(config)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
