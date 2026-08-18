"""CLI para gerar ou verificar o congelamento da B11."""

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

from experiments.benchmark_freeze import generate_freeze_manifest, verify_freeze_manifest
from experiments.config import load_campaign


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Congela ou verifica o benchmark")
    parser.add_argument("operation", choices=("generate", "verify"))
    parser.add_argument("--config", type=Path, default=Path("experiments/configs/pilot.toml"))
    parser.add_argument("--workers", type=int, required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.operation == "generate":
            result = generate_freeze_manifest(
                load_campaign(arguments.config), workers=arguments.workers
            )
        else:
            root = Path(__file__).resolve().parents[1]
            result = verify_freeze_manifest(root, workers=arguments.workers)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
