"""Expansão determinística e identidade dos cenários experimentais."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from typing import Any, Mapping

from metaheuristica import RunConfig
from metaheuristica.errors import ConfigurationError

from experiments.config import ALGORITHM_FIELDS, CONFIG_TYPES, CampaignConfig


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Scenario:
    payload: Mapping[str, Any]
    scenario_id: str
    filename: str


def _safe_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    return cleaned.strip("_").lower()


def expand_scenarios(config: CampaignConfig) -> tuple[Scenario, ...]:
    hashes = {
        instance.path: file_sha256(config.repository_root / instance.path)
        for instance in config.instances
    }
    scenarios: list[Scenario] = []
    for algorithm in sorted(config.algorithms):
        grid = config.algorithms[algorithm]
        fields = ALGORITHM_FIELDS[algorithm]
        combinations = product(*(grid[field] for field in fields))
        for values in combinations:
            parameters = dict(zip(fields, values))
            try:
                CONFIG_TYPES[algorithm](**parameters)
            except (TypeError, ValueError) as error:
                raise ConfigurationError(
                    f"algorithms.{algorithm}: combinação inválida: {error}"
                ) from error
            for instance in sorted(config.instances, key=lambda item: item.name):
                for k in sorted(instance.k_values):
                    for seed in sorted(config.seeds):
                        RunConfig(
                            k=k, seed=seed, budget=instance.budget,
                            weights=config.weights, cache_enabled=config.cache_enabled,
                        )
                        payload = {
                            "schema_version": config.schema_version,
                            "purpose": config.purpose,
                            "algorithm": algorithm,
                            "parameters": parameters,
                            "instance": {
                                "name": instance.name,
                                "path": instance.path,
                                "sha256": hashes[instance.path],
                            },
                            "k": k,
                            "seed": seed,
                            "budget": instance.budget,
                            "weights": {
                                "demand": config.weights.demand,
                                "production": config.weights.production,
                                "territorial": config.weights.territorial,
                                "affinity": config.weights.affinity,
                            },
                            "cache_enabled": config.cache_enabled,
                        }
                        identifier = sha256(canonical_json(payload)).hexdigest()
                        filename = (
                            f"{algorithm}_{_safe_name(instance.name)}_k{k}_s{seed}_"
                            f"{identifier[:12]}.json"
                        )
                        scenarios.append(Scenario(payload, identifier, filename))
    scenarios.sort(
        key=lambda item: (
            item.payload["algorithm"], item.payload["instance"]["name"],
            item.payload["k"], item.payload["seed"],
            canonical_json(item.payload["parameters"]), item.scenario_id,
        )
    )
    ids = [item.scenario_id for item in scenarios]
    if len(set(ids)) != len(ids):
        raise ConfigurationError("expansão produziu cenários duplicados")
    prefixes = [item.scenario_id[:12] for item in scenarios]
    if len(set(prefixes)) != len(prefixes):
        raise ConfigurationError("colisão entre prefixos de IDs de cenário")
    return tuple(scenarios)


def select_scenario(scenarios: tuple[Scenario, ...], identifier: str) -> Scenario:
    if not identifier:
        raise ConfigurationError("scenario-id não pode ser vazio")
    matches = [item for item in scenarios if item.scenario_id.startswith(identifier)]
    if not matches:
        raise ConfigurationError(f"scenario-id inexistente: {identifier}")
    if len(matches) > 1:
        raise ConfigurationError(f"scenario-id ambíguo: {identifier}")
    return matches[0]
