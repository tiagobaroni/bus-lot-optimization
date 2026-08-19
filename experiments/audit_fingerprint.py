"""Impressão digital determinística do caminho científico, para a auditoria B11B."""

from __future__ import annotations

import os

for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "ARROW_NUM_THREADS",
):
    os.environ.setdefault(_thread_variable, "1")

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

from metaheuristica import (
    AcoConfig,
    PsoConfig,
    RunConfig,
    TabuConfig,
    load_artesp_instance,
    load_tiny_instance,
    run_aco,
    run_greedy,
    run_pso,
    run_tabu,
)


SCHEMA_VERSION = 1
FINGERPRINT_SEED = 20260819
ARTESP_SIZES = (20, 60, 150)
K_VALUES = (3, 5, 8)
TINY_INSTANCE = "tiny_manual"
TINY_K = 2
TINY_BUDGET = 101
BUDGETS = {"tabu": 25_007, "aco": 4_007, "pso": 4_007}
STOCHASTIC = ("tabu", "aco", "pso")
BASELINE_PATH = Path("results/audit/fingerprint_baseline.json")

# Segundos colocados do tuning oficial, lidos de results/tables/tuning_summary.parquet
# na linha rank igual a 2 de cada algoritmo. Cada um difere do vencedor em
# exatamente um parâmetro, o que faz destes três cenários sondas de eixo único.
# A conferência contra o Parquet é feita por teste, para que divergência apareça
# como falha e não seja absorvida em silêncio.
RUNNER_UP = {
    "tabu": {"tabu_tenure": 20, "neighborhood_size": 20, "stagnation_limit": 100},
    "aco": {"alpha": 1.0, "beta": 1.0, "rho": 0.1, "n_ants": 40},
    "pso": {"n_particles": 20, "inertia": 0.4, "cognitive": 2.0, "social": 1.5},
}
RUNNER_UP_INSTANCE = "artesp_rmsp_60"
RUNNER_UP_K = 5


@dataclass(frozen=True, slots=True)
class FingerprintScenario:
    """Cenário determinístico da impressão digital."""

    algorithm: str
    instance: str
    k: int
    budget: int | None
    variant: str = "frozen"

    @property
    def scenario_id(self) -> str:
        return f"{self.algorithm}:{self.instance}:{self.k}:{self.variant}"


def scenarios() -> tuple[FingerprintScenario, ...]:
    """Expande os 42 cenários fixos da impressão digital."""

    expanded: list[FingerprintScenario] = []
    for algorithm in STOCHASTIC:
        for size in ARTESP_SIZES:
            for k in K_VALUES:
                expanded.append(
                    FingerprintScenario(
                        algorithm=algorithm,
                        instance=f"artesp_rmsp_{size}",
                        k=k,
                        budget=BUDGETS[algorithm],
                    )
                )
        expanded.append(
            FingerprintScenario(
                algorithm=algorithm,
                instance=TINY_INSTANCE,
                k=TINY_K,
                budget=TINY_BUDGET,
            )
        )
        expanded.append(
            FingerprintScenario(
                algorithm=algorithm,
                instance=RUNNER_UP_INSTANCE,
                k=RUNNER_UP_K,
                budget=BUDGETS[algorithm],
                variant="runner_up",
            )
        )
    for size in ARTESP_SIZES:
        for k in K_VALUES:
            expanded.append(
                FingerprintScenario(
                    algorithm="greedy",
                    instance=f"artesp_rmsp_{size}",
                    k=k,
                    budget=None,
                )
            )
    return tuple(expanded)


def _frozen_parameters(root: Path) -> dict[str, dict[str, Any]]:
    with (root / "experiments/configs/frozen_parameters.toml").open("rb") as stream:
        return tomllib.load(stream)


def _load_instance(root: Path, name: str):
    if name == TINY_INSTANCE:
        return load_tiny_instance(root / "data/instances/tiny_manual.json")
    return load_artesp_instance(root / "data/instances", int(name.rsplit("_", 1)[1]))


def _evaluation_payload(evaluation: Any) -> dict[str, float]:
    return {
        "total_cost": evaluation.total_cost,
        "c_demand": evaluation.c_demand,
        "c_production": evaluation.c_production,
        "c_territorial": evaluation.c_territorial,
        "c_affinity": evaluation.c_affinity,
        "cv_demand": evaluation.cv_demand,
        "cv_production": evaluation.cv_production,
    }


def _greedy_payload(result: Any) -> dict[str, Any]:
    return {
        "algorithm": "greedy",
        "k": result.k,
        "solution": [int(label) for label in result.solution],
        "evaluation": _evaluation_payload(result.evaluation),
        "evaluations": result.evaluations,
        "processing_order": list(result.processing_order),
        "trace": [
            {
                "unit_id": step.unit_id,
                "unit_index": step.unit_index,
                "lot": step.lot,
                "partial_cost": step.partial_cost,
                "evaluations": step.evaluations,
            }
            for step in result.trace
        ],
        "fingerprint_variant": "frozen",
    }


