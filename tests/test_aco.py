from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from metaheuristica.aco import (
    AcoConfig,
    _ConstructedAnt,
    _EvaluatedAnt,
    _PartialConstructionState,
    _choice_probabilities,
    _construct_ant,
    _construction_choices,
    _deposit_amount,
    _heuristic_values,
    _initial_pheromone,
    _update_pheromone,
    run_aco,
)
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.metrics import RunConfig, TerminationReason
from metaheuristica.objective import _balance_totals_matrix, _evaluate_partial_assignment
from metaheuristica.problem import EvaluationResult, ObjectiveWeights


INSTANCES_DIR = Path(__file__).parents[1] / "data/instances"
TINY = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")


def _evaluation(cost: float) -> EvaluationResult:
    return EvaluationResult(cost, cost, 0.0, 0.0, 0.0, cost, 0.0)


def test_aco_config_is_immutable_and_has_no_defaults() -> None:
    config = AcoConfig(1, 2, 0.1, 20)
    assert config.alpha == 1.0
    assert config.beta == 2.0
    with pytest.raises(FrozenInstanceError):
        config.rho = 0.3  # type: ignore[misc]
    with pytest.raises(TypeError):
        AcoConfig()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("alpha", 0.0),
        ("alpha", float("nan")),
        ("beta", -1.0),
        ("beta", float("inf")),
        ("rho", 0.0),
        ("rho", 1.0),
        ("rho", float("nan")),
        ("n_ants", 0),
        ("n_ants", True),
    ],
)
def test_aco_config_rejects_invalid_values(field: str, value: object) -> None:
    values: dict[str, object] = {"alpha": 1.0, "beta": 1.0, "rho": 0.1, "n_ants": 20}
    values[field] = value
    with pytest.raises(ConfigurationError):
        AcoConfig(**values)  # type: ignore[arg-type]


def test_construction_choices_follow_restricted_growth_and_force_openings() -> None:
    assert _construction_choices([], n_units=5, k=3).allowed == (0,)
    assert _construction_choices([], n_units=5, k=3).forced
    assert _construction_choices([0], n_units=5, k=3).allowed == (0, 1)
    assert not _construction_choices([0], n_units=5, k=3).forced
    forced = _construction_choices([0, 0, 0], n_units=5, k=3)
    assert forced.allowed == (1,)
    assert forced.forced
    assert _construction_choices([0, 0, 0, 1], n_units=5, k=3).allowed == (2,)


@pytest.mark.parametrize("prefix", [[1], [0, 2], [0, 0, 0, 0]])
def test_construction_rejects_noncanonical_or_infeasible_prefix(prefix: list[int]) -> None:
    with pytest.raises(SolutionValidationError):
        _construction_choices(prefix, n_units=4, k=3)


def test_initial_pheromone_is_dense_float64_and_uniform() -> None:
    tau = _initial_pheromone(4, 2)
    assert tau.shape == (4, 2)
    assert tau.dtype == np.float64
    assert np.array_equal(tau, np.ones((4, 2)))


def test_heuristic_reuses_partial_cost_and_normalizes_best_to_two() -> None:
    prefix = (0,)
    choices = (0, 1)
    eta = _heuristic_values(
        TINY, prefix, choices, k=2, weights=ObjectiveWeights()
    )
    costs = [
        _evaluate_partial_assignment(
            TINY,
            np.arange(2),
            np.array((*prefix, choice)),
            k=2,
            weights=ObjectiveWeights(),
        ).total_cost
        for choice in choices
    ]
    assert eta[np.argmin(costs)] == pytest.approx(2.0, abs=1e-12)
    assert eta[np.argmax(costs)] == pytest.approx(1.0, abs=1e-12)
    assert np.all((eta >= 1.0) & (eta <= 2.0))


