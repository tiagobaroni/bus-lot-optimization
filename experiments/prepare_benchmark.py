"""Gera o roteiro estático que será usado na B11-E."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_freeze import verify_freeze_manifest
from experiments.config import load_campaign
from experiments.run_benchmark import DEFAULT_CONFIG, DEFAULT_PILOT, schedule_document
from experiments.storage import atomic_write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepara o roteiro estático da B11-E")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--pilot-runs", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--output", type=Path,
        default=Path("results/tables/benchmark_execution_schedule.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        config = load_campaign(arguments.config)
        verify_freeze_manifest(config.repository_root, workers=arguments.workers)
        document = schedule_document(
            config, pilot_runs=config.repository_root / arguments.pilot_runs
        )
        output = config.repository_root / arguments.output
        if not output.resolve().is_relative_to(config.repository_root):
            raise ConfigurationError("saída do roteiro deve permanecer no repositório")
        atomic_write_json(output, document)
        print(json.dumps({"path": str(arguments.output), "batches": 5, "subgroups": 270}, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
