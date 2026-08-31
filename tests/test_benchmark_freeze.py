from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
from types import MappingProxyType
from typing import Any

import pytest

from experiments import benchmark_freeze
from experiments.benchmark_freeze import (
    FIXED_PROTECTED, FREEZE_PATH, PILOT_ARTIFACTS, _environment, _hash_files,
    generate_freeze_manifest, protected_paths, verify_freeze_manifest,
)
from experiments.config import CampaignConfig, InstanceConfig, load_campaign
from experiments.provenance import capture_provenance, utc_now
from experiments.storage import atomic_write_json, read_json
from metaheuristica import ObjectiveWeights
from metaheuristica.errors import ConfigurationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DYNAMIC_PROTECTED = (
    "src/metaheuristica/nucleo.py",
    "src/metaheuristica/interno/auxiliar.py",
    "experiments/rotina.py",
)
GIT_IDENTITY = (
    "-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture",
)
# Literal deliberado: é a derivação de comparação independente do conjunto
# tolerado, e não uma segunda leitura da constante que o módulo expõe.
SCHEDULE = "results/tables/benchmark_execution_schedule.json"


def test_hash_files_detects_missing_and_changed_file(tmp_path: Path) -> None:
    path = tmp_path / "protected.txt"
    path.write_text("first", encoding="utf-8")
    first = _hash_files(tmp_path, ("protected.txt",))
    path.write_text("second", encoding="utf-8")
    second = _hash_files(tmp_path, ("protected.txt",))
    assert first != second
    with pytest.raises(ConfigurationError, match="ausente"):
        _hash_files(tmp_path, ("missing.txt",))


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True
    )
    return completed.stdout.decode().strip()


def _build_repository(tmp_path: Path) -> Path:
    """Repositório versionado com o escopo protegido inteiro em miniatura."""

    root = tmp_path / "repositorio"
    root.mkdir()
    _write(root, ".gitignore", "results/\n_temp/\n")
    for relative in (*FIXED_PROTECTED, *DYNAMIC_PROTECTED, *PILOT_ARTIFACTS):
        _write(root, relative, f"conteúdo de {relative}\n")
    _git(root, "init")
    _git(root, "add", "-A")
    _git(root, *GIT_IDENTITY, "commit", "-m", "estado congelado")
    return root


def _write_manifest(root: Path, *, workers: int = 16) -> dict[str, Any]:
    """Manifesto íntegro, montado com os próprios utilitários do módulo."""

    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "pilot_campaign": "pilot_prebenchmark",
        "pilot_commit": _git(root, "rev-parse", "HEAD"),
        "approved_workers": workers,
        "frozen_parameters_sha256": None,
        "protected_files": _hash_files(root, protected_paths(root)),
        "pilot_artifacts": _hash_files(root, PILOT_ARTIFACTS),
        "environment": _environment(capture_provenance(root, allow_dirty=True)),
    }
    atomic_write_json(root / FREEZE_PATH, manifest)
    return manifest


def _mutate_manifest(root: Path, **changes: Any) -> None:
    manifest = read_json(root / FREEZE_PATH)
    manifest.update(changes)
    atomic_write_json(root / FREEZE_PATH, manifest)


@pytest.fixture
def frozen_repository(tmp_path: Path) -> Path:
    root = _build_repository(tmp_path)
    _write_manifest(root)
    return root


def test_verify_accepts_the_repository_it_froze(frozen_repository: Path) -> None:
    manifest = verify_freeze_manifest(frozen_repository, workers=16)
    assert manifest["approved_workers"] == 16


def test_verify_rejects_incompatible_schema_version(frozen_repository: Path) -> None:
    _mutate_manifest(frozen_repository, schema_version=2)
    with pytest.raises(ConfigurationError, match="versão do congelamento incompatível"):
        verify_freeze_manifest(frozen_repository, workers=16)


def test_verify_rejects_divergent_workers(frozen_repository: Path) -> None:
    with pytest.raises(ConfigurationError, match="workers diverge"):
        verify_freeze_manifest(frozen_repository, workers=8)


def test_verify_rejects_manifest_without_protected_files(frozen_repository: Path) -> None:
    _mutate_manifest(frozen_repository, protected_files=[])
    with pytest.raises(ConfigurationError, match="arquivos protegidos ausentes"):
        verify_freeze_manifest(frozen_repository, workers=16)


def test_verify_rejects_modified_protected_file(frozen_repository: Path) -> None:
    _write(frozen_repository, "src/metaheuristica/nucleo.py", "outro conteúdo\n")
    with pytest.raises(ConfigurationError, match="congelamento divergente") as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    assert "src/metaheuristica/nucleo.py" in str(error.value)


