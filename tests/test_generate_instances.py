from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyogrio

from experiments.generate_instances import SEED, generate_instances


PROJECT_ROOT = Path(__file__).parents[1]
SOURCE_DIR = PROJECT_ROOT / "_temp" / "dados_artesp"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_generated_instances_are_nested_and_spatially_distributed(tmp_path: Path) -> None:
    generate_instances(SOURCE_DIR, tmp_path, SEED)

    instances = {
        size: _read(tmp_path / f"artesp_rmsp_{size}.json") for size in (20, 60, 150)
    }
    ids = {size: instance["unit_ids"] for size, instance in instances.items()}
    manifest = _read(tmp_path / "selection_manifest.json")

    assert all(len(ids[size]) == len(set(ids[size])) == size for size in ids)
    assert set(ids[20]) < set(ids[60]) < set(ids[150])
    assert manifest["eligibility"]["n_source"] == 894
    assert manifest["eligibility"]["n_eligible"] == 883
    assert len(manifest["eligibility"]["excluded"]) == 11
    assert manifest["instances"]["20"]["summary"]["n_celulas_espaciais"] == 16
    assert manifest["instances"]["20"]["summary"]["n_municipios_principais"] > 1

    units = pd.read_parquet(tmp_path / "artesp_rmsp_150_units.parquet")
    pairs = pd.read_parquet(tmp_path / "artesp_rmsp_150_pair_metrics.parquet")
    selected_150 = set(ids[150])
    assert len(units) == units["unit_id"].nunique() == 150
    assert set(units["unit_id"]) == selected_150
    assert set(pairs["unit_id_a"]) <= selected_150
    assert set(pairs["unit_id_b"]) <= selected_150
    for column in ("s_territorial", "t_terminal", "i_integration", "o_market"):
        assert pairs[column].between(0.0, 1.0).all()

    for size in (20, 60, 150):
        gpkg = tmp_path / f"artesp_rmsp_{size}.gpkg"
        layers = set(pyogrio.list_layers(gpkg)[:, 0])
        assert layers == {"itinerarios", "paradas", "terminais"}
        routes = pyogrio.read_dataframe(gpkg, layer="itinerarios")
        stops = pyogrio.read_dataframe(gpkg, layer="paradas")
        terminals = pyogrio.read_dataframe(gpkg, layer="terminais")
        assert len(routes) == size
        assert set(routes["unit_id"]) == set(ids[size])
        assert not stops.duplicated(["unit_id", "stop_sequence"]).any()
        assert terminals["id_terminal"].is_unique


def test_tiny_instance_has_manual_optimum_and_geopackage(tmp_path: Path) -> None:
    generate_instances(SOURCE_DIR, tmp_path, SEED)

    tiny = _read(tmp_path / "tiny_manual.json")
    assert tiny["k"] == 2
    assert tiny["expected_optimum"]["canonical_solution"] == [0, 0, 1, 1]
    assert tiny["expected_optimum"]["cost"] == 0.0
    assert set(pyogrio.list_layers(tmp_path / "tiny_manual.gpkg")[:, 0]) == {
        "itinerarios",
        "paradas",
    }
    assert len(pyogrio.read_dataframe(tmp_path / "tiny_manual.gpkg", layer="paradas")) == 8


def test_generation_is_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_instances(SOURCE_DIR, first, SEED)
    generate_instances(SOURCE_DIR, second, SEED)

    for filename in (
        "artesp_rmsp_20.json",
        "artesp_rmsp_60.json",
        "artesp_rmsp_150.json",
        "artesp_rmsp_150_units.parquet",
        "artesp_rmsp_150_pair_metrics.parquet",
        "selection_manifest.json",
        "tiny_manual.json",
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
