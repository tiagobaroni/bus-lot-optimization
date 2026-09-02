"""Portão de conformidade em modo oficial e diagnósticos condicionais."""

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from metaheuristica import AcoConfig, RunConfig, load_artesp_instance
from metaheuristica_gpu.config import load_gpu_config
from metaheuristica_gpu.environment import GpuConfigurationError
from metaheuristica_gpu.numerics import ABS_TOL, NumericalDivergenceError
from metaheuristica_gpu.storage import GpuStorageError


ROOT = Path(__file__).parents[2]


@lru_cache(maxsize=None)
def _campanha():
    return load_gpu_config(ROOT / "gpu/configs/gpu_benchmark.toml")


def test_conformidade_obsoleta_nao_pode_ser_congelada(tmp_path: Path) -> None:
    import metaheuristica_gpu.run as modulo

    conformidade = tmp_path / "conformidade.json"
    roteiro = tmp_path / "roteiro.json"
    manifesto = tmp_path / "manifesto.json"
    conformidade.write_text(
        '{"passed":true,"configuration":{"config_sha256":"antigo",'
        '"scenario_ids_sha256":"antigo"}}',
        encoding="utf-8",
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "CONFORMANCE", conformidade)
        patch.setattr(modulo, "SCHEDULE", roteiro)
        patch.setattr(modulo, "MANIFEST", manifesto)
        with pytest.raises(GpuConfigurationError, match="configuração obsoleta"):
            modulo.generate_manifest(_campanha())
    assert not roteiro.exists()
    assert not manifesto.exists()


def test_a_conformidade_afirma_a_trajetoria_em_modo_oficial_sobre_instancia_real() -> None:
    """F8-1, componente `M2`: o portão passa a afirmar, e não só a registrar.

    `run_conformance` publicava `reproducible_data()` das duas execuções
    pareadas e **não afirmava nada**, e as duas rodavam com
    `verify_every_batch=True`, modo em que `HybridEvaluator.evaluate_batch`
    substitui os resultados da GPU pelos normativos: comparar ali é comparar
    CPU com CPU.

    As três propriedades que impedem este caso de ser vazio estão asseveradas
    aqui dentro. Primeira, o par roda em **modo oficial**, medido pelos
    argumentos de fato passados e não por leitura do código. Segunda, a
    instância é **real**, com 20 unidades, e não a `tiny_manual` de quatro
    unidades com `K=2`, cujo custo é exatamente zero em 99 dos 100 checkpoints
    do ACO e em 98 dos 100 do PSO. Terceira, e é a que fecha o argumento, a
    divergência medida é **estritamente positiva**: se os resultados da GPU
    tivessem sido descartados, ela valeria exatamente zero.
    """

    import metaheuristica_gpu.run as modulo

    chamadas: list[tuple[str, int, bool]] = []

    def espiao(nome, real):
        def interno(instance, run, config, **extras):
            chamadas.append((nome, instance.n_units, bool(extras.get("verify_every_batch", False))))
            return real(instance, run, config, **extras)

        return interno

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "run_aco_gpu", espiao("aco", modulo.run_aco_gpu))
        patch.setattr(modulo, "run_pso_gpu", espiao("pso", modulo.run_pso_gpu))
        trajetorias = modulo.conformance_trajectories(_campanha())

    assert [nome for nome, _, _ in chamadas] == ["aco", "pso"]
    assert all(unidades >= 20 for _, unidades, _ in chamadas)
    assert all(verificacao is False for _, _, verificacao in chamadas)
    assert len(trajetorias) == 2
    for item in trajetorias:
        assert item["verify_every_batch"] is False
        assert item["checkpoints"] == 100
        assert item["tolerance"] == ABS_TOL
        assert 0.0 < item["maximum_difference"] <= ABS_TOL


def test_a_conformidade_reprova_divergencia_acima_da_regua() -> None:
    """Caso negativo obrigatório de F8-1 `M2`: o portão tem dentes.

    A injeção é de `1e-11`, uma ordem acima da régua normativa de `1e-12`, e
    entra no lado da GPU do par, sobre o primeiro checkpoint, que é onde a
    divergência conforme de 1 ulp já aparece. O denominador é medido: o caso
    exige que a perturbação tenha de fato ocorrido e que ela tenha alterado o
    objeto, para que uma injeção que não injetasse nada não passasse por aqui
    como sucesso.
    """

    import metaheuristica_gpu.run as modulo

    injecoes: list[float] = []
    real = modulo.run_aco_gpu

    def perturbado(instance, run, config, **extras):
        resultado = real(instance, run, config, **extras)
        alvo = resultado.checkpoints[0]
        adulterada = replace(
            alvo.evaluation, total_cost=alvo.evaluation.total_cost + 1e-11
        )
        injecoes.append(adulterada.total_cost - alvo.evaluation.total_cost)
        return replace(
            resultado,
            checkpoints=(replace(alvo, evaluation=adulterada),) + resultado.checkpoints[1:],
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "run_aco_gpu", perturbado)
        with pytest.raises(NumericalDivergenceError, match="checkpoint 1: total_cost diverge"):
            modulo.conformance_trajectories(_campanha())

    assert injecoes, "denominador do caso: a injeção tem de ter sido percorrida"
    assert injecoes[0] > ABS_TOL


@lru_cache(maxsize=None)
def _execucao_real(verify_every_batch: bool):
    from metaheuristica_gpu.aco import run_aco_gpu

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    return run_aco_gpu(
        instance,
        RunConfig(k=5, seed=10, budget=200),
        AcoConfig(alpha=1.0, beta=2.0, rho=0.1, n_ants=20),
        verify_every_batch=verify_every_batch,
    )


