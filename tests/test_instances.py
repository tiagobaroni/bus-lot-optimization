from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from metaheuristica import InstanceDataError
from metaheuristica.instances import load_artesp_instance, load_tiny_instance


PROJECT_ROOT = Path(__file__).parents[1]
INSTANCES_DIR = PROJECT_ROOT / "data" / "instances"


def test_tiny_instance_is_loaded_in_explicit_order() -> None:
    instance = load_tiny_instance(INSTANCES_DIR / "tiny_manual.json")
    assert instance.name == "tiny_manual"
    assert instance.unit_ids == ("A", "B", "C", "D")
    assert instance.demand.tolist() == [10.0] * 4
    assert instance.production.tolist() == [100.0] * 4
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