@pytest.mark.parametrize(
    ("size", "k", "prefix"),
    [
        (20, 3, (0, 0, 0, 1, 0, 0, 0, 2)),
        (20, 5, (0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1)),
        (60, 8, tuple(index % 8 for index in range(40))),
    ],
)
def test_incremental_partial_state_is_equivalent_within_tolerance(
    size: int, k: int, prefix: tuple[int, ...]
) -> None:
    """F4-5: a equivalência é da grandeza, não dos bits.

    `_PartialConstructionState` acumula os cortes linha a linha, na ordem da
    construção, enquanto `_evaluate_partial_assignment` soma o triângulo
    superior numa única redução. As duas ordens de somatório diferem em até
    um ULP, e a versão anterior deste teste afirmava igualdade exata dos sete
    campos apoiada num único caso de três unidades com `K=2`. Manter aquela
    afirmação induziria a onda de correção a usar um oráculo errado: o oráculo
    da construção do ACO é a própria construção anterior, comparada por
    `float.hex()`, que é o que
    `test_batched_choice_costs_reproduce_the_reference_bit_by_bit` fixa.
    """

    instance = load_artesp_instance(INSTANCES_DIR, size)
    state = _PartialConstructionState(instance, k=k, weights=ObjectiveWeights())
    for lot in prefix[:-1]:
        state.append(lot)
    incremental = state.evaluate_choice(prefix[-1])
    common = _evaluate_partial_assignment(
        instance,
        np.arange(len(prefix)),
        np.array(prefix),
        k=k,
        weights=ObjectiveWeights(),
    )
    for field in (
        "total_cost", "c_demand", "c_production", "c_territorial", "c_affinity",
        "cv_demand", "cv_production",
    ):
        assert getattr(incremental, field) == pytest.approx(
            getattr(common, field), abs=1e-12
        ), field


def _construction_walk(instance, k: int, *, seed: int):
    """Percorre uma construção real e devolve as escolhas abertas por posição."""

    rng = np.random.default_rng(seed)
    state = _PartialConstructionState(instance, k=k, weights=ObjectiveWeights())
    prefix: list[int] = []
    for _ in range(instance.n_units):
        available = _construction_choices(prefix, n_units=instance.n_units, k=k)
        if not available.forced:
            yield state, available.allowed
        selected = int(rng.choice(available.allowed))
        prefix.append(selected)
        state.append(selected)


WALKED = [(TINY, 2), (TINY, 3)]
WALKED += [(20, k) for k in range(2, 13)]
WALKED += [(60, k) for k in range(2, 13)]
WALKED += [(150, k) for k in (3, 8, 12)]


@pytest.mark.parametrize(("source", "k"), WALKED)
def test_batched_choice_costs_reproduce_the_reference_bit_by_bit(
    source: object, k: int
) -> None:
    """Oráculo de identidade da variante O4, item B2 do Apêndice B do registro.

    `_PartialConstructionState.evaluate_choice` é a implementação anterior,
    preservada intacta como referência normativa. `choice_costs` é a variante
    O4, que monta a matriz `(m, K)` contígua e reduz com `np.add.reduce`. A
    comparação é por `float.hex()`, sobre construções reais, porque a alegação
    inteira do achado F4-1 é a preservação dos bits.
    """

    instance = source if source is TINY else load_artesp_instance(INSTANCES_DIR, source)
    compared = 0
    for state, choices in _construction_walk(instance, k, seed=k):
        expected = [state.evaluate_choice(lot).total_cost for lot in choices]
        obtained = state.choice_costs(choices)
        assert obtained.dtype == np.float64
        assert obtained.shape == (len(choices),)
        for reference, batched in zip(expected, obtained):
            assert reference.hex() == float(batched).hex()
            compared += 1
    assert compared > 0


def _cv_from_matrix(
    matrix: np.ndarray, *, ddof: int = 0, blas: bool = False, fortran: bool = False
):
    """Réplica local da redução, com os desvios usados pelos controles negativos."""

    count = matrix.shape[1]
    means = np.add.reduce(matrix, axis=1) / count
    deviations = np.subtract(matrix, means[:, np.newaxis])
    if fortran:
        deviations = np.asfortranarray(deviations)
    np.square(deviations, out=deviations)
    if blas:
        totals = deviations @ np.ones(count, dtype=np.float64)
    else:
        totals = np.add.reduce(deviations, axis=1)
    return np.sqrt(totals / (count - ddof)) / means