def test_verify_rejects_removed_protected_file(frozen_repository: Path) -> None:
    (frozen_repository / "pyproject.toml").unlink()
    with pytest.raises(ConfigurationError, match="arquivo protegido ausente"):
        verify_freeze_manifest(frozen_repository, workers=16)


def test_verify_rejects_new_file_inside_the_protected_scope(
    frozen_repository: Path,
) -> None:
    """F6-03: escopo recalculado, e não reidratado das chaves gravadas."""

    _write(frozen_repository, "experiments/sonda.py", "print('sonda')\n")
    with pytest.raises(ConfigurationError, match="escopo protegido divergente") as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    assert "experiments/sonda.py" in str(error.value)


def test_verify_rejects_new_module_under_metaheuristica(
    frozen_repository: Path,
) -> None:
    _write(frozen_repository, "src/metaheuristica/interno/extra.py", "x = 1\n")
    with pytest.raises(ConfigurationError, match="escopo protegido divergente") as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    assert "src/metaheuristica/interno/extra.py" in str(error.value)


def test_verify_rejects_removed_module_inside_the_dynamic_scope(
    frozen_repository: Path,
) -> None:
    (frozen_repository / "experiments/rotina.py").unlink()
    with pytest.raises(ConfigurationError, match="escopo protegido divergente") as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    assert "experiments/rotina.py" in str(error.value)


def test_verify_rejects_pilot_artifact_dropped_from_the_manifest(
    frozen_repository: Path,
) -> None:
    """A composição dos artefatos do piloto também é recalculada, e não reidratada."""

    manifest = read_json(frozen_repository / FREEZE_PATH)
    artifacts = dict(manifest["pilot_artifacts"])
    del artifacts["results/tables/pilot_validation.json"]
    _mutate_manifest(frozen_repository, pilot_artifacts=artifacts)
    _write(
        frozen_repository,
        "results/tables/pilot_validation.json",
        "veredito adulterado\n",
    )
    with pytest.raises(
        ConfigurationError, match="escopo de artefatos do piloto divergente"
    ) as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    assert "results/tables/pilot_validation.json" in str(error.value)


def test_scope_message_names_every_cause_at_once(frozen_repository: Path) -> None:
    """Duas causas simultâneas precisam aparecer na mesma recusa."""

    (frozen_repository / "pyproject.toml").unlink()
    _write(frozen_repository, "experiments/sonda.py", "print('sonda')\n")
    with pytest.raises(ConfigurationError, match="escopo protegido divergente") as error:
        verify_freeze_manifest(frozen_repository, workers=16)
    message = str(error.value)
    assert "experiments/sonda.py" in message
    assert "pyproject.toml" in message


def test_verify_rejects_manifest_without_pilot_artifacts(
    frozen_repository: Path,
) -> None:
    _mutate_manifest(frozen_repository, pilot_artifacts=[])
    with pytest.raises(ConfigurationError, match="artefatos do piloto ausentes"):
        verify_freeze_manifest(frozen_repository, workers=16)


def test_verify_rejects_divergent_pilot_artifact(frozen_repository: Path) -> None:
    _write(
        frozen_repository, "results/tables/pilot_runs.parquet", "artefato adulterado\n"
    )
    with pytest.raises(ConfigurationError, match="artefato do piloto diverge"):
        verify_freeze_manifest(frozen_repository, workers=16)


def test_verify_rejects_divergent_environment(frozen_repository: Path) -> None:
    manifest = read_json(frozen_repository / FREEZE_PATH)
    environment = dict(manifest["environment"])
    environment["python"] = "0.0.0"
    _mutate_manifest(frozen_repository, environment=environment)
    with pytest.raises(ConfigurationError, match="ambiente diverge"):
        verify_freeze_manifest(frozen_repository, workers=16)
    assert verify_freeze_manifest(
        frozen_repository, workers=16, check_environment=False
    )["schema_version"] == 1


def _fixture_config(root: Path) -> CampaignConfig:
    return CampaignConfig(
        schema_version=1,
        name="pilot_prebenchmark",
        purpose="pilot",
        output_root="results",
        seeds=(20260818,),
        weights=ObjectiveWeights(
            demand=0.25, production=0.25, territorial=0.25, affinity=0.25
        ),
        cache_enabled=False,
        instances=(
            InstanceConfig(
                "artesp_rmsp_20", "data/instances/artesp_rmsp_20.json", 100, (3,)
            ),
        ),
        algorithms=MappingProxyType({
            "tabu": MappingProxyType({
                "tabu_tenure": (10,), "neighborhood_size": (20,),
                "stagnation_limit": (100,),
            })
        }),
        frozen_parameters_sha256=None,
        source_path=root / "experiments/configs/pilot.toml",
        repository_root=root,
    )


