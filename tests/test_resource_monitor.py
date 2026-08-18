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
