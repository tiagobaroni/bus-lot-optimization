import pandas as pd

from experiments.benchmark_statistics import descriptive_summary


def _tiny_runs() -> pd.DataFrame:
    rows = []
    for algorithm, costs in (("aco", [0.1, 0.3]), ("pso", [0.2, 0.2])):
        for seed, cost in zip((10, 11), costs):
            rows.append({
                "algorithm": algorithm, "instance": "artesp_rmsp_20", "k": 3,
                "seed": seed, "total_cost": cost, "runtime_seconds": 1.0,
            })
    return pd.DataFrame(rows)


def test_descriptive_summary_computes_mean_and_std():
    summary = descriptive_summary(_tiny_runs())
    aco = summary[summary["algorithm"] == "aco"].iloc[0]
    assert aco["cost_mean"] == 0.2
    assert aco["n_seeds"] == 2
    assert aco["cost_min"] == 0.1
    assert aco["cost_max"] == 0.3
