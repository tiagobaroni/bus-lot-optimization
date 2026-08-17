"""Gera as instâncias reais aninhadas usadas nos experimentos.

A seleção combina cobertura espacial obrigatória com aproximação incremental
das distribuições do universo em território, demanda e PU.km.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString


SEED = 20260816
SIZES = (20, 60, 150)
GRID_SIZE = 4
GPKG_TIMESTAMP = "2026-08-16T17:12:56.754Z"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_geopackage_timestamp(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE gpkg_contents SET last_change = ?",
            (GPKG_TIMESTAMP,),
        )
        connection.commit()
        connection.execute("VACUUM")


def _prepare_geopackage_output(path: Path) -> None:
    allowed_names = {"tiny_manual.gpkg", *(f"artesp_rmsp_{size}.gpkg" for size in SIZES)}
    if path.suffix != ".gpkg" or path.name not in allowed_names:
        raise ValueError(f"Destino GeoPackage inesperado: {path}")
    if path.exists():
        path.unlink()


def _centroids(stops_path: Path) -> pd.DataFrame:
    stops = pd.read_parquet(stops_path, columns=["unit_id", "lat", "lon"])
    return (
        stops.groupby("unit_id", as_index=False, sort=True)
        .agg(centroid_lat=("lat", "mean"), centroid_lon=("lon", "mean"))
    )


def _quartile_grid(values: pd.Series) -> tuple[pd.Series, list[float]]:
    boundaries = [float(value) for value in values.quantile([0.25, 0.5, 0.75])]
    bins = np.searchsorted(np.asarray(boundaries), values.to_numpy(), side="right")
    return pd.Series(bins, index=values.index, dtype="int64"), boundaries


def _choose_candidate(
    frame: pd.DataFrame,
    selected: list[int],
    candidates: Iterable[int],
    random_priority: np.ndarray,
) -> int:
    candidate_array = np.fromiter(candidates, dtype=int)
    scores = np.zeros(len(frame), dtype=float)
    size = len(selected) + 1

    for column, weight in (
        ("spatial_cell", 2.0),
        ("estrato_demanda_quartil", 1.0),
        ("estrato_pu_km_quartil", 1.0),
    ):
        categories = sorted(frame[column].unique())
        category_index = {category: index for index, category in enumerate(categories)}
        codes = frame[column].map(category_index).to_numpy(dtype=int)
        population_counts = np.bincount(codes, minlength=len(categories))
        selected_counts = np.bincount(codes[selected], minlength=len(categories))
        expected = size * population_counts / len(frame)
        denominators = np.maximum(expected, 1.0)
        base_terms = (selected_counts - expected) ** 2 / denominators
        category_scores = np.full(len(categories), base_terms.sum())
        category_scores -= base_terms
        category_scores += (selected_counts + 1 - expected) ** 2 / denominators
        scores += weight * category_scores[codes]

    return min(
        candidate_array,
        key=lambda candidate: (
            float(scores[candidate]),
            int(random_priority[candidate]),
            str(frame.at[candidate, "unit_id"]),
        ),
    )


def _select_nested(frame: pd.DataFrame, seed: int) -> dict[int, list[int]]:
    rng = np.random.default_rng(seed)
    random_priority = np.empty(len(frame), dtype=int)
    random_priority[rng.permutation(len(frame))] = np.arange(len(frame))
    selected: list[int] = []

    # A menor instância cobre toda a grade antes do preenchimento proporcional.
    cells = sorted(frame["spatial_cell"].unique())
    for cell in rng.permutation(cells):
        candidates = frame.index[(frame["spatial_cell"] == cell) & ~frame.index.isin(selected)]
        selected.append(_choose_candidate(frame, selected, candidates, random_priority))

    result: dict[int, list[int]] = {}
    for target in SIZES:
        while len(selected) < target:
            candidates = frame.index[~frame.index.isin(selected)]
            selected.append(_choose_candidate(frame, selected, candidates, random_priority))
        result[target] = selected.copy()
    return result


def _counts(frame: pd.DataFrame, indices: list[int], column: str) -> dict[str, int]:
    counts = frame.loc[indices, column].value_counts(dropna=False).sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def _summary(frame: pd.DataFrame, indices: list[int]) -> dict[str, Any]:
    sample = frame.loc[indices]
    return {
        "n_unidades": len(sample),
        "n_celulas_espaciais": int(sample["spatial_cell"].nunique()),
        "n_municipios_principais": int(sample["estrato_municipio_principal"].nunique()),
        "limites_centroides": {
            "lat_min": float(sample["centroid_lat"].min()),
            "lat_max": float(sample["centroid_lat"].max()),
            "lon_min": float(sample["centroid_lon"].min()),
            "lon_max": float(sample["centroid_lon"].max()),
        },
        "celulas_espaciais": _counts(frame, indices, "spatial_cell"),
        "quartis_demanda": _counts(frame, indices, "estrato_demanda_quartil"),
        "quartis_pu_km": _counts(frame, indices, "estrato_pu_km_quartil"),
        "municipios_principais": _counts(frame, indices, "estrato_municipio_principal"),
    }


def _filter_pairs(frame: pd.DataFrame, unit_ids: set[str]) -> pd.DataFrame:
    return frame[
        frame["unit_id_a"].isin(unit_ids) & frame["unit_id_b"].isin(unit_ids)
    ].copy()


def _export_compact_data(
    source_dir: Path,
    output_dir: Path,
    units: pd.DataFrame,
    selected_ids: list[str],
) -> dict[str, Any]:
    selected_set = set(selected_ids)
    units_export = (
        units[units["unit_id"].isin(selected_set)]
        .sort_values("unit_id")
        .reset_index(drop=True)
    )
    units_output = output_dir / "artesp_rmsp_150_units.parquet"
    units_export.to_parquet(units_output, index=False)

    s = _filter_pairs(pd.read_parquet(source_dir / "s_overlap_long.parquet"), selected_set)
    s["s_territorial"] = s["intersection_area_m2"] / s[
        ["area_i_m2", "area_j_m2"]
    ].min(axis=1)
    s["s_territorial"] = s["s_territorial"].clip(0.0, 1.0)
    s = s[["unit_id_a", "unit_id_b", "s_territorial"]]

    links = _filter_pairs(pd.read_parquet(source_dir / "functional_links.parquet"), selected_set)
    links["t_terminal"] = (links["shared_terminal_count"] > 0).astype(float)
    links["i_integration"] = (
        (links["shared_terminal_count"] > 0)
        | (links["shared_stop_count"] > 0)
        | (links["nearby_stop_pair_count"] > 0)
    ).astype(float)
    links = links[["unit_id_a", "unit_id_b", "t_terminal", "i_integration"]]

    o = _filter_pairs(pd.read_parquet(source_dir / "o_market_long.parquet"), selected_set)
    o = o[["unit_id_a", "unit_id_b", "o_jaccard"]].rename(
        columns={"o_jaccard": "o_market"}
    )

    pair_metrics = s.merge(links, on=["unit_id_a", "unit_id_b"], how="outer").merge(
        o, on=["unit_id_a", "unit_id_b"], how="outer"
    )
    metric_columns = ["s_territorial", "t_terminal", "i_integration", "o_market"]
    pair_metrics[metric_columns] = pair_metrics[metric_columns].fillna(0.0)
    pair_metrics = pair_metrics.sort_values(["unit_id_a", "unit_id_b"]).reset_index(drop=True)
    pairs_output = output_dir / "artesp_rmsp_150_pair_metrics.parquet"
    pair_metrics.to_parquet(pairs_output, index=False)

    return {
        "units": {
            "file": units_output.name,
            "sha256": _sha256(units_output),
            "n_rows": len(units_export),
            "description": "Atributos das 150 unidades da maior instância.",
        },
        "pair_metrics": {
            "file": pairs_output.name,
            "sha256": _sha256(pairs_output),
            "n_rows": len(pair_metrics),
            "description": (
                "Tabela esparsa para a instância de 150; pares ausentes têm métricas zero."
            ),
            "columns": {
                "s_territorial": "interseção dos buffers dividida pela menor área",
                "t_terminal": "1 quando existe terminal compartilhado",
                "i_integration": (
                    "1 para terminal compartilhado, parada compartilhada ou paradas a até 400 m"
                ),
                "o_market": "Jaccard ponderado dos mercados O-D potenciais",
            },
        },
    }


def _export_real_geopackage(
    source_dir: Path,
    output_path: Path,
    units: pd.DataFrame,
    unit_ids: list[str],
) -> None:
    _prepare_geopackage_output(output_path)
    selected = set(unit_ids)
    attributes = [
        "unit_id",
        "codigo_linha",
        "sentido",
        "nome_legivel",
        "passengers_day",
        "pu_km_day",
        "route_length_km",
        "estrato_municipio_principal",
        "estrato_demanda_quartil",
        "estrato_pu_km_quartil",
    ]
    routes = gpd.read_parquet(source_dir / "shapes.geoparquet")
    routes = routes[routes["unit_id"].isin(selected)][["unit_id", "geometry"]]
    routes = routes.merge(units[attributes], on="unit_id", how="left", validate="one_to_one")
    routes = routes.sort_values("unit_id")

    stops = pd.read_parquet(source_dir / "stops.parquet")
    stops = stops[stops["unit_id"].isin(selected)].copy()
    stops = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["lon"], stops["lat"]),
        crs="EPSG:4326",
    ).sort_values(["unit_id", "stop_sequence"])

    unit_terminals = pd.read_parquet(source_dir / "unit_terminals.parquet")
    terminal_ids = unit_terminals.loc[
        unit_terminals["unit_id"].isin(selected), "id_terminal"
    ].unique()
    terminals = gpd.read_parquet(source_dir / "terminals.geoparquet")
    terminals = terminals[terminals["id_terminal"].isin(terminal_ids)].sort_values(
        "id_terminal"
    )

    routes.to_file(output_path, layer="itinerarios", driver="GPKG", engine="pyogrio")
    stops.to_file(output_path, layer="paradas", driver="GPKG", engine="pyogrio", mode="a")
    terminals.to_file(
        output_path, layer="terminais", driver="GPKG", engine="pyogrio", mode="a"
    )
    _normalize_geopackage_timestamp(output_path)


def _export_tiny_instance(output_dir: Path) -> dict[str, Any]:
    units = [
        {"unit_id": "A", "passengers_day": 10.0, "pu_km_day": 100.0},
        {"unit_id": "B", "passengers_day": 10.0, "pu_km_day": 100.0},
        {"unit_id": "C", "passengers_day": 10.0, "pu_km_day": 100.0},
        {"unit_id": "D", "passengers_day": 10.0, "pu_km_day": 100.0},
    ]
    pairs = [
        {
            "unit_id_a": "A",
            "unit_id_b": "B",
            "s_territorial": 1.0,
            "t_terminal": 1.0,
            "i_integration": 1.0,
            "o_market": 1.0,
        },
        {
            "unit_id_a": "C",
            "unit_id_b": "D",
            "s_territorial": 1.0,
            "t_terminal": 1.0,
            "i_integration": 1.0,
            "o_market": 1.0,
        },
    ]
    instance = {
        "schema_version": "1.0.0",
        "name": "tiny_manual",
        "description": (
            "Instância sintética verificável manualmente: A-B e C-D formam duas duplas."
        ),
        "k": 2,
        "units": units,
        "pair_metrics": pairs,
        "absent_pair_rule": "pares ausentes têm S, T, I e O iguais a zero",
        "expected_optimum": {
            "canonical_solution": [0, 0, 1, 1],
            "unit_order": ["A", "B", "C", "D"],
            "cost": 0.0,
            "justification": (
                "Os lotes têm demanda e PU.km iguais e nenhuma relação positiva é cortada."
            ),
        },
    }
    json_path = output_dir / "tiny_manual.json"
    json_path.write_text(json.dumps(instance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    geometries = [
        LineString([(-46.80, -23.60), (-46.70, -23.60)]),
        LineString([(-46.80, -23.605), (-46.70, -23.605)]),
        LineString([(-46.45, -23.45), (-46.35, -23.45)]),
        LineString([(-46.45, -23.455), (-46.35, -23.455)]),
    ]
    routes = gpd.GeoDataFrame(units, geometry=geometries, crs="EPSG:4326")
    stops_rows: list[dict[str, Any]] = []
    for unit, geometry in zip(units, geometries, strict=True):
        for sequence, coordinate in enumerate(geometry.coords):
            stops_rows.append(
                {
                    "unit_id": unit["unit_id"],
                    "stop_sequence": sequence,
                    "geometry": gpd.points_from_xy([coordinate[0]], [coordinate[1]])[0],
                }
            )
    stops = gpd.GeoDataFrame(stops_rows, geometry="geometry", crs="EPSG:4326")
    gpkg_path = output_dir / "tiny_manual.gpkg"
    _prepare_geopackage_output(gpkg_path)
    routes.to_file(gpkg_path, layer="itinerarios", driver="GPKG", engine="pyogrio")
    stops.to_file(gpkg_path, layer="paradas", driver="GPKG", engine="pyogrio", mode="a")
    _normalize_geopackage_timestamp(gpkg_path)

    return {
        "json": {"file": json_path.name, "sha256": _sha256(json_path)},
        "geopackage": {"file": gpkg_path.name, "sha256": _sha256(gpkg_path)},
    }


def generate_instances(source_dir: Path, output_dir: Path, seed: int = SEED) -> None:
    units_path = source_dir / "units.parquet"
    stops_path = source_dir / "stops.parquet"
    units = pd.read_parquet(units_path)
    frame = units.merge(_centroids(stops_path), on="unit_id", how="left", validate="one_to_one")

    required = [
        "passengers_day",
        "pu_km_day",
        "centroid_lat",
        "centroid_lon",
        "estrato_demanda_quartil",
        "estrato_pu_km_quartil",
        "estrato_municipio_principal",
    ]
    eligible_mask = frame[required].notna().all(axis=1)
    excluded = frame.loc[~eligible_mask, ["unit_id", *required]].copy()
    eligible = frame.loc[eligible_mask].sort_values("unit_id").reset_index(drop=True)

    lat_bin, lat_boundaries = _quartile_grid(eligible["centroid_lat"])
    lon_bin, lon_boundaries = _quartile_grid(eligible["centroid_lon"])
    eligible["spatial_cell"] = [
        f"L{lat_value + 1}-O{lon_value + 1}"
        for lat_value, lon_value in zip(lat_bin, lon_bin, strict=True)
    ]

    if eligible["spatial_cell"].nunique() != GRID_SIZE**2:
        raise ValueError("A grade espacial não contém as 16 células esperadas.")

    selections = _select_nested(eligible, seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "seed": seed,
        "source": {
            "units": str(units_path),
            "units_sha256": _sha256(units_path),
            "stops": str(stops_path),
            "stops_sha256": _sha256(stops_path),
        },
        "eligibility": {
            "n_source": int(len(frame)),
            "n_eligible": int(len(eligible)),
            "rule": "campos de demanda, PU.km, centroide e estratificação não nulos",
            "excluded": excluded.replace({np.nan: None}).to_dict(orient="records"),
        },
        "spatial_method": {
            "description": (
                "Grade 4 x 4 formada pelos quartis de latitude e longitude dos "
                "centroides médios das paradas; a instância de 20 cobre todas as células."
            ),
            "latitude_boundaries": lat_boundaries,
            "longitude_boundaries": lon_boundaries,
        },
        "selection_method": (
            "Seleção incremental que minimiza desvios das distribuições do universo em "
            "célula espacial, quartil de demanda e quartil de PU.km; peso territorial 2."
        ),
        "instances": {},
    }

    manifest["tiny_manual"] = _export_tiny_instance(output_dir)

    for size, indices in selections.items():
        unit_ids = eligible.loc[indices, "unit_id"].tolist()
        instance = {
            "schema_version": "1.0.0",
            "name": f"artesp_rmsp_{size}",
            "n_units": size,
            "seed": seed,
            "unit_ids": unit_ids,
        }
        path = output_dir / f"artesp_rmsp_{size}.json"
        path.write_text(json.dumps(instance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        gpkg_path = output_dir / f"artesp_rmsp_{size}.gpkg"
        _export_real_geopackage(source_dir, gpkg_path, units, unit_ids)
        manifest["instances"][str(size)] = {
            "file": path.name,
            "sha256": _sha256(path),
            "geopackage": {
                "file": gpkg_path.name,
                "sha256": _sha256(gpkg_path),
                "layers": ["itinerarios", "paradas", "terminais"],
            },
            "summary": _summary(eligible, indices),
        }

    largest_ids = eligible.loc[selections[max(SIZES)], "unit_id"].tolist()
    manifest["compact_data"] = _export_compact_data(
        source_dir, output_dir, units, largest_ids
    )

    manifest_path = output_dir / "selection_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("_temp/dados_artesp"))
    parser.add_argument("--output", type=Path, default=Path("data/instances"))
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    generate_instances(args.source, args.output, args.seed)


if __name__ == "__main__":
    main()
