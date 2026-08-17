"""Carregamento estrito das instâncias minúscula e ARTESP."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from metaheuristica.errors import InstanceDataError
from metaheuristica.problem import ProblemInstance


METRIC_COLUMNS = ("s_territorial", "t_terminal", "i_integration", "o_market")
SUPPORTED_ARTESP_SIZES = (20, 60, 150)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InstanceDataError(f"arquivo não encontrado: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise InstanceDataError(f"JSON inválido em {path}: {error}") from error
    if not isinstance(data, dict):
        raise InstanceDataError(f"{path}: raiz JSON deve ser um objeto")
    return data


def _unit_ids(value: Any, *, source: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise InstanceDataError(f"{source}: unit_ids deve ser uma lista não vazia")
    unit_ids = tuple(value)
    if any(not isinstance(unit_id, str) or not unit_id for unit_id in unit_ids):
        raise InstanceDataError(f"{source}: unit_ids deve conter textos não vazios")
    if len(set(unit_ids)) != len(unit_ids):
        raise InstanceDataError(f"{source}: unit_ids contém duplicatas")
    return unit_ids


def _dense_metrics(
    unit_ids: tuple[str, ...], pairs: Iterable[Mapping[str, Any]], *, source: Path
) -> dict[str, np.ndarray]:
    index = {unit_id: position for position, unit_id in enumerate(unit_ids)}
    matrices = {
        column: np.zeros((len(unit_ids), len(unit_ids)), dtype=np.float64)
        for column in METRIC_COLUMNS
    }
    seen: set[tuple[str, str]] = set()
    for row_number, pair in enumerate(pairs, start=1):
        try:
            unit_a = pair["unit_id_a"]
            unit_b = pair["unit_id_b"]
        except KeyError as error:
            raise InstanceDataError(
                f"{source}: par {row_number} não contém {error.args[0]}"
            ) from error
        if not isinstance(unit_a, str) or not isinstance(unit_b, str):
            raise InstanceDataError(f"{source}: par {row_number} possui ID não textual")
        if unit_a not in index or unit_b not in index:
            unknown = sorted({unit_a, unit_b} - set(index))
            raise InstanceDataError(f"{source}: par com IDs desconhecidos: {unknown!r}")
        if unit_a == unit_b:
            raise InstanceDataError(f"{source}: autorrelação não permitida para {unit_a}")
        key = tuple(sorted((unit_a, unit_b)))
        if key in seen:
            raise InstanceDataError(f"{source}: par duplicado: {key!r}")
        seen.add(key)
        i, j = index[unit_a], index[unit_b]
        for column in METRIC_COLUMNS:
            if column not in pair:
                raise InstanceDataError(f"{source}: par {key!r} sem a métrica {column}")
            try:
                value = float(pair[column])
            except (TypeError, ValueError) as error:
                raise InstanceDataError(
                    f"{source}: {column} inválida no par {key!r}"
                ) from error
            if not np.isfinite(value) or value < 0.0 or value > 1.0:
                raise InstanceDataError(
                    f"{source}: {column} fora de [0, 1] no par {key!r}: {value}"
                )
            matrices[column][i, j] = matrices[column][j, i] = value
    return matrices


def load_tiny_instance(path: str | Path) -> ProblemInstance:
    source = Path(path)
    data = _read_json(source)
    units = data.get("units")
    if not isinstance(units, list) or not units:
        raise InstanceDataError(f"{source}: units deve ser uma lista não vazia")
    try:
        unit_ids = _unit_ids([unit["unit_id"] for unit in units], source=source)
        demand = [unit["passengers_day"] for unit in units]
        production = [unit["pu_km_day"] for unit in units]
    except (KeyError, TypeError) as error:
        raise InstanceDataError(f"{source}: unidade sem campo obrigatório") from error
    pairs = data.get("pair_metrics")
    if not isinstance(pairs, list):
        raise InstanceDataError(f"{source}: pair_metrics deve ser uma lista")
    matrices = _dense_metrics(unit_ids, pairs, source=source)
    metadata = {unit["unit_id"]: dict(unit) for unit in units}
    return ProblemInstance(
        name=str(data.get("name", source.stem)),
        unit_ids=unit_ids,
        demand=demand,
        production=production,
        metadata=metadata,
        **matrices,
    )


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def load_artesp_instance(instances_dir: str | Path, size: int) -> ProblemInstance:
    if isinstance(size, bool) or size not in SUPPORTED_ARTESP_SIZES:
        raise InstanceDataError(
            f"tamanho ARTESP não suportado: {size}; use {SUPPORTED_ARTESP_SIZES}"
        )
    directory = Path(instances_dir)
    definition_path = directory / f"artesp_rmsp_{size}.json"
    definition = _read_json(definition_path)
    unit_ids = _unit_ids(definition.get("unit_ids"), source=definition_path)
    if definition.get("n_units") != size or len(unit_ids) != size:
        raise InstanceDataError(
            f"{definition_path}: quantidade declarada ou carregada difere de {size}"
        )

    units_path = directory / "artesp_rmsp_150_units.parquet"
    pairs_path = directory / "artesp_rmsp_150_pair_metrics.parquet"
    try:
        units = pd.read_parquet(units_path)
        pairs = pd.read_parquet(pairs_path)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise InstanceDataError(f"falha ao ler dados Parquet em {directory}: {error}") from error

    required_unit_columns = {"unit_id", "passengers_day", "pu_km_day"}
    missing_columns = required_unit_columns - set(units.columns)
    if missing_columns:
        raise InstanceDataError(f"{units_path}: colunas ausentes: {sorted(missing_columns)!r}")
    if units["unit_id"].duplicated().any():
        duplicated = sorted(units.loc[units["unit_id"].duplicated(False), "unit_id"].unique())
        raise InstanceDataError(f"{units_path}: IDs duplicados: {duplicated!r}")
    indexed = units.set_index("unit_id", drop=False)
    missing_ids = [unit_id for unit_id in unit_ids if unit_id not in indexed.index]
    if missing_ids:
        raise InstanceDataError(f"{units_path}: IDs ausentes: {missing_ids!r}")
    selected = indexed.loc[list(unit_ids)].reset_index(drop=True)

    required_pair_columns = {"unit_id_a", "unit_id_b", *METRIC_COLUMNS}
    missing_pair_columns = required_pair_columns - set(pairs.columns)
    if missing_pair_columns:
        raise InstanceDataError(
            f"{pairs_path}: colunas ausentes: {sorted(missing_pair_columns)!r}"
        )
    selected_set = set(unit_ids)
    filtered_pairs = pairs[
        pairs["unit_id_a"].isin(selected_set) & pairs["unit_id_b"].isin(selected_set)
    ]
    matrices = _dense_metrics(unit_ids, _records(filtered_pairs), source=pairs_path)
    metadata = {
        record["unit_id"]: record for record in _records(selected)
    }
    return ProblemInstance(
        name=str(definition.get("name", definition_path.stem)),
        unit_ids=unit_ids,
        demand=selected["passengers_day"].to_numpy(dtype=np.float64),
        production=selected["pu_km_day"].to_numpy(dtype=np.float64),
        metadata=metadata,
        **matrices,
    )
