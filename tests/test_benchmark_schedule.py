from pathlib import Path

import pandas as pd
import pytest

from experiments.benchmark_schedule import load_pilot_estimates, schedule_batch
from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]
PILOT = ROOT / "results/tables/pilot_runs.parquet"


def test_interpolation_and_schedule_are_deterministic() -> None:
    estimates = load_pilot_estimates(PILOT)
    low = estimates[("aco", "artesp_rmsp_150", 3)]
    high = estimates[("aco", "artesp_rmsp_150", 8)]
    assert estimates[("aco", "artesp_rmsp_150", 4)] == pytest.approx(low + (high - low) / 5)
    config = load_campaign(ROOT / "experiments/configs/benchmark.toml")
    first = schedule_batch(config, batch=1, pilot_runs=PILOT)
    second = schedule_batch(config, batch=1, pilot_runs=PILOT)
    assert first == second
    assert len(first) == 54
    assert first[0].selection.algorithm == "aco"
    assert first[0].selection.instance == "artesp_rmsp_150"
    assert first[0].selection.k == 8
    assert [item.rank for item in first] == list(range(1, 55))


def test_invalid_pilot_time_is_rejected(tmp_path: Path) -> None:
    frame = pd.read_parquet(PILOT)
    frame.loc[0, "runtime_seconds"] = 0
    path = tmp_path / "pilot.parquet"
    frame.to_parquet(path, index=False)
    with pytest.raises(ConfigurationError, match="inválido"):
        load_pilot_estimates(path)
