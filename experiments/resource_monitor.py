"""Monitoramento Linux da árvore de processos de uma campanha."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterable

from metaheuristica.errors import ConfigurationError

from experiments.provenance import utc_now


GIB = 1024 ** 3
# Razão máxima tolerada entre o tempo de CPU de um processo otimizador e o
# intervalo entre duas amostras. Uma thread de cálculo dá aproximadamente 1,0;
# duas dariam 2,0. A folga de 1,10 absorve a quantização do tique de 0,01 s, que
# na campanha de 31/08/2026 mediu no máximo 1,0496 sobre 4.758 intervalos.
MAX_OPTIMIZER_CPU_RATIO = 1.10
# Amostra gravada antes de existir coluna de sessão. Ela nunca é confundida com
# uma sessão real, e a série acumulada continua no arquivo apenas como histórico.
LEGACY_SESSION = "legado"
TEXT_FIELDS = ("session_id", "sampled_at", "optimizer_pids")
# As únicas colunas numéricas que o esquema admite vazias. Elas nasceram depois
# das demais e faltam nas linhas herdadas de sessões anteriores, que o monitor
# regrava com `restval`. Célula vazia em qualquer outra coluna é CSV corrompido e
# precisa ser recusada na leitura: tolerá-la em toda coluna adia o erro para
# dentro de `summarize_samples`, como `TypeError`, ou para o Parquet, como coluna
# de tipo objeto.
OPTIONAL_NUMERIC_FIELDS = (
    "optimizer_thread_ticks_total",
    "optimizer_thread_count",
    "max_optimizer_cpu_ratio",
)


def _session_of(row: dict[str, Any]) -> str:
    return str(row.get("session_id") or LEGACY_SESSION)


def _read_meminfo(proc_root: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in (proc_root / "meminfo").read_text(encoding="utf-8").splitlines():
        name, raw = line.split(":", 1)
        amount = int(raw.strip().split()[0])
        values[name] = amount * 1024
    return values


def _read_process(proc_root: Path, pid: int) -> dict[str, int] | None:
    try:
        stat = (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
        close = stat.rfind(")")
        fields = stat[close + 2:].split()
        status = (proc_root / str(pid) / "status").read_text(
            encoding="utf-8"
        ).splitlines()
        command = (proc_root / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace"
        )
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
        return None
    status_values = {
        line.split(":", 1)[0]: line.split(":", 1)[1].strip()
        for line in status if ":" in line
    }
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "cpu_ticks": int(fields[11]) + int(fields[12]),
        "rss_bytes": int(status_values.get("VmRSS", "0 kB").split()[0]) * 1024,
        "threads": int(status_values.get("Threads", "1")),
        "infrastructure": int("multiprocessing.resource_tracker" in command),
    }


def _thread_ticks(proc_root: Path, pid: int) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        tasks = tuple((proc_root / str(pid) / "task").iterdir())
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return values
    for task in tasks:
        if not task.name.isdigit():
            continue
        try:
            stat = (task / "stat").read_text(encoding="utf-8")
            close = stat.rfind(")")
            fields = stat[close + 2:].split()
            values[f"{pid}:{task.name}"] = int(fields[11]) + int(fields[12])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return values


def sample_process_tree(
    root_pid: int,
    *,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Obtém uma fotografia consistente o bastante da árvore de processos."""

    processes: dict[int, dict[str, int]] = {}
    try:
        entries = tuple(proc_root.iterdir())
    except OSError as error:
        raise ConfigurationError(f"não foi possível ler {proc_root}") from error
    for entry in entries:
        if entry.name.isdigit():
            process = _read_process(proc_root, int(entry.name))
            if process is not None:
                processes[process["pid"]] = process
    selected = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, process in processes.items():
            if process["ppid"] in selected and pid not in selected:
                selected.add(pid)
                changed = True
    tree = [processes[pid] for pid in selected if pid in processes]
    descendants = [process for process in tree if process["pid"] != root_pid]
    optimizer_processes = [
        process for process in descendants if not process["infrastructure"]
    ]
    memory = _read_meminfo(proc_root)
    return {
        "rss_bytes": sum(process["rss_bytes"] for process in tree),
        "descendant_rss_bytes": sum(
            process["rss_bytes"] for process in descendants
        ),
        "cpu_ticks": sum(process["cpu_ticks"] for process in tree),
        "process_count": len(tree),
        "descendant_count": len(descendants),
        "optimizer_process_count": len(optimizer_processes),
        "max_optimizer_threads": max(
            (process["threads"] for process in optimizer_processes), default=0
        ),
        "optimizer_thread_ticks": {
            key: value
            for process in optimizer_processes
            for key, value in _thread_ticks(proc_root, process["pid"]).items()
        },
        # Tempo de CPU do processo inteiro. No `/proc/<pid>/stat` os campos 14 e
        # 15 já somam todas as threads do processo, ao contrário de
        # `/proc/<pid>/task/<tid>/stat`, que é por thread. É a base da razão de
        # consumo, e não depende de identificar thread alguma.
        "optimizer_process_ticks": {
            str(process["pid"]): process["cpu_ticks"]
            for process in optimizer_processes
        },
        "memory_total_bytes": memory["MemTotal"],
        "memory_available_bytes": memory["MemAvailable"],
        "swap_total_bytes": memory.get("SwapTotal", 0),
        "swap_free_bytes": memory.get("SwapFree", 0),
    }


