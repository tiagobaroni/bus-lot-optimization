from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from experiments.config import load_campaign
from experiments.scenarios import canonical_json, expand_scenarios


ROOT = Path(__file__).parents[1]


def test_official_tuning_configuration_expands_exact_protocol() -> None:
    config = load_campaign(ROOT / "experiments/configs/tuning.toml")
    scenarios = expand_scenarios(config)
    assert len(scenarios) == 440
    assert Counter(item.payload["algorithm"] for item in scenarios) == {
        "aco": 160, "pso": 160, "tabu": 120,
    }
    assert {item.payload["instance"]["name"] for item in scenarios} == {
        "artesp_rmsp_60"
    }
    assert {item.payload["k"] for item in scenarios} == {5}
    assert {item.payload["budget"] for item in scenarios} == {60000}
    assert {item.payload["cache_enabled"] for item in scenarios} == {False}
    assert {tuple(item.payload["weights"].values()) for item in scenarios} == {
        (0.25, 0.25, 0.25, 0.25)
    }

    seeds_by_configuration: dict[tuple[str, bytes], set[int]] = defaultdict(set)
    for scenario in scenarios:
        key = scenario.payload["algorithm"], canonical_json(scenario.payload["parameters"])
        seeds_by_configuration[key].add(scenario.payload["seed"])
    assert len(seeds_by_configuration) == 44
    assert all(seeds == set(range(10)) for seeds in seeds_by_configuration.values())
