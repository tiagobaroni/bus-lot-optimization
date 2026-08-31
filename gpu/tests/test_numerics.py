from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    AcoConfig, ObjectiveWeights, RunConfig, evaluate_solution,
    load_artesp_instance, load_tiny_instance, run_aco,
)
from metaheuristica_gpu.numerics import (
    ABS_TOL, NumericalDivergenceError, require_equivalent,
    require_equivalent_trajectory,
)


ROOT = Path(__file__).parents[2]


def test_tolerance_accepts_roundoff_and_rejects_material_difference() -> None:
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    result = evaluate_solution(instance, np.array([0, 0, 1, 1]), k=2, weights=ObjectiveWeights())
    assert require_equivalent(result, replace(result, total_cost=result.total_cost + 5e-13)) <= 1e-12
    with pytest.raises(NumericalDivergenceError, match="total_cost"):
        require_equivalent(result, replace(result, total_cost=result.total_cost + 1e-8))


def test_o_codigo_morto_de_desempate_e_de_sincronizacao_nao_volta() -> None:
    """F8-1, componente `M3`: a remoção fica presa por asserção.

    `arbitrate_best` desempatava por `(custo CPU, rótulos)`, com o custo
    **primeiro**, contra rótulos apenas do caminho normativo: chamá-la
    introduziria divergência de critério entre CPU e GPU onde hoje não existe
    nenhuma. Ela e `synchronized_call` não tinham chamador algum, e
    `synchronization_seconds` não era atribuído em lugar algum do pacote. O
    caso reprova se qualquer um dos três reaparecer.
    """

    from dataclasses import fields

    import metaheuristica_gpu.numerics as numerics
    import metaheuristica_gpu.timing as timing

    assert not hasattr(numerics, "arbitrate_best")
    assert not hasattr(timing, "synchronized_call")
    campos = {item.name for item in fields(timing.GpuTiming)}
    assert "synchronization_seconds" not in campos
    # Eixo negativo: o resto do cronômetro continua publicado, de modo que o
    # caso não passaria por a classe inteira ter sido esvaziada.
    assert {"host_to_device_seconds", "kernel_seconds", "device_to_host_seconds"} <= campos
    assert "synchronization_seconds" not in timing.GpuTiming().to_dict()


@lru_cache(maxsize=None)
def _par_real(budget: int = 400):
    instance = load_artesp_instance(ROOT / "data/instances", 20)
    run = RunConfig(k=5, seed=10, budget=budget)
    config = AcoConfig(alpha=1.0, beta=2.0, rho=0.1, n_ants=20)
    from metaheuristica_gpu.aco import run_aco_gpu

    return run_aco_gpu(instance, run, config), run_aco(instance, run, config)


def test_a_trajetoria_equivalente_admite_a_divergencia_de_um_ulp_e_a_mede() -> None:
    """F8-1, componente `M2`: a régua é `1e-12`, e não igualdade exata.

    Medido em `artesp_rmsp_20`, `K=5`, semente 10 e orçamento 400, em modo
    oficial: os cem checkpoints diferem bit a bit dos da CPU já a partir do
    primeiro, com `max |delta|` de `2,220e-16`, isto é 1/4503 do `abs_tol`
    normativo. A asserção de que a igualdade **exata** falha está aqui dentro
    de propósito: sem ela o caso passaria igual se a divergência fosse zero, e
    seria a igualdade exata que estaria sendo medida.
    """

    gpu, cpu = _par_real()
    assert gpu.checkpoints != cpu.checkpoints
    diferenca = require_equivalent_trajectory(gpu, cpu)
    assert 0.0 < diferenca <= ABS_TOL
    assert diferenca < 1e-15