def _write_verdict(root: Path, *, commit: str) -> None:
    atomic_write_json(
        root / "results/tables/pilot_validation.json",
        {
            "schema_version": 1,
            "campaign": "pilot_prebenchmark",
            "passed": True,
            "reproduction_passed": True,
            "campaign_commit": commit,
        },
    )


@pytest.fixture
def generation_repository(tmp_path: Path) -> Path:
    root = _build_repository(tmp_path)
    _write_verdict(root, commit=_git(root, "rev-parse", "HEAD"))
    return root


def test_generation_rejects_dirty_worktree(generation_repository: Path) -> None:
    """F6-02: assinar o congelamento sobre worktree suja congela o que não foi validado."""

    _write(generation_repository, "src/metaheuristica/nucleo.py", "alteração não commitada\n")
    with pytest.raises(ConfigurationError, match="worktree suja") as error:
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    assert "src/metaheuristica/nucleo.py" in str(error.value)
    assert not (generation_repository / FREEZE_PATH).exists()


def test_generation_rejects_pilot_commit_divergent_from_head(
    generation_repository: Path,
) -> None:
    """F6-02: o commit do piloto precisa ser confrontado com o HEAD."""

    _write_verdict(generation_repository, commit="0" * 40)
    with pytest.raises(ConfigurationError, match="commit do piloto diverge do HEAD"):
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    assert not (generation_repository / FREEZE_PATH).exists()


