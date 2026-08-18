from pathlib import Path

import pytest

from experiments.benchmark_batches import (
    benchmark_subgroups, select_benchmark, validate_benchmark_partition,
)
from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "experiments/configs/benchmark.toml"


def test_official_benchmark_partition_is_exact() -> None:
    config = load_campaign(CONFIG)
    report = validate_benchmark_partition(config)
    assert report["scenarios"] == 1_620
    assert report["batches"] == 5
    assert report["subgroups"] == 270
    all_ids: set[str] = set()
    for batch in range(1, 6):
        selection = select_benchmark(config, batch=batch)
        assert len(selection.scenarios) == 324
        assert set(selection.seeds) == set(range(10 + (batch - 1) * 6, 16 + (batch - 1) * 6))
        assert not (all_ids & {item.scenario_id for item in selection.scenarios})
        all_ids.update(item.scenario_id for item in selection.scenarios)


def test_each_batch_has_54_complete_subgroups() -> None:
    config = load_campaign(CONFIG)
    groups = benchmark_subgroups(config, 1)
    assert len(groups) == 54
    assert all(len(group.scenarios) == 6 for group in groups)
    selected = select_benchmark(
        config, batch=1, algorithm="aco", instance="artesp_rmsp_150", k=8
    )
    assert {item.payload["seed"] for item in selected.scenarios} == set(range(10, 16))


@pytest.mark.parametrize("batch", [0, 6, True])
def test_invalid_batch_is_rejected(batch) -> None:
    with pytest.raises(ConfigurationError, match="lote"):
        select_benchmark(load_campaign(CONFIG), batch=batch)


def test_partial_or_unknown_subgroup_is_rejected() -> None:
    config = load_campaign(CONFIG)
    with pytest.raises(ConfigurationError, match="conjuntamente"):
        select_benchmark(config, batch=1, algorithm="aco")
    with pytest.raises(ConfigurationError, match="incompleto"):
        select_benchmark(config, batch=1, algorithm="none", instance="none", k=99)