def run_scenario(root: Path, scenario: FingerprintScenario) -> tuple[str, dict[str, Any]]:
    """Executa um cenário e devolve seu payload determinístico."""

    instance = _load_instance(root, scenario.instance)
    if scenario.algorithm == "greedy":
        return scenario.scenario_id, _greedy_payload(run_greedy(instance, k=scenario.k))
    if scenario.variant == "runner_up":
        parameters = dict(RUNNER_UP[scenario.algorithm])
    else:
        parameters = dict(_frozen_parameters(root)[scenario.algorithm])
    assert scenario.budget is not None
    run_config = RunConfig(k=scenario.k, seed=FINGERPRINT_SEED, budget=scenario.budget)
    if scenario.algorithm == "tabu":
        result = run_tabu(instance, run_config, TabuConfig(**parameters))
    elif scenario.algorithm == "aco":
        result = run_aco(instance, run_config, AcoConfig(**parameters))
    else:
        result = run_pso(instance, run_config, PsoConfig(**parameters))
    payload = result.reproducible_data()
    payload["fingerprint_variant"] = scenario.variant
    payload["fingerprint_parameters"] = dict(sorted(parameters.items()))
    return scenario.scenario_id, payload


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(document: dict[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "content_sha256"}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def generate(
    root: Path,
    *,
    workers: int = 16,
    only: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Executa os cenários selecionados e monta o documento da impressão digital."""

    selected = [
        scenario
        for scenario in scenarios()
        if only is None or scenario.scenario_id in only
    ]
    if not selected:
        raise ValueError("nenhum cenário selecionado")
    entries: dict[str, dict[str, Any]] = {}
    if workers <= 1:
        for scenario in selected:
            identifier, payload = run_scenario(root, scenario)
            entries[identifier] = payload
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for identifier, payload in pool.map(
                run_scenario, [root] * len(selected), selected
            ):
                entries[identifier] = payload
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "seed": FINGERPRINT_SEED,
        "budgets": {**dict(sorted(BUDGETS.items())), "tiny": TINY_BUDGET},
        "scenarios": dict(sorted(entries.items())),
    }
    document["content_sha256"] = _content_hash(document)
    return document


def compare(baseline: Any, current: Any) -> list[str]:
    """Compara dois documentos exatamente e devolve as diferenças encontradas."""

    differences: list[str] = []
    _walk("", baseline, current, differences)
    return differences


def _walk(path: str, left: Any, right: Any, differences: list[str]) -> None:
    if type(left) is not type(right):
        differences.append(
            f"{path}: tipo {type(left).__name__} contra {type(right).__name__}"
        )
        return
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else key
            if key not in left:
                differences.append(f"{child}: ausente na linha de base")
            elif key not in right:
                differences.append(f"{child}: ausente no documento atual")
            else:
                _walk(child, left[key], right[key], differences)
        return
    if isinstance(left, list):
        if len(left) != len(right):
            differences.append(f"{path}: tamanho {len(left)} contra {len(right)}")
            return
        for index, (item_left, item_right) in enumerate(zip(left, right)):
            _walk(f"{path}[{index}]", item_left, item_right, differences)
        return
    if isinstance(left, float):
        if left.hex() != right.hex():
            differences.append(f"{path}: {left!r} contra {right!r}")
        return
    if left != right:
        differences.append(f"{path}: {left!r} contra {right!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera ou compara a impressão digital da auditoria B11B"
    )
    parser.add_argument("operation", choices=("generate", "compare"))
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="restringe a cenários informados; repetível. Em compare, apenas os "
        "cenários informados são conferidos, o que serve a verificações "
        "intermediárias por arquivo refatorado.",
    )
    arguments = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    only = tuple(arguments.only) if arguments.only else None
    if only is not None and arguments.operation == "generate":
        parser.error("generate exige o conjunto completo; --only vale só em compare")
    document = generate(root, workers=arguments.workers, only=only)
    baseline_path = root / arguments.baseline
    if arguments.operation == "generate":
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(document["content_sha256"])
        return 0
    with baseline_path.open(encoding="utf-8") as stream:
        baseline = json.load(stream)
    if only is not None:
        # Sem esta restrição, comparar um subconjunto acusaria como diferença todos
        # os cenários que a linha de base tem e o documento atual não executou.
        baseline = dict(baseline)
        baseline["scenarios"] = {
            key: value
            for key, value in baseline["scenarios"].items()
            if key in set(only)
        }
        faltantes = set(only) - set(baseline["scenarios"])
        if faltantes:
            print(f"cenários ausentes da linha de base: {sorted(faltantes)}", file=sys.stderr)
            return 2
        baseline.pop("content_sha256", None)
        document = dict(document)
        document.pop("content_sha256", None)
    differences = compare(baseline, document)
    if not differences:
        print("impressão digital idêntica")
        return 0
    for difference in differences:
        print(difference, file=sys.stderr)
    print(f"{len(differences)} diferenças", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
