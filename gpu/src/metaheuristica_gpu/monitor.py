"""Telemetria, exclusividade e proteção térmica da B11A."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from functools import partial
import multiprocessing
import os
from pathlib import Path
import queue as queue_module
import subprocess
import threading
import time
from typing import Any, Callable, Iterator


class GpuSafetyError(RuntimeError):
    pass


class ThermalInterruption(GpuSafetyError):
    pass


class ThermalWaitTimeout(GpuSafetyError):
    pass


# Havia dois sítios lendo este limiar, o preflight e um resfriamento no fim da
# execução, e o segundo devolvia na primeira amostra dentro do limiar enquanto o
# primeiro exigia a janela inteira: a saída de um não implicava a entrada do
# outro, e toda transição encadeada começava com margem nula. A defesa não é
# manter os dois em dia, é existir um único critério, num único sítio.
GPU_TEMPERATURE_LIMIT_C = 50

# Teto sobre o tempo TOTAL dentro do preflight, espera e janela sustentada
# incluídas. Não decide se a placa está apta, apenas por quanto tempo se admite
# aguardar, e por isso não é um segundo critério de aceitação.
GPU_THERMAL_WAIT_TIMEOUT_S = 1200

THROTTLING_ACTIVE = "active"
THROTTLING_INACTIVE = "inactive"
THROTTLING_UNKNOWN = "unknown"

_THROTTLING_INACTIVE_TEXTS = frozenset({"not active", "no", "0", "n/a"})
_THROTTLING_ACTIVE_TEXTS = frozenset({"active", "yes", "1"})


def throttling_state(value: str) -> str:
    """Três categorias, e não duas. `nvidia-smi` devolve `[N/A]`, com colchetes,
    quando o contador não é suportado, e ler isso como throttling ativo trocava
    ausência de informação por evento térmico observado."""
    text = value.strip().lower()
    if text in _THROTTLING_INACTIVE_TEXTS:
        return THROTTLING_INACTIVE
    if text in _THROTTLING_ACTIVE_TEXTS:
        return THROTTLING_ACTIVE
    return THROTTLING_UNKNOWN


@dataclass(frozen=True, slots=True)
class GpuSample:
    monotonic_seconds: float
    temperature_c: int
    gpu_utilization_percent: float
    memory_utilization_percent: float
    memory_used_mib: int
    memory_total_mib: int
    power_w: float
    sm_clock_mhz: int
    memory_clock_mhz: int
    software_thermal_slowdown: str
    hardware_thermal_slowdown: str
    external_processes: int


def query_sample(owner_pid: int | None = None) -> GpuSample:
    """`owner_pid` é o processo que legitimamente segura a placa. Ele existe
    porque o monitor deixou de rodar dentro do processo medido: sem declarar o
    dono, o processo que executa a otimização passa a ser contado como
    concorrente já na primeira amostra de todos os cenários.

    Quem amostra também nunca é concorrente de si mesmo, e por isso o próprio
    processo continua excluído junto do dono declarado. Enquanto o monitor
    rodava dentro do processo medido os dois eram o mesmo, e a exclusão única
    bastava; separados, deixar de excluir o processo que amostra reabriria o
    mesmo defeito uma casa adiante.
    """
    owners = {os.getpid()} if owner_pid is None else {os.getpid(), owner_pid}
    fields_queried = (
        "temperature.gpu", "utilization.gpu", "utilization.memory", "memory.used",
        "memory.total", "power.draw", "clocks.sm", "clocks.mem",
        "clocks_event_reasons.sw_thermal_slowdown",
        "clocks_event_reasons.hw_thermal_slowdown",
    )
    command = ["nvidia-smi", f"--query-gpu={','.join(fields_queried)}", "--format=csv,noheader,nounits"]
    try:
        output = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5).stdout.strip()
        values = [item.strip() for item in output.split(",")]
        process_output = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise GpuSafetyError("telemetria NVIDIA indisponível") from error
    if len(values) != len(fields_queried):
        raise GpuSafetyError("amostra NVIDIA incompleta")
    external = 0
    for line in process_output.splitlines():
        if not line.strip():
            continue
        try:
            pid = int(line.split(",", 1)[0].strip())
        except ValueError:
            external += 1
        else:
            external += int(pid not in owners)
    return GpuSample(
        time.monotonic(), int(values[0]), float(values[1]), float(values[2]),
        int(values[3]), int(values[4]), float(values[5]), int(values[6]), int(values[7]),
        throttling_state(values[8]), throttling_state(values[9]), external,
    )


def write_samples_csv(path: Path, samples: list[GpuSample]) -> None:
    """Os nomes das colunas vêm da própria estrutura da amostra, e não da
    primeira amostra coletada: uma falha antes da primeira amostra tem de deixar
    o arquivo em disco, com cabeçalho, sem mascarar o erro original."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[item.name for item in fields(GpuSample)])
        writer.writeheader(); writer.writerows(asdict(item) for item in samples)
    os.replace(temporary, path)


