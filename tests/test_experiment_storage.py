from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil

from experiments.config import load_campaign
from experiments.execution import build_plan, execute_campaign
from experiments.scenarios import Scenario, expand_scenarios
from experiments.storage import (
    ArtifactPaths, ScenarioState, _with_content_hash, artifact_paths,
    atomic_write_json, classify, read_json, record_failure, record_interrupted,
)


ROOT = Path(__file__).parents[1]


def _scenario() -> Scenario:
    payload = {
        "schema_version": 1, "purpose": "pilot", "algorithm": "pso",
        "parameters": {}, "instance": {"name": "x", "path": "x", "sha256": "0" * 64},
        "k": 2, "seed": 1, "budget": 100,
        "weights": {"demand": 0.25, "production": 0.25, "territorial": 0.25, "affinity": 0.25},
        "cache_enabled": False,
    }
    return Scenario(payload, "a" * 64, "scenario.json")


def _paths(tmp_path: Path) -> ArtifactPaths:
    return ArtifactPaths(
        tmp_path / "result.json",
        tmp_path / "failure.json",
        tmp_path / "failure.interrupted.json",
    )


def test_failure_history_appends_attempts_atomically(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    scenario = _scenario()
    record_failure(paths, scenario, ValueError("first"))
    record_failure(paths, scenario, RuntimeError("second"))
    document = read_json(paths.failure)
    assert [attempt["message"] for attempt in document["attempts"]] == ["first", "second"]
    assert not list(tmp_path.glob("*.tmp"))


def test_interruption_record_does_not_consume_an_attempt(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    scenario = _scenario()
    record_failure(paths, scenario, ValueError("primeira"))
    record_interrupted(paths, scenario, RuntimeError("worker morto"))
    record_interrupted(paths, scenario, RuntimeError("worker morto outra vez"))
    assert len(read_json(paths.failure)["attempts"]) == 1
    interruption = read_json(paths.interrupted)
    assert interruption["kind"] == "interrupted"
    assert len(interruption["events"]) == 2
    assert classify(paths, scenario) is ScenarioState.FAILED
    paths.failure.unlink()
    assert classify(paths, scenario) is ScenarioState.PENDING


def _benchmark_campaign(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir(parents=True)
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    path = tmp_path / "campaign.toml"
    path.write_text('''schema_version = 1
name = "toy_official"
purpose = "benchmark"
output_root = "out"
seeds = [1]
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


def test_nonofficial_benchmark_result_is_not_completed(tmp_path: Path) -> None:
    """Resultado gerado fora do fluxo oficial não conclui cenário do benchmark."""

    config = _benchmark_campaign(tmp_path)
    assert execute_campaign(config, allow_unversioned=True).succeeded == 1
    scenario = expand_scenarios(config)[0]
    paths = artifact_paths(tmp_path / "out", "benchmark", scenario)
    document = read_json(paths.result)
    assert document["official"] is False
    assert classify(paths, scenario) is ScenarioState.PENDING
    plan = build_plan(config)
    assert plan.completed == 0
    assert [item.scenario_id for item in plan.selected] == [scenario.scenario_id]

    official = dict(document)
    official["provenance"] = {**document["provenance"], "official": True}
    official["official"] = True
    atomic_write_json(paths.result, _with_content_hash(official))
    assert classify(paths, scenario) is ScenarioState.COMPLETED
    assert not build_plan(config).selected


def test_nonofficial_result_still_completes_a_development_purpose(tmp_path: Path) -> None:
    """A recusa é da finalidade benchmark, e não do piloto ou do tuning."""

    config = _benchmark_campaign(tmp_path)
    pilot = replace(config, purpose="pilot")
    scenario = expand_scenarios(pilot)[0]
    assert scenario.payload["purpose"] == "pilot"
    assert execute_campaign(pilot, allow_unversioned=True).succeeded == 1
    paths = artifact_paths(tmp_path / "out", "pilot", scenario)
    assert read_json(paths.result)["official"] is False
    assert classify(paths, scenario) is ScenarioState.COMPLETED
