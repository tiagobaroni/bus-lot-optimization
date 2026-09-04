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


def convergence_figure(checkpoints: pd.DataFrame, *, instance: str) -> plt.Figure:
    subset = checkpoints[
        (checkpoints["instance"] == instance) & (checkpoints["k"] == 5)
    ]
    figure, axis = plt.subplots(figsize=(7, 5))
    for algorithm in ("tabu", "aco", "pso"):
        data = subset[subset["algorithm"] == algorithm]
        budget = data["evaluations"].max()
        percent = data["evaluations"] / budget * 100
        grouped = data.assign(percent=percent).groupby("index").agg(
            percent=("percent", "first"),
            median=("total_cost", "median"),
            q1=("total_cost", lambda s: s.quantile(0.25)),
            q3=("total_cost", lambda s: s.quantile(0.75)),
        ).sort_values("percent")
        axis.plot(
            grouped["percent"], grouped["median"],
            label=ALGORITHM_LABELS[algorithm], color=COLORS[algorithm],
        )
        axis.fill_between(
            grouped["percent"], grouped["q1"], grouped["q3"],
            color=COLORS[algorithm], alpha=0.15,
        )
    axis.set_xlabel("Orçamento consumido (%)")
    axis.set_ylabel("Melhor custo (mediana e IQR)")
    axis.set_title(f"Convergência — {instance}, K=5")
    axis.grid(alpha=0.25)
    axis.legend()
    return figure


def write_convergence_figures(
    checkpoints: pd.DataFrame, figures_dir: Path
) -> dict[str, list[Path]]:
    outputs: dict[str, list[Path]] = {}
    for instance in sorted(checkpoints["instance"].unique()):
        size = instance.rsplit("_", 1)[1]
        figure = convergence_figure(checkpoints, instance=instance)
        outputs[instance] = _save_figure(
            figure, figures_dir / f"benchmark_convergence_{size}"
        )
    return outputs


def _instance_size(value: str) -> int:
    return int(value.rsplit("_", 1)[1])


def scalability_figures(runs: pd.DataFrame) -> dict[str, plt.Figure]:
    subset = runs[runs["k"] == 5].assign(size=lambda d: d["instance"].map(_instance_size))
    figures = {}
    for key, column, ylabel in (
        ("time", "runtime_seconds", "Tempo médio de otimização (s)"),
        ("quality", "total_cost", "Custo final médio"),
    ):
        figure, axis = plt.subplots(figsize=(7, 5))
        for algorithm in ("tabu", "aco", "pso"):
            data = subset[subset["algorithm"] == algorithm].groupby("size", as_index=False)[column].mean()
            data = data.sort_values("size")
            axis.plot(
                data["size"], data[column],
                marker="o", label=ALGORITHM_LABELS[algorithm], color=COLORS[algorithm],
            )
        axis.set_xlabel("Tamanho da instância (N)")
        axis.set_ylabel(ylabel)
        axis.set_title(f"Escalabilidade — {ylabel}, K=5")
        axis.grid(alpha=0.25)
        axis.legend()
        figures[key] = figure
    return figures


def write_scalability_figures(runs: pd.DataFrame, figures_dir: Path) -> dict[str, list[Path]]:
    outputs = {}
    for key, figure in scalability_figures(runs).items():
        outputs[key] = _save_figure(figure, figures_dir / f"benchmark_scalability_{key}")
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Análise e visualização do benchmark (B12)")
    parser.add_argument("--tables-dir", type=Path, default=Path("results/tables"))
    parser.add_argument("--figures-dir", type=Path, default=Path("results/figures"))
    arguments = parser.parse_args(argv)

    runs = pd.read_parquet(arguments.tables_dir / "benchmark_runs.parquet")
    checkpoints = pd.read_parquet(arguments.tables_dir / "benchmark_checkpoints.parquet")
    greedy_runs = pd.read_parquet(arguments.tables_dir / "greedy_runs.parquet")

    summary_paths = write_summary_tables(runs, arguments.tables_dir)
    by_k_paths = write_by_k_and_greedy_tables(runs, greedy_runs, arguments.tables_dir)
    convergence_paths = write_convergence_figures(checkpoints, arguments.figures_dir)
    scalability_paths = write_scalability_figures(runs, arguments.figures_dir)

    report = {
        "tables": {
            **{key: str(path) for key, path in summary_paths.items()},
            **{key: str(path) for key, path in by_k_paths.items()},
        },
        "figures": {
            "convergence": {k: [str(p) for p in v] for k, v in convergence_paths.items()},
            "scalability": {k: [str(p) for p in v] for k, v in scalability_paths.items()},
        },
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
