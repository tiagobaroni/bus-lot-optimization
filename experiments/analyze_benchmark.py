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


def by_k_table(runs: pd.DataFrame) -> pd.DataFrame:
    grouped = runs.groupby(["algorithm", "instance", "k"], as_index=False).agg(
        total_cost=("total_cost", "mean"),
        cv_demand=("cv_demand", "mean"),
        cv_production=("cv_production", "mean"),
        c_territorial=("c_territorial", "mean"),
        c_affinity=("c_affinity", "mean"),
    )
    return grouped.sort_values(["instance", "k", "algorithm"]).reset_index(drop=True)


def vs_greedy_table(runs: pd.DataFrame, greedy_runs: pd.DataFrame) -> pd.DataFrame:
    summary = runs.groupby(["algorithm", "instance", "k"], as_index=False).agg(
        total_cost=("total_cost", "mean"),
        runtime_seconds=("runtime_seconds", "mean"),
    )
    merged = summary.merge(
        greedy_runs[["instance", "k", "total_cost", "runtime_seconds"]],
        on=["instance", "k"], suffixes=("", "_greedy"),
    )
    merged["cost_difference"] = merged["total_cost"] - merged["total_cost_greedy"]
    merged["improvement_percent"] = (
        (merged["total_cost_greedy"] - merged["total_cost"])
        / merged["total_cost_greedy"] * 100
    )
    merged["time_ratio_vs_greedy"] = (
        merged["runtime_seconds"] / merged["runtime_seconds_greedy"]
    )
    return merged.sort_values(["instance", "k", "algorithm"]).reset_index(drop=True)


def write_by_k_and_greedy_tables(
    runs: pd.DataFrame, greedy_runs: pd.DataFrame, tables_dir: Path
) -> dict[str, Path]:
    by_k_path = tables_dir / "benchmark_by_k.parquet"
    vs_greedy_path = tables_dir / "benchmark_vs_greedy.parquet"
    _atomic_parquet(by_k_path, by_k_table(runs))
    _atomic_parquet(vs_greedy_path, vs_greedy_table(runs, greedy_runs))
    return {"by_k": by_k_path, "vs_greedy": vs_greedy_path}
