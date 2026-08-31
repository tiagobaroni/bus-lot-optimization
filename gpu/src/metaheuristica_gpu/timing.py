"""Métricas sincronizadas do caminho híbrido CPU-GPU."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter

import cupy as cp


# F8-1, componente `M3`. O campo `synchronization_seconds` e o auxiliar
# `synchronized_call` foram removidos: o campo não era atribuído em lugar
# algum do pacote e o auxiliar não tinha chamador, de modo que o documento de
# cada cenário publicava um zero que nada media, ao lado de checkpoints que de
# fato divergem em 1 ulp. `arbitration_cpu_seconds` permanece porque a
# remoção prescrita nomeia apenas os três itens acima; ele passa a ser
# declarado como estruturalmente nulo no schema de diagnóstico publicado por
# `run.py`, já que seu único incremento vivia dentro de `arbitrate_best`.
@dataclass(slots=True)
class GpuTiming:
    host_to_device_seconds: float = 0.0
    kernel_seconds: float = 0.0
    device_to_host_seconds: float = 0.0
    arbitration_cpu_seconds: float = 0.0
    batches: int = 0
    candidates: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def warmup_gpu() -> dict[str, float]:
    start = perf_counter()
    values = cp.arange(1024, dtype=cp.float64)
    result = cp.sum(values * values)
    cp.cuda.get_current_stream().synchronize()
    if float(result.get()) <= 0.0:
        raise RuntimeError("aquecimento GPU produziu resultado inválido")
    return {"warmup_seconds": perf_counter() - start}
