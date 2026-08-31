from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil

import pandas as pd
import pytest

from experiments.config import load_campaign
from experiments.scenarios import (
    ARTESP_DATA_FILES,
    expand_scenarios,
    instance_data_files,
    instance_data_hashes,
    select_scenario,
)
from metaheuristica import InstanceDataError
from metaheuristica.errors import ConfigurationError
from metaheuristica.instances import SUPPORTED_ARTESP_SIZES, load_artesp_instance


ROOT = Path(__file__).parents[1]


def test_diagnostic_pilot_expands_to_54_stably_ordered_scenarios() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml")
    first = expand_scenarios(config)
    second = expand_scenarios(config)
    assert len(first) == 54
    assert first == second
    assert len({scenario.scenario_id for scenario in first}) == 54
    assert len({scenario.filename for scenario in first}) == 54


def test_selection_accepts_full_id_and_unique_prefix() -> None:
    scenarios = expand_scenarios(load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml"))
    expected = scenarios[0]
    assert select_scenario(scenarios, expected.scenario_id) == expected
    assert select_scenario(scenarios, expected.scenario_id[:12]) == expected


def test_selection_rejects_missing_or_ambiguous_id() -> None:
    scenarios = expand_scenarios(load_campaign(ROOT / "experiments/configs/pilot_diagnostic.toml"))
    with pytest.raises(ConfigurationError, match="inexistente"):
        select_scenario(scenarios, "ffffffffffff")
    with pytest.raises(ConfigurationError, match="ambíguo"):
        select_scenario(scenarios, scenarios[0].scenario_id[:1])


def test_output_root_does_not_participate_in_identity() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot.toml")
    changed = replace(config, output_root="another-output")
    assert [item.scenario_id for item in expand_scenarios(config)] == [
        item.scenario_id for item in expand_scenarios(changed)
    ]


def _campaign_with_artesp_20(root: Path) -> Path:
    """Repositório mínimo com a instância de 20 unidades e os dois Parquet."""

    instances = root / "data" / "instances"
    instances.mkdir(parents=True)
    for name in (
        "artesp_rmsp_20.json",
        "artesp_rmsp_150_units.parquet",
        "artesp_rmsp_150_pair_metrics.parquet",
    ):
        shutil.copy2(ROOT / "data" / "instances" / name, instances / name)
    config_path = root / "campaign.toml"
    config_path.write_text(
        "\n".join([
            "schema_version = 1",
            'name = "identidade"',
            'purpose = "pilot"',
            'output_root = "results"',
            "seeds = [1]",
            "cache_enabled = false",
            "",
            "[weights]",
            "demand = 0.25",
            "production = 0.25",
            "territorial = 0.25",
            "affinity = 0.25",
            "",
            "[[instances]]",
            'name = "artesp_rmsp_20"',
            'path = "data/instances/artesp_rmsp_20.json"',
            "budget = 100",
            "k_values = [3]",
            "",
            "[algorithms.tabu]",
            "tabu_tenure = [10]",
            "neighborhood_size = [20]",
            "stagnation_limit = [100]",
        ]) + "\n",
        encoding="utf-8",
    )
    return config_path


def test_identity_covers_the_parquet_that_carry_the_objective_data(tmp_path: Path) -> None:
    """F6-08: o JSON da instância não carrega demanda, produção nem métricas de par.

    Os dois Parquet carregam tudo isso e são abertos por nome literal. Enquanto
    ficaram fora do payload, multiplicar `passengers_day` por 1,5 produzia
    identificador idêntico sobre dados de objetivo diferentes.
    """

    config_path = _campaign_with_artesp_20(tmp_path)
    before = expand_scenarios(load_campaign(config_path, repository_root=tmp_path))

    units_path = tmp_path / "data" / "instances" / "artesp_rmsp_150_units.parquet"
    units = pd.read_parquet(units_path)
    units["passengers_day"] = units["passengers_day"] * 1.5
    units.to_parquet(units_path, index=False)

    after = expand_scenarios(load_campaign(config_path, repository_root=tmp_path))
    assert [item.scenario_id for item in before] != [item.scenario_id for item in after]
    assert [item.filename for item in before] != [item.filename for item in after]
    assert (
        before[0].payload["instance"]["sha256"]
        == after[0].payload["instance"]["sha256"]
    )


def test_identity_of_the_tiny_instance_declares_no_external_data() -> None:
    """A instância manual é autocontida: o mapa de dados externos fica vazio."""

    assert instance_data_files(Path("data/instances/tiny_manual.json")) == ()
    assert instance_data_hashes(ROOT / "data/instances/tiny_manual.json") == {}
    assert [path.name for path in instance_data_files(
        ROOT / "data/instances/artesp_rmsp_60.json"
    )] == [
        "artesp_rmsp_150_units.parquet",
        "artesp_rmsp_150_pair_metrics.parquet",
    ]


def test_missing_parquet_is_refused_instead_of_producing_a_partial_identity(
    tmp_path: Path,
) -> None:
    config_path = _campaign_with_artesp_20(tmp_path)
    (tmp_path / "data" / "instances" / "artesp_rmsp_150_units.parquet").unlink()
    with pytest.raises(ConfigurationError, match="arquivo de dados ausente"):
        expand_scenarios(load_campaign(config_path, repository_root=tmp_path))


def test_the_external_data_map_is_exactly_what_the_loader_opens(tmp_path: Path) -> None:
    """O mapa de dados externos é medido no carregador, não copiado dos nomes dele.

    Cobrir os dois Parquet no identificador só resolve o F6-08 enquanto os dois
    forem mesmo o que `load_artesp_instance` abre à parte do JSON de definição.
    Uma segunda lista de nomes, mantida à mão neste módulo, reintroduziria o
    defeito um nível acima: bastaria o carregador passar a abrir um terceiro
    arquivo para o identificador voltar a ignorar dados do objetivo. Este caso
    prende os dois lados, por tamanho suportado, contra o comportamento do
    carregador. **Suficiência:** um diretório com o JSON de definição e apenas os
    arquivos declarados basta para carregar, logo não há arquivo esquecido.
    **Necessidade:** esconder qualquer um dos declarados faz o carregamento
    reprovar, logo não há arquivo declarado a mais.
    """

    for size in SUPPORTED_ARTESP_SIZES:
        definition = f"artesp_rmsp_{size}.json"
        declared = [
            path.name
            for path in instance_data_files(ROOT / "data" / "instances" / definition)
        ]
        assert declared == list(ARTESP_DATA_FILES)

        directory = tmp_path / f"tamanho_{size}"
        directory.mkdir()
        for name in (definition, *declared):
            shutil.copy2(ROOT / "data" / "instances" / name, directory / name)
        assert load_artesp_instance(directory, size).n_units == size

        for name in declared:
            present = directory / name
            hidden = directory / f"{name}.oculto"
            present.rename(hidden)
            with pytest.raises(InstanceDataError):
                load_artesp_instance(directory, size)
            hidden.rename(present)


def test_a_size_the_loader_refuses_declares_no_external_data() -> None:
    """Eixo negativo: o mapa não reconhece definição que o carregador não aceita."""

    assert 10 not in SUPPORTED_ARTESP_SIZES
    assert instance_data_files(Path("data/instances/artesp_rmsp_10.json")) == ()
    with pytest.raises(InstanceDataError, match="não suportado"):
        load_artesp_instance(ROOT / "data" / "instances", 10)
