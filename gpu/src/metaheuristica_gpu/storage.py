"""Persistência atômica e validação mínima dos resultados GPU."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from metaheuristica_gpu.scenarios import GpuScenario, canonical_json


class GpuStorageError(RuntimeError):
    pass


def atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json(document)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GpuStorageError(f"JSON GPU inválido: {path}") from error
    if not isinstance(value, dict):
        raise GpuStorageError("documento GPU deve ser objeto")
    return value


def result_path(root: Path, scenario: GpuScenario) -> Path:
    return root / "raw" / scenario.filename


def validate_result(document: dict[str, Any], scenario: GpuScenario) -> None:
    if document.get("scenario_id") != scenario.scenario_id or document.get("scenario") != scenario.payload:
        raise GpuStorageError("resultado GPU incompatível com cenário")
    result = document.get("result")
    if not isinstance(result, dict) or result.get("evaluations") != scenario.payload["budget"]:
        raise GpuStorageError("resultado GPU incompleto")


def is_complete(root: Path, scenario: GpuScenario) -> bool:
    path = result_path(root, scenario)
    if not path.exists():
        return False
    validate_result(read_json(path), scenario)
    return True
