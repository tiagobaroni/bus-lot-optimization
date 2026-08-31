from __future__ import annotations

import os
import subprocess
import sys
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
    _AcoDiagnostics,
    _choices_from_counts,
)
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.metrics import RunConfig, TerminationReason
from metaheuristica import objective as objective_module
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
    redução linha a linha. Sem a recusa na implementação real, uma refatoração
    futura que produza a matriz por transposição ou com `order="F"` quebraria a
    identidade em silêncio, sem que teste algum reclamasse.
    """

    instance = load_artesp_instance(INSTANCES_DIR, 60)
    matrices = _balance_matrices(instance, 8, seed=8)
    fortran = np.asfortranarray(matrices[-1])
    assert not fortran.flags["C_CONTIGUOUS"]
    assert np.array_equal(fortran, matrices[-1])
    with pytest.raises(objective_module.MemoryLayoutError, match="ordem C"):
        _balance_totals_matrix(fortran)
    divergent, total = _count_divergences(matrices, fortran=True)
    assert total > 0
    assert divergent > 0


_PREAMBULO_DA_SONDA = """
import numpy as np

import metaheuristica.objective as objective

try:
    assert False, "sentinela anti-vacuo"
except AssertionError:
    print("OTIMIZACAO=nao")
else:
    print("OTIMIZACAO=sim")

print("MODULO=" + objective.__file__)
"""


def _sonda_otimizada(corpo: str) -> dict[str, str]:
    """Roda `corpo` num subprocesso com `-O` e devolve os marcadores impressos.

    O caminho de importação sai do módulo que este processo já carregou, e não
    de uma raiz fixa, para que uma execução sobre cópia carregue a cópia. O
    marcador `MODULO` prende isso na própria sonda.
    """

    raiz = Path(objective_module.__file__).parents[1]
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(raiz)
    concluido = subprocess.run(
        [sys.executable, "-O", "-c", _PREAMBULO_DA_SONDA + corpo],
        capture_output=True,
        text=True,
        env=ambiente,
        check=False,
    )
    assert concluido.returncode == 0, concluido.stderr
    marcadores = dict(
        linha.split("=", 1)
        for linha in concluido.stdout.splitlines()
        if "=" in linha
    )
    # Metade anti-vácuo, dentro do próprio caso: um subprocesso que não
    # estivesse otimizado faria o caso passar sem exercitar nada, porque o
    # `assert` antigo também recusaria. O `assert` trivialmente falso do
    # preâmbulo não pode levantar aqui.
    assert marcadores["OTIMIZACAO"] == "sim"
    assert marcadores["MODULO"] == objective_module.__file__
    return marcadores


def test_input_matrix_refusal_survives_optimized_mode() -> None:
    """A recusa da matriz de entrada sobrevive a `python -O`, e o `assert` não sobreviveria.

    Em modo normal `assert` e `raise` falham igual, de modo que trocar um pelo
    outro não é observável por teste algum. O que os separa é `python -O`, que
    **remove** o `assert` e mantém o `raise`. Medido contra a forma anterior,
    este mesmo corpo imprimia `RECUSA=nenhuma`.
    """

    marcadores = _sonda_otimizada(
        """
matriz = np.asfortranarray(np.arange(12, dtype=np.float64).reshape(3, 4) + 1.0)
print("NAO_CONTIGUA=" + str(not matriz.flags["C_CONTIGUOUS"]))
try:
    objective._balance_totals_matrix(matriz)
except objective.MemoryLayoutError as erro:
    print("RECUSA=" + type(erro).__name__)
    print("MENSAGEM=" + str(erro))
else:
    print("RECUSA=nenhuma")
