from pathlib import Path

from experiments import run_benchmark


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
