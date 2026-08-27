"""Estatísticas, ranking e sensibilidade descritiva do tuning."""

from __future__ import annotations

from itertools import product
import json
from math import isfinite
from typing import Any, Mapping

import numpy as np
import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.config import ALGORITHM_FIELDS, CampaignConfig
from experiments.scenarios import canonical_json


TOLERANCES: Mapping[str, float] = {
    "mean_cost": 1e-12,
    "std_cost": 1e-12,
    # Zero por desenho: segundos e custo adimensional não compartilham escala, e
    # afrouxar o tempo promove-o de critério de desempate a critério decisivo,
    # contra a hierarquia declarada na seção 12.1.
    "mean_runtime_seconds": 0.0,
}
COST_COLUMNS = (
    "total_cost", "c_demand", "c_production", "c_territorial", "c_affinity",
    "cv_demand", "cv_production", "runtime_seconds",
)


def _parameters(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ConfigurationError("parameters_json inválido") from error
    if not isinstance(value, dict):
        raise ConfigurationError("parameters_json deve representar objeto")
    return value


def _parameter_tuple(row: pd.Series) -> tuple[Any, ...]:
    return tuple(row[f"param_{name}"] for name in ALGORITHM_FIELDS[row["algorithm"]])


def _choose_best(frame: pd.DataFrame, indices: list[int]) -> int:
    candidates = list(indices)
    for column, tolerance in TOLERANCES.items():
        minimum = min(float(frame.loc[index, column]) for index in candidates)
        candidates = [
            index for index in candidates
            if float(frame.loc[index, column]) <= minimum + tolerance
        ]
    return min(candidates, key=lambda index: _parameter_tuple(frame.loc[index]))


def summarize_tuning(runs: pd.DataFrame, config: CampaignConfig) -> pd.DataFrame:
    """Valida execuções e devolve uma linha ranqueada por configuração."""

    required = {
        "scenario_id", "algorithm", "instance", "k", "seed", "budget",
        "cache_enabled", "parameters_json", "official", *COST_COLUMNS,
    }
    missing = required - set(runs.columns)
    if missing:
        raise ConfigurationError(f"runs sem colunas: {sorted(missing)}")
    if len(runs) != 440:
        raise ConfigurationError(f"tuning deve conter 440 execuções; recebeu {len(runs)}")
    if runs["scenario_id"].duplicated().any():
        raise ConfigurationError("runs contém scenario_id duplicado")
    if not runs["official"].map(lambda value: value is True).all():
        raise ConfigurationError("tuning contém resultado não oficial")
    if set(runs["algorithm"]) != set(ALGORITHM_FIELDS):
        raise ConfigurationError("tuning não contém exatamente os três algoritmos")
    if set(runs["instance"]) != {"artesp_rmsp_60"} or set(runs["k"]) != {5}:
        raise ConfigurationError("tuning usa instância ou K inesperado")
    if set(runs["budget"]) != {60000} or set(runs["cache_enabled"]) != {False}:
        raise ConfigurationError("tuning usa orçamento ou cache inesperado")
    for column in COST_COLUMNS:
        values = pd.to_numeric(runs[column], errors="coerce")
        if not np.isfinite(values.to_numpy(dtype=np.float64)).all():
            raise ConfigurationError(f"runs contém valor não finito em {column}")

    expected_grids = {
        algorithm: {
            canonical_json(dict(zip(fields, values))).decode("utf-8")
            for values in product(
                *(config.algorithms[algorithm][field] for field in fields)
            )
        }
        for algorithm, fields in ALGORITHM_FIELDS.items()
    }
    rows: list[dict[str, Any]] = []
    grouped = runs.groupby(["algorithm", "parameters_json"], sort=False)
    for (algorithm, parameters_text), group in grouped:
        parameters = _parameters(parameters_text)
        canonical_parameters = canonical_json(parameters).decode("utf-8")
        if canonical_parameters not in expected_grids[algorithm]:
            raise ConfigurationError(f"parâmetros fora da grade para {algorithm}")
        if set(group["seed"]) != set(range(10)) or len(group) != 10:
            raise ConfigurationError(
                f"configuração {algorithm} não contém exatamente as seeds 0 a 9"
            )
        costs = group["total_cost"].to_numpy(dtype=np.float64)
        row: dict[str, Any] = {
            "algorithm": algorithm,
            "parameters_json": canonical_parameters,
            "n_runs": len(group),
            "seeds_json": canonical_json(sorted(int(seed) for seed in group["seed"])).decode(),
            "mean_cost": float(np.mean(costs)),
            "std_cost": float(np.std(costs, ddof=1)),
            "min_cost": float(np.min(costs)),
            "median_cost": float(np.median(costs)),
            "max_cost": float(np.max(costs)),
            "mean_runtime_seconds": float(np.mean(group["runtime_seconds"])),
        }
        for column in (
            "c_demand", "c_production", "c_territorial", "c_affinity",
            "cv_demand", "cv_production",
        ):
            row[f"mean_{column}"] = float(np.mean(group[column]))
        for name in ALGORITHM_FIELDS[algorithm]:
            if name not in parameters:
                raise ConfigurationError(f"parâmetro ausente para {algorithm}: {name}")
            row[f"param_{name}"] = parameters[name]
        rows.append(row)
    summary = pd.DataFrame(rows)
    if len(summary) != 44:
        raise ConfigurationError(f"tuning deve conter 44 configurações; recebeu {len(summary)}")
    ranked_parts: list[pd.DataFrame] = []
    for algorithm in sorted(ALGORITHM_FIELDS):
        part = summary[summary["algorithm"] == algorithm].copy()
        remaining = list(part.index)
        indices: list[int] = []
        while remaining:
            best = _choose_best(part, remaining)
            indices.append(best)
            remaining.remove(best)
        part["rank"] = 0
        for rank, index in enumerate(indices, start=1):
            part.loc[index, "rank"] = rank
        part["selected"] = part["rank"] == 1
        ranked_parts.append(part)
    result = pd.concat(ranked_parts, ignore_index=True)
    result.sort_values(["algorithm", "rank"], inplace=True, ignore_index=True)
    if result.groupby("algorithm")["selected"].sum().to_dict() != {
        "aco": 1, "pso": 1, "tabu": 1,
    }:
        raise ConfigurationError("ranking não produziu um vencedor por algoritmo")
    return result


def parameter_effects(summary: pd.DataFrame) -> pd.DataFrame:
    """Calcula efeitos marginais puramente descritivos por nível."""

    rows: list[dict[str, Any]] = []
    for algorithm, fields in ALGORITHM_FIELDS.items():
        algorithm_rows = summary[summary["algorithm"] == algorithm]
        for field in fields:
            column = f"param_{field}"
            for level, group in algorithm_rows.groupby(column, sort=True):
                means = group["mean_cost"].to_numpy(dtype=np.float64)
                rows.append({
                    "algorithm": algorithm,
                    "parameter": field,
                    "level": float(level),
                    "n_configurations": len(group),
                    "n_runs": int(group["n_runs"].sum()),
                    "mean_of_mean_cost": float(np.mean(means)),
                    "std_of_mean_cost": float(np.std(means, ddof=1)),
                    "best_mean_cost": float(np.min(means)),
                    "worst_mean_cost": float(np.max(means)),
                    "mean_runtime_seconds": float(np.mean(group["mean_runtime_seconds"])),
                    "interpretation": "descriptive_noncausal",
                })
    result = pd.DataFrame(rows)
    result.sort_values(["algorithm", "parameter", "level"], inplace=True, ignore_index=True)
    return result
