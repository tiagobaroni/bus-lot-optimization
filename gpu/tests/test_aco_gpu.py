from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    AcoConfig, ObjectiveWeights, RunConfig, evaluate_solution,
    load_artesp_instance, load_tiny_instance, run_aco,
)
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica_gpu.aco import _PartialState, _construct, _update, run_aco_gpu


ROOT = Path(__file__).parents[2]


def test_aco_gpu_matches_cpu_deterministically() -> None:
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    run = RunConfig(k=2, seed=3, budget=100)
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.1, n_ants=40)
    cpu = run_aco(instance, run, config)
    gpu = run_aco_gpu(instance, run, config, verify_every_batch=True)
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluation == cpu.evaluation
    assert gpu.checkpoints == cpu.checkpoints
    assert gpu.evaluations == cpu.evaluations == 100


@pytest.mark.parametrize("k", [3, 8])
def test_aco_gpu_matches_cpu_on_a_real_instance(k: int) -> None:
    """Equivalência CPU e GPU do ACO fora do caso degenerado do `tiny_manual`.

    O teste acima roda em quatro unidades com `K=2`, onde as duas trajetórias
    chegam a custo zero. Este exercita a construção espelhada numa instância
    real, que é o que protege o espelhamento da variante O4.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    run = RunConfig(k=k, seed=11, budget=400)
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20)
    cpu = run_aco(instance, run, config)
    gpu = run_aco_gpu(instance, run, config, verify_every_batch=True)
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluation == cpu.evaluation
    assert gpu.checkpoints == cpu.checkpoints
    assert gpu.diagnostics["forced_assignments"] == cpu.diagnostics["forced_assignments"]
    assert gpu.evaluations == cpu.evaluations == 400


def test_gpu_construction_shares_the_cpu_partial_state() -> None:
    """O espelho delega o estado parcial, em vez de reimplementá-lo.

    Uma cópia textual da aritmética é exatamente o modo de falha que o pacote
    corrige no PSO: o espelho reteve a ordem anterior e divergiu em silêncio.
    Este teste falha se alguém voltar a introduzir uma classe local.
    """

    from metaheuristica.aco import _PartialConstructionState

    assert _PartialState is _PartialConstructionState
    instance = load_artesp_instance(ROOT / "data/instances", 20)
    state = _PartialState(instance, k=4, weights=ObjectiveWeights())
    for lot in (0, 1, 2, 3, 0, 1):
        state.append(lot)
    costs = state.choice_costs((0, 1, 2, 3))
    reference = [state.evaluate_choice(lot).total_cost for lot in (0, 1, 2, 3)]
    for expected, obtained in zip(reference, costs):
        assert expected.hex() == float(obtained).hex()


def test_gpu_construction_is_identical_to_the_cpu_construction() -> None:
    """A formiga construída na GPU coincide com a da CPU sob o mesmo gerador."""

    from metaheuristica.aco import _construct_ant

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20)
    tau = np.ones((instance.n_units, 5), dtype=np.float64)
    weights = ObjectiveWeights()
    mirrored = _construct(
        instance, 5, weights, tau, config, np.random.Generator(np.random.PCG64(5))
    )
    reference = _construct_ant(
        instance,
        k=5,
        weights=weights,
        tau=tau,
        config=config,
        rng=np.random.Generator(np.random.PCG64(5)),
    )
    assert mirrored.solution.tolist() == reference.solution.tolist()
    assert mirrored.forced == reference.forced_assignments
    assert mirrored.probabilistic == reference.probabilistic_assignments


def test_aco_gpu_publishes_the_incumbent_object_in_both_tables() -> None:
    """A tabela principal e a de checkpoints carregam o mesmo objeto.

    O caminho GPU publicava `evaluation` recalculada na CPU ao lado de
    checkpoints medidos na GPU, dois objetos distintos por construção, e a
    guarda de `metrics.py` tolerava até `1e-12` de divergência entre eles. A
    conferência de conformidade contra a CPU continua sendo feita, por
    `require_equivalent`, que é contrato do projeto e admite `1e-12`; o que muda
    é apenas qual objeto é publicado.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    run = RunConfig(k=3, seed=11, budget=400)
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20)
    gpu = run_aco_gpu(instance, run, config)
    assert gpu.evaluation is gpu.checkpoints[-1].evaluation


def _instancia_pequena():
    return load_tiny_instance(ROOT / "data/instances/tiny_manual.json")


