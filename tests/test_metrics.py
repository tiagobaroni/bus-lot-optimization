from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from metaheuristica.errors import ConfigurationError
from metaheuristica.metrics import (
    ConvergenceCheckpoint,
    ConvergenceRecorder,
    OptimizationResult,
    RunConfig,
    TerminationReason,
    checkpoint_thresholds,
)
from metaheuristica.problem import EvaluationResult, ObjectiveWeights


EVALUATION = EvaluationResult(0.5, 0.1, 0.2, 0.3, 0.4, 0.11, 0.22)


def test_run_config_is_immutable_and_has_expected_defaults() -> None:
    config = RunConfig(k=2, seed=7, budget=100)
    assert config.weights == ObjectiveWeights()
    assert config.checkpoint_count == 100
    assert config.cache_enabled is False
    with pytest.raises(FrozenInstanceError):
        config.seed = 8  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("k", True),
        ("k", 1),
        ("seed", True),
        ("seed", -1),
        ("budget", 99),
        ("budget", True),
        ("checkpoint_count", 99),
        ("cache_enabled", 1),
    ],
)
def test_run_config_rejects_invalid_values(field: str, value: object) -> None:
    values: dict[str, object] = {"k": 2, "seed": 7, "budget": 100}
    values[field] = value
    with pytest.raises(ConfigurationError):
        RunConfig(**values)  # type: ignore[arg-type]


def test_checkpoint_thresholds_use_ceiling_and_finish_at_budget() -> None:
    thresholds = checkpoint_thresholds(151)
    assert len(thresholds) == 100
    assert thresholds[:3] == (2, 4, 5)
    assert thresholds[-1] == 151
    assert all(left < right for left, right in zip(thresholds, thresholds[1:]))


def test_recorder_updates_incumbent_before_materializing_checkpoint() -> None:
    recorder = ConvergenceRecorder(checkpoint_thresholds(100))
    recorder.observe(1, (0, 0, 1, 1), EVALUATION, True)
    assert recorder.checkpoints == (ConvergenceCheckpoint(1, 1, EVALUATION),)


def test_recorder_uses_canonical_key_to_break_cost_tie() -> None:
    recorder = ConvergenceRecorder(checkpoint_thresholds(200))
    recorder.observe(1, (0, 1, 0, 1), EVALUATION, True)
    recorder.observe(2, (0, 0, 1, 1), EVALUATION, True)
    assert recorder.incumbent_solution == (0, 0, 1, 1)
    assert recorder.checkpoints[0].evaluations == 2


def test_noneligible_evaluation_preserves_previous_incumbent() -> None:
    recorder = ConvergenceRecorder(checkpoint_thresholds(200))
    recorder.observe(1, (0, 0, 1, 1), EVALUATION, True)
    worse = EvaluationResult(0.9, 0.2, 0.3, 0.4, 0.5, 0.2, 0.3)
    recorder.observe(2, None, worse, False)
    assert recorder.checkpoints[0].evaluation is EVALUATION


def _result(*, diagnostics: object = None) -> OptimizationResult:
    checkpoints = tuple(
        ConvergenceCheckpoint(index, index, EVALUATION) for index in range(1, 101)
    )
    return OptimizationResult(
        algorithm="test",
        k=2,
        seed=1,
        budget=100,
        weights=ObjectiveWeights(),
        solution=np.array([1, 1, 0, 0]),
        evaluation=EVALUATION,
        evaluations=100,
        cache_hits=0,
        checkpoints=checkpoints,
        runtime_seconds=0.25,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={} if diagnostics is None else diagnostics,  # type: ignore[arg-type]
    )


def test_result_is_canonical_immutable_and_json_serializable() -> None:
    result = _result(diagnostics={"iterations": 4, "values": [1.0, None]})
    assert result.solution.tolist() == [0, 0, 1, 1]
    assert result.solution.flags.writeable is False
    assert result.to_dict()["diagnostics"] == {
        "iterations": 4,
        "values": [1.0, None],
    }
    json.dumps(result.to_dict(), allow_nan=False)


