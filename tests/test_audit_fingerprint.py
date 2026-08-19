"""Testes do oráculo de impressão digital da auditoria B11B."""

from math import nextafter
from pathlib import Path
import tomllib

import pytest

from experiments.audit_fingerprint import (
    BUDGETS,
    FINGERPRINT_SEED,
    RUNNER_UP,
    TINY_BUDGET,
    compare,
    generate,
    scenarios,
)


ROOT = Path(__file__).resolve().parents[1]


def test_expande_42_cenarios_com_ids_unicos():
    expanded = scenarios()
    assert len(expanded) == 42
    identifiers = [scenario.scenario_id for scenario in expanded]
    assert len(set(identifiers)) == 42
    algorithms = {scenario.algorithm for scenario in expanded}
    assert algorithms == {"tabu", "aco", "pso", "greedy"}
    runner_up = [s for s in expanded if s.variant == "runner_up"]
    assert len(runner_up) == 3
    assert {s.algorithm for s in runner_up} == {"tabu", "aco", "pso"}
    assert {(s.instance, s.k) for s in runner_up} == {("artesp_rmsp_60", 5)}


def test_runner_up_coincide_com_o_segundo_colocado_do_tuning():
    import json

    import pandas as pd

    summary = pd.read_parquet(ROOT / "results/tables/tuning_summary.parquet")
    for algorithm, expected in RUNNER_UP.items():
        row = summary[
            (summary["algorithm"] == algorithm) & (summary["rank"] == 2)
        ].iloc[0]
        assert json.loads(row["parameters_json"]) == expected
        assert bool(row["selected"]) is False


def test_seed_disjunta_das_campanhas_oficiais():
    comprometidas = set(range(10)) | {0, 1, 2} | {20260817, 20260818} | set(range(10, 40))
    assert FINGERPRINT_SEED not in comprometidas


def test_orcamentos_forcam_geracao_e_iteracao_parciais():
    with (ROOT / "experiments/configs/frozen_parameters.toml").open("rb") as stream:
        frozen = tomllib.load(stream)
    assert BUDGETS["aco"] % frozen["aco"]["n_ants"] != 0
    assert BUDGETS["pso"] % frozen["pso"]["n_particles"] != 0
    assert TINY_BUDGET % frozen["aco"]["n_ants"] != 0


def test_compare_aprova_documento_identico():
    documento = {"scenarios": {"a": {"custo": 0.125, "avaliacoes": 10}}}
    assert compare(documento, documento) == []


def test_compare_detecta_diferenca_de_um_ulp():
    base = {"scenarios": {"a": {"custo": 0.125}}}
    perturbado = {"scenarios": {"a": {"custo": nextafter(0.125, 1.0)}}}
    diferencas = compare(base, perturbado)
    assert len(diferencas) == 1
    assert "scenarios.a.custo" in diferencas[0]


def test_compare_distingue_zero_negativo():
    assert compare({"v": 0.0}, {"v": -0.0}) != []


def test_compare_distingue_inteiro_de_flutuante():
    assert compare({"v": 1}, {"v": 1.0}) != []


def test_compare_detecta_chave_ausente_e_tamanho_de_lista():
    assert compare({"a": 1, "b": 2}, {"a": 1}) != []
    assert compare({"a": [1, 2]}, {"a": [1]}) != []


def test_generate_e_deterministico_na_instancia_minuscula():
    primeiro = generate(ROOT, workers=1, only=("tabu:tiny_manual:2:frozen",))
    segundo = generate(ROOT, workers=1, only=("tabu:tiny_manual:2:frozen",))
    assert compare(primeiro, segundo) == []
    assert primeiro["content_sha256"] == segundo["content_sha256"]


def test_generate_em_processos_coincide_com_execucao_serial():
    serial = generate(ROOT, workers=1, only=("tabu:tiny_manual:2:frozen", "aco:tiny_manual:2:frozen"))
    paralelo = generate(ROOT, workers=2, only=("tabu:tiny_manual:2:frozen", "aco:tiny_manual:2:frozen"))
    assert compare(serial, paralelo) == []
