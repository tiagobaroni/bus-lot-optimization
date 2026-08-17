"""Tipos fundamentais e imutáveis do problema."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, isfinite
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from metaheuristica.errors import ConfigurationError, InstanceDataError


FloatArray = NDArray[np.float64]


def _readonly_float_array(value: Any, *, name: str, ndim: int) -> FloatArray:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise InstanceDataError(f"{name}: não foi possível converter para float64") from error
    if array.ndim != ndim:
        raise InstanceDataError(f"{name}: esperadas {ndim} dimensões, recebidas {array.ndim}")
    if not np.isfinite(array).all():
        raise InstanceDataError(f"{name}: contém valor não finito")
    immutable = np.frombuffer(array.tobytes(order="C"), dtype=np.float64).reshape(array.shape)
    return immutable


def _readonly_metadata(
    unit_ids: tuple[str, ...], metadata: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Mapping[str, Any]]:
    unknown = set(metadata) - set(unit_ids)
    if unknown:
        raise InstanceDataError(f"metadata: IDs desconhecidos: {sorted(unknown)!r}")
    frozen = {
        unit_id: MappingProxyType(dict(metadata.get(unit_id, {}))) for unit_id in unit_ids
    }
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    """Pesos normalizados dos quatro componentes da função objetivo."""

    demand: float = 0.25
    production: float = 0.25
    territorial: float = 0.25
    affinity: float = 0.25

    def __post_init__(self) -> None:
        values = self.as_tuple()
        if not all(isfinite(value) for value in values):
            raise ConfigurationError("pesos: todos os valores devem ser finitos")
        if any(value < 0.0 for value in values):
            raise ConfigurationError("pesos: todos os valores devem ser não negativos")
        if not isclose(sum(values), 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ConfigurationError("pesos: a soma deve ser igual a 1")

    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.demand, self.production, self.territorial, self.affinity


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Decomposição completa produzida por uma única avaliação."""

    total_cost: float
    c_demand: float
    c_production: float
    c_territorial: float
    c_affinity: float
    cv_demand: float
    cv_production: float

    def __post_init__(self) -> None:
        values = (
            self.total_cost,
            self.c_demand,
            self.c_production,
            self.c_territorial,
            self.c_affinity,
            self.cv_demand,
            self.cv_production,
        )
        if not all(isfinite(value) for value in values):
            raise ConfigurationError("resultado da avaliação contém valor não finito")


@dataclass(frozen=True, slots=True)
class ProblemInstance:
    """Dados imutáveis de uma instância, independentes do número de lotes K."""

    name: str
    unit_ids: tuple[str, ...]
    demand: FloatArray
    production: FloatArray
    s_territorial: FloatArray
    t_terminal: FloatArray
    i_integration: FloatArray
    o_market: FloatArray
    metadata: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    w_affinity: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        unit_ids = tuple(self.unit_ids)
        if not self.name.strip():
            raise InstanceDataError("name: identificador da instância não pode ser vazio")
        if not unit_ids:
            raise InstanceDataError("unit_ids: a instância não pode ser vazia")
        if any(not isinstance(unit_id, str) or not unit_id for unit_id in unit_ids):
            raise InstanceDataError("unit_ids: todos os IDs devem ser textos não vazios")
        if len(set(unit_ids)) != len(unit_ids):
            raise InstanceDataError("unit_ids: contém IDs duplicados")

        demand = _readonly_float_array(self.demand, name="demand", ndim=1)
        production = _readonly_float_array(self.production, name="production", ndim=1)
        matrices = {
            "s_territorial": _readonly_float_array(
                self.s_territorial, name="s_territorial", ndim=2
            ),
            "t_terminal": _readonly_float_array(self.t_terminal, name="t_terminal", ndim=2),
            "i_integration": _readonly_float_array(
                self.i_integration, name="i_integration", ndim=2
            ),
            "o_market": _readonly_float_array(self.o_market, name="o_market", ndim=2),
        }
        n_units = len(unit_ids)
        if demand.shape != (n_units,) or production.shape != (n_units,):
            raise InstanceDataError(
                f"vetores: esperada dimensão ({n_units},), recebidas "
                f"{demand.shape} e {production.shape}"
            )
        if np.any(demand <= 0.0):
            raise InstanceDataError("demand: todos os valores devem ser positivos")
        if np.any(production <= 0.0):
            raise InstanceDataError("production: todos os valores devem ser positivos")
        for matrix_name, matrix in matrices.items():
            if matrix.shape != (n_units, n_units):
                raise InstanceDataError(
                    f"{matrix_name}: esperada dimensão ({n_units}, {n_units}), "
                    f"recebida {matrix.shape}"
                )
            if np.any(matrix < 0.0) or np.any(matrix > 1.0):
                raise InstanceDataError(f"{matrix_name}: valores devem estar em [0, 1]")
            if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-12):
                raise InstanceDataError(f"{matrix_name}: matriz deve ser simétrica")
            if not np.allclose(np.diag(matrix), 0.0, rtol=0.0, atol=1e-12):
                raise InstanceDataError(f"{matrix_name}: diagonal deve ser zero")
        for matrix_name in ("t_terminal", "i_integration"):
            matrix = matrices[matrix_name]
            if not np.all((matrix == 0.0) | (matrix == 1.0)):
                raise InstanceDataError(f"{matrix_name}: valores devem ser binários")

        w_affinity = _readonly_float_array(
            (matrices["t_terminal"] + matrices["i_integration"] + matrices["o_market"])
            / 3.0,
            name="w_affinity",
            ndim=2,
        )

        object.__setattr__(self, "unit_ids", unit_ids)
        object.__setattr__(self, "demand", demand)
        object.__setattr__(self, "production", production)
        for matrix_name, matrix in matrices.items():
            object.__setattr__(self, matrix_name, matrix)
        object.__setattr__(self, "w_affinity", w_affinity)
        object.__setattr__(self, "metadata", _readonly_metadata(unit_ids, self.metadata))

    @property
    def n_units(self) -> int:
        return len(self.unit_ids)
