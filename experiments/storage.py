"""Persistência atômica e classificação dos artefatos operacionais."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import traceback
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.provenance import utc_now
from experiments.scenarios import Scenario, canonical_json


class ScenarioState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ArtifactPaths:
    result: Path
    failure: Path


def artifact_paths(root: Path, purpose: str, scenario: Scenario) -> ArtifactPaths:
    return ArtifactPaths(
        root / "raw" / purpose / scenario.filename,
        root / "failures" / purpose / scenario.filename,
    )


def _with_content_hash(document: dict[str, Any]) -> dict[str, Any]:
    content = dict(document)
    content.pop("content_sha256", None)
    content["content_sha256"] = sha256(canonical_json(content)).hexdigest()
    return content


def validate_document(document: Any, scenario: Scenario) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ConfigurationError("resultado armazenado deve ser objeto JSON")
    expected = document.get("content_sha256")
    if not isinstance(expected, str):
        raise ConfigurationError("resultado sem content_sha256")
    if _with_content_hash(document)["content_sha256"] != expected:
        raise ConfigurationError("hash interno do resultado divergente")
    if document.get("schema_version") != 1:
        raise ConfigurationError("versão de resultado incompatível")
    if document.get("scenario_id") != scenario.scenario_id:
        raise ConfigurationError("ID do resultado diverge do cenário")
    if document.get("scenario") != scenario.payload:
        raise ConfigurationError("payload do resultado diverge do cenário")
    result = document.get("result")
    if not isinstance(result, dict):
        raise ConfigurationError("resultado comum ausente")
    checks = {
        "algorithm": scenario.payload["algorithm"],
        "k": scenario.payload["k"],
        "seed": scenario.payload["seed"],
        "budget": scenario.payload["budget"],
        "evaluations": scenario.payload["budget"],
        "termination_reason": "budget_exhausted",
    }
    for field, value in checks.items():
        if result.get(field) != value:
            raise ConfigurationError(f"resultado incompatível no campo {field}")
    if result.get("weights") != scenario.payload["weights"]:
        raise ConfigurationError("pesos do resultado divergem do cenário")
    checkpoints = result.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != 100:
        raise ConfigurationError("resultado deve conter 100 checkpoints")
    if not isinstance(document.get("provenance"), dict):
        raise ConfigurationError("proveniência ausente")
    frozen_hash = scenario.payload.get("frozen_parameters_sha256")
    if frozen_hash is not None and document["provenance"].get(
        "frozen_parameters_sha256"
    ) != frozen_hash:
        raise ConfigurationError("hash dos parâmetros congelados divergente")
    canonical_json(document)
    return document


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"JSON inválido em {path}") from error


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        read_json(temporary)
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_result_document(
    scenario: Scenario,
    result: dict[str, Any],
    provenance: dict[str, Any],
    *,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    document = _with_content_hash({
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "scenario": scenario.payload,
        "result": result,
        "provenance": provenance,
        "official": bool(provenance.get("official")),
        "started_at": started_at,
        "finished_at": finished_at,
    })
    return validate_document(document, scenario)


def classify(paths: ArtifactPaths, scenario: Scenario) -> ScenarioState:
    if paths.result.exists():
        validate_document(read_json(paths.result), scenario)
        return ScenarioState.COMPLETED
    return ScenarioState.FAILED if paths.failure.exists() else ScenarioState.PENDING


def record_failure(paths: ArtifactPaths, scenario: Scenario, error: BaseException) -> None:
    attempts: list[dict[str, Any]] = []
    if paths.failure.exists():
        existing = read_json(paths.failure)
        if existing.get("scenario_id") != scenario.scenario_id:
            raise ConfigurationError("registro de falha incompatível")
        attempts = list(existing.get("attempts", []))
    attempts.append({
        "at": utc_now(),
        "exception_type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    })
    atomic_write_json(paths.failure, {
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "scenario": scenario.payload,
        "attempts": attempts,
    })