def test_a_construcao_recusa_feromonio_nao_positivo() -> None:
    """F8-10: o espelho não conferia positividade e finitude de `tau` e `eta`.

    O caminho normativo recusa por `ConfigurationError` em
    `metaheuristica.aco._choice_probabilities`. O espelho tomava o logaritmo
    direto, e uma célula nula produzia peso `-inf` sem aviso de erro, com a
    probabilidade correspondente zerada em silêncio.
    """

    instance = _instancia_pequena()
    weights = ObjectiveWeights()
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=4)
    tau = np.ones((instance.n_units, 2), dtype=np.float64)
    tau[1, 0] = 0.0
    with pytest.raises(ConfigurationError, match="positivos e finitos"):
        _construct(
            instance, 2, weights, tau, config,
            np.random.Generator(np.random.PCG64(3)),
        )

    infinito = np.ones((instance.n_units, 2), dtype=np.float64)
    infinito[1, 0] = np.inf
    with pytest.raises(ConfigurationError, match="positivos e finitos"):
        _construct(
            instance, 2, weights, infinito, config,
            np.random.Generator(np.random.PCG64(3)),
        )


def test_a_formiga_nao_canonica_e_recusada_pelo_espelho() -> None:
    """F8-10: faltava a pós-condição de canonicidade que `_construct_ant` tem.

    O crescimento restrito torna o prefixo canônico por construção, logo o
    único modo de exercitar a pós-condição é afrouxar as escolhas permitidas.
    Sem a conferência, `canonicalize_solution` renomeava em silêncio e a
    formiga publicada deixava de ser a que foi construída.
    """

    instance = _instancia_pequena()
    weights = ObjectiveWeights()
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=4)
    tau = np.ones((instance.n_units, 2), dtype=np.float64)

    class _EscolhaAlternada:
        """Gerador que alterna entre o maior e o menor lote permitido.

        Produz o prefixo `[1, 0, 1, 0]`, que é solução válida, com os dois
        lotes ocupados, e **não canônica**: é o único modo de chegar ao ramo,
        porque o crescimento restrito o torna inalcançável.
        """

        def __init__(self) -> None:
            self._real = np.random.Generator(np.random.PCG64(3))
            self._passo = 0

        def choice(self, choices, p=None):
            escolha = max(choices) if self._passo % 2 == 0 else min(choices)
            self._passo += 1
            return int(escolha)

        def __getattr__(self, nome):
            return getattr(self._real, nome)

    import metaheuristica_gpu.aco as modulo

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "_choices", lambda prefix, n, k: ((0, 1), False))
        with pytest.raises(SolutionValidationError, match="não canônica"):
            _construct(instance, 2, weights, tau, config, _EscolhaAlternada())


def test_o_deposito_recusa_custo_fora_do_intervalo_normalizado() -> None:
    """F8-10: a clipagem silenciosa substituía a exceção de `_deposit_amount`.

    O espelho fazia `1.0 - min(1.0, max(0.0, custo))`, de modo que um custo
    total corrompido entrava na matriz como depósito válido em vez de parar a
    execução.
    """

    instance = _instancia_pequena()
    solution = np.zeros(instance.n_units, dtype=np.int64)
    solution[-1] = 1
    tau = np.ones((instance.n_units, 2), dtype=np.float64)
    avaliacao = evaluate_solution(instance, solution, k=2)
    corrompida = replace(avaliacao, total_cost=2.0)
    with pytest.raises(ConfigurationError, match="intervalo normalizado"):
        _update(tau, [(solution, corrompida)], 0.5)


def test_a_evaporacao_do_espelho_tem_o_mesmo_piso_do_nucleo() -> None:
    """F8-10: sem o piso, a evaporação do espelho chega a zero exato.

    `metaheuristica.aco._update_pheromone` põe piso no menor subnormal
    positivo e recusa matriz não positiva depois do depósito. O espelho não
    fazia nem uma coisa nem outra: com `rho = 0,5` o arredondamento para par
    leva o subnormal a `0,0`, e a célula zerada só apareceria depois, como
    logaritmo de zero na construção seguinte.
    """

    from metaheuristica.aco import _EvaluatedAnt, _update_pheromone

    instance = _instancia_pequena()
    solution = np.zeros(instance.n_units, dtype=np.int64)
    solution[-1] = 1
    avaliacao = evaluate_solution(instance, solution, k=2)
    subnormal = np.nextafter(0.0, 1.0)
    tau = np.full((instance.n_units, 2), 1.0, dtype=np.float64)
    tau[0, 1] = subnormal

    espelhada = _update(tau, [(solution, avaliacao)], 0.5)
    nucleo = _update_pheromone(
        tau, (_EvaluatedAnt(solution, avaliacao),), rho=0.5
    )
    # A célula `[0, 1]` não recebe depósito desta formiga, logo mede só a
    # evaporação: é a que discrimina o piso.
    assert solution[0] == 0
    assert float(espelhada[0, 1]).hex() == subnormal.hex()
    assert float(espelhada[0, 1]) > 0.0
    assert [float(v).hex() for v in espelhada.ravel()] == [
        float(v).hex() for v in nucleo.ravel()
    ]


