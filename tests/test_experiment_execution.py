from __future__ import annotations

import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from experiments.config import load_campaign
from experiments.consolidation import consolidate_campaign
from experiments.execution import build_plan, execute_campaign
from experiments.execution import _write_interruption_report
from experiments.scenarios import expand_scenarios, file_sha256
from experiments.storage import artifact_paths
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]


def _campaign(tmp_path: Path, *, seeds: str = "[1]"):
    data = tmp_path / "data"
    data.mkdir(parents=True)
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    config = tmp_path / "campaign.toml"
    config.write_text(
        f'''schema_version = 1
name = "tiny_test"
purpose = "pilot"
output_root = "out"
seeds = {seeds}
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
''',
        encoding="utf-8",
    )
    return load_campaign(config, repository_root=tmp_path)


def test_sequential_execution_resume_and_consolidation(tmp_path: Path) -> None:
    config = _campaign(tmp_path)
    first = execute_campaign(config, allow_unversioned=True)
    assert first.succeeded == 1
    assert first.failed == 0
    plan = build_plan(config)
    assert plan.completed == 1
    assert not plan.selected

    second = execute_campaign(config, allow_unversioned=True)
    assert second.succeeded == 0
    assert second.skipped == 1

    manifest = consolidate_campaign(config, allow_unversioned=True)
    assert manifest["complete"] is True
    assert manifest["official"] is False
    runs_path = tmp_path / manifest["runs"]["path"]
    checkpoints_path = tmp_path / manifest["checkpoints"]["path"]
    assert file_sha256(runs_path) == manifest["runs"]["sha256"]
    assert file_sha256(checkpoints_path) == manifest["checkpoints"]["sha256"]
    assert len(pd.read_parquet(runs_path)) == 1
    assert len(pd.read_parquet(checkpoints_path)) == 100


def test_parallel_execution_matches_sequential_deterministic_result(tmp_path: Path) -> None:
    sequential_root = tmp_path / "sequential"
    parallel_root = tmp_path / "parallel"
    sequential = _campaign(sequential_root, seeds="[1, 2]")
    parallel = _campaign(parallel_root, seeds="[1, 2]")
    assert execute_campaign(sequential, workers=1, allow_unversioned=True).succeeded == 2
    assert execute_campaign(parallel, workers=2, allow_unversioned=True).succeeded == 2

    sequential_documents = []
    parallel_documents = []
    for config, target in ((sequential, sequential_documents), (parallel, parallel_documents)):
        for scenario in expand_scenarios(config):
            path = artifact_paths(config.repository_root / config.output_root, config.purpose, scenario).result
            document = json.loads(path.read_text(encoding="utf-8"))
            result = dict(document["result"])
            result.pop("runtime_seconds")
            target.append(result)
    assert sequential_documents == parallel_documents


def test_corrupted_existing_result_is_not_overwritten(tmp_path: Path) -> None:
    config = _campaign(tmp_path)
    scenario = expand_scenarios(config)[0]
    path = artifact_paths(tmp_path / "out", "pilot", scenario).result
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="JSON inválido"):
        execute_campaign(config, allow_unversioned=True)
    assert path.read_text(encoding="utf-8") == "not json"


def test_incomplete_consolidation_requires_explicit_authorization(tmp_path: Path) -> None:
    config = _campaign(tmp_path)
    with pytest.raises(ConfigurationError, match="incompleta"):
        consolidate_campaign(config, allow_unversioned=True)


def test_incomplete_consolidation_is_marked_provisional(tmp_path: Path) -> None:
    config = _campaign(tmp_path, seeds="[1, 2]")
    assert execute_campaign(
        config, max_runs=1, allow_unversioned=True
    ).succeeded == 1
    manifest = consolidate_campaign(
        config, allow_incomplete=True, allow_unversioned=True
    )
    assert manifest["complete"] is False
    assert manifest["official"] is False
    assert manifest["completed"] == 1
    assert manifest["missing"] == 1


def test_consolidation_captures_provenance_before_creating_tables(
    tmp_path: Path, monkeypatch
) -> None:
    config = _campaign(tmp_path)
    execute_campaign(config, allow_unversioned=True)
    tables = tmp_path / "out/tables"

    def provenance_before_outputs(*args, **kwargs):
        assert not tables.exists()
        return {"official": True}

    monkeypatch.setattr(
        "experiments.consolidation.capture_provenance", provenance_before_outputs
    )
    manifest = consolidate_campaign(config)
    assert manifest["complete"] is True


def test_failure_continues_and_is_retried(tmp_path: Path, monkeypatch) -> None:
    config = _campaign(tmp_path, seeds="[1, 2]")
    from experiments import worker

    original = worker.run_scenario
    calls = 0

    def fails_once(scenario, repository_root):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected failure")
        return original(scenario, repository_root)

    monkeypatch.setattr(worker, "run_scenario", fails_once)
    first = execute_campaign(config, allow_unversioned=True)
    assert first.failed == 1
    assert first.succeeded == 1
    assert build_plan(config).failed == 1

    monkeypatch.setattr(worker, "run_scenario", original)
    second = execute_campaign(config, allow_unversioned=True)
    assert second.succeeded == 1
    assert second.failed == 0
    assert build_plan(config).completed == 2
    scenario = expand_scenarios(config)[0]
    failure = artifact_paths(tmp_path / "out", "pilot", scenario).failure
    assert failure.exists()
    assert json.loads(failure.read_text())["attempts"][0]["message"] == "injected failure"


def test_interruption_report_describes_resumable_state(tmp_path: Path) -> None:
    config = _campaign(tmp_path, seeds="[1, 2]")
    assert execute_campaign(
        config, max_runs=1, allow_unversioned=True
    ).succeeded == 1
    _write_interruption_report(config, workers=2)
    path = tmp_path / "out/operational/tiny_test/interruption.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["expected"] == 2
    assert report["completed"] == 1
    assert report["pending"] == 1
    assert report["failed"] == 0
    assert set(report["states"].values()) == {"completed", "pending"}
    assert report["temporary_files"] == []


def test_explicit_ordered_selection_is_preserved(tmp_path: Path) -> None:
    config = _campaign(tmp_path, seeds="[1, 2]")
    scenarios = expand_scenarios(config)
    plan = build_plan(config, selected_scenarios=tuple(reversed(scenarios)))
    assert [item.scenario_id for item in plan.selected] == [
        item.scenario_id for item in reversed(scenarios)
    ]
    with pytest.raises(ConfigurationError, match="incompatíveis"):
        build_plan(config, scenario_id=scenarios[0].scenario_id, selected_scenarios=scenarios)
