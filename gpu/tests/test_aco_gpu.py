from pathlib import Path

from metaheuristica import AcoConfig, RunConfig, load_tiny_instance, run_aco
from metaheuristica_gpu.aco import run_aco_gpu


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
