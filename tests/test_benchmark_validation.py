from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from experiments.benchmark_batches import select_benchmark
from experiments.benchmark_validation import validate_batch
from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]


def test_barrier_rejects_missing_results_without_writing(tmp_path: Path, monkeypatch) -> None:
    original = load_campaign(ROOT / "experiments/configs/benchmark.toml")
    selection = select_benchmark(original, batch=1)
    config = replace(original, repository_root=tmp_path, output_root="out")
    monkeypatch.setattr(
        "experiments.benchmark_validation.select_benchmark",
        lambda config, batch: selection,
    )
    monkeypatch.setattr("experiments.benchmark_validation.blocked_failures", lambda *a, **k: ())
    with pytest.raises(ConfigurationError, match="resultado ausente"):
        validate_batch(config, batch=1)
    assert not (tmp_path / "out/tables").exists()


def test_valid_controlled_batch_builds_isolated_artifacts(tmp_path: Path, monkeypatch) -> None:
    original = load_campaign(ROOT / "experiments/configs/benchmark.toml")
    selection = select_benchmark(original, batch=1)
    config = replace(original, repository_root=tmp_path, output_root="out")
    documents = [{"scenario": scenario.payload} for scenario in selection.scenarios]
    runs = pd.DataFrame({"scenario_id": [item.scenario_id for item in selection.scenarios]})
    checkpoints = pd.DataFrame({"scenario_id": ["x"] * 32_400})
    monkeypatch.setattr("experiments.benchmark_validation.select_benchmark", lambda c, batch: selection)
    monkeypatch.setattr("experiments.benchmark_validation.blocked_failures", lambda *a, **k: ())
    monkeypatch.setattr("experiments.benchmark_validation._documents", lambda *a, **k: documents)
    monkeypatch.setattr("experiments.benchmark_validation._validate_operations", lambda *a, **k: [{}])
    monkeypatch.setattr("experiments.benchmark_validation.documents_to_frames", lambda docs: (runs, checkpoints))
    report = validate_batch(config, batch=1)
    assert report["passed"] is True
    assert report["completed"] == 324
    assert report["checkpoints"] == 32_400
    assert (tmp_path / report["runs"]["path"]).is_file()
    assert not (tmp_path / "out/tables/benchmark_runs.parquet").exists()
