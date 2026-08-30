from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from metaheuristica.errors import (
    ConfigurationError,
    EvaluationLimitReached,
    SolutionValidationError,
)
from metaheuristica.evaluator import FitnessEvaluator
from metaheuristica.instances import load_tiny_instance
from metaheuristica.metrics import ConvergenceRecorder, RunConfig, TerminationReason
from metaheuristica.optimizer import OptimizationContext, execute_optimizer


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")


@dataclass(frozen=True)
class DummyConfig:
    cycle_size: int = 7


def _search(context: OptimizationContext, config: DummyConfig) -> None:
    solutions = ([0, 0, 1, 1], [0, 1, 0, 1], [0, 1, 1, 0])
    cycle_position = 0
    context.update_diagnostics(
        rng_fingerprint=int(context.rng.bit_generator.random_raw())
    )
    while True:
        context.update_diagnostics(cycle_position=cycle_position)
        index = int(context.rng.integers(0, len(solutions)))
        context.evaluate(solutions[index])
        cycle_position = (cycle_position + 1) % config.cycle_size


def test_execute_optimizer_exhausts_budget_and_builds_all_checkpoints() -> None:
    result = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=7, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert result.solution.flags.writeable is False
    assert result.diagnostics["cycle_position"] == 1


def test_context_exposes_common_incumbent_as_read_only_state() -> None:
    observed: list[tuple[tuple[int, ...], float]] = []

    def search(context: OptimizationContext, config: None) -> None:
        assert context.incumbent_solution is None
        assert context.incumbent_evaluation is None
        context.evaluate([0, 0, 1, 1])
        assert context.incumbent_solution == (0, 0, 1, 1)
        assert context.incumbent_evaluation is not None
        observed.append(
            (context.incumbent_solution, context.incumbent_evaluation.total_cost)
        )
        while True:
            context.evaluate([0, 1, 0, 1])

    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        None,
        algorithm="incumbent_test",
        search=search,
    )
    assert observed == [((0, 0, 1, 1), 0.0)]


def test_context_exposes_instance_and_k_as_read_only_properties() -> None:
    observed: list[tuple[object, int]] = []

    def search(context: OptimizationContext, config: None) -> None:
        observed.append((context.instance, context.k))
        with pytest.raises(AttributeError):
            context.k = 3  # type: ignore[misc]
        while True:
            context.evaluate([0, 0, 1, 1])

    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        None,
        algorithm="context_properties",
        search=search,
    )
    assert observed == [(TINY, 2)]


def test_last_completed_evaluation_is_available_on_limit_signal() -> None:
    observed: list[float] = []

    def search(context: OptimizationContext, config: None) -> None:
        while True:
            try:
                context.evaluate([0, 0, 1, 1])
            except EvaluationLimitReached as exhausted:
                observed.append(exhausted.result.total_cost)
                raise

    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        None,
        algorithm="limit_result_test",
        search=search,
    )
    assert observed == [0.0]


def test_same_seed_reproduces_all_deterministic_fields() -> None:
    arguments = (TINY, RunConfig(k=2, seed=9, budget=100), DummyConfig())
    first = execute_optimizer(*arguments, algorithm="dummy", search=_search)
    second = execute_optimizer(*arguments, algorithm="dummy", search=_search)
    assert first.reproducible_data() == second.reproducible_data()


def test_different_seeds_produce_different_local_rng_streams() -> None:
    first = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    second = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=6, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert first.diagnostics["rng_fingerprint"] != second.diagnostics["rng_fingerprint"]


def test_optimizer_does_not_change_numpy_global_rng_state() -> None:
    np.random.seed(123)
    expected = np.random.random(3)
    np.random.seed(123)
    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
    )
    assert np.array_equal(np.random.random(3), expected)


def test_clock_excludes_final_validation_and_serialization() -> None:
    ticks = iter((10.0, 12.5))
    result = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        DummyConfig(),
        algorithm="dummy",
        search=_search,
        clock=lambda: next(ticks),
    )
    assert result.runtime_seconds == 2.5


def test_algorithm_ending_early_is_rejected() -> None:
    def early(context: OptimizationContext, config: None) -> None:
        context.evaluate([0, 0, 1, 1])

    with pytest.raises(ConfigurationError, match="antes de esgotar"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="early",
            search=early,
        )


def test_nonbudget_algorithm_error_is_propagated() -> None:
    def broken(context: OptimizationContext, config: None) -> None:
        raise SolutionValidationError("erro real")

    with pytest.raises(SolutionValidationError, match="erro real"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="broken",
            search=broken,
        )


