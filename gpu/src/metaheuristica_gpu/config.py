"""Configuração estrita e isolada das campanhas GPU."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from metaheuristica import AcoConfig, ObjectiveWeights, PsoConfig


class GpuConfigError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GpuCampaignConfig:
    schema_version: int
    name: str
    purpose: str
    output_root: str
    instance: str
    instance_size: int
    k: int
    budget: int
    seeds: tuple[int, ...]
    algorithms: tuple[str, ...]
    backend: str
    precision: str
    weights: ObjectiveWeights
    aco: AcoConfig
    pso: PsoConfig
    source_path: Path
    repository_root: Path


def load_gpu_config(path: str | Path, *, repository_root: Path | None = None) -> GpuCampaignConfig:
    source = Path(path).resolve()
    root = repository_root or source.parents[2]
    try:
        data: dict[str, Any] = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise GpuConfigError(f"configuração GPU inválida: {error}") from error
    expected = {
        "schema_version", "name", "purpose", "output_root", "instance",
        "instance_size", "k", "budget", "seeds", "algorithms", "backend",
        "precision", "weights", "aco", "pso",
    }
    if set(data) != expected:
        raise GpuConfigError(f"campos GPU divergentes: {sorted(set(data) ^ expected)}")
    if data["schema_version"] != 1 or data["purpose"] not in {"gpu_benchmark", "gpu_diagnostic"}:
        raise GpuConfigError("versão ou finalidade GPU inválida")
    if data["backend"] != "cupy_cuda12" or data["precision"] != "float64":
        raise GpuConfigError("backend exige CuPy CUDA 12 em float64")
    seeds = tuple(data["seeds"])
    algorithms = tuple(data["algorithms"])
    if not seeds or len(seeds) != len(set(seeds)) or any(isinstance(x, bool) or not isinstance(x, int) for x in seeds):
        raise GpuConfigError("seeds GPU inválidas")
    if algorithms != ("aco", "pso"):
        raise GpuConfigError("campanha GPU exige exatamente ACO e PSO")
    output = Path(data["output_root"])
    if output.is_absolute() or not (root / output).resolve().is_relative_to(root):
        raise GpuConfigError("output_root GPU deve permanecer no repositório")
    weights = ObjectiveWeights(**data["weights"])
    return GpuCampaignConfig(
        1, str(data["name"]), str(data["purpose"]), str(output),
        str(data["instance"]), int(data["instance_size"]), int(data["k"]),
        int(data["budget"]), seeds, algorithms, str(data["backend"]),
        str(data["precision"]), weights, AcoConfig(**data["aco"]),
        PsoConfig(**data["pso"]), source, root,
    )
