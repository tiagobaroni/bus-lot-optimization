"""Exportação cartográfica dos agrupamentos (B15)."""

from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from metaheuristica.canonical import canonicalize_solution, validate_solution
from metaheuristica.errors import ConfigurationError, SolutionValidationError

INSTANCE_SIZES = (20, 60, 150)
ALGORITHMS = ("tabu", "aco", "pso")
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


def align_to_reference(
    labels: Sequence[int], reference: Sequence[int], *, k: int
) -> np.ndarray:
    """Renomeia `labels` para casar com `reference` por sobreposição máxima."""

    labels_array = np.asarray(labels, dtype=np.int64)
    reference_array = np.asarray(reference, dtype=np.int64)
    contingency = np.zeros((k, k), dtype=np.int64)
    np.add.at(contingency, (labels_array, reference_array), 1)
    rows, columns = linear_sum_assignment(contingency, maximize=True)
    mapping = np.empty(k, dtype=np.int64)
    mapping[rows] = columns
    return mapping[labels_array]


def align_selected(selected: pd.DataFrame) -> pd.DataFrame:
    """Alinha os rótulos dos três métodos dentro de cada par (instância, K)."""

    order = {name: position for position, name in enumerate(ALGORITHMS)}
    frames = []
    for (_, k), group in selected.groupby(["instance", "k"], sort=False):
        ranked = group.assign(_order=group["algorithm"].map(order))
        ranked = ranked.sort_values(["total_cost", "_order"])
        reference_row = ranked.iloc[0]
        n_units = len(reference_row["solution"])
        reference = canonicalize_solution(
            reference_row["solution"], n_units=n_units, k=int(k)
        )
        aligned = [
            [int(value) for value in align_to_reference(row.solution, reference, k=int(k))]
            for row in ranked.itertuples()
        ]
        result = ranked.drop(columns="_order").copy()
        result["solution_aligned"] = aligned
        result["reference_algorithm"] = reference_row["algorithm"]
        frames.append(result)
    return pd.concat(frames, ignore_index=True)