def test_budget_without_viable_incumbent_is_explicit_error() -> None:
    def provisional(context: OptimizationContext, config: None) -> None:
        while True:
            context.evaluate_provisional_for_repair([0, 0, 0, 0])

    with pytest.raises(ConfigurationError, match="incumbente"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="provisional",
            search=provisional,
        )


def test_finalize_fecha_a_contabilidade_antes_de_a_fronteira_propagar() -> None:
    """B21, parte 1: o ponto de fechamento roda antes de `_stop_at_limit`.

    `_stop_at_limit` levanta `EvaluationLimitReached` **depois** de a avaliação
    ter sido consumida, e tudo o que o chamador escreveria depois da chamada é
    perdido. É essa perda que produz F1-04, A5 e F5-3, cada um observado por uma
    frente diferente. O contrato novo dá ao chamador um ponto de fechamento
    executado depois da avaliação e antes do teste de fronteira.

    A rotina de brinquedo consome exatamente o orçamento e registra os dois
    lados do ponto de levantamento. O oráculo é a assimetria entre as duas
    contagens: o fechamento roda nas 100 avaliações, e o que vem depois da
    chamada roda em 99, porque na centésima a exceção propaga.
    """

    registro: list[str] = []

    def search(context: OptimizationContext, config: None) -> None:
        while True:
            context.evaluate([0, 0, 1, 1], finalize=lambda: registro.append("fecha"))
            registro.append("depois")

    resultado = execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        None,
        algorithm="contrato",
        search=search,
    )

    assert resultado.evaluations == 100
    assert registro.count("fecha") == 100
    assert registro.count("depois") == 99
    assert registro[-1] == "fecha"


def test_finalize_tambem_existe_na_avaliacao_provisoria_do_reparo() -> None:
    """O contrato é dos dois métodos de avaliação, e não só do principal.

    O reparo consome orçamento por `evaluate_provisional_for_repair`, logo a
    última avaliação de uma execução pode ser consumida ali. Sem o ponto de
    fechamento nesse método, o mesmo defeito de contrato sobrevive no caminho
    do reparo.
    """

    registro: list[str] = []

    def search(context: OptimizationContext, config: None) -> None:
        while True:
            context.evaluate_provisional_for_repair(
                [0, 0, 1, 1], finalize=lambda: registro.append("fecha")
            )
            registro.append("depois")

    execute_optimizer(
        TINY,
        RunConfig(k=2, seed=1, budget=100),
        None,
        algorithm="contrato_reparo",
        search=search,
    )

    assert registro.count("fecha") == 100
    assert registro.count("depois") == 99
    assert registro[-1] == "fecha"


def test_finalize_nao_chamavel_e_recusado() -> None:
    """O ponto de fechamento é um contrato, e contrato mal formado é erro."""

    def search(context: OptimizationContext, config: None) -> None:
        context.evaluate([0, 0, 1, 1], finalize=42)  # type: ignore[arg-type]

    with pytest.raises(ConfigurationError, match="finalize deve ser chamável"):
        execute_optimizer(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            None,
            algorithm="contrato_invalido",
            search=search,
        )


class _AvaliadorComFronteiraAntecipada(FitnessEvaluator):
    """Avaliador que fecha a fronteira com o contador longe do orçamento.

    No caminho real `remaining` é `budget - evaluations`, logo quando ele chega
    a zero os dois números são o mesmo e a interpolação duplicada de F1-04 fica
    **invisível**: a mensagem defeituosa imprime `100/100` exatamente como a
    correta imprimiria. É por isso que o diff de F1-04 na impressão digital é
    zero e este caso é o único oráculo do achado. Separar os dois números é a
    única forma de observar o defeito, e é o que esta subclasse faz.
    """

    __slots__ = ()

    @property
    def remaining(self) -> int:
        return 0 if self.evaluations >= 1 else super().remaining


def test_a_mensagem_da_fronteira_traz_o_orcamento_no_denominador() -> None:
    """F1-04: `optimizer.py:103` interpolava `evaluations` nos dois lados."""

    run_config = RunConfig(k=2, seed=1, budget=140)
    evaluator = _AvaliadorComFronteiraAntecipada(TINY, k=2, budget=140)
    recorder = ConvergenceRecorder(run_config.thresholds)
    context = OptimizationContext(
        evaluator, np.random.Generator(np.random.PCG64(1)), recorder
    )

    with pytest.raises(EvaluationLimitReached) as levantada:
        context.evaluate([0, 0, 1, 1])

    # A propriedade que torna o caso discriminante, asseverada aqui dentro: os
    # dois lados da barra são números diferentes neste cenário.
    assert evaluator.evaluations == 1
    assert evaluator.budget == 140
    assert "1/140 avaliações" in str(levantada.value)
