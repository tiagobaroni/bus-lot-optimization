"""Estatística descritiva e inferencial do benchmark principal."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

ALGORITHMS = ("aco", "pso", "tabu")


def descriptive_summary(runs: pd.DataFrame) -> pd.DataFrame:
    grouped = runs.groupby(["algorithm", "instance", "k"], as_index=False).agg(
        cost_mean=("total_cost", "mean"),
        cost_std=("total_cost", lambda s: s.std(ddof=1)),
        cost_min=("total_cost", "min"),
        cost_max=("total_cost", "max"),
        runtime_mean=("runtime_seconds", "mean"),
        runtime_std=("runtime_seconds", lambda s: s.std(ddof=1)),
        n_seeds=("seed", "nunique"),
    )
    return grouped.sort_values(["instance", "k", "algorithm"]).reset_index(drop=True)


def _paired_costs(runs: pd.DataFrame, instance: str, k: int) -> dict[str, np.ndarray]:
    subset = runs[(runs["instance"] == instance) & (runs["k"] == k)]
    pivot = subset.pivot(index="seed", columns="algorithm", values="total_cost")
    missing = set(ALGORITHMS) - set(pivot.columns)
    if missing:
        raise ValueError(f"algoritmos ausentes em {instance}/K={k}: {sorted(missing)}")
    if pivot[list(ALGORITHMS)].isna().any().any():
        raise ValueError(f"seeds desalinhadas entre algoritmos em {instance}/K={k}")
    return {algorithm: pivot[algorithm].to_numpy() for algorithm in ALGORITHMS}


def rank_biserial(differences: np.ndarray) -> float:
    """Correlação rank-biserial pareada (Kerby, 2014): soma dos postos com
    sinal, não contagem de sinais. Ranqueia o valor absoluto das diferenças
    (com postos médios em caso de empate, via `scipy.stats.rankdata`), soma
    os postos das diferenças positivas e negativas separadamente, e devolve
    a diferença normalizada pela soma total dos postos.
    """
    nonzero = differences[differences != 0]
    if nonzero.size == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero))
    positive_rank_sum = ranks[nonzero > 0].sum()
    negative_rank_sum = ranks[nonzero < 0].sum()
    return float((positive_rank_sum - negative_rank_sum) / (positive_rank_sum + negative_rank_sum))


def _holm_correction(p_values: list[float]) -> list[float]:
    order = np.argsort(p_values)
    m = len(p_values)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, index in enumerate(order):
        value = min((m - rank) * p_values[index], 1.0)
        running_max = max(running_max, value)
        adjusted[index] = running_max
    return adjusted.tolist()


_PAIRS = (("pso", "tabu"), ("pso", "aco"), ("tabu", "aco"))


def friedman_and_pairs(runs: pd.DataFrame, *, alpha: float = 0.05) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for instance in sorted(runs["instance"].unique()):
        for k in sorted(runs.loc[runs["instance"] == instance, "k"].unique()):
            costs = _paired_costs(runs, instance, int(k))
            statistic, p_value = stats.friedmanchisquare(
                *(costs[a] for a in ALGORITHMS)
            )
            row: dict[str, Any] = {
                "instance": instance, "k": int(k),
                "friedman_statistic": float(statistic),
                "friedman_p_value": float(p_value),
                "rejects_h0": bool(p_value < alpha),
            }
            if row["rejects_h0"]:
                raw_p = []
                pair_statistics = []
                for a, b in _PAIRS:
                    statistic_pair, p_pair = stats.wilcoxon(costs[a], costs[b])
                    pair_statistics.append((a, b, statistic_pair))
                    raw_p.append(float(p_pair))
                holm_p = _holm_correction(raw_p)
                for (a, b, statistic_pair), p_corrected, p_raw in zip(
                    pair_statistics, holm_p, raw_p
                ):
                    effect = rank_biserial(costs[a] - costs[b])
                    row[f"wilcoxon_{a}_vs_{b}_statistic"] = float(statistic_pair)
                    row[f"wilcoxon_{a}_vs_{b}_p_value"] = p_raw
                    row[f"wilcoxon_{a}_vs_{b}_p_holm"] = p_corrected
                    row[f"wilcoxon_{a}_vs_{b}_rank_biserial"] = effect
            rows.append(row)
    return pd.DataFrame(rows)
