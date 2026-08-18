from pathlib import Path

from metaheuristica_gpu.config import load_gpu_config
from metaheuristica_gpu.scenarios import expand_gpu_scenarios


ROOT = Path(__file__).parents[2]


def test_official_gpu_campaign_expands_60_isolated_ids() -> None:
    config = load_gpu_config(ROOT / "gpu/configs/gpu_benchmark.toml")
    scenarios = expand_gpu_scenarios(config)
    assert len(scenarios) == 60
    assert len({item.scenario_id for item in scenarios}) == 60
    assert {item.payload["algorithm"] for item in scenarios} == {"aco", "pso"}
    assert {item.payload["seed"] for item in scenarios} == set(range(10, 40))
    assert {item.payload["k"] for item in scenarios} == {5}
    assert {item.payload["precision"] for item in scenarios} == {"float64"}