def preflight_idle(
    *,
    duration_seconds: int = 60,
    timeout_seconds: float | None = None,
    provider: Callable[[], GpuSample] = query_sample,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    sink: Callable[[GpuSample], None] | None = None,
) -> tuple[GpuSample, ...]:
    """Portão único de aptidão térmica, na entrada da execução do cenário.

    A temperatura é **aguardada**: a placa quente esfria sozinha, e reprovar por
    isso devolvia uma decisão de cara ou coroa a cada transição encadeada. A
    concorrência na placa **não** é aguardada, porque outro processo
    computacional não vai embora sozinho, e converter essa recusa em espera
    trocaria uma proteção por atraso silencioso.

    `timeout_seconds` resolve para a constante dentro da função, e não no
    default: ligado em tempo de definição, nenhum caso conseguiria provar que a
    constante é a fonte única do teto.
    """
    limite_espera = GPU_THERMAL_WAIT_TIMEOUT_S if timeout_seconds is None else timeout_seconds
    inicio = monotonic()
    coletadas: list[GpuSample] = []
    janela: list[GpuSample] = []
    while True:
        sample = provider()
        coletadas.append(sample)
        if sink is not None:
            sink(sample)
        if sample.external_processes:
            raise GpuSafetyError("outro processo computacional usa a GPU")
        if sample.temperature_c > GPU_TEMPERATURE_LIMIT_C:
            janela.clear()
        else:
            janela.append(sample)
            if len(janela) >= duration_seconds:
                break
        decorrido = monotonic() - inicio
        if decorrido >= limite_espera:
            raise ThermalWaitTimeout(
                f"placa não estabilizou em {GPU_TEMPERATURE_LIMIT_C} graus Celsius "
                f"ou abaixo após {int(decorrido)} s de espera; última leitura de "
                f"{sample.temperature_c} graus Celsius"
            )
        sleeper(1.0)
    average = sum(item.gpu_utilization_percent for item in janela) / len(janela)
    if average > 5.0:
        raise GpuSafetyError("utilização média inicial acima de 5%")
    return tuple(coletadas)


