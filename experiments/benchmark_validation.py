"""Barreiras e consolidação progressiva do benchmark principal."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.benchmark_batches import select_benchmark
from experiments.benchmark_freeze import FREEZE_PATH, verify_freeze_manifest
from experiments.benchmark_operations import blocked_failures, operational_root
from experiments.config import CampaignConfig
from experiments.consolidation import _atomic_parquet, consolidate_campaign, documents_to_frames
from experiments.pilot_validation import _validate_result
from experiments.provenance import capture_provenance, utc_now
from experiments.scenarios import canonical_json, expand_scenarios, file_sha256
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


def _unexpected_results(config: CampaignConfig) -> list[str]:
    """Nomeia todo artefato do diretório de resultados fora da campanha.

    O escopo é a campanha inteira e não o lote, porque quando a barreira do lote
    ``n`` roda os lotes anteriores já publicaram legitimamente os seus
    resultados. Somente ``raw`` é varrido: ``failures`` guarda registros de falha
    e de interrupção, que não são resultados.
    """

    raw = config.repository_root / config.output_root / "raw" / config.purpose
    if not raw.exists():
        return []
    known = {scenario.filename for scenario in expand_scenarios(config)}
    return sorted(path.name for path in raw.iterdir() if path.name not in known)


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
            # A barreira não pode aceitar veredito calculado sobre a série
            # acumulada: os critérios valem por sessão, e um resumo sem
            # identificação de sessão não diz sobre qual janela ele decidiu.
            _require(
                bool(summary.get("session_id")),
                "resumo de recursos sem identificação de sessão",
            )
            _require(
                int(summary.get("samples_session", 0)) >= 1,
                "resumo de recursos sem amostra da sessão",
            )
            _require(summary.get("passed") is True, "critério de recursos não satisfeito")
    return operations


def validate_batch(
    config: CampaignConfig, *, batch: int, workers: int = 16
) -> dict[str, Any]:
    if batch > 1:
        previous = operational_root(config) / "barriers" / f"batch-{batch - 1:02d}.json"
        _require(previous.is_file() and read_json(previous).get("passed") is True,
                 "barreira anterior ausente ou inválida")
    # Congelamento e proveniência pertencem à barreira, e não à linha de comando
    # que a invoca: é o relatório do lote que serve de evidência auditável.
    verify_freeze_manifest(config.repository_root, workers=workers)
    freeze_sha256 = file_sha256(config.repository_root / FREEZE_PATH)
    provenance = capture_provenance(config.repository_root, allow_dirty=False)
    selection = select_benchmark(config, batch=batch)
    expected_ids = {item.scenario_id for item in selection.scenarios}
    _require(not blocked_failures(config, batch=batch), "lote contém segunda falha")
    _require(not _temporary_files(config), "campanha contém arquivos temporários")
    unexpected = _unexpected_results(config)
    _require(not unexpected, f"resultado inesperado na campanha: {unexpected}")
    documents = _documents(config, batch)
    _require(len(documents) == 324, "lote deve conter 324 resultados")
    commits = {item["provenance"].get("git_commit") for item in documents}
    _require(
        len(commits) == 1 and None not in commits,
        f"proveniência do lote não é uniforme: {sorted(commit or '' for commit in commits)}",
    )
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
    # Tabela de barreira é artefato operacional: gravá-la em results/tables/,
    # que é versionado, sujava a worktree e impedia oficialmente o lote seguinte.
    tables = (
        config.repository_root / config.output_root / "operational" / "benchmark_batches"
    )
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
        "workers": workers,
        "git_commit": provenance["git_commit"],
        "git_dirty": provenance["git_dirty"],
        "results_commit": next(iter(commits)),
        "freeze_sha256": freeze_sha256,
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
