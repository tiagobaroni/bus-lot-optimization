from __future__ import annotations

from dataclasses import FrozenInstanceError
from inspect import signature
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from metaheuristica import PsoConfig, RunConfig, run_pso
from metaheuristica import optimizer as optimizer_module
from metaheuristica import pso as pso_module
from metaheuristica.errors import (
    ConfigurationError,
    EvaluationLimitReached,
    SolutionValidationError,
)
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.pso import (
    VELOCITY_LIMIT,
    _Best,
    _best_comparison,
    _initial_particle,
    _Particle,
    _project_position,
    _trial_state,
    decode_position,
)
from metaheuristica.problem import EvaluationResult


TINY = load_tiny_instance(Path(__file__).parents[1] / "data/instances/tiny_manual.json")
INSTANCES = Path(__file__).parents[1] / "data/instances"


def evaluation(cost: float) -> EvaluationResult:
    return EvaluationResult(cost, cost, 0.0, 0.0, 0.0, cost, 0.0)


def test_pso_config_is_frozen_and_has_no_defaults() -> None:
    config = PsoConfig(4, 0.7, 1.5, 2.0)
    assert all(parameter.default is parameter.empty for parameter in signature(PsoConfig).parameters.values())
    with pytest.raises(FrozenInstanceError):
        config.inertia = 0.4  # type: ignore[misc]


@pytest.mark.parametrize(
    "arguments",
    [
        (0, 0.7, 1.5, 1.5),
        (True, 0.7, 1.5, 1.5),
        (2, -0.1, 1.5, 1.5),
        (2, 1.1, 1.5, 1.5),
        (2, 0.7, 0.0, 1.5),
        (2, 0.7, 1.5, float("inf")),
    ],
)
def test_pso_config_rejects_invalid_values(arguments: tuple[object, ...]) -> None:
    with pytest.raises(ConfigurationError):
        PsoConfig(*arguments)  # type: ignore[arg-type]


def test_decode_position_covers_boundaries_and_one() -> None:
    position = np.array([0.0, 0.249999, 0.25, 0.5, 0.999, 1.0], dtype=np.float64)
    assert decode_position(position, n_units=6, k=4).tolist() == [0, 0, 1, 2, 3, 3]


@pytest.mark.parametrize(
    "position",
    [
        np.array([0.0, 1.0], dtype=np.float32),
        np.array([[0.0, 1.0]], dtype=np.float64),
        np.array([0.0, np.nan], dtype=np.float64),
        np.array([-0.1, 1.0], dtype=np.float64),
    ],
)
def test_decode_position_rejects_invalid_position(position: np.ndarray) -> None:
    with pytest.raises(SolutionValidationError):
        decode_position(position, n_units=2, k=2)


def test_initial_population_is_balanced_viable_and_reproducible() -> None:
    first_rng = np.random.Generator(np.random.PCG64(17))
    second_rng = np.random.Generator(np.random.PCG64(17))
    first = [_initial_particle(11, 4, first_rng) for _ in range(3)]
    second = [_initial_particle(11, 4, second_rng) for _ in range(3)]
    for left, right in zip(first, second):
        labels = decode_position(left.position, n_units=11, k=4)
        counts = np.bincount(labels, minlength=4)
        assert counts.max() - counts.min() <= 1
        assert np.array_equal(left.position, right.position)
        assert np.array_equal(left.velocity, right.velocity)
        assert np.all((-0.5 <= left.velocity) & (left.velocity <= 0.5))
    assert not np.shares_memory(first[0].position, first[1].position)


def test_projection_preserves_internal_fraction_and_decodes_repair() -> None:
    position = np.array([0.1, 0.4, 0.8, 1.0], dtype=np.float64)
    original = decode_position(position, n_units=4, k=3)
    repaired = np.array([0, 1, 2, 2], dtype=np.int64)
    projected = _project_position(position, original, repaired, k=3)
    assert np.array_equal(decode_position(projected, n_units=4, k=3), repaired)
    original_fraction = np.clip(3 * position - original, 0.0, np.nextafter(1.0, 0.0))
    projected_fraction = 3 * projected - repaired
    assert np.allclose(projected_fraction, original_fraction, rtol=0.0, atol=5e-16)


