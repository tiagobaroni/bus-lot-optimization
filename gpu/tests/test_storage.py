import json

import pytest

from metaheuristica_gpu.scenarios import GpuScenario
from metaheuristica_gpu.storage import GpuStorageError, atomic_write_json, is_complete, read_json


def test_escrita_atomica_e_validacao(tmp_path):
    scenario = GpuScenario({"budget": 3}, "abc")
    document = {"scenario_id": "abc", "scenario": {"budget": 3}, "result": {"evaluations": 3}}
    path = tmp_path / "raw/abc.json"
    atomic_write_json(path, document)
    assert read_json(path) == document
    assert is_complete(tmp_path, scenario)
    assert not list(path.parent.glob("*.tmp"))


def test_corrupcao_nao_e_ignorada(tmp_path):
    scenario = GpuScenario({"budget": 3}, "abc")
    path = tmp_path / "raw/abc.json"
    path.parent.mkdir(parents=True)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(GpuStorageError):
        is_complete(tmp_path, scenario)

