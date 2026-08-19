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
    with pytest.raises(ConfigurationError, match="worktree suja"):
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    assert not (generation_repository / FREEZE_PATH).exists()


def test_generation_rejects_pilot_commit_divergent_from_head(
    generation_repository: Path,
) -> None:
    """F6-02: o commit do piloto precisa ser confrontado com o HEAD."""

    _write_verdict(generation_repository, commit="0" * 40)
    with pytest.raises(ConfigurationError, match="commit do piloto diverge do HEAD"):
        generate_freeze_manifest(_fixture_config(generation_repository), workers=16)
    assert not (generation_repository / FREEZE_PATH).exists()


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