def test_best_comparison_uses_cost_solution_and_position() -> None:
    incumbent = _Best(
        np.array([0.2, 0.8]), np.array([0, 1]), evaluation(1.0)
    )
    cheaper = _Best(np.array([0.9, 0.1]), np.array([0, 1]), evaluation(0.5))
    assert _best_comparison(cheaper, incumbent) == (True, True)
    lower_solution = _Best(
        np.array([0.9, 0.1]), np.array([0, 0]), evaluation(1.0 + 5e-13)
    )
    assert _best_comparison(lower_solution, incumbent) == (True, False)
    lower_position = _Best(
        np.array([0.1, 0.9]), np.array([0, 1]), evaluation(1.0)
    )
    assert _best_comparison(lower_position, incumbent) == (True, False)


def test_run_pso_exhausts_budget_and_produces_consistent_diagnostics() -> None:
    result = run_pso(
        TINY,
        RunConfig(k=2, seed=23, budget=100),
        PsoConfig(4, 0.7, 1.5, 1.5),
    )
    diagnostics = result.diagnostics
    assert result.algorithm == "pso"
    assert result.evaluations == 100
    assert len(result.checkpoints) == 100
    assert len(set(result.solution.tolist())) == 2
    assert diagnostics["particles_evaluated"] + diagnostics["repair_evaluations"] == 100
    assert diagnostics["iterations_completed"] >= 0


def test_run_pso_is_reproducible() -> None:
    arguments = (
        TINY,
        RunConfig(k=2, seed=5, budget=100),
        PsoConfig(3, 0.4, 2.0, 1.5),
    )
    first = run_pso(*arguments)
    second = run_pso(*arguments)
    assert first.reproducible_data() == second.reproducible_data()


def test_population_cannot_exceed_budget() -> None:
    with pytest.raises(ConfigurationError, match="exceder"):
        run_pso(
            TINY,
            RunConfig(k=2, seed=1, budget=100),
            PsoConfig(101, 0.7, 1.5, 1.5),
        )


class _ConstantRng:
    """Gerador substituto que devolve `r1` e `r2` iguais a 1.

    Serve ao cenário exato registrado na auditoria, em que os coeficientes
    aleatórios são fixados em 1 para que a aritmética do passo seja conferível à
    mão.
    """

    def random(self, shape: Any) -> np.ndarray:
        return np.ones(shape, dtype=np.float64)


def particle_with_pbest(
    position: list[float], velocity: list[float], pbest_position: list[float]
) -> _Particle:
    particle = _Particle(
        np.array(position, dtype=np.float64), np.array(velocity, dtype=np.float64)
    )
    particle.pbest = _Best(
        np.array(pbest_position, dtype=np.float64),
        np.zeros(len(position), dtype=np.int64),
        evaluation(1.0),
    )
    return particle


def test_trial_state_limits_the_step_during_the_search() -> None:
    """O limite de velocidade precisa bornar o deslocamento, não só o estado guardado.

    Cenário discriminante da verificação adversarial do achado A1: com
    `x = 0,10`, `pbest = gbest = 1,0`, `v = 0,5`, `r1 = r2 = 1` e os pesos
    congelados, a velocidade bruta vale 3,35. Aplicar a velocidade bruta à
    posição dá passo 0,9 e rótulo 4; saturar a velocidade antes dá passo 0,5 e
    rótulo 3. Um cenário com `x = 0,50` não serve, porque produz o mesmo passo
    sob as duas ordens.
    """

    particle = particle_with_pbest(
        [0.10, 0.30, 0.50, 0.70, 0.90], [0.5] * 5, [1.0] * 5
    )
    trial = _trial_state(
        particle,
        np.ones(5, dtype=np.float64),
        PsoConfig(5, 0.4, 2.0, 1.5),
        _ConstantRng(),  # type: ignore[arg-type]
    )
    step = np.abs(trial.position - particle.position)
    assert step.max() <= VELOCITY_LIMIT
    assert np.all(
        (-VELOCITY_LIMIT <= trial.velocity) & (trial.velocity <= VELOCITY_LIMIT)
    )
    assert trial.velocity_clips == 5
    assert decode_position(trial.position, n_units=5, k=5).tolist() == [3, 4, 4, 4, 4]


