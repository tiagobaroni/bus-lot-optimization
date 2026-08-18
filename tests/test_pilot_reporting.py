from __future__ import annotations

from pathlib import Path

import pandas as pd

from experiments.pilot_reporting import (
    _convergence_figure, _resources_figure, _save_figure, _time_figure,
)


def _runs() -> pd.DataFrame:
    rows = []
    for size in (20, 60, 150):
        for k in (3, 8):
            for index, algorithm in enumerate(("tabu", "aco", "pso"), start=1):
                rows.append({
                    "algorithm": algorithm, "instance": f"artesp_rmsp_{size}",
                    "k": k, "runtime_seconds": float(index),
                })
    return pd.DataFrame(rows)


def test_preliminary_figures_are_exportable(tmp_path: Path) -> None:
    runs = _runs()
    checkpoints = pd.DataFrame([
        {
            "algorithm": row.algorithm, "instance": row.instance, "k": row.k,
            "evaluations": evaluation, "total_cost": 1 / evaluation,
        }
        for row in runs.itertuples()
        for evaluation in (1, 2, 3)
    ])
    samples = pd.DataFrame({
        "elapsed_seconds": [0.0, 1.0], "cpu_percent": [0.0, 100.0],
        "rss_bytes": [1, 2], "memory_available_bytes": [10, 9],
    })
    figures = (
        _convergence_figure(checkpoints), _time_figure(runs), _resources_figure(samples)
    )
    for index, figure in enumerate(figures):
        outputs = _save_figure(figure, tmp_path / f"figure_{index}")
        assert all(path.stat().st_size > 0 for path in outputs)