@pytest.mark.parametrize(
    "delta, reprova", [(5e-13, False), (2e-12, True), (1e-11, True)]
)
def test_a_trajetoria_equivalente_reprova_divergencia_acima_da_regua(
    delta: float, reprova: bool
) -> None:
    """Caso negativo de F8-1 `M2`, nos dois eixos e com a fronteira presa.

    Os três deltas são literais independentes da constante sob verificação:
    `5e-13` está dentro da faixa, `2e-12` e `1e-11` estão fora. Trocar `ABS_TOL`
    por `1e-11` derrubaria o segundo caso, e trocá-la por `1e-13` derrubaria o
    primeiro, de modo que a fronteira fica presa dos dois lados.
    """

    gpu, cpu = _par_real()
    alvo = gpu.checkpoints[0]
    perturbado = replace(
        alvo, evaluation=replace(alvo.evaluation, total_cost=alvo.evaluation.total_cost + delta)
    )
    # Denominador do caso: a perturbação de fato alterou o objeto.
    assert perturbado.evaluation.total_cost != alvo.evaluation.total_cost
    divergente = replace(gpu, checkpoints=(perturbado,) + gpu.checkpoints[1:])
    if reprova:
        with pytest.raises(NumericalDivergenceError, match="checkpoint 1"):
            require_equivalent_trajectory(divergente, cpu)
    else:
        assert require_equivalent_trajectory(divergente, cpu) <= ABS_TOL


class _Execucao:
    """Duble estrutural, com os quatro atributos que a comparação consulta.

    Um dublê é preferível a `dataclasses.replace` sobre `OptimizationResult`
    para estes três eixos: o `__post_init__` do núcleo já recusa orçamento
    incoerente com os limiares dos checkpoints, de modo que construir o caso
    pelo tipo real esbarraria na validação do núcleo antes de chegar à
    comparação que este caso mede.
    """

    def __init__(self, evaluations, solution, checkpoints, evaluation) -> None:
        self.evaluations = evaluations
        self.solution = solution
        self.checkpoints = checkpoints
        self.evaluation = evaluation


def _duble(origem, **mudancas) -> _Execucao:
    campos = {
        "evaluations": origem.evaluations,
        "solution": np.asarray(origem.solution),
        "checkpoints": origem.checkpoints,
        "evaluation": origem.evaluation,
    }
    campos.update(mudancas)
    return _Execucao(**campos)


def test_a_trajetoria_equivalente_reprova_desalinhamento_sem_consultar_tolerancia() -> None:
    """O que não é ponto flutuante é comparado por igualdade exata.

    Solução final diferente é divergência de **critério**, e não de último bit:
    se a comparação de rótulos, do orçamento ou do alinhamento dos checkpoints
    fosse afrouxada, uma GPU que percorresse outra trajetória passaria pelo
    portão desde que os custos coincidissem dentro de `1e-12`.
    """

    gpu, cpu = _par_real()
    # Eixo negativo: os dublês sem mudança alguma passam, logo as falhas abaixo
    # vêm da mudança e não da forma do dublê.
    assert require_equivalent_trajectory(_duble(gpu), _duble(cpu)) <= ABS_TOL

    with pytest.raises(NumericalDivergenceError, match="orçamento consumido diverge"):
        require_equivalent_trajectory(_duble(gpu, evaluations=gpu.evaluations + 1), _duble(cpu))

    rotulos = np.asarray(gpu.solution).copy()
    distintos = np.flatnonzero(rotulos != rotulos[0])
    assert distintos.size, "denominador do caso: a solução tem ao menos dois rótulos"
    rotulos[distintos[0]] = rotulos[0]
    assert rotulos.tolist() != np.asarray(gpu.solution).tolist()
    with pytest.raises(NumericalDivergenceError, match="solução final diverge"):
        require_equivalent_trajectory(_duble(gpu, solution=rotulos), _duble(cpu))

    with pytest.raises(NumericalDivergenceError, match="quantidade de checkpoints diverge"):
        require_equivalent_trajectory(_duble(gpu, checkpoints=gpu.checkpoints[:-1]), _duble(cpu))

    desalinhados = gpu.checkpoints[1:] + gpu.checkpoints[:1]
    with pytest.raises(NumericalDivergenceError, match="checkpoint desalinhado"):
        require_equivalent_trajectory(_duble(gpu, checkpoints=desalinhados), _duble(cpu))