def test_search_loop_keeps_every_coordinate_step_within_the_velocity_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O limite de passo vale em toda a busca, não apenas na população inicial."""

    original = pso_module._trial_state
    steps: list[float] = []

    def spy(particle: Any, gbest_position: Any, config: Any, rng: Any) -> Any:
        trial = original(particle, gbest_position, config, rng)
        steps.append(float(np.abs(trial.position - particle.position).max()))
        return trial

    monkeypatch.setattr(pso_module, "_trial_state", spy)
    result = run_pso(
        TINY,
        RunConfig(k=2, seed=3, budget=100),
        PsoConfig(4, 0.4, 2.0, 1.5),
    )
    assert len(steps) >= 20
    # A saturação da posição nunca aumenta o passo: com posição em [0, 1] e
    # velocidade em [-0,5, 0,5], recortar a soma em [0, 1] só pode mover o
    # resultado na direção da posição de partida. A única folga concebível é o
    # arredondamento da própria soma, de cerca de um ULP, e a medição da campanha
    # nem chega a exercê-la, com máximo exatamente 0x1.0000000000000p-1.
    assert max(steps) <= VELOCITY_LIMIT
    assert result.diagnostics["velocity_clips"] > 0


def test_trial_state_reproduces_the_formula_and_both_counters() -> None:
    """Fixa a fórmula inteira de `_trial_state`, com sorteios e contadores.

    Os valores esperados vêm dos dois sorteios de `PCG64(2026)` combinados com os
    pesos congelados. A primeira e a terceira coordenadas saturam a velocidade em
    `+0,5` e `-0,5`; sob a ordem defeituosa elas dariam passo `+0,9` e `-0,9` e
    dois recortes de posição.
    """

    expected_r1 = np.array(
        [
            0.17893481367543618,
            0.6399131657151546,
            0.4672684011434851,
            0.37050052710804804,
        ]
    )
    expected_r2 = np.array(
        [
            0.3549173343096512,
            0.790518245853265,
            0.9051438366771739,
            0.17735319182304865,
        ]
    )
    draws = np.random.Generator(np.random.PCG64(2026))
    assert np.array_equal(draws.random(4), expected_r1)
    assert np.array_equal(draws.random(4), expected_r2)

    particle = particle_with_pbest(
        [0.10, 0.50, 0.90, 0.30], [0.50, -0.10, -0.50, 0.05], [1.00, 0.40, 0.00, 0.35]
    )
    trial = _trial_state(
        particle,
        np.array([1.00, 0.45, 0.00, 0.32]),
        PsoConfig(4, 0.4, 2.0, 1.5),
        np.random.Generator(np.random.PCG64(2026)),
    )
    expected_velocity = np.array(
        [0.5, -0.22727150158202575, -0.5, 0.06237064846549627]
    )
    expected_position = np.array(
        [0.6, 0.27272849841797425, 0.4, 0.36237064846549627]
    )
    assert np.allclose(trial.velocity, expected_velocity, rtol=0.0, atol=1e-15)
    assert np.allclose(trial.position, expected_position, rtol=0.0, atol=1e-15)
    assert np.abs(trial.position - particle.position).max() <= VELOCITY_LIMIT
    assert trial.velocity_clips == 2
    assert trial.position_clips == 0


def test_trial_state_depends_on_which_global_best_it_receives() -> None:
    """Sem esta divergência, o instantâneo do melhor global não teria efeito algum."""

    particle = particle_with_pbest([0.30, 0.60], [0.10, -0.10], [0.35, 0.65])
    config = PsoConfig(2, 0.4, 2.0, 1.5)
    synchronous = _trial_state(
        particle,
        np.array([0.80, 0.20]),
        config,
        np.random.Generator(np.random.PCG64(11)),
    )
    asynchronous = _trial_state(
        particle,
        np.array([0.20, 0.90]),
        config,
        np.random.Generator(np.random.PCG64(11)),
    )
    assert not np.array_equal(synchronous.position, asynchronous.position)
    assert not np.array_equal(synchronous.velocity, asynchronous.velocity)


def test_pso_uses_a_single_global_best_snapshot_per_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Todas as partículas de uma iteração enxergam o mesmo melhor global.

    A atualização assíncrona, que consultaria o melhor global já atualizado
    dentro da própria iteração, faria as partículas seguintes de uma iteração
    receberem outro vetor.
    """

    n_particles = 4
    original = pso_module._trial_state
    records: list[tuple[np.ndarray, np.ndarray]] = []

    def spy(particle: Any, gbest_position: Any, config: Any, rng: Any) -> Any:
        records.append((particle.position.copy(), gbest_position.copy()))
        return original(particle, gbest_position, config, rng)

    monkeypatch.setattr(pso_module, "_trial_state", spy)
    run_pso(
        TINY,
        RunConfig(k=2, seed=0, budget=100),
        PsoConfig(n_particles, 0.4, 2.0, 1.5),
    )
    assert len(records) % n_particles == 0
    blocks = [
        records[index : index + n_particles]
        for index in range(0, len(records), n_particles)
    ]
    assert len(blocks) >= 2
    for block in blocks:
        for _, seen in block:
            assert np.array_equal(seen, block[0][1])
    # O cenário só discrimina se em alguma iteração o melhor global mudar por
    # causa de uma partícula que não é a última: a posição comprometida por essa
    # partícula reaparece como instantâneo da iteração seguinte, e mesmo assim as
    # partículas posteriores da iteração em que a mudança ocorreu continuaram com
    # o instantâneo antigo, conforme a asserção acima.
    mid_iteration_updates = [
        (index, order)
        for index in range(len(blocks) - 1)
        if not np.array_equal(blocks[index][0][1], blocks[index + 1][0][1])
        for order, (committed, _) in enumerate(blocks[index + 1][:-1])
        if np.array_equal(committed, blocks[index + 1][0][1])
    ]
    assert mid_iteration_updates


