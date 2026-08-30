"""CLI integral da infraestrutura e da execução posterior da B11A."""

from __future__ import annotations

import os

THREAD_LIMIT_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "ARROW_NUM_THREADS",
)

# O ambiente recebido é capturado antes da escrita: relê-lo depois devolveria o
# que este bloco acabou de escrever e não documentaria configuração alguma.
INHERITED_THREAD_LIMITS: dict[str, str | None] = {
    variable: os.environ.get(variable) for variable in THREAD_LIMIT_VARIABLES
}

# A fixação precisa vir antes de qualquer importação de NumPy ou de
# `metaheuristica`, no mesmo padrão do ponto de entrada da CPU. O projeto `gpu/`
# não importa `experiments`, onde essa proteção vive, e `src/metaheuristica/`
# não tem bloco de ambiente, logo sem este bloco a garantia de uma thread
# computacional por execução simplesmente não existia deste lado.
for _thread_variable in THREAD_LIMIT_VARIABLES:
    os.environ[_thread_variable] = "1"

import argparse
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from metaheuristica import RunConfig, load_artesp_instance, load_tiny_instance

from metaheuristica_gpu.aco import run_aco_gpu
from metaheuristica_gpu.config import GpuCampaignConfig, GpuConfigError, load_gpu_config
from metaheuristica_gpu.environment import (
    GpuConfigurationError, file_sha256, gpu_code_hash, inspect_gpu_environment,
)
from metaheuristica_gpu.microbenchmark import run_microbenchmark
from metaheuristica_gpu.monitor import cooldown, monitor_process, preflight_idle
from metaheuristica_gpu.numerics import verify_batch
from metaheuristica_gpu.objective import GpuBatchObjective
from metaheuristica_gpu.pso import run_pso_gpu
from metaheuristica_gpu.scenarios import GpuScenario, canonical_json, expand_gpu_scenarios
from metaheuristica_gpu.storage import (
    GpuStorageError, atomic_write_json, is_complete, read_json, result_path, validate_result,
)
from metaheuristica_gpu.timing import warmup_gpu


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "gpu/configs/gpu_benchmark.toml"
MANIFEST = ROOT / "results/gpu/metadata/gpu_readiness_manifest.json"
CONFORMANCE = ROOT / "results/gpu/metadata/gpu_conformance.json"
SCHEDULE = ROOT / "results/gpu/metadata/gpu_execution_schedule.json"


def _git_clean() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip())
    return commit, dirty


def _instance(config: GpuCampaignConfig):
    if config.instance == "tiny_manual":
        return load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    return load_artesp_instance(ROOT / "data/instances", config.instance_size)


def _scenario(config: GpuCampaignConfig, identifier: str) -> GpuScenario:
    matches = [item for item in expand_gpu_scenarios(config) if item.scenario_id.startswith(identifier)]
    if len(matches) != 1:
        raise GpuConfigError("scenario-id GPU inexistente ou ambíguo")
    return matches[0]


