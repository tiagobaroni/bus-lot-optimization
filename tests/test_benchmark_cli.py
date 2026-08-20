import json
from pathlib import Path

import pytest

from experiments import run_benchmark
from experiments.benchmark_batches import select_benchmark
from experiments.benchmark_freeze import verify_freeze_manifest
from experiments.benchmark_operations import operational_root
from experiments.benchmark_validation import _validate_operations
from experiments.scenarios import expand_scenarios
from experiments.storage import (
    _with_content_hash, artifact_paths, atomic_write_json, read_json,
)
from metaheuristica.errors import ConfigurationError
from tests.toy_repository import write_approved_resource_summary


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


def test_saturated_execute_covers_the_whole_batch(toy_benchmark, monkeypatch, capsys) -> None:
    """O caminho oficial é ``execute --batch N`` sem filtro de subgrupo.

    A invocação por subgrupo submete seis cenários e ocupa seis dos dezesseis
    workers; sem filtros a seleção é o lote inteiro, o diário sai com o nome do
    lote e a barreira o encontra.
    """

    config = toy_benchmark
    selection = select_benchmark(config, batch=1)
    assert selection.name == "batch-01"
    assert len(selection.scenarios) == 324
    raw = config.repository_root / config.output_root / "raw" / config.purpose
    reference = ROOT / "results/raw/benchmark"
    before = set(reference.glob("*")) if reference.exists() else set()
    for scenario in selection.scenarios[:3]:
        artifact_paths(
            config.repository_root / config.output_root, config.purpose, scenario
        ).result.unlink()
    monkeypatch.setattr(run_benchmark, "load_campaign", lambda path: config)
    assert run_benchmark.main([
        "execute", "--config", str(config.source_path), "--batch", "1",
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["summary"] == {
        "expected": 648, "selected": 3, "skipped": 645,
        "succeeded": 3, "failed": 0, "interrupted": False,
    }
    operation = output["operation"]
    assert operation["selection"] == "batch-01"
    assert operation["round"] == "initial"
    assert operation["workers"] == 16
    assert len(operation["scenario_ids"]) == 324
    diary = operational_root(config) / "operations/batch-01_initial.json"
    assert diary.is_file()
    assert sorted(diary.parent.glob("batch-01_*.json")) == [diary]
    write_approved_resource_summary(config, batch=1)
    operations = _validate_operations(
        config, 1, {item.scenario_id for item in selection.scenarios}
    )
    assert len(operations) == 1
    assert len(tuple(raw.glob("*.json"))) == 648
    assert (set(reference.glob("*")) if reference.exists() else set()) == before


def test_workers_other_than_sixteen_are_refused_in_both_gates(
    toy_benchmark, monkeypatch, capsys
) -> None:
    """A seção 29 fala em reduzir workers, e as duas guardas recusam."""

    config = toy_benchmark
    monkeypatch.setattr(run_benchmark, "load_campaign", lambda path: config)
    assert run_benchmark.main([
        "execute", "--config", str(config.source_path), "--batch", "1",
        "--workers", "12",
    ]) == 2
    assert "16 workers" in capsys.readouterr().err
    with pytest.raises(ConfigurationError, match="workers diverge do congelamento"):
        verify_freeze_manifest(config.repository_root, workers=12)
    assert verify_freeze_manifest(
        config.repository_root, workers=16
    )["approved_workers"] == 16