def repairing_run() -> tuple[Any, ...]:
    """Cenário de `tiny_manual` que efetivamente repara, ao contrário do de baixo.

    Com `seed=7` e vinte partículas o `tiny_manual` completa cinco reparos no
    orçamento de 100 avaliações, o que torna as asserções sobre reparo não
    vazias.
    """

    return (
        TINY,
        RunConfig(k=2, seed=7, budget=100),
        PsoConfig(20, 0.4, 2.0, 1.5),
    )


def test_repaired_candidate_is_not_evaluated_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Achado A4: o candidato vencedor do reparo não é reavaliado pelo contexto.

    O espião conta apenas as avaliações completas, isto é as que consumiram
    orçamento e devolveram resultado, incluindo a última, que sai por
    `EvaluationLimitReached`. Sob a forma anterior, cada partícula reparada
    pagava uma segunda unidade de orçamento pela mesma solução, e a contagem
    coincidia com `particles_evaluated`.
    """

    calls: list[tuple[int, ...]] = []
    original = optimizer_module.OptimizationContext.evaluate

    def spy(self: Any, solution: Any, **kwargs: Any) -> Any:
        key = tuple(int(value) for value in np.asarray(solution))
        try:
            result = original(self, solution, **kwargs)
        except EvaluationLimitReached:
            calls.append(key)
            raise
        calls.append(key)
        return result

    monkeypatch.setattr(optimizer_module.OptimizationContext, "evaluate", spy)
    result = run_pso(*repairing_run())
    diagnostics = result.diagnostics

    assert diagnostics["repairs_completed"] == 5
    assert len(calls) == diagnostics["particles_evaluated"] - diagnostics["repairs_completed"]


def test_repairing_run_keeps_the_evaluation_identity() -> None:
    """A identidade de contagem continua valendo num cenário que repara.

    `test_run_pso_exhausts_budget_and_produces_consistent_diagnostics` verifica
    a mesma identidade de forma vazia, porque o cenário dele não tem reparo
    algum: é o achado F2-01, alocado à Onda C e **não** fechado aqui. Este
    cenário repara cinco vezes, e a identidade precisa sobreviver ao
    reaproveitamento da avaliação vencedora, que move uma unidade da coluna de
    reparo para a coluna de partículas sem mudar o total.
    """

    result = run_pso(*repairing_run())
    diagnostics = result.diagnostics

    assert diagnostics["repairs_completed"] == 5
    assert diagnostics["repair_evaluations"] > 0
    assert (
        diagnostics["particles_evaluated"] + diagnostics["repair_evaluations"]
        == result.evaluations
        == 100
    )


def test_projection_that_exhausts_the_sixteen_steps_fails_explicitly() -> None:
    """Achado A6: o recuo ao ponto médio descartava a fração prescrita em silêncio.

    O ramo `for ... else` de `_project_position` nunca é percorrido pelos 42
    cenários da impressão digital, e por isso este teste é o único oráculo
    disponível. Ele monta `position`, `original_labels` e `repaired_solution` à
    mão, com um rótulo reparado fora do intervalo `[0, K)`, que é a única forma
    de entrada que impede o laço de decodificar o alvo: a chave projetada cai
    sempre dentro da célula do rótulo pedido, e a única folga em contrato é de
    poucos ULP na fronteira, absorvida em dois ou três dos dezesseis passos.
    Sob a forma anterior, o ramo substituía a chave por `(lote + 0,5)/K`,
    descartando a fração que a seção 16 manda preservar, e a execução só falhava
    depois, com a mensagem enganosa de posição fora de `[0, 1]`.
    """

    with pytest.raises(SolutionValidationError, match="fração interna"):
        _project_position([0.2, 0.7], [0, 1], [0, 3], k=2)


def test_projection_within_the_sixteen_steps_stays_intact() -> None:
    """O contorno: o caminho normal continua preservando a fração interna.

    O lado negativo da guarda nova. Sem ele, levantar incondicionalmente em
    `_project_position` passaria neste arquivo, e a falha só apareceria na
    impressão digital.
    """

    projected = _project_position([0.2, 0.7], [0, 1], [1, 0], k=2)
    assert decode_position(projected, n_units=2, k=2).tolist() == [1, 0]
    fractions = 2.0 * projected - np.array([1.0, 0.0])
    assert np.allclose(fractions, [0.4, 0.4], rtol=0.0, atol=1e-15)


def test_the_midpoint_fallback_is_not_reached_by_a_normal_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alcançabilidade: a sonda que sustenta a previsão de diff zero do pacote.

    Com a guarda nova, esgotar os dezesseis passos levanta, logo uma execução
    que termina normalmente é prova de que o ramo não foi atingido em nenhuma
    das coordenadas projetadas. O espião existe para que a asserção tenha
    denominador medido em vez de ser verdadeira por vacuidade: sem projeção
    alguma, não haveria o que sondar.
    """

    instance = load_artesp_instance(INSTANCES, 20)
    original = pso_module._project_position
    coordinates = 0

    def spy(position: Any, original_labels: Any, repaired: Any, *, k: int) -> Any:
        nonlocal coordinates
        coordinates += len(np.asarray(position))
        return original(position, original_labels, repaired, k=k)

    monkeypatch.setattr(pso_module, "_project_position", spy)
    result = run_pso(
        instance,
        RunConfig(k=5, seed=7, budget=600),
        PsoConfig(20, 0.4, 2.0, 1.5),
    )

    assert result.diagnostics["repairs_completed"] > 0
    assert coordinates >= 1000
    assert result.evaluations == 600


