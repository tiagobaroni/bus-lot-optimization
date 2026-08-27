from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    AcoConfig, ObjectiveWeights, RunConfig, load_artesp_instance,
    load_tiny_instance, run_aco,
)
from metaheuristica_gpu.aco import _PartialState, _construct, run_aco_gpu


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
