from __future__ import annotations

from collections import Counter
from pathlib import Path

from experiments.config import load_campaign
from experiments.scenarios import expand_scenarios


ROOT = Path(__file__).parents[1]


def test_official_pilot_expands_18_approved_scenarios() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot.toml")
    scenarios = expand_scenarios(config)
    assert len(scenarios) == 18
    assert len({item.scenario_id for item in scenarios}) == 18
    assert Counter(item.payload["algorithm"] for item in scenarios) == {
        "aco": 6, "pso": 6, "tabu": 6,
    }
    assert Counter(item.payload["k"] for item in scenarios) == {3: 9, 8: 9}
    assert {item.payload["seed"] for item in scenarios} == {20260818}
    assert {item.payload["budget"] for item in scenarios} == {20_000, 60_000, 150_000}
    assert all("frozen_parameters_sha256" in item.payload for item in scenarios)


def test_main_benchmark_expands_1620_approved_scenarios() -> None:
    config = load_campaign(ROOT / "experiments/configs/benchmark.toml")
    scenarios = expand_scenarios(config)
    assert len(scenarios) == 1_620
    assert len({item.scenario_id for item in scenarios}) == 1_620
    assert Counter(item.payload["algorithm"] for item in scenarios) == {
        "aco": 540, "pso": 540, "tabu": 540,
    }
    assert Counter(item.payload["instance"]["name"] for item in scenarios) == {
        "artesp_rmsp_20": 540,
        "artesp_rmsp_60": 540,
        "artesp_rmsp_150": 540,
    }
    assert Counter(item.payload["k"] for item in scenarios) == {
        3: 270, 4: 270, 5: 270, 6: 270, 7: 270, 8: 270,
    }
    assert Counter(item.payload["seed"] for item in scenarios) == {
        seed: 54 for seed in range(10, 40)
    }
