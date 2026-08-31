from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import traceback
from typing import Callable

import pytest

from experiments.config import load_campaign
from metaheuristica.errors import ConfigurationError


ROOT = Path(__file__).parents[1]
CONFIG_SOURCE = ROOT / "experiments/config.py"
BASE = (ROOT / "experiments/configs/pilot.toml").read_text(encoding="utf-8")
INSTANCE_BLOCK = BASE[BASE.index("[[instances]]") : BASE.index("[algorithms.tabu]")]
ALGORITHM_BLOCK = BASE[BASE.index("[algorithms.tabu]") :]


def _without_instances(text: str) -> str:
    return text.replace(INSTANCE_BLOCK, "")


def _without_algorithms(text: str) -> str:
    return text.replace(ALGORITHM_BLOCK, "")


def _at_root(text: str, line: str) -> str:
    """Insere a linha na seção raiz do TOML, e não dentro da última tabela.

    Acrescentar ao fim do arquivo não põe a chave na raiz: ela cai dentro do
    último cabeçalho, hoje `[algorithms.pso]`. Era o que fazia a versão anterior
    de `test_unknown_root_field_is_rejected`, que dizia recusar campo raiz
    desconhecido e na verdade exercitava a recusa de campo desconhecido do PSO.
    """

    return text.replace("schema_version = 1", f"schema_version = 1\n{line}", 1)


@dataclass(frozen=True, slots=True)
class Refusal:
    """Uma recusa de TOML estrito, com a transformação que a provoca."""

    name: str
    transform: Callable[[str], str]
    message: str


