from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from metaheuristica import (
    ConfigurationError,
    EvaluationResult,
    InstanceDataError,
    ObjectiveWeights,
    ProblemInstance,
)


def make_instance(**overrides: object) -> ProblemInstance:
    defaults: dict[str, object] = {
        "name": "teste",
        "unit_ids": ("A", "B"),
        "demand": np.array([10.0, 20.0]),
        "production": np.array([100.0, 200.0]),
        "s_territorial": np.zeros((2, 2)),
        "t_terminal": np.zeros((2, 2)),
        "i_integration": np.zeros((2, 2)),
        "o_market": np.zeros((2, 2)),
        "metadata": {"A": {"nome": "Linha A"}},
    }
    defaults.update(overrides)
    return ProblemInstance(**defaults)  # type: ignore[arg-type]


def test_uniform_weights_are_the_default() -> None:
    assert ObjectiveWeights().as_tuple() == (0.25, 0.25, 0.25, 0.25)


@pytest.mark.parametrize(
    "weights",
    [
        (float("nan"), 0.0, 0.0, 1.0),
        (-0.1, 0.1, 0.5, 0.5),
        (0.2, 0.2, 0.2, 0.2),
    ],
)
def test_invalid_weights_are_rejected(weights: tuple[float, ...]) -> None:
    with pytest.raises(ConfigurationError):
        ObjectiveWeights(*weights)


def test_evaluation_result_is_immutable() -> None:
    result = EvaluationResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        result.total_cost = 1.0  # type: ignore[misc]


def test_instance_copies_and_protects_arrays_and_metadata() -> None:
    source = np.array([10.0, 20.0])
    instance = make_instance(demand=source)
    source[0] = 999.0

    assert instance.demand.tolist() == [10.0, 20.0]
    assert instance.w_affinity.shape == (2, 2)
    with pytest.raises(ValueError):
        instance.demand[0] = 1.0
    with pytest.raises(ValueError):
        instance.demand.setflags(write=True)
    with pytest.raises(TypeError):
        instance.metadata["A"]["nome"] = "alterado"  # type: ignore[index]


def test_instance_rejects_duplicate_ids_and_wrong_dimensions() -> None:
    with pytest.raises(InstanceDataError, match="duplicados"):
        make_instance(unit_ids=("A", "A"))
    with pytest.raises(InstanceDataError, match="esperada dimensão"):
        make_instance(s_territorial=np.zeros((3, 3)))
