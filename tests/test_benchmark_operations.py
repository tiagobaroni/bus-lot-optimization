from pathlib import Path
import shutil

import pytest

from experiments.benchmark_operations import initial_coverage
from experiments.config import load_campaign
from experiments.scenarios import expand_scenarios
from experiments.storage import artifact_paths, record_failure


ROOT = Path(__file__).parents[1]


def _benchmark(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    path = tmp_path / "campaign.toml"
    path.write_text('''schema_version = 1
name = "tiny_benchmark"
purpose = "benchmark"
output_root = "out"
seeds = [10, 11, 12, 13, 14, 15]
cache_enabled = false
[weights]
demand = 0.25
production = 0.25
territorial = 0.25
affinity = 0.25
[[instances]]
name = "tiny"
path = "data/tiny.json"
budget = 100
k_values = [2]
[algorithms.pso]
n_particles = [20]
inertia = [0.7]
cognitive = [1.5]
social = [1.5]
''', encoding="utf-8")
    return load_campaign(path, repository_root=tmp_path)


def test_initial_coverage_distinguishes_absent_and_failed(tmp_path: Path, monkeypatch) -> None:
    config = _benchmark(tmp_path)
    # O seletor oficial exige 324 IDs; neste teste isolamos sua saída mínima.
    scenarios = expand_scenarios(config)
    from experiments import benchmark_operations
    from experiments.benchmark_batches import BenchmarkSelection
    selection = BenchmarkSelection(1, tuple(range(10, 16)), scenarios)
    monkeypatch.setattr(benchmark_operations, "select_benchmark", lambda *a, **k: selection)
    assert initial_coverage(config, batch=1) is False
    for scenario in scenarios:
        record_failure(
            artifact_paths(tmp_path / "out", "benchmark", scenario), scenario,
            RuntimeError("falha injetada"),
        )
    assert initial_coverage(config, batch=1) is True
