"""Validação e canonicalização das soluções de partição."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from metaheuristica.errors import ConfigurationError, SolutionValidationError


IntArray = NDArray[np.int64]


def _immutable_int_array(array: np.ndarray) -> IntArray:
    return np.frombuffer(array.astype(np.int64, copy=False).tobytes(), dtype=np.int64)


def validate_k(k: int, n_units: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int):
        raise ConfigurationError("K deve ser um número inteiro")
    if k < 2 or k > n_units:
        raise ConfigurationError(f"K deve satisfazer 2 <= K <= N; K={k}, N={n_units}")


def validate_solution(solution: Any, *, n_units: int, k: int) -> IntArray:
    """Valida uma solução viável e devolve uma cópia imutável em int64."""

    validate_k(k, n_units)
    array = np.asarray(solution)
    if array.ndim != 1:
        raise SolutionValidationError("solução deve ser um vetor unidimensional")
    if array.shape != (n_units,):
        raise SolutionValidationError(
            f"solução deve ter {n_units} posições; recebeu {array.shape[0]}"
        )
    if not np.issubdtype(array.dtype, np.integer) or np.issubdtype(array.dtype, np.bool_):
        raise SolutionValidationError("solução deve conter somente rótulos inteiros")

    validated = np.array(array, dtype=np.int64, copy=True)
    if np.any(validated < 0) or np.any(validated >= k):
        raise SolutionValidationError(f"rótulos devem estar no intervalo de 0 a {k - 1}")
    active = np.bincount(validated, minlength=k)
    empty = np.flatnonzero(active == 0)
    if empty.size:
        raise SolutionValidationError(f"solução contém lotes vazios: {empty.tolist()}")
    return _immutable_int_array(validated)


def canonicalize_solution(solution: Any, *, n_units: int, k: int) -> IntArray:
    """Valida e renomeia lotes pela ordem da primeira ocorrência."""

    validated = validate_solution(solution, n_units=n_units, k=k)
    label_map: dict[int, int] = {}
    canonical = np.empty(n_units, dtype=np.int64)
    next_label = 0
    for index, label_value in enumerate(validated):
        label = int(label_value)
        if label not in label_map:
            label_map[label] = next_label
            next_label += 1
        canonical[index] = label_map[label]
    return _immutable_int_array(canonical)


def solution_key(solution: Sequence[int] | IntArray, *, n_units: int, k: int) -> tuple[int, ...]:
    """Produz a chave canônica e imutável usada por comparação e cache."""

    canonical = canonicalize_solution(solution, n_units=n_units, k=k)
    return tuple(int(label) for label in canonical)
