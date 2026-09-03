import csv
from dataclasses import fields, replace
from itertools import cycle
import multiprocessing.synchronize
import os
import signal
import subprocess
import time

import pytest

from metaheuristica_gpu import monitor
from metaheuristica_gpu.monitor import (
    GpuSafetyError,
    GpuSafetyMonitor,
    GpuSample,
    ThermalInterruption,
    cooldown,
    preflight_idle,
)


BASE = GpuSample(
    0.0, 40, 0.0, 0.0, 100, 12288, 20.0, 200, 400,
    monitor.THROTTLING_INACTIVE, monitor.THROTTLING_INACTIVE, 0,
)


def test_preflight_accepts_idle_and_rejects_competitor() -> None:
    assert len(preflight_idle(duration_seconds=3, provider=lambda: BASE,
                              sleeper=lambda _: None, monotonic=lambda: 0.0)) == 3
    with pytest.raises(GpuSafetyError, match="processo"):
        preflight_idle(duration_seconds=1, provider=lambda: replace(BASE, external_processes=1))


# --- F8-6. Os dois limiares de temperatura -----------------------------------


def _preflight_aceita(temperatura: int) -> bool:
    """Verdadeiro quando o preflight aceita uma placa nessa temperatura."""
    try:
        preflight_idle(
            duration_seconds=1, timeout_seconds=0,
            provider=lambda: replace(BASE, temperature_c=temperatura),
            sleeper=lambda _: None, monotonic=lambda: 0.0,
        )
    except GpuSafetyError:
        return False
    return True


def _cooldown_libera(temperatura: int) -> bool:
    """Verdadeiro quando o resfriamento devolve já na primeira amostra."""
    tomadas: list[int] = []

    def provider() -> GpuSample:
        tomadas.append(1)
        return replace(BASE, temperature_c=temperatura if len(tomadas) == 1 else 0)

    return len(cooldown(provider=provider, sleeper=lambda _: None)) == 1


def test_preflight_e_resfriamento_aceitam_exatamente_o_mesmo_conjunto() -> None:
    """Identidade de conjunto, e não desigualdade: uma asserção de limiar sobre um
    dos dois lados passaria mesmo com a faixa de cinco graus em que o resfriamento
    libera e o preflight recusa."""
    faixa = range(30, 81)
    aceitas_pelo_preflight = {t for t in faixa if _preflight_aceita(t)}
    liberadas_pelo_resfriamento = {t for t in faixa if _cooldown_libera(t)}
    assert aceitas_pelo_preflight == liberadas_pelo_resfriamento
    assert aceitas_pelo_preflight, "o conjunto precisa discriminar, e não ficar vazio"
    assert aceitas_pelo_preflight != set(faixa), "o conjunto precisa discriminar"


def test_os_dois_limiares_vem_de_uma_unica_constante(monkeypatch) -> None:
    limite = monitor.GPU_TEMPERATURE_LIMIT_C
    assert _preflight_aceita(limite) and not _preflight_aceita(limite + 1)
    assert _cooldown_libera(limite) and not _cooldown_libera(limite + 1)
    monkeypatch.setattr(monitor, "GPU_TEMPERATURE_LIMIT_C", limite - 7)
    assert not _preflight_aceita(limite) and not _cooldown_libera(limite)
    assert _preflight_aceita(limite - 7) and _cooldown_libera(limite - 7)


# --- F8-7. Telemetria perdida na falha de segurança ---------------------------


