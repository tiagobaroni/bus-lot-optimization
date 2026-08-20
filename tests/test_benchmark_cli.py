from pathlib import Path

from experiments import run_benchmark
from experiments.scenarios import expand_scenarios
from experiments.storage import (
    _with_content_hash, artifact_paths, atomic_write_json, read_json,
)


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "experiments/configs/benchmark.toml"


def test_schedule_and_plan_are_read_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_benchmark, "verify_freeze_manifest", lambda *a, **k: {"schema_version": 1})
    raw = ROOT / "results/raw/benchmark"
    before = set(raw.glob("*")) if raw.exists() else set()
    assert run_benchmark.main(["schedule", "--config", str(CONFIG)]) == 0
    assert '"batches"' in capsys.readouterr().out
    assert run_benchmark.main([
        "plan", "--config", str(CONFIG), "--batch", "1",
        "--algorithm", "aco", "--instance", "artesp_rmsp_150", "--k", "8",
    ]) == 0
    output = capsys.readouterr().out
    assert '"expected": 6' in output
    assert (set(raw.glob("*")) if raw.exists() else set()) == before


def test_cli_rejects_partial_subgroup_and_wrong_workers(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_benchmark, "verify_freeze_manifest", lambda *a, **k: {"schema_version": 1})
    assert run_benchmark.main([
        "plan", "--config", str(CONFIG), "--batch", "1", "--algorithm", "aco",
    ]) == 2
    assert "conjuntamente" in capsys.readouterr().err
    assert run_benchmark.main([
        "readiness", "--config", str(CONFIG), "--workers", "8",
    ]) == 2
    assert "16 workers" in capsys.readouterr().err


def test_preflight_inspects_existing_results_instead_of_counting(toy_benchmark) -> None:
    """O preflight contava resultados e não olhava se eram oficiais."""

    config = toy_benchmark
    known = {item.filename: item for item in expand_scenarios(config)}
    inspection = run_benchmark.inspect_existing_results(config, known)
    assert len(inspection["existing"]) == 648
    assert inspection["unexpected"] == []
    assert inspection["nonofficial"] == []

    scenario = known[inspection["existing"][0]]
    path = artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    ).result
    document = read_json(path)
    document["official"] = False
    atomic_write_json(path, _with_content_hash(document))
    intruso = config.repository_root / config.output_root / "raw" / config.purpose
    (intruso / "alien_result.json").write_text("{}", encoding="utf-8")
    inspection = run_benchmark.inspect_existing_results(config, known)
    assert inspection["nonofficial"] == [scenario.filename]
    assert inspection["unexpected"] == ["alien_result.json"]