def _celulas_alcancaveis(n_units: int, k: int) -> set[tuple[int, int]]:
    """Células que a construção de crescimento restrito pode depositar.

    Derivação independente, propagando os estados de `opened` possíveis a
    partir de `_choices_from_counts` do núcleo, que é a mesma aritmética que a
    construção usa. Não reproduz a máscara da produção: deriva a propriedade
    que ela deveria ter. Copia a forma do caso escrito no lote L5 em
    `tests/test_aco.py`.
    """

    from metaheuristica.aco import _choices_from_counts

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


def test_o_minimo_publicado_usa_exatamente_a_mascara_alcancavel() -> None:
    """Observação `f`: o espelho tomava `final_tau_min` sobre a matriz inteira.

    É o defeito `F4-4` que o pacote B11 corrigiu no núcleo, sobrevivendo na
    cópia da réplica. A asserção é de **identidade de conjunto**, e não de
    limiar: limiar prende só o alargamento da máscara, porque estreitá-la
    torna o mínimo publicado maior, e foi assim que a mutação que descartava a
    diagonal principal sobreviveu à suíte inteira no lote L5.
    """

    import metaheuristica_gpu.aco as modulo

    capturadas: list[np.ndarray] = []
    original = modulo._reachable_mask

    def espiao(shape):
        mascara = original(shape)
        capturadas.append(np.array(mascara, copy=True))
        return mascara

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    n_units, k = instance.n_units, 3
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "_reachable_mask", espiao)
        run_aco_gpu(
            instance,
            RunConfig(k=k, seed=11, budget=200),
            AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20),
        )

    assert len(capturadas) == 1, "a máscara deve ser construída uma vez por execução"
    mascara = capturadas[0]
    assert mascara.shape == (n_units, k)
    obtida = {(int(i), int(j)) for i, j in np.argwhere(mascara)}
    esperada = _celulas_alcancaveis(n_units, k)
    assert obtida == esperada, (
        f"máscara alargada em {sorted(obtida - esperada)} e "
        f"estreitada em {sorted(esperada - obtida)}"
    )


