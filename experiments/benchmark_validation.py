"""Barreiras e consolidação progressiva do benchmark principal."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_batches import select_benchmark
from experiments.benchmark_operations import blocked_failures, operational_root
from experiments.config import CampaignConfig
from experiments.consolidation import _atomic_parquet, consolidate_campaign, documents_to_frames
from experiments.pilot_validation import _validate_result
from experiments.provenance import utc_now
from experiments.scenarios import canonical_json, file_sha256
from experiments.storage import artifact_paths, atomic_write_json, read_json, validate_document


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigurationError(message)


def _temporary_files(config: CampaignConfig) -> list[str]:
    root = config.repository_root / config.output_root
    return sorted(
        str(path.relative_to(config.repository_root))
        for directory in (root / "raw" / config.purpose, root / "failures" / config.purpose)
        if directory.exists()
        for path in directory.glob("*.tmp")
    )


def _documents(config: CampaignConfig, batch: int) -> list[dict[str, Any]]:
    selection = select_benchmark(config, batch=batch)
    root = config.repository_root / config.output_root
    documents: list[dict[str, Any]] = []
    for scenario in selection.scenarios:
        paths = artifact_paths(root, config.purpose, scenario)
        _require(paths.result.is_file(), f"resultado ausente: {scenario.scenario_id}")
        document = validate_document(read_json(paths.result), scenario)
        _require(document.get("official") is True, "resultado não oficial no benchmark")
        _validate_result(config, scenario, document)
        documents.append(document)
    return documents


def _validate_operations(config: CampaignConfig, batch: int, expected_ids: set[str]) -> list[dict[str, Any]]:
    directory = operational_root(config) / "operations"
    operations = [
        read_json(path) for path in sorted(directory.glob(f"batch-{batch:02d}_*.json"))
    ] if directory.exists() else []
    covered = {
        identifier for operation in operations if operation.get("round") == "initial"
        for identifier in operation.get("scenario_ids", [])
    }
    _require(covered == expected_ids, "diário não cobre a rodada inicial integral do lote")
    for operation in operations:
        sessions = operation.get("sessions", [])
        _require(bool(sessions), "operação sem sessão registrada")
        for session in sessions:
            summary_path = config.repository_root / session["resource_summary"]
            _require(summary_path.is_file(), "resumo de recursos ausente")
            summary = read_json(summary_path)
            _require(summary.get("passed") is True, "critério de recursos não satisfeito")
    return operations


def validate_batch(config: CampaignConfig, *, batch: int) -> dict[str, Any]:
    if batch > 1:
        previous = operational_root(config) / "barriers" / f"batch-{batch - 1:02d}.json"
        _require(previous.is_file() and read_json(previous).get("passed") is True,
                 "barreira anterior ausente ou inválida")
    selection = select_benchmark(config, batch=batch)
    expected_ids = {item.scenario_id for item in selection.scenarios}
    _require(not blocked_failures(config, batch=batch), "lote contém segunda falha")
    _require(not _temporary_files(config), "campanha contém arquivos temporários")
    documents = _documents(config, batch)
    _require(len(documents) == 324, "lote deve conter 324 resultados")
    algorithms = Counter(item["scenario"]["algorithm"] for item in documents)
    instances = Counter(item["scenario"]["instance"]["name"] for item in documents)
    ks = Counter(item["scenario"]["k"] for item in documents)
    seeds = Counter(item["scenario"]["seed"] for item in documents)
    _require(set(algorithms.values()) == {108}, "distribuição por algoritmo divergente")
    _require(set(instances.values()) == {108}, "distribuição por instância divergente")
    _require(set(ks.values()) == {54}, "distribuição por K divergente")
    _require(set(seeds.values()) == {54}, "distribuição por seed divergente")
    operations = _validate_operations(config, batch, expected_ids)
    runs, checkpoints = documents_to_frames(documents)
    _require(len(checkpoints) == 32_400, "lote deve conter 32400 checkpoints")
    tables = config.repository_root / config.output_root / "tables" / "benchmark_batches"
    runs_path = tables / f"batch-{batch:02d}_runs.parquet"
    checkpoints_path = tables / f"batch-{batch:02d}_checkpoints.parquet"
    _atomic_parquet(runs_path, runs)
    _atomic_parquet(checkpoints_path, checkpoints)
    report = {
        "schema_version": 1,
        "campaign": config.name,
        "batch": batch,
        "passed": True,
        "expected": 324,
        "completed": len(runs),
        "checkpoints": len(checkpoints),
        "scenario_ids_sha256": sha256(canonical_json(sorted(expected_ids))).hexdigest(),
        "runs": {"path": str(runs_path.relative_to(config.repository_root)), "sha256": file_sha256(runs_path)},
        "checkpoint_table": {"path": str(checkpoints_path.relative_to(config.repository_root)), "sha256": file_sha256(checkpoints_path)},
        "operations": len(operations),
        "validated_at": utc_now(),
    }
    path = operational_root(config) / "barriers" / f"batch-{batch:02d}.json"
    atomic_write_json(path, report)
    return report


def finalize_benchmark(config: CampaignConfig) -> dict[str, Any]:
    for batch in range(1, 6):
        path = operational_root(config) / "barriers" / f"batch-{batch:02d}.json"
        _require(path.is_file() and read_json(path).get("passed") is True,
                 f"barreira do lote {batch} ausente")
    return consolidate_campaign(config)
