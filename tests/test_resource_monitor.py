from __future__ import annotations

import csv
from dataclasses import MISSING, fields
import os
from pathlib import Path
import sys
import time
import warnings

import pytest

from experiments.resource_monitor import (
    MAX_OPTIMIZER_CPU_RATIO,
    ResourceMonitor,
    read_samples,
    sample_process_tree,
    summarize_samples,
)
from metaheuristica.errors import ConfigurationError


def _sample(**changes):
    row = {
        "elapsed_seconds": 0.0,
        "cpu_percent": 100.0,
        "rss_bytes": 1_000,
        "descendant_rss_bytes": 500,
        "process_count": 2,
        "descendant_count": 1,
        "optimizer_process_count": 1,
        "max_optimizer_threads": 1,
        "active_optimizer_threads": 1,
        "max_active_threads_per_optimizer": 1,
        "memory_total_bytes": 32 * 1024 ** 3,
        "memory_available_bytes": 16 * 1024 ** 3,
        "swap_total_bytes": 4 * 1024 ** 3,
        "swap_free_bytes": 4 * 1024 ** 3,
    }
    row.update(changes)
    return row


def test_resource_summary_applies_approved_limits() -> None:
    summary = summarize_samples(
        [_sample(), _sample(elapsed_seconds=1.0, optimizer_process_count=0)], workers=16
    )
    assert summary["passed"] is True
    assert summary["minimum_memory_required_bytes"] == int(32 * 1024 ** 3 * 0.10)


def test_resource_summary_rejects_swap_threads_memory_and_cpu() -> None:
    summary = summarize_samples([
        _sample(),
        _sample(
            elapsed_seconds=1.0,
            memory_available_bytes=1,
            swap_free_bytes=0,
            max_optimizer_threads=4,
            active_optimizer_threads=2,
            max_active_threads_per_optimizer=2,
            cpu_percent=2000.0,
            optimizer_process_count=1,
        ),
    ], workers=16)
    assert summary["passed"] is False
    assert set(name for name, passed in summary["checks"].items() if not passed) == {
        "memory_margin", "swap_unchanged", "one_active_thread_per_optimizer",
        "cpu_within_workers", "no_persistent_optimizers",
    }


def test_monitor_writes_readable_csv(tmp_path: Path) -> None:
    path = tmp_path / "resources.csv"
    with ResourceMonitor(path, workers=1, interval_seconds=0.01):
        pass
    rows = read_samples(path)
    assert len(rows) >= 2
    assert rows[0]["process_count"] >= 1


def test_criteria_are_computed_per_session_and_not_over_the_whole_series() -> None:
    """F7-5: um intervalo não monitorado entrava nos critérios como observado.

    O monitor recarrega do CSV as amostras da sessão anterior. Com a série
    tratada como contínua, uma pausa de um dia em que o uso normal da máquina
    consumisse swap não devolvido reprovava um lote inteiro já concluído.
    """

    anterior = [
        _sample(session_id="2026-08-19T00:00:00Z", swap_free_bytes=4 * 1024 ** 3),
        _sample(
            session_id="2026-08-19T00:00:00Z",
            elapsed_seconds=1.0,
            swap_free_bytes=4 * 1024 ** 3,
            memory_available_bytes=1,
        ),
    ]
    atual = [
        _sample(session_id="2026-08-20T00:00:00Z", swap_free_bytes=3 * 1024 ** 3),
        _sample(
            session_id="2026-08-20T00:00:00Z",
            elapsed_seconds=3.0,
            swap_free_bytes=3 * 1024 ** 3,
            optimizer_process_count=0,
        ),
    ]

    summary = summarize_samples(anterior + atual, workers=16)
    assert summary["checks"]["swap_unchanged"] is True
    assert summary["checks"]["memory_margin"] is True
    assert summary["swap_consumed_bytes"] == 0
    assert summary["passed"] is True
    assert summary["session_id"] == "2026-08-20T00:00:00Z"
    assert summary["samples_total"] == 4
    assert summary["samples_session"] == 2


def test_a_series_without_session_column_is_summarized_as_a_single_legacy_session() -> None:
    summary = summarize_samples(
        [_sample(), _sample(elapsed_seconds=1.0, optimizer_process_count=0)], workers=16
    )
    assert summary["session_id"] == "legado"
    assert summary["samples_total"] == summary["samples_session"] == 2
    assert summary["passed"] is True


