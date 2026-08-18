"""Leitura estrita das configurações declarativas de experimentos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
import tomllib

from metaheuristica import AcoConfig, ObjectiveWeights, PsoConfig, TabuConfig
from metaheuristica.errors import ConfigurationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PURPOSES = {"tuning", "pilot", "benchmark"}
ALGORITHM_FIELDS = {
    "tabu": ("tabu_tenure", "neighborhood_size", "stagnation_limit"),
    "aco": ("alpha", "beta", "rho", "n_ants"),
    "pso": ("n_particles", "inertia", "cognitive", "social"),
}
CONFIG_TYPES = {"tabu": TabuConfig, "aco": AcoConfig, "pso": PsoConfig}


@dataclass(frozen=True, slots=True)
class InstanceConfig:
    name: str
    path: str
    budget: int
    k_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    schema_version: int
    name: str
    purpose: str
    output_root: str
    seeds: tuple[int, ...]
    weights: ObjectiveWeights
    cache_enabled: bool
    instances: tuple[InstanceConfig, ...]
    algorithms: Mapping[str, Mapping[str, tuple[Any, ...]]]
    frozen_parameters_sha256: str | None
    source_path: Path
    repository_root: Path


def _require_keys(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = expected - set(data)
    unknown = set(data) - expected
    if missing:
        raise ConfigurationError(f"{path}: campos ausentes: {sorted(missing)}")
    if unknown:
        raise ConfigurationError(f"{path}: campos desconhecidos: {sorted(unknown)}")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{path}: deve ser texto não vazio")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{path}: deve ser inteiro positivo")
    return value


def _k(value: Any, path: str) -> int:
    parsed = _positive_int(value, path)
    if parsed < 2:
        raise ConfigurationError(f"{path}: K deve ser pelo menos 2")
    return parsed


def _budget(value: Any, path: str) -> int:
    parsed = _positive_int(value, path)
    if parsed < 100:
        raise ConfigurationError(f"{path}: orçamento deve permitir 100 checkpoints")
    return parsed


def _unique_tuple(values: Any, path: str, validator: Any) -> tuple[Any, ...]:
    if not isinstance(values, list) or not values:
        raise ConfigurationError(f"{path}: deve ser lista não vazia")
    parsed = tuple(validator(value, f"{path}[{index}]") for index, value in enumerate(values))
    if len(set(parsed)) != len(parsed):
        raise ConfigurationError(f"{path}: contém valores duplicados")
    return parsed


def _seed(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{path}: deve ser inteiro")
    return value


def _grid_value(value: Any, path: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{path}: deve ser numérico")
    return value


def load_campaign(path: str | Path, *, repository_root: Path | None = None) -> CampaignConfig:
    """Lê e valida integralmente uma campanha TOML."""

    source = Path(path).resolve()
    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as error:
        raise ConfigurationError(f"configuração inexistente: {source}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"TOML inválido: {error}") from error
    _require_keys(
        data,
        {
            "schema_version", "name", "purpose", "output_root", "seeds",
            "cache_enabled", "weights", "instances", "algorithms",
        },
        "config",
    )
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise ConfigurationError("schema_version: versão suportada é 1")
    name = _text(data["name"], "name")
    purpose = _text(data["purpose"], "purpose")
    if purpose not in PURPOSES:
        raise ConfigurationError(f"purpose: deve pertencer a {sorted(PURPOSES)}")
    output_root = _text(data["output_root"], "output_root")
    if Path(output_root).is_absolute():
        raise ConfigurationError("output_root: deve ser relativo à raiz do repositório")
    seeds = _unique_tuple(data["seeds"], "seeds", _seed)
    if not isinstance(data["cache_enabled"], bool):
        raise ConfigurationError("cache_enabled: deve ser booleano")

    weights_data = data["weights"]
    if not isinstance(weights_data, dict):
        raise ConfigurationError("weights: deve ser tabela")
    _require_keys(weights_data, {"demand", "production", "territorial", "affinity"}, "weights")
    try:
        weights = ObjectiveWeights(**weights_data)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"weights: {error}") from error

    root = (repository_root or REPOSITORY_ROOT).resolve()
    if not (root / output_root).resolve().is_relative_to(root):
        raise ConfigurationError("output_root: não pode sair da raiz do repositório")
    raw_instances = data["instances"]
    if not isinstance(raw_instances, list) or not raw_instances:
        raise ConfigurationError("instances: deve ser lista não vazia de tabelas")
    instances: list[InstanceConfig] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_instances):
        item_path = f"instances[{index}]"
        if not isinstance(raw, dict):
            raise ConfigurationError(f"{item_path}: deve ser tabela")
        _require_keys(raw, {"name", "path", "budget", "k_values"}, item_path)
        instance_name = _text(raw["name"], f"{item_path}.name")
        if instance_name in names:
            raise ConfigurationError(f"{item_path}.name: duplicado")
        names.add(instance_name)
        relative_path = _text(raw["path"], f"{item_path}.path")
        if Path(relative_path).is_absolute():
            raise ConfigurationError(f"{item_path}.path: deve ser relativo")
        resolved = (root / relative_path).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ConfigurationError(f"{item_path}.path: arquivo inexistente ou fora da raiz")
        k_values = _unique_tuple(raw["k_values"], f"{item_path}.k_values", _k)
        instances.append(InstanceConfig(instance_name, relative_path, _budget(raw["budget"], f"{item_path}.budget"), k_values))

    raw_algorithms = data["algorithms"]
    if not isinstance(raw_algorithms, dict) or not raw_algorithms:
        raise ConfigurationError("algorithms: deve ser tabela não vazia")
    unknown_algorithms = set(raw_algorithms) - set(ALGORITHM_FIELDS)
    if unknown_algorithms:
        raise ConfigurationError(f"algorithms: desconhecidos: {sorted(unknown_algorithms)}")
    algorithms: dict[str, Mapping[str, tuple[Any, ...]]] = {}
    for algorithm, raw_grid in raw_algorithms.items():
        if not isinstance(raw_grid, dict):
            raise ConfigurationError(f"algorithms.{algorithm}: deve ser tabela")
        fields = set(ALGORITHM_FIELDS[algorithm])
        _require_keys(raw_grid, fields, f"algorithms.{algorithm}")
        parsed_grid: dict[str, tuple[Any, ...]] = {}
        for field in ALGORITHM_FIELDS[algorithm]:
            parsed_grid[field] = _unique_tuple(
                raw_grid[field], f"algorithms.{algorithm}.{field}", _grid_value
            )
            if purpose != "tuning" and len(parsed_grid[field]) != 1:
                raise ConfigurationError(
                    f"algorithms.{algorithm}.{field}: {purpose} exige valor único"
                )
        algorithms[algorithm] = MappingProxyType(parsed_grid)

    from experiments.frozen_parameters import validate_frozen_parameters

    frozen_hash = validate_frozen_parameters(
        campaign_name=name, algorithms=algorithms, repository_root=root
    )
    return CampaignConfig(
        1, name, purpose, output_root, seeds, weights, data["cache_enabled"],
        tuple(instances), MappingProxyType(algorithms), frozen_hash, source, root,
    )
