"""Um único critério de aptidão térmica, avaliado num único sítio.

Enquanto havia dois, o do fim da execução devolvia na primeira amostra dentro do
limiar e o da entrada exigia a janela inteira: a saída de um não implicava a
entrada do outro, e toda transição encadeada começava com margem nula.

A defesa não é mantê-los em dia, é não haver dois. A propriedade abaixo é
derivada da **definição** — quais funções decidem lendo o limiar — e não dos
nomes do código, para que renomear o segundo critério não a burle.
"""

import inspect

from metaheuristica_gpu import monitor
from metaheuristica_gpu import run as run_module

IMPORTADOS_DE_MONITOR = {
    "GpuSample", "monitor_process", "preflight_idle", "write_samples_csv",
}


def _funcoes_que_leem(modulo, constante: str) -> set[str]:
    return {
        nome for nome, objeto in vars(modulo).items()
        if inspect.isfunction(objeto)
        and getattr(objeto, "__module__", None) == modulo.__name__
        and constante in inspect.getsource(objeto)
    }


def test_um_unico_sitio_decide_a_aptidao_termica() -> None:
    leitoras = _funcoes_que_leem(monitor, "GPU_TEMPERATURE_LIMIT_C")
    # Igualdade exata é o próprio anti-vácuo: não-vazia prova que a varredura
    # enxerga o código, e não-maior prova que não há segundo critério. Uma
    # função rebatizada que decidisse aptidão também leria a constante, e o
    # conjunto iria a dois elementos.
    assert leitoras == {"preflight_idle"}


def test_a_orquestracao_nao_decide_aptidao_termica() -> None:
    assert _funcoes_que_leem(run_module, "GPU_TEMPERATURE_LIMIT_C") == set()


def test_a_orquestracao_importa_do_monitor_exatamente_o_previsto() -> None:
    """Um segundo critério teria de entrar por aqui para ser chamado."""
    presentes = {
        nome for nome in IMPORTADOS_DE_MONITOR | {"cooldown"}
        if hasattr(run_module, nome)
    }
    assert presentes == IMPORTADOS_DE_MONITOR
