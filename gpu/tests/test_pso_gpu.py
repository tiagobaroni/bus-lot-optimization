from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    FitnessEvaluator, PsoConfig, RunConfig, load_artesp_instance,
    load_tiny_instance, run_pso,
)
from metaheuristica.errors import SolutionValidationError
from metaheuristica.repair import repair_empty_lots_with_evaluation
from metaheuristica_gpu.pso import _decode, _project, run_pso_gpu


ROOT = Path(__file__).parents[2]


def test_pso_gpu_matches_cpu_deterministically() -> None:
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    run = RunConfig(k=2, seed=4, budget=100)
    config = PsoConfig(n_particles=40, inertia=0.4, cognitive=2.0, social=1.5)
    cpu = run_pso(instance, run, config)
    gpu = run_pso_gpu(instance, run, config, verify_every_batch=True)
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluation == cpu.evaluation
    assert gpu.checkpoints == cpu.checkpoints
    assert gpu.evaluations == cpu.evaluations == 100


@pytest.mark.parametrize("k", [3, 5])
def test_pso_gpu_matches_cpu_on_a_real_instance(k: int) -> None:
    """Equivalência CPU e GPU do PSO fora do caso degenerado do `tiny_manual`.

    O teste acima roda em quatro unidades com `K=2`, onde as duas trajetórias
    chegam a custo zero de qualquer forma, de modo que ele passava mesmo com o
    espelho de `_trial` retendo a ordem anterior ao pacote A1. Numa instância
    real a divergência aparece: antes do espelhamento, o custo total difere em
    `5,16e-2`, contra a régua normativa de `1e-12` de
    `metaheuristica_gpu.numerics`.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    run = RunConfig(k=k, seed=7, budget=600)
    config = PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5)
    cpu = run_pso(instance, run, config)
    gpu = run_pso_gpu(instance, run, config, verify_every_batch=True)
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluation == cpu.evaluation
    assert gpu.checkpoints == cpu.checkpoints
    assert gpu.diagnostics["position_clips"] == cpu.diagnostics["position_clips"]
    assert gpu.diagnostics["velocity_clips"] == cpu.diagnostics["velocity_clips"]
    assert gpu.evaluations == cpu.evaluations == 600


def test_pso_gpu_publishes_the_incumbent_object_in_both_tables() -> None:
    """A tabela principal e a de checkpoints carregam o mesmo objeto.

    Mesma correção do ACO na GPU: o resultado publicava uma avaliação
    recalculada na CPU ao lado de checkpoints medidos na GPU. A conferência de
    conformidade por `require_equivalent`, com a tolerância de `1e-12` que é
    contrato do projeto, permanece intacta.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    run = RunConfig(k=3, seed=7, budget=600)
    config = PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5)
    gpu = run_pso_gpu(instance, run, config)
    assert gpu.evaluation is gpu.checkpoints[-1].evaluation


def test_a_decodificacao_do_espelho_recusa_posicao_fora_do_caminho_normativo() -> None:
    """F8-10: o espelho decodificava sem conferir `dtype`, finitude e faixa.

    `metaheuristica.pso.decode_position` recusa os quatro casos abaixo por
    `SolutionValidationError`. O espelho só conferia a dimensão, de modo que
    posição com `NaN` ou fora de `[0, 1]` produzia rótulo arbitrário em
    silêncio, que é a entrada de todo o resto do caminho.
    """

    with pytest.raises(SolutionValidationError, match="float64"):
        _decode(np.array([0.1, 0.6], dtype=np.float32), 2, 2)
    with pytest.raises(SolutionValidationError, match="dimensão"):
        _decode(np.array([0.1, 0.6, 0.3], dtype=np.float64), 2, 2)
    with pytest.raises(SolutionValidationError, match="finitos"):
        _decode(np.array([0.1, np.nan], dtype=np.float64), 2, 2)
    with pytest.raises(SolutionValidationError, match=r"\[0, 1\]"):
        _decode(np.array([0.1, 1.6], dtype=np.float64), 2, 2)


def test_a_projecao_do_espelho_que_esgota_os_dezesseis_passos_falha() -> None:
    """Observação `e`: o espelho recuava ao ponto médio em silêncio.

    O núcleo converteu esse recuo em falha explícita no pacote B10, com a
    razão de que fixar `u = 0,5` descarta a fração interna que a seção 16 da
    formulação manda preservar. A cópia da réplica reteve a forma anterior. A
    entrada é a mesma do caso do núcleo, `tests/test_pso.py`: um rótulo
    reparado fora do intervalo `[0, K)` é a única forma que impede o laço de
    decodificar o alvo.
    """

    with pytest.raises(SolutionValidationError, match="fração interna"):
        _project(np.array([0.2, 0.7]), np.array([0, 1]), np.array([0, 3]), 2)


