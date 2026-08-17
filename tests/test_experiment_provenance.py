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
