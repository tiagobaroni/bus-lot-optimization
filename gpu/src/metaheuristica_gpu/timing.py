"""Métricas sincronizadas do caminho híbrido CPU-GPU."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Callable, TypeVar

import cupy as cp


T = TypeVar("T")


@dataclass(slots=True)
class GpuTiming:
    host_to_device_seconds: float = 0.0
    kernel_seconds: float = 0.0
    device_to_host_seconds: float = 0.0
    arbitration_cpu_seconds: float = 0.0
    synchronization_seconds: float = 0.0
    batches: int = 0
    candidates: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def synchronized_call(action: Callable[[], T]) -> tuple[T, float]:
    cp.cuda.get_current_stream().synchronize()
    start = perf_counter()
    result = action()
    cp.cuda.get_current_stream().synchronize()
    return result, perf_counter() - start


def warmup_gpu() -> dict[str, float]:
    start = perf_counter()
    values = cp.arange(1024, dtype=cp.float64)
    result = cp.sum(values * values)
    cp.cuda.get_current_stream().synchronize()
    if float(result.get()) <= 0.0:
        raise RuntimeError("aquecimento GPU produziu resultado inválido")
    return {"warmup_seconds": perf_counter() - start}