def test_resumption_keeps_the_absolute_instant_of_every_sample(tmp_path: Path) -> None:
    """F7-6: `elapsed_seconds` é tempo monitorado e esconde a parada real."""

    path = tmp_path / "resources.csv"
    with ResourceMonitor(path, workers=1, interval_seconds=0.01) as first:
        pass
    with ResourceMonitor(path, workers=1, interval_seconds=0.01) as second:
        pass

    rows = read_samples(path)
    sessions = [row["session_id"] for row in rows]
    assert first.session_id != second.session_id
    assert set(sessions) == {first.session_id, second.session_id}

    anteriores = [row for row in rows if row["session_id"] == first.session_id]
    atuais = [row for row in rows if row["session_id"] == second.session_id]
    # O relógio da série é contínuo por construção, e é isso que o achado aponta.
    assert atuais[0]["elapsed_seconds"] > anteriores[-1]["elapsed_seconds"]
    # O instante absoluto é o que permite reconstruir o intervalo não monitorado.
    assert atuais[0]["sampled_at"] > anteriores[-1]["sampled_at"]
    assert all(row["sampled_at"] for row in rows)

    summary = summarize_samples(rows, workers=1)
    assert summary["session_id"] == second.session_id
    assert summary["samples_total"] == len(rows)
    assert summary["samples_session"] == len(atuais)
    assert summary["samples_total"] > summary["samples_session"]


def test_a_new_thread_with_accumulated_ticks_counts_as_active(tmp_path: Path) -> None:
    """F7-7: `tid` novo era comparado consigo mesmo e nunca contava como ativo."""

    monitor = ResourceMonitor(tmp_path / "resources.csv", workers=1)
    monitor._last_thread_ticks = {}

    row = {
        "optimizer_thread_ticks": {"10:10": 7, "10:11": 0},
        "optimizer_process_ticks": {"10": 7},
        "cpu_ticks": 0,
    }
    monitor._samples = []
    monitor._started = 0.0
    monitor._record(row)

    sample = monitor._samples[-1]
    assert sample["active_optimizer_threads"] == 1
    assert sample["max_active_threads_per_optimizer"] == 1
    assert sample["optimizer_thread_ticks_total"] == 7
    assert sample["optimizer_thread_count"] == 2


def _write_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerow(row)


def test_reading_refuses_an_empty_cell_in_a_required_column(tmp_path: Path) -> None:
    """A tolerância a célula vazia vale só para as colunas opcionais.

    Aplicada a todas as colunas, ela fazia `read_samples` deixar de recusar CSV
    corrompido: a célula virava `None` e o erro reaparecia tarde, como
    `TypeError` dentro de `summarize_samples` ou como coluna de tipo objeto no
    Parquet.
    """

    path = tmp_path / "resources.csv"
    row = dict(_sample())
    row["rss_bytes"] = ""
    _write_csv(path, list(_sample()), row)
    with pytest.raises(ConfigurationError, match="rss_bytes"):
        read_samples(path)


def test_reading_tolerates_the_new_columns_absent_from_an_inherited_row(
    tmp_path: Path,
) -> None:
    """Linha de sessão anterior, regravada com as colunas novas vazias."""

    path = tmp_path / "resources.csv"
    fieldnames = [
        *_sample(), "session_id", "sampled_at",
        "optimizer_thread_ticks_total", "optimizer_thread_count",
    ]
    _write_csv(path, fieldnames, dict(_sample()))
    rows = read_samples(path)
    assert rows[0]["optimizer_thread_ticks_total"] is None
    assert rows[0]["optimizer_thread_count"] is None
    assert rows[0]["rss_bytes"] == 1_000
    summary = summarize_samples(rows, workers=16)
    assert summary["session_id"] == "legado"
    assert summary["schema_version"] == 2


