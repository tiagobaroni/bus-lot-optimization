"""Worker isolado para uma única execução experimental."""

from __future__ import annotations

import os

for _thread_variable in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"
):
    os.environ[_thread_variable] = "1"

from pathlib import Path
import re
from typing import Any

from metaheuristica import (
    AcoConfig, ObjectiveWeights, PsoConfig, RunConfig, TabuConfig,
    load_artesp_instance, load_tiny_instance, run_aco, run_pso, run_tabu,
)
from metaheuristica.errors import ConfigurationError

from experiments.provenance import utc_now
from experiments.scenarios import Scenario, file_sha256


def _load_instance(path: Path):
    match = re.fullmatch(r"artesp_rmsp_(20|60|150)\.json", path.name)
    if match:
        return load_artesp_instance(path.parent, int(match.group(1)))
    return load_tiny_instance(path)


def run_scenario(scenario: Scenario, repository_root: str) -> dict[str, Any]:
    """Executa um cenário e devolve dados ainda não persistidos."""

    root = Path(repository_root)
    path = root / scenario.payload["instance"]["path"]
    if file_sha256(path) != scenario.payload["instance"]["sha256"]:
        raise ConfigurationError("arquivo da instância mudou depois da expansão")
    instance = _load_instance(path)
    weights = ObjectiveWeights(**scenario.payload["weights"])
    run_config = RunConfig(
        k=scenario.payload["k"], seed=scenario.payload["seed"],
        budget=scenario.payload["budget"], weights=weights,
        cache_enabled=scenario.payload["cache_enabled"],
    )
    algorithm = scenario.payload["algorithm"]
    parameters = scenario.payload["parameters"]
    started_at = utc_now()
    if algorithm == "tabu":
        result = run_tabu(instance, run_config, TabuConfig(**parameters))
    elif algorithm == "aco":
        result = run_aco(instance, run_config, AcoConfig(**parameters))
    elif algorithm == "pso":
        result = run_pso(instance, run_config, PsoConfig(**parameters))
    else:
        raise ConfigurationError(f"algoritmo desconhecido: {algorithm}")
    return {
        "result": result.to_dict(),
        "started_at": started_at,
        "finished_at": utc_now(),
        "thread_limits": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            )
        },
    }
