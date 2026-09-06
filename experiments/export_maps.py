"""Exportação cartográfica dos agrupamentos (B15)."""

from __future__ import annotations

import json

import pandas as pd

from metaheuristica.canonical import validate_solution
from metaheuristica.errors import ConfigurationError, SolutionValidationError

INSTANCE_SIZES = (20, 60, 150)
ALGORITHMS = ("tabu", "aco", "pso")
K_VALUES = (3, 4, 5, 6, 7, 8)
EXPECTED_RUNS = 1620
EXPECTED_SEEDS = 30
COMBINATIONS = 54
GROUP_KEYS = ["instance", "algorithm", "k"]


def select_best_runs(
    runs: pd.DataFrame,
    *,
    unit_counts: dict[str, int],
    expected_runs: int = EXPECTED_RUNS,
    expected_seeds: int = EXPECTED_SEEDS,
    combinations: int = COMBINATIONS,
) -> pd.DataFrame:
    """Escolhe, por combinação, a execução oficial de menor custo."""

    official = runs[runs["official"].astype(bool)]
    if len(official) != expected_runs:
        raise ConfigurationError(
            f"o recorte oficial tem {len(official)} execuções, e não {expected_runs}"
        )
    sizes = official.groupby(GROUP_KEYS).size()
    if len(sizes) != combinations:
        raise ConfigurationError(
            f"há {len(sizes)} combinações instância×algoritmo×K, e não {combinations}"
        )
    divergent = sizes[sizes != expected_seeds]
    if not divergent.empty:
        raise ConfigurationError(
            "combinação sem as seeds esperadas: "
            + ", ".join(f"{key}={value}" for key, value in divergent.items())
        )

    ordered = official.sort_values([*GROUP_KEYS, "total_cost", "seed"])
    # `drop_duplicates` preserva a LINHA inteira da vencedora; `groupby().first()`
    # tomaria o primeiro valor não-nulo de cada coluna em separado.
    best = ordered.drop_duplicates(subset=GROUP_KEYS, keep="first").copy()
    best["solution"] = best["solution_json"].map(json.loads)
    _validate_solutions(best, unit_counts=unit_counts)
    return best[[*GROUP_KEYS, "seed", "total_cost", "scenario_id", "solution"]]


def _validate_solutions(selected: pd.DataFrame, *, unit_counts: dict[str, int]) -> None:
    """Recusa solução com comprimento ou número de lotes divergente."""

    for row in selected.itertuples():
        expected_units = unit_counts.get(row.instance)
        if expected_units is None:
            raise ConfigurationError(f"instância desconhecida no parquet: {row.instance}")
        try:
            validate_solution(row.solution, n_units=expected_units, k=int(row.k))
        except SolutionValidationError as error:
            raise ConfigurationError(
                f"solução inválida em {row.scenario_id}: {error}"
            ) from error
