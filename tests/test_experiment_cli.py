from __future__ import annotations

from pathlib import Path
import shutil

from experiments import run
from experiments.benchmark_batches import select_benchmark
from experiments.config import load_campaign
from experiments.storage import artifact_paths, record_failure


ROOT = Path(__file__).parents[1]


def _config(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    path = tmp_path / "cli.toml"
    path.write_text(
        '''schema_version = 1
name = "cli_test"
purpose = "pilot"
output_root = "out"
seeds = [4]
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
[algorithms.aco]
alpha = [1.0]
beta = [1.0]
rho = [0.1]
n_ants = [20]
''', encoding="utf-8"
    )
    return path


def _invoke(monkeypatch, config_path: Path, *arguments: str) -> int:
    config = load_campaign(config_path, repository_root=config_path.parent)
    monkeypatch.setattr(run, "load_campaign", lambda path: config)
    return run.main(["--config", str(config_path), *arguments])


def test_plan_has_no_output_side_effect(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _config(tmp_path)
    assert _invoke(monkeypatch, config, "plan") == 0
    assert '"expected": 1' in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_cli_execute_resume_and_consolidate(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    assert _invoke(monkeypatch, config, "--allow-unversioned", "execute") == 0
    assert _invoke(monkeypatch, config, "--allow-unversioned", "execute") == 0
    assert _invoke(monkeypatch, config, "--allow-unversioned", "consolidate") == 0
    assert (tmp_path / "out/tables/pilot_manifest.json").is_file()


def test_cli_rejects_incompatible_option(tmp_path: Path, monkeypatch, capsys) -> None:
    assert _invoke(monkeypatch, _config(tmp_path), "--workers", "2", "plan") == 2
    assert "exclusivas" in capsys.readouterr().err


def test_benchmark_execution_is_refused_after_a_second_failure(
    toy_benchmark, monkeypatch, capsys
) -> None:
    """A CLI genérica era o caminho para a terceira tentativa.

    ``run_benchmark retry`` recusa ID com duas tentativas, mas
    ``experiments.run`` tratava a finalidade ``benchmark`` sem limite algum.
    """

    config = toy_benchmark
    scenario = select_benchmark(config, batch=1).scenarios[0]
    paths = artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    )
    record_failure(paths, scenario, RuntimeError("primeira"))
    record_failure(paths, scenario, RuntimeError("segunda"))
    # Sem o resultado publicado o ID volta a parecer pendente para a retomada,
    # que é exatamente o estado em que a terceira tentativa acontecia.
    paths.result.unlink()
    monkeypatch.setattr(run, "load_campaign", lambda path: config)
    assert run.main([
        "--config", str(config.source_path), "--workers", "16", "execute",
    ]) == 2
    assert "segunda falha" in capsys.readouterr().err
    assert not paths.result.exists()
