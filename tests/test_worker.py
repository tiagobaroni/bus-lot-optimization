"""Garantia e registro de uma thread computacional por execução."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "ARROW_NUM_THREADS",
)

WORKER_SCRIPT = """
import json, sys
from pathlib import Path

from experiments.config import load_campaign
from experiments.scenarios import expand_scenarios
from experiments.worker import run_scenario

root = Path(sys.argv[1])
config = load_campaign(root / "campaign.toml", repository_root=root)
output = run_scenario(expand_scenarios(config)[0], str(root))
print(json.dumps({
    "thread_limits": output["thread_limits"],
    "inherited_thread_limits": output["inherited_thread_limits"],
    "observed_threads": output["observed_threads"],
}))
"""

ARROW_SCRIPT = """
import json
import pyarrow as pa
print(json.dumps({"cpu_count": pa.cpu_count()}))
"""

ARROW_WORKER_SCRIPT = """
import json
import pyarrow as pa
import experiments.worker  # noqa: F401
print(json.dumps({"cpu_count": pa.cpu_count(), "io": pa.io_thread_count()}))
"""


def _run(script: str, *arguments: str, environment: dict[str, str]) -> dict:
    base = {
        key: value
        for key, value in os.environ.items()
        if key not in THREAD_VARIABLES
    }
    base["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "src")])
    base.update(environment)
    completed = subprocess.run(
        [sys.executable, "-c", script, *arguments],
        check=True, capture_output=True, text=True, env=base, cwd=ROOT,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _campaign(root: Path) -> None:
    data = root / "data"
    data.mkdir(parents=True)
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    (root / "campaign.toml").write_text(
        """schema_version = 1
name = "tiny_worker"
purpose = "pilot"
output_root = "out"
seeds = [1]
cache_enabled = false

[weights]
demand = 0.25
production = 0.25
territorial = 0.25
affinity = 0.25

[[instances]]
name = "tiny"
path = "data/tiny.json"
budget = 100
k_values = [2]

[algorithms.pso]
n_particles = [20]
inertia = [0.7]
cognitive = [1.5]
social = [1.5]
""",
        encoding="utf-8",
    )


def test_worker_records_the_environment_it_received_and_not_the_one_it_wrote(
    tmp_path: Path,
) -> None:
    """F7-2: `thread_limits` relia as chaves que o próprio processo escrevera.

    Escrita e leitura acontecem no mesmo `os.environ`, no mesmo processo, a
    poucas linhas de distância, então a asserção `set(limits.values()) == {"1"}`
    é verdadeira por construção e não pode falhar. O ambiente recebido do pai é
    o registro que efetivamente documenta a configuração, e ele só existe se for
    capturado antes da escrita.
    """

    _campaign(tmp_path)
    record = _run(
        WORKER_SCRIPT,
        str(tmp_path),
        environment={variable: "8" for variable in THREAD_VARIABLES},
    )

    assert set(record["inherited_thread_limits"].values()) == {"8"}
    assert set(record["thread_limits"].values()) == {"1"}
    assert set(record["inherited_thread_limits"]) == set(THREAD_VARIABLES)


def test_worker_records_an_empty_environment_as_received_when_nothing_is_set(
    tmp_path: Path,
) -> None:
    _campaign(tmp_path)
    record = _run(WORKER_SCRIPT, str(tmp_path), environment={})

    assert set(record["inherited_thread_limits"].values()) == {None}
    assert set(record["thread_limits"].values()) == {"1"}


def test_worker_observes_a_single_computational_thread(tmp_path: Path) -> None:
    """F7-2: a contagem observada documenta o comportamento, não a intenção."""

    _campaign(tmp_path)
    observed = _run(
        WORKER_SCRIPT,
        str(tmp_path),
        environment={variable: "8" for variable in THREAD_VARIABLES},
    )["observed_threads"]

    assert observed["threads_total"] is not None
    assert observed["threads_with_ticks"] == 1
    assert observed["threads_total"] >= observed["threads_with_ticks"]
    assert observed["arrow_cpu_count"] == 1
    assert observed["arrow_io_thread_count"] == 1


@pytest.mark.skipif(
    (os.cpu_count() or 1) < 2, reason="a inércia da variável só aparece com vários núcleos"
)
def test_arrow_is_contained_by_omp_and_not_by_its_own_variable() -> None:
    """F7-4: `ARROW_NUM_THREADS` não é variável reconhecida pelo Arrow.

    Quem controla `pa.cpu_count()` é `OMP_NUM_THREADS`, mais as chamadas
    explícitas de `pa.set_cpu_count` e `pa.set_io_thread_count`. O enunciado da
    restrição global mantém a variável por simetria e declara que ela é inerte.
    """

    inert = _run(ARROW_SCRIPT, environment={"ARROW_NUM_THREADS": "1"})
    assert inert["cpu_count"] > 1

    effective = _run(ARROW_SCRIPT, environment={"OMP_NUM_THREADS": "1"})
    assert effective["cpu_count"] == 1

    worker = _run(ARROW_WORKER_SCRIPT, environment={"ARROW_NUM_THREADS": "8"})
    assert worker["cpu_count"] == 1
    assert worker["io"] == 1
