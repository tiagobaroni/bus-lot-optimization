from __future__ import annotations

import numpy as np
import pytest

from metaheuristica import ConfigurationError, SolutionValidationError
from metaheuristica.canonical import (
    canonicalize_solution,
    solution_key,
    validate_solution,
)


def test_canonicalization_follows_first_occurrence() -> None:
    canonical = canonicalize_solution([2, 2, 0, 1, 0], n_units=5, k=3)
    assert canonical.tolist() == [0, 0, 1, 2, 1]
    assert not canonical.flags.writeable


def test_equivalent_partitions_share_key_and_canonicalization_is_idempotent() -> None:
    first = solution_key([0, 0, 1, 1, 2, 2], n_units=6, k=3)
    second = solution_key([2, 2, 0, 0, 1, 1], n_units=6, k=3)
    assert first == second == (0, 0, 1, 1, 2, 2)
    assert solution_key(first, n_units=6, k=3) == first


def test_validated_solution_is_an_immutable_copy() -> None:
    source = np.array([0, 1, 1], dtype=np.int32)
    validated = validate_solution(source, n_units=3, k=2)
    source[0] = 1
    assert validated.tolist() == [0, 1, 1]
    assert validated.dtype == np.int64
    with pytest.raises(ValueError):
        validated[0] = 1
    with pytest.raises(ValueError):
        validated.setflags(write=True)


@pytest.mark.parametrize(
    ("solution", "message"),
    [
        ([0, 1], "3 posições"),
        ([[0, 1, 1]], "unidimensional"),
        ([0.0, 1.0, 1.0], "inteiros"),
        ([0, 1, 2], "intervalo"),
        ([0, 0, 0], "lotes vazios"),
        ([True, False, True], "inteiros"),
    ],
)
def test_invalid_solutions_are_rejected(solution: object, message: str) -> None:
    with pytest.raises(SolutionValidationError, match=message):
        validate_solution(solution, n_units=3, k=2)


@pytest.mark.parametrize("k", [1, 4, 2.0, True])
def test_invalid_k_is_rejected(k: object) -> None:
    with pytest.raises(ConfigurationError):
        validate_solution([0, 1, 1], n_units=3, k=k)  # type: ignore[arg-type]
