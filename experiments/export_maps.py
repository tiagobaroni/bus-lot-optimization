"""Exportação cartográfica dos agrupamentos (B15)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
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

UNIVERSE_SIZE = 150
UNIVERSE = f"artesp_rmsp_{UNIVERSE_SIZE}"
DESCRIPTIVE_COLUMNS = [
    "unit_id", "codigo_linha", "sentido", "nome_legivel",
    "passengers_day", "pu_km_day", "route_length_km",
]
NESTING_LABELS = {20: "20_60_150", 60: "60_150", 150: "so_150"}

METRIC_CRS = "EPSG:31983"
GEOGRAPHIC_CRS = "EPSG:4326"
DEGENERATE_BUFFER_METERS = 50.0


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


def column_name(instance: str, algorithm: str, k: int) -> str:
    """Nome da coluna de lote de uma combinação instância×algoritmo×K."""

    size = instance.rsplit("_", 1)[-1]
    return f"lot_i{size}_{algorithm}_k{k}"


def instance_paths(instances_dir: Path, size: int) -> dict[str, Path]:
    """Caminhos do `.gpkg` e do `.json` de uma instância, pelo seu tamanho."""

    return {"gpkg": instances_dir / f"artesp_rmsp_{size}.gpkg",
            "json": instances_dir / f"artesp_rmsp_{size}.json"}


def read_unit_ids(instances_dir: Path) -> dict[int, list[str]]:
    """Lê `unit_ids` das três instâncias, recusando arquivo ausente."""

    unit_ids: dict[int, list[str]] = {}
    for size in INSTANCE_SIZES:
        paths = instance_paths(instances_dir, size)
        for path in paths.values():
            if not path.exists():
                raise ConfigurationError(f"instância ausente: {path}")
        unit_ids[size] = list(
            json.loads(paths["json"].read_text(encoding="utf-8"))["unit_ids"]
        )
    return unit_ids


def build_itinerarios(instances_dir: Path, aligned: pd.DataFrame) -> gpd.GeoDataFrame:
    """Monta o universo de itinerários com o aninhamento e as colunas de lote."""

    unit_ids = read_unit_ids(instances_dir)
    frame = gpd.read_file(instances_dir / f"{UNIVERSE}.gpkg", layer="itinerarios")
    missing = set(unit_ids[UNIVERSE_SIZE]) - set(frame["unit_id"])
    unknown = set(frame["unit_id"]) - set(unit_ids[UNIVERSE_SIZE])
    if missing or unknown:
        raise ConfigurationError(
            f"itinerários divergem de unit_ids; faltando {sorted(missing)}, "
            f"sobrando {sorted(unknown)}"
        )
    frame = frame[[*DESCRIPTIVE_COLUMNS, "geometry"]].copy()

    in_20 = frame["unit_id"].isin(unit_ids[20])
    in_60 = frame["unit_id"].isin(unit_ids[60])
    frame["in_20"] = in_20
    frame["in_60"] = in_60
    frame["aninhamento"] = np.where(
        in_20, NESTING_LABELS[20],
        np.where(in_60, NESTING_LABELS[60], NESTING_LABELS[150]),
    )

    for row in aligned.itertuples():
        column = column_name(row.instance, row.algorithm, int(row.k))
        if column in frame.columns:
            raise ConfigurationError(f"coluna de lote duplicada: {column}")
        size_text = row.instance.rsplit("_", 1)[-1]
        size = int(size_text) if size_text.isdigit() else None
        if size not in unit_ids:
            raise ConfigurationError(
                f"instância desconhecida em aligned: {row.instance}"
            )
        solution_aligned = list(row.solution_aligned)
        if len(solution_aligned) != len(unit_ids[size]):
            raise ConfigurationError(
                f"solução alinhada de {row.instance} tem {len(solution_aligned)} "
                f"unidades, e não {len(unit_ids[size])}"
            )
        mapping = dict(zip(unit_ids[size], solution_aligned))
        frame[column] = frame["unit_id"].map(mapping).astype("Int64")
    return frame


def build_envoltorias(
    itinerarios: gpd.GeoDataFrame,
    aligned: pd.DataFrame,
    unit_ids: dict[int, list[str]],
) -> gpd.GeoDataFrame:
    """Casco convexo dos itinerários de cada lote, calculado em CRS métrico."""

    metric = itinerarios.to_crs(METRIC_CRS).set_index("unit_id")
    records = []
    for row in aligned.itertuples():
        size = int(row.instance.rsplit("_", 1)[-1])
        labels = pd.Series(row.solution_aligned, index=unit_ids[size])
        for lot, members in labels.groupby(labels):
            geometries = metric.loc[list(members.index), "geometry"]
            hull = geometries.union_all().convex_hull
            degenerate = hull.geom_type != "Polygon"
            if degenerate:
                hull = hull.buffer(DEGENERATE_BUFFER_METERS)
            records.append({
                "instance": row.instance, "algorithm": row.algorithm,
                "k": int(row.k), "lot": int(lot), "seed": int(row.seed),
                "total_cost": float(row.total_cost),
                "scenario_id": row.scenario_id, "n_units": int(len(members)),
                "area_km2": float(hull.area / 1e6), "degenerado": bool(degenerate),
                "geometry": hull,
            })
    frame = gpd.GeoDataFrame(records, geometry="geometry", crs=METRIC_CRS)
    return frame.to_crs(GEOGRAPHIC_CRS)
