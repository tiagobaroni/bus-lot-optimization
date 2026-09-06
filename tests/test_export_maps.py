import hashlib
import json
from itertools import permutations
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import pytest
from shapely.geometry import LineString, Polygon

from metaheuristica.errors import ConfigurationError
from experiments.export_maps import (
    align_selected,
    align_to_reference,
    atomic_write_text,
    build_envoltorias,
    build_itinerarios,
    build_manifest,
    column_name,
    read_unit_ids,
    select_best_runs,
    write_gpkg,
)

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

# Segundo par, armadilha do guloso por linha: escolher o maximo de cada linha
# da matriz de contingencia sem impor bijecao funde os lotes 1 e 2 (ambos tem
# o maximo na mesma coluna) e da concordancia 4, MAIOR que o otimo (3), o que
# e' impossivel para uma permutacao valida. Sem este par, um guloso por linha
# (`contingency.argmax(axis=1)`) passa nos mesmos testes que a atribuicao
# otima por `linear_sum_assignment`.
GREEDY_TRAP_OTHER = [0, 0, 1, 2, 0, 0]


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


@pytest.mark.parametrize("other", [DISCRIMINATING_OTHER, GREEDY_TRAP_OTHER])
def test_align_to_reference_maximizes_agreement_over_every_permutation(other):
    # Propriedade, e nao caso: nenhuma das k! renomeacoes concorda mais com a
    # referencia do que a escolhida. Mata canonicalizacao, identidade e guloso.
    # `GREEDY_TRAP_OTHER` e' o par que pega o guloso por linha: ele da
    # concordancia 4, acima do otimo (3), porque nao e' uma permutacao valida.
    aligned = align_to_reference(other, DISCRIMINATING_REFERENCE, k=3)
    best = max(
        _agreement([mapping[label] for label in other],
                   DISCRIMINATING_REFERENCE)
        for mapping in permutations(range(3))
    )
    assert _agreement(aligned, DISCRIMINATING_REFERENCE) == best


@pytest.mark.parametrize("other", [DISCRIMINATING_OTHER, GREEDY_TRAP_OTHER])
def test_align_to_reference_is_a_permutation(other):
    aligned = align_to_reference(other, DISCRIMINATING_REFERENCE, k=3)
    assert sorted(np.bincount(aligned, minlength=3)) == \
        sorted(np.bincount(other, minlength=3))
    for i in range(len(other)):
        for j in range(len(other)):
            same_before = other[i] == other[j]
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


def test_align_selected_breaks_cost_ties_by_tabu_aco_pso_order():
    # Os tres `total_cost` sao iguais: sem o desempate `tabu, aco, pso`, a
    # escolha da referencia dependeria da ordem de insercao das linhas.
    selected = pd.DataFrame([
        {"instance": "i", "algorithm": "tabu", "k": 3, "seed": 10, "total_cost": 0.5,
         "scenario_id": "a", "solution": DISCRIMINATING_REFERENCE},
        {"instance": "i", "algorithm": "aco", "k": 3, "seed": 11, "total_cost": 0.5,
         "scenario_id": "b", "solution": DISCRIMINATING_OTHER},
        {"instance": "i", "algorithm": "pso", "k": 3, "seed": 12, "total_cost": 0.5,
         "scenario_id": "c", "solution": [2, 2, 0, 0, 1, 1]},
    ])
    aligned = align_selected(selected)
    assert set(aligned["reference_algorithm"]) == {"tabu"}


def test_align_selected_breaks_ties_among_non_reference_methods_too():
    # `tabu` e' o mais caro; `aco` e `pso` empatam entre si. O desempate tem
    # de escolher `aco` pela ordem `tabu, aco, pso`, nao `pso`.
    selected = pd.DataFrame([
        {"instance": "i", "algorithm": "tabu", "k": 3, "seed": 10, "total_cost": 0.9,
         "scenario_id": "a", "solution": DISCRIMINATING_REFERENCE},
        {"instance": "i", "algorithm": "aco", "k": 3, "seed": 11, "total_cost": 0.2,
         "scenario_id": "b", "solution": DISCRIMINATING_OTHER},
        {"instance": "i", "algorithm": "pso", "k": 3, "seed": 12, "total_cost": 0.2,
         "scenario_id": "c", "solution": [2, 2, 0, 0, 1, 1]},
    ])
    aligned = align_selected(selected)
    assert set(aligned["reference_algorithm"]) == {"aco"}


