"""Validação das configurações selecionadas no tuning oficial."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import tomllib

from metaheuristica.errors import ConfigurationError

from experiments.scenarios import file_sha256


OFFICIAL_CAMPAIGNS = {"pilot_prebenchmark", "benchmark_main"}
PARAMETER_FIELDS = {
    "tabu": ("tabu_tenure", "neighborhood_size", "stagnation_limit"),
    "aco": ("alpha", "beta", "rho", "n_ants"),
    "pso": ("n_particles", "inertia", "cognitive", "social"),
}


def validate_frozen_parameters(
    *,
    campaign_name: str,
    algorithms: dict[str, dict[str, tuple[Any, ...]]] | Any,
    repository_root: Path,
) -> str | None:
    """Exige igualdade exata com a seleção da B9 nas campanhas oficiais."""

    if campaign_name not in OFFICIAL_CAMPAIGNS:
        return None
    path = repository_root / "experiments/configs/frozen_parameters.toml"
    try:
        with path.open("rb") as stream:
            frozen = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"parâmetros congelados inválidos: {path}") from error

    if set(algorithms) != set(PARAMETER_FIELDS):
        raise ConfigurationError("campanha oficial exige TS, ACO e PSO")
    for algorithm, fields in PARAMETER_FIELDS.items():
        section = frozen.get(algorithm)
        if not isinstance(section, dict) or set(section) != set(fields):
            raise ConfigurationError(
                f"frozen_parameters.toml: seção {algorithm} incompatível"
            )
        grid = algorithms[algorithm]
        if set(grid) != set(fields):
            raise ConfigurationError(f"algorithms.{algorithm}: campos incompatíveis")
        for field in fields:
            values = tuple(grid[field])
            if len(values) != 1 or values[0] != section[field]:
                raise ConfigurationError(
                    f"algorithms.{algorithm}.{field}: diverge dos parâmetros congelados"
                )
    return file_sha256(path)
