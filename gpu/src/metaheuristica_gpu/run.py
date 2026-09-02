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

from metaheuristica import (
    RunConfig, load_artesp_instance, load_tiny_instance, run_aco, run_pso,
)

from metaheuristica_gpu.aco import run_aco_gpu
from metaheuristica_gpu.config import GpuCampaignConfig, GpuConfigError, load_gpu_config
from metaheuristica_gpu.environment import (
    GpuConfigurationError, file_sha256, gpu_code_hash, inspect_gpu_environment,
)
from metaheuristica_gpu.microbenchmark import run_microbenchmark
from metaheuristica_gpu.monitor import cooldown, monitor_process, preflight_idle
from metaheuristica_gpu.numerics import (
    ABS_TOL, require_equivalent_trajectory, verify_batch,
)
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

# F8-1, componente `M2`. O par de conformidade em **modo oficial**, isto é com
# `verify_every_batch` no padrão `False`, roda sobre instância real. Com
# `tiny_manual` e `K=2` o custo é exatamente zero em 99 dos 100 checkpoints do
# ACO e em 98 dos 100 do PSO, de modo que a trajetória não é exercitada e a
# igualdade passaria por vacuidade.
CONFORMANCE_TRAJECTORY_SIZE = 20
CONFORMANCE_TRAJECTORY_K = 5
CONFORMANCE_TRAJECTORY_SEED = 10
CONFORMANCE_TRAJECTORY_BUDGET = 400

# F8-5. Os campos abaixo são publicados em todo documento de cenário e valem
# zero por **desenho**, não por medição. A declaração viaja junto do resultado
# para que quem audite os JSON leia a condição no mesmo lugar em que lê o
# valor, em vez de precisar reconstruí-la do código.
DIAGNOSTICS_SCHEMA: dict[str, Any] = {
    "schema_version": 1,
    "conditional_fields": {
        "result.diagnostics.max_numerical_difference": {
            "condition": "verify_every_batch",
            "value_without_condition": 0.0,
            "meaning": (
                "maior divergência entre GPU e CPU observada na verificação "
                "lote a lote; a execução oficial usa verify_every_batch=False, "
                "logo o campo é estruturalmente 0.0 e NÃO significa ausência "
                "de divergência. A divergência real do modo oficial é de 1 ulp "
                "por avaliação, conforme a conformidade registrada em "
                "gpu_conformance.json."
            ),
        },
        "result.diagnostics.gpu_timing.arbitration_cpu_seconds": {
            "condition": None,
            "value_without_condition": 0.0,
            "meaning": (
                "tempo de arbitragem CPU de quase empates; o único sítio que o "
                "incrementava era `arbitrate_best`, removida por não ter "
                "chamador algum, logo o campo é sempre 0.0. A arbitragem que a "
                "seção 29.1 exige é executada pelo código normativo "
                "compartilhado, no ConvergenceRecorder."
            ),
        },
    },
}


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


def _configuration_identity(config: GpuCampaignConfig) -> dict[str, str]:
    """Identifica a configuração e o conjunto de cenários que ela expande."""

    identifiers = sorted(item.scenario_id for item in expand_gpu_scenarios(config))
    return {
        "config_sha256": file_sha256(config.source_path),
        "scenario_ids_sha256": sha256(canonical_json(identifiers)).hexdigest(),
    }


