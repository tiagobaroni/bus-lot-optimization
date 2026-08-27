from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from experiments.provenance import capture_provenance
from metaheuristica.errors import ConfigurationError


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_clean_dirty_and_unversioned_provenance(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.invalid")
    (repository / "tracked.txt").write_text("clean", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "initial")
    clean = capture_provenance(repository)
    assert clean["official"] is True

    (repository / "tracked.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="suja"):
        capture_provenance(repository)
    dirty = capture_provenance(repository, allow_dirty=True)
    assert dirty["official"] is False
    assert dirty["dirty_sha256"]

    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ConfigurationError, match="Git indisponível"):
        capture_provenance(outside)
    assert capture_provenance(outside, allow_unversioned=True)["official"] is False


def test_unversioned_does_not_erase_the_commit_of_a_dirty_worktree(
    tmp_path: Path,
) -> None:
    """F6-12: `--allow-unversioned` mascarava worktree suja.

    O ramo único de exceção cobria os dois motivos, então uma execução sobre
    repositório existente e sujo era registrada como se não houvesse repositório,
    perdendo commit e `dirty_sha256`, que são justamente o que permite
    reconstruir o estado de uma execução não oficial.
    """

    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.invalid")
    (repository / "tracked.txt").write_text("limpo", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "inicial")
    (repository / "tracked.txt").write_text("sujo", encoding="utf-8")

    masked = capture_provenance(repository, allow_unversioned=True)
    assert masked["git_commit"] is not None
    assert len(masked["git_commit"]) == 40
    assert masked["git_dirty"] is True
    assert masked["dirty_sha256"]
    assert masked["nonofficial_reasons"] == ["dirty_worktree"]
    assert masked["official"] is False


def test_unversioned_is_reserved_for_the_absence_of_a_repository(tmp_path: Path) -> None:
    outside = tmp_path / "sem_git"
    outside.mkdir()
    unversioned = capture_provenance(outside, allow_unversioned=True)
    assert unversioned["git_commit"] is None
    assert unversioned["git_dirty"] is None
    assert unversioned["dirty_sha256"] is None
    assert unversioned["nonofficial_reasons"] == ["unversioned"]
    assert unversioned["official"] is False
