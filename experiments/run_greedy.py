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
