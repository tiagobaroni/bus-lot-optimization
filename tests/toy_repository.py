"""Repositório de benchmark de brinquedo, versionado e congelado.

A barreira de lote só aceita 324 resultados por lote e 32.400 checkpoints, de
modo que exercitá-la com validadores reais exige uma campanha completa. Este
módulo constrói um repositório Git independente, com o escopo protegido em
miniatura, três instâncias sintéticas de nove unidades e orçamento 100, e
executa dois lotes inteiros pelo caminho saturado, isto é sem filtros de
subgrupo. Nada aqui escreve fora de ``tmp_path``.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pandas as pd


from experiments.benchmark_batches import select_benchmark
from experiments.benchmark_freeze import (
    FIXED_PROTECTED, FREEZE_PATH, PILOT_ARTIFACTS, _environment, _hash_files,
    protected_paths,
)
from experiments.benchmark_operations import execute_operation, resource_paths
from experiments.config import load_campaign
from experiments.provenance import capture_provenance, utc_now
from experiments.resource_monitor import summarize_samples
from experiments.storage import atomic_write_json


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GIT_IDENTITY = ("-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture")
TOY_INSTANCES = ("toy_a", "toy_b", "toy_c")
TOY_K_VALUES = (3, 4, 5, 6, 7, 8)
TOY_UNITS = 9
TOY_PARAMETERS: dict[str, dict[str, Any]] = {
    "aco": {"alpha": 1.0, "beta": 2.0, "rho": 0.1, "n_ants": 10},
    "pso": {"n_particles": 20, "inertia": 0.7, "cognitive": 1.5, "social": 1.5},
    "tabu": {"tabu_tenure": 5, "neighborhood_size": 10, "stagnation_limit": 20},
}


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True
    )
    return completed.stdout.decode()


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _instance_document(name: str, offset: int) -> dict[str, Any]:
    units = [
        {
            "unit_id": f"U{index:02d}",
            "passengers_day": 10.0 + index + offset,
            "pu_km_day": 100.0 + 10.0 * index + offset,
        }
        for index in range(TOY_UNITS)
    ]
    pairs = [
        {
            "unit_id_a": first["unit_id"],
            "unit_id_b": second["unit_id"],
            "s_territorial": round(((left * 7 + right * 3 + offset) % 10) / 10.0, 2),
            "t_terminal": float((left + right + offset) % 2),
            "i_integration": float((left * right + offset) % 2),
            "o_market": round(((left * 3 + right * 5 + offset) % 10) / 10.0, 2),
        }
        for (left, first), (right, second) in itertools.combinations(
            list(enumerate(units)), 2
        )
    ]
    return {
        "schema_version": "1.0.0",
        "name": name,
        "description": "instância sintética da suíte",
        "k": 2,
        "units": units,
        "pair_metrics": pairs,
        "absent_pair_rule": "zero",
    }


def _campaign_toml(seeds: tuple[int, ...]) -> str:
    lines = [
        "schema_version = 1",
        'name = "toy_benchmark"',
        'purpose = "benchmark"',
        'output_root = "results"',
        f"seeds = {list(seeds)}",
        "cache_enabled = false",
        "",
        "[weights]",
        "demand = 0.25",
        "production = 0.25",
        "territorial = 0.25",
        "affinity = 0.25",
    ]
    for name in TOY_INSTANCES:
        lines += [
            "",
            "[[instances]]",
            f'name = "{name}"',
            f'path = "data/instances/{name}.json"',
            "budget = 100",
            f"k_values = {list(TOY_K_VALUES)}",
        ]
    for algorithm, parameters in TOY_PARAMETERS.items():
        lines += ["", f"[algorithms.{algorithm}]"]
        lines += [f"{field} = [{value}]" for field, value in parameters.items()]
    return "\n".join(lines) + "\n"


def _write_pilot_runs(path: Path) -> None:
    rows = [
        {
            "algorithm": algorithm,
            "instance": instance,
            "k": k,
            "runtime_seconds": 1.0 + index + k / 10.0,
        }
        for index, (algorithm, instance) in enumerate(
            itertools.product(sorted(TOY_PARAMETERS), TOY_INSTANCES)
        )
        for k in (3, 8)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def write_freeze_manifest(root: Path, *, workers: int = 16) -> dict[str, Any]:
    """Congelamento íntegro do repositório de brinquedo, sem dublê algum."""

    provenance = capture_provenance(root, allow_dirty=True)
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "pilot_campaign": "toy_pilot",
        "pilot_commit": provenance["git_commit"],
        "approved_workers": workers,
        "frozen_parameters_sha256": None,
        "protected_files": _hash_files(root, protected_paths(root)),
        "pilot_artifacts": _hash_files(root, PILOT_ARTIFACTS),
        "environment": _environment(provenance),
    }
    atomic_write_json(root / FREEZE_PATH, manifest)
    return manifest


def build_toy_repository(root: Path, *, seeds: tuple[int, ...] = tuple(range(10, 22))):
    """Cria o repositório, versiona o escopo protegido e devolve a campanha."""

    root.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPOSITORY_ROOT / ".gitignore", root / ".gitignore")
    for offset, name in enumerate(TOY_INSTANCES):
        _write(
            root, f"data/instances/{name}.json",
            json.dumps(_instance_document(name, offset), ensure_ascii=False),
        )
    _write(root, "experiments/configs/benchmark.toml", _campaign_toml(seeds))
    _write(root, "experiments/toy_automation.py", '"""Automação de brinquedo."""\n')
    for relative in (*FIXED_PROTECTED, *PILOT_ARTIFACTS):
        if not (root / relative).exists():
            _write(root, relative, f"conteúdo de {relative}\n")
    # Somente o roteiro do piloto é lido de verdade, pelo escalonador.
    _write_pilot_runs(root / "results/tables/pilot_runs.parquet")
    git(root, "init")
    git(root, "add", "-A")
    git(root, *GIT_IDENTITY, "commit", "-m", "escopo protegido de brinquedo")
    write_freeze_manifest(root)
    git(root, "add", "-A")
    git(root, *GIT_IDENTITY, "commit", "-m", "congelamento de brinquedo")
    return load_campaign(root / "experiments/configs/benchmark.toml", repository_root=root)


def _approved_sample(**changes: Any) -> dict[str, Any]:
    row = {
        "elapsed_seconds": 0.0,
        "cpu_percent": 100.0,
        "rss_bytes": 1_000,
        "descendant_rss_bytes": 500,
        "process_count": 2,
        "descendant_count": 1,
        "optimizer_process_count": 1,
        "max_optimizer_threads": 1,
        "active_optimizer_threads": 1,
        "max_active_threads_per_optimizer": 1,
        "max_optimizer_cpu_ratio": 1.0,
        "optimizer_pids": "101",
        "memory_total_bytes": 32 * 1024 ** 3,
        "memory_available_bytes": 16 * 1024 ** 3,
        "swap_total_bytes": 4 * 1024 ** 3,
        "swap_free_bytes": 4 * 1024 ** 3,
    }
    row.update(changes)
    return row


def write_approved_resource_summary(
    config, *, batch: int, round_name: str = "initial", workers: int = 16
) -> Path:
    """Fixa um resumo de recursos aprovado, montado de amostras sintéticas.

    O monitor real observa a árvore de processos do próprio pytest, e qualquer
    processo remanescente de um teste anterior reprova
    ``no_persistent_optimizers``. Esse critério é do ambiente e o seu acerto é
    coberto por ``tests/test_resource_monitor.py``; aqui o oráculo é a barreira,
    que precisa de um resumo aprovado e estável entre máquinas.
    """

    selection = select_benchmark(config, batch=batch)
    _, summary_path = resource_paths(config, selection, round_name=round_name)
    summary = summarize_samples(
        [_approved_sample(), _approved_sample(elapsed_seconds=1.0, optimizer_process_count=0)],
        workers=workers,
    )
    assert summary["passed"] is True
    atomic_write_json(summary_path, summary)
    return summary_path


def run_toy_batch(config, *, batch: int, workers: int = 4) -> None:
    """Executa um lote inteiro pelo caminho saturado, sem filtro de subgrupo."""

    execute_operation(
        config, select_benchmark(config, batch=batch),
        workers=workers, round_name="initial",
    )
    write_approved_resource_summary(config, batch=batch, workers=workers)