class GpuSafetyMonitor:
    def __init__(
        self, path: Path, *, provider: Callable[[], GpuSample] = query_sample,
        interval_seconds: float = 1.0, sink: Callable[[GpuSample], None] | None = None,
        require_known_throttling: bool = False,
    ) -> None:
        self.path = path; self.provider = provider; self.interval_seconds = interval_seconds
        self.sink = sink; self.require_known_throttling = require_known_throttling
        self.samples: list[GpuSample] = []; self._stop = threading.Event()
        self._thread: threading.Thread | None = None; self._error: GpuSafetyError | None = None
        self._hot = 0

    def _check(self, sample: GpuSample) -> None:
        self._hot = self._hot + 1 if sample.temperature_c >= 80 else 0
        if self._hot >= 10:
            raise ThermalInterruption("GPU permaneceu em pelo menos 80 graus por 10 segundos")
        states = (sample.software_thermal_slowdown, sample.hardware_thermal_slowdown)
        if THROTTLING_ACTIVE in states:
            raise ThermalInterruption("GPU indicou throttling térmico")
        if self.require_known_throttling and THROTTLING_UNKNOWN in states:
            raise ThermalInterruption("telemetria de throttling incompleta")
        if sample.external_processes:
            raise ThermalInterruption("outro processo computacional apareceu na GPU")

    def _sample(self) -> None:
        sample = self.provider(); self.samples.append(sample)
        if self.sink is not None:
            self.sink(sample)
        self._check(sample)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self._sample()
            except GpuSafetyError as error:
                self._error = error; self._stop.set()
            except Exception:
                self._error = ThermalInterruption("monitor perdeu telemetria")
                self._stop.set()

    def guard(self) -> None:
        if self._error is not None:
            raise self._error

    def __enter__(self) -> "GpuSafetyMonitor":
        try:
            self._sample()
        except BaseException:
            # `__exit__` não roda quando `__enter__` levanta, e ele era o único
            # lugar que gravava a telemetria: sem esta gravação, toda
            # interrupção de segurança na primeira amostra perdia o arquivo.
            write_samples_csv(self.path, self.samples)
            raise
        self._thread = threading.Thread(target=self._run, name="gpu-safety", daemon=True)
        self._thread.start(); return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, 2 * self.interval_seconds))
        if self._error is None:
            try:
                self._sample()
            except GpuSafetyError as error:
                self._error = error
        write_samples_csv(self.path, self.samples)
        if exc_type is None and self._error is not None:
            raise self._error


class SharedFlag:
    """Sinalizador entre processos, e sem trava alguma.

    Um `multiprocessing.Event` guarda um semáforo compartilhado, e o processo
    que morre enquanto o segura trava para sempre quem chamar `set` ou `is_set`
    depois. Quem chama é o laço cronometrado, por meio de `guard`, e travá-lo é
    justamente o que este canal existe para impedir.
    """

    def __init__(self, cell: Any) -> None:
        self._cell = cell

    def set(self) -> None:
        self._cell.value = 1

    def is_set(self) -> bool:
        return bool(self._cell.value)


def _publish(sample_queue: Any, sample: GpuSample) -> None:
    sample_queue.put(("sample", sample))


def _monitor_worker(
    path: str, sample_queue: Any, abort_event: Any, stop_event: Any,
    interval_seconds: float, provider: Callable[[], GpuSample] | None,
    owner_pid: int, require_known_throttling: bool,
) -> None:
    """Corpo do processo de monitoramento. Ele é quem paga os dois `nvidia-smi`
    por amostra, longe do processo cujo tempo é publicado."""
    if provider is None:
        provider = partial(query_sample, owner_pid=owner_pid)
    monitor = GpuSafetyMonitor(
        Path(path), provider=provider, interval_seconds=interval_seconds,
        sink=partial(_publish, sample_queue), require_known_throttling=require_known_throttling,
    )
    try:
        with monitor:
            while not stop_event.is_set():
                time.sleep(min(interval_seconds, 0.05))
                monitor.guard()
    except GpuSafetyError as error:
        sample_queue.put(("error", type(error).__name__, str(error)))
        abort_event.set()
    except BaseException as error:
        sample_queue.put(("error", "ThermalInterruption", f"monitor perdeu telemetria: {error}"))
        abort_event.set()