def test_csv_gravado_quando_a_primeira_amostra_reprova(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    amostra = replace(BASE, external_processes=1)
    with pytest.raises(GpuSafetyError, match="processo"):
        with GpuSafetyMonitor(caminho, provider=lambda: amostra, interval_seconds=10.0):
            pass
    assert caminho.is_file()
    linhas = list(csv.DictReader(caminho.read_text(encoding="utf-8").splitlines()))
    assert len(linhas) == 1
    assert int(linhas[0]["external_processes"]) == 1


def test_csv_gravado_com_cabecalho_quando_a_telemetria_some(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"

    def provider() -> GpuSample:
        raise GpuSafetyError("telemetria NVIDIA indisponível")

    with pytest.raises(GpuSafetyError, match="telemetria NVIDIA indisponível"):
        with GpuSafetyMonitor(caminho, provider=provider, interval_seconds=10.0):
            pass
    assert caminho.is_file()
    assert caminho.read_text(encoding="utf-8").splitlines() == [
        ",".join(campo.name for campo in fields(GpuSample))
    ]


# --- F8-8. Valor desconhecido de throttling -----------------------------------


@pytest.mark.parametrize("texto", ["Not Active", "not active", "no", "0", "n/a"])
def test_textos_reconhecidos_como_inativos(texto: str) -> None:
    assert monitor.throttling_state(texto) == monitor.THROTTLING_INACTIVE


@pytest.mark.parametrize("texto", ["Active", "active", "yes", "1"])
def test_textos_reconhecidos_como_ativos(texto: str) -> None:
    assert monitor.throttling_state(texto) == monitor.THROTTLING_ACTIVE


@pytest.mark.parametrize("texto", ["[N/A]", "[Not Supported]", "", "qualquer coisa"])
def test_texto_desconhecido_e_categoria_propria(texto: str) -> None:
    estado = monitor.throttling_state(texto)
    assert estado == monitor.THROTTLING_UNKNOWN
    assert estado != monitor.THROTTLING_ACTIVE
    assert estado != monitor.THROTTLING_INACTIVE


def test_desconhecido_nao_interrompe_por_padrao(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    amostra = replace(
        BASE,
        software_thermal_slowdown=monitor.THROTTLING_UNKNOWN,
        hardware_thermal_slowdown=monitor.THROTTLING_UNKNOWN,
    )
    with GpuSafetyMonitor(caminho, provider=lambda: amostra, interval_seconds=10.0):
        pass
    assert caminho.is_file()


def test_desconhecido_interrompe_quando_a_politica_exige(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    amostra = replace(BASE, software_thermal_slowdown=monitor.THROTTLING_UNKNOWN)
    with pytest.raises(ThermalInterruption, match="telemetria de throttling incompleta"):
        with GpuSafetyMonitor(
            caminho, provider=lambda: amostra, interval_seconds=10.0,
            require_known_throttling=True,
        ):
            pass


def test_throttling_ativo_continua_interrompendo(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    amostra = replace(BASE, hardware_thermal_slowdown=monitor.THROTTLING_ACTIVE)
    with pytest.raises(ThermalInterruption, match="throttling térmico"):
        with GpuSafetyMonitor(caminho, provider=lambda: amostra, interval_seconds=10.0):
            pass


# --- F8-11. O monitor fora do processo cronometrado ---------------------------


class ProvedorDeAmostras:
    """Provedor picklável: roda no processo do monitor e registra onde rodou.

    Guarda o identificador do processo em `memory_used_mib` e o número acumulado
    de subprocessos que ele mesmo disparou em `memory_total_mib`, que são os dois
    campos inteiros livres da amostra.
    """

    def __init__(
        self, *, subprocessos_por_amostra: int = 0,
        inseguro_a_partir_de: int | None = None, travar_a_partir_de: int | None = None,
    ) -> None:
        self.subprocessos_por_amostra = subprocessos_por_amostra
        self.inseguro_a_partir_de = inseguro_a_partir_de
        self.travar_a_partir_de = travar_a_partir_de
        self.amostras = 0
        self.chamadas = 0

    def __call__(self) -> GpuSample:
        self.amostras += 1
        for _ in range(self.subprocessos_por_amostra):
            subprocess.run(["/bin/true"], check=True, capture_output=True, timeout=10)
            self.chamadas += 1
        if self.travar_a_partir_de is not None and self.amostras >= self.travar_a_partir_de:
            time.sleep(600)
        externos = int(
            self.inseguro_a_partir_de is not None
            and self.amostras >= self.inseguro_a_partir_de
        )
        return replace(
            BASE, monotonic_seconds=float(self.amostras), memory_used_mib=os.getpid(),
            memory_total_mib=self.chamadas, external_processes=externos,
        )


def test_monitor_nao_roda_no_processo_cronometrado(tmp_path, monkeypatch) -> None:
    caminho = tmp_path / "telemetria.csv"
    provedor = ProvedorDeAmostras(subprocessos_por_amostra=2)
    chamadas_no_pai: list[object] = []
    original = subprocess.run

    def contando(*args, **kwargs):
        chamadas_no_pai.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(monitor.subprocess, "run", contando)
    with monitor.monitor_process(caminho, interval_seconds=0.02, provider=provedor) as guarda:
        assert guarda.pid != os.getpid()
        limite = time.monotonic() + 1.0
        while time.monotonic() < limite:
            guarda.guard()
            time.sleep(0.005)
    guarda.raise_if_unsafe()
    assert chamadas_no_pai == []
    assert len(guarda.samples) >= 2, "sem amostra, a asserção de zero chamadas seria vazia"
    assert {amostra.memory_used_mib for amostra in guarda.samples} == {guarda.pid}
    assert os.getpid() not in {amostra.memory_used_mib for amostra in guarda.samples}
    assert max(amostra.memory_total_mib for amostra in guarda.samples) >= 2


def test_aborto_chega_na_amostra_que_o_detecta(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    provedor = ProvedorDeAmostras(inseguro_a_partir_de=3)
    with pytest.raises(ThermalInterruption, match="processo"):
        with monitor.monitor_process(caminho, interval_seconds=0.02, provider=provedor) as guarda:
            limite = time.monotonic() + 30.0
            while time.monotonic() < limite:
                guarda.guard()
                time.sleep(0.002)
            raise AssertionError("o monitor não abortou dentro de 30 segundos")
    assert len(guarda.samples) == 3
    assert [amostra.external_processes for amostra in guarda.samples] == [0, 0, 1]


def test_csv_gravado_quando_o_filho_morre(tmp_path) -> None:
    caminho = tmp_path / "telemetria.csv"
    provedor = ProvedorDeAmostras()
    with monitor.monitor_process(caminho, interval_seconds=0.02, provider=provedor) as guarda:
        limite = time.monotonic() + 30.0
        while len(guarda.samples) < 2 and time.monotonic() < limite:
            guarda.guard()
            time.sleep(0.005)
        guarda.guard()
        assert len(guarda.samples) >= 2
        os.kill(guarda.pid, signal.SIGKILL)
        guarda.process.join(10.0)
        assert not guarda.process.is_alive()
        assert not caminho.exists(), "o filho morto não pode ter gravado o arquivo"
    assert caminho.is_file()
    linhas = list(csv.DictReader(caminho.read_text(encoding="utf-8").splitlines()))
    assert len(linhas) >= 2
    assert {int(linha["memory_used_mib"]) for linha in linhas} == {guarda.pid}


class _SaidaFalsa:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def _nvidia_smi_falso(pids: tuple[int, ...]):
    linha = "40, 0, 0, 100, 12288, 20.0, 200, 400, Not Active, Not Active"
    processos = "".join(f"{pid}, python\n" for pid in pids)

    def executar(command, **kwargs):
        if "--query-compute-apps=pid,process_name" in command:
            return _SaidaFalsa(processos)
        return _SaidaFalsa(linha)

    return executar


def test_amostragem_no_filho_nao_conta_o_processo_medido_como_externo(monkeypatch) -> None:
    """O monitor mudou de processo, e `os.getpid()` deixou de ser o processo que
    segura o contexto da placa: sem o dono explícito, a primeira amostra de toda
    execução acusaria o processo medido como concorrente e derrubaria os 60
    cenários."""
    medido, monitorando, alheio = 4242, 4243, 4244
    monkeypatch.setattr(monitor.subprocess, "run", _nvidia_smi_falso((medido,)))
    monkeypatch.setattr(monitor.os, "getpid", lambda: monitorando)
    assert monitor.query_sample().external_processes == 1
    assert monitor.query_sample(owner_pid=medido).external_processes == 0
    assert monitor.query_sample(owner_pid=monitorando).external_processes == 1
    # E quem amostra não é concorrente de si mesmo: com os dois processos
    # listados, só o de fora conta.
    monkeypatch.setattr(
        monitor.subprocess, "run", _nvidia_smi_falso((medido, monitorando))
    )
    assert monitor.query_sample(owner_pid=medido).external_processes == 0
    monkeypatch.setattr(
        monitor.subprocess, "run", _nvidia_smi_falso((medido, monitorando, alheio))
    )
    assert monitor.query_sample(owner_pid=medido).external_processes == 1


def test_o_monitor_em_processo_proprio_declara_o_processo_medido_como_dono(tmp_path) -> None:
    """Regressão da armadilha acima pelo caminho integrado: o gerente de contexto
    tem de passar o identificador do processo que ele envolve, e não deixar o
    filho tomar o próprio."""
    caminho = tmp_path / "telemetria.csv"
    with monitor.monitor_process(caminho, interval_seconds=0.02) as guarda:
        assert guarda.owner_pid == os.getpid()
        assert guarda.owner_pid != guarda.pid


def _primitivas_com_trava(raiz: object, profundidade: int = 4) -> list[object]:
    """Coleta, no grafo de atributos alcançável a partir de `raiz`, os objetos que
    guardam semáforo entre processos.

    A expectativa é derivada da definição de "sem trava", isto é da ausência de
    qualquer `SemLock` no caminho, e não dos nomes que o monitor escolheu para os
    seus atributos: uma reimplementação com outro nome continua sendo pega.
    """
    encontrados: list[object] = []
    vistos: set[int] = set()

    def visitar(atual: object, resta: int) -> None:
        if resta < 0 or id(atual) in vistos:
            return
        vistos.add(id(atual))
        if isinstance(atual, multiprocessing.synchronize.SemLock):
            encontrados.append(atual)
        for valor in vars(atual).values() if hasattr(atual, "__dict__") else ():
            visitar(valor, resta - 1)

    visitar(raiz, profundidade)
    return encontrados


def test_o_canal_de_parada_nao_guarda_semaforo_entre_processos(tmp_path) -> None:
    """O filho morto enquanto segura um semáforo compartilhado trava para sempre
    quem o consultar depois, e quem consulta é o laço cronometrado, por `guard`.

    Este caso prende a *identidade* da primitiva, e não o travamento em si: o
    travamento só ocorre quando a morte cai dentro da seção crítica, que é uma
    janela de microssegundos, e um caso comportamental para ele seria
    probabilístico. Sem este caso, trocar os dois canais de volta por
    `multiprocessing.Event` deixa a suíte inteira verde.
    """
    # Prova de que a busca acha o que diz achar. Sem esta metade, um erro na
    # varredura faria as asserções abaixo passarem por vácuo.
    evento = multiprocessing.get_context("spawn").Event()
    assert _primitivas_com_trava(evento), "a varredura não acha o semáforo de um Event"

    caminho = tmp_path / "telemetria.csv"
    with monitor.monitor_process(caminho, interval_seconds=0.02) as guarda:
        canais = (guarda.abort_event, guarda.stop_event)
        for canal in canais:
            assert isinstance(canal, monitor.SharedFlag)
            assert not _primitivas_com_trava(canal), f"{canal!r} guarda semáforo"
        # E o canal continua sendo um canal: sinaliza e é lido de volta.
        assert not guarda.stop_event.is_set()
        guarda.stop_event.set()
        assert guarda.stop_event.is_set()


# --- B11F. Portão térmico único na entrada ------------------------------------

_MAX_AMOSTRAS = 5000


def _serie(temperaturas: list[int]):
    """Percorre a série e depois repete o último valor.

    A contagem máxima existe porque, com a espera térmica, várias mutações
    plausíveis não reprovam: elas deixam de terminar. Sem esta guarda a suíte
    pendura em vez de acusar.
    """
    restantes = list(temperaturas)
    ultimo = temperaturas[-1]
    tomadas = [0]

    def provider() -> GpuSample:
        tomadas[0] += 1
        assert tomadas[0] <= _MAX_AMOSTRAS, "provider consultado além do limite: laço sem saída"
        return replace(BASE, temperature_c=restantes.pop(0) if restantes else ultimo)

    return provider


def _oscila(temperaturas: list[int]):
    """Oscila indefinidamente, sem degenerar em série constante."""
    ciclo = cycle(temperaturas)
    tomadas = [0]

    def provider() -> GpuSample:
        tomadas[0] += 1
        assert tomadas[0] <= _MAX_AMOSTRAS, "provider consultado além do limite: laço sem saída"
        return replace(BASE, temperature_c=next(ciclo))

    return provider


class _Relogio:
    """Relógio determinístico: cada chamada do sleeper avança o tempo pedido."""

    def __init__(self) -> None:
        self.agora = 0.0

    def monotonic(self) -> float:
        return self.agora

    def sleeper(self, segundos: float) -> None:
        self.agora += segundos


def test_preflight_aguarda_placa_quente_e_aprova() -> None:
    relogio = _Relogio()
    amostras = preflight_idle(
        duration_seconds=5, provider=_serie([55, 54, 52, 51] + [48] * 5),
        sleeper=relogio.sleeper, monotonic=relogio.monotonic,
    )
    lidas = [item.temperature_c for item in amostras]
    # Anti-vácuo: a série cruzou o limiar de verdade, e a contagem é exata.
    assert max(lidas) > monitor.GPU_TEMPERATURE_LIMIT_C
    assert min(lidas) <= monitor.GPU_TEMPERATURE_LIMIT_C
    assert len(lidas) == 9


def test_preflight_esgota_o_teto_quando_a_placa_nunca_esfria() -> None:
    relogio = _Relogio()
    with pytest.raises(monitor.ThermalWaitTimeout) as capturado:
        preflight_idle(
            duration_seconds=5, timeout_seconds=30, provider=_serie([90, 70]),
            sleeper=relogio.sleeper, monotonic=relogio.monotonic,
        )
    mensagem = str(capturado.value)
    # Anti-vácuo: houve espera, e a mensagem reporta a ÚLTIMA leitura, não a
    # primeira nem um literal fixo. Com provider constante isso não se veria.
    assert relogio.agora >= 30
    assert "70" in mensagem and "90" not in mensagem


def test_preflight_esgota_o_teto_sob_oscilacao_em_torno_do_limiar() -> None:
    """O teto cobre o tempo TOTAL no preflight, não apenas a descida inicial."""
    relogio = _Relogio()
    limite = monitor.GPU_TEMPERATURE_LIMIT_C
    coletadas: list[GpuSample] = []
    with pytest.raises(monitor.ThermalWaitTimeout):
        preflight_idle(
            duration_seconds=5, timeout_seconds=40,
            provider=_oscila([limite, limite + 1]),
            sleeper=relogio.sleeper, monotonic=relogio.monotonic,
            sink=coletadas.append,
        )
    # Anti-vácuo dentro do caso, e não no comentário: o limite SUPERIOR mata a
    # mutação que reinicia o cronômetro a cada progresso, e a contagem de
    # amostras frias prova que a placa atingiu o limiar muitas vezes e mesmo
    # assim não aprovou — que é a propriedade que o caso promete.
    assert 40 <= relogio.agora <= 42
    assert sum(1 for item in coletadas if item.temperature_c <= limite) > 5


def test_preflight_nao_aguarda_quando_ha_processo_externo() -> None:
    """A espera é exclusiva da temperatura."""
    relogio = _Relogio()
    coletadas: list[GpuSample] = []
    quente_e_ocupada = replace(BASE, temperature_c=70, external_processes=1)
    with pytest.raises(GpuSafetyError, match="processo"):
        preflight_idle(
            duration_seconds=5, timeout_seconds=600,
            provider=lambda: quente_e_ocupada, sleeper=relogio.sleeper,
            monotonic=relogio.monotonic, sink=coletadas.append,
        )
    # Anti-vácuo: recusou sem consumir espera, e a amostra que motivou a recusa
    # chegou ao sink antes do levantamento.
    assert relogio.agora == 0
    assert len(coletadas) == 1 and coletadas[0].external_processes == 1


def test_preflight_reinicia_a_janela_inteira_quando_a_placa_volta_a_subir() -> None:
    """Contagem EXATA. Um `>` frouxo passa com reinício, com janela cumulativa e
    com decaimento parcial."""
    relogio = _Relogio()
    limite = monitor.GPU_TEMPERATURE_LIMIT_C
    amostras = preflight_idle(
        duration_seconds=5,
        provider=_serie([limite - 1, limite - 1, limite + 5] + [limite - 1] * 5),
        sleeper=relogio.sleeper, monotonic=relogio.monotonic,
    )
    # Reinício integral: 2 frias descartadas + 1 quente + 5 frias = 8.
    # Decaimento por pop() daria 7; janela cumulativa daria 6.
    assert len(amostras) == 8
    assert any(item.temperature_c > limite for item in amostras)


def test_preflight_recusa_utilizacao_media_alta_sem_aguardar() -> None:
    relogio = _Relogio()
    ocupada = replace(BASE, temperature_c=40, gpu_utilization_percent=42.0)
    with pytest.raises(GpuSafetyError, match="utilização"):
        preflight_idle(
            duration_seconds=3, provider=lambda: ocupada,
            sleeper=relogio.sleeper, monotonic=relogio.monotonic,
        )
    # Anti-vácuo: a recusa veio depois da janela completa, e não de espera.
    assert relogio.agora == 2


def test_preflight_entrega_todas_as_amostras_ao_sink() -> None:
    relogio = _Relogio()
    recebidas: list[GpuSample] = []
    preflight_idle(
        duration_seconds=3, provider=_serie([55, 48, 48, 48]),
        sleeper=relogio.sleeper, monotonic=relogio.monotonic,
        sink=recebidas.append,
    )
    # Igualdade exata: mata a mutação "só entrega as amostras da janela".
    assert [item.temperature_c for item in recebidas] == [55, 48, 48, 48]


def test_o_teto_vem_de_uma_unica_constante(monkeypatch) -> None:
    """Um literal 1200 no corpo sobreviveria a todos os casos acima, porque
    todos passam `timeout_seconds` explícito."""
    monkeypatch.setattr(monitor, "GPU_THERMAL_WAIT_TIMEOUT_S", 5)
    relogio = _Relogio()
    with pytest.raises(monitor.ThermalWaitTimeout):
        preflight_idle(
            duration_seconds=5, provider=_serie([70]),
            sleeper=relogio.sleeper, monotonic=relogio.monotonic,
        )
    assert 5 <= relogio.agora <= 6
