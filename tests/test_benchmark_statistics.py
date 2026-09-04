import numpy as np
import pandas as pd
import pytest

from experiments.benchmark_statistics import (
    descriptive_summary, friedman_and_pairs, rank_biserial, _holm_correction,
)


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


def _paired_runs(*, distinct: bool) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for seed in range(10, 40):
        base = rng.uniform(0.4, 0.6)
        aco = base + (0.15 if distinct else rng.normal(0, 0.001))
        pso = base
        tabu = base + (rng.normal(0, 0.001) if distinct else rng.normal(0, 0.001))
        for algorithm, cost in (("aco", aco), ("pso", pso), ("tabu", tabu)):
            rows.append({
                "algorithm": algorithm, "instance": "artesp_rmsp_20", "k": 3,
                "seed": seed, "total_cost": cost,
            })
    return pd.DataFrame(rows)


def test_friedman_rejects_h0_when_groups_differ():
    result = friedman_and_pairs(_paired_runs(distinct=True))
    row = result.iloc[0]
    # `row["rejects_h0"]` sai como numpy.bool_ depois de passar por
    # DataFrame.iloc numa linha de dtypes mistos; numpy.bool_(True) is True
    # é False em Python, então a comparação tem de ser por valor, não `is`.
    assert bool(row["rejects_h0"]) == True
    assert row["friedman_p_value"] < 0.05
    assert "wilcoxon_pso_vs_aco_p_holm" in result.columns
    assert row["wilcoxon_pso_vs_aco_p_holm"] < 0.05


def test_friedman_does_not_reject_h0_when_groups_are_equal():
    result = friedman_and_pairs(_paired_runs(distinct=False))
    row = result.iloc[0]
    assert bool(row["rejects_h0"]) == False


def test_rank_biserial_of_all_positive_differences_is_one():
    assert rank_biserial(np.array([1.0, 2.0, 3.0])) == 1.0


def test_rank_biserial_matches_signed_rank_definition():
    # diferenças [1, -1, 5]: valores absolutos [1, 1, 5], os dois empates em 1
    # dividem o posto 1-2 (posto médio 1.5 cada), o 5 fica com posto 3.
    # soma dos postos positivos (para +1 e +5) = 1.5 + 3 = 4.5;
    # soma dos postos negativos (para -1) = 1.5.
    # r = (4.5 - 1.5) / (4.5 + 1.5) = 0.5 — NÃO é 1/3, que seria a simples
    # contagem de sinais (2 positivos - 1 negativo, sobre 3), fórmula errada
    # que não é a rank-biserial correlation pareada de fato.
    assert rank_biserial(np.array([1.0, -1.0, 5.0])) == pytest.approx(0.5)


def test_rank_biserial_of_no_signal_is_zero():
    assert rank_biserial(np.array([1.0, -1.0, 2.0, -2.0])) == 0.0


def test_holm_correction_matches_known_case():
    # três p-valores 0.01, 0.02, 0.03: Holm multiplica por (m - rank)
    # 0.01*3=0.03; 0.02*2=0.04; 0.03*1=0.03 -> ajustado por acumulado: [0.03, 0.04, 0.04]
    adjusted = _holm_correction([0.01, 0.02, 0.03])
    assert adjusted == pytest.approx([0.03, 0.04, 0.04])