def _diagnosticos_do_pso(budget: int) -> dict[str, Any]:
    """Executa o cenário calibrado de A5 e devolve os diagnósticos publicados."""

    resultado = run_pso(
        TINY,
        RunConfig(k=2, seed=3, budget=budget),
        PsoConfig(n_particles=4, inertia=0.4, cognitive=2.0, social=1.5),
    )
    assert resultado.evaluations == budget
    return dict(resultado.diagnostics)


def test_a_ultima_iteracao_do_pso_e_contada_mesmo_no_orcamento_multiplo() -> None:
    """A5, achado adicional do verificador, item B6 do Apêndice B.

    `_stop_at_limit` confere `remaining == 0` **depois** de uma avaliação bem
    sucedida, e o caminho de exceção nunca alcançava o incremento de
    `iterations_completed`. Consequência: a última iteração de qualquer execução
    do PSO nunca era contada, mesmo quando o orçamento divide exato por
    `n_particles`. Com orçamento 100 e `n_particles=4` são quatro avaliações
    iniciais mais 24 iterações completas de quatro tentativas cada, e o valor
    publicado era **23**.

    Os 42 cenários da impressão digital **não** exercitam este caminho, porque
    a Tarefa 14 calibrou os orçamentos para não serem múltiplos de
    `n_particles`. Este caso é o único oráculo do achado.
    """

    diagnosticos = _diagnosticos_do_pso(100)

    # A propriedade que torna o cenário o do achado, asseverada aqui dentro: o
    # orçamento menos as avaliações iniciais divide exato pelo número de
    # partículas, logo nenhuma iteração fica pela metade.
    assert (100 - 4) % 4 == 0
    assert diagnosticos["particles_evaluated"] == 100
    assert diagnosticos["repair_attempts"] == 0
    assert diagnosticos["iterations_completed"] == 24