def test_root_pid_is_captured_by_the_process_that_instantiates(tmp_path: Path) -> None:
    """Achado F7-9: `root_pid` saía da importação do módulo, não da instanciação.

    O valor padrão de um campo de `dataclass` é avaliado uma única vez, quando a
    classe é criada, isto é na primeira importação do módulo. Sob `spawn` o
    defeito é **invisível**, porque o filho reexecuta o módulo do zero e a
    expressão é reavaliada; medido, `spawn` e `forkserver` devolvem o PID do
    próprio filho tanto antes quanto depois da correção. O eixo que discrimina é
    `fork`, em que o filho herda o objeto de classe já construído, com o valor do
    pai congelado dentro dele. Se o monitor fosse instanciado num worker da
    campanha, `root_pid` seria o do processo principal, `descendants` viria vazio
    e os critérios de thread e de otimizador ficariam verdadeiros de forma vazia,
    com `passed` verdadeiro sem ter observado nada.
    """

    leitura, escrita = os.pipe()
    with warnings.catch_warnings():
        # O aviso de `fork` em processo com threads é pertinente em geral. Aqui o
        # filho não toma trava alguma: ele lê o próprio PID, constrói o monitor,
        # que só cria um `Event` e listas vazias, escreve no cano e sai por
        # `os._exit`, sem `atexit` e sem descarga de buffers herdados.
        warnings.simplefilter("ignore", DeprecationWarning)
        filho = os.fork()
    if filho == 0:  # pragma: no cover - executa apenas no processo filho
        try:
            os.close(leitura)
            monitor = ResourceMonitor(tmp_path / "recursos.csv", workers=1)
            herdado = int("experiments.resource_monitor" in sys.modules)
            os.write(escrita, f"{os.getpid()} {monitor.root_pid} {herdado}".encode())
            os.close(escrita)
        finally:
            os._exit(0)

    os.close(escrita)
    with os.fdopen(leitura, "rb") as cano:
        bruto = cano.read()
    _, estado = os.waitpid(filho, 0)

    assert os.waitstatus_to_exitcode(estado) == 0
    filho_pid, root_pid, herdado = (int(campo) for campo in bruto.split())
    # As duas propriedades que tornam o caso discriminante, asseveradas aqui
    # dentro: o filho é outro processo, e o módulo já estava importado nele, isto
    # é ele não o reexecutou, logo a classe que ele usa é a que o pai construiu.
    # Sem a segunda, o caso passaria por vácuo sob qualquer método de partida que
    # reimporte o módulo.
    assert filho_pid != os.getpid()
    assert herdado == 1

    assert root_pid == filho_pid


def test_root_pid_is_declared_as_a_factory_and_not_as_a_frozen_default() -> None:
    """A forma do campo, que é o que o achado F7-9 pede corrigido."""

    field_by_name = {item.name: item for item in fields(ResourceMonitor)}
    root_pid = field_by_name["root_pid"]
    assert root_pid.default is MISSING
    assert root_pid.default_factory is os.getpid


def _arvore_sintetica(
    base: Path, *, root_pid: int, filhos: list[tuple[int, str, int, int]]
) -> Path:
    """Árvore de processos no formato que `_read_process` consome.

    O corte `stat[close + 2:]` remove `pid (comm) `, de modo que o estado do
    processo é o primeiro elemento restante e `fields[k]` é `campos[k - 1]`.
    """

    raiz = base / "proc"
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "meminfo").write_text(
        "MemTotal: 33554432 kB\nMemAvailable: 16777216 kB\n"
        "SwapTotal: 4194304 kB\nSwapFree: 4194304 kB\n",
        encoding="utf-8",
    )

    def escreve(pid: int, ppid: int, comando: str, utime: int, stime: int) -> None:
        diretorio = raiz / str(pid)
        (diretorio / "task" / str(pid)).mkdir(parents=True, exist_ok=True)
        campos = ["0"] * 22
        campos[0] = str(ppid)     # fields[1], o quarto campo do /proc
        campos[10] = str(utime)   # fields[11]
        campos[11] = str(stime)   # fields[12]
        linha = f"{pid} (python3) S " + " ".join(campos) + "\n"
        (diretorio / "stat").write_text(linha, encoding="utf-8")
        (diretorio / "task" / str(pid) / "stat").write_text(linha, encoding="utf-8")
        (diretorio / "status").write_text(
            "VmRSS:\t1024 kB\nThreads:\t4\n", encoding="utf-8"
        )
        (diretorio / "cmdline").write_bytes(comando.encode("utf-8"))

    escreve(root_pid, 1, "orquestrador", 0, 0)
    for pid, comando, utime, stime in filhos:
        escreve(pid, root_pid, comando, utime, stime)
    return raiz


def test_sample_tree_reports_cpu_ticks_per_optimizer_process(tmp_path: Path) -> None:
    raiz = _arvore_sintetica(
        tmp_path,
        root_pid=100,
        # `utime` e `stime` distintos e não nulos: a soma fica presa, e trocar um
        # índice pelo outro deixa de passar por acaso.
        filhos=[
            (101, "worker", 700, 23),
            (102, "multiprocessing.resource_tracker", 5, 1),
        ],
    )
    amostra = sample_process_tree(100, proc_root=raiz)
    assert amostra["optimizer_process_ticks"] == {"101": 723}
    assert amostra["optimizer_process_count"] == 1
    assert amostra["descendant_count"] == 2


def _fotografia(*, ticks_por_pid: dict[str, int]) -> dict:
    """Fotografia no formato que `_record` consome, sem tocar em `/proc`."""

    return {
        "rss_bytes": 1_000,
        "descendant_rss_bytes": 500,
        "cpu_ticks": sum(ticks_por_pid.values()),
        "process_count": len(ticks_por_pid) + 1,
        "descendant_count": len(ticks_por_pid),
        "optimizer_process_count": len(ticks_por_pid),
        "max_optimizer_threads": 4,
        "optimizer_thread_ticks": {
            f"{pid}:{pid}": valor for pid, valor in ticks_por_pid.items()
        },
        "optimizer_process_ticks": dict(ticks_por_pid),
        "memory_total_bytes": 32 * 1024 ** 3,
        "memory_available_bytes": 16 * 1024 ** 3,
        "swap_total_bytes": 4 * 1024 ** 3,
        "swap_free_bytes": 4 * 1024 ** 3,
    }


def test_record_computes_cpu_ratio_between_consecutive_samples() -> None:
    monitor = ResourceMonitor(Path("/dev/null"), workers=16)
    monitor._started = 0.0
    relogio = os.sysconf("SC_CLK_TCK")
    monitor._record(_fotografia(ticks_por_pid={"101": 0}))
    # Recuar o instante da última amostra é o que fixa o intervalo em um segundo;
    # sem isso o divisor seria o tempo real entre as duas chamadas.
    monitor._last_sample_at -= 1.0
    monitor._record(_fotografia(ticks_por_pid={"101": relogio}))
    linha = monitor._samples[-1]
    assert linha["max_optimizer_cpu_ratio"] == pytest.approx(1.0, abs=0.05)
    assert linha["optimizer_pids"] == "101"


def test_record_excludes_process_seen_for_the_first_time() -> None:
    monitor = ResourceMonitor(Path("/dev/null"), workers=16)
    monitor._started = 0.0
    relogio = os.sysconf("SC_CLK_TCK")
    monitor._record(_fotografia(ticks_por_pid={"101": 0}))
    monitor._last_sample_at -= 1.0
    # 202 nasce agora, com cinquenta segundos de histórico. Contá-lo compararia
    # contra zero, que é exatamente o defeito que este bloco corrige.
    monitor._record(_fotografia(ticks_por_pid={"101": relogio, "202": 50 * relogio}))
    linha = monitor._samples[-1]
    assert linha["max_optimizer_cpu_ratio"] == pytest.approx(1.0, abs=0.05)
    assert linha["optimizer_pids"] == "101 202"


def test_record_ignores_a_process_that_disappeared() -> None:
    monitor = ResourceMonitor(Path("/dev/null"), workers=16)
    monitor._started = 0.0
    relogio = os.sysconf("SC_CLK_TCK")
    monitor._record(_fotografia(ticks_por_pid={"101": 0, "202": 0}))
    monitor._last_sample_at -= 1.0
    monitor._record(_fotografia(ticks_por_pid={"101": relogio}))
    linha = monitor._samples[-1]
    assert linha["max_optimizer_cpu_ratio"] == pytest.approx(1.0, abs=0.05)
    assert linha["optimizer_pids"] == "101"


def test_record_leaves_ratio_undefined_on_first_sample() -> None:
    monitor = ResourceMonitor(Path("/dev/null"), workers=16)
    monitor._started = 0.0
    monitor._record(_fotografia(ticks_por_pid={"101": 0}))
    assert monitor._samples[-1]["max_optimizer_cpu_ratio"] is None
    assert monitor._samples[-1]["optimizer_pids"] == "101"


def test_record_discards_a_non_positive_interval() -> None:
    monitor = ResourceMonitor(Path("/dev/null"), workers=16)
    monitor._started = 0.0
    relogio = os.sysconf("SC_CLK_TCK")
    monitor._record(_fotografia(ticks_por_pid={"101": 0}))
    # Relógio da amostra anterior no futuro: o intervalo não é positivo e não há
    # divisor legítimo. Grampear em 1e-9 produziria razão de dez milhões.
    monitor._last_sample_at = time.monotonic() + 60.0
    monitor._record(_fotografia(ticks_por_pid={"101": relogio}))
    assert monitor._samples[-1]["max_optimizer_cpu_ratio"] is None
