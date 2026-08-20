"""Fixtures compartilhadas da suíte."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from experiments.config import load_campaign
from tests.toy_repository import build_toy_repository, git, run_toy_batch


@pytest.fixture(scope="session")
def toy_benchmark_source(tmp_path_factory) -> Path:
    """Repositório de brinquedo com os lotes 1 e 2 concluídos.

    Construído uma única vez por sessão, porque executar 648 cenários reais é
    caro. Cada teste recebe uma cópia gravável, de modo que mutações de um caso
    negativo não contaminem os demais.
    """

    root = tmp_path_factory.mktemp("toy_benchmark") / "repositorio"
    config = build_toy_repository(root)
    for batch in (1, 2):
        run_toy_batch(config, batch=batch)
    assert git(root, "status", "--porcelain", "--untracked-files=all") == ""
    return root


@pytest.fixture
def toy_benchmark(toy_benchmark_source: Path, tmp_path: Path):
    root = tmp_path / "repositorio"
    shutil.copytree(toy_benchmark_source, root, symlinks=True)
    return load_campaign(
        root / "experiments/configs/benchmark.toml", repository_root=root
    )
