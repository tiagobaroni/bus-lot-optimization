from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.config import load_campaign
from experiments.scenarios import expand_scenarios, select_scenario
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]


def test_diagnostic_pilot_expands_to_54_stably_ordered_scenarios() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml")
    first = expand_scenarios(config)
    second = expand_scenarios(config)
    assert len(first) == 54
    assert first == second
    assert len({scenario.scenario_id for scenario in first}) == 54
    assert len({scenario.filename for scenario in first}) == 54


def test_selection_accepts_full_id_and_unique_prefix() -> None:
    scenarios = expand_scenarios(load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml"))
    expected = scenarios[0]
    assert select_scenario(scenarios, expected.scenario_id) == expected
    assert select_scenario(scenarios, expected.scenario_id[:12]) == expected


def test_selection_rejects_missing_or_ambiguous_id() -> None:
    scenarios = expand_scenarios(load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml"))
    with pytest.raises(ConfigurationError, match="inexistente"):
        select_scenario(scenarios, "ffffffffffff")
    with pytest.raises(ConfigurationError, match="ambíguo"):
        select_scenario(scenarios, scenarios[0].scenario_id[:1])


def test_output_root_does_not_participate_in_identity() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot.toml")
    changed = replace(config, output_root="another-output")
    assert [item.scenario_id for item in expand_scenarios(config)] == [
        item.scenario_id for item in expand_scenarios(changed)
    ]