def _cpu_reference(config: GpuCampaignConfig) -> dict[str, Any]:
    """Valida os 60 pares oficiais da B11-E usados pela campanha GPU."""

    manifest_path = ROOT / "results/tables/benchmark_manifest.json"
    runs_path = ROOT / "results/tables/benchmark_runs.parquet"
    if not manifest_path.is_file() or not runs_path.is_file():
        raise GpuConfigurationError("consolidação oficial da B11-E ausente")
    manifest = read_json(manifest_path)
    required = {
        "complete": True, "official": True, "completed": 1620,
        "expected": 1620, "failed_records": 0, "missing": 0,
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise GpuConfigurationError("manifesto da B11-E não está completo e oficial")
    runs = manifest.get("runs")
    if not isinstance(runs, dict) or runs.get("path") != "results/tables/benchmark_runs.parquet":
        raise GpuConfigurationError("manifesto da B11-E referencia tabela CPU inválida")
    if runs.get("sha256") != file_sha256(runs_path):
        raise GpuConfigurationError("tabela CPU diverge do manifesto da B11-E")

    frame = pd.read_parquet(runs_path)
    keys = ["algorithm", "instance", "k", "seed"]
    required_columns = {*keys, "official", "parameters_json"}
    if not required_columns.issubset(frame.columns):
        raise GpuConfigurationError("tabela CPU não contém o contrato de pareamento")
    paired = frame[
        frame["algorithm"].isin(config.algorithms)
        & (frame["instance"] == config.instance)
        & (frame["k"] == config.k)
        & frame["seed"].isin(config.seeds)
    ]
    if len(paired) != 60 or paired.duplicated(keys).any():
        raise GpuConfigurationError("pareamento CPU da B11A-E não contém 60 linhas únicas")
    expected = {
        (algorithm, config.instance, config.k, seed)
        for algorithm in config.algorithms for seed in config.seeds
    }
    observed = set(paired[keys].itertuples(index=False, name=None))
    if observed != expected or not paired["official"].eq(True).all():
        raise GpuConfigurationError("pareamento CPU da B11A-E está incompleto ou não oficial")
    expected_parameters = {
        "aco": {name: getattr(config.aco, name) for name in config.aco.__dataclass_fields__},
        "pso": {name: getattr(config.pso, name) for name in config.pso.__dataclass_fields__},
    }
    for row in paired[["algorithm", "parameters_json"]].itertuples(index=False):
        if json.loads(row.parameters_json) != expected_parameters[row.algorithm]:
            raise GpuConfigurationError(
                f"parâmetros CPU de {row.algorithm} divergem da campanha GPU"
            )
    return {
        "complete": True,
        "official": True,
        "paired_scenarios": len(paired),
        "runs_sha256": runs["sha256"],
    }


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


def conformance_trajectories(config: GpuCampaignConfig) -> list[dict[str, Any]]:
    """Assevera a equivalência de trajetória em modo oficial, e não só a registra.

    F8-1, componente `M2`. `run_conformance` apenas **registrava**
    `reproducible_data()` das duas execuções pareadas e não **afirmava** nada;
    e as duas rodavam com `verify_every_batch=True`, modo em que
    `HybridEvaluator.evaluate_batch` substitui os resultados da GPU pelos
    normativos, de modo que qualquer comparação ali é CPU contra CPU. O par
    abaixo roda em **modo oficial**, que é o caminho que os 60 cenários
    executam, sobre **instância real**, e a comparação é asseverada por
    `require_equivalent_trajectory`, com a régua normativa de `1e-12`.

    A divergência esperada é conforme, e não defeito: medida em
    `artesp_rmsp_20`, `K=5`, semente 10 e orçamento 400, os cem checkpoints
    diferem bit a bit dos da CPU já a partir do checkpoint 1, com
    `max |delta|` de `2,220e-16`, isto é 1/4503 do `abs_tol` normativo, com
    solução final idêntica rótulo a rótulo nos dois algoritmos.
    """

    instance = load_artesp_instance(ROOT / "data/instances", CONFORMANCE_TRAJECTORY_SIZE)
    run = RunConfig(
        k=CONFORMANCE_TRAJECTORY_K,
        seed=CONFORMANCE_TRAJECTORY_SEED,
        budget=CONFORMANCE_TRAJECTORY_BUDGET,
    )
    pairs = (
        ("aco", run_aco_gpu, run_aco, config.aco),
        ("pso", run_pso_gpu, run_pso, config.pso),
    )
    trajectories = []
    for algorithm, on_gpu, on_cpu, algorithm_config in pairs:
        gpu = on_gpu(instance, run, algorithm_config)
        cpu = on_cpu(instance, run, algorithm_config)
        difference = require_equivalent_trajectory(gpu, cpu)
        trajectories.append({
            "algorithm": algorithm, "instance": CONFORMANCE_TRAJECTORY_SIZE,
            "k": run.k, "seed": run.seed, "budget": run.budget,
            "verify_every_batch": False, "checkpoints": len(gpu.checkpoints),
            "maximum_difference": difference, "tolerance": ABS_TOL,
        })
    return trajectories


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
    trajectories = conformance_trajectories(config)
    maximum = max(maximum, *(item["maximum_difference"] for item in trajectories))
    report = {
        "schema_version": 1, "passed": True, "environment": environment.to_dict(),
        "configuration": _configuration_identity(config),
        "maximum_difference": maximum, "cases": cases,
        "trajectories": trajectories,
        "aco": aco.reproducible_data(), "pso": pso.reproducible_data(),
    }
    atomic_write_json(CONFORMANCE, report); return report


def generate_manifest(config: GpuCampaignConfig) -> dict[str, Any]:
    if not CONFORMANCE.is_file():
        raise GpuConfigurationError("conformidade GPU ainda não aprovada")
    conformance = read_json(CONFORMANCE)
    if conformance.get("passed") is not True:
        raise GpuConfigurationError("conformidade GPU ainda não aprovada")
    if conformance.get("configuration") != _configuration_identity(config):
        raise GpuConfigurationError("conformidade GPU pertence a configuração obsoleta")
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
    identity = _configuration_identity(config)
    if manifest.get("scenario_ids_sha256") != identity["scenario_ids_sha256"]:
        raise GpuConfigurationError("IDs GPU divergem do manifesto")
    if canonical_json(read_json(SCHEDULE)) != canonical_json(schedule_document(config)):
        raise GpuConfigurationError("roteiro GPU diverge da configuração")
    conformance = read_json(CONFORMANCE)
    if conformance.get("passed") is not True or conformance.get("configuration") != identity:
        raise GpuConfigurationError("conformidade GPU diverge da configuração")
    return manifest


def readiness(config: GpuCampaignConfig) -> dict[str, Any]:
    environment = inspect_gpu_environment(); manifest = verify_manifest(config)
    cpu = _cpu_readiness(); reference = _cpu_reference(config); commit, dirty = _git_clean()
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
        "cpu_reference": reference,
        "gpu_manifest_schema": manifest["schema_version"], "git_commit": commit,
        "git_dirty": dirty,
    }


