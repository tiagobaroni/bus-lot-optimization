"""Preflight e proveniência do ambiente CUDA isolado."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import cupy as cp
import numpy as np


class GpuConfigurationError(RuntimeError):
    """Indica que a B11A não pode usar a GPU com segurança."""


@dataclass(frozen=True, slots=True)
class GpuEnvironment:
    python: str
    numpy: str
    cupy: str
    system: str
    kernel: str
    driver: str
    cuda_runtime: str
    gpu_name: str
    gpu_uuid: str
    memory_total_mib: int
    compute_capability: str
    float64_kernel_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nvidia_smi(*fields: str) -> list[str]:
    command = [
        "nvidia-smi",
        f"--query-gpu={','.join(fields)}",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise GpuConfigurationError("nvidia-smi indisponível") from error
    rows = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise GpuConfigurationError("preflight exige exatamente uma GPU NVIDIA")
    values = [value.strip() for value in rows[0].split(",")]
    if len(values) != len(fields):
        raise GpuConfigurationError("resposta inesperada do nvidia-smi")
    return values


def _runtime_text(version: int) -> str:
    major = version // 1000
    minor = (version % 1000) // 10
    return f"{major}.{minor}"


def _float64_kernel() -> bool:
    values = cp.asarray([1.0, 2.0, 3.0], dtype=cp.float64)
    result = cp.sum(values * values)
    cp.cuda.get_current_stream().synchronize()
    return bool(float(result.get()) == 14.0 and values.dtype == cp.float64)


def inspect_gpu_environment() -> GpuEnvironment:
    if sys.version_info[:2] != (3, 14):
        raise GpuConfigurationError("ambiente GPU exige Python 3.14")
    name, uuid, memory, capability, driver = _nvidia_smi(
        "name", "uuid", "memory.total", "compute_cap", "driver_version"
    )
    runtime_version = int(cp.cuda.runtime.runtimeGetVersion())
    runtime = _runtime_text(runtime_version)
    if not runtime.startswith("12."):
        raise GpuConfigurationError(f"runtime CUDA deve ser 12.x, obteve {runtime}")
    device = cp.cuda.Device(0)
    properties = cp.cuda.runtime.getDeviceProperties(device.id)
    actual_capability = f"{properties['major']}.{properties['minor']}"
    if actual_capability != capability:
        raise GpuConfigurationError("compute capability diverge do driver")
    if float(capability) < 6.0:
        raise GpuConfigurationError("GPU sem capacidade float64 adequada")
    passed = _float64_kernel()
    if not passed:
        raise GpuConfigurationError("kernel mínimo float64 falhou")
    return GpuEnvironment(
        python=platform.python_version(), numpy=np.__version__, cupy=cp.__version__,
        system=platform.system(), kernel=platform.release(), driver=driver,
        cuda_runtime=runtime, gpu_name=name, gpu_uuid=uuid,
        memory_total_mib=int(memory), compute_capability=capability,
        float64_kernel_passed=passed,
    )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gpu_code_hash(root: Path) -> str:
    files = sorted((root / "gpu/src").rglob("*.py"))
    payload = [(str(path.relative_to(root)), file_sha256(path)) for path in files]
    return sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
