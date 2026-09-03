import json
from types import SimpleNamespace

import pytest

from metaheuristica_gpu import run as run_module
from metaheuristica_gpu.run import GpuConfigurationError

from metaheuristica_gpu.scenarios import GpuScenario
from metaheuristica_gpu.storage import (
    GpuStorageError,
    atomic_write_json,
    is_complete,
    read_json,
    result_path,
    validate_result,
)


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



# --- B11F. Proveniência de código no resultado --------------------------------

CENARIO_A = GpuScenario({"budget": 3, "seed": 10, "algorithm": "aco"}, "aaa")
CENARIO_B = GpuScenario({"budget": 3, "seed": 11, "algorithm": "aco"}, "bbb")


def _documento(cenario: GpuScenario, gpu_code_sha256: str) -> dict:
    return run_module.scenario_document(
        cenario,
        SimpleNamespace(to_dict=lambda: {"evaluations": cenario.payload["budget"]}),
        SimpleNamespace(to_dict=lambda: {}),
        {},
        cold_total_seconds=1.0,
        telemetry="results/gpu/telemetry/aaa.csv",
        gpu_code_sha256=gpu_code_sha256,
    )


def _grava(raiz, cenario: GpuScenario, gpu_code_sha256: str) -> None:
    atomic_write_json(result_path(raiz, cenario), _documento(cenario, gpu_code_sha256))


def test_documento_declara_o_hash_do_codigo_gpu() -> None:
    assert _documento(CENARIO_A, "abc123")["gpu_code_sha256"] == "abc123"


def test_o_caminho_de_completude_ignora_o_hash(tmp_path) -> None:
    """A conferência de hash não pode migrar para `validate_result`.

    `is_complete` chama `validate_result` e **propaga** `GpuStorageError`
    (`storage.py:52-57`). Conferir o hash ali faria `readiness`, `execute` e
    `consolidate` recusarem duro sobre resultados íntegros, só por terem sido
    produzidos sob o código anterior.
    """
    _grava(tmp_path, CENARIO_A, "hash-de-outra-versao")
    documento = read_json(result_path(tmp_path, CENARIO_A))
    validate_result(documento, CENARIO_A)          # não levanta
    assert is_complete(tmp_path, CENARIO_A)        # e continua completo
    assert documento["gpu_code_sha256"] == "hash-de-outra-versao"


def test_hash_unico_recusa_divergencia(tmp_path) -> None:
    _grava(tmp_path, CENARIO_A, "hash-a")
    _grava(tmp_path, CENARIO_B, "hash-b")
    with pytest.raises(GpuConfigurationError, match="divergentes"):
        run_module._results_code_hash(tmp_path, [CENARIO_A, CENARIO_B])


def test_hash_unico_aceita_campanha_coerente(tmp_path) -> None:
    _grava(tmp_path, CENARIO_A, "hash-a")
    _grava(tmp_path, CENARIO_B, "hash-a")
    assert run_module._results_code_hash(tmp_path, [CENARIO_A, CENARIO_B]) == "hash-a"
    # Anti-vácuo: conjunto vazio é ausência de campanha, e não concordância.
    assert run_module._results_code_hash(tmp_path, []) is None


def test_documento_sem_procedencia_e_recusado(tmp_path) -> None:
    """`{None}` tem tamanho 1 e passaria por "hash único" se a ausência da chave
    fosse tolerada, publicando uma campanha sem procedência nenhuma."""
    documento = _documento(CENARIO_A, "hash-a")
    del documento["gpu_code_sha256"]
    atomic_write_json(result_path(tmp_path, CENARIO_A), documento)
    with pytest.raises(GpuConfigurationError, match="procedência"):
        run_module._results_code_hash(tmp_path, [CENARIO_A])


def test_a_prontidao_recusa_divergencia_contra_o_manifesto() -> None:
    """Sem este caso, apagar a guarda de produção deixa a tarefa verde."""
    with pytest.raises(GpuConfigurationError, match="manifesto"):
        run_module._assert_results_match_manifest(
            "hash-dos-resultados", {"gpu_code_sha256": "hash-do-manifesto"})
    # Anti-vácuo: com hashes iguais não levanta, e campanha vazia também não.
    run_module._assert_results_match_manifest("h", {"gpu_code_sha256": "h"})
    run_module._assert_results_match_manifest(None, {"gpu_code_sha256": "h"})