def _commit_extra(root: Path, relative: str, text: str, message: str) -> str:
    """Acrescenta um commit ao repositório de brinquedo e devolve o novo HEAD."""

    _write(root, relative, text)
    _git(root, "add", "-A")
    _git(root, *GIT_IDENTITY, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def test_generation_accepts_divergent_head_when_only_derived_paths_changed(
    generation_repository: Path, monkeypatch
) -> None:
    """R2: a guarda é condicional, e o que ela mede é o diff do escopo protegido."""

    pilot_commit = _git(generation_repository, "rev-parse", "HEAD")
    head_commit = _commit_extra(
        generation_repository, "docs/nota_derivada.md", "registro posterior\n",
        "acrescenta documento derivado",
    )
    assert head_commit != pilot_commit
    # O intervalo não é vazio: o que o torna aceitável é a interseção vazia com o
    # escopo protegido, e não a ausência de mudanças.
    assert _git(
        generation_repository, "diff", "--name-only", f"{pilot_commit}..{head_commit}"
    ) == "docs/nota_derivada.md"
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    manifest = generate_freeze_manifest(
        _fixture_config(generation_repository), workers=16
    )
    assert manifest["pilot_commit"] == pilot_commit
    assert manifest["head_commit"] == head_commit
    # R3: árvore limpa registra conjunto sujo vazio, e não ausência de campo.
    assert manifest["tolerated_dirty_paths"] == []
    written = read_json(generation_repository / FREEZE_PATH)
    assert written["pilot_commit"] == pilot_commit
    assert written["head_commit"] == head_commit
    assert written["tolerated_dirty_paths"] == []


def test_generation_rejects_divergent_head_that_touches_a_protected_path(
    generation_repository: Path, monkeypatch
) -> None:
    """R2: a metade que recusa, sem a qual a guarda condicional é porta aberta."""

    pilot_commit = _git(generation_repository, "rev-parse", "HEAD")
    head_commit = _commit_extra(
        generation_repository, "src/metaheuristica/nucleo.py", "outro conteúdo\n",
        "altera módulo protegido",
    )
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    with pytest.raises(ConfigurationError, match="caminho protegido") as error:
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    message = str(error.value)
    assert "src/metaheuristica/nucleo.py" in message
    assert pilot_commit in message and head_commit in message
    assert not (generation_repository / FREEZE_PATH).exists()


def test_audit_fingerprint_is_outside_the_protected_scope() -> None:
    """R2: a ferramenta de conferência da auditoria não é código de campanha."""

    relative = "experiments/audit_fingerprint.py"
    assert (REPOSITORY_ROOT / relative).is_file()
    assert relative in benchmark_freeze.AUDIT_ONLY_PATHS
    assert relative not in protected_paths(REPOSITORY_ROOT)


def test_new_experiment_module_enters_the_scope_and_only_the_exception_leaves(
    tmp_path: Path,
) -> None:
    """R2: a exceção é estreita, e o conjunto é preso por identidade.

    A derivação de comparação é independente: ela é a lista literal do que a
    fixture escreveu, e não uma segunda chamada da mesma varredura.
    """

    root = _build_repository(tmp_path)
    _write(root, "experiments/audit_fingerprint.py", "ferramenta de auditoria\n")
    _write(root, "experiments/modulo_novo.py", "print('novo')\n")
    expected = {*FIXED_PROTECTED, *DYNAMIC_PROTECTED, "experiments/modulo_novo.py"}
    assert set(protected_paths(root)) == expected


def test_generation_revalidates_pilot_behaviour_before_signing(
    generation_repository: Path,
) -> None:
    """F6-02: o veredito gravado não basta, os artefatos reais são reavaliados."""

    with pytest.raises(ConfigurationError, match="resultado ausente"):
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    assert not (generation_repository / FREEZE_PATH).exists()


def _doubled_affinity_evaluation(original):
    """Reproduz a mutação da auditoria: peso de afinidade dobrado no objetivo."""

    def evaluate(instance, labels, *, k, weights):
        evaluation = original(instance, labels, k=k, weights=weights)
        return replace(
            evaluation,
            c_affinity=2.0 * evaluation.c_affinity,
            total_cost=evaluation.total_cost + weights.affinity * evaluation.c_affinity,
        )

    return evaluate


def test_revalidation_rejects_altered_objective_function(monkeypatch) -> None:
    """F6-02: a cadeia demonstrada pela auditoria, com a função objetivo alterada."""

    from experiments import pilot_validation

    config = load_campaign(REPOSITORY_ROOT / "experiments/configs/pilot.toml")
    validation = read_json(
        REPOSITORY_ROOT / "results/tables/pilot_validation.json"
    )
    benchmark_freeze._revalidate_pilot_behaviour(config, validation)
    monkeypatch.setattr(
        pilot_validation,
        "evaluate_solution",
        _doubled_affinity_evaluation(pilot_validation.evaluate_solution),
    )
    with pytest.raises(ConfigurationError, match="reavaliação divergente"):
        benchmark_freeze._revalidate_pilot_behaviour(config, validation)


def test_revalidation_rejects_verdict_with_foreign_commit() -> None:
    config = load_campaign(REPOSITORY_ROOT / "experiments/configs/pilot.toml")
    validation = read_json(
        REPOSITORY_ROOT / "results/tables/pilot_validation.json"
    )
    with pytest.raises(ConfigurationError, match="proveniência"):
        benchmark_freeze._revalidate_pilot_behaviour(
            config, {**validation, "campaign_commit": "0" * 40}
        )


def test_tolerated_dirty_paths_come_from_what_the_manifest_hashes() -> None:
    """R3: o conjunto tolerado é derivado, e não uma segunda lista escrita à mão.

    A comparação é independente da derivação: o roteiro entra aqui como literal,
    e a identidade prende o conjunto pelos dois lados, de modo que nem um
    caminho a mais nem um a menos passa em silêncio.
    """

    assert benchmark_freeze.SCHEDULE_PATH == SCHEDULE
    assert SCHEDULE in FIXED_PROTECTED
    assert benchmark_freeze._tolerated_dirty_paths() == {*PILOT_ARTIFACTS, SCHEDULE}
    assert len(benchmark_freeze._tolerated_dirty_paths()) == len(PILOT_ARTIFACTS) + 1


@pytest.fixture
def transaction_repository(tmp_path: Path) -> Path:
    """Repositório onde o roteiro e dois artefatos do piloto são rastreados.

    `_build_repository` ignora `results/`, e arquivo ignorado nunca aparece como
    sujeira: sem rastrear o roteiro e ao menos um artefato, o caso de sujeira
    tolerada passaria por vácuo. O `add -f` é nominal para não tirar `results/`
    do `.gitignore`, e a árvore fica limpa ao fim da montagem, o que a asserção
    abaixo mede em vez de supor.
    """

    root = _build_repository(tmp_path)
    _git(
        root, "add", "-f", SCHEDULE, "results/tables/pilot_runs.parquet",
        "results/tables/pilot_manifest.json",
    )
    _git(root, *GIT_IDENTITY, "commit", "-m", "rastreia o roteiro e dois artefatos")
    # O veredito continua ignorado, e por isso escrevê-lo não suja a árvore.
    _write_verdict(root, commit=_git(root, "rev-parse", "HEAD"))
    assert _git(root, "status", "--porcelain") == ""
    return root


def _sha256_of(root: Path, relative: str) -> str:
    return _hash_files(root, (relative,))[relative]


def test_generation_proceeds_with_dirt_restricted_to_pilot_artifacts(
    transaction_repository: Path, monkeypatch
) -> None:
    """R3: o fechamento é uma transação única e roda sobre o que ele mesmo produz."""

    relative = "results/tables/pilot_runs.parquet"
    _write(transaction_repository, relative, "tempos novos do piloto\n")
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    manifest = generate_freeze_manifest(
        _fixture_config(transaction_repository), workers=16
    )
    assert manifest["tolerated_dirty_paths"] == [relative]
    # O que ficou congelado é o conteúdo sujo, e não o conteúdo commitado: é
    # essa igualdade que sustenta a oficialidade por conteúdo.
    assert manifest["pilot_artifacts"][relative] == _sha256_of(
        transaction_repository, relative
    )


def test_generation_proceeds_with_the_regenerated_schedule_dirty(
    transaction_repository: Path, monkeypatch
) -> None:
    """R3: o caso que motivou o pacote, o roteiro regerado depois do piloto."""

    _write(transaction_repository, SCHEDULE, "roteiro regerado sobre os tempos novos\n")
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    manifest = generate_freeze_manifest(
        _fixture_config(transaction_repository), workers=16
    )
    assert manifest["tolerated_dirty_paths"] == [SCHEDULE]
    assert manifest["protected_files"][SCHEDULE] == _sha256_of(
        transaction_repository, SCHEDULE
    )


def test_generation_still_rejects_dirt_outside_the_tolerated_set(
    transaction_repository: Path, monkeypatch
) -> None:
    """R3: a metade que recusa, sem a qual o pacote vira porta aberta.

    A sujeira tolerada está presente ao mesmo tempo, de propósito: o que decide
    a recusa é o que sobra fora do conjunto, e não a existência de sujeira.
    """

    _write(transaction_repository, "results/tables/pilot_runs.parquet", "tempos novos\n")
    _write(
        transaction_repository, "src/metaheuristica/nucleo.py",
        "alteração não commitada\n",
    )
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    with pytest.raises(ConfigurationError, match="worktree suja") as error:
        generate_freeze_manifest(_fixture_config(transaction_repository), workers=16)
    message = str(error.value)
    assert "src/metaheuristica/nucleo.py" in message
    assert "results/tables/pilot_runs.parquet" not in message
    assert not (transaction_repository / FREEZE_PATH).exists()


def test_generation_rejects_untracked_file_outside_the_tolerated_set(
    transaction_repository: Path, monkeypatch
) -> None:
    """R3: arquivo não rastreado é sujeira, e a leitura do estado precisa vê-lo.

    `capture_provenance` conta arquivo não rastreado como sujeira desde a
    correção da F5; uma leitura que só olhasse o que já está rastreado deixaria
    entrar arquivo novo em cima do congelamento.
    """

    _write(transaction_repository, "sobra.txt", "arquivo novo, fora do conjunto\n")
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    with pytest.raises(ConfigurationError, match="worktree suja") as error:
        generate_freeze_manifest(_fixture_config(transaction_repository), workers=16)
    assert "sobra.txt" in str(error.value)
    assert not (transaction_repository / FREEZE_PATH).exists()


def test_manifest_records_exactly_the_paths_that_were_dirty(
    transaction_repository: Path, monkeypatch
) -> None:
    """R3: o registro é identidade, e não continência.

    Desigualdade sobre conjunto não prende conjunto: gravar a lista inteira do
    tolerado, ou o conjunto sujo mais um vizinho, passaria por continência e
    morre aqui.
    """

    dirty = {SCHEDULE, "results/tables/pilot_manifest.json"}
    for relative in sorted(dirty):
        _write(transaction_repository, relative, f"reescrito na transação: {relative}\n")
    monkeypatch.setattr(
        benchmark_freeze, "_revalidate_pilot_behaviour", lambda *args, **kwargs: None
    )
    manifest = generate_freeze_manifest(
        _fixture_config(transaction_repository), workers=16
    )
    assert set(manifest["tolerated_dirty_paths"]) == dirty
    written = read_json(transaction_repository / FREEZE_PATH)
    assert set(written["tolerated_dirty_paths"]) == dirty
    # O estado sujo também fica identificado, e não apenas enumerado.
    assert isinstance(written["tolerated_dirty_sha256"], str)
    assert len(written["tolerated_dirty_sha256"]) == 64
