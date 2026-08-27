"""Captura de proveniência ambiental e estado do repositório."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import subprocess
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.scenarios import canonical_json, file_sha256


THREAD_VARIABLES = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "ARROW_NUM_THREADS",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git(root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=root, check=True, capture_output=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ConfigurationError("Git indisponível ou diretório sem repositório") from error
    return completed.stdout


def _dirty_hash(root: Path, status: bytes) -> str:
    digest = sha256()
    digest.update(status)
    digest.update(_git(root, "diff", "--binary", "HEAD"))
    for entry in status.split(b"\0"):
        if not entry.startswith(b"?? "):
            continue
        relative = entry[3:].decode("utf-8", errors="surrogateescape")
        path = root / relative
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        if path.is_file():
            digest.update(file_sha256(path).encode("ascii"))
    return digest.hexdigest()


def capture_provenance(
    repository_root: Path,
    *,
    allow_dirty: bool = False,
    allow_unversioned: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    # Os dois motivos de não oficialidade são separados de propósito. Enquanto
    # um único `except` cobria os dois, `--allow-unversioned` sobre worktree
    # suja apagava o commit e o hash do estado sujo e registrava `unversioned`,
    # isto é o registro afirmava ausência de repositório onde havia repositório
    # e havia diferença rastreável.
    try:
        commit = _git(repository_root, "rev-parse", "HEAD").decode().strip()
        status = _git(
            repository_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
    except ConfigurationError:
        if not allow_unversioned:
            raise ConfigurationError(
                "Git indisponível; use --allow-unversioned para execução não oficial"
            )
        commit = None
        dirty = None
        dirty_hash = None
        reasons.append("unversioned")
    else:
        dirty = bool(status)
        dirty_hash = _dirty_hash(repository_root, status) if dirty else None
        if dirty and not (allow_dirty or allow_unversioned):
            raise ConfigurationError("worktree suja; use --allow-dirty para execução não oficial")
        if dirty:
            reasons.append("dirty_worktree")

    packages = {}
    for package in (
        "numpy", "pandas", "pyarrow", "matplotlib", "bus-lot-optimization"
    ):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "dirty_sha256": dirty_hash,
        "official": not reasons,
        "nonofficial_reasons": reasons,
        "python": platform.python_version(),
        "system": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "packages": packages,
        "thread_limits": {name: os.environ.get(name) for name in THREAD_VARIABLES},
    }
