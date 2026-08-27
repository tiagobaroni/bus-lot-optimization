"""Garantias de durabilidade da escrita atômica de Parquet."""

from __future__ import annotations

import os
from pathlib import Path
import stat

import pandas as pd

from experiments.consolidation import _atomic_parquet


def _fsync_spy(monkeypatch) -> list[bool]:
    """Registra, para cada `os.fsync`, se o descritor era de diretório.

    O efeito observável de F6-10, sobreviver a uma queda de energia, não é
    testável em suíte. O que é testável é a chamada: sem sincronizar o
    diretório, a entrada trocada por `os.replace` pode se perder mesmo com o
    conteúdo do arquivo já em disco.
    """

    observed: list[bool] = []
    original = os.fsync

    def spy(descriptor: int) -> None:
        observed.append(stat.S_ISDIR(os.fstat(descriptor).st_mode))
        original(descriptor)

    monkeypatch.setattr(os, "fsync", spy)
    return observed


def test_atomic_parquet_syncs_the_file_and_then_the_directory(
    tmp_path: Path, monkeypatch
) -> None:
    observed = _fsync_spy(monkeypatch)
    destination = tmp_path / "tabelas" / "execucoes.parquet"
    frame = pd.DataFrame({"scenario_id": ["a", "b"], "total_cost": [0.5, 0.25]})

    _atomic_parquet(destination, frame)

    assert observed == [False, True], (
        "esperado sincronizar o arquivo e, depois da troca, o diretório"
    )
    assert pd.read_parquet(destination).equals(frame)
    assert not list(destination.parent.glob("*.tmp"))


def test_atomic_parquet_replaces_an_existing_table_in_place(
    tmp_path: Path, monkeypatch
) -> None:
    observed = _fsync_spy(monkeypatch)
    destination = tmp_path / "execucoes.parquet"
    _atomic_parquet(destination, pd.DataFrame({"valor": [1]}))
    _atomic_parquet(destination, pd.DataFrame({"valor": [2, 3]}))

    assert observed == [False, True, False, True]
    assert pd.read_parquet(destination)["valor"].tolist() == [2, 3]
