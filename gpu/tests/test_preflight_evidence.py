"""A evidência que explica a falha não pode ir embora com ela.

A série do preflight é o único registro da trajetória térmica entre cenários.
Enquanto ela não era persistida, a margem térmica só podia ser inferida da
primeira amostra pós-warmup, que foi o que o diagnóstico de 03/09/2026 teve de
fazer para explicar a interrupção do cenário 4.
"""

import csv

import pytest

from metaheuristica_gpu import run as run_module
from metaheuristica_gpu.monitor import GpuSafetyError, GpuSample, ThermalWaitTimeout
from metaheuristica_gpu.scenarios import GpuScenario

CENARIO = GpuScenario({"budget": 3, "seed": 10, "algorithm": "aco"}, "aaa")


def _amostra(temperatura: int) -> GpuSample:
    return GpuSample(0.0, temperatura, 0.0, 0.0, 100, 12288, 20.0, 200, 400,
                     "inactive", "inactive", 0)


def _preflight_falho(erro, temperaturas):
    def falso(*, sink=None, **kwargs):
        for valor in temperaturas:
            if sink is not None:
                sink(_amostra(valor))
        raise erro
    return falso


@pytest.mark.parametrize("erro", [
    ThermalWaitTimeout("teto esgotado"),
    GpuSafetyError("outro processo computacional usa a GPU"),
])
def test_serie_do_preflight_sobrevive_a_falha(tmp_path, monkeypatch, erro) -> None:
    monkeypatch.setattr(run_module, "preflight_idle", _preflight_falho(erro, [70, 68, 66]))
    with pytest.raises(type(erro)):
        run_module._preflight_with_evidence(tmp_path, CENARIO)

    caminho = tmp_path / "telemetry" / f"{CENARIO.scenario_id}_preflight.csv"
    assert caminho.is_file(), "a série do preflight não chegou ao disco"
    linhas = list(csv.DictReader(caminho.read_text(encoding="utf-8").splitlines()))
    # Anti-vácuo: são as amostras da espera, e não um arquivo vazio com cabeçalho.
    assert [int(item["temperature_c"]) for item in linhas] == [70, 68, 66]


def test_serie_do_preflight_e_gravada_no_sucesso(tmp_path, monkeypatch) -> None:
    def falso(*, sink=None, **kwargs):
        if sink is not None:
            sink(_amostra(45))
        return ()

    monkeypatch.setattr(run_module, "preflight_idle", falso)
    run_module._preflight_with_evidence(tmp_path, CENARIO)
    caminho = tmp_path / "telemetry" / f"{CENARIO.scenario_id}_preflight.csv"
    linhas = list(csv.DictReader(caminho.read_text(encoding="utf-8").splitlines()))
    assert [int(item["temperature_c"]) for item in linhas] == [45]