def test_a_projecao_do_espelho_dentro_dos_dezesseis_passos_permanece_intacta() -> None:
    """O lado negativo da guarda: o caminho normal preserva a fração interna.

    Sem ele, levantar incondicionalmente passaria no caso anterior e a
    regressão só apareceria na campanha.
    """

    projetada = _project(np.array([0.2, 0.7]), np.array([0, 1]), np.array([1, 0]), 2)
    assert _decode(projetada, 2, 2).tolist() == [1, 0]
    fracoes = 2.0 * projetada - np.array([1.0, 0.0])
    assert np.allclose(fracoes, [0.4, 0.4], rtol=0.0, atol=1e-15)


def test_o_ramo_sem_avaliacao_reaproveitavel_do_reparo_e_inalcancavel() -> None:
    """Observação `b`: demonstração de que o ramo removido era morto.

    O espelho entrava no bloco de reparo somente quando a decodificação
    deixava algum lote vazio, e `repair_empty_lots_with_evaluation` devolve
    `None` apenas quando o estado recebido já era viável e nenhuma unidade de
    orçamento foi consumida. Os dois lados são medidos: a propriedade do
    núcleo, por enumeração de estados com lote vazio, e o caminho integrado,
    por espião com denominador asseverado.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    for estado in (
        [0] * instance.n_units,
        [0] * (instance.n_units - 1) + [1],
        [i % 3 for i in range(instance.n_units)],
    ):
        rotulos = np.array(estado, dtype=np.int64)
        vazios = np.count_nonzero(np.bincount(rotulos, minlength=5)) < 5
        if not vazios:
            continue
        avaliador = FitnessEvaluator(instance, k=5, budget=2000)
        _, vencedora = repair_empty_lots_with_evaluation(rotulos, avaliador)
        assert vencedora is not None
        assert avaliador.evaluations > 0

    import metaheuristica_gpu.pso as modulo

    real = modulo.repair_empty_lots_with_evaluation
    chamadas = 0
    sem_avaliacao = 0

    def espiao(solution, evaluator):
        nonlocal chamadas, sem_avaliacao
        chamadas += 1
        reparada, vencedora = real(solution, evaluator)
        if vencedora is None:
            sem_avaliacao += 1
        return reparada, vencedora

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "repair_empty_lots_with_evaluation", espiao)
        resultado = run_pso_gpu(
            instance,
            RunConfig(k=5, seed=7, budget=600),
            PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5),
        )

    assert resultado.diagnostics["repair_attempts"] > 0
    assert chamadas > 0, "denominador medido: o bloco de reparo tem de ser percorrido"
    assert sem_avaliacao == 0


def test_a_particula_reparada_passa_pela_validacao_normativa() -> None:
    """Observação `a`: o `commit` direto da partícula reparada não validava.

    O ramo vizinho, o do caminho sem reparo, chama `validate_solution`, e a
    CPU valida nos dois. Aqui o reparo é forçado a devolver um estado com lote
    vazio: sem a validação, ele entrava no melhor pessoal e no melhor global
    sem nunca ser recusado, porque o `commit` não passa pelo gravador e o
    incumbente publicado vem do gravador.
    """

    import metaheuristica_gpu.pso as modulo

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    real = modulo.repair_empty_lots_with_evaluation
    chamadas = 0

    def espiao(solution, evaluator):
        nonlocal chamadas
        chamadas += 1
        _, vencedora = real(solution, evaluator)
        return np.zeros(instance.n_units, dtype=np.int64), vencedora

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "repair_empty_lots_with_evaluation", espiao)
        with pytest.raises(SolutionValidationError, match="lotes vazios"):
            run_pso_gpu(
                instance,
                RunConfig(k=5, seed=7, budget=600),
                PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5),
            )

    assert chamadas > 0, "denominador medido: o bloco de reparo tem de ser percorrido"


def test_o_custo_de_preparacao_do_dispositivo_do_pso_tem_campo_proprio() -> None:
    """F8-14, lado PSO: campo próprio, positivo, sem mover o cronômetro."""

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    resultado = run_pso_gpu(
        instance,
        RunConfig(k=3, seed=7, budget=300),
        PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5),
    )
    preparacao = resultado.diagnostics["device_preparation_seconds"]
    assert isinstance(preparacao, float)
    assert preparacao > 0.0
    assert resultado.runtime_seconds > 0.0


def test_o_tempo_oficial_do_pso_continua_excluindo_a_preparacao() -> None:
    """F8-14, lado PSO: a exclusão fica presa por asserção, e não por convenção.

    O relógio roteirizado recusa chamada além do roteiro, de modo que uma
    medição acrescentada ao caminho falha em vez de deslocar as asserções.
    """

    import metaheuristica_gpu.pso as modulo

    roteiro = [0.0, 10.0, 11.0]
    chamadas: list[int] = []

    def relogio() -> float:
        if len(chamadas) >= len(roteiro):
            raise AssertionError(
                f"relógio chamado {len(chamadas) + 1} vezes; o roteiro prevê {len(roteiro)}"
            )
        chamadas.append(len(chamadas))
        return roteiro[len(chamadas) - 1]

    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "perf_counter", relogio)
        resultado = run_pso_gpu(
            instance,
            RunConfig(k=2, seed=4, budget=100),
            PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5),
        )

    assert len(chamadas) == len(roteiro)
    assert resultado.diagnostics["device_preparation_seconds"] == 10.0
    assert resultado.runtime_seconds == 1.0


def test_os_contadores_do_espelho_coincidem_no_cenario_interrompido() -> None:
    """B21: o espelho conta saturações e iterações do mesmo jeito que o núcleo.

    O caso vizinho compara os dois contadores com orçamento 600 e 20
    partículas, que é múltiplo exato do número de partículas. Nele a última
    iteração raramente fica pela metade, e a divergência de granularidade que
    este pacote corrige passaria **silenciosa**: o espelho somaria as
    saturações de todas as tentativas antes de qualquer avaliação e chegaria ao
    mesmo total.

    Este caso exercita o cenário **interrompido**, em que o orçamento não é
    múltiplo do número de partículas e a última iteração é cortada no meio pela
    fronteira. É onde o núcleo passou a contar só as tentativas avaliadas, e é
    onde o espelho tem de contar do mesmo jeito, sob pena de reintroduzir a
    assimetria de instrumentação que o pacote B20 acabou de eliminar entre os
    dois lados.
    """

    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    run = RunConfig(k=2, seed=4, budget=100)
    config = PsoConfig(n_particles=40, inertia=0.4, cognitive=2.0, social=1.5)

    # A propriedade que faz do cenário o interrompido, asseverada aqui dentro:
    # nem o orçamento nem o que sobra dele depois da população inicial divide
    # exato pelo número de partículas, logo a última iteração é cortada.
    assert run.budget % config.n_particles != 0
    assert (run.budget - config.n_particles) % config.n_particles != 0

    cpu = run_pso(instance, run, config)
    gpu = run_pso_gpu(instance, run, config)

    # Denominador do caso: os três contadores medem alguma coisa neste cenário.
    assert cpu.diagnostics["position_clips"] > 0
    assert cpu.diagnostics["velocity_clips"] > 0
    assert cpu.diagnostics["iterations_completed"] > 0

    assert gpu.diagnostics["position_clips"] == cpu.diagnostics["position_clips"]
    assert gpu.diagnostics["velocity_clips"] == cpu.diagnostics["velocity_clips"]
    assert (
        gpu.diagnostics["iterations_completed"]
        == cpu.diagnostics["iterations_completed"]
    )
    assert gpu.evaluations == cpu.evaluations == run.budget


# F8-4. As funções abaixo são locais a este arquivo, e a réplica no arquivo do
# ACO é deliberada: a lista de arquivos deste pacote são os dois arquivos de
# teste, e um módulo auxiliar comum ficaria fora dela.
_INSTANCIA_REAL = 20
_K_REAL = 5
_SEMENTE_REAL = 10
_ORCAMENTO_REAL = 400
_CONFIG_REAL = PsoConfig(n_particles=20, inertia=0.4, cognitive=2.0, social=1.5)


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


def test_pso_gpu_matches_cpu_in_official_mode_on_a_real_instance() -> None:
    """F8-4: a trajetória completa passa a ser exercitada no modo da campanha.

    Os dois casos de equivalência que já existiam rodam com
    `verify_every_batch=True`, modo em que `HybridEvaluator.evaluate_batch`
    substitui os resultados da placa pelos normativos antes de gravá-los: as
    asserções externas comparam CPU com CPU. Este caso roda em **modo oficial**,
    que é o caminho que os 60 cenários executam, e a régua é a normativa de
    `1e-12`, e **não** igualdade exata.

    A instância é real, e não a `tiny_manual`, cuja trajetória é degenerada: com
    `K=2` o custo é exatamente zero em 98 dos 100 checkpoints do PSO, de modo
    que a igualdade passaria sem exercitar a evolução dos melhores pessoais nem
    a do melhor global.

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
    gpu = run_pso_gpu(instance, run, config)
    cpu = run_pso(instance, run, config)

    assert gpu.checkpoints != cpu.checkpoints
    diferenca = require_equivalent_trajectory(gpu, cpu)
    assert 0.0 < diferenca <= ABS_TOL
    assert gpu.solution.tolist() == cpu.solution.tolist()
    assert gpu.evaluations == cpu.evaluations == _ORCAMENTO_REAL


