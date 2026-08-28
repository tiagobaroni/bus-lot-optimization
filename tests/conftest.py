"""Fixtures compartilhadas e disponibilidade do pacote-fonte ignorado."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from experiments.config import load_campaign
from tests.toy_repository import build_toy_repository, git, run_toy_batch


PROJECT_ROOT = Path(__file__).parents[1]
# `_temp/` é ignorado pelo Git, logo um clone limpo não tem o pacote-fonte da
# geração de instâncias. Sem declaração explícita, os testes que dependem dele
# quebravam a suíte integral do clone limpo, o que é o oposto da promessa de
# reprodução por comandos explícitos.
SOURCE_PACKAGE = PROJECT_ROOT / "_temp" / "dados_artesp"
SOURCE_OPT_OUT = "BUS_LOT_SEM_PACOTE_FONTE"
SOURCE_SKIP_REASON = (
    f"pacote-fonte ausente em {SOURCE_PACKAGE.relative_to(PROJECT_ROOT)}, que o Git "
    f"ignora; declare {SOURCE_OPT_OUT}=1 para aceitar a suíte sem a cobertura da "
    "geração de instâncias"
)


def source_package_available() -> bool:
    return (SOURCE_PACKAGE / "units.parquet").is_file()


def source_opt_out_declared() -> bool:
    return os.environ.get(SOURCE_OPT_OUT, "") == "1"


def pytest_configure(config: pytest.Config) -> None:
    """Faz o motivo de todo teste pulado aparecer no sumário, inclusive com `-q`.

    `skipif` silencioso é o mecanismo que produz suíte verde sem cobertura, que é
    o padrão de defeito que esta correção existe para não introduzir.
    """

    reportchars = getattr(config.option, "reportchars", "") or ""
    if "s" not in reportchars:
        config.option.reportchars = reportchars + "s"


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
