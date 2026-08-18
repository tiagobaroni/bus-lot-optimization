from pathlib import Path

from metaheuristica import PsoConfig, RunConfig, load_tiny_instance, run_pso
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