def scenario_document(
    scenario: GpuScenario,
    result: Any,
    environment: Any,
    warmup: dict[str, float],
    *,
    cold_total_seconds: float,
    telemetry: str,
) -> dict[str, Any]:
    """Monta o documento oficial de um cenário.

    Extraído de `execute_scenario` para que o conteúdo do documento seja
    testável sem exigir a campanha da CPU concluída, exclusividade da placa e
    os 60 artefatos: `execute_scenario` recusa antes de qualquer computação
    quando `_b11_complete()` é falso, que é o estado de hoje.
    """

    return {
        "schema_version": 1, "scenario_id": scenario.scenario_id,
        "scenario": scenario.payload, "result": result.to_dict(),
        "environment": environment.to_dict(), "warmup": warmup,
        "cold_total_seconds": cold_total_seconds,
        "telemetry": telemetry,
        # F8-5: a condição viaja junto do valor, e não só no código.
        "diagnostics_schema": DIAGNOSTICS_SCHEMA,
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
    document = scenario_document(
        scenario, result, environment, warmup,
        cold_total_seconds=perf_counter() - cold_start,
        telemetry=str(monitor_path.relative_to(ROOT)),
    )
    validate_result(document, scenario); atomic_write_json(result_path(output, scenario), document)
    atomic_write_json(session_path, {"scenario_id": scenario.scenario_id, "status": "complete"})
    return document


def device_fraction(gpu_timing: dict[str, Any], runtime_seconds: float) -> float:
    """Fração do tempo oficial que de fato ocorreu no dispositivo.

    F8-5, item B3 do Apêndice B do registro. `consolidate` publicava `speedup`
    e descartava `diagnostics.gpu_timing` ao montar `gpu_runs.parquet`, de modo
    que a tabela oficial trazia o ganho sem a grandeza que o interpreta: um
    `speedup` de 1,35 com 0,09% de dispositivo e um de 1,35 com 16% são
    afirmações muito diferentes sobre o que foi acelerado, e a tabela não as
    distinguia. **Este item não passou por verificação adversarial e entra como
    recomendação, e não como achado.**

    O numerador é o tempo das três fases do dispositivo, transferência de ida,
    kernel e transferência de volta, e o denominador é o tempo oficial do
    cenário, que é o mesmo que entra no `speedup`.
    """

    if not isinstance(runtime_seconds, (int, float)) or runtime_seconds <= 0.0:
        raise GpuStorageError("tempo oficial GPU não positivo ao derivar device_fraction")
    on_device = 0.0
    for phase in ("host_to_device_seconds", "kernel_seconds", "device_to_host_seconds"):
        value = gpu_timing.get(phase)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0.0:
            raise GpuStorageError(f"gpu_timing sem a fase {phase}")
        on_device += float(value)
    return on_device / float(runtime_seconds)


def consolidated_row(document: dict[str, Any]) -> dict[str, Any]:
    """Linha de `gpu_runs.parquet` derivada de um documento de cenário.

    Extraída de `consolidate` pelo mesmo motivo que `scenario_document`: rodar
    `consolidate` exige os 60 documentos completos e a tabela oficial da CPU, e
    hoje ela recusa antes de montar linha alguma.
    """

    return {
        "scenario_id": document["scenario_id"],
        "algorithm": document["scenario"]["algorithm"],
        "instance": document["scenario"]["instance"],
        "k": document["scenario"]["k"],
        "seed": document["scenario"]["seed"],
        "gpu_runtime_seconds": document["result"]["runtime_seconds"],
        "total_cost": document["result"]["evaluation"]["total_cost"],
        # F8-5: a fração de dispositivo acompanha o `speedup` na mesma linha, em
        # vez de o `gpu_timing` que a produz ser descartado aqui.
        "device_fraction": device_fraction(
            document["result"]["diagnostics"]["gpu_timing"],
            document["result"]["runtime_seconds"],
        ),
    }


def consolidate(config: GpuCampaignConfig) -> dict[str, Any]:
    scenarios = expand_gpu_scenarios(config); output = ROOT / config.output_root
    documents = []
    for scenario in scenarios:
        if not is_complete(output, scenario):
            raise GpuStorageError("campanha GPU incompleta")
        documents.append(read_json(result_path(output, scenario)))
    rows = [consolidated_row(doc) for doc in documents]
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
