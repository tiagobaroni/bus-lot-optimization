import json
from itertools import permutations

import numpy as np
import pandas as pd
import pytest

from metaheuristica.errors import ConfigurationError
from experiments.export_maps import align_selected, align_to_reference, select_best_runs

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


def test_select_best_runs_rejects_wrong_total():
    with pytest.raises(ConfigurationError, match="execuções"):
        _select(_runs_frame(seeds=range(10, 39)))


def test_select_best_runs_rejects_missing_seeds():
    runs = _runs_frame().drop(index=0)
    with pytest.raises(ConfigurationError, match="seeds esperadas"):
        _select(runs, expected_runs=89)


def test_select_best_runs_rejects_missing_combination():
    with pytest.raises(ConfigurationError, match="combinações"):
        _select(_runs_frame(algorithms=("tabu", "aco")), expected_runs=60)


def test_select_best_runs_rejects_solution_with_wrong_length():
    runs = _runs_frame()
    winner = (runs["seed"] == 25) & (runs["algorithm"] == "tabu")
    runs.loc[winner, "solution_json"] = json.dumps([0, 1, 2])
    with pytest.raises(ConfigurationError, match="solução inválida"):
        _select(runs)


def test_select_best_runs_rejects_solution_with_wrong_lot_count():
    # k=3 declarado, dois lotes de fato: a spec manda recusar, e sem esta guarda
    # a coluna sairia com rotulos nao contiguos e a simbologia perderia a classe.
    runs = _runs_frame()
    winner = (runs["seed"] == 25) & (runs["algorithm"] == "tabu")
    runs.loc[winner, "solution_json"] = json.dumps([0, 0, 0, 1, 1, 1])
    with pytest.raises(ConfigurationError, match="solução inválida"):
        _select(runs)


# Par discriminante: alinhar por sobreposicao maxima concorda com a referencia
# em 5 das 6 posicoes; canonicalizar por primeira ocorrencia concorda em 3.
DISCRIMINATING_REFERENCE = [0, 0, 1, 1, 2, 2]
DISCRIMINATING_OTHER = [0, 1, 0, 0, 2, 2]
DISCRIMINATING_ALIGNED = [1, 0, 1, 1, 2, 2]


def _agreement(left, right) -> int:
    return sum(1 for a, b in zip(left, right) if a == b)


def test_align_to_reference_recovers_a_permuted_copy():
    permuted = [2, 2, 0, 0, 1, 1]
    assert list(align_to_reference(permuted, DISCRIMINATING_REFERENCE, k=3)) == \
        DISCRIMINATING_REFERENCE


def test_align_to_reference_beats_canonicalization():
    # O teste que a versao 1 nao tinha: canonicalizar `other` daria
    # [0, 1, 0, 0, 2, 2], que concorda com a referencia em 3 posicoes.
    aligned = list(align_to_reference(DISCRIMINATING_OTHER,
                                      DISCRIMINATING_REFERENCE, k=3))
    assert aligned == DISCRIMINATING_ALIGNED
    assert _agreement(aligned, DISCRIMINATING_REFERENCE) == 5
    assert _agreement(DISCRIMINATING_OTHER, DISCRIMINATING_REFERENCE) == 3


def test_align_to_reference_maximizes_agreement_over_every_permutation():
    # Propriedade, e nao caso: nenhuma das k! renomeacoes concorda mais com a
    # referencia do que a escolhida. Mata canonicalizacao, identidade e guloso.
    aligned = align_to_reference(DISCRIMINATING_OTHER, DISCRIMINATING_REFERENCE, k=3)
    best = max(
        _agreement([mapping[label] for label in DISCRIMINATING_OTHER],
                   DISCRIMINATING_REFERENCE)
        for mapping in permutations(range(3))
    )
    assert _agreement(aligned, DISCRIMINATING_REFERENCE) == best


def test_align_to_reference_is_a_permutation():
    aligned = align_to_reference(DISCRIMINATING_OTHER, DISCRIMINATING_REFERENCE, k=3)
    assert sorted(np.bincount(aligned, minlength=3)) == \
        sorted(np.bincount(DISCRIMINATING_OTHER, minlength=3))
    for i in range(len(DISCRIMINATING_OTHER)):
        for j in range(len(DISCRIMINATING_OTHER)):
            same_before = DISCRIMINATING_OTHER[i] == DISCRIMINATING_OTHER[j]
            assert same_before == (aligned[i] == aligned[j])


def test_align_to_reference_is_idempotent_on_the_reference():
    aligned = align_to_reference(DISCRIMINATING_REFERENCE,
                                 DISCRIMINATING_REFERENCE, k=3)
    assert list(aligned) == DISCRIMINATING_REFERENCE


def _discriminating_selected() -> pd.DataFrame:
    return pd.DataFrame([
        {"instance": "artesp_rmsp_150", "algorithm": "tabu", "k": 3, "seed": 10,
         "total_cost": 0.1, "scenario_id": "a", "solution": DISCRIMINATING_REFERENCE},
        {"instance": "artesp_rmsp_150", "algorithm": "aco", "k": 3, "seed": 11,
         "total_cost": 0.2, "scenario_id": "b", "solution": DISCRIMINATING_OTHER},
        {"instance": "artesp_rmsp_150", "algorithm": "pso", "k": 3, "seed": 12,
         "total_cost": 0.3, "scenario_id": "c", "solution": [2, 2, 0, 0, 1, 1]},
    ])


def test_align_selected_uses_the_cheapest_method_as_reference():
    aligned = align_selected(_discriminating_selected()).set_index("algorithm")
    assert set(aligned["reference_algorithm"]) == {"tabu"}
    # `pso` e' a referencia permutada: alinhado, tem de coincidir com ela.
    assert aligned.loc["pso", "solution_aligned"] == DISCRIMINATING_REFERENCE
    # `aco` e' outra particao: alinhado, e' o vetor de sobreposicao maxima, e
    # NAO a sua canonicalizacao.
    assert aligned.loc["aco", "solution_aligned"] == DISCRIMINATING_ALIGNED
    assert aligned.loc["aco", "solution_aligned"] != DISCRIMINATING_OTHER


def test_align_selected_stores_the_canonical_labels_of_the_reference():
    selected = pd.DataFrame([
        {"instance": "i", "algorithm": "tabu", "k": 2, "seed": 10, "total_cost": 0.1,
         "scenario_id": "a", "solution": [1, 1, 0, 0]},
        {"instance": "i", "algorithm": "aco", "k": 2, "seed": 11, "total_cost": 0.2,
         "scenario_id": "b", "solution": [0, 0, 1, 1]},
        {"instance": "i", "algorithm": "pso", "k": 2, "seed": 12, "total_cost": 0.3,
         "scenario_id": "c", "solution": [0, 0, 1, 1]},
    ])
    aligned = align_selected(selected).set_index("algorithm")
    assert aligned.loc["tabu", "solution_aligned"] == [0, 0, 1, 1]