REFUSALS = (
    Refusal(
        "raiz_campo_ausente",
        lambda text: text.replace("cache_enabled = false\n", ""),
        "config: campos ausentes: ['cache_enabled']",
    ),
    Refusal(
        "raiz_campo_desconhecido",
        lambda text: _at_root(text, "desconhecido = 1"),
        "config: campos desconhecidos: ['desconhecido']",
    ),
    Refusal(
        "nome_vazio",
        lambda text: text.replace('name = "pilot_prebenchmark"', 'name = ""'),
        "name: deve ser texto não vazio",
    ),
    Refusal(
        "k_nao_positivo",
        lambda text: text.replace("k_values = [3, 8]", "k_values = [0, 8]", 1),
        "instances[0].k_values[0]: deve ser inteiro positivo",
    ),
    Refusal(
        "k_menor_que_dois",
        lambda text: text.replace("k_values = [3, 8]", "k_values = [1, 8]", 1),
        "instances[0].k_values[0]: K deve ser pelo menos 2",
    ),
    Refusal(
        "orcamento_curto",
        lambda text: text.replace("budget = 20000", "budget = 50", 1),
        "instances[0].budget: orçamento deve permitir 100 checkpoints",
    ),
    Refusal(
        "sementes_vazias",
        lambda text: text.replace("seeds = [20260818]", "seeds = []"),
        "seeds: deve ser lista não vazia",
    ),
    Refusal(
        "sementes_duplicadas",
        lambda text: text.replace("seeds = [20260818]", "seeds = [1, 1]"),
        "seeds: contém valores duplicados",
    ),
    Refusal(
        "semente_nao_inteira",
        lambda text: text.replace("seeds = [20260818]", "seeds = [1.5]"),
        "seeds[0]: deve ser inteiro",
    ),
    Refusal(
        "grade_nao_numerica",
        lambda text: text.replace("tabu_tenure = [10]", 'tabu_tenure = ["dez"]'),
        "algorithms.tabu.tabu_tenure[0]: deve ser numérico",
    ),
    Refusal(
        "toml_invalido",
        lambda text: text.replace('name = "pilot_prebenchmark"', "name = "),
        "TOML inválido: Invalid value (at line 2, column 8)",
    ),
    Refusal(
        "schema_desconhecido",
        lambda text: text.replace("schema_version = 1", "schema_version = 2"),
        "schema_version: versão suportada é 1",
    ),
    Refusal(
        "proposito_desconhecido",
        lambda text: text.replace('purpose = "pilot"', 'purpose = "outro"'),
        "purpose: deve pertencer a ['benchmark', 'pilot', 'tuning']",
    ),
    Refusal(
        "saida_absoluta",
        lambda text: text.replace('output_root = "results"', 'output_root = "/tmp/saida"'),
        "output_root: deve ser relativo à raiz do repositório",
    ),
    Refusal(
        "cache_nao_booleano",
        lambda text: text.replace("cache_enabled = false", "cache_enabled = 1"),
        "cache_enabled: deve ser booleano",
    ),
    Refusal(
        "pesos_nao_tabela",
        lambda text: text.replace(
            "[weights]\ndemand = 0.25\nproduction = 0.25\n"
            "territorial = 0.25\naffinity = 0.25",
            "weights = 1",
        ),
        "weights: deve ser tabela",
    ),
    Refusal(
        "pesos_campo_ausente",
        lambda text: text.replace("affinity = 0.25\n", "", 1),
        "weights: campos ausentes: ['affinity']",
    ),
    Refusal(
        "pesos_campo_desconhecido",
        lambda text: text.replace("affinity = 0.25", "affinity = 0.25\nextra = 0.0", 1),
        "weights: campos desconhecidos: ['extra']",
    ),
    Refusal(
        "pesos_sem_soma_um",
        lambda text: text.replace("demand = 0.25", "demand = 0.50", 1),
        "weights: pesos: a soma deve ser igual a 1",
    ),
    Refusal(
        "saida_fora_da_raiz",
        lambda text: text.replace('output_root = "results"', 'output_root = "../fora"'),
        "output_root: não pode sair da raiz do repositório",
    ),
    Refusal(
        "instancias_vazias",
        lambda text: _at_root(_without_instances(text), "instances = []"),
        "instances: deve ser lista não vazia de tabelas",
    ),
    Refusal(
        "instancia_nao_tabela",
        lambda text: _at_root(_without_instances(text), "instances = [1]"),
        "instances[0]: deve ser tabela",
    ),
    Refusal(
        "instancia_campo_ausente",
        lambda text: text.replace("budget = 20000\n", "", 1),
        "instances[0]: campos ausentes: ['budget']",
    ),
    Refusal(
        "instancia_campo_desconhecido",
        lambda text: text.replace("budget = 20000", "budget = 20000\nextra = 1", 1),
        "instances[0]: campos desconhecidos: ['extra']",
    ),
    Refusal(
        "instancia_nome_duplicado",
        lambda text: text.replace('name = "artesp_rmsp_60"', 'name = "artesp_rmsp_20"'),
        "instances[1].name: duplicado",
    ),
    Refusal(
        "instancia_caminho_absoluto",
        lambda text: text.replace(
            'path = "data/instances/artesp_rmsp_20.json"', 'path = "/etc/hostname"'
        ),
        "instances[0].path: deve ser relativo",
    ),
    Refusal(
        "instancia_caminho_inexistente",
        lambda text: text.replace(
            'path = "data/instances/artesp_rmsp_20.json"',
            'path = "data/instances/inexistente.json"',
        ),
        "instances[0].path: arquivo inexistente ou fora da raiz",
    ),
    Refusal(
        "algoritmos_vazios",
        lambda text: _at_root(_without_algorithms(text), "algorithms = {}"),
        "algorithms: deve ser tabela não vazia",
    ),
    Refusal(
        "algoritmo_desconhecido",
        lambda text: text + "\n[algorithms.xpto]\nfoo = [1]\n",
        "algorithms: desconhecidos: ['xpto']",
    ),
    Refusal(
        "algoritmo_nao_tabela",
        lambda text: _without_algorithms(text) + "[algorithms]\ntabu = 1\n",
        "algorithms.tabu: deve ser tabela",
    ),
    Refusal(
        "algoritmo_campo_ausente",
        lambda text: text.replace("stagnation_limit = [100]\n", "", 1),
        "algorithms.tabu: campos ausentes: ['stagnation_limit']",
    ),
    Refusal(
        "algoritmo_campo_desconhecido",
        lambda text: text.replace(
            "stagnation_limit = [100]", "stagnation_limit = [100]\nextra = [1]", 1
        ),
        "algorithms.tabu: campos desconhecidos: ['extra']",
    ),
    Refusal(
        "grade_multipla_fora_do_tuning",
        lambda text: text.replace("tabu_tenure = [10]", "tabu_tenure = [10, 12]"),
        "algorithms.tabu.tabu_tenure: pilot exige valor único",
    ),
)