def _instances_dir(tmp_path: Path) -> Path:
    # Universo de 6 unidades: 2 no recorte de 20, 4 no de 60, 6 no de 150.
    # A ordem do GPKG e' invertida em relacao a `unit_ids` de proposito: um
    # `build` que confiasse na ordem das feicoes trocaria os lotes de lugar.
    directory = tmp_path / "instances"
    directory.mkdir()
    unit_ids = {20: ["u0", "u1"], 60: ["u0", "u1", "u2", "u3"],
                150: ["u0", "u1", "u2", "u3", "u4", "u5"]}
    for size, ids in unit_ids.items():
        (directory / f"artesp_rmsp_{size}.json").write_text(
            json.dumps({"name": f"artesp_rmsp_{size}", "n_units": len(ids),
                        "unit_ids": ids}), encoding="utf-8")
    gpkg = directory / "artesp_rmsp_150.gpkg"
    gpd.GeoDataFrame(
        {
            "unit_id": list(reversed(unit_ids[150])),
            "codigo_linha": ["c"] * 6, "sentido": ["ida"] * 6,
            "nome_legivel": ["n"] * 6, "passengers_day": [1.0] * 6,
            "pu_km_day": [2.0] * 6, "route_length_km": [3.0] * 6,
        },
        # Segmentos retos: o casco convexo de um deles NAO e' poligono, o que
        # torna o ramo do lote degenerado exercitavel na Task 5.
        geometry=[LineString([(index, 0), (index, 1)]) for index in range(6)],
        crs="EPSG:4326",
    ).to_file(gpkg, layer="itinerarios", driver="GPKG")
    # `main` le a camada `terminais`: sem ela, os testes da Task 8 abortam com
    # DataLayerError antes da primeira asercao.
    gpd.GeoDataFrame(
        {"id_terminal": [1], "nome": ["t"], "terminal_situacao": ["ativo"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:4326",
    ).to_file(gpkg, layer="terminais", driver="GPKG", mode="a")
    # As instancias menores tambem precisam do proprio `.gpkg`: a spec, secao 9,
    # manda recusar quando falta, e o manifesto registra o sha de cada uma.
    for size in (20, 60):
        gpd.GeoDataFrame(
            {"unit_id": unit_ids[size]},
            geometry=[LineString([(index, 0), (index, 1)])
                      for index in range(len(unit_ids[size]))],
            crs="EPSG:4326",
        ).to_file(directory / f"artesp_rmsp_{size}.gpkg", layer="itinerarios",
                  driver="GPKG")
    return directory


def _aligned_row(instance, algorithm, k, solution, solution_aligned, *, seed=10,
                 cost=0.1, scenario="s") -> dict:
    return {"instance": instance, "algorithm": algorithm, "k": k, "seed": seed,
            "total_cost": cost, "scenario_id": scenario, "solution": solution,
            "solution_aligned": solution_aligned, "reference_algorithm": algorithm}


def test_column_name_follows_the_agreed_pattern():
    assert column_name("artesp_rmsp_20", "pso", 5) == "lot_i20_pso_k5"


def test_read_unit_ids_returns_the_three_nested_slices(tmp_path):
    unit_ids = read_unit_ids(_instances_dir(tmp_path))
    assert set(unit_ids) == {20, 60, 150}
    assert unit_ids[20] == ["u0", "u1"]
    # O aninhamento que a spec, secao 2, declara verificado.
    assert set(unit_ids[20]) < set(unit_ids[60]) < set(unit_ids[150])


def test_read_unit_ids_rejects_a_missing_instance_file(tmp_path):
    directory = _instances_dir(tmp_path)
    (directory / "artesp_rmsp_60.gpkg").unlink()
    with pytest.raises(ConfigurationError, match="instância ausente"):
        read_unit_ids(directory)


def test_build_itinerarios_joins_by_unit_id_not_by_position(tmp_path):
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "tabu", 2, [1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1])])
    frame = build_itinerarios(directory, aligned).set_index("unit_id")
    column = column_name("artesp_rmsp_150", "tabu", 2)
    assert list(frame.loc[["u0", "u1", "u2"], column]) == [0, 0, 0]
    assert list(frame.loc[["u3", "u4", "u5"], column]) == [1, 1, 1]


def test_build_itinerarios_uses_the_aligned_labels_not_the_raw_ones(tmp_path):
    # `solution` e `solution_aligned` sao DIFERENTES de proposito: trocar uma
    # pela outra na implementacao e' um bug de uma palavra que produziria os
    # nove paineis coloridos pela numeracao bruta, que e' o que a spec, secao 7,
    # diz que arruina o bloco.
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "aco", 2, [1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1])])
    frame = build_itinerarios(directory, aligned).set_index("unit_id")
    column = column_name("artesp_rmsp_150", "aco", 2)
    assert list(frame.loc[["u0", "u1", "u2"], column]) == [0, 0, 0]


