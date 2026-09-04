import json
from pathlib import Path

import pandas as pd

from experiments.run_greedy import build_documents, consolidate, INSTANCE_SIZES, K_VALUES


def test_build_documents_produces_eighteen_combinations():
    root = Path(__file__).resolve().parents[1]
    provenance = {"official": True, "git_commit": "deadbeef", "git_dirty": False}
    documents = build_documents(root, provenance)
    assert len(documents) == 18
    combinations = {(d["instance"], d["k"]) for d in documents}
    expected = {
        (f"artesp_rmsp_{size}", k) for size in INSTANCE_SIZES for k in K_VALUES
    }
    assert combinations == expected


def test_build_documents_are_deterministic_and_hashed():
    root = Path(__file__).resolve().parents[1]
    provenance = {"official": True, "git_commit": "deadbeef", "git_dirty": False}
    first = build_documents(root, provenance)
    second = build_documents(root, provenance)
    for a, b in zip(first, second):
        assert a["total_cost"] == b["total_cost"]
        assert a["solution"] == b["solution"]
    for document in first:
        assert document["official"] is True
        assert isinstance(document["content_sha256"], str) and len(document["content_sha256"]) == 64
        assert set(document["instance_data_sha256"]) == {
            "artesp_rmsp_150_units.parquet", "artesp_rmsp_150_pair_metrics.parquet",
        }


def test_consolidate_writes_parquet_and_manifest(tmp_path):
    root = tmp_path
    (root / "results" / "tables").mkdir(parents=True)
    provenance = {"official": True, "git_commit": "deadbeef", "git_dirty": False}
    documents = [
        {
            "algorithm": "greedy", "instance": "artesp_rmsp_20",
            "instance_path": "data/instances/artesp_rmsp_20.json",
            "instance_sha256": "x" * 64,
            "instance_data_sha256": {
                "artesp_rmsp_150_units.parquet": "u" * 64,
                "artesp_rmsp_150_pair_metrics.parquet": "p" * 64,
            },
            "k": 3, "evaluations": 10,
            "runtime_seconds": 0.01, "total_cost": 0.5, "c_demand": 0.1,
            "c_production": 0.1, "c_territorial": 0.1, "c_affinity": 0.1,
            "cv_demand": 0.1, "cv_production": 0.1, "solution": [0, 1, 2],
            "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:01Z",
            "provenance": provenance, "official": True,
            "content_sha256": "y" * 64,
        }
    ]
    manifest = consolidate(root, documents, provenance)
    assert manifest["completed"] == 1
    assert manifest["complete"] is False  # só 1 de 18
    runs = pd.read_parquet(root / "results" / "tables" / "greedy_runs.parquet")
    assert len(runs) == 1
    assert runs.iloc[0]["instance"] == "artesp_rmsp_20"
    written = json.loads((root / "results" / "tables" / "greedy_manifest.json").read_text())
    assert written["schema_version"] == 1