def _declared_refusal_sites() -> set[int]:
    """Deriva os sítios de recusa lendo a fonte, e não a suíte.

    Derivação independente da tabela acima: é contra ela que a identidade da
    cobertura é asseverada. Contar por desigualdade não prenderia o conjunto.
    """

    return {
        number
        for number, line in enumerate(
            CONFIG_SOURCE.read_text(encoding="utf-8").splitlines(), start=1
        )
        if line.strip().startswith("raise ConfigurationError")
    }


def _refuse(text: str, target: Path) -> tuple[int, str]:
    """Grava o TOML, exige a recusa e devolve o sítio alcançado e a mensagem."""

    target.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_campaign(target, repository_root=ROOT)
    frame = traceback.extract_tb(caught.value.__traceback__)[-1]
    assert Path(frame.filename) == CONFIG_SOURCE
    assert frame.lineno is not None
    return frame.lineno, str(caught.value)


def test_versioned_pilot_is_strict_and_expands_known_dimensions() -> None:
    config = load_campaign(ROOT / "experiments/configs/pilot.toml")
    assert config.purpose == "pilot"
    assert config.name == "pilot_prebenchmark"
    assert config.seeds == (20260818,)
    assert config.frozen_parameters_sha256 is not None
    assert len(config.instances) == 3
    assert set(config.algorithms) == {"tabu", "aco", "pso"}


def test_missing_configuration_is_explicit(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    with pytest.raises(ConfigurationError) as caught:
        load_campaign(missing)
    assert str(caught.value) == f"configuração inexistente: {missing.resolve()}"


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal.name)
def test_strict_toml_refusals_carry_the_expected_message(
    refusal: Refusal, tmp_path: Path
) -> None:
    """Achado F2-12: uma recusa por caso, com a mensagem asseverada.

    Recusa sem mensagem verificada não distingue uma recusa da outra: um TOML
    mal construído pode parar numa guarda anterior à pretendida e o caso passaria
    do mesmo jeito. Por isso a comparação é de igualdade com a mensagem inteira, e
    não por trecho.
    """

    text = refusal.transform(BASE)
    # Propriedade que torna o caso discriminante, asseverada aqui dentro: a
    # transformação de fato alterou o TOML. Uma substituição que não casasse
    # deixaria o arquivo válido e o caso passaria por vácuo com a recusa errada.
    assert text != BASE

    _line, message = _refuse(text, tmp_path / f"{refusal.name}.toml")
    assert message == refusal.message


def test_every_strict_toml_refusal_site_of_the_loader_is_exercised(
    tmp_path: Path,
) -> None:
    """Achado F2-12, a triagem: os sítios de `experiments/config.py`, todos.

    A auditoria mediu 231 sítios de `ConfigurationError`, 177 nunca acionados, e
    **não** recomenda cobrir os 177 indiscriminadamente. O escopo prescrito são os
    que materializam regra normativa e governam a expansão determinística dos
    1.620 cenários, e a concentração maior está aqui, na leitura estrita do TOML
    de campanha. A asserção é de **identidade** entre o conjunto de sítios que a
    suíte alcança e o conjunto derivado da leitura da fonte: desigualdade sobre um
    conjunto não o prende, e sítio novo de recusa que nasça sem caso derruba este
    teste.
    """

    reached: set[int] = set()
    messages: list[str] = []
    for refusal in REFUSALS:
        text = refusal.transform(BASE)
        assert text != BASE, refusal.name
        line, message = _refuse(text, tmp_path / f"{refusal.name}.toml")
        reached.add(line)
        messages.append(message)

    missing = tmp_path / "missing.toml"
    with pytest.raises(ConfigurationError) as caught:
        load_campaign(missing)
    reached.add(traceback.extract_tb(caught.value.__traceback__)[-1].lineno)

    assert reached == _declared_refusal_sites()
    assert len(reached) == 28
    # Duas recusas distintas com a mesma mensagem seriam indistinguíveis para quem
    # lê a falha, e é exatamente o que a estratégia de teste do pacote proíbe.
    assert len(set(messages)) == len(messages)
