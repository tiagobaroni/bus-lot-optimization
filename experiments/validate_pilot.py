"""CLI da validação oficial do piloto B10."""

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
from experiments.pilot_validation import validate_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida o piloto pré-benchmark")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--skip-reproduction", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        result = validate_pilot(
            load_campaign(arguments.config), reproduce=not arguments.skip_reproduction
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
