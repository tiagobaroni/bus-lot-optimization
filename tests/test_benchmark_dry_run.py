from pathlib import Path
import shutil

from experiments.benchmark_batches import BenchmarkSelection
from experiments.benchmark_operations import execute_operation
from experiments.config import load_campaign
from experiments.consolidation import consolidate_campaign
from experiments.scenarios import expand_scenarios
from tests.toy_repository import GIT_IDENTITY, git


ROOT = Path(__file__).parents[1]


def test_reduced_campaign_executes_monitors_resumes_and_consolidates(tmp_path: Path) -> None:
    official_root = ROOT / "results/raw/benchmark"
    official_before = {
        path.name for path in official_root.glob("*.json")
    } if official_root.exists() else set()
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(ROOT / "data/instances/tiny_manual.json", data / "tiny.json")
    config_path = tmp_path / "dry.toml"
    config_path.write_text('''schema_version = 1
name = "benchmark_dry_run"
purpose = "benchmark"
output_root = "out"
seeds = [10, 11]
cache_enabled = false
[weights]
demand = 0.25
production = 0.25
territorial = 0.25
affinity = 0.25
[[instances]]
name = "tiny"
path = "data/tiny.json"
budget = 100
k_values = [2]
[algorithms.pso]
n_particles = [20]
inertia = [0.7]
cognitive = [1.5]
social = [1.5]
''', encoding="utf-8")
    # A campanha de ensaio é versionada e limpa, de modo que os resultados
    # saem oficiais: resultado não oficial não conclui cenário de benchmark e a
    # retomada o reexecutaria.
    (tmp_path / ".gitignore").write_text("out/\n", encoding="utf-8")
    git(tmp_path, "init")
    git(tmp_path, "add", "-A")
    git(tmp_path, *GIT_IDENTITY, "commit", "-m", "ensaio reduzido")
    config = load_campaign(config_path, repository_root=tmp_path)
    scenarios = expand_scenarios(config)
    selection = BenchmarkSelection(1, (10, 11), scenarios, "pso", "tiny", 2)
    first, operation = execute_operation(
        config, selection, workers=2, round_name="initial",
    )
    assert first.succeeded == 2
    assert operation["sessions"][0]["summary"]["interrupted"] is False
    assert Path(tmp_path / operation["sessions"][0]["resource_summary"]).is_file()
    second, operation = execute_operation(
        config, selection, workers=2, round_name="initial",
    )
    assert second.succeeded == 0
    assert len(operation["sessions"]) == 2
    manifest = consolidate_campaign(config)
    assert manifest["complete"] is True
    assert manifest["completed"] == 2
    official_after = {
        path.name for path in official_root.glob("*.json")
    } if official_root.exists() else set()
    assert official_after == official_before
