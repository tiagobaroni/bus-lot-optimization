from __future__ import annotations

from pathlib import Path

import pytest

from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]


def test_official_parameter_divergence_is_rejected(tmp_path: Path) -> None:
    text = (ROOT / "experiments/configs/pilot.toml").read_text(encoding="utf-8")
    path = tmp_path / "pilot.toml"
    path.write_text(text.replace("beta = [2.0]", "beta = [1.0]"), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="diverge"):
        load_campaign(path, repository_root=ROOT)


def test_diagnostic_campaign_is_exempt_from_frozen_parameters() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml")
    assert config.frozen_parameters_sha256 is None