def test_reproducible_data_excludes_only_runtime() -> None:
    first = _result()
    second_data = first.to_dict()
    assert "runtime_seconds" in second_data
    assert "runtime_seconds" not in first.reproducible_data()


@pytest.mark.parametrize(
    "diagnostics",
    [{1: "invalid"}, {"bad": float("nan")}, {"array": np.array([1])}],
)
def test_result_rejects_nonserializable_diagnostics(diagnostics: object) -> None:
    with pytest.raises(ConfigurationError):
        _result(diagnostics=diagnostics)


def test_result_rejects_wrong_checkpoint_count() -> None:
    with pytest.raises(ConfigurationError):
        OptimizationResult(
            algorithm="test",
            k=2,
            seed=1,
            budget=100,
            weights=ObjectiveWeights(),
            solution=np.array([0, 0, 1, 1]),
            evaluation=EVALUATION,
            evaluations=100,
            cache_hits=0,
            checkpoints=tuple(
                ConvergenceCheckpoint(index, index, EVALUATION)
                for index in range(1, 100)
            ),
            runtime_seconds=0.1,
            termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        )


def _result_with_final_evaluation(
    final: EvaluationResult, last_checkpoint: EvaluationResult
) -> OptimizationResult:
    """Constrói um resultado cujo checkpoint 100 pode divergir da avaliação final."""

    checkpoints = tuple(
        ConvergenceCheckpoint(
            index, index, last_checkpoint if index == 100 else EVALUATION
        )
        for index in range(1, 101)
    )
    return OptimizationResult(
        algorithm="aco_gpu",
        k=2,
        seed=1,
        budget=100,
        weights=ObjectiveWeights(),
        solution=np.array([1, 1, 0, 0]),
        evaluation=final,
        evaluations=100,
        cache_hits=0,
        checkpoints=checkpoints,
        runtime_seconds=0.25,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={},
    )


def test_result_rejects_final_evaluation_that_diverges_from_last_checkpoint() -> None:
    """Caso negativo da guarda que a tolerância de `1e-12` deixava passar.

    A tabela principal da seção 9 e a tabela de checkpoints da seção 27 descrevem
    a mesma execução e precisam carregar o mesmo número. Com
    `math.isclose(rel_tol=1e-12, abs_tol=1e-12)` uma divergência de `9e-13`
    passava, e `to_dict` exportava `0x1.0000000003f55p-2` num lugar contra
    `0x1.0000000000000p-2` no outro. O cenário abaixo é o reproduzido pelo
    verificador, no caminho GPU, onde os dois objetos são distintos por
    construção.
    """

    checkpoint = EvaluationResult(0.25, 0.1, 0.2, 0.3, 0.4, 0.11, 0.22)
    final = EvaluationResult(0.25 + 9e-13, 0.1, 0.2, 0.3, 0.4, 0.11, 0.22)
    assert final.total_cost.hex() != checkpoint.total_cost.hex()
    with pytest.raises(
        ConfigurationError, match="avaliação final diverge do último checkpoint"
    ):
        _result_with_final_evaluation(final, checkpoint)


def test_result_accepts_final_evaluation_identical_to_last_checkpoint() -> None:
    """Caso positivo: valores iguais bit a bit em objetos distintos são aceitos.

    Garante que o aperto da guarda recusa a divergência sem passar a exigir
    identidade de objeto, que o caminho GPU não tem.
    """

    checkpoint = EvaluationResult(0.25, 0.1, 0.2, 0.3, 0.4, 0.11, 0.22)
    final = EvaluationResult(0.25, 0.1, 0.2, 0.3, 0.4, 0.11, 0.22)
    assert final is not checkpoint
    result = _result_with_final_evaluation(final, checkpoint)
    assert result.checkpoints[-1].evaluation.total_cost.hex() == (
        result.evaluation.total_cost.hex()
    )
