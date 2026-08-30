import csv
from dataclasses import fields, replace
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


def test_preflight_accepts_idle_and_rejects_heat_or_competitor() -> None:
    assert len(preflight_idle(duration_seconds=3, provider=lambda: BASE, sleeper=lambda _: None)) == 3
    with pytest.raises(GpuSafetyError, match="temperatura"):
        preflight_idle(duration_seconds=1, provider=lambda: replace(BASE, temperature_c=51))
    with pytest.raises(GpuSafetyError, match="processo"):
        preflight_idle(duration_seconds=1, provider=lambda: replace(BASE, external_processes=1))


# --- F8-6. Os dois limiares de temperatura -----------------------------------


def _preflight_aceita(temperatura: int) -> bool:
    """Verdadeiro quando o preflight aceita uma placa nessa temperatura."""
    try:
        preflight_idle(
            duration_seconds=1,
            provider=lambda: replace(BASE, temperature_c=temperatura),
            sleeper=lambda _: None,
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