def test_o_minimo_publicado_do_espelho_fica_acima_da_evaporacao_pura() -> None:
    """O lado numérico da observação `f`, com denominador medido.

    A asserção só discrimina se existir célula inalcançável de fato, isto é se
    a máscara for própria; sem essa guarda o caso passaria por vacuidade numa
    configuração em que todas as células recebem depósito.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    rho = 0.5
    resultado = run_aco_gpu(
        instance,
        RunConfig(k=3, seed=11, budget=200),
        AcoConfig(alpha=1.0, beta=2.0, rho=rho, n_ants=20),
    )
    geracoes = resultado.diagnostics["generations_completed"]
    assert geracoes > 0
    evaporada = (1.0 - rho) ** geracoes
    assert _celulas_alcancaveis(instance.n_units, 3) != {
        (i, j) for i in range(instance.n_units) for j in range(3)
    }
    assert resultado.diagnostics["final_tau_min"] > evaporada


def test_o_custo_de_preparacao_do_dispositivo_e_registrado_em_campo_proprio() -> None:
    """F8-14: o que sai do tempo oficial passa a ter campo próprio e positivo."""

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    resultado = run_aco_gpu(
        instance,
        RunConfig(k=3, seed=11, budget=200),
        AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20),
    )
    preparacao = resultado.diagnostics["device_preparation_seconds"]
    assert isinstance(preparacao, float)
    assert preparacao > 0.0
    assert resultado.runtime_seconds > 0.0


def test_o_tempo_oficial_do_aco_continua_excluindo_a_preparacao() -> None:
    """F8-14: a comparabilidade com as 60 execuções fica presa por asserção.

    O relógio roteirizado torna as duas grandezas exatas: se o cronômetro
    oficial passasse a incluir a preparação, `runtime_seconds` valeria 11,0 e
    não 1,0. O relógio recusa chamada além do roteiro, para que uma medição
    acrescentada ao caminho apareça como falha em vez de deslocar a asserção.
    """

    import metaheuristica_gpu.aco as modulo

    roteiro = [0.0, 10.0, 11.0]
    chamadas = []

    def relogio() -> float:
        if len(chamadas) >= len(roteiro):
            raise AssertionError(
                f"relógio chamado {len(chamadas) + 1} vezes; o roteiro prevê {len(roteiro)}"
            )
        chamadas.append(len(chamadas))
        return roteiro[len(chamadas) - 1]

    instance = _instancia_pequena()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "perf_counter", relogio)
        resultado = run_aco_gpu(
            instance,
            RunConfig(k=2, seed=3, budget=100),
            AcoConfig(alpha=1.0, beta=2.0, rho=0.5, n_ants=20),
        )

    assert len(chamadas) == len(roteiro)
    assert resultado.diagnostics["device_preparation_seconds"] == 10.0
    assert resultado.runtime_seconds == 1.0


def test_a_chave_registrada_pelo_avaliador_hibrido_e_canonica() -> None:
    """F8-10: o avaliador híbrido gravava a tupla bruta, sem canonicalizar.

    O desempate de quase empate do `ConvergenceRecorder` é lexicográfico sobre
    essa tupla, logo chave não canônica produziria desempate diferente do da
    CPU.
    """

    from metaheuristica import solution_key
    from metaheuristica_gpu.evaluator import HybridEvaluator
    from metaheuristica_gpu.objective import GpuBatchObjective

    instance = _instancia_pequena()
    run = RunConfig(k=2, seed=3, budget=100)
    nao_canonica = np.array([1, 1, 0, 1], dtype=np.int64)
    esperada = solution_key(nao_canonica, n_units=instance.n_units, k=2)
    assert tuple(int(v) for v in nao_canonica) != esperada

    objective = GpuBatchObjective(instance, k=2, weights=run.weights)
    try:
        avaliador = HybridEvaluator(instance, run, objective)
        avaliador.evaluate_batch([nao_canonica])
    finally:
        objective.close()
    assert avaliador.incumbent_solution == esperada


# F8-4. As três funções abaixo são locais a este arquivo, e a réplica no arquivo
# do PSO é deliberada: a lista de arquivos deste pacote são os dois arquivos de
# teste, e um módulo auxiliar comum ficaria fora dela.
_INSTANCIA_REAL = 20
_K_REAL = 5
_SEMENTE_REAL = 10
_ORCAMENTO_REAL = 400
_CONFIG_REAL = AcoConfig(alpha=1.0, beta=2.0, rho=0.1, n_ants=20)


def _cenario_real():
    return (
        load_artesp_instance(ROOT / "data/instances", _INSTANCIA_REAL),
        RunConfig(k=_K_REAL, seed=_SEMENTE_REAL, budget=_ORCAMENTO_REAL),
        _CONFIG_REAL,
    )


def _objetivo_com_desvio(delta: float, apenas_primeiro_lote: bool):
    """Objetivo em lote que soma `delta` ao custo total devolvido pela placa."""

    from metaheuristica_gpu.objective import GpuBatchObjective

    class _ComDesvio(GpuBatchObjective):
        lotes_injetados = 0

        def __init__(self, *args, **extras) -> None:
            super().__init__(*args, **extras)
            self._lotes = 0

        def evaluate(self, solutions, *, timing=None):
            resultados = super().evaluate(solutions, timing=timing)
            self._lotes += 1
            if apenas_primeiro_lote and self._lotes != 1:
                return resultados
            type(self).lotes_injetados += 1
            return tuple(
                replace(item, total_cost=item.total_cost + delta) for item in resultados
            )

    return _ComDesvio


def test_aco_gpu_matches_cpu_in_official_mode_on_a_real_instance() -> None:
    """F8-4: a trajetória completa passa a ser exercitada no modo da campanha.

    Os dois casos de equivalência que já existiam rodam com
    `verify_every_batch=True`, modo em que `HybridEvaluator.evaluate_batch`
    substitui os resultados da placa pelos normativos antes de gravá-los: as
    asserções externas comparam CPU com CPU. Este caso roda em **modo oficial**,
    que é o caminho que os 60 cenários executam, e a régua é a normativa de
    `1e-12`, e **não** igualdade exata.

    A instância é real, e não a `tiny_manual`, cuja trajetória é degenerada: com
    `K=2` o custo é exatamente zero em 99 dos 100 checkpoints do ACO, de modo
    que a igualdade passaria sem exercitar a evolução de `tau`.

    As duas asserções que impedem o caso de ser vazio estão aqui dentro. A
    igualdade **exata** de checkpoints tem de **falhar**, porque os números
    vieram do dispositivo, e a divergência medida tem de ser **estritamente
    positiva**: se os resultados da placa tivessem sido descartados, ela valeria
    zero e a igualdade exata valeria. Medido em `artesp_rmsp_20`, `K=5`, semente
    10 e orçamento 400: os cem checkpoints diferem já a partir do primeiro, com
    `max |delta|` de `2,220e-16`, isto é 1/4503 do `abs_tol` normativo.
    """

    from metaheuristica_gpu.numerics import ABS_TOL, require_equivalent_trajectory

    instance, run, config = _cenario_real()
    gpu = run_aco_gpu(instance, run, config)
    cpu = run_aco(instance, run, config)

    assert gpu.checkpoints != cpu.checkpoints
    diferenca = require_equivalent_trajectory(gpu, cpu)
    assert 0.0 < diferenca <= ABS_TOL
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluations == cpu.evaluations == _ORCAMENTO_REAL


def test_o_modo_de_verificacao_do_aco_substitui_os_resultados_da_gpu() -> None:
    """F8-4, a vacuidade medida diretamente e sem injeção alguma.

    A mesma instância, o mesmo `K`, a mesma semente e o mesmo orçamento, e
    apenas o modo muda. Sob `verify_every_batch=True` a igualdade de
    checkpoints contra a CPU é **exata**, o que só é possível porque os
    resultados da placa foram substituídos pelos normativos; em modo oficial a
    igualdade exata **falha**, porque os números publicados são os do
    dispositivo. É essa diferença que torna as asserções externas dos dois
    casos de equivalência incapazes de discriminar, e é ela que o caso acima
    corrige.
    """

    instance, run, config = _cenario_real()
    cpu = run_aco(instance, run, config)
    verificado = run_aco_gpu(instance, run, config, verify_every_batch=True)
    oficial = run_aco_gpu(instance, run, config)

    assert verificado.checkpoints == cpu.checkpoints
    assert oficial.checkpoints != cpu.checkpoints
    assert verificado.diagnostics["max_numerical_difference"] > 0.0
    assert oficial.diagnostics["max_numerical_difference"] == 0.0


def test_a_trajetoria_oficial_do_aco_reprova_divergencia_de_1e_11() -> None:
    """Validação negativa obrigatória de F8-4, com o eixo medido antes de escrito.

    **A injeção é confinada ao primeiro lote, e a razão é medida.** Somada a
    todos os lotes, uma divergência de `1e-11` é apanhada pelo
    `require_equivalent` que `run_aco_gpu` já aplica ao incumbente antes de
    devolver, em modo oficial, e por `verify_batch` em modo de verificação: nos
    dois casos a execução levanta, e um caso escrito sobre essa forma provaria
    apenas que uma guarda **anterior** a este pacote tem dentes. Confinada ao
    primeiro lote, a divergência não alcança o incumbente final, a execução
    **completa** e nenhuma guarda do caminho de produção a vê. Só a comparação
    de trajetória a apanha, no checkpoint 1.

    As duas metades estão asseveradas aqui dentro: que a injeção de fato
    ocorreu, e que a execução chegou ao fim, isto é que o portão que reprova é
    o novo e não um vizinho.
    """

    from metaheuristica_gpu.numerics import NumericalDivergenceError, require_equivalent_trajectory

    import metaheuristica_gpu.aco as modulo

    instance, run, config = _cenario_real()
    cpu = run_aco(instance, run, config)
    injetado = _objetivo_com_desvio(1e-11, apenas_primeiro_lote=True)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "GpuBatchObjective", injetado)
        gpu = run_aco_gpu(instance, run, config)

    assert injetado.lotes_injetados == 1, "denominador do caso: a injeção foi percorrida"
    assert gpu.evaluations == _ORCAMENTO_REAL, "a execução completou, sem guarda anterior disparar"
    with pytest.raises(NumericalDivergenceError, match="checkpoint 1: total_cost diverge"):
        require_equivalent_trajectory(gpu, cpu)