def test_build_itinerarios_marks_the_nesting(tmp_path):
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame(columns=["instance", "algorithm", "k", "seed",
                                    "total_cost", "scenario_id", "solution",
                                    "solution_aligned", "reference_algorithm"])
    frame = build_itinerarios(directory, aligned).set_index("unit_id")
    assert list(frame.loc[["u0", "u1"], "aninhamento"]) == ["20_60_150"] * 2
    assert list(frame.loc[["u2", "u3"], "aninhamento"]) == ["60_150"] * 2
    assert list(frame.loc[["u4", "u5"], "aninhamento"]) == ["so_150"] * 2
    assert list(frame.loc[["u0", "u2", "u4"], "in_20"]) == [True, False, False]
    assert list(frame.loc[["u0", "u2", "u4"], "in_60"]) == [True, True, False]
    assert "in_150" not in frame.columns


def test_build_itinerarios_leaves_units_outside_the_slice_null(tmp_path):
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_20", "pso", 2, [0, 1], [0, 1])])
    frame = build_itinerarios(directory, aligned).set_index("unit_id")
    column = column_name("artesp_rmsp_20", "pso", 2)
    assert list(frame.loc[["u0", "u1"], column]) == [0, 1]
    assert frame.loc[["u2", "u3", "u4", "u5"], column].isna().all()


def test_build_itinerarios_holds_the_three_instances_side_by_side(tmp_path):
    # A camada real tem 54 colunas de lote das tres instancias ao mesmo tempo,
    # com o padrao de nulos aninhado. Nenhum teste de instancia unica prova isso.
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([
        _aligned_row("artesp_rmsp_20", "pso", 2, [0, 1], [0, 1]),
        _aligned_row("artesp_rmsp_60", "aco", 2, [0, 0, 1, 1], [0, 0, 1, 1]),
        _aligned_row("artesp_rmsp_150", "tabu", 2, [0, 0, 0, 1, 1, 1],
                     [0, 0, 0, 1, 1, 1]),
    ])
    frame = build_itinerarios(directory, aligned)
    columns = [column_name("artesp_rmsp_20", "pso", 2),
               column_name("artesp_rmsp_60", "aco", 2),
               column_name("artesp_rmsp_150", "tabu", 2)]
    assert len(set(columns)) == 3
    assert all(column in frame.columns for column in columns)
    assert [int(frame[column].notna().sum()) for column in columns] == [2, 4, 6]
    assert all(str(frame[column].dtype) == "Int64" for column in columns)
    # Os atributos descritivos da instancia de 150 sobrevivem ao recorte de
    # colunas, e o resultado continua um GeoDataFrame em EPSG:4326 (CRS de
    # armazenamento exigido pelas restricoes globais do bloco). A lista abaixo
    # e' literal, e nao a constante `DESCRIPTIVE_COLUMNS` do proprio modulo:
    # comparar a constante contra si mesma, atraves do recorte feito com ela,
    # nunca falharia por uma constante truncada.
    expected_descriptive_columns = ["unit_id", "codigo_linha", "sentido",
                                    "nome_legivel", "passengers_day",
                                    "pu_km_day", "route_length_km"]
    assert all(column in frame.columns for column in expected_descriptive_columns)
    # Um valor sobrevivente de verdade, nao so o nome da coluna: pega
    # truncamento que preservasse o rotulo mas descartasse o conteudo.
    assert frame.set_index("unit_id").loc["u0", "pu_km_day"] == 2.0
    assert isinstance(frame, gpd.GeoDataFrame)
    assert frame.crs.to_string() == "EPSG:4326"


def test_build_itinerarios_rejects_unit_id_divergence(tmp_path):
    directory = _instances_dir(tmp_path)
    payload = json.loads((directory / "artesp_rmsp_150.json").read_text(encoding="utf-8"))
    payload["unit_ids"][0] = "fantasma"
    (directory / "artesp_rmsp_150.json").write_text(json.dumps(payload), encoding="utf-8")
    aligned = pd.DataFrame(columns=["instance", "algorithm", "k", "seed",
                                    "total_cost", "scenario_id", "solution",
                                    "solution_aligned", "reference_algorithm"])
    with pytest.raises(ConfigurationError, match="divergem"):
        build_itinerarios(directory, aligned)