def _balance_matrices(instance, k: int, *, seed: int) -> list[np.ndarray]:
    matrices: list[np.ndarray] = []
    for state, choices in _construction_walk(instance, k, seed=seed):
        unit_index = len(state.labels)
        matrix = np.empty((len(choices), k), dtype=np.float64, order="C")
        matrix[:] = state.demand_totals
        matrix[np.arange(len(choices)), list(choices)] += instance.demand[unit_index]
        matrices.append(matrix)
    return matrices


def _count_divergences(matrices: list[np.ndarray], **kwargs) -> tuple[int, int]:
    divergent = 0
    total = 0
    for matrix in matrices:
        expected = _balance_totals_matrix(matrix)[1]
        obtained = _cv_from_matrix(matrix, **kwargs)
        for left, right in zip(expected, obtained):
            total += 1
            divergent += float(left).hex() != float(right).hex()
    return divergent, total


def test_negative_controls_prove_the_comparator_detects_divergence() -> None:
    """Sem controle negativo, ausência de divergência não significaria nada.

    Os dois controles são os que sustentaram a verificação adversarial da F4:
    `ddof=1` tem de divergir em toda linha, e o produto por BLAS tem de divergir
    em parte delas. O agregado é sobre `K` de 2 a 12 porque o produto por BLAS
    coincide com a redução em pares nos `K` pequenos, e um controle preso a um
    único `K` poderia parar de discriminar sem que ninguém notasse. Se algum dos
    dois deixar de divergir, o comparador por `float.hex()` perdeu sensibilidade
    e o oráculo de identidade perdeu o valor.
    """

    instance = load_artesp_instance(INSTANCES_DIR, 60)
    matrices = [
        matrix for k in range(2, 13) for matrix in _balance_matrices(instance, k, seed=k)
    ]
    assert matrices
    divergent_ddof, total = _count_divergences(matrices, ddof=1)
    divergent_blas, _ = _count_divergences(matrices, blas=True)
    assert divergent_ddof == total
    assert divergent_blas > 0


def test_balance_matrix_refuses_memory_that_is_not_c_contiguous() -> None:
    """Guarda-corpo obrigatório: a identidade bit a bit depende de ordem C.

    Construída em ordem Fortran, a mesma matriz reduzida em `axis=1` diverge da
    redução linha a linha. Sem a asserção na implementação real, uma refatoração
    futura que produza a matriz por transposição ou com `order="F"` quebraria a
    identidade em silêncio, sem que teste algum reclamasse.
    """

    instance = load_artesp_instance(INSTANCES_DIR, 60)
    matrices = _balance_matrices(instance, 8, seed=8)
    fortran = np.asfortranarray(matrices[-1])
    assert not fortran.flags["C_CONTIGUOUS"]
    assert np.array_equal(fortran, matrices[-1])
    with pytest.raises(AssertionError, match="ordem C"):
        _balance_totals_matrix(fortran)
    divergent, total = _count_divergences(matrices, fortran=True)
    assert total > 0
    assert divergent > 0


def test_probability_formula_is_normalized_and_reflects_alpha_beta() -> None:
    neutral = _choice_probabilities([1.0, 1.0], [1.0, 2.0], alpha=1.0, beta=1.0)
    stronger_eta = _choice_probabilities(
        [1.0, 1.0], [1.0, 2.0], alpha=1.0, beta=2.0
    )
    stronger_tau = _choice_probabilities(
        [1.0, 2.0], [1.0, 1.0], alpha=2.0, beta=1.0
    )
    assert np.sum(neutral) == pytest.approx(1.0, abs=1e-12)
    assert stronger_eta[1] > neutral[1]
    assert stronger_tau[1] > 0.5


def test_probability_formula_is_stable_for_extreme_positive_values() -> None:
    probabilities = _choice_probabilities(
        [1e-300, 1e300], [1.0, 2.0], alpha=2.0, beta=2.0
    )
    assert np.isfinite(probabilities).all()
    assert probabilities.sum() == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("tau", "eta"),
    [([0.0, 1.0], [1.0, 1.0]), ([1.0, np.inf], [1.0, 1.0]), ([1.0], [1.0, 2.0])],
)
def test_probability_formula_rejects_invalid_inputs(
    tau: list[float], eta: list[float]
) -> None:
    with pytest.raises(ConfigurationError):
        _choice_probabilities(tau, eta, alpha=1.0, beta=1.0)


