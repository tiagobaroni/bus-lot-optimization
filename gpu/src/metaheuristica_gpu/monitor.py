"""Telemetria, exclusividade e proteção térmica da B11A."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable


class GpuSafetyError(RuntimeError):
    pass


class ThermalInterruption(GpuSafetyError):
    pass


@dataclass(frozen=True, slots=True)
class GpuSample:
    monotonic_seconds: float
    temperature_c: int
    gpu_utilization_percent: float
    memory_utilization_percent: float
    memory_used_mib: int
    memory_total_mib: int
    power_w: float
    sm_clock_mhz: int
    memory_clock_mhz: int
    software_thermal_slowdown: bool
    hardware_thermal_slowdown: bool
    external_processes: int


def _active(value: str) -> bool:
    return value.strip().lower() not in {"not active", "no", "0", "n/a"}


def query_sample() -> GpuSample:
    fields = (
        "temperature.gpu", "utilization.gpu", "utilization.memory", "memory.used",
        "memory.total", "power.draw", "clocks.sm", "clocks.mem",
        "clocks_event_reasons.sw_thermal_slowdown",
        "clocks_event_reasons.hw_thermal_slowdown",
    )
    command = ["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"]
    try:
        output = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5).stdout.strip()
        values = [item.strip() for item in output.split(",")]
        process_output = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise GpuSafetyError("telemetria NVIDIA indisponível") from error
    if len(values) != len(fields):
        raise GpuSafetyError("amostra NVIDIA incompleta")
    external = 0
    for line in process_output.splitlines():
        if not line.strip():
            continue
        try:
            pid = int(line.split(",", 1)[0].strip())
        except ValueError:
            external += 1
        else:
            external += int(pid != os.getpid())
    return GpuSample(
        time.monotonic(), int(values[0]), float(values[1]), float(values[2]),
        int(values[3]), int(values[4]), float(values[5]), int(values[6]), int(values[7]),
        _active(values[8]), _active(values[9]), external,
    )


def preflight_idle(
    *,
    duration_seconds: int = 60,
    provider: Callable[[], GpuSample] = query_sample,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[GpuSample, ...]:
    samples = []
    for index in range(duration_seconds):
        sample = provider(); samples.append(sample)
        if sample.temperature_c > 50:
            raise GpuSafetyError("temperatura inicial acima de 50 graus Celsius")
        if sample.external_processes:
            raise GpuSafetyError("outro processo computacional usa a GPU")
        if index + 1 < duration_seconds:
            sleeper(1.0)
    average = sum(item.gpu_utilization_percent for item in samples) / len(samples)
    if average > 5.0:
        raise GpuSafetyError("utilização média inicial acima de 5%")
    return tuple(samples)


class GpuSafetyMonitor:
    def __init__(
        self, path: Path, *, provider: Callable[[], GpuSample] = query_sample,
        interval_seconds: float = 1.0,
    ) -> None:
        self.path = path; self.provider = provider; self.interval_seconds = interval_seconds
        self.samples: list[GpuSample] = []; self._stop = threading.Event()
        self._thread: threading.Thread | None = None; self._error: GpuSafetyError | None = None
        self._hot = 0

    def _check(self, sample: GpuSample) -> None:
        self._hot = self._hot + 1 if sample.temperature_c >= 80 else 0
        if self._hot >= 10:
            raise ThermalInterruption("GPU permaneceu em pelo menos 80 graus por 10 segundos")
        if sample.software_thermal_slowdown or sample.hardware_thermal_slowdown:
            raise ThermalInterruption("GPU indicou throttling térmico")
        if sample.external_processes:
            raise ThermalInterruption("outro processo computacional apareceu na GPU")

    def _sample(self) -> None:
        sample = self.provider(); self.samples.append(sample); self._check(sample)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self._sample()
            except GpuSafetyError as error:
                self._error = error; self._stop.set()
            except Exception as error:
                self._error = ThermalInterruption("monitor perdeu telemetria")
                self._stop.set()

    def guard(self) -> None:
        if self._error is not None:
            raise self._error

    def __enter__(self) -> "GpuSafetyMonitor":
        self._sample()
        self._thread = threading.Thread(target=self._run, name="gpu-safety", daemon=True)
        self._thread.start(); return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, 2 * self.interval_seconds))
        try:
            self._sample()
        except GpuSafetyError as error:
            self._error = self._error or error
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(asdict(self.samples[0])))
            writer.writeheader(); writer.writerows(asdict(item) for item in self.samples)
        os.replace(temporary, self.path)
        if exc_type is None and self._error is not None:
            raise self._error


def cooldown(
    *, provider: Callable[[], GpuSample] = query_sample,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[GpuSample, ...]:
    samples = []
    while True:
        sample = provider(); samples.append(sample)
        if sample.temperature_c <= 55:
            return tuple(samples)
        sleeper(1.0)
