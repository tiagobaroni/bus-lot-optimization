"""Worker isolado para uma única execução experimental."""

from __future__ import annotations

import os

from experiments import INHERITED_THREAD_LIMITS, THREAD_LIMIT_VARIABLES

# A escrita já ocorreu na importação de `experiments`, que é obrigatoriamente
# anterior a este módulo; repeti-la aqui é redundante e barato, e serve de
# defesa caso a ordem de importação mude.
for _thread_variable in THREAD_LIMIT_VARIABLES:
    os.environ[_thread_variable] = "1"

from pathlib import Path
import re
from typing import Any

import pyarrow as pa

# Estas duas chamadas, e não `ARROW_NUM_THREADS`, são o que efetivamente contém
# o Arrow, junto de `OMP_NUM_THREADS`.
pa.set_cpu_count(1)
pa.set_io_thread_count(1)

from metaheuristica import (
    AcoConfig, ObjectiveWeights, PsoConfig, RunConfig, TabuConfig,
    load_artesp_instance, load_tiny_instance, run_aco, run_pso, run_tabu,
)
from metaheuristica.errors import ConfigurationError

from experiments.provenance import utc_now
from experiments.scenarios import Scenario, file_sha256


def observed_thread_state() -> dict[str, Any]:
    """Mede o processo em vez de reler o que ele próprio declarou.

    O registro de `thread_limits` lê as sete variáveis do mesmo `os.environ` em
    que acabou de escrevê-las, logo é verdadeiro por construção e não pode
    falhar. O que segue é observação: quantas threads existem, quantas
    acumularam tempo de CPU e em quantas o Arrow diz que pode trabalhar.
    """

    tasks = Path("/proc/self/task")
    total: int | None = None
    with_ticks: int | None = None
    if tasks.is_dir():
        total = 0
        with_ticks = 0
        for task in sorted(tasks.iterdir()):
            if not task.name.isdigit():
                continue
            try:
                stat = (task / "stat").read_text(encoding="utf-8")
            except OSError:
                continue
            fields = stat[stat.rfind(")") + 2:].split()
            total += 1
            if int(fields[11]) + int(fields[12]) > 0:
                with_ticks += 1
    return {
        "threads_total": total,
        "threads_with_ticks": with_ticks,
        "arrow_cpu_count": pa.cpu_count(),
        "arrow_io_thread_count": pa.io_thread_count(),
    }


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
        # Declarado: o que este processo escreveu e relê.
        "thread_limits": {
            name: os.environ.get(name) for name in THREAD_LIMIT_VARIABLES
        },
        # Recebido: o que o processo pai entregou, capturado antes da escrita.
        "inherited_thread_limits": dict(INHERITED_THREAD_LIMITS),
        # Observado: medido depois da otimização, quando threads acidentais de
        # BLAS já teriam sido criadas.
        "observed_threads": observed_thread_state(),
    }
