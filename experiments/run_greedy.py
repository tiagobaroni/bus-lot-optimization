"""Campanha oficial da heurística gulosa sobre as 18 combinações do benchmark."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

import pandas as pd

from metaheuristica.errors import ConfigurationError
from metaheuristica.greedy import run_greedy
from metaheuristica.instances import load_artesp_instance

from experiments.provenance import capture_provenance, utc_now
from experiments.scenarios import canonical_json, file_sha256, instance_data_hashes
from experiments.storage import atomic_write_json

_ROW_FIELDS = (
    "algorithm", "instance", "instance_path", "instance_sha256", "k",
    "evaluations", "runtime_seconds", "total_cost", "c_demand", "c_production",
    "c_territorial", "c_affinity", "cv_demand", "cv_production",
    "started_at", "finished_at", "official", "content_sha256",
)

INSTANCE_SIZES = (20, 60, 150)
K_VALUES = (3, 4, 5, 6, 7, 8)


def _instance_path(root: Path, size: int) -> Path:
    return root / "data" / "instances" / f"artesp_rmsp_{size}.json"


def build_documents(root: Path, provenance: dict[str, Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for size in INSTANCE_SIZES:
        instance = load_artesp_instance(root / "data" / "instances", size)
        instance_path = _instance_path(root, size)
        # `load_artesp_instance` também lê dois Parquet (demanda, produção e
        # métricas de par) que o JSON sozinho não cobre; sem isso, trocar
        # esses dados não apareceria em nenhum hash do documento. Mesma
        # função que `experiments/scenarios.py` já usa para o benchmark
        # principal (`expand_scenarios`).
        instance_data_hash = instance_data_hashes(instance_path)
        for k in K_VALUES:
            started_at = utc_now()
            start = time.perf_counter()
            result = run_greedy(instance, k=k)
            runtime_seconds = time.perf_counter() - start
            document = {
                "schema_version": 1,
                "algorithm": "greedy",
                "instance": f"artesp_rmsp_{size}",
                "instance_path": str(instance_path.relative_to(root)),
                "instance_sha256": file_sha256(instance_path),
                "instance_data_sha256": instance_data_hash,
                "k": k,
                "evaluations": result.evaluations,
                "runtime_seconds": runtime_seconds,
                "total_cost": result.evaluation.total_cost,
                "c_demand": result.evaluation.c_demand,
                "c_production": result.evaluation.c_production,
                "c_territorial": result.evaluation.c_territorial,
                "c_affinity": result.evaluation.c_affinity,
                "cv_demand": result.evaluation.cv_demand,
                "cv_production": result.evaluation.cv_production,
                "solution": [int(label) for label in result.solution],
                "started_at": started_at,
                "finished_at": utc_now(),
                "provenance": provenance,
                "official": bool(provenance.get("official")),
            }
            document["content_sha256"] = sha256(canonical_json(document)).hexdigest()
            documents.append(document)
    return documents


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def consolidate(
    root: Path, documents: list[dict[str, Any]], provenance: dict[str, Any]
) -> dict[str, Any]:
    rows = []
    for document in documents:
        row = {field: document[field] for field in _ROW_FIELDS}
        row["solution_json"] = json.dumps(document["solution"], sort_keys=True)
        row["instance_data_sha256_json"] = json.dumps(
            document["instance_data_sha256"], sort_keys=True
        )
        rows.append(row)
    runs = pd.DataFrame(rows).sort_values(["instance", "k"]).reset_index(drop=True)
    tables = root / "results" / "tables"
    runs_path = tables / "greedy_runs.parquet"
    manifest_path = tables / "greedy_manifest.json"
    _atomic_parquet(runs_path, runs)
    ids = sorted(f"{d['instance']}_k{d['k']}" for d in documents)
    manifest = {
        "schema_version": 1,
        "campaign": "greedy_baseline",
        "purpose": "greedy",
        "expected": len(INSTANCE_SIZES) * len(K_VALUES),
        "completed": len(documents),
        "complete": len(documents) == len(INSTANCE_SIZES) * len(K_VALUES),
        "official": bool(
            len(documents) == len(INSTANCE_SIZES) * len(K_VALUES)
            and provenance.get("official")
        ),
        "scenario_ids_sha256": sha256(canonical_json(ids)).hexdigest(),
        "runs": {
            "path": "results/tables/greedy_runs.parquet",
            "sha256": file_sha256(runs_path),
        },
        "consolidated_at": utc_now(),
        "provenance": provenance,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Executa a campanha oficial da heurística gulosa"
    )
    parser.add_argument("--allow-dirty", action="store_true")
    arguments = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        provenance = capture_provenance(root, allow_dirty=arguments.allow_dirty)
        documents = build_documents(root, provenance)
        manifest = consolidate(root, documents, provenance)
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