def test_build_itinerarios_rejects_an_unknown_instance_size(tmp_path):
    # `read_unit_ids` so conhece 20, 60 e 150; uma linha de `aligned` com outro
    # tamanho nao pode virar `KeyError` cru — o `main` da Task 8 so pega
    # `ConfigurationError`.
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_999", "pso", 2, [0, 1], [0, 1])])
    with pytest.raises(ConfigurationError, match="desconhecida"):
        build_itinerarios(directory, aligned)


def test_build_itinerarios_rejects_a_solution_length_mismatch(tmp_path):
    # `solution_aligned` com comprimento diferente do `unit_ids` da instancia
    # nao pode virar `ValueError` cru do `zip(..., strict=True)`.
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_20", "pso", 2, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])])
    with pytest.raises(ConfigurationError, match="alinhada"):
        build_itinerarios(directory, aligned)


def test_build_itinerarios_rejects_a_duplicate_lot_column(tmp_path):
    # Duas linhas de `aligned` que produzem o mesmo nome de coluna nao podem
    # sobrescrever uma a outra em silencio.
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([
        _aligned_row("artesp_rmsp_20", "pso", 2, [0, 1], [0, 1], seed=10),
        _aligned_row("artesp_rmsp_20", "pso", 2, [1, 0], [1, 0], seed=11),
    ])
    with pytest.raises(ConfigurationError, match="duplicada"):
        build_itinerarios(directory, aligned)


def _envoltorias(tmp_path, solution, solution_aligned, k=2):
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "tabu", k, solution, solution_aligned)])
    itinerarios = build_itinerarios(directory, aligned)
    return build_envoltorias(itinerarios, aligned, read_unit_ids(directory))


def test_build_envoltorias_creates_one_polygon_per_lot(tmp_path):
    envoltorias = _envoltorias(tmp_path, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])
    assert len(envoltorias) == 2
    assert sorted(envoltorias["lot"]) == [0, 1]
    assert set(envoltorias["n_units"]) == {3}
    assert (envoltorias.geometry.geom_type == "Polygon").all()
    assert list(envoltorias["seed"]) == [10, 10]
    # Sem esta asercao, `degenerado = True` incondicional passaria.
    assert not envoltorias["degenerado"].any()


def test_build_envoltorias_computes_area_in_the_metric_crs(tmp_path):
    # Em graus, a area destes cascos sairia na casa de 1e-6; em km2, de 1e4.
    # A asercao de magnitude separa a implementacao que nunca reprojeta.
    envoltorias = _envoltorias(tmp_path, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])
    assert envoltorias["area_km2"].min() > 1.0


def test_build_envoltorias_returns_geographic_coordinates(tmp_path):
    # `set_crs` sem transformar deixaria o CRS certo e as coordenadas em 1e6.
    # Esta asercao pega essa, e a de area pega a outra: sao defeitos distintos.
    envoltorias = _envoltorias(tmp_path, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])
    assert envoltorias.crs.to_string() == "EPSG:4326"
    minimum_x, minimum_y, maximum_x, maximum_y = envoltorias.total_bounds
    assert -180 <= minimum_x <= maximum_x <= 180
    assert -90 <= minimum_y <= maximum_y <= 90


def test_build_envoltorias_marks_the_degenerate_lot(tmp_path):
    envoltorias = _envoltorias(tmp_path, [0, 1, 1, 1, 1, 1], [0, 1, 1, 1, 1, 1])
    single = envoltorias[envoltorias["lot"] == 0].iloc[0]
    # O casco convexo de um segmento reto e' LineString, nao poligono: o ramo
    # do buffer de 50 m e' de fato exercitado aqui.
    assert single["degenerado"]
    assert single.geometry.geom_type == "Polygon"
    assert single["n_units"] == 1
    # E o lote normal do mesmo cenario nao pode vir marcado.
    assert not envoltorias[envoltorias["lot"] == 1].iloc[0]["degenerado"]


def test_build_envoltorias_uses_the_aligned_labels_not_the_raw_ones(tmp_path):
    # Bruto poria uma unidade no lote 0 e cinco no 1; alinhado, o inverso.
    envoltorias = _envoltorias(tmp_path, [0, 1, 1, 1, 1, 1], [1, 0, 0, 0, 0, 0])
    by_lot = envoltorias.set_index("lot")["n_units"].to_dict()
    assert by_lot == {0: 5, 1: 1}


def _one_scenario(tmp_path):
    directory = _instances_dir(tmp_path)
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "tabu", 2, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])])
    itinerarios = build_itinerarios(directory, aligned)
    envoltorias = build_envoltorias(itinerarios, aligned, read_unit_ids(directory))
    return directory, aligned, itinerarios, envoltorias


