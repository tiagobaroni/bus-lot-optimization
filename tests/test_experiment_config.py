from __future__ import annotations

from pathlib import Path

import pytest

from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]


def test_versioned_pilot_is_strict_and_expands_known_dimensions() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot.toml")
    assert config.purpose == "pilot"
    assert config.seeds == (20260817,)
    assert len(config.instances) == 3
    assert set(config.algorithms) == {"tabu", "aco", "pso"}


def test_missing_configuration_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="inexistente"):
        load_campaign(tmp_path / "missing.toml")


def test_unknown_root_field_is_rejected(tmp_path: Path) -> None:
    source = ROOT / "experiments/configs/pilot.toml"
    target = tmp_path / "invalid.toml"
    target.write_text(source.read_text() + "\nunknown = 1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="desconhecidos"):
        load_campaign(target)


def test_duplicate_seed_is_rejected(tmp_path: Path) -> None:
    text = (ROOT / "experiments/configs/pilot.toml").read_text()
    target = tmp_path / "invalid.toml"
    target.write_text(text.replace("[20260817]", "[1, 1]", 1), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="duplicados"):
        load_campaign(target)
