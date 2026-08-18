"""CLI da automação experimental."""

from __future__ import annotations

import os

for _thread_variable in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "ARROW_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
import json
from pathlib import Path
import sys

from metaheuristica.errors import ConfigurationError

from experiments.config import load_campaign
from experiments.consolidation import consolidate_campaign
from experiments.execution import build_plan, execute_campaign
from experiments.provenance import capture_provenance


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automação de experimentos")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--scenario-id")
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--allow-unversioned", action="store_true")
    parser.add_argument("--monitor-resources", action="store_true")
    parser.add_argument("operation", choices=("plan", "execute", "consolidate"))
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = load_campaign(arguments.config)
        if arguments.operation == "plan":
            if (arguments.allow_incomplete or arguments.fail_fast
                    or arguments.workers != 1 or arguments.monitor_resources):
                raise ConfigurationError("plan recebeu opções exclusivas de execução ou consolidação")
            plan = build_plan(
                config, scenario_id=arguments.scenario_id, max_runs=arguments.max_runs
            )
            provenance = capture_provenance(
                config.repository_root, allow_dirty=True, allow_unversioned=True
            )
            print(json.dumps({
                "campaign": config.name, "purpose": config.purpose,
                "expected": plan.expected, "completed": plan.completed,
                "failed": plan.failed, "pending": plan.pending,
                "selected": len(plan.selected), "git_commit": provenance["git_commit"],
                "git_dirty": provenance["git_dirty"],
                "by_algorithm": plan.by_algorithm,
                "by_instance": plan.by_instance,
                "by_k": plan.by_k,
            }, ensure_ascii=False, sort_keys=True))
            return 0
        if arguments.operation == "execute":
            if arguments.allow_incomplete:
                raise ConfigurationError("--allow-incomplete é exclusivo de consolidate")
            if config.purpose == "benchmark":
                from experiments.benchmark_freeze import verify_freeze_manifest
                verify_freeze_manifest(
                    config.repository_root, workers=arguments.workers
                )
            def execute():
                return execute_campaign(
                    config, workers=arguments.workers,
                    scenario_id=arguments.scenario_id, max_runs=arguments.max_runs,
                    fail_fast=arguments.fail_fast, allow_dirty=arguments.allow_dirty,
                    allow_unversioned=arguments.allow_unversioned,
                )

            if arguments.monitor_resources:
                from experiments.resource_monitor import ResourceMonitor
                monitor_path = (
                    config.repository_root / config.output_root / "operational"
                    / config.name / "resources.csv"
                )
                with ResourceMonitor(monitor_path, workers=arguments.workers):
                    summary = execute()
            else:
                summary = execute()
            print(json.dumps(summary.__dict__ if hasattr(summary, "__dict__") else {
                field: getattr(summary, field) for field in summary.__dataclass_fields__
            }, sort_keys=True))
            if summary.interrupted:
                return 130
            return 3 if summary.failed else 0
        if (arguments.scenario_id or arguments.max_runs is not None
                or arguments.fail_fast or arguments.workers != 1
                or arguments.monitor_resources):
            raise ConfigurationError("consolidate recebeu opção incompatível")
        manifest = consolidate_campaign(
            config, allow_incomplete=arguments.allow_incomplete,
            allow_dirty=arguments.allow_dirty,
            allow_unversioned=arguments.allow_unversioned,
        )
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
