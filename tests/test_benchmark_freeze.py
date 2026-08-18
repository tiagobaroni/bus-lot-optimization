from __future__ import annotations

from pathlib import Path

import pytest

from experiments.benchmark_freeze import _hash_files
from metaheuristica.errors import ConfigurationError


def test_hash_files_detects_missing_and_changed_file(tmp_path: Path) -> None:
    path = tmp_path / "protected.txt"
    path.write_text("first", encoding="utf-8")
    first = _hash_files(tmp_path, ("protected.txt",))
    path.write_text("second", encoding="utf-8")
    second = _hash_files(tmp_path, ("protected.txt",))
    assert first != second
    with pytest.raises(ConfigurationError, match="ausente"):
        _hash_files(tmp_path, ("missing.txt",))