def test_os_contadores_de_saturacao_nao_incluem_a_iteracao_interrompida() -> None:
    """A5: as somas de `position_clips` e `velocity_clips` eram antecipadas.

    O laço somava os contadores das `n_particles` tentativas **antes** de
    qualquer avaliação, de modo que a iteração interrompida pela fronteira do
    orçamento contribuía por inteiro, inclusive pelas tentativas que nunca
    foram avaliadas.

    O experimento é o de orçamento crescente, que é a forma como o verificador
    demonstrou o achado de modo mais direto. Com orçamento 100 a iteração 24
    fecha exatamente; de 101 a 104 a iteração 25 vai sendo avaliada tentativa a
    tentativa. O oráculo não depende de conhecer a repartição das saturações
    entre as quatro tentativas, e sim de um limite superior que o defeito viola:
    **uma única tentativa não pode saturar mais posições do que a instância tem
    unidades**.
    """

    instance = TINY
    curva = {budget: _diagnosticos_do_pso(budget) for budget in range(100, 105)}

    # Denominador do caso, asseverado aqui dentro: a iteração 25 inteira satura
    # mais posições do que uma tentativa isolada poderia, o que é o que torna o
    # limite superior abaixo discriminante em vez de vazio.
    total_da_iteracao = (
        curva[104]["position_clips"] - curva[100]["position_clips"]
    )
    assert total_da_iteracao > instance.n_units

    # A iteração 25 é interrompida logo na primeira tentativa quando o orçamento
    # é 101, logo o que ela acrescenta é o de uma tentativa só.
    acrescimo_de_uma_tentativa = (
        curva[101]["position_clips"] - curva[100]["position_clips"]
    )
    assert 0 <= acrescimo_de_uma_tentativa <= instance.n_units
    assert curva[101]["position_clips"] < curva[104]["position_clips"]

    # A curva é não decrescente e cresce por tentativa avaliada, e não por
    # iteração iniciada.
    for anterior, seguinte in zip(range(100, 104), range(101, 105)):
        assert curva[anterior]["position_clips"] <= curva[seguinte]["position_clips"]
        assert curva[anterior]["velocity_clips"] <= curva[seguinte]["velocity_clips"]

    # E a iteração completa continua contribuindo por inteiro: a correção retira
    # as tentativas não avaliadas, e não as avaliadas.
    assert curva[104]["position_clips"] == curva[100]["position_clips"] + total_da_iteracao
    assert curva[101]["iterations_completed"] == 24
    assert curva[104]["iterations_completed"] == 25
