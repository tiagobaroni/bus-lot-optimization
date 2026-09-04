import pandas as pd
import pytest

from experiments.analyze_benchmark import write_summary_tables, write_convergence_figures, write_scalability_figures


def _tiny_runs() -> pd.DataFrame:
    # Custo com pequena variação por seed e por algoritmo, de propósito: com
    # `total_cost` idêntico em todo bloco, `friedmanchisquare` devolve NaN (a
    # estatística de postos empatados degenera) e o teste passaria sem testar
    # nada de verdade sobre `friedman_and_pairs`.
    rng_offsets = {"aco": 0.0, "pso": 0.01, "tabu": 0.02}
    rows = []
    for algorithm, offset in rng_offsets.items():
        for seed in range(10, 40):
            rows.append({
                "algorithm": algorithm, "instance": "artesp_rmsp_20", "k": 3,
                "seed": seed, "total_cost": 0.3 + offset + 0.001 * (seed % 5),
                "runtime_seconds": 1.0,
            })
    return pd.DataFrame(rows)


def test_write_summary_tables_creates_both_parquets(tmp_path):
    paths = write_summary_tables(_tiny_runs(), tmp_path)
    assert paths["summary"].exists()
    assert paths["statistical_tests"].exists()
    summary = pd.read_parquet(paths["summary"])
    assert len(summary) == 3  # um por algoritmo
    tests_table = pd.read_parquet(paths["statistical_tests"])
    assert len(tests_table) == 1  # uma combinação instância×K


def _runs_two_k() -> pd.DataFrame:
    rows = []
    for k in (3, 8):
        for algorithm in ("aco", "pso", "tabu"):
            rows.append({
                "algorithm": algorithm, "instance": "artesp_rmsp_20", "k": k,
                "total_cost": 0.3, "cv_demand": 0.1, "cv_production": 0.1,
                "c_territorial": 0.1, "c_affinity": 0.1, "runtime_seconds": 1.0,
            })
    return pd.DataFrame(rows)


def test_by_k_table_has_one_row_per_algorithm_instance_k():
    from experiments.analyze_benchmark import by_k_table
    table = by_k_table(_runs_two_k())
    assert len(table) == 6  # 3 algoritmos x 2 valores de K


def test_vs_greedy_table_computes_improvement():
    from experiments.analyze_benchmark import vs_greedy_table
    runs = pd.DataFrame([{
        "algorithm": "aco", "instance": "artesp_rmsp_20", "k": 3,
        "total_cost": 0.3, "runtime_seconds": 2.0,
    }])
    greedy_runs = pd.DataFrame([{
        "instance": "artesp_rmsp_20", "k": 3, "total_cost": 0.5,
        "runtime_seconds": 0.01,
    }])
    table = vs_greedy_table(runs, greedy_runs)
    row = table.iloc[0]
    assert row["cost_difference"] == pytest.approx(0.3 - 0.5)
    assert row["improvement_percent"] == pytest.approx((0.5 - 0.3) / 0.5 * 100)


def _tiny_checkpoints() -> pd.DataFrame:
    rows = []
    for algorithm in ("aco", "pso", "tabu"):
        for seed in (10, 11):
            for index in range(1, 6):
                rows.append({
                    "algorithm": algorithm, "instance": "artesp_rmsp_20", "k": 5,
                    "seed": seed, "index": index, "evaluations": index * 20,
                    "total_cost": 1.0 / index,
                })
    return pd.DataFrame(rows)


def test_write_convergence_figures_creates_png_and_pdf_per_instance(tmp_path):
    outputs = write_convergence_figures(_tiny_checkpoints(), tmp_path)
    assert set(outputs) == {"artesp_rmsp_20"}
    for path in outputs["artesp_rmsp_20"]:
        assert path.exists()
    suffixes = {path.suffix for path in outputs["artesp_rmsp_20"]}
    assert suffixes == {".png", ".pdf"}


def _runs_three_sizes() -> pd.DataFrame:
    rows = []
    for size in (20, 60, 150):
        for algorithm in ("aco", "pso", "tabu"):
            rows.append({
                "algorithm": algorithm, "instance": f"artesp_rmsp_{size}", "k": 5,
                "total_cost": 0.3, "runtime_seconds": float(size),
            })
    return pd.DataFrame(rows)


def test_write_scalability_figures_creates_time_and_quality(tmp_path):
    outputs = write_scalability_figures(_runs_three_sizes(), tmp_path)
    assert set(outputs) == {"time", "quality"}
    for paths in outputs.values():
        assert {p.suffix for p in paths} == {".png", ".pdf"}
