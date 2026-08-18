"""Monitoramento Linux da árvore de processos de uma campanha."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterable

from metaheuristica.errors import ConfigurationError


GIB = 1024 ** 3


def _read_meminfo(proc_root: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in (proc_root / "meminfo").read_text(encoding="utf-8").splitlines():
        name, raw = line.split(":", 1)
        amount = int(raw.strip().split()[0])
        values[name] = amount * 1024
    return values


def _read_process(proc_root: Path, pid: int) -> dict[str, int] | None:
    try:
        stat = (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
        close = stat.rfind(")")
        fields = stat[close + 2:].split()
        status = (proc_root / str(pid) / "status").read_text(
            encoding="utf-8"
        ).splitlines()
        command = (proc_root / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace"
        )
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
        return None
    status_values = {
        line.split(":", 1)[0]: line.split(":", 1)[1].strip()
        for line in status if ":" in line
    }
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "cpu_ticks": int(fields[11]) + int(fields[12]),
        "rss_bytes": int(status_values.get("VmRSS", "0 kB").split()[0]) * 1024,
        "threads": int(status_values.get("Threads", "1")),
        "infrastructure": int("multiprocessing.resource_tracker" in command),
    }


def _thread_ticks(proc_root: Path, pid: int) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        tasks = tuple((proc_root / str(pid) / "task").iterdir())
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return values
    for task in tasks:
        if not task.name.isdigit():
            continue
        try:
            stat = (task / "stat").read_text(encoding="utf-8")
            close = stat.rfind(")")
            fields = stat[close + 2:].split()
            values[f"{pid}:{task.name}"] = int(fields[11]) + int(fields[12])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return values


def sample_process_tree(
    root_pid: int,
    *,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Obtém uma fotografia consistente o bastante da árvore de processos."""

    processes: dict[int, dict[str, int]] = {}
    try:
        entries = tuple(proc_root.iterdir())
    except OSError as error:
        raise ConfigurationError(f"não foi possível ler {proc_root}") from error
    for entry in entries:
        if entry.name.isdigit():
            process = _read_process(proc_root, int(entry.name))
            if process is not None:
                processes[process["pid"]] = process
    selected = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, process in processes.items():
            if process["ppid"] in selected and pid not in selected:
                selected.add(pid)
                changed = True
    tree = [processes[pid] for pid in selected if pid in processes]
    descendants = [process for process in tree if process["pid"] != root_pid]
    optimizer_processes = [
        process for process in descendants if not process["infrastructure"]
    ]
    memory = _read_meminfo(proc_root)
    return {
        "rss_bytes": sum(process["rss_bytes"] for process in tree),
        "descendant_rss_bytes": sum(
            process["rss_bytes"] for process in descendants
        ),
        "cpu_ticks": sum(process["cpu_ticks"] for process in tree),
        "process_count": len(tree),
        "descendant_count": len(descendants),
        "optimizer_process_count": len(optimizer_processes),
        "max_optimizer_threads": max(
            (process["threads"] for process in optimizer_processes), default=0
        ),
        "optimizer_thread_ticks": {
            key: value
            for process in optimizer_processes
            for key, value in _thread_ticks(proc_root, process["pid"]).items()
        },
        "memory_total_bytes": memory["MemTotal"],
        "memory_available_bytes": memory["MemAvailable"],
        "swap_total_bytes": memory.get("SwapTotal", 0),
        "swap_free_bytes": memory.get("SwapFree", 0),
    }


