"""Tabela e figuras preliminares do piloto B10."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.storage import read_json


ALGORITHM_LABELS = {"tabu": "Busca Tabu", "aco": "ACO", "pso": "PSO"}
COLORS = {"tabu": "#1f77b4", "aco": "#ff7f0e", "pso": "#2ca02c"}


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(descriptor)
    temporary = Path(name)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _save_figure(figure: plt.Figure, base: Path) -> list[Path]:
    outputs: list[Path] = []
    base.parent.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        target = base.with_suffix(f".{extension}")
        temporary = target.with_name(f".{target.name}.tmp")
        figure.savefig(temporary, format=extension, dpi=180, bbox_inches="tight")
        os.replace(temporary, target)
        outputs.append(target)
    plt.close(figure)
    return outputs


def _instance_size(value: str) -> int:
    try:
        return int(value.rsplit("_", 1)[1])
    except (IndexError, ValueError) as error:
        raise ConfigurationError(f"instância inesperada: {value}") from error


def _convergence_figure(checkpoints: pd.DataFrame) -> plt.Figure:
    figure, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=False)
    for row, k in enumerate((3, 8)):
        for column, size in enumerate((20, 60, 150)):
            axis = axes[row, column]
            subset = checkpoints[
                (checkpoints["k"] == k)
                & (checkpoints["instance"].map(_instance_size) == size)
            ]
            for algorithm in ("tabu", "aco", "pso"):
                data = subset[subset["algorithm"] == algorithm].sort_values("evaluations")
                axis.plot(
                    data["evaluations"], data["total_cost"],
                    label=ALGORITHM_LABELS[algorithm], color=COLORS[algorithm],
                )
            axis.set_title(f"N={size}, K={k}")
            axis.grid(alpha=0.25)
            axis.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            axis.xaxis.set_major_formatter(
                FuncFormatter(lambda value, position: f"{value / 1000:g}")
            )
            if row == 1:
                axis.set_xlabel("Avaliações (mil)")
            if column == 0:
                axis.set_ylabel("Melhor custo")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=3
    )
    figure.suptitle("Convergência preliminar do piloto", y=0.995)
    figure.subplots_adjust(top=0.84, hspace=0.30, wspace=0.20)
    return figure


def _time_figure(runs: pd.DataFrame) -> plt.Figure:
    ordered = runs.assign(size=runs["instance"].map(_instance_size)).sort_values(
        ["size", "k", "algorithm"]
    )
    scenarios = [(size, k) for size in (20, 60, 150) for k in (3, 8)]
    x = np.arange(len(scenarios), dtype=float)
    width = 0.25
    figure, axis = plt.subplots(figsize=(11, 5))
    for offset, algorithm in enumerate(("tabu", "aco", "pso")):
        values = []
        for size, k in scenarios:
            row = ordered[
                (ordered["size"] == size) & (ordered["k"] == k)
                & (ordered["algorithm"] == algorithm)
            ]
            values.append(float(row.iloc[0]["runtime_seconds"]))
        axis.bar(
            x + (offset - 1) * width, values, width,
            label=ALGORITHM_LABELS[algorithm], color=COLORS[algorithm],
        )
    axis.set_xticks(x, [f"N={size}\nK={k}" for size, k in scenarios])
    axis.set_ylabel("Tempo de otimização (s)")
    axis.set_yscale("log")
    axis.set_title("Tempo preliminar do piloto")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    return figure


def _resources_figure(samples: pd.DataFrame) -> plt.Figure:
    figure, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    elapsed = samples["elapsed_seconds"]
    axes[0].plot(elapsed, samples["cpu_percent"], color="#9467bd")
    axes[0].set_ylabel("CPU (%)")
    axes[1].plot(elapsed, samples["rss_bytes"] / 1024 ** 3, color="#d62728")
    axes[1].set_ylabel("RSS (GiB)")
    axes[2].plot(
        elapsed, samples["memory_available_bytes"] / 1024 ** 3, color="#17becf"
    )
    axes[2].set_ylabel("Memória disponível (GiB)")
    axes[2].set_xlabel("Tempo monitorado (s)")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.suptitle("Recursos do piloto pré-benchmark")
    return figure


def generate_pilot_report(config: CampaignConfig) -> dict[str, Any]:
    if config.name != "pilot_prebenchmark":
        raise ConfigurationError("configuração não é o piloto B10")
    root = config.repository_root / config.output_root
    tables = root / "tables"
    figures = root / "figures"
    validation = read_json(tables / "pilot_validation.json")
    if validation.get("passed") is not True:
        raise ConfigurationError("validação do piloto não foi aprovada")
    runs = pd.read_parquet(tables / "pilot_runs.parquet")
    checkpoints = pd.read_parquet(tables / "pilot_checkpoints.parquet")
    samples = pd.read_parquet(tables / "pilot_resource_samples.parquet")
    if len(runs) != 18 or len(checkpoints) != 1_800:
        raise ConfigurationError("dados consolidados do piloto estão incompletos")

    columns = [
        "scenario_id", "algorithm", "instance", "k", "seed", "budget",
        "total_cost", "c_demand", "c_production", "c_territorial", "c_affinity",
        "evaluations", "runtime_seconds", "termination_reason", "official",
    ]
    table = runs[columns].sort_values(
        ["instance", "k", "algorithm"], ignore_index=True
    )
    csv_path = tables / "pilot_preliminary.csv"
    _atomic_csv(table, csv_path)
    output_paths = [csv_path]
    output_paths.extend(_save_figure(
        _convergence_figure(checkpoints), figures / "pilot_convergence"
    ))
    output_paths.extend(_save_figure(_time_figure(runs), figures / "pilot_time"))
    output_paths.extend(_save_figure(
        _resources_figure(samples), figures / "pilot_resources"
    ))
    return {
        "schema_version": 1,
        "campaign": config.name,
        "preliminary": True,
        "runs": len(runs),
        "checkpoints": len(checkpoints),
        "outputs": [str(path.relative_to(config.repository_root)) for path in output_paths],
    }
