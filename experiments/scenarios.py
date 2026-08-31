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
from metaheuristica.instances import SUPPORTED_ARTESP_SIZES

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


# Os tamanhos vêm do próprio carregador, e não de uma lista repetida aqui: uma
# segunda cópia da mesma verdade reintroduziria o defeito um nível acima, porque
# passaria a existir tamanho que o carregador aceita e o identificador ignora.
ARTESP_DEFINITIONS = frozenset(
    f"artesp_rmsp_{size}.json" for size in SUPPORTED_ARTESP_SIZES
)
ARTESP_DATA_FILES = (
    "artesp_rmsp_150_units.parquet",
    "artesp_rmsp_150_pair_metrics.parquet",
)


def instance_data_files(path: Path) -> tuple[Path, ...]:
    """Arquivos de dados que a instância carrega além do próprio JSON.

    O JSON de uma instância ARTESP traz apenas nome, contagem e a lista de
    unidades. Demanda, produção e todas as métricas de par vivem nos dois
    Parquet que ``load_artesp_instance`` abre por nome literal no mesmo
    diretório, iguais para todo tamanho que o carregador suporta. Enquanto eles
    ficaram fora do identificador, trocar os dados do objetivo não mudava o
    ``scenario_id``.
    """

    if path.name in ARTESP_DEFINITIONS:
        return tuple(path.parent / name for name in ARTESP_DATA_FILES)
    return ()


def instance_data_hashes(path: Path) -> dict[str, str]:
    """SHA-256, por nome de arquivo, dos dados que a instância carrega à parte."""

    hashes: dict[str, str] = {}
    for data_path in instance_data_files(path):
        if not data_path.is_file():
            raise ConfigurationError(f"arquivo de dados ausente: {data_path.name}")
        hashes[data_path.name] = file_sha256(data_path)
    return hashes


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
    data_hashes = {
        instance.path: instance_data_hashes(config.repository_root / instance.path)
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
                                "data_sha256": data_hashes[instance.path],
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
                        if config.frozen_parameters_sha256 is not None:
                            payload["frozen_parameters_sha256"] = (
                                config.frozen_parameters_sha256
                            )
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