def test_o_campo_condicional_e_declarado_como_tal_e_a_declaracao_e_verdadeira() -> None:
    """F8-5: a condição do campo passa a viajar junto do valor.

    O campo `max_numerical_difference` só é alimentado dentro do bloco
    `if verify_every_batch:` do avaliador, e a execução oficial usa o padrão
    `False`: ele é estruturalmente `0.0` nas 60 execuções, ao lado de
    checkpoints que de fato divergem em 1 ulp. Declarar a condição não basta:
    o caso mede os **dois modos** e exige que a declaração corresponda ao que
    acontece, e exige também que cada caminho declarado no schema exista de
    fato no documento publicado.
    """

    from metaheuristica_gpu.run import DIAGNOSTICS_SCHEMA

    declarados = DIAGNOSTICS_SCHEMA["conditional_fields"]
    entrada = declarados["result.diagnostics.max_numerical_difference"]
    assert entrada["condition"] == "verify_every_batch"
    assert entrada["value_without_condition"] == 0.0

    oficial = _execucao_real(False)
    verificado = _execucao_real(True)
    assert oficial.diagnostics["max_numerical_difference"] == 0.0
    # Eixo negativo: sob a condição declarada o campo mede alguma coisa, logo o
    # zero do modo oficial vem da condição e não de o campo nunca ter valor.
    assert verificado.diagnostics["max_numerical_difference"] > 0.0
    assert verificado.diagnostics["max_numerical_difference"] <= ABS_TOL
    assert oficial.diagnostics["gpu_timing"]["arbitration_cpu_seconds"] == 0.0

    documento = {"result": oficial.to_dict()}
    for caminho in declarados:
        alvo = documento
        for parte in caminho.split("."):
            assert isinstance(alvo, dict) and parte in alvo, f"{caminho} não existe no documento"
            alvo = alvo[parte]


def test_a_fracao_de_dispositivo_e_publicada_e_coerente_com_o_cronometro() -> None:
    """F8-5, item B3 do Apêndice B: o `speedup` ganha a grandeza que o interpreta.

    `consolidate` descartava `diagnostics.gpu_timing` ao montar
    `gpu_runs.parquet`, publicando `speedup` sem a fração de dispositivo. A
    fração passa a ser derivada por função própria, medida aqui contra as três
    fases do cronômetro de uma execução real e nos dois eixos de recusa.
    """

    from metaheuristica_gpu.run import device_fraction

    resultado = _execucao_real(False)
    cronometro = dict(resultado.diagnostics["gpu_timing"])
    fracao = device_fraction(cronometro, resultado.runtime_seconds)
    esperada = (
        cronometro["host_to_device_seconds"]
        + cronometro["kernel_seconds"]
        + cronometro["device_to_host_seconds"]
    ) / resultado.runtime_seconds
    assert fracao == esperada
    assert 0.0 < fracao < 1.0

    with pytest.raises(GpuStorageError, match="não positivo"):
        device_fraction(cronometro, 0.0)
    with pytest.raises(GpuStorageError, match="sem a fase kernel_seconds"):
        device_fraction({k: v for k, v in cronometro.items() if k != "kernel_seconds"}, 1.0)


def test_o_documento_do_cenario_carrega_o_schema_de_diagnostico() -> None:
    """F8-5: a declaração é publicada no artefato, e não só definida no módulo.

    `execute_scenario` recusa antes de montar documento algum enquanto a
    campanha da CPU não estiver concluída, e a montagem é o que este caso
    precisa medir; por isso ela foi extraída para `scenario_document`. O caso
    prende o **sítio**: sem a chave, a declaração existiria no código e não
    chegaria a quem lê os JSON.
    """

    from metaheuristica_gpu.run import DIAGNOSTICS_SCHEMA, scenario_document
    from metaheuristica_gpu.scenarios import expand_gpu_scenarios

    class _Ambiente:
        def to_dict(self):
            return {"driver": "sintético"}

    cenario = expand_gpu_scenarios(_campanha())[0]
    documento = scenario_document(
        cenario, _execucao_real(False), _Ambiente(), {"warmup_seconds": 0.1},
        cold_total_seconds=1.0, telemetry="results/gpu/telemetry/x.csv",
    )
    assert documento["diagnostics_schema"] == DIAGNOSTICS_SCHEMA
    assert documento["scenario_id"] == cenario.scenario_id
    for caminho in DIAGNOSTICS_SCHEMA["conditional_fields"]:
        alvo = documento
        for parte in caminho.split("."):
            assert isinstance(alvo, dict) and parte in alvo, f"{caminho} ausente"
            alvo = alvo[parte]


def test_a_linha_consolidada_publica_a_fracao_de_dispositivo() -> None:
    """F8-5, item B3: a fração entra na tabela, ao lado do que ela interpreta.

    `consolidate` exige os 60 documentos completos e a tabela oficial da CPU, e
    recusa antes de montar linha alguma; a montagem foi extraída para
    `consolidated_row` justamente para que este caso possa medi-la. Sem ele, a
    função derivada existiria e não seria chamada por ninguém, que é a forma
    exata do código morto que o pacote acabou de remover.
    """

    from metaheuristica_gpu.run import consolidated_row, device_fraction

    resultado = _execucao_real(False)
    documento = {
        "scenario_id": "aco:artesp_rmsp_150:5:s10",
        "scenario": {"algorithm": "aco", "instance": "artesp_rmsp_150", "k": 5, "seed": 10},
        "result": resultado.to_dict(),
    }
    linha = consolidated_row(documento)
    assert linha["device_fraction"] == device_fraction(
        resultado.diagnostics["gpu_timing"], resultado.runtime_seconds
    )
    assert 0.0 < linha["device_fraction"] < 1.0
    assert linha["gpu_runtime_seconds"] == resultado.runtime_seconds
