import json

import numpy as np
import pandas as pd
import pytest

from metaheuristica.errors import ConfigurationError
from experiments.export_maps import select_best_runs

UNIT_COUNTS = {"artesp_rmsp_20": 6, "artesp_rmsp_60": 6, "artesp_rmsp_150": 6}


def _solution(k: int, n_units: int = 6) -> list[int]:
    # Solucao valida: exatamente k lotes nao vazios sobre n_units unidades.
    return [index % k for index in range(n_units)]


def _runs_frame(*, instances=("artesp_rmsp_20",), algorithms=("tabu", "aco", "pso"),
                k_values=(3,), seeds=range(10, 40), official=True) -> pd.DataFrame:
    # Custo em V, com o minimo na seed 25: nem a primeira nem a ultima linha do
    # grupo e' a vencedora, entao um `first()` ou um `last()` que ignorasse a
    # ordenacao por custo seria pego por este teste sozinho.
    rows = []
    for instance in instances:
        for algorithm in algorithms:
            for k in k_values:
                for seed in seeds:
                    rows.append({
                        "instance": instance, "algorithm": algorithm, "k": k,
                        "seed": seed, "total_cost": 0.5 + abs(seed - 25) * 0.01,
                        "scenario_id": f"{algorithm}_{instance}_k{k}_s{seed}",
                        "solution_json": json.dumps(_solution(k)),
                        "official": official,
                    })
    return pd.DataFrame(rows)


def _select(runs, **overrides):
    arguments = {"unit_counts": UNIT_COUNTS, "expected_runs": 90,
                 "expected_seeds": 30, "combinations": 3}
    arguments.update(overrides)
    return select_best_runs(runs, **arguments)


def test_select_best_runs_picks_lowest_cost_per_combination():
    selected = _select(_runs_frame())
    assert len(selected) == 3
    assert set(selected["seed"]) == {25}


def test_select_best_runs_breaks_cost_ties_by_lowest_seed():
    # Seeds em ordem decrescente para forcar a ordenacao a realmente
    # selecionar a seed minima, nao apenas preservar a ordem de insercao.
    runs = _runs_frame(seeds=range(39, 9, -1))
    runs["total_cost"] = 0.5
    assert set(_select(runs)["seed"]) == {10}


def test_select_best_runs_ignores_unofficial_rows():
    extra = _runs_frame(seeds=[99], official=False)
    extra["total_cost"] = -1.0
    runs = pd.concat([_runs_frame(), extra], ignore_index=True)
    assert 99 not in set(_select(runs)["seed"])


def test_select_best_runs_keeps_the_whole_winning_row():
    # `groupby(...).first()` do pandas toma o primeiro valor NAO-NULO de cada
    # coluna independentemente, e pode compor uma linha quimera com campos de
    # execucoes diferentes. Aqui a vencedora tem `scenario_id` nulo: se a
    # implementacao usar `first()`, o `scenario_id` vem da linha perdedora.
    runs = _runs_frame()
    winner = (runs["seed"] == 25) & (runs["algorithm"] == "tabu")
    runs.loc[winner, "scenario_id"] = None
    selected = _select(runs).set_index("algorithm")
    assert pd.isna(selected.loc["tabu", "scenario_id"])
