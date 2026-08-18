"""CLI para gerar a apresentação preliminar da B10."""

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
from experiments.pilot_reporting import generate_pilot_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera artefatos preliminares do piloto")
    parser.add_argument("--config", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = generate_pilot_report(load_campaign(arguments.config))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
