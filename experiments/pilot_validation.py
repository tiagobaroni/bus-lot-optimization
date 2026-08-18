"""Validação funcional, operacional e reprodutível do piloto B10."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from metaheuristica import (
    ObjectiveWeights, canonicalize_solution, evaluate_solution, validate_solution,
)
from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.consolidation import _atomic_parquet
from experiments.execution import build_plan, execute_campaign
from experiments.resource_monitor import read_samples, summarize_samples
from experiments.scenarios import Scenario, expand_scenarios, file_sha256
from experiments.storage import (
    artifact_paths, atomic_write_json, read_json, validate_document,
)
from experiments.worker import _load_instance


EVALUATION_FIELDS = (
    "total_cost", "c_demand", "c_production", "c_territorial", "c_affinity",
    "cv_demand", "cv_production",
)
REPRODUCTION_CASES = (
    ("tabu", "artesp_rmsp_20", 3),
    ("aco", "artesp_rmsp_60", 8),
    ("pso", "artesp_rmsp_150", 3),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigurationError(message)


def _load_official_documents(config: CampaignConfig) -> list[tuple[Scenario, dict[str, Any]]]:
    output_root = config.repository_root / config.output_root
    documents: list[tuple[Scenario, dict[str, Any]]] = []
    for scenario in expand_scenarios(config):
        path = artifact_paths(output_root, config.purpose, scenario).result
        _require(path.is_file(), f"resultado ausente: {scenario.scenario_id}")
        document = validate_document(read_json(path), scenario)
        _require(document.get("official") is True, "piloto contém resultado não oficial")
        documents.append((scenario, document))
    return documents


def _validate_result(config: CampaignConfig, scenario: Scenario, document: dict[str, Any]) -> None:
    result = document["result"]
    solution = result["solution"]
    path = config.repository_root / scenario.payload["instance"]["path"]
    _require(
        file_sha256(path) == scenario.payload["instance"]["sha256"],
        "hash da instância divergente",
    )
    instance = _load_instance(path)
    labels = validate_solution(
        solution,
        n_units=instance.n_units,
        k=scenario.payload["k"],
    )
    _require(
        canonicalize_solution(
            labels, n_units=instance.n_units, k=scenario.payload["k"]
        ).tolist() == solution,
        f"solução não canônica: {scenario.scenario_id}",
    )
    checkpoints = result["checkpoints"]
    costs = [float(item["evaluation"]["total_cost"]) for item in checkpoints]
    _require(
        all(current <= previous + 1e-15 for previous, current in zip(costs, costs[1:])),
        f"incumbente crescente: {scenario.scenario_id}",
    )
    _require(
        checkpoints[-1]["evaluation"] == result["evaluation"],
        f"último checkpoint divergente: {scenario.scenario_id}",
    )
    weights = ObjectiveWeights(**scenario.payload["weights"])
    recalculated = evaluate_solution(
        instance, labels, k=scenario.payload["k"], weights=weights
    )
    recalculated_dict = asdict(recalculated)
    _require(
        recalculated_dict == result["evaluation"],
        f"reavaliação divergente: {scenario.scenario_id}",
    )
    _require(result["evaluations"] == scenario.payload["budget"], "orçamento divergente")
    _require(result["termination_reason"] == "budget_exhausted", "término divergente")
    _require(result["cache_hits"] == 0, "cache deveria permanecer desabilitado")
    _require(
        all(np.isfinite(float(result["evaluation"][field])) for field in EVALUATION_FIELDS),
        "avaliação não finita",
    )
    limits = document["provenance"].get("thread_limits", {})
    _require(limits and set(limits.values()) == {"1"}, "limites de threads divergentes")


def _validate_consolidation(config: CampaignConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    tables = config.repository_root / config.output_root / "tables"
    manifest_path = tables / "pilot_manifest.json"
    runs_path = tables / "pilot_runs.parquet"
    checkpoints_path = tables / "pilot_checkpoints.parquet"
    manifest = read_json(manifest_path)
    _require(manifest.get("complete") is True, "manifesto do piloto incompleto")
    _require(manifest.get("official") is True, "manifesto do piloto não oficial")
    _require(manifest.get("expected") == 18, "manifesto deve esperar 18 execuções")
    _require(manifest.get("completed") == 18, "manifesto deve conter 18 execuções")
    _require(file_sha256(runs_path) == manifest["runs"]["sha256"], "hash de runs divergente")
    _require(
        file_sha256(checkpoints_path) == manifest["checkpoints"]["sha256"],
        "hash de checkpoints divergente",
    )
    runs = pd.read_parquet(runs_path)
    checkpoints = pd.read_parquet(checkpoints_path)
    _require(len(runs) == 18, "pilot_runs deve conter 18 linhas")
    _require(len(checkpoints) == 1_800, "pilot_checkpoints deve conter 1.800 linhas")
    _require(not runs["scenario_id"].duplicated().any(), "runs contém duplicatas")
    _require(
        (checkpoints.groupby("scenario_id").size() == 100).all(),
        "cenário sem exatamente 100 checkpoints",
    )
    return runs, checkpoints, manifest


def _validate_interruption(config: CampaignConfig) -> dict[str, Any]:
    path = (
        config.repository_root / config.output_root / "operational"
        / config.name / "interruption.json"
    )
    report = read_json(path)
    _require(report.get("expected") == 18, "interrupção com total inesperado")
    _require(1 <= int(report.get("completed", 0)) < 18, "interrupção fora da janela aprovada")
    _require(report.get("failed") == 0, "interrupção registrou falha")
    _require(report.get("temporary_files") == [], "interrupção deixou temporários")
    _require(report.get("workers") == 16, "interrupção não usou 16 workers")
    plan = build_plan(config)
    _require(plan.completed == 18 and plan.pending == 0, "retomada não concluiu o piloto")
    completed_before = {
        identifier for identifier, state in report["states"].items()
        if state == "completed"
    }
    current_ids = {scenario.scenario_id for scenario in expand_scenarios(config)}
    _require(completed_before <= current_ids, "retomada perdeu resultado previamente válido")
    return {
        "passed": True,
        "completed_before_interruption": len(completed_before),
        "pending_before_resume": report["pending"],
        "workers": report["workers"],
    }


def _deterministic_result(result: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(result)
    comparable.pop("runtime_seconds", None)
    return comparable


def reproduce_selected(config: CampaignConfig) -> list[dict[str, Any]]:
    scenarios = expand_scenarios(config)
    root = config.repository_root
    temporary_root = root / "_temp"
    temporary_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="b10_reproduction_", dir=temporary_root))
    relative_output = str(directory.relative_to(root))
    isolated = replace(config, output_root=relative_output)
    rows: list[dict[str, Any]] = []
    official_root = root / config.output_root
    for algorithm, instance, k in REPRODUCTION_CASES:
        scenario = next(
            item for item in scenarios
            if item.payload["algorithm"] == algorithm
            and item.payload["instance"]["name"] == instance
            and item.payload["k"] == k
        )
        summary = execute_campaign(
            isolated,
            workers=1,
            scenario_id=scenario.scenario_id,
            allow_dirty=True,
        )
        _require(summary.succeeded == 1 and summary.failed == 0, "reprodução falhou")
        original_path = artifact_paths(
            official_root, config.purpose, scenario
        ).result
        repeated_path = artifact_paths(
            directory, config.purpose, scenario
        ).result
        original = validate_document(read_json(original_path), scenario)
        repeated = validate_document(read_json(repeated_path), scenario)
        equal = _deterministic_result(original["result"]) == _deterministic_result(
            repeated["result"]
        )
        _require(equal, f"reprodução divergente: {scenario.scenario_id}")
        rows.append({
            "scenario_id": scenario.scenario_id,
            "algorithm": algorithm,
            "instance": instance,
            "k": k,
            "passed": True,
        })
    return rows


def validate_pilot(config: CampaignConfig, *, reproduce: bool = True) -> dict[str, Any]:
    _require(config.name == "pilot_prebenchmark", "configuração não é o piloto B10")
    documents = _load_official_documents(config)
    commits = {document["provenance"].get("git_commit") for _, document in documents}
    _require(len(commits) == 1 and None not in commits, "proveniência não uniforme")
    for scenario, document in documents:
        _validate_result(config, scenario, document)
    runs, checkpoints, manifest = _validate_consolidation(config)
    interruption = _validate_interruption(config)

    operational = (
        config.repository_root / config.output_root / "operational" / config.name
    )
    samples = read_samples(operational / "resources.csv")
    resource_summary = summarize_samples(samples, workers=16)
    _require(resource_summary["passed"] is True, "critérios de recursos falharam")
    tables = config.repository_root / config.output_root / "tables"
    resource_samples_path = tables / "pilot_resource_samples.parquet"
    resource_summary_path = tables / "pilot_resource_summary.json"
    _atomic_parquet(resource_samples_path, pd.DataFrame(samples))
    atomic_write_json(resource_summary_path, resource_summary)

    reproductions = reproduce_selected(config) if reproduce else []
    validation = {
        "schema_version": 1,
        "campaign": config.name,
        "passed": True,
        "runs": len(runs),
        "checkpoints": len(checkpoints),
        "campaign_commit": next(iter(commits)),
        "manifest_sha256": file_sha256(tables / "pilot_manifest.json"),
        "interruption": interruption,
        "resources": {
            "passed": resource_summary["passed"],
            "summary_sha256": file_sha256(resource_summary_path),
            "samples_sha256": file_sha256(resource_samples_path),
        },
        "reproductions": reproductions,
        "reproduction_passed": len(reproductions) == 3 if reproduce else None,
        "functional_checks": {"passed": True, "documents": len(documents)},
    }
    atomic_write_json(tables / "pilot_validation.json", validation)
    return validation