def summarize_samples(samples: Iterable[dict[str, Any]], *, workers: int) -> dict[str, Any]:
    """Resume **a sessão atual**, e não a série acumulada do arquivo.

    O monitor recarrega do CSV as amostras de sessões anteriores, e os critérios
    eram calculados sobre a série inteira: a memória mínima era o mínimo de todas
    as linhas e a variação de swap comparava a primeira amostra da primeira
    sessão com a última da sessão atual. Entre as duas há um intervalo de duração
    arbitrária em que nada foi amostrado, e o que aconteceu na máquina durante
    esse intervalo reprovava um lote inteiro já concluído. A sessão atual é a da
    última amostra; a série acumulada permanece no arquivo como histórico e
    aparece no resumo apenas como `samples_total`.
    """

    rows = list(samples)
    if not rows:
        raise ConfigurationError("monitor de recursos não produziu amostras")
    session_id = _session_of(rows[-1])
    current = [row for row in rows if _session_of(row) == session_id]
    if not current:
        raise ConfigurationError("resumo de recursos sem amostra da sessão atual")
    memory_total = int(current[0]["memory_total_bytes"])
    minimum_required = max(int(memory_total * 0.10), 2 * GIB)
    minimum_available = min(int(row["memory_available_bytes"]) for row in current)
    swap_delta = max(
        0, int(current[0]["swap_free_bytes"]) - int(current[-1]["swap_free_bytes"])
    )
    max_threads = max(int(row["max_optimizer_threads"]) for row in current)
    max_active_threads = max(
        int(row["max_active_threads_per_optimizer"]) for row in current
    )
    peak_cpu = max(float(row["cpu_percent"]) for row in current)
    remaining_optimizers = int(current[-1]["optimizer_process_count"])
    checks = {
        "memory_margin": minimum_available >= minimum_required,
        "swap_unchanged": swap_delta == 0,
        "one_active_thread_per_optimizer": max_active_threads <= 1,
        "cpu_within_workers": peak_cpu <= workers * 100 * 1.10,
        "no_persistent_optimizers": remaining_optimizers == 0,
    }
    return {
        # Versão 2: `samples` deixou de contar o arquivo e passou a contar a
        # sessão, e o resumo ganhou `session_id`, `samples_total` e
        # `samples_session`. O artefato versionado do piloto ainda está na versão
        # 1, com a semântica antiga de `samples` e sem os três campos; o número
        # existe para que os dois não sejam comparados em silêncio.
        "schema_version": 2,
        "workers": workers,
        "session_id": session_id,
        "samples": len(current),
        # Publicados juntos de propósito: a diferença entre os dois é o que
        # documenta, no próprio artefato, que houve sessão anterior.
        "samples_total": len(rows),
        "samples_session": len(current),
        "peak_rss_bytes": max(int(row["rss_bytes"]) for row in current),
        "peak_descendant_rss_bytes": max(
            int(row["descendant_rss_bytes"]) for row in current
        ),
        "minimum_memory_available_bytes": minimum_available,
        "minimum_memory_required_bytes": minimum_required,
        "swap_consumed_bytes": swap_delta,
        "peak_cpu_percent": peak_cpu,
        "max_process_count": max(int(row["process_count"]) for row in current),
        "max_optimizer_threads": max_threads,
        "max_active_optimizer_threads": max_active_threads,
        "remaining_optimizers": remaining_optimizers,
        "checks": checks,
        "passed": all(checks.values()),
    }


