"""Geração e verificação do congelamento que autoriza a B11."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.pilot_validation import _load_official_documents, _validate_result
from experiments.provenance import capture_provenance, utc_now
from experiments.scenarios import file_sha256
from experiments.storage import atomic_write_json, read_json


FREEZE_PATH = Path("results/tables/benchmark_freeze_manifest.json")
PILOT_ARTIFACTS = (
    "results/tables/pilot_runs.parquet",
    "results/tables/pilot_checkpoints.parquet",
    "results/tables/pilot_manifest.json",
    "results/tables/pilot_resource_samples.parquet",
    "results/tables/pilot_resource_summary.json",
    "results/tables/pilot_validation.json",
    "results/tables/pilot_preliminary.csv",
    "results/figures/pilot_convergence.png",
    "results/figures/pilot_convergence.pdf",
    "results/figures/pilot_time.png",
    "results/figures/pilot_time.pdf",
    "results/figures/pilot_resources.png",
    "results/figures/pilot_resources.pdf",
)
# Nomeado porque entra em dois lugares, no escopo protegido e na derivação da
# sujeira tolerável. A constante existe justamente para que a segunda derivação
# não seja uma segunda cópia do mesmo caminho.
SCHEDULE_PATH = "results/tables/benchmark_execution_schedule.json"
FIXED_PROTECTED = (
    "data/instances/artesp_rmsp_20.json",
    "data/instances/artesp_rmsp_60.json",
    "data/instances/artesp_rmsp_150.json",
    "data/instances/artesp_rmsp_150_units.parquet",
    "data/instances/artesp_rmsp_150_pair_metrics.parquet",
    "data/instances/selection_manifest.json",
    "experiments/configs/pilot.toml",
    "experiments/configs/benchmark.toml",
    "experiments/configs/frozen_parameters.toml",
    SCHEDULE_PATH,
    "pyproject.toml",
    "uv.lock",
)
AUDIT_ONLY_PATHS = (
    # `experiments/audit_fingerprint.py` é a ferramenta de conferência da
    # auditoria, criada pela Tarefa 14 do bloco B11B, e não participa de campanha
    # alguma: conferido por busca em todo o repositório, nenhum código de campanha
    # a importa, e o único importador é `tests/test_audit_fingerprint.py`. Ela é
    # folha na árvore de dependências das campanhas, de modo que congelá-la
    # confundiria a fronteira: qualquer ajuste na ferramenta que audita passaria a
    # invalidar o congelamento daquilo que ela audita. A exceção é nominal de
    # propósito, arquivo por arquivo, e não por sufixo, diretório ou heurística,
    # para que todo arquivo novo de `experiments/` continue entrando no escopo
    # protegido por padrão.
    "experiments/audit_fingerprint.py",
)


def protected_paths(root: Path) -> tuple[str, ...]:
    dynamic = [
        str(path.relative_to(root))
        for directory, pattern in ((root / "src/metaheuristica", "*.py"), (root / "experiments", "*.py"))
        for path in directory.rglob(pattern)
    ]
    return tuple(sorted(set((*FIXED_PROTECTED, *dynamic)) - set(AUDIT_ONLY_PATHS)))


def _protected_paths_changed_between(
    root: Path, pilot_commit: str, head_commit: str
) -> tuple[str, ...]:
    """Caminhos do escopo protegido tocados entre dois commits.

    A comparação é textual entre a lista de caminhos que o Git reporta no
    intervalo e o escopo protegido corrente. `--no-renames` é deliberado: com a
    detecção de renomeação ligada, o Git reportaria apenas o nome novo e um
    arquivo protegido renomeado para fora do escopo passaria despercebido.
    """

    completed = subprocess.run(
        [
            "git", "diff", "--name-only", "--no-renames",
            f"{pilot_commit}..{head_commit}",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ConfigurationError(
            "commit do piloto diverge do HEAD e o intervalo entre os dois não pôde "
            f"ser lido: {pilot_commit} contra {head_commit}"
        )
    changed = {line for line in completed.stdout.decode().splitlines() if line}
    return tuple(sorted(changed & set(protected_paths(root))))


def _tolerated_dirty_paths() -> frozenset[str]:
    """Sujeira que a geração tolera, derivada do que ela mesma hasheia.

    O fechamento é uma transação única, e não uma sequência de commits
    independentes: executar o piloto produz os treze artefatos, regerar o
    roteiro consome os tempos do piloto, e o manifesto congela os catorze. Exigir
    árvore limpa aqui é exigir que a transação já esteja fechada antes de existir
    o passo que a fecha, e é essa circularidade que a tolerância desfaz.

    O conjunto é derivado de `PILOT_ARTIFACTS` e de `SCHEDULE_PATH`, e não
    escrito uma segunda vez: duas cópias da mesma verdade divergiriam em
    silêncio, que é o defeito de fronteira já corrigido um nível abaixo.
    """

    return frozenset((*PILOT_ARTIFACTS, SCHEDULE_PATH))


def _dirty_paths(root: Path) -> tuple[str, ...]:
    """Caminhos que o Git reporta como sujos, rastreados ou não.

    A leitura repete a de `capture_provenance`, `--porcelain=v1 -z` com
    `--untracked-files=all`, para que as duas concordem sobre o que é sujeira:
    arquivo não rastreado conta, e uma leitura que só olhasse o que já está
    rastreado deixaria arquivo novo entrar por cima do congelamento. Com `-z` o
    Git não cita nem escapa caminho algum, e renomeação vem em dois registros; o
    nome antigo entra no conjunto junto com o novo, porque mover um arquivo para
    fora do escopo protegido também é sujeira que precisa ser vista.
    """

    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ConfigurationError("estado da árvore não pôde ser lido pelo Git")
    entries = [
        entry
        for entry in completed.stdout.decode("utf-8", errors="surrogateescape").split("\0")
        if entry
    ]
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        paths.add(entry[3:])
        if ("R" in entry[:2] or "C" in entry[:2]) and index < len(entries):
            paths.add(entries[index])
            index += 1
    return tuple(sorted(paths))


def _hash_files(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise ConfigurationError(f"arquivo protegido ausente: {relative}")
        hashes[relative] = file_sha256(path)
    return hashes


def _environment(provenance: dict[str, Any]) -> dict[str, Any]:
    """Campos de proveniência que o congelamento compara entre execuções.

    `observed_threads` **não** entra nesta lista, e a decisão é deliberada. A
    origem é estrutural: o argumento é a proveniência do processo orquestrador,
    devolvida por `capture_provenance`, e a contagem observada é medição de cada
    worker, publicada por cenário em `execution._publish_success`; ela não existe
    neste dicionário e a indexação direta abaixo levantaria `KeyError`. O motivo
    de fundo é o mesmo: contagem de threads é medição do processo, varia de uma
    execução para outra por causa de threads auxiliares do alocador e do Arrow, e
    compará-la converteria ruído de ambiente em recusa do manifesto congelado. O
    que o congelamento compara é o ambiente **declarado**; o contraditório da
    contagem observada é feito por cenário, no documento de resultado, e pelo
    monitor de recursos.
    """

    return {
        key: provenance[key]
        for key in (
            "python", "system", "kernel", "architecture", "processor", "cpu_count",
            "packages", "thread_limits",
        )
    }


def _revalidate_pilot_behaviour(
    config: CampaignConfig, validation: dict[str, Any]
) -> None:
    """Reavalia artefatos reais do piloto antes de assinar o congelamento.

    O veredito gravado em ``pilot_validation.json`` atesta o passado. Só a
    reexecução de ``_validate_result`` contra os documentos oficiais atesta que o
    código presente ainda reproduz o comportamento que o piloto aprovou, e é essa
    reavaliação que detecta alteração semântica da função objetivo.
    """

    documents = _load_official_documents(config)
    commits = {document["provenance"].get("git_commit") for _, document in documents}
    if commits != {validation.get("campaign_commit")}:
        raise ConfigurationError(
            "proveniência dos artefatos do piloto diverge do veredito: "
            f"{sorted(commit or '' for commit in commits)}"
        )
    for scenario, document in documents:
        _validate_result(config, scenario, document)


def generate_freeze_manifest(config: CampaignConfig, *, workers: int) -> dict[str, Any]:
    """Assina o congelamento que autoriza a B11.

    A tolerância a sujeira restrita, e por que o manifesto continua oficial.
    `capture_provenance` julga oficialidade **por commit**, e por isso marca
    `official` como falso e acrescenta `dirty_worktree` sempre que a árvore está
    suja. O congelamento julga **por conteúdo**: cada um dos catorze caminhos
    toleráveis é hasheado aqui, os treze artefatos em `pilot_artifacts` e o
    roteiro em `protected_files`, de modo que o conteúdo ainda não commitado fica
    preso pelo `sha256` que o manifesto grava, e `verify_freeze_manifest` o
    cobra na execução seguinte. A garantia por commit não é perdida, é
    substituída por uma garantia mais estreita e verificável no mesmo ato, e é
    por isso que o manifesto desta transação continua oficial.

    Para que a substituição não seja tácita, o manifesto grava
    `tolerated_dirty_paths`, com exatamente quais caminhos estavam sujos, e
    `tolerated_dirty_sha256`, a impressão do estado sujo que a proveniência
    devolve. Árvore limpa grava lista vazia, e não campo ausente. A leitura do
    estado é feita **antes** da escrita do manifesto, e é por essa razão, e não
    por omissão, que `FREEZE_PATH` nunca aparece na própria lista.

    Sujeira em qualquer caminho fora do conjunto continua sendo recusa, com a
    mensagem nomeando os arquivos: sem essa metade, tolerar sujeira restrita
    equivaleria a aceitar qualquer árvore suja, que é o oposto do que o
    congelamento existe para garantir.
    """

    if config.name != "pilot_prebenchmark":
        raise ConfigurationError("congelamento exige o piloto oficial da B10")
    root = config.repository_root
    validation = read_json(root / "results/tables/pilot_validation.json")
    if validation.get("passed") is not True or validation.get("reproduction_passed") is not True:
        raise ConfigurationError("piloto ainda não foi integralmente aprovado")
    artifact_hashes = _hash_files(root, PILOT_ARTIFACTS)
    dirty = _dirty_paths(root)
    untolerated = tuple(sorted(set(dirty) - _tolerated_dirty_paths()))
    if untolerated:
        raise ConfigurationError(
            "worktree suja fora dos artefatos que o congelamento hasheia: "
            f"{list(untolerated)}"
        )
    provenance = capture_provenance(root, allow_dirty=True)
    pilot_commit = validation.get("campaign_commit")
    head_commit = provenance["git_commit"]
    if pilot_commit != head_commit:
        # A guarda é condicional e verificável, e não posicional. O que ela
        # precisa garantir é que o código congelado não mudou desde a execução do
        # piloto, e isso se mede pelo diff entre os dois commits: commits
        # posteriores que só acrescentem artefatos derivados do próprio piloto
        # deixam o escopo protegido intacto e não invalidam nada. Aceitar "o
        # commit anterior" seria truque posicional, que quebra ao segundo commit.
        touched = _protected_paths_changed_between(root, pilot_commit, head_commit)
        if touched:
            raise ConfigurationError(
                "commit do piloto diverge do HEAD em caminho protegido: "
                f"{pilot_commit} contra {head_commit}, em {list(touched)}"
            )
    _revalidate_pilot_behaviour(config, validation)
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "pilot_campaign": config.name,
        "pilot_commit": pilot_commit,
        "head_commit": head_commit,
        "approved_workers": workers,
        "frozen_parameters_sha256": config.frozen_parameters_sha256,
        "protected_files": _hash_files(root, protected_paths(root)),
        "pilot_artifacts": artifact_hashes,
        "tolerated_dirty_paths": list(dirty),
        "tolerated_dirty_sha256": provenance["dirty_sha256"],
        "environment": _environment(provenance),
    }
    path = root / FREEZE_PATH
    atomic_write_json(path, manifest)
    verify_freeze_manifest(root, workers=workers, check_environment=True)
    return manifest


def verify_freeze_manifest(
    root: Path,
    *,
    workers: int,
    check_environment: bool = True,
) -> dict[str, Any]:
    manifest = read_json(root / FREEZE_PATH)
    if manifest.get("schema_version") != 1:
        raise ConfigurationError("versão do congelamento incompatível")
    if manifest.get("approved_workers") != workers:
        raise ConfigurationError("quantidade de workers diverge do congelamento")
    expected_protected = manifest.get("protected_files")
    if not isinstance(expected_protected, dict):
        raise ConfigurationError("arquivos protegidos ausentes do congelamento")
    current_scope = protected_paths(root)
    divergent = set(current_scope) ^ set(expected_protected)
    if divergent:
        # A lista fixa pertence ao escopo exista ou não em disco, de modo que a
        # sua ausência não aparece na diferença simétrica. Sem acumulá-la aqui, a
        # mensagem nomearia apenas uma das causas quando houvesse duas.
        divergent.update(
            relative for relative in FIXED_PROTECTED
            if not (root / relative).is_file()
        )
        raise ConfigurationError(f"escopo protegido divergente: {sorted(divergent)}")
    current_protected = _hash_files(root, current_scope)
    if current_protected != expected_protected:
        changed = sorted(
            path for path in set(current_protected) | set(expected_protected)
            if current_protected.get(path) != expected_protected.get(path)
        )
        raise ConfigurationError(f"congelamento divergente: {changed}")
    expected_artifacts = manifest.get("pilot_artifacts")
    if not isinstance(expected_artifacts, dict):
        raise ConfigurationError("artefatos do piloto ausentes do congelamento")
    artifact_scope = tuple(sorted(PILOT_ARTIFACTS))
    if artifact_scope != tuple(sorted(expected_artifacts)):
        divergent = sorted(set(PILOT_ARTIFACTS) ^ set(expected_artifacts))
        raise ConfigurationError(
            f"escopo de artefatos do piloto divergente: {divergent}"
        )
    if _hash_files(root, artifact_scope) != expected_artifacts:
        raise ConfigurationError("artefato do piloto diverge do congelamento")
    if check_environment:
        current_environment = _environment(capture_provenance(root, allow_dirty=True))
        if current_environment != manifest.get("environment"):
            raise ConfigurationError("ambiente diverge do congelamento")
    return manifest
