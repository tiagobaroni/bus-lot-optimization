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
