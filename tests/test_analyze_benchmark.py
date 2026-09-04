import pandas as pd

from experiments.analyze_benchmark import write_summary_tables


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