@dataclass
class ResourceMonitor:
    path: Path
    workers: int
    interval_seconds: float = 1.0
    # O padrão precisa ser fábrica: expressão em valor padrão de `dataclass` é
    # avaliada uma única vez, na criação da classe, isto é na primeira importação
    # do módulo, e não a cada instanciação. Sob `fork` o filho herda a classe já
    # construída, e o monitor instanciado nele passaria a observar a árvore do
    # processo pai.
    root_pid: int = field(default_factory=os.getpid)
    # A coluna de sessão é a fronteira que faltava: sem ela, o CSV recarregado é
    # uma série contínua fictícia, e o intervalo não monitorado entre sessões
    # entra nos critérios como se tivesse sido observado.
    session_id: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not Path("/proc/self").exists():
            raise ConfigurationError("monitor de recursos exige Linux com /proc")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._samples: list[dict[str, Any]] = []
        self._started = 0.0
        self._last_ticks: int | None = None
        self._last_sample_at: float | None = None
        self._last_thread_ticks: dict[str, int] = {}
        self._last_process_ticks: dict[str, int] = {}

    def _sample(self) -> None:
        self._record(sample_process_tree(self.root_pid))

    def _record(self, row: dict[str, Any]) -> None:
        """Deriva as colunas de uma fotografia e a acrescenta à série.

        Separada da coleta para que a contabilidade de threads ativas seja
        exercitável sobre uma árvore de processos sintética.
        """

        now = time.monotonic()
        ticks = int(row.pop("cpu_ticks"))
        thread_ticks = row.pop("optimizer_thread_ticks")
        process_ticks = {
            str(pid): int(value)
            for pid, value in row.pop("optimizer_process_ticks").items()
        }
        cpu_percent = 0.0
        if self._last_ticks is not None and self._last_sample_at is not None:
            elapsed = max(now - self._last_sample_at, 1e-9)
            cpu_percent = (
                (ticks - self._last_ticks) / os.sysconf("SC_CLK_TCK") / elapsed * 100
            )
        # O intervalo é o do relógio, e precisa ser estritamente positivo: o
        # grampo de 1e-9 que serve ao percentual de CPU aqui produziria razão de
        # dez milhões a partir de um único tique.
        ratio: float | None = None
        if self._last_sample_at is not None and now > self._last_sample_at:
            intervalo = now - self._last_sample_at
            # Só processos presentes nas duas amostras: quem aparece agora não
            # tem intervalo definido, e compará-lo contra zero converteria
            # histórico acumulado em consumo aparente.
            razoes = [
                (value - self._last_process_ticks[pid])
                / os.sysconf("SC_CLK_TCK")
                / intervalo
                for pid, value in process_ticks.items()
                if pid in self._last_process_ticks
            ]
            ratio = max(razoes) if razoes else None
        self._last_ticks = ticks
        self._last_sample_at = now
        row["session_id"] = self.session_id
        # `elapsed_seconds` é tempo monitorado acumulado e não tempo decorrido:
        # numa retomada o relógio da série é deslocado para que a primeira
        # amostra nova caia um intervalo depois da última antiga, e a parada real
        # desaparece da coluna. `sampled_at` é o instante absoluto, e só o par
        # das duas permite reconstruir o intervalo não monitorado.
        row["elapsed_seconds"] = now - self._started
        row["sampled_at"] = utc_now()
        row["cpu_percent"] = max(cpu_percent, 0.0)
        row["max_optimizer_cpu_ratio"] = ratio
        row["optimizer_pids"] = " ".join(sorted(process_ticks))
        active_by_pid: dict[str, int] = {}
        for identifier, value in thread_ticks.items():
            previous = self._last_thread_ticks.get(identifier)
            # `tid` visto pela primeira vez era comparado consigo mesmo, e por
            # isso nunca contado como ativo na amostra em que aparecia. Um `tid`
            # novo é ativo quando já acumulou tempo de CPU.
            active = value > previous if previous is not None else value > 0
            if active:
                pid = identifier.split(":", 1)[0]
                active_by_pid[pid] = active_by_pid.get(pid, 0) + 1
        row["active_optimizer_threads"] = sum(active_by_pid.values())
        row["max_active_threads_per_optimizer"] = max(
            active_by_pid.values(), default=0
        )
        # O total acumulado por thread, e não apenas o delta, porque a resolução
        # de `utime + stime` é de um tick e um delta nulo não distingue thread
        # ociosa de thread abaixo do piso do relógio.
        row["optimizer_thread_ticks_total"] = sum(thread_ticks.values())
        row["optimizer_thread_count"] = len(thread_ticks)
        self._last_thread_ticks = thread_ticks
        self._last_process_ticks = process_ticks
        self._samples.append(row)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self._sample()
            except (OSError, ConfigurationError):
                continue

    def __enter__(self) -> ResourceMonitor:
        offset = 0.0
        if self.path.exists():
            self._samples = read_samples(self.path)
            if self._samples:
                offset = float(self._samples[-1]["elapsed_seconds"]) + self.interval_seconds
        self._started = time.monotonic() - offset
        self._last_ticks = None
        self._last_sample_at = None
        self._last_thread_ticks = {}
        self._last_process_ticks = {}
        self._sample()
        self._thread = threading.Thread(
            target=self._run, name="resource-monitor", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.interval_seconds * 2, 1.0))
        self._sample()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        # A união preserva a ordem e admite CSV anterior sem as colunas novas,
        # que são gravadas vazias para as linhas herdadas.
        fieldnames: list[str] = []
        for sample in self._samples:
            for name in sample:
                if name not in fieldnames:
                    fieldnames.append(name)
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, restval="")
            writer.writeheader()
            writer.writerows(self._samples)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


def read_samples(path: Path) -> list[dict[str, Any]]:
    integer_fields = {
        "rss_bytes", "descendant_rss_bytes", "process_count", "descendant_count",
        "optimizer_process_count", "max_optimizer_threads",
        "active_optimizer_threads", "max_active_threads_per_optimizer",
        "optimizer_thread_ticks_total", "optimizer_thread_count",
        "memory_total_bytes",
        "memory_available_bytes",
        "swap_total_bytes", "swap_free_bytes",
    }
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for raw in csv.DictReader(stream):
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if key in TEXT_FIELDS:
                    row[key] = value
                elif value is None or value == "":
                    if key not in OPTIONAL_NUMERIC_FIELDS:
                        raise ConfigurationError(
                            "amostra de recursos com célula vazia na coluna "
                            f"obrigatória {key} em {path}"
                        )
                    # Coluna nova ausente numa linha herdada de sessão anterior.
                    row[key] = None
                else:
                    row[key] = int(value) if key in integer_fields else float(value)
            rows.append(row)
    return rows