def summarize_samples(samples: Iterable[dict[str, Any]], *, workers: int) -> dict[str, Any]:
    rows = list(samples)
    if not rows:
        raise ConfigurationError("monitor de recursos não produziu amostras")
    memory_total = int(rows[0]["memory_total_bytes"])
    minimum_required = max(int(memory_total * 0.10), 2 * GIB)
    minimum_available = min(int(row["memory_available_bytes"]) for row in rows)
    swap_delta = max(
        0, int(rows[0]["swap_free_bytes"]) - int(rows[-1]["swap_free_bytes"])
    )
    max_threads = max(int(row["max_optimizer_threads"]) for row in rows)
    max_active_threads = max(
        int(row["max_active_threads_per_optimizer"]) for row in rows
    )
    peak_cpu = max(float(row["cpu_percent"]) for row in rows)
    remaining_optimizers = int(rows[-1]["optimizer_process_count"])
    checks = {
        "memory_margin": minimum_available >= minimum_required,
        "swap_unchanged": swap_delta == 0,
        "one_active_thread_per_optimizer": max_active_threads <= 1,
        "cpu_within_workers": peak_cpu <= workers * 100 * 1.10,
        "no_persistent_optimizers": remaining_optimizers == 0,
    }
    return {
        "schema_version": 1,
        "workers": workers,
        "samples": len(rows),
        "peak_rss_bytes": max(int(row["rss_bytes"]) for row in rows),
        "peak_descendant_rss_bytes": max(
            int(row["descendant_rss_bytes"]) for row in rows
        ),
        "minimum_memory_available_bytes": minimum_available,
        "minimum_memory_required_bytes": minimum_required,
        "swap_consumed_bytes": swap_delta,
        "peak_cpu_percent": peak_cpu,
        "max_process_count": max(int(row["process_count"]) for row in rows),
        "max_optimizer_threads": max_threads,
        "max_active_optimizer_threads": max_active_threads,
        "remaining_optimizers": remaining_optimizers,
        "checks": checks,
        "passed": all(checks.values()),
    }


@dataclass
class ResourceMonitor:
    path: Path
    workers: int
    interval_seconds: float = 1.0
    root_pid: int = os.getpid()

    def __post_init__(self) -> None:
        if not Path("/proc/self").exists():
            raise ConfigurationError("monitor de recursos exige Linux com /proc")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._samples: list[dict[str, Any]] = []
        self._started = 0.0
        self._last_ticks: int | None = None
        self._last_sample_at: float | None = None
        self._last_thread_ticks: dict[str, int] = {}

    def _sample(self) -> None:
        now = time.monotonic()
        row = sample_process_tree(self.root_pid)
        ticks = int(row.pop("cpu_ticks"))
        thread_ticks = row.pop("optimizer_thread_ticks")
        cpu_percent = 0.0
        if self._last_ticks is not None and self._last_sample_at is not None:
            elapsed = max(now - self._last_sample_at, 1e-9)
            cpu_percent = (
                (ticks - self._last_ticks) / os.sysconf("SC_CLK_TCK") / elapsed * 100
            )
        self._last_ticks = ticks
        self._last_sample_at = now
        row["elapsed_seconds"] = now - self._started
        row["cpu_percent"] = max(cpu_percent, 0.0)
        active_by_pid: dict[str, int] = {}
        for identifier, value in thread_ticks.items():
            if value > self._last_thread_ticks.get(identifier, value):
                pid = identifier.split(":", 1)[0]
                active_by_pid[pid] = active_by_pid.get(pid, 0) + 1
        row["active_optimizer_threads"] = sum(active_by_pid.values())
        row["max_active_threads_per_optimizer"] = max(
            active_by_pid.values(), default=0
        )
        self._last_thread_ticks = thread_ticks
        self._samples.append(row)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self._sample()
            except (OSError, ConfigurationError):
                continue

    def __enter__(self) -> ResourceMonitor:
        offset = 0.0
        if self.path.exists():
            self._samples = read_samples(self.path)
            if self._samples:
                offset = float(self._samples[-1]["elapsed_seconds"]) + self.interval_seconds
        self._started = time.monotonic() - offset
        self._last_ticks = None
        self._last_sample_at = None
        self._last_thread_ticks = {}
        self._sample()
        self._thread = threading.Thread(
            target=self._run, name="resource-monitor", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.interval_seconds * 2, 1.0))
        self._sample()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        fieldnames = list(self._samples[0])
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._samples)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


def read_samples(path: Path) -> list[dict[str, Any]]:
    integer_fields = {
        "rss_bytes", "descendant_rss_bytes", "process_count", "descendant_count",
        "optimizer_process_count", "max_optimizer_threads",
        "active_optimizer_threads", "max_active_threads_per_optimizer",
        "memory_total_bytes",
        "memory_available_bytes",
        "swap_total_bytes", "swap_free_bytes",
    }
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for raw in csv.DictReader(stream):
            rows.append({
                key: int(value) if key in integer_fields else float(value)
                for key, value in raw.items()
            })
    return rows
