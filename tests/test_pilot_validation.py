from __future__ import annotations

from pathlib import Path

import pytest

from experiments import pilot_validation
from experiments.config import load_campaign
from experiments.pilot_validation import _deterministic_result
from experiments.scenarios import expand_scenarios
from metaheuristica.errors import ConfigurationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_reproduction_comparison_excludes_only_runtime() -> None:
    left = {"solution": [0, 1], "evaluation": {"total_cost": 0.0}, "runtime_seconds": 1.0}
    right = {"solution": [0, 1], "evaluation": {"total_cost": 0.0}, "runtime_seconds": 2.0}
    assert _deterministic_result(left) == _deterministic_result(right)
    right["solution"] = [1, 0]
    assert _deterministic_result(left) != _deterministic_result(right)


def test_timing_window_accepts_measurement_that_excludes_preprocessing() -> None:
    """Verificação 7: o carregamento aparece fora da janela cronometrada."""

    report = pilot_validation._timing_window_report(
        load_seconds=0.20, window_seconds=1.00, total_seconds=1.21
    )
    assert report["passed"] is True
    assert report["attributed_load_seconds"] == pytest.approx(0.0)
    assert report["load_fraction"] == pytest.approx(0.0)


def test_timing_window_rejects_preprocessing_inside_the_window() -> None:
    """Verificação 7: carregar a instância dentro da janela é recusado."""

    with pytest.raises(ConfigurationError, match="pré-processamento"):
        pilot_validation._timing_window_report(
            load_seconds=0.20, window_seconds=1.20, total_seconds=1.21
        )


def test_timing_window_rejects_partially_included_preprocessing() -> None:
    with pytest.raises(ConfigurationError, match="pré-processamento"):
        pilot_validation._timing_window_report(
            load_seconds=0.20, window_seconds=1.10, total_seconds=1.21
        )


def test_timing_window_rejects_probe_without_sensitivity() -> None:
    """Sem carregamento mensurável a verificação seria vazia, e por isso recusa."""

    with pytest.raises(ConfigurationError, match="sensibilidade"):
        pilot_validation._timing_window_report(
            load_seconds=1e-9, window_seconds=1.00, total_seconds=1.30
        )


def test_timing_probe_measures_the_real_boundary_of_the_timed_window() -> None:
    """Executa a fronteira de produção e confirma que ela exclui o carregamento."""

    config = load_campaign(REPOSITORY_ROOT / "experiments/configs/pilot.toml")
    report = pilot_validation._probe_timing_window(config)
    assert report["passed"] is True
    assert report["load_seconds"] > 0.0
    assert report["window_seconds"] > 0.0
    assert report["excluded_seconds"] >= 0.0


def test_timing_probe_scenario_has_its_own_identity() -> None:
    """A sonda não pode herdar a identidade do cenário oficial de que deriva."""

    config = load_campaign(REPOSITORY_ROOT / "experiments/configs/pilot.toml")
    probe = pilot_validation._timing_probe_scenario(config)
    official = expand_scenarios(config)
    assert probe.payload["budget"] == pilot_validation.TIMING_PROBE_BUDGET
    assert probe.scenario_id not in {item.scenario_id for item in official}
    assert probe.filename not in {item.filename for item in official}
    assert probe.filename.startswith("timing_probe_")
