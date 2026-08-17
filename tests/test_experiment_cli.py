from __future__ import annotations

from pathlib import Path
import shutil

from experiments import run
from experiments.config import load_campaign


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
