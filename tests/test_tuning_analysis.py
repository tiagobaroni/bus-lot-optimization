from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from experiments.config import ALGORITHM_FIELDS, load_campaign
from experiments.scenarios import canonical_json, expand_scenarios
from experiments.tuning_analysis import (
    _choose_best,
    parameter_effects,
    summarize_tuning,
)
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]
CONFIG = load_campaign(ROOT / "experiments/configs/tuning.toml")


def synthetic_runs() -> pd.DataFrame:
    rows = []
    for scenario in expand_scenarios(CONFIG):
        payload = scenario.payload
        parameters = payload["parameters"]
        parameter_signal = sum(float(value) for value in parameters.values()) * 1e-3
        algorithm_signal = {"aco": 0.1, "pso": 0.2, "tabu": 0.3}[payload["algorithm"]]
        cost = algorithm_signal + parameter_signal + payload["seed"] * 1e-5
        rows.append({
            "scenario_id": scenario.scenario_id,
            "algorithm": payload["algorithm"],
            "instance": payload["instance"]["name"],
            "k": payload["k"],
            "seed": payload["seed"],
            "budget": payload["budget"],
            "cache_enabled": payload["cache_enabled"],
            "parameters_json": canonical_json(parameters).decode(),
            "official": True,
            "total_cost": cost,
            "c_demand": cost,
            "c_production": cost + 0.01,
            "c_territorial": cost + 0.02,
            "c_affinity": cost + 0.03,
            "cv_demand": cost + 0.04,
            "cv_production": cost + 0.05,
            "runtime_seconds": 10.0 + parameter_signal,
        })
    return pd.DataFrame(rows)


def test_summary_has_manual_statistics_and_one_winner_per_algorithm() -> None:
    runs = synthetic_runs()
    summary = summarize_tuning(runs.sample(frac=1.0, random_state=7), CONFIG)
    assert len(summary) == 44
    assert summary.groupby("algorithm")["selected"].sum().to_dict() == {
        "aco": 1, "pso": 1, "tabu": 1,
    }
    first = summary.iloc[0]
    group = runs[
        (runs["algorithm"] == first["algorithm"])
        & (runs["parameters_json"] == first["parameters_json"])
    ]
    assert first["mean_cost"] == pytest.approx(group["total_cost"].mean())
    assert first["std_cost"] == pytest.approx(group["total_cost"].std(ddof=1))
    assert first["median_cost"] == pytest.approx(group["total_cost"].median())
    assert first["mean_c_affinity"] == pytest.approx(group["c_affinity"].mean())


def test_ranking_ties_follow_dispersion_time_and_parameters() -> None:
    frame = pd.DataFrame([
        {"algorithm": "pso", "mean_cost": 1.0, "std_cost": 0.2,
         "mean_runtime_seconds": 5.0, "param_n_particles": 20,
         "param_inertia": 0.4, "param_cognitive": 1.5, "param_social": 1.5},
        {"algorithm": "pso", "mean_cost": 1.0 + 5e-13, "std_cost": 0.1,
         "mean_runtime_seconds": 5.0, "param_n_particles": 40,
         "param_inertia": 0.4, "param_cognitive": 1.5, "param_social": 1.5},
    ])
    assert _choose_best(frame, [0, 1]) == 1
    frame.loc[0, "std_cost"] = 0.1
    frame.loc[1, "mean_runtime_seconds"] = 6.0
    assert _choose_best(frame, [0, 1]) == 0
    frame.loc[1, "mean_runtime_seconds"] = 5.0
    assert _choose_best(frame, [0, 1]) == 0


def test_parameter_effects_cover_every_level_and_are_descriptive() -> None:
    effects = parameter_effects(summarize_tuning(synthetic_runs(), CONFIG))
    assert len(effects) == 23
    assert set(effects["interpretation"]) == {"descriptive_noncausal"}
    assert effects["n_runs"].sum() == sum(
        len(ALGORITHM_FIELDS[algorithm]) * count
        for algorithm, count in {"aco": 160, "pso": 160, "tabu": 120}.items()
    )


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda frame: frame.drop(frame.index[0]), "440"),
        (lambda frame: frame.assign(official=False), "não oficial"),
        (lambda frame: frame.assign(total_cost=np.inf), "não finito"),
    ],
)
def test_summary_rejects_incomplete_unofficial_or_nonfinite_data(mutation, match) -> None:
    with pytest.raises(ConfigurationError, match=match):
        summarize_tuning(mutation(synthetic_runs()), CONFIG)