def test_write_gpkg_writes_every_layer(tmp_path):
    directory, aligned, itinerarios, envoltorias = _one_scenario(tmp_path)
    terminais = gpd.read_file(directory / "artesp_rmsp_150.gpkg", layer="terminais")
    target = tmp_path / "saida" / "lot_assignments.gpkg"
    write_gpkg(target, {"itinerarios": itinerarios, "envoltorias": envoltorias,
                        "terminais": terminais})
    assert sorted(name for name, _ in pyogrio.list_layers(target)) == [
        "envoltorias", "itinerarios", "terminais"]


def test_write_gpkg_leaves_no_file_when_a_layer_fails(tmp_path):
    # Atomicidade de verdade: a asercao "nao sobrou .tmp" e' satisfeita ate' por
    # uma escrita direta sem temporario. O que so' a escrita atomica garante e'
    # que uma falha no meio nao deixa o arquivo final pela metade.
    _, _, itinerarios, _ = _one_scenario(tmp_path)
    target = tmp_path / "saida" / "lot_assignments.gpkg"
    with pytest.raises(AttributeError):
        write_gpkg(target, {"itinerarios": itinerarios, "quebrada": "não é camada"})
    assert not target.exists()
    assert not list(target.parent.glob(".*tmp*"))


def test_atomic_write_text_replaces_without_leaving_residue(tmp_path):
    target = tmp_path / "saida" / "manifesto.json"
    atomic_write_text(target, "primeiro")
    atomic_write_text(target, "segundo")
    assert target.read_text(encoding="utf-8") == "segundo"
    assert not list(target.parent.glob(".*tmp*"))


def test_build_manifest_records_the_real_source_digest(tmp_path):
    directory = _instances_dir(tmp_path)
    runs_path = tmp_path / "benchmark_runs.parquet"
    runs_path.write_bytes(b"conteudo")
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "tabu", 2, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])])
    manifest = build_manifest(runs_path, directory, aligned,
                              generated_at="2026-09-06T00:00:00")
    # Comparar com o digest conhecido, e nao so' afirmar que a chave e' verdadeira:
    # `assert manifest[...]["content_sha256"]` passa com o sha de qualquer coisa.
    assert manifest["source"]["content_sha256"] == \
        hashlib.sha256(b"conteudo").hexdigest()
    assert manifest["source"]["path"] == str(runs_path)


def test_build_manifest_lists_every_combination_with_its_winning_seed(tmp_path):
    directory = _instances_dir(tmp_path)
    runs_path = tmp_path / "benchmark_runs.parquet"
    runs_path.write_bytes(b"conteudo")
    # Tres combinacoes com seeds DIFERENTES: com uma linha so' e uma seed so',
    # a asercao sobre a seed vencedora passa por vacuo.
    aligned = pd.DataFrame([
        _aligned_row("artesp_rmsp_150", "tabu", 2, [0, 0, 0, 1, 1, 1],
                     [0, 0, 0, 1, 1, 1], seed=11, cost=0.1, scenario="t"),
        _aligned_row("artesp_rmsp_60", "aco", 2, [0, 0, 1, 1], [0, 0, 1, 1],
                     seed=22, cost=0.2, scenario="a"),
        _aligned_row("artesp_rmsp_20", "pso", 2, [0, 1], [0, 1],
                     seed=33, cost=0.3, scenario="p"),
    ])
    manifest = build_manifest(runs_path, directory, aligned,
                              generated_at="2026-09-06T00:00:00")
    by_column = {item["column"]: item for item in manifest["combinations"]}
    assert by_column["lot_i150_tabu_k2"]["seed"] == 11
    assert by_column["lot_i60_aco_k2"]["seed"] == 22
    assert by_column["lot_i20_pso_k2"]["seed"] == 33
    assert manifest["references"]["artesp_rmsp_150|2"] == "tabu"


def test_build_manifest_records_path_and_digest_of_every_instance(tmp_path):
    directory = _instances_dir(tmp_path)
    runs_path = tmp_path / "benchmark_runs.parquet"
    runs_path.write_bytes(b"conteudo")
    aligned = pd.DataFrame([_aligned_row(
        "artesp_rmsp_150", "tabu", 2, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1])])
    manifest = build_manifest(runs_path, directory, aligned,
                              generated_at="2026-09-06T00:00:00")
    entry = manifest["instances"]["artesp_rmsp_20"]
    # A spec, secao 6.4, pede caminho E sha de cada instancia consumida, e
    # nenhum sha pode ser nulo: instancia sem arquivo e' caso de recusa.
    assert entry["gpkg_path"].endswith("artesp_rmsp_20.gpkg")
    assert len(entry["gpkg_sha256"]) == 64
    assert len(entry["json_sha256"]) == 64
