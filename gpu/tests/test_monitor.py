from dataclasses import replace

import pytest

from metaheuristica_gpu.monitor import GpuSample, GpuSafetyError, preflight_idle


BASE = GpuSample(0.0, 40, 0.0, 0.0, 100, 12288, 20.0, 200, 400, False, False, 0)


def test_preflight_accepts_idle_and_rejects_heat_or_competitor() -> None:
    assert len(preflight_idle(duration_seconds=3, provider=lambda: BASE, sleeper=lambda _: None)) == 3
    with pytest.raises(GpuSafetyError, match="temperatura"):
        preflight_idle(duration_seconds=1, provider=lambda: replace(BASE, temperature_c=51))
    with pytest.raises(GpuSafetyError, match="processo"):
        preflight_idle(duration_seconds=1, provider=lambda: replace(BASE, external_processes=1))
