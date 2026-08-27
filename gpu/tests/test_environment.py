from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from metaheuristica_gpu.environment import (
    THREAD_LIMIT_VARIABLES, inspect_gpu_environment, observed_thread_state,
)


ENTRYPOINT_SCRIPT = """
import json, os

import metaheuristica_gpu.run as run

from metaheuristica_gpu.environment import inspect_gpu_environment

environment = inspect_gpu_environment()
print(json.dumps({
    "environ": {name: os.environ.get(name) for name in run.THREAD_LIMIT_VARIABLES},
    "inherited": run.INHERITED_THREAD_LIMITS,
    "thread_limits": environment.thread_limits,
    "observed_threads": environment.observed_threads,
}))
"""


def test_real_gpu_environment_supports_float64_cuda12() -> None:
    environment = inspect_gpu_environment()
    assert environment.cuda_runtime.startswith("12.")
    assert environment.compute_capability == "8.6"
    assert environment.float64_kernel_passed is True


def test_environment_records_the_thread_variables_and_the_observed_threads() -> None:
    environment = inspect_gpu_environment()
    assert set(environment.thread_limits) == set(THREAD_LIMIT_VARIABLES)
    assert environment.observed_threads["threads_total"] is not None
    assert (
        environment.observed_threads["threads_with_ticks"]
        <= environment.observed_threads["threads_total"]
    )
    assert observed_thread_state()["threads_total"] >= 1


def test_gpu_entrypoint_fixes_the_seven_variables_before_importing() -> None:
    """F7-3: o ponto de entrada da GPU não fixava variável de thread alguma.

    O projeto `gpu/` não importa `experiments`, onde a proteção da CPU vive, e
    `src/metaheuristica/` não tem bloco de ambiente. O subprocesso recebe as
    sete em `8` e, depois da importação, precisa vê-las em `1`, com o valor
    recebido preservado à parte.
    """

    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment.update({variable: "8" for variable in THREAD_LIMIT_VARIABLES})
    completed = subprocess.run(
        [sys.executable, "-c", ENTRYPOINT_SCRIPT],
        check=True, capture_output=True, text=True, env=environment, cwd=root,
    )
    record = json.loads(completed.stdout.strip().splitlines()[-1])

    assert set(record["environ"].values()) == {"1"}
    assert set(record["inherited"].values()) == {"8"}
    assert set(record["thread_limits"].values()) == {"1"}
    assert record["observed_threads"]["threads_total"] >= 1
