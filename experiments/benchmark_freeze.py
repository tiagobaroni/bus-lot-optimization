"""Geração e verificação do congelamento que autoriza a B11."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.pilot_validation import _load_official_documents, _validate_result
from experiments.provenance import capture_provenance, utc_now
from experiments.scenarios import file_sha256
from experiments.storage import atomic_write_json, read_json


FREEZE_PATH = Path("results/tables/benchmark_freeze_manifest.json")
PILOT_ARTIFACTS = (
    "results/tables/pilot_runs.parquet",
    "results/tables/pilot_checkpoints.parquet",
    "results/tables/pilot_manifest.json",
    "results/tables/pilot_resource_samples.parquet",
    "results/tables/pilot_resource_summary.json",
    "results/tables/pilot_validation.json",
    "results/tables/pilot_preliminary.csv",
    "results/figures/pilot_convergence.png",
    "results/figures/pilot_convergence.pdf",
    "results/figures/pilot_time.png",
    "results/figures/pilot_time.pdf",
    "results/figures/pilot_resources.png",
    "results/figures/pilot_resources.pdf",
)
FIXED_PROTECTED = (
    "data/instances/artesp_rmsp_20.json",
    "data/instances/artesp_rmsp_60.json",
    "data/instances/artesp_rmsp_150.json",
    "data/instances/artesp_rmsp_150_units.parquet",
    "data/instances/artesp_rmsp_150_pair_metrics.parquet",
    "data/instances/selection_manifest.json",
    "experiments/configs/pilot.toml",
    "experiments/configs/benchmark.toml",
    "experiments/configs/frozen_parameters.toml",
    "results/tables/benchmark_execution_schedule.json",
    "pyproject.toml",
    "uv.lock",
)


def protected_paths(root: Path) -> tuple[str, ...]:
    dynamic = [
        str(path.relative_to(root))
        for directory, pattern in ((root / "src/metaheuristica", "*.py"), (root / "experiments", "*.py"))
        for path in directory.rglob(pattern)
    ]
    return tuple(sorted(set((*FIXED_PROTECTED, *dynamic))))


def _hash_files(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise ConfigurationError(f"arquivo protegido ausente: {relative}")
        hashes[relative] = file_sha256(path)
    return hashes


def _environment(provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        key: provenance[key]
        for key in (
            "python", "system", "kernel", "architecture", "processor", "cpu_count",
            "packages", "thread_limits",
        )
    }


def _revalidate_pilot_behaviour(
    config: CampaignConfig, validation: dict[str, Any]
) -> None:
    """Reavalia artefatos reais do piloto antes de assinar o congelamento.

    O veredito gravado em ``pilot_validation.json`` atesta o passado. Só a
    reexecução de ``_validate_result`` contra os documentos oficiais atesta que o
    código presente ainda reproduz o comportamento que o piloto aprovou, e é essa
    reavaliação que detecta alteração semântica da função objetivo.
    """

    documents = _load_official_documents(config)
    if not documents:
        raise ConfigurationError("piloto sem documento oficial para revalidar")
    commits = {document["provenance"].get("git_commit") for _, document in documents}
    if commits != {validation.get("campaign_commit")}:
        raise ConfigurationError(
            "proveniência dos artefatos do piloto diverge do veredito: "
            f"{sorted(commit or '' for commit in commits)}"
        )
    for scenario, document in documents:
        _validate_result(config, scenario, document)


def generate_freeze_manifest(config: CampaignConfig, *, workers: int) -> dict[str, Any]:
    if config.name != "pilot_prebenchmark":
        raise ConfigurationError("congelamento exige o piloto oficial da B10")
    root = config.repository_root
    validation = read_json(root / "results/tables/pilot_validation.json")
    if validation.get("passed") is not True or validation.get("reproduction_passed") is not True:
        raise ConfigurationError("piloto ainda não foi integralmente aprovado")
    artifact_hashes = _hash_files(root, PILOT_ARTIFACTS)
    provenance = capture_provenance(root, allow_dirty=False)
    pilot_commit = validation.get("campaign_commit")
    if pilot_commit != provenance["git_commit"]:
        raise ConfigurationError(
            "commit do piloto diverge do HEAD: "
            f"{pilot_commit} contra {provenance['git_commit']}"
        )
    _revalidate_pilot_behaviour(config, validation)
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "pilot_campaign": config.name,
        "pilot_commit": pilot_commit,
        "approved_workers": workers,
        "frozen_parameters_sha256": config.frozen_parameters_sha256,
        "protected_files": _hash_files(root, protected_paths(root)),
        "pilot_artifacts": artifact_hashes,
        "environment": _environment(provenance),
    }
    path = root / FREEZE_PATH
    atomic_write_json(path, manifest)
    verify_freeze_manifest(root, workers=workers, check_environment=True)
    return manifest


def verify_freeze_manifest(
    root: Path,
    *,
    workers: int,
    check_environment: bool = True,
) -> dict[str, Any]:
    manifest = read_json(root / FREEZE_PATH)
    if manifest.get("schema_version") != 1:
        raise ConfigurationError("versão do congelamento incompatível")
    if manifest.get("approved_workers") != workers:
        raise ConfigurationError("quantidade de workers diverge do congelamento")
    expected_protected = manifest.get("protected_files")
    if not isinstance(expected_protected, dict):
        raise ConfigurationError("arquivos protegidos ausentes do congelamento")
    current_scope = protected_paths(root)
    if current_scope != tuple(sorted(expected_protected)):
        divergent = sorted(set(current_scope) ^ set(expected_protected))
        raise ConfigurationError(f"escopo protegido divergente: {divergent}")
    current_protected = _hash_files(root, current_scope)
    if current_protected != expected_protected:
        changed = sorted(
            path for path in set(current_protected) | set(expected_protected)
            if current_protected.get(path) != expected_protected.get(path)
        )
        raise ConfigurationError(f"congelamento divergente: {changed}")
    expected_artifacts = manifest.get("pilot_artifacts")
    if not isinstance(expected_artifacts, dict):
        raise ConfigurationError("artefatos do piloto ausentes do congelamento")
    if _hash_files(root, tuple(sorted(expected_artifacts))) != expected_artifacts:
        raise ConfigurationError("artefato do piloto diverge do congelamento")
    if check_environment:
        current_environment = _environment(capture_provenance(root, allow_dirty=True))
        if current_environment != manifest.get("environment"):
            raise ConfigurationError("ambiente diverge do congelamento")
    return manifest