def test_constructed_ant_is_canonical_viable_and_reproducible() -> None:
    config = AcoConfig(1, 1, 0.1, 20)
    tau = _initial_pheromone(TINY.n_units, 2)
    first = _construct_ant(
        TINY,
        k=2,
        weights=ObjectiveWeights(),
        tau=tau,
        config=config,
        rng=np.random.default_rng(7),
    )
    second = _construct_ant(
        TINY,
        k=2,
        weights=ObjectiveWeights(),
        tau=tau,
        config=config,
        rng=np.random.default_rng(7),
    )
    assert np.array_equal(first.solution, second.solution)
    assert first.solution[0] == 0
    assert len(set(first.solution)) == 2
    assert first.forced_assignments + first.probabilistic_assignments == TINY.n_units
    assert np.array_equal(tau, np.ones_like(tau))


def test_forced_choice_does_not_consume_rng() -> None:
    first = np.random.default_rng(99)
    second = np.random.default_rng(99)
    state = deepcopy(first.bit_generator.state)
    choice = _construction_choices([], n_units=4, k=2)
    assert choice.forced
    assert first.bit_generator.state == state
    assert first.bit_generator.random_raw() == second.bit_generator.random_raw()


def test_deposit_amount_handles_boundaries_and_tolerance() -> None:
    assert _deposit_amount(0.0) == 1.0
    assert _deposit_amount(1.0) == 0.0
    assert _deposit_amount(1.0 + 5e-13) == 0.0
    with pytest.raises(ConfigurationError):
        _deposit_amount(1.0 + 2e-12)


def test_pheromone_update_evaporates_then_sums_every_ant_deposit() -> None:
    tau = np.ones((4, 2), dtype=np.float64)
    ants = (
        _EvaluatedAnt(np.array([0, 0, 1, 1]), _evaluation(0.0)),
        _EvaluatedAnt(np.array([0, 1, 0, 1]), _evaluation(0.5)),
    )
    updated = _update_pheromone(tau, ants, rho=0.1)
    expected = np.full((4, 2), 0.9)
    expected[np.arange(4), ants[0].solution] += 1.0
    expected[np.arange(4), ants[1].solution] += 0.5
    assert np.array_equal(updated, expected)
    assert np.array_equal(tau, np.ones((4, 2)))


def test_aco_runs_to_budget_and_produces_coherent_diagnostics() -> None:
    result = run_aco(
        TINY,
        RunConfig(k=2, seed=7, budget=100),
        AcoConfig(alpha=1, beta=1, rho=0.1, n_ants=20),
    )
    assert result.algorithm == "aco"
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert result.diagnostics["ants_evaluated"] == 100
    assert result.diagnostics["generations_completed"] == 5
    assert result.diagnostics["pheromone_updates"] == 5
    assert result.diagnostics["forced_assignments"] + result.diagnostics[
        "probabilistic_assignments"
    ] == 100 * TINY.n_units


def test_partial_generation_does_not_update_pheromone() -> None:
    complete = run_aco(
        TINY,
        RunConfig(k=2, seed=3, budget=100),
        AcoConfig(1, 1, 0.1, 20),
    )
    partial = run_aco(
        TINY,
        RunConfig(k=2, seed=3, budget=103),
        AcoConfig(1, 1, 0.1, 20),
    )
    assert partial.diagnostics["ants_evaluated"] == 103
    assert partial.diagnostics["generations_completed"] == 5
    assert partial.diagnostics["pheromone_updates"] == 5
    assert partial.diagnostics["final_tau_min"] == complete.diagnostics["final_tau_min"]
    assert partial.diagnostics["final_tau_max"] == complete.diagnostics["final_tau_max"]


def test_aco_is_reproducible_except_for_runtime() -> None:
    run = RunConfig(k=2, seed=11, budget=100)
    config = AcoConfig(1, 2, 0.3, 20)
    first = run_aco(TINY, run, config)
    second = run_aco(TINY, run, config)
    assert first.reproducible_data() == second.reproducible_data()