"""
    )
    assert marcadores["NAO_CONTIGUA"] == "True"
    assert marcadores["RECUSA"] == "MemoryLayoutError"
    assert "matriz de entrada" in marcadores["MENSAGEM"]


def test_deviation_matrix_refusal_survives_optimized_mode() -> None:
    """A recusa dos desvios sobrevive a `python -O`, e é alcançada por injeção.

    Com a entrada contígua em ordem C, `np.subtract` devolve sempre um arranjo
    contíguo em ordem C, de modo que a segunda recusa é **inalcançável por
    entrada**: ela guarda uma refatoração futura, não um dado de hoje. O caso
    encena essa refatoração, fazendo `np.subtract` devolver ordem Fortran, e
    exige que a recusa dispare mesmo sob otimização. A mensagem distingue as
    duas recusas, o que impede que a primeira passe por esta.
    """

    marcadores = _sonda_otimizada(
        """
matriz = np.ascontiguousarray(np.arange(12, dtype=np.float64).reshape(3, 4) + 1.0)
print("ENTRADA_CONTIGUA=" + str(matriz.flags["C_CONTIGUOUS"]))
original = np.subtract
np.subtract = lambda a, b: np.asfortranarray(original(a, b))
try:
    print("INJECAO_NAO_C=" + str(not np.subtract(matriz, matriz).flags["C_CONTIGUOUS"]))
    try:
        objective._balance_totals_matrix(matriz)
    except objective.MemoryLayoutError as erro:
        print("RECUSA=" + type(erro).__name__)
        print("MENSAGEM=" + str(erro))
    else:
        print("RECUSA=nenhuma")
finally:
    np.subtract = original
