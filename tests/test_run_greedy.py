from pathlib import Path

from experiments.run_greedy import build_documents, INSTANCE_SIZES, K_VALUES


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
