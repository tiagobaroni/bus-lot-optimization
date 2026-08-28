"""CLI para resumir, selecionar e congelar o tuning oficial."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import pandas as pd

from metaheuristica.errors import ConfigurationError

from experiments.config import ALGORITHM_FIELDS, CampaignConfig, load_campaign
from experiments.consolidation import _atomic_parquet
from experiments.provenance import utc_now
from experiments.scenarios import canonical_json, file_sha256
from experiments.storage import atomic_write_json, read_json
from experiments.tuning_analysis import TOLERANCES, parameter_effects, summarize_tuning


FROZEN_RELATIVE = "experiments/configs/frozen_parameters.toml"
MANIFEST_NAME = "tuning_manifest.json"


def _artifact_paths(root: Path, output_root: str) -> dict[str, Path]:
    """Os quatro artefatos escritos pela análise, sob a raiz dada."""

    tables = root / output_root / "tables"
    return {
        "summary": tables / "tuning_summary.parquet",
        "parameter_effects": tables / "tuning_parameter_effects.parquet",
        "selection": tables / "tuning_selection.json",
        "frozen": root / FROZEN_RELATIVE,
    }


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


def _sources(
    entries: dict[str, tuple[Path, Path]], repository_root: Path
) -> dict[str, Any]:
    """Caminho lógico na raiz oficial e sha256 dos bytes efetivamente produzidos.

    Os dois coincidem na análise oficial. No modo de verificação os bytes vivem
    num diretório descartável, e o documento continua nomeando os caminhos
    oficiais, de modo que o que é comparado é o conteúdo e não o destino.
    """

    return {
        name: {
            "path": str(logical.relative_to(repository_root)),
            "sha256": file_sha256(produced),
        }
        for name, (logical, produced) in entries.items()
    }


def _selection_document(
    summary: pd.DataFrame,
    *,
    commit: str,
    workers: int,
    sources: dict[str, Any],
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
        "tolerance": dict(TOLERANCES),
        "criteria": [
            "mean_cost", "sample_std_cost", "mean_runtime_seconds",
            "lexicographic_parameters",
        ],
        "seeds": list(range(10)),
        "n_configurations": len(summary),
        "n_runs": int(summary["n_runs"].sum()),
        "campaign_commit": commit,
        "campaign_workers": workers,
        # Sem carimbo de tempo, de propósito. O sha256 deste documento é embutido
        # em `frozen_parameters.toml`, que o congelamento protege; um instante de
        # execução aqui dentro faz o hash de um arquivo protegido mudar a cada
        # reexecução, sem que decisão alguma tenha mudado, e bloqueia a campanha.
        # O instante da execução é informado pela CLI, fora do que entra no hash.
        "sources": sources,
        "winners": winners,
    }


def _frozen_toml(
    selection: dict[str, Any], *, selection_path: str, selection_sha256: str
) -> str:
    lines = [
        "schema_version = 1",
        f'campaign_commit = "{selection["campaign_commit"]}"',
        f'selection_path = "{selection_path}"',
        f'selection_sha256 = "{selection_sha256}"',
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


def _load(config_path: str | Path) -> CampaignConfig:
    config = load_campaign(config_path)
    if config.purpose != "tuning":
        raise ConfigurationError("análise requer configuração de tuning")
    return config


def _produce(config: CampaignConfig, destination: Path) -> dict[str, Any]:
    """Produz os quatro artefatos sob `destination` e devolve a seleção.

    `destination` é a própria raiz do repositório na análise oficial e um
    diretório descartável no modo de verificação. Os caminhos gravados dentro do
    documento e do TOML são sempre os lógicos, relativos à raiz oficial, de modo
    que os bytes produzidos pelos dois modos são comparáveis diretamente.
    """

    _, runs, runs_path, _ = _validate_sources(config)
    commit, workers = _campaign_metadata(runs)
    summary = summarize_tuning(runs, config)
    effects = parameter_effects(summary)
    logical = _artifact_paths(config.repository_root, config.output_root)
    produced = _artifact_paths(destination, config.output_root)
    tables = config.repository_root / config.output_root / "tables"
    manifest_path = tables / MANIFEST_NAME
    _atomic_parquet(produced["summary"], summary)
    _atomic_parquet(produced["parameter_effects"], effects)
    selection = _selection_document(
        summary, commit=commit, workers=workers,
        sources=_sources(
            {
                "manifest": (manifest_path, manifest_path),
                "runs": (runs_path, runs_path),
                "summary": (logical["summary"], produced["summary"]),
                "parameter_effects": (
                    logical["parameter_effects"], produced["parameter_effects"]
                ),
            },
            config.repository_root,
        ),
    )
    atomic_write_json(produced["selection"], selection)
    selection_sha256 = file_sha256(produced["selection"])
    _atomic_text(
        produced["frozen"],
        _frozen_toml(
            selection,
            selection_path=str(
                logical["selection"].relative_to(config.repository_root)
            ),
            selection_sha256=selection_sha256,
        ),
    )
    if selection_sha256 not in produced["frozen"].read_text(encoding="utf-8"):
        raise ConfigurationError("TOML congelado diverge da seleção")
    return selection


def analyze(config_path: str | Path) -> dict[str, Any]:
    config = _load(config_path)
    return _produce(config, config.repository_root)


def _identical(produced: Path, official: Path) -> bool:
    if not official.is_file():
        return False
    return file_sha256(produced) == file_sha256(official)


def verify_analysis(config_path: str | Path) -> tuple[dict[str, Any], list[str]]:
    """Reexecuta a análise sem escrever e nomeia os artefatos divergentes.

    É o modo que permite conferir a análise oficial sob congelamento: os
    artefatos são produzidos num diretório descartável, fora da raiz, e apenas
    comparados com os oficiais. Artefato ausente conta como divergente.
    """

    config = _load(config_path)
    logical = _artifact_paths(config.repository_root, config.output_root)
    with tempfile.TemporaryDirectory(prefix="analyze_tuning_verify_") as name:
        destination = Path(name)
        selection = _produce(config, destination)
        produced = _artifact_paths(destination, config.output_root)
        divergent = sorted(
            str(logical[key].relative_to(config.repository_root))
            for key in logical
            if not _identical(produced[key], logical[key])
        )
    return selection, divergent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analisa o tuning oficial")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--verify", action="store_true",
        help="compara os artefatos em vez de escrevê-los; não grava nada",
    )
    args = parser.parse_args(argv)
    divergent: list[str] = []
    try:
        if args.verify:
            selection, divergent = verify_analysis(args.config)
        else:
            selection = analyze(args.config)
    except ConfigurationError as error:
        parser.error(str(error))
    print(json.dumps(selection, ensure_ascii=False, sort_keys=True))
    # O instante da execução vai para o erro padrão, e não para dentro do
    # documento: a saída padrão é o documento de seleção, resumido por sha256 no
    # TOML congelado, e qualquer carimbo ali dentro reabre o achado F9-3.
    print(f"análise executada em {utc_now()}", file=sys.stderr)
    if not args.verify:
        return 0
    if divergent:
        print("artefatos divergentes: " + ", ".join(divergent), file=sys.stderr)
        return 1
    print("artefatos idênticos aos oficiais", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
