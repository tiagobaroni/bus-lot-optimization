"""IDs imutáveis e não colidentes dos cenários GPU."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from metaheuristica_gpu.config import GpuCampaignConfig, GpuConfigError
from metaheuristica_gpu.environment import file_sha256


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True, slots=True)
class GpuScenario:
    payload: dict[str, object]
    scenario_id: str

    @property
    def filename(self) -> str:
        return f"{self.scenario_id}.json"


def expand_gpu_scenarios(config: GpuCampaignConfig) -> tuple[GpuScenario, ...]:
    instance_path = (
        config.repository_root / "data/instances/tiny_manual.json"
        if config.instance == "tiny_manual"
        else config.repository_root / f"data/instances/artesp_rmsp_{config.instance_size}.json"
    )
    scenarios = []
    for algorithm in config.algorithms:
        parameters = config.aco.__dict__ if hasattr(config.aco, "__dict__") else {
            name: getattr(config.aco, name) for name in config.aco.__dataclass_fields__
        }
        if algorithm == "pso":
            parameters = {name: getattr(config.pso, name) for name in config.pso.__dataclass_fields__}
        for seed in config.seeds:
            payload = {
                "schema_version": 1, "purpose": config.purpose,
                "algorithm": algorithm, "instance": config.instance,
                "instance_size": config.instance_size,
                "instance_path": str(instance_path.relative_to(config.repository_root)),
                "instance_sha256": file_sha256(instance_path),
                "k": config.k, "seed": seed, "budget": config.budget,
                "weights": dict(zip(("demand", "production", "territorial", "affinity"), config.weights.as_tuple())),
                "parameters": parameters, "backend": config.backend,
                "precision": config.precision,
            }
            identifier = sha256(canonical_json(payload)).hexdigest()
            scenarios.append(GpuScenario(payload, identifier))
    scenarios.sort(key=lambda item: (item.payload["algorithm"], item.payload["seed"], item.scenario_id))
    if config.purpose == "gpu_benchmark" and len(scenarios) != 60:
        raise GpuConfigError(f"campanha oficial GPU deve conter 60 IDs, obteve {len(scenarios)}")
    if len({item.scenario_id for item in scenarios}) != len(scenarios):
        raise GpuConfigError("IDs GPU duplicados")
    return tuple(scenarios)