def _cpu_readiness() -> dict[str, Any]:
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "experiments.run_benchmark", "readiness"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if completed.returncode != 0:
        raise GpuConfigurationError(f"readiness CPU falhou: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def _b11_complete() -> bool:
    path = ROOT / "results/tables/benchmark_manifest.json"
    return path.is_file() and read_json(path).get("complete") is True and read_json(path).get("official") is True


def _protected_hashes(config: GpuCampaignConfig) -> dict[str, str]:
    files = [
        ROOT / "gpu/uv.lock",
        ROOT / "gpu/configs/gpu_benchmark.toml",
        ROOT / "gpu/configs/gpu_diagnostic.toml",
        CONFORMANCE,
        SCHEDULE,
    ]
    return {str(path.relative_to(ROOT)): file_sha256(path) for path in files}


@contextmanager
def _exclusive_gpu():
    path = ROOT / "results/gpu/operational/gpu.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GpuConfigurationError("já existe uma execução GPU ativa") from error
        yield


def schedule_document(config: GpuCampaignConfig) -> dict[str, Any]:
    scenarios = expand_gpu_scenarios(config)
    return {
        "schema_version": 1, "campaign": config.name, "sequential": True,
        "scenarios": [{"rank": index, "scenario_id": item.scenario_id, **item.payload}
                      for index, item in enumerate(scenarios, start=1)],
    }


def run_conformance(config: GpuCampaignConfig) -> dict[str, Any]:
    environment = inspect_gpu_environment()
    maximum = 0.0; cases = []
    for size in (20, 60, 150):
        instance = load_artesp_instance(ROOT / "data/instances", size)
        k = 5
        solutions = np.stack([np.roll(np.arange(size, dtype=np.int64) % k, shift) for shift in range(2)])
        with GpuBatchObjective(instance, k=k) as objective:
            results = objective.evaluate(solutions)
        difference = verify_batch(instance, solutions, results, k=k, weights=config.weights)
        maximum = max(maximum, difference); cases.append({"instance": size, "difference": difference})
    tiny = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    run = RunConfig(k=2, seed=0, budget=100)
    aco = run_aco_gpu(tiny, run, config.aco, verify_every_batch=True)
    pso = run_pso_gpu(tiny, run, config.pso, verify_every_batch=True)
    report = {
        "schema_version": 1, "passed": True, "environment": environment.to_dict(),
        "maximum_difference": maximum, "cases": cases,
        "aco": aco.reproducible_data(), "pso": pso.reproducible_data(),
    }
    atomic_write_json(CONFORMANCE, report); return report


def generate_manifest(config: GpuCampaignConfig) -> dict[str, Any]:
    if not CONFORMANCE.is_file() or read_json(CONFORMANCE).get("passed") is not True:
        raise GpuConfigurationError("conformidade GPU ainda não aprovada")
    atomic_write_json(SCHEDULE, schedule_document(config))
    commit, dirty = _git_clean()
    manifest = {
        "schema_version": 1, "gpu_code_sha256": gpu_code_hash(ROOT),
        "protected_files": _protected_hashes(config), "scenario_count": 60,
        "scenario_ids_sha256": sha256(canonical_json(sorted(
            item.scenario_id for item in expand_gpu_scenarios(config)
        ))).hexdigest(), "created_from_commit": commit, "created_with_dirty_tree": dirty,
    }
    atomic_write_json(MANIFEST, manifest); return manifest


def verify_manifest(config: GpuCampaignConfig) -> dict[str, Any]:
    manifest = read_json(MANIFEST)
    if manifest.get("gpu_code_sha256") != gpu_code_hash(ROOT):
        raise GpuConfigurationError("código GPU diverge do manifesto")
    if manifest.get("protected_files") != _protected_hashes(config):
        raise GpuConfigurationError("arquivo GPU protegido diverge do manifesto")
    return manifest


def readiness(config: GpuCampaignConfig) -> dict[str, Any]:
    environment = inspect_gpu_environment(); manifest = verify_manifest(config)
    cpu = _cpu_readiness(); commit, dirty = _git_clean()
    if dirty:
        raise GpuConfigurationError("readiness GPU exige worktree limpa")
    scenarios = expand_gpu_scenarios(config)
    output = ROOT / config.output_root
    existing = sum(is_complete(output, item) for item in scenarios)
    return {
        "schema_version": 1, "infrastructure_ready": True,
        "execution_ready": _b11_complete(), "waiting_for_b11e": not _b11_complete(),
        "scenario_count": len(scenarios), "existing_official_results": existing,
        "gpu": environment.to_dict(), "cpu_readiness": cpu["ready"],
        "gpu_manifest_schema": manifest["schema_version"], "git_commit": commit,
        "git_dirty": dirty,
    }


def execute_scenario(config: GpuCampaignConfig, scenario: GpuScenario) -> dict[str, Any]:
    if not _b11_complete():
        raise GpuConfigurationError("B11-E ainda não foi concluída")
    _cpu_readiness(); verify_manifest(config)
    _, dirty = _git_clean()
    if dirty:
        raise GpuConfigurationError("execução GPU oficial exige worktree limpa")
    output = ROOT / config.output_root
    if is_complete(output, scenario):
        return read_json(result_path(output, scenario))
    session_path = output / "sessions" / f"{scenario.scenario_id}.json"
    with _exclusive_gpu():
        atomic_write_json(session_path, {"scenario_id": scenario.scenario_id, "status": "preflight"})
        try:
            preflight_idle()
            environment = inspect_gpu_environment(); cold_start = perf_counter(); warmup = warmup_gpu()
            instance = _instance(config)
            run_config = RunConfig(k=config.k, seed=int(scenario.payload["seed"]), budget=config.budget)
            monitor_path = output / "telemetry" / f"{scenario.scenario_id}.csv"
            atomic_write_json(session_path, {"scenario_id": scenario.scenario_id, "status": "running"})
            # O monitor passa a viver em processo próprio, como o
            # ResourceMonitor da CPU já faz, com o processo medido isolado dos
            # dois `nvidia-smi` por segundo. O canal de parada é explícito, para
            # que uma falha de segurança derrube a execução com a mesma latência
            # de antes, de um intervalo de amostragem.
            with monitor_process(monitor_path, interval_seconds=1.0) as safety:
                if scenario.payload["algorithm"] == "aco":
                    result = run_aco_gpu(instance, run_config, config.aco, guard=safety.guard)
                else:
                    result = run_pso_gpu(instance, run_config, config.pso, guard=safety.guard)
            safety.raise_if_unsafe()
            cooldown()
        except Exception as error:
            atomic_write_json(session_path, {
                "scenario_id": scenario.scenario_id,
                "status": "interrupted" if isinstance(error, RuntimeError) else "failed",
                "error_type": type(error).__name__, "message": str(error),
            })
            raise
    document = {
        "schema_version": 1, "scenario_id": scenario.scenario_id,
        "scenario": scenario.payload, "result": result.to_dict(),
        "environment": environment.to_dict(), "warmup": warmup,
        "cold_total_seconds": perf_counter() - cold_start,
        "telemetry": str(monitor_path.relative_to(ROOT)),
    }
    validate_result(document, scenario); atomic_write_json(result_path(output, scenario), document)
    atomic_write_json(session_path, {"scenario_id": scenario.scenario_id, "status": "complete"})
    return document


def consolidate(config: GpuCampaignConfig) -> dict[str, Any]:
    scenarios = expand_gpu_scenarios(config); output = ROOT / config.output_root
    documents = []
    for scenario in scenarios:
        if not is_complete(output, scenario):
            raise GpuStorageError("campanha GPU incompleta")
        documents.append(read_json(result_path(output, scenario)))
    rows = [{
        "scenario_id": doc["scenario_id"], "algorithm": doc["scenario"]["algorithm"],
        "instance": doc["scenario"]["instance"], "k": doc["scenario"]["k"],
        "seed": doc["scenario"]["seed"], "gpu_runtime_seconds": doc["result"]["runtime_seconds"],
        "total_cost": doc["result"]["evaluation"]["total_cost"],
    } for doc in documents]
    frame = pd.DataFrame(rows).sort_values(["algorithm", "seed"])
    cpu_path = ROOT / "results/tables/benchmark_runs.parquet"
    if not cpu_path.is_file():
        raise GpuStorageError("tabela oficial CPU ausente")
    cpu = pd.read_parquet(cpu_path)
    cpu = cpu[(cpu["instance"] == config.instance) & (cpu["k"] == config.k) &
              cpu["algorithm"].isin(config.algorithms) & cpu["seed"].isin(config.seeds)]
    cpu = cpu[["algorithm", "instance", "k", "seed", "runtime_seconds"]].rename(
        columns={"runtime_seconds": "cpu_runtime_seconds"}
    )
    paired = frame.merge(cpu, on=["algorithm", "instance", "k", "seed"], validate="one_to_one")
    if len(paired) != 60:
        raise GpuStorageError("pareamento CPU x GPU incompleto")
    paired["speedup"] = paired["cpu_runtime_seconds"] / paired["gpu_runtime_seconds"]
    table = output / "tables/gpu_runs.parquet"; table.parent.mkdir(parents=True, exist_ok=True)
    paired.to_parquet(table, index=False)
    summary = paired.groupby("algorithm", as_index=False)["speedup"].agg(["count", "median", "mean", "min", "max"])
    summary_path = output / "tables/gpu_speedup_summary.parquet"
    summary.to_parquet(summary_path, index=False)
    report = {"schema_version": 1, "complete": True, "completed": 60,
              "runs_sha256": file_sha256(table), "summary_sha256": file_sha256(summary_path)}
    atomic_write_json(output / "tables/gpu_manifest.json", report); return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Experimento adicional GPU B11A")
    parser.add_argument("operation", choices=("readiness", "plan", "conformance", "microbenchmark", "freeze", "execute", "resume", "validate", "consolidate"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenario-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = load_gpu_config(arguments.config)
        if arguments.operation == "readiness": output = readiness(config)
        elif arguments.operation == "plan":
            scenarios = expand_gpu_scenarios(config)
            output = {"campaign": config.name, "scenarios": len(scenarios), "completed": sum(is_complete(ROOT / config.output_root, item) for item in scenarios)}
        elif arguments.operation == "conformance": output = run_conformance(config)
        elif arguments.operation == "microbenchmark":
            instance = load_artesp_instance(ROOT / "data/instances", 150)
            solutions = np.stack([np.roll(np.arange(150, dtype=np.int64) % 5, shift) for shift in range(40)])
            output = run_microbenchmark(instance, solutions, k=5)
        elif arguments.operation == "freeze": output = generate_manifest(config)
        elif arguments.operation in {"execute", "resume"}:
            if not arguments.scenario_id: raise GpuConfigError("execução exige --scenario-id")
            output = execute_scenario(config, _scenario(config, arguments.scenario_id))
        elif arguments.operation == "validate":
            if not arguments.scenario_id: raise GpuConfigError("validação exige --scenario-id")
            scenario = _scenario(config, arguments.scenario_id); path = result_path(ROOT / config.output_root, scenario)
            validate_result(read_json(path), scenario); output = {"valid": True, "scenario_id": scenario.scenario_id}
        else: output = consolidate(config)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True)); return 0
    except (GpuConfigError, GpuConfigurationError, GpuStorageError, RuntimeError) as error:
        print(f"erro: {error}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
