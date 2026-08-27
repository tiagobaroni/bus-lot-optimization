from pathlib import Path

import pytest

from metaheuristica import (
    PsoConfig, RunConfig, load_artesp_instance, load_tiny_instance, run_pso,
)
from metaheuristica_gpu.pso import run_pso_gpu


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
