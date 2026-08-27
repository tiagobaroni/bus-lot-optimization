"""Consolidação determinística dos resultados operacionais."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.provenance import capture_provenance, utc_now
from experiments.scenarios import canonical_json, expand_scenarios, file_sha256
from experiments.storage import (
    _fsync_directory, artifact_paths, read_json, validate_document,
)


def _json_text(value: Any) -> str:
    return canonical_json(value).decode("utf-8")


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        frame.to_parquet(temporary, index=False)
        # O descritor é aberto para escrita porque sincronizar sobre descritor
        # somente leitura funciona no Linux mas não é contrato garantido.
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Sem sincronizar o diretório, a entrada trocada pode não sobreviver a
        # uma queda de energia mesmo com o conteúdo já em disco, que é a mesma
        # garantia que `atomic_write_json` já dava e esta escrita não dava.
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def documents_to_frames(
    documents: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Converte documentos já validados em tabelas determinísticas."""
    run_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    for document in documents:
        scenario = document["scenario"]
        result = document["result"]
        evaluation = result["evaluation"]
        row = {
            "scenario_id": document["scenario_id"],
            "purpose": scenario["purpose"],
            "algorithm": scenario["algorithm"],
            "instance": scenario["instance"]["name"],
            "instance_path": scenario["instance"]["path"],
            "instance_sha256": scenario["instance"]["sha256"],
            "k": scenario["k"],
            "seed": scenario["seed"],
            "budget": scenario["budget"],
            "cache_enabled": scenario["cache_enabled"],
            **evaluation,
            "evaluations": result["evaluations"],
            "cache_hits": result["cache_hits"],
            "runtime_seconds": result["runtime_seconds"],
            "termination_reason": result["termination_reason"],
            "parameters_json": _json_text(scenario["parameters"]),
            "weights_json": _json_text(scenario["weights"]),
            "solution_json": _json_text(result["solution"]),
            "diagnostics_json": _json_text(result["diagnostics"]),
            "provenance_json": _json_text(document["provenance"]),
            "started_at": document["started_at"],
            "finished_at": document["finished_at"],
            "official": document["official"],
            "content_sha256": document["content_sha256"],
            "scenario_json": _json_text(scenario),
            "result_json": _json_text(result),
        }
        run_rows.append(row)
        for checkpoint in result["checkpoints"]:
            checkpoint_rows.append({
                "scenario_id": document["scenario_id"],
                "algorithm": scenario["algorithm"],
                "instance": scenario["instance"]["name"],
                "k": scenario["k"],
                "seed": scenario["seed"],
                "parameters_json": _json_text(scenario["parameters"]),
                "index": checkpoint["index"],
                "evaluations": checkpoint["evaluations"],
                **checkpoint["evaluation"],
            })
    run_rows.sort(key=lambda row: (
        row["algorithm"], row["instance"], row["k"], row["seed"],
        row["parameters_json"], row["scenario_id"],
    ))
    checkpoint_rows.sort(key=lambda row: (
        row["algorithm"], row["instance"], row["k"], row["seed"],
        row["parameters_json"], row["scenario_id"], row["index"],
    ))
    return pd.DataFrame(run_rows), pd.DataFrame(checkpoint_rows)


def consolidate_campaign(
    config: CampaignConfig,
    *,
    allow_incomplete: bool = False,
    allow_dirty: bool = False,
    allow_unversioned: bool = False,
) -> dict[str, Any]:
    from experiments.storage import atomic_write_json

    scenarios = expand_scenarios(config)
    output_root = config.repository_root / config.output_root
    expected_ids = {scenario.scenario_id for scenario in scenarios}
    raw_directory = output_root / "raw" / config.purpose
    if raw_directory.exists():
        expected_names = {scenario.filename for scenario in scenarios}
        unexpected = sorted(
            path.name for path in raw_directory.glob("*.json")
            if path.name not in expected_names
        )
        if unexpected:
            raise ConfigurationError(f"resultados inesperados: {unexpected}")

    documents: list[dict[str, Any]] = []
    missing: list[str] = []
    failures = 0
    for scenario in scenarios:
        paths = artifact_paths(output_root, config.purpose, scenario)
        if paths.failure.exists():
            failures += 1
        if not paths.result.exists():
            missing.append(scenario.scenario_id)
            continue
        documents.append(validate_document(read_json(paths.result), scenario))
    if missing and not allow_incomplete:
        raise ConfigurationError(
            f"campanha incompleta: {len(missing)} de {len(scenarios)} resultados ausentes"
        )
    included_ids = {document["scenario_id"] for document in documents}
    if len(included_ids) != len(documents) or not included_ids <= expected_ids:
        raise ConfigurationError("IDs duplicados ou inesperados na consolidação")

    runs, checkpoints = documents_to_frames(documents)
    tables = output_root / "tables"
    runs_path = tables / f"{config.purpose}_runs.parquet"
    checkpoints_path = tables / f"{config.purpose}_checkpoints.parquet"
    manifest_path = tables / f"{config.purpose}_manifest.json"
    provenance = capture_provenance(
        config.repository_root,
        allow_dirty=allow_dirty,
        allow_unversioned=allow_unversioned,
    )
    _atomic_parquet(runs_path, runs)
    _atomic_parquet(checkpoints_path, checkpoints)
    all_official = all(document["official"] for document in documents)
    complete = not missing
    official = bool(complete and all_official and provenance["official"])
    manifest = {
        "schema_version": 1,
        "campaign": config.name,
        "purpose": config.purpose,
        "config_sha256": file_sha256(config.source_path),
        "expected": len(scenarios),
        "completed": len(documents),
        "failed_records": failures,
        "missing": len(missing),
        "complete": complete,
        "official": official,
        "scenario_ids_sha256": sha256(canonical_json(sorted(included_ids))).hexdigest(),
        "runs": {"path": str(runs_path.relative_to(config.repository_root)), "sha256": file_sha256(runs_path)},
        "checkpoints": {"path": str(checkpoints_path.relative_to(config.repository_root)), "sha256": file_sha256(checkpoints_path)},
        "consolidated_at": utc_now(),
        "provenance": provenance,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest
