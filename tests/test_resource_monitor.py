from __future__ import annotations

from pathlib import Path

from experiments.resource_monitor import ResourceMonitor, read_samples, summarize_samples


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

    row = {"optimizer_thread_ticks": {"10:10": 7, "10:11": 0}, "cpu_ticks": 0}
    monitor._samples = []
    monitor._started = 0.0
    monitor._record(row)

    sample = monitor._samples[-1]
    assert sample["active_optimizer_threads"] == 1
    assert sample["max_active_threads_per_optimizer"] == 1
    assert sample["optimizer_thread_ticks_total"] == 7
    assert sample["optimizer_thread_count"] == 2
