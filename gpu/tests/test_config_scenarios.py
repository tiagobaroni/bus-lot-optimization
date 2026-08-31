from pathlib import Path

import pytest

from metaheuristica_gpu.config import GpuConfigError, load_gpu_config
from metaheuristica_gpu.scenarios import expand_gpu_scenarios


ROOT = Path(__file__).parents[2]


def test_official_gpu_campaign_expands_60_isolated_ids() -> None:
    config = load_gpu_config(ROOT / "gpu/configs/gpu_benchmark.toml")
    scenarios = expand_gpu_scenarios(config)
    assert len(scenarios) == 60
    assert len({item.scenario_id for item in scenarios}) == 60
    assert {item.payload["algorithm"] for item in scenarios} == {"aco", "pso"}
    assert {item.payload["seed"] for item in scenarios} == set(range(10, 40))
    assert {item.payload["k"] for item in scenarios} == {5}
    assert {item.payload["precision"] for item in scenarios} == {"float64"}


def _toml_da_campanha() -> str:
    return (ROOT / "gpu/configs/gpu_benchmark.toml").read_text(encoding="utf-8")


def test_o_teto_do_carregador_e_o_teto_que_o_objetivo_aplica() -> None:
    """F8-9: a duplicação do literal fica presa, em vez de ficar silenciosa.

    O teto vive como literal em `gpu/src/metaheuristica_gpu/objective.py`, que
    não pertence à lista de arquivos deste pacote, e por isso não pôde ser
    retirado de lá e importado do carregador. O caso mede o teto **pelo
    comportamento** do objetivo em lote, e não por leitura de constante: com
    `BATCH_CEILING` candidatos o lote é aceito, e com um a mais é recusado. Se
    um dos dois lados mudar sozinho, o caso reprova.
    """

    import numpy as np

    from metaheuristica import load_artesp_instance
    from metaheuristica_gpu.config import BATCH_CEILING
    from metaheuristica_gpu.objective import GpuBatchObjective, GpuObjectiveError

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    with GpuBatchObjective(instance, k=5) as objective:
        no_teto = np.stack([
            np.roll(np.arange(20, dtype=np.int64) % 5, shift) % 5
            for shift in range(BATCH_CEILING)
        ])
        assert len(objective.evaluate(no_teto)) == BATCH_CEILING
        acima = np.stack([no_teto[index % BATCH_CEILING] for index in range(BATCH_CEILING + 1)])
        with pytest.raises(GpuObjectiveError, match="lote deve conter"):
            objective.evaluate(acima)


@pytest.mark.parametrize(
    "campo, valor, recusa",
    [
        ("n_ants", 41, True),
        ("n_particles", 41, True),
        ("n_ants", 40, False),
        ("n_particles", 40, False),
    ],
)
def test_a_populacao_e_cruzada_contra_o_teto_de_lote(
    tmp_path, campo: str, valor: int, recusa: bool
) -> None:
    """F8-9: `n_ants` e `n_particles` passam a ser conferidos no carregamento.

    Antes deste caso o carregador validava schema, backend, precisão, seeds e
    algoritmos e **não** comparava os dois valores contra o teto de lote, de
    modo que a campanha operava colada no limite com folga zero: um ciclo de
    tuning que subisse a população para 41 seria aceito no carregamento e só
    falharia na primeira avaliação, com a sessão gravada como `interrupted`.

    O eixo negativo, com o valor 40, está aqui dentro: sem ele uma recusa
    incondicional passaria nos dois primeiros casos.
    """

    texto = _toml_da_campanha()
    original = f"{campo} = 40"
    assert original in texto, "denominador do caso: a campanha usa exatamente 40"
    alterado = texto.replace(original, f"{campo} = {valor}")
    assert (alterado != texto) == (valor != 40)
    caminho = tmp_path / "campanha.toml"
    caminho.write_text(alterado, encoding="utf-8")

    if recusa:
        with pytest.raises(GpuConfigError, match=f"{campo} = {valor} excede o teto"):
            load_gpu_config(caminho, repository_root=ROOT)
    else:
        config = load_gpu_config(caminho, repository_root=ROOT)
        assert (config.aco.n_ants, config.pso.n_particles) == (40, 40)
