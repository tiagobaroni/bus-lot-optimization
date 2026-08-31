from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import InstanceDataError, canonicalize_solution, evaluate_solution
from metaheuristica.instances import load_artesp_instance, load_tiny_instance


PROJECT_ROOT = Path(__file__).parents[1]
INSTANCES_DIR = PROJECT_ROOT / "data" / "instances"


def test_tiny_instance_is_loaded_in_explicit_order() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    assert instance.name == "tiny_manual"
    assert instance.unit_ids == ("A", "B", "C", "D")
    assert instance.demand.tolist() == [10.0] * 4
    assert instance.production.tolist() == [200.0, 100.0, 200.0, 100.0]
    assert instance.s_territorial[0, 1] == 1.0
    assert instance.s_territorial[2, 3] == 1.0
    assert np.array_equal(
        instance.w_affinity,
        (instance.t_terminal + instance.i_integration + instance.o_market) / 3.0,
    )
    assert instance.metadata["A"]["unit_id"] == "A"


@pytest.mark.parametrize("size", [20, 60, 150])
def test_artesp_instances_load_with_dense_readonly_matrices(size: int) -> None:
    instance = load_artesp_instance(INSTANCES_DIR, size)
    assert instance.n_units == size
    assert instance.demand.shape == (size,)
    for matrix in (
        instance.s_territorial,
        instance.t_terminal,
        instance.i_integration,
        instance.o_market,
        instance.w_affinity,
    ):
        assert matrix.shape == (size, size)
        assert np.array_equal(matrix, matrix.T)
        assert np.count_nonzero(np.diag(matrix)) == 0
        assert not matrix.flags.writeable


def test_artesp_instance_orders_are_nested_prefixes() -> None:
    ids_20 = load_artesp_instance(INSTANCES_DIR, 20).unit_ids
    ids_60 = load_artesp_instance(INSTANCES_DIR, 60).unit_ids
    ids_150 = load_artesp_instance(INSTANCES_DIR, 150).unit_ids
    assert ids_60[:20] == ids_20
    assert ids_150[:60] == ids_60


def test_tiny_loader_rejects_unknown_pair_and_out_of_range_metric(tmp_path: Path) -> None:
    source = json.loads((INSTANCES_DIR / "tiny_manual.json").read_text(encoding="utf-8"))
    source["pair_metrics"][0]["unit_id_b"] = "X"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(InstanceDataError, match="desconhecidos"):
        load_tiny_instance(invalid)

    source["pair_metrics"][0]["unit_id_b"] = "B"
    source["pair_metrics"][0]["s_territorial"] = 1.1
    invalid.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(InstanceDataError, match=r"fora de \[0, 1\]"):
        load_tiny_instance(invalid)


def test_artesp_loader_rejects_unsupported_size() -> None:
    with pytest.raises(InstanceDataError, match="não suportado"):
        load_artesp_instance(INSTANCES_DIR, 10)


VERSIONED_INSTANCE_SHA256 = {
    "artesp_rmsp_20.json":
        "9616ea96d24eaf1902bdc9857806f914f1a0ed024d6e875ec90e04421184c740",
    "artesp_rmsp_60.json":
        "a819812f87c91553dd10e34b0de92cd0d048832e9f3ee01a7e7314e118d1d412",
    "artesp_rmsp_150.json":
        "7ab22bad2ea9669a1fc1205e2ba2f1cf6af4d608c2ce5a2e2b6cb474c072be5d",
    "tiny_manual.json":
        "d5d624c5608edc096298af5240c7e041a09df1a8c60ba828ad669df71fb8b116",
    "artesp_rmsp_150_units.parquet":
        "8c4bd3cb5b1367259406cadfe36bf6654f1d230a7383604d346863ae6eaeb617",
    "artesp_rmsp_150_pair_metrics.parquet":
        "4bf5b7b1b68bac594a1aab6b0b47119dfd7ccf7b48eca89f26c0f095a1ebc2cd",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_versioned_instance_files_are_pinned_by_hash() -> None:
    """F2-15: os arquivos congelados não tinham linha de defesa testada.

    Alterar qualquer um deles mantinha a suíte verde, porque o único
    verificador de hash é o do congelamento, ele próprio sem teste. Os valores
    literais abaixo são o oráculo: divergência aqui é troca de dado, não
    observação.
    """

    for name, expected in VERSIONED_INSTANCE_SHA256.items():
        assert _sha256(INSTANCES_DIR / name) == expected, name


def test_versioned_tiny_optimum_matches_exhaustive_enumeration() -> None:
    """F2-15: o bloco `expected_optimum` do arquivo versionado era decorativo.

    Nenhum carregador o lê e o único teste que o lia trabalhava sobre cópia
    regerada em `tmp_path`. Aqui ele é confrontado com a enumeração exaustiva
    das atribuições de `N=4` unidades em `K=2` lotes, feita sobre o arquivo
    versionado.
    """

    path = INSTANCES_DIR / "tiny_manual.json"
    declared = json.loads(path.read_text(encoding="utf-8"))["expected_optimum"]
    instance = load_tiny_instance(path)
    assert declared["unit_order"] == list(instance.unit_ids)

    k = 2
    best_cost = math.inf
    optima: set[tuple[int, ...]] = set()
    for labels in itertools.product(range(k), repeat=instance.n_units):
        if len(set(labels)) != k:
            continue
        canonical = tuple(
            int(value)
            for value in canonicalize_solution(labels, n_units=instance.n_units, k=k)
        )
        cost = evaluate_solution(instance, canonical, k=k).total_cost
        if cost < best_cost:
            best_cost = cost
            optima = {canonical}
        elif cost == best_cost:
            optima.add(canonical)

    assert optima == {tuple(declared["canonical_solution"])}
    assert best_cost == declared["cost"]
    assert best_cost.hex() == float(declared["cost"]).hex()