class MonitorProcess:
    """Alça do monitor que vive em processo próprio.

    `guard` é o canal de parada consumido pelo laço cronometrado, e ele só lê um
    evento entre processos: nem subprocesso nem leitura de fila entram na janela
    medida. Quem esvazia a fila de amostras é uma thread de leitura própria, que
    também impede o filho de travar quando o cano de mensagens enche.
    """

    def __init__(
        self, path: Path, process: Any, sample_queue: Any, abort_event: Any,
        stop_event: Any, owner_pid: int, interval_seconds: float,
    ) -> None:
        self.path = path; self.process = process; self.sample_queue = sample_queue
        self.abort_event = abort_event; self.stop_event = stop_event
        self.owner_pid = owner_pid; self.interval_seconds = interval_seconds
        self.samples: list[GpuSample] = []; self._error: GpuSafetyError | None = None
        self._lock = threading.Lock(); self._reader_stop = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, name="gpu-safety-reader", daemon=True)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def _consume(self, item: tuple) -> None:
        if item[0] == "sample":
            self.samples.append(item[1]); return
        _, name, message = item
        if self._error is None:
            self._error = (ThermalInterruption if name == "ThermalInterruption" else GpuSafetyError)(message)

    def _read_loop(self) -> None:
        # A leitura fica aqui, e não no `guard`, por duas razões independentes:
        # o filho pararia de amostrar se ninguém esvaziasse o cano, e uma
        # mensagem cortada ao meio pela morte do filho bloqueia a leitura para
        # sempre. Numa thread própria isso não alcança o laço cronometrado.
        while not self._reader_stop.is_set():
            try:
                item = self.sample_queue.get(timeout=0.1)
            except queue_module.Empty:
                continue
            except (OSError, ValueError, EOFError):
                return
            with self._lock:
                self._consume(item)

    def start(self) -> None:
        self._reader.start()

    def _await_error(self, timeout: float = 2.0) -> GpuSafetyError | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._error is not None:
                    return self._error
            time.sleep(0.01)
        with self._lock:
            return self._error

    def guard(self) -> None:
        if self.abort_event.is_set():
            raise self._await_error() or ThermalInterruption(
                "monitor de segurança interrompeu a execução"
            )

    def raise_if_unsafe(self) -> None:
        with self._lock:
            error = self._error
        if error is not None:
            raise error
        if self.abort_event.is_set():
            raise self._await_error() or ThermalInterruption(
                "monitor de segurança interrompeu a execução"
            )

    def close(self) -> None:
        self.stop_event.set()
        # O prazo cobre o pior caso de saída do filho, que é a espera pela
        # thread de amostragem mais a amostra de encerramento, cujos dois
        # disparos de `nvidia-smi` carregam limite de 5 segundos cada. Prazo
        # menor faria o encerramento normal terminar em `terminate`, e a
        # gravação do arquivo pelo filho viraria caminho morto.
        deadline = time.monotonic() + max(15.0, 4 * self.interval_seconds)
        while self.process.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=5.0)
        time.sleep(max(0.3, 2 * min(self.interval_seconds, 0.5)))
        self._reader_stop.set(); self._reader.join(timeout=1.0)
        if not self._reader.is_alive():
            try:
                self.sample_queue.close(); self.sample_queue.cancel_join_thread()
            except (OSError, ValueError):
                pass
        if not self.path.exists():
            # O filho grava o arquivo ao terminar. Quando ele morre antes disso,
            # a telemetria que chegou até aqui é tudo que existe, e a exigência
            # de preservar telemetria em interrupção de segurança vale igual.
            with self._lock:
                write_samples_csv(self.path, list(self.samples))


@contextmanager
def monitor_process(
    path: Path, *, interval_seconds: float = 1.0,
    provider: Callable[[], GpuSample] | None = None, owner_pid: int | None = None,
    require_known_throttling: bool = False,
) -> Iterator[MonitorProcess]:
    context = multiprocessing.get_context("spawn")
    sample_queue = context.Queue()
    abort_event = SharedFlag(context.Value("b", 0, lock=False))
    stop_event = SharedFlag(context.Value("b", 0, lock=False))
    owner = os.getpid() if owner_pid is None else owner_pid
    process = context.Process(
        target=_monitor_worker,
        args=(str(path), sample_queue, abort_event, stop_event, interval_seconds,
              provider, owner, require_known_throttling),
        name="gpu-safety-monitor", daemon=True,
    )
    process.start()
    handle = MonitorProcess(
        Path(path), process, sample_queue, abort_event, stop_event, owner, interval_seconds,
    )
    handle.start()
    try:
        yield handle
    finally:
        handle.close()
