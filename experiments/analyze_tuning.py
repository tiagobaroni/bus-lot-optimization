"""CLI para resumir, selecionar e congelar o tuning oficial."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.config import ALGORITHM_FIELDS, load_campaign
from experiments.consolidation import _atomic_parquet
from experiments.provenance import utc_now
from experiments.scenarios import canonical_json, file_sha256
from experiments.storage import atomic_write_json, read_json
from experiments.tuning_analysis import TOLERANCE, parameter_effects, summarize_tuning


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_sources(config) -> tuple[dict[str, Any], pd.DataFrame, Path, Path]:
    tables = config.repository_root / config.output_root / "tables"
    manifest_path = tables / "tuning_manifest.json"
    manifest = read_json(manifest_path)
    if not manifest.get("complete") or not manifest.get("official"):
        raise ConfigurationError("manifesto do tuning deve ser completo e oficial")
    if manifest.get("expected") != 440 or manifest.get("completed") != 440:
        raise ConfigurationError("manifesto não contém 440 resultados")
    if manifest.get("config_sha256") != file_sha256(config.source_path):
        raise ConfigurationError("hash da configuração diverge do manifesto")
    runs_path = config.repository_root / manifest["runs"]["path"]
    checkpoints_path = config.repository_root / manifest["checkpoints"]["path"]
    if file_sha256(runs_path) != manifest["runs"]["sha256"]:
        raise ConfigurationError("hash de tuning_runs diverge do manifesto")
    if file_sha256(checkpoints_path) != manifest["checkpoints"]["sha256"]:
        raise ConfigurationError("hash de tuning_checkpoints diverge do manifesto")
    runs = pd.read_parquet(runs_path)
    checkpoints = pd.read_parquet(checkpoints_path)
    if len(runs) != 440 or len(checkpoints) != 44000:
        raise ConfigurationError("quantidade de runs ou checkpoints inválida")
    if set(checkpoints["scenario_id"]) != set(runs["scenario_id"]):
        raise ConfigurationError("IDs de runs e checkpoints divergem")
    if not (checkpoints.groupby("scenario_id").size() == 100).all():
        raise ConfigurationError("cada execução deve possuir 100 checkpoints")
    return manifest, runs, runs_path, checkpoints_path


def _campaign_metadata(runs: pd.DataFrame) -> tuple[str, int]:
    commits: set[str] = set()
    workers: set[int] = set()
    for text in runs["provenance_json"]:
        provenance = json.loads(text)
        if not provenance.get("official"):
            raise ConfigurationError("runs contém proveniência não oficial")
        commit = provenance.get("git_commit")
        worker_count = provenance.get("campaign_workers")
        if not isinstance(commit, str) or not commit:
            raise ConfigurationError("commit ausente na proveniência")
        if isinstance(worker_count, bool) or not isinstance(worker_count, int):
            raise ConfigurationError("workers ausentes na proveniência")
        commits.add(commit)
        workers.add(worker_count)
    if len(commits) != 1 or len(workers) != 1:
        raise ConfigurationError("campanha mistura commits ou quantidades de workers")
    return commits.pop(), workers.pop()


def _selection_document(
    summary: pd.DataFrame,
    *,
    commit: str,
    workers: int,
    manifest_path: Path,
    runs_path: Path,
    summary_path: Path,
    effects_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    winners: dict[str, Any] = {}
    for algorithm in sorted(ALGORITHM_FIELDS):
        ranked = summary[summary["algorithm"] == algorithm].sort_values("rank")
        winner = ranked.iloc[0]
        runner_up = ranked.iloc[1]
        winners[algorithm] = {
            "parameters": json.loads(winner["parameters_json"]),
            "statistics": {
                "mean_cost": float(winner["mean_cost"]),
                "std_cost": float(winner["std_cost"]),
                "mean_runtime_seconds": float(winner["mean_runtime_seconds"]),
            },
            "runner_up": {
                "parameters": json.loads(runner_up["parameters_json"]),
                "mean_cost": float(runner_up["mean_cost"]),
            },
            "mean_cost_difference_to_runner_up": float(
                runner_up["mean_cost"] - winner["mean_cost"]
            ),
        }
    return {
        "schema_version": 1,
        "selection_method": "automatic_no_override",
        "tolerance": TOLERANCE,
        "criteria": [
            "mean_cost", "sample_std_cost", "mean_runtime_seconds",
            "lexicographic_parameters",
        ],
        "seeds": list(range(10)),
        "n_configurations": len(summary),
        "n_runs": int(summary["n_runs"].sum()),
        "campaign_commit": commit,
        "campaign_workers": workers,
        "selected_at": utc_now(),
        "sources": {
            "manifest": {"path": str(manifest_path.relative_to(repository_root)), "sha256": file_sha256(manifest_path)},
            "runs": {"path": str(runs_path.relative_to(repository_root)), "sha256": file_sha256(runs_path)},
            "summary": {"path": str(summary_path.relative_to(repository_root)), "sha256": file_sha256(summary_path)},
            "parameter_effects": {"path": str(effects_path.relative_to(repository_root)), "sha256": file_sha256(effects_path)},
        },
        "winners": winners,
    }


def _frozen_toml(selection: dict[str, Any], selection_path: Path, root: Path) -> str:
    lines = [
        "schema_version = 1",
        f'campaign_commit = "{selection["campaign_commit"]}"',
        f'selection_path = "{selection_path.relative_to(root)}"',
        f'selection_sha256 = "{file_sha256(selection_path)}"',
        f'manifest_path = "{selection["sources"]["manifest"]["path"]}"',
        f'manifest_sha256 = "{selection["sources"]["manifest"]["sha256"]}"',
        'change_policy = "requires_new_tuning"',
        "",
    ]
    for algorithm in ("tabu", "aco", "pso"):
        lines.append(f"[{algorithm}]")
        parameters = selection["winners"][algorithm]["parameters"]
        for name in ALGORITHM_FIELDS[algorithm]:
            value = parameters[name]
            lines.append(f"{name} = {json.dumps(value)}")
        lines.append("")
    return "\n".join(lines)


def analyze(config_path: str | Path) -> dict[str, Any]:
    config = load_campaign(config_path)
    if config.purpose != "tuning":
        raise ConfigurationError("análise requer configuração de tuning")
    manifest, runs, runs_path, _ = _validate_sources(config)
    commit, workers = _campaign_metadata(runs)
    summary = summarize_tuning(runs, config)
    effects = parameter_effects(summary)
    tables = config.repository_root / config.output_root / "tables"
    summary_path = tables / "tuning_summary.parquet"
    effects_path = tables / "tuning_parameter_effects.parquet"
    selection_path = tables / "tuning_selection.json"
    frozen_path = config.repository_root / "experiments/configs/frozen_parameters.toml"
    _atomic_parquet(summary_path, summary)
    _atomic_parquet(effects_path, effects)
    selection = _selection_document(
        summary, commit=commit, workers=workers,
        manifest_path=tables / "tuning_manifest.json", runs_path=runs_path,
        summary_path=summary_path, effects_path=effects_path,
        repository_root=config.repository_root,
    )
    atomic_write_json(selection_path, selection)
    _atomic_text(frozen_path, _frozen_toml(selection, selection_path, config.repository_root))
    if file_sha256(selection_path) not in frozen_path.read_text(encoding="utf-8"):
        raise ConfigurationError("TOML congelado diverge da seleção")
    return selection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analisa o tuning oficial")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        selection = analyze(args.config)
    except ConfigurationError as error:
        parser.error(str(error))
    print(json.dumps(selection, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