def test_o_modo_de_verificacao_do_pso_substitui_os_resultados_da_gpu() -> None:
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
    cpu = run_pso(instance, run, config)
    verificado = run_pso_gpu(instance, run, config, verify_every_batch=True)
    oficial = run_pso_gpu(instance, run, config)

    assert verificado.checkpoints == cpu.checkpoints
    assert oficial.checkpoints != cpu.checkpoints
    assert verificado.diagnostics["max_numerical_difference"] > 0.0
    assert oficial.diagnostics["max_numerical_difference"] == 0.0


def test_a_trajetoria_oficial_do_pso_reprova_divergencia_de_1e_11() -> None:
    """Validação negativa obrigatória de F8-4, com o eixo medido antes de escrito.

    **A injeção é confinada ao primeiro lote, e a razão é medida.** Somada a
    todos os lotes, uma divergência de `1e-11` é apanhada pelo
    `require_equivalent` que `run_pso_gpu` já aplica ao incumbente antes de
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

    import metaheuristica_gpu.pso as modulo

    instance, run, config = _cenario_real()
    cpu = run_pso(instance, run, config)
    injetado = _objetivo_com_desvio(1e-11, apenas_primeiro_lote=True)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "GpuBatchObjective", injetado)
        gpu = run_pso_gpu(instance, run, config)

    assert injetado.lotes_injetados == 1, "denominador do caso: a injeção foi percorrida"
    assert gpu.evaluations == _ORCAMENTO_REAL, "a execução completou, sem guarda anterior disparar"
    with pytest.raises(NumericalDivergenceError, match="checkpoint 1: total_cost diverge"):
        require_equivalent_trajectory(gpu, cpu)


def test_o_pso_da_replica_compartilha_os_objetos_do_nucleo() -> None:
    """F8-12: a unificação fica presa por identidade de referência.

    O teste prescrito pelo pacote compara `__module__`, e aqui ele é mais forte
    do que isso: compara **identidade de objeto**, porque um invólucro definido
    na réplica teria `__module__` igual a `metaheuristica_gpu.pso` e a asserção
    por módulo ou falharia ou precisaria ser afrouxada até não medir nada. É a
    mesma forma que
    `test_aco_gpu.py::test_gpu_construction_shares_the_cpu_partial_state` já
    usa desde o pacote B5. Uma divergência futura por cópia reaparece como
    falha em vez de ficar silenciosa.

    O **eixo negativo** está aqui dentro: o que continua duplicado de propósito,
    porque o núcleo avalia um candidato por vez e a réplica avalia em lote,
    continua sendo objeto próprio da réplica. Sem essa metade, uma asserção que
    exigisse tudo do núcleo passaria por vacuidade se alguém importasse o
    módulo inteiro.
    """

    import metaheuristica.pso as nucleo
    import metaheuristica_gpu.pso as replica

    unificados = (
        "_Best", "_Particle", "_Trial", "_best_comparison", "_canonical_candidate",
        "_copy_best", "_initial_particle", "_trial_state", "decode_position",
        "_project_position",
    )
    for nome in unificados:
        assert getattr(replica, nome) is getattr(nucleo, nome), nome
        assert getattr(replica, nome).__module__ == "metaheuristica.pso", nome
    assert replica.VELOCITY_LIMIT is nucleo.VELOCITY_LIMIT

    proprios = ("run_pso_gpu", "_Pending", "_decode", "_project")
    for nome in proprios:
        assert getattr(replica, nome).__module__ == "metaheuristica_gpu.pso", nome


def test_o_laco_em_lote_do_enxame_continua_proprio_da_replica() -> None:
    """F8-12: o que **não** foi unificado, medido em vez de afirmado.

    A restrição dura do pacote proíbe alterar a ordem das operações de
    somatório, e importar o laço do núcleo exigiria reescrevê-lo em torno do
    lote. O laço da réplica submete várias tentativas de uma vez, e o do núcleo
    avalia uma por vez: o caso mede essa diferença pelo tamanho dos lotes de
    fato submetidos ao avaliador, e não por leitura do código.
    """

    import metaheuristica_gpu.pso as modulo
    from metaheuristica_gpu.evaluator import HybridEvaluator

    tamanhos: list[int] = []
    original = HybridEvaluator.evaluate_batch

    def espiao(self, solutions):
        tamanhos.append(len(solutions))
        return original(self, solutions)

    instance, run, config = _cenario_real()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(HybridEvaluator, "evaluate_batch", espiao)
        modulo.run_pso_gpu(instance, run, config)

    assert tamanhos, "denominador do caso: o avaliador em lote foi percorrido"
    assert max(tamanhos) > 1, "o laço da réplica submete lote, e não um candidato por vez"
    assert max(tamanhos) <= config.n_particles
