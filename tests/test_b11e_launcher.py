"""Testes isolados do lançador operacional da B11-E.

Os dublês impedem qualquer acesso à CLI real do benchmark. O lançador opera
somente dentro de um repositório temporário.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "experiments" / "executa_b11e.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_launcher(
    tmp_path: Path,
    *,
    existing_results: int = 0,
    execute_codes: str = "0,0,0,0,0",
    retry_codes: str = "0",
    barrier_codes: str = "0,0,0,0,0",
    finalize_code: int = 0,
    completed_barriers: tuple[int, ...] = (),
    readiness_code: int = 0,
    readiness_ready: bool = True,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    repository = tmp_path / "repository"
    bin_dir = tmp_path / "bin"
    barrier_dir = repository / "barriers"
    repository.mkdir()
    bin_dir.mkdir()
    barrier_dir.mkdir()
    (repository / "_temp").mkdir()
    for batch in completed_barriers:
        (barrier_dir / f"batch-{batch:02d}.json").write_text(
            '{"passed": true}\n', encoding="utf-8"
        )

    calls = tmp_path / "calls.log"
    counters = tmp_path / "counters"
    counters.mkdir()
    readiness = json.dumps(
        {
            "ready": readiness_ready,
            "git_dirty": False,
            "partition": {"scenarios": 1620},
            "existing_results": existing_results,
        }
    )
    _write_executable(
        bin_dir / "git",
        "#!/usr/bin/env bash\n"
        'printf "git %s\\n" "$*" >> "$B11E_TEST_CALLS"\n'
        "exit 0\n",
    )
    _write_executable(
        bin_dir / "sleep",
        "#!/usr/bin/env bash\n"
        'printf "sleep %s\\n" "$*" >> "$B11E_TEST_CALLS"\n',
    )
    _write_executable(
        bin_dir / "uv",
        """#!/usr/bin/env bash
set -u
printf 'uv %s\n' "$*" >> "$B11E_TEST_CALLS"
operation="${5:-}"
batch="${7:-0}"
next_code() {
    local name=$1 values=$2 index_file="$B11E_TEST_COUNTERS/$1"
    local index=0
    if [ -f "$index_file" ]; then index=$(<"$index_file"); fi
    IFS=',' read -r -a codes <<< "$values"
    local code=${codes[$index]:-${codes[${#codes[@]}-1]}}
    printf '%s' "$((index + 1))" > "$index_file"
    return "$code"
}
case "$operation" in
    readiness)
        printf '%s\n' "$B11E_TEST_READINESS"
        exit "$B11E_TEST_READINESS_CODE"
        ;;
    execute) next_code execute "$B11E_TEST_EXECUTE_CODES"; exit $? ;;
    retry) next_code retry "$B11E_TEST_RETRY_CODES"; exit $? ;;
    barrier) next_code barrier "$B11E_TEST_BARRIER_CODES"; exit $? ;;
    finalize) exit "$B11E_TEST_FINALIZE_CODE" ;;
    *) exit 99 ;;
esac
""",
    )
    environment = dict(os.environ)
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "B11E_REPOSITORY_ROOT": str(repository),
            "B11E_BARRIER_DIR": str(barrier_dir),
            "B11E_TEST_CALLS": str(calls),
            "B11E_TEST_COUNTERS": str(counters),
            "B11E_TEST_READINESS": readiness,
            "B11E_TEST_READINESS_CODE": str(readiness_code),
            "B11E_TEST_EXECUTE_CODES": execute_codes,
            "B11E_TEST_RETRY_CODES": retry_codes,
            "B11E_TEST_BARRIER_CODES": barrier_codes,
            "B11E_TEST_FINALIZE_CODE": str(finalize_code),
            "PAUSA_ENTRE_LOTES": "0",
        }
    )
    result = subprocess.run(
        ["bash", str(LAUNCHER)],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return result, recorded


def _operations(calls: list[str]) -> list[str]:
    return [line.split()[5] for line in calls if line.startswith("uv ")]


def test_clean_start_runs_five_batches_barriers_and_finalize(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _operations(calls) == [
        "readiness", "execute", "barrier", "execute", "barrier",
        "execute", "barrier", "execute", "barrier", "execute", "barrier",
        "finalize",
    ]


def test_partial_resume_accepts_existing_official_results(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, existing_results=137)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "137 resultados existentes" in result.stdout
    assert _operations(calls).count("execute") == 5


def test_existing_barrier_is_revalidated_and_batch_is_skipped(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, completed_barriers=(1,))
    assert result.returncode == 0, result.stdout + result.stderr
    operations = _operations(calls)
    assert operations[:3] == ["readiness", "barrier", "execute"]
    assert operations.count("execute") == 4
    assert "barreira revalidada" in result.stdout


def test_failed_revalidation_stops_before_execute(tmp_path: Path) -> None:
    result, calls = _run_launcher(
        tmp_path, completed_barriers=(1,), barrier_codes="2"
    )
    assert result.returncode == 1
    assert _operations(calls) == ["readiness", "barrier"]
    assert "falhou na revalidacao" in result.stdout


def test_multiple_completed_batches_are_skipped(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, completed_barriers=(1, 2, 3))
    assert result.returncode == 0, result.stdout + result.stderr
    assert _operations(calls).count("execute") == 2
    assert _operations(calls).count("barrier") == 5


def test_all_completed_batches_are_revalidated_then_finalized(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, completed_barriers=(1, 2, 3, 4, 5))
    assert result.returncode == 0, result.stdout + result.stderr
    assert _operations(calls) == ["readiness"] + ["barrier"] * 5 + ["finalize"]
    assert not any(line.startswith("sleep ") for line in calls)


def test_one_retry_is_used_after_initial_failure(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, execute_codes="3,0,0,0,0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _operations(calls)[:4] == ["readiness", "execute", "retry", "barrier"]
    assert _operations(calls).count("retry") == 1


def test_second_failure_stops_campaign(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, execute_codes="3", retry_codes="3")
    assert result.returncode == 1
    assert _operations(calls) == ["readiness", "execute", "retry"]
    assert "ainda tem falhas depois do retry" in result.stdout


@pytest.mark.parametrize("code", [2, 130, 17])
def test_execute_error_codes_stop_before_barrier(tmp_path: Path, code: int) -> None:
    result, calls = _run_launcher(tmp_path, execute_codes=str(code))
    assert result.returncode == 1
    assert _operations(calls) == ["readiness", "execute"]


def test_readiness_failure_stops_before_batches(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, readiness_code=2)
    assert result.returncode == 1
    assert _operations(calls) == ["readiness"]


def test_invalid_readiness_document_stops_before_batches(tmp_path: Path) -> None:
    result, calls = _run_launcher(tmp_path, readiness_ready=False)
    assert result.returncode == 1
    assert _operations(calls) == ["readiness"]


def test_launcher_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(LAUNCHER)], text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
