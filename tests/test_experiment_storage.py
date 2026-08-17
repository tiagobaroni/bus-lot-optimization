from __future__ import annotations

from pathlib import Path

from experiments.scenarios import Scenario
from experiments.storage import ArtifactPaths, read_json, record_failure


def _scenario() -> Scenario:
    payload = {
        "schema_version": 1, "purpose": "pilot", "algorithm": "pso",
        "parameters": {}, "instance": {"name": "x", "path": "x", "sha256": "0" * 64},
        "k": 2, "seed": 1, "budget": 100,
        "weights": {"demand": 0.25, "production": 0.25, "territorial": 0.25, "affinity": 0.25},
        "cache_enabled": False,
    }
    return Scenario(payload, "a" * 64, "scenario.json")


def test_failure_history_appends_attempts_atomically(tmp_path: Path) -> None:
    paths = ArtifactPaths(tmp_path / "result.json", tmp_path / "failure.json")
    scenario = _scenario()
    record_failure(paths, scenario, ValueError("first"))
    record_failure(paths, scenario, RuntimeError("second"))
    document = read_json(paths.failure)
    assert [attempt["message"] for attempt in document["attempts"]] == ["first", "second"]
    assert not list(tmp_path.glob("*.tmp"))