"""
    )
    assert marcadores["ENTRADA_CONTIGUA"] == "True"
    assert marcadores["INJECAO_NAO_C"] == "True"
    assert marcadores["RECUSA"] == "MemoryLayoutError"
    assert "matriz de desvios" in marcadores["MENSAGEM"]


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


ABORT_GENERATIONS = ((0.5, 1075), (0.6, 814), (0.9, 324))


def _covering_ants() -> tuple[_EvaluatedAnt, ...]:
    """Formigas que juntas depositam nas sete células alcançáveis de 4 por 2."""

    return (
        _EvaluatedAnt(np.array([0, 0, 1, 1]), _evaluation(0.25)),
        _EvaluatedAnt(np.array([0, 1, 0, 1]), _evaluation(0.75)),
        _EvaluatedAnt(np.array([0, 1, 1, 0]), _evaluation(0.5)),
    )


@pytest.mark.parametrize(("rho", "generations"), ABORT_GENERATIONS)
def test_evaporation_floor_keeps_high_rho_runs_alive(
    rho: float, generations: int
) -> None:
    """F4-3: sem piso, a evaporação pura chegava a zero e matava a execução."""

    # Alvo do teste, asseverado aqui para que ele não perca o alvo numa edição
    # futura: a geração escolhida é exatamente a primeira em que a evaporação
    # pura de uma célula com j > i produziria zero se não houvesse piso.
    evaporated = 1.0
    for _ in range(generations - 1):
        evaporated *= 1.0 - rho
    assert evaporated > 0.0
    assert evaporated * (1.0 - rho) == 0.0

    result = run_aco(
        TINY,
        RunConfig(k=2, seed=7, budget=generations),
        AcoConfig(alpha=1, beta=1, rho=rho, n_ants=1),
    )
    assert result.diagnostics["generations_completed"] == generations
    assert result.termination_reason is TerminationReason.BUDGET_EXHAUSTED
    assert result.evaluations == generations


def _update_pheromone_without_floor(
    tau: np.ndarray, ants: tuple[_EvaluatedAnt, ...], *, rho: float
) -> np.ndarray:
    """Réplica de `_update_pheromone` sem o piso, para servir de controle."""

    updated = np.array(tau * (1.0 - rho), dtype=np.float64, copy=True)
    rows = np.arange(tau.shape[0], dtype=np.int64)
    for ant in ants:
        updated[rows, ant.solution] += _deposit_amount(ant.evaluation.total_cost)
    return updated


def _hex_matrix(matrix: np.ndarray) -> list[str]:
    return [float(value).hex() for value in np.ravel(matrix)]


@pytest.mark.parametrize("rho", [0.1, 0.3])
def test_evaporation_floor_moves_no_bit_on_the_frozen_grid(rho: float) -> None:
    """F4-3: o piso é inerte na campanha congelada e na grade de tuning."""

    ants = _covering_ants()
    floored = _initial_pheromone(4, 2)
    floorless = _initial_pheromone(4, 2)
    for _ in range(50):
        floored = _update_pheromone(floored, ants, rho=rho)
        floorless = _update_pheromone_without_floor(floorless, ants, rho=rho)
    assert _hex_matrix(floored) == _hex_matrix(floorless)

    # Regime de saturação, que é o pior caso de `rho` de 0,1 e 0,3: mesmo com a
    # célula já no menor subnormal o piso continua inerte, porque a
    # multiplicação arredonda de volta para o próprio subnormal.
    subnormal = float(np.nextafter(0.0, 1.0))
    saturated = _initial_pheromone(4, 2)
    saturated[0, 1] = subnormal
    assert _hex_matrix(_update_pheromone(saturated, ants, rho=rho)) == _hex_matrix(
        _update_pheromone_without_floor(saturated, ants, rho=rho)
    )

    # Controle negativo, na mesma execução e com o mesmo comparador. Uma
    # asserção de igualdade de bits só discrimina se existir vizinho em que os
    # bits se movem: com `rho = 0.5` o subnormal cai exatamente no meio, o
    # arredondamento para par o leva a zero sem o piso, e as duas matrizes
    # divergem na célula (0, 1), de índice 1 no arranjo achatado.
    moved = _update_pheromone(saturated, ants, rho=0.5)
    unfloored = _update_pheromone_without_floor(saturated, ants, rho=0.5)
    assert _hex_matrix(moved) != _hex_matrix(unfloored)
    assert _hex_matrix(unfloored)[1] == (0.0).hex()
    assert _hex_matrix(moved)[1] == subnormal.hex()


def test_final_tau_min_ignores_structurally_unreachable_cells() -> None:
    """F4-4: o mínimo publicado media evaporação pura, e não o feromônio real."""

    rho = 0.1
    result = run_aco(
        TINY,
        RunConfig(k=2, seed=7, budget=1000),
        AcoConfig(alpha=1, beta=1, rho=rho, n_ants=20),
    )
    generations = result.diagnostics["generations_completed"]
    assert generations == 50
    evaporated = 1.0
    for _ in range(generations):
        evaporated *= 1.0 - rho
    # Toda célula com j > i vale exatamente a evaporação pura, porque nunca
    # recebe depósito. O mínimo publicado tem de ficar estritamente acima dela.
    assert result.diagnostics["final_tau_min"] > (1.0 - rho) ** generations
    assert result.diagnostics["final_tau_min"] > evaporated

    # E a célula inalcançável existe mesmo, abaixo do mínimo alcançável. A
    # máscara é recalculada aqui de forma independente, para que o teste não
    # compare a produção consigo mesma.
    tau = _initial_pheromone(4, 2)
    ants = _covering_ants()
    for _ in range(generations):
        tau = _update_pheromone(tau, ants, rho=rho)
    reachable = np.tril(np.ones(tau.shape, dtype=bool))
    assert not reachable[0, 1]
    # O fixture só discrimina se todas as células alcançáveis receberem ao
    # menos um depósito; sem isto alguma delas ficaria na evaporação pura e a
    # comparação abaixo passaria a ser entre dois valores iguais.
    assert bool((tau[reachable] > evaporated).all())
    assert float(np.min(tau)) == float(tau[0, 1]) == evaporated
    assert float(np.min(tau)) < float(np.min(tau[reachable]))


def _reachable_cells(n_units: int, k: int) -> set[tuple[int, int]]:
    """Células que a construção de crescimento restrito pode depositar.

    Enumeradas propagando os estados de `opened` possíveis a partir de
    `_choices_from_counts`, que é a mesma aritmética que a construção usa. Não
    reproduz a máscara da produção: deriva a propriedade que ela deveria ter.
    """

    cells: set[tuple[int, int]] = set()
    states = {0}
    for filled in range(n_units):
        following = set()
        for opened in states:
            allowed = _choices_from_counts(
                filled=filled, opened=opened, n_units=n_units, k=k
            ).allowed
            for lot in allowed:
                cells.add((filled, int(lot)))
                following.add(max(opened, int(lot) + 1))
        states = following
    return cells


def test_published_minimum_uses_exactly_the_reachable_mask() -> None:
    """A máscara de produção não pode alargar **nem estreitar**.

    O caso anterior prende só o teto: asseverar que o mínimo publicado fica
    acima da evaporação pura fica mais fácil, e não mais difícil, quando a
    máscara encolhe. Estreitá-la descartando a diagonal principal, que são as
    células mais depositadas da matriz, muda o valor publicado e passava
    despercebido pela suíte inteira. Este caso prende os dois lados, comparando
    a máscara que a produção constrói com a enumeração independente das células
    que a construção pode alcançar.

    A comparação é com `K < n_units`. Nessa faixa, e só nela, o triângulo
    inferior coincide exatamente com o conjunto alcançável; ver o caso seguinte.
    """

    capturadas: list[np.ndarray] = []
    original = _AcoDiagnostics.__init__

    def capturar(self, reachable, *args, **kwargs):
        capturadas.append(np.array(reachable, copy=True))
        return original(self, reachable, *args, **kwargs)

    n_units, k = 4, 2
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_AcoDiagnostics, "__init__", capturar)
        run_aco(
            TINY,
            RunConfig(k=k, seed=7, budget=200),
            AcoConfig(alpha=1, beta=1, rho=0.1, n_ants=4),
        )

    assert len(capturadas) == 1, "a máscara deve ser construída uma vez por execução"
    mascara = capturadas[0]
    assert mascara.shape == (n_units, k)

    esperada = _reachable_cells(n_units, k)
    obtida = {(int(i), int(j)) for i, j in np.argwhere(mascara)}
    assert obtida == esperada, (
        f"máscara alargada em {sorted(obtida - esperada)} e "
        f"estreitada em {sorted(esperada - obtida)}"
    )


def test_the_reachable_mask_is_the_lower_triangle_only_below_k_equals_n() -> None:
    """A equivalência entre triângulo inferior e alcançabilidade tem fronteira.

    Com `K == n_units`, que `validate_k` aceita, cada unidade é forçada a abrir
    o próprio lote e só a diagonal é alcançável: o triângulo inferior passa a
    conter células que nunca recebem depósito, e o mínimo publicado volta a
    medir evaporação pura. Nenhum dos 42 cenários da conferência usa essa
    configuração, e a especificação escopou a garantia a `K < n_units`, mas a
    fronteira fica asseverada aqui para não se perder.
    """

    for n_units, k in ((4, 2), (4, 3), (6, 3), (10, 9)):
        triangulo = {
            (int(i), int(j))
            for i, j in np.argwhere(np.tril(np.ones((n_units, k), dtype=bool)))
        }
        assert triangulo == _reachable_cells(n_units, k), (n_units, k)

    for n_units in (4, 5, 10):
        k = n_units
        triangulo = {
            (int(i), int(j))
            for i, j in np.argwhere(np.tril(np.ones((n_units, k), dtype=bool)))
        }
        alcancavel = _reachable_cells(n_units, k)
        assert alcancavel == {(i, i) for i in range(n_units)}
        assert triangulo > alcancavel, (
            "com K == n_units o triângulo inferior deixa de caracterizar o "
            "conjunto alcançável, e esta é a fronteira que o pacote não cobre"
        )
