"""CLI de análise e visualização do benchmark principal (B12)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

from experiments.benchmark_statistics import descriptive_summary, friedman_and_pairs

ALGORITHM_LABELS = {"tabu": "Busca Tabu", "aco": "ACO", "pso": "PSO"}
COLORS = {"tabu": "#1f77b4", "aco": "#ff7f0e", "pso": "#2ca02c"}


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _save_figure(figure: plt.Figure, base: Path) -> list[Path]:
    outputs = []
    base.parent.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        target = base.with_suffix(f".{extension}")
        temporary = target.with_name(f".{target.name}.tmp")
        figure.savefig(temporary, format=extension, dpi=180, bbox_inches="tight")
        os.replace(temporary, target)
        outputs.append(target)
    plt.close(figure)
    return outputs


def write_summary_tables(runs: pd.DataFrame, tables_dir: Path) -> dict[str, Path]:
    summary_path = tables_dir / "benchmark_summary.parquet"
    tests_path = tables_dir / "benchmark_statistical_tests.parquet"
    _atomic_parquet(summary_path, descriptive_summary(runs))
    _atomic_parquet(tests_path, friedman_and_pairs(runs))
    return {"summary": summary_path, "statistical_tests": tests_path}
