"""Estatística descritiva e inferencial do benchmark principal."""

from __future__ import annotations

import pandas as pd

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
