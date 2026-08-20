"""Barreira de lote exercitada com validadores reais.

Os testes usam o repositório de brinquedo de ``conftest.py``, com dois lotes
completos executados pelo caminho saturado. Nenhum deles substitui
``select_benchmark``, ``blocked_failures``, ``_documents``,
``_validate_operations`` ou ``documents_to_frames`` por dublê, com uma única
exceção nomeada e justificada no teste da contagem de 324.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.benchmark_batches import BenchmarkSelection, select_benchmark
from experiments.benchmark_freeze import FREEZE_PATH
from experiments.benchmark_operations import blocked_failures, operational_root
from experiments.benchmark_validation import validate_batch
from experiments.scenarios import file_sha256
from experiments.storage import (
    _with_content_hash, artifact_paths, atomic_write_json, read_json, record_failure,
)
from metaheuristica.errors import ConfigurationError
from tests.toy_repository import git


def _result_path(config, *, batch: int = 1, index: int = 0) -> Path:
    scenario = select_benchmark(config, batch=batch).scenarios[index]
    return artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    ).result


def _rewrite(path: Path, document: dict) -> None:
    atomic_write_json(path, _with_content_hash(document))


def _diary(config, *, batch: int = 1) -> Path:
    return operational_root(config) / "operations" / f"batch-{batch:02d}_initial.json"


def test_barrier_writes_outside_versioned_tables_and_leaves_worktree_clean(
    toy_benchmark,
) -> None:
    config = toy_benchmark
    root = config.repository_root
    report = validate_batch(config, batch=1)
    # A worktree limpa é o oráculo de F6-01, e as duas asseverações seguintes
    # impedem que ele passe apenas porque o .gitignore ganhou a linha de rede.
    assert git(root, "status", "--porcelain", "--untracked-files=all") == ""
    assert not (root / "results/tables/benchmark_batches").exists()
    assert report["runs"]["path"].startswith("results/operational/")
    assert report["checkpoint_table"]["path"].startswith("results/operational/")
    assert (root / report["runs"]["path"]).is_file()
    assert file_sha256(root / report["runs"]["path"]) == report["runs"]["sha256"]


def test_barrier_chains_two_real_batches_and_records_provenance(toy_benchmark) -> None:
    config = toy_benchmark
    root = config.repository_root
    head = git(root, "rev-parse", "HEAD").strip()
    first = validate_batch(config, batch=1)
    assert first["passed"] is True
    assert first["completed"] == 324
    assert first["checkpoints"] == 32_400
    assert first["operations"] == 1
    assert first["git_commit"] == head
    assert first["git_dirty"] is False
    assert first["results_commit"] == head
    assert first["freeze_sha256"] == file_sha256(root / FREEZE_PATH)
    second = validate_batch(config, batch=2)
    assert second["batch"] == 2
    assert second["completed"] == 324
    assert second["scenario_ids_sha256"] != first["scenario_ids_sha256"]
    assert (operational_root(config) / "barriers/batch-02.json").is_file()


def test_barrier_refuses_batch_two_before_the_previous_barrier(toy_benchmark) -> None:
    with pytest.raises(ConfigurationError, match="barreira anterior"):
        validate_batch(toy_benchmark, batch=2)


def test_barrier_refuses_second_failure_recorded_in_the_history(toy_benchmark) -> None:
    config = toy_benchmark
    scenario = select_benchmark(config, batch=1).scenarios[0]
    paths = artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    )
    record_failure(paths, scenario, RuntimeError("primeira"))
    record_failure(paths, scenario, RuntimeError("segunda"))
    assert paths.result.is_file()
    assert blocked_failures(config, batch=1) == (scenario.scenario_id,)
    with pytest.raises(ConfigurationError, match="segunda falha"):
        validate_batch(config, batch=1)


def test_barrier_refuses_temporary_files(toy_benchmark) -> None:
    config = toy_benchmark
    raw = config.repository_root / config.output_root / "raw" / config.purpose
    (raw / "pendente.tmp").write_text("", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="temporários"):
        validate_batch(config, batch=1)


def test_barrier_refuses_alien_artifact_in_the_results_directory(toy_benchmark) -> None:
    config = toy_benchmark
    raw = config.repository_root / config.output_root / "raw" / config.purpose
    (raw / "alien_result.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="resultado inesperado"):
        validate_batch(config, batch=1)


def test_barrier_refuses_missing_result(toy_benchmark) -> None:
    config = toy_benchmark
    _result_path(config).unlink()
    with pytest.raises(ConfigurationError, match="resultado ausente"):
        validate_batch(config, batch=1)


def test_barrier_refuses_batch_short_of_the_expected_count(
    toy_benchmark, monkeypatch
) -> None:
    """Único dublê da suíte, e ele é indispensável.

    ``select_benchmark`` já recusa lote diferente de 324, de modo que a guarda de
    contagem da barreira só pode ser exercitada com um seletor que devolva menos.
    Sem este teste, trocar a igualdade por ``>= 1`` sobrevive à suíte inteira.
    """

    config = toy_benchmark
    complete = select_benchmark(config, batch=1)
    truncated = BenchmarkSelection(
        complete.batch, complete.seeds, complete.scenarios[:-1]
    )
    monkeypatch.setattr(
        "experiments.benchmark_validation.select_benchmark",
        lambda config, batch: truncated,
    )
    with pytest.raises(ConfigurationError, match="324 resultados"):
        validate_batch(config, batch=1)


def test_barrier_refuses_nonofficial_result(toy_benchmark) -> None:
    config = toy_benchmark
    path = _result_path(config)
    document = read_json(path)
    document["official"] = False
    _rewrite(path, document)
    with pytest.raises(ConfigurationError, match="não oficial"):
        validate_batch(config, batch=1)


def test_barrier_refuses_results_from_divergent_commits(toy_benchmark) -> None:
    config = toy_benchmark
    path = _result_path(config)
    document = read_json(path)
    document["provenance"] = {**document["provenance"], "git_commit": "0" * 40}
    _rewrite(path, document)
    with pytest.raises(ConfigurationError, match="proveniência"):
        validate_batch(config, batch=1)


def test_barrier_refuses_diary_without_full_initial_coverage(toy_benchmark) -> None:
    config = toy_benchmark
    path = _diary(config)
    document = read_json(path)
    document["scenario_ids"] = document["scenario_ids"][:-1]
    atomic_write_json(path, document)
    with pytest.raises(ConfigurationError, match="diário não cobre"):
        validate_batch(config, batch=1)


def test_barrier_refuses_absent_diary(toy_benchmark) -> None:
    config = toy_benchmark
    _diary(config).unlink()
    with pytest.raises(ConfigurationError, match="diário não cobre"):
        validate_batch(config, batch=1)


def test_barrier_refuses_operation_without_session(toy_benchmark) -> None:
    config = toy_benchmark
    path = _diary(config)
    document = read_json(path)
    document["sessions"] = []
    atomic_write_json(path, document)
    with pytest.raises(ConfigurationError, match="sem sessão"):
        validate_batch(config, batch=1)


def test_barrier_refuses_resource_summary_not_approved(toy_benchmark) -> None:
    config = toy_benchmark
    document = read_json(_diary(config))
    summary_path = config.repository_root / document["sessions"][0]["resource_summary"]
    summary = read_json(summary_path)
    summary["passed"] = False
    atomic_write_json(summary_path, summary)
    with pytest.raises(ConfigurationError, match="recursos"):
        validate_batch(config, batch=1)


def test_barrier_refuses_dirty_worktree(toy_benchmark) -> None:
    config = toy_benchmark
    (config.repository_root / "rascunho.txt").write_text("sujo", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="worktree suja"):
        validate_batch(config, batch=1)


def test_barrier_refuses_divergent_freeze(toy_benchmark) -> None:
    config = toy_benchmark
    path = config.repository_root / FREEZE_PATH
    manifest = read_json(path)
    manifest["approved_workers"] = 8
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="workers diverge do congelamento"):
        validate_batch(config, batch=1)
