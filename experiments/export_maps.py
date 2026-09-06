"""Exportação cartográfica dos agrupamentos (B15)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from metaheuristica.canonical import canonicalize_solution, validate_solution
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from experiments.map_styles import write_style_files
from experiments.provenance import capture_provenance
from experiments.scenarios import file_sha256

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# Pacotes que decidem os empates de alinhamento (`scipy`) e a geometria do
# pacote cartográfico (`geopandas`, `pyogrio`, `shapely`), registrados à parte
# de `capture_provenance`. A tupla de pacotes do helper cobre numpy, pandas,
# pyarrow, matplotlib e o próprio projeto, e não inclui nenhum dos quatro
# acima; mudar essa tupla arriscaria os manifestos oficiais que já a
# congelam, então a B15 os registra em bloco próprio, no mesmo padrão.
GEOSPATIAL_PACKAGES = ("scipy", "geopandas", "pyogrio", "shapely")

MANIFEST_SCHEMA_VERSION = "1.0.0"

INSTANCE_SIZES = (20, 60, 150)
ALGORITHMS = ("tabu", "aco", "pso")
EXPECTED_RUNS = 1620
EXPECTED_SEEDS = 30
COMBINATIONS = 54
GROUP_KEYS = ["instance", "algorithm", "k"]

UNIVERSE_SIZE = 150
UNIVERSE = f"artesp_rmsp_{UNIVERSE_SIZE}"
DESCRIPTIVE_COLUMNS = [
    "unit_id", "codigo_linha", "sentido", "nome_legivel",
    "passengers_day", "pu_km_day", "route_length_km",
]
NESTING_LABELS = {20: "20_60_150", 60: "60_150", 150: "so_150"}

HIGHLIGHT_K = 5
INSTANCE_NAMES = tuple(f"artesp_rmsp_{size}" for size in INSTANCE_SIZES)
NESTING_DESCRIPTIONS = {
    "20_60_150": "Nos três recortes (20, 60 e 150)",
    "60_150": "Nos recortes de 60 e 150",
    "so_150": "Somente no recorte de 150",
}

METRIC_CRS = "EPSG:31983"
GEOGRAPHIC_CRS = "EPSG:4326"
DEGENERATE_BUFFER_METERS = 50.0


def select_best_runs(
    runs: pd.DataFrame,
    *,
    unit_counts: dict[str, int],
    expected_runs: int = EXPECTED_RUNS,
    expected_seeds: int = EXPECTED_SEEDS,
    combinations: int = COMBINATIONS,
) -> pd.DataFrame:
    """Escolhe, por combinação, a execução oficial de menor custo."""

    official = runs[runs["official"].astype(bool)]
    if len(official) != expected_runs:
        raise ConfigurationError(
            f"o recorte oficial tem {len(official)} execuções, e não {expected_runs}"
        )
    sizes = official.groupby(GROUP_KEYS).size()
    if len(sizes) != combinations:
        raise ConfigurationError(
            f"há {len(sizes)} combinações instância×algoritmo×K, e não {combinations}"
        )
    divergent = sizes[sizes != expected_seeds]
    if not divergent.empty:
        raise ConfigurationError(
            "combinação sem as seeds esperadas: "
            + ", ".join(f"{key}={value}" for key, value in divergent.items())
        )

    ordered = official.sort_values([*GROUP_KEYS, "total_cost", "seed"])
    # `drop_duplicates` preserva a LINHA inteira da vencedora; `groupby().first()`
    # tomaria o primeiro valor não-nulo de cada coluna em separado.
    best = ordered.drop_duplicates(subset=GROUP_KEYS, keep="first").copy()
    best["solution"] = best["solution_json"].map(json.loads)
    _validate_solutions(best, unit_counts=unit_counts)
    return best[[*GROUP_KEYS, "seed", "total_cost", "scenario_id", "solution"]]


def _validate_solutions(selected: pd.DataFrame, *, unit_counts: dict[str, int]) -> None:
    """Recusa solução com comprimento ou número de lotes divergente."""

    for row in selected.itertuples():
        expected_units = unit_counts.get(row.instance)
        if expected_units is None:
            raise ConfigurationError(f"instância desconhecida no parquet: {row.instance}")
        try:
            validate_solution(row.solution, n_units=expected_units, k=int(row.k))
        except SolutionValidationError as error:
            raise ConfigurationError(
                f"solução inválida em {row.scenario_id}: {error}"
            ) from error


def align_to_reference(
    labels: Sequence[int], reference: Sequence[int], *, k: int
) -> np.ndarray:
    """Renomeia `labels` para casar com `reference` por sobreposição máxima."""

    labels_array = np.asarray(labels, dtype=np.int64)
    reference_array = np.asarray(reference, dtype=np.int64)
    contingency = np.zeros((k, k), dtype=np.int64)
    np.add.at(contingency, (labels_array, reference_array), 1)
    rows, columns = linear_sum_assignment(contingency, maximize=True)
    mapping = np.empty(k, dtype=np.int64)
    mapping[rows] = columns
    return mapping[labels_array]


def align_selected(selected: pd.DataFrame) -> pd.DataFrame:
    """Alinha os rótulos dos três métodos dentro de cada par (instância, K)."""

    order = {name: position for position, name in enumerate(ALGORITHMS)}
    frames = []
    for (_, k), group in selected.groupby(["instance", "k"], sort=False):
        ranked = group.assign(_order=group["algorithm"].map(order))
        ranked = ranked.sort_values(["total_cost", "_order"])
        reference_row = ranked.iloc[0]
        n_units = len(reference_row["solution"])
        reference = canonicalize_solution(
            reference_row["solution"], n_units=n_units, k=int(k)
        )
        aligned = [
            [int(value) for value in align_to_reference(row.solution, reference, k=int(k))]
            for row in ranked.itertuples()
        ]
        result = ranked.drop(columns="_order").copy()
        result["solution_aligned"] = aligned
        result["reference_algorithm"] = reference_row["algorithm"]
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


def column_name(instance: str, algorithm: str, k: int) -> str:
    """Nome da coluna de lote de uma combinação instância×algoritmo×K."""

    size = instance.rsplit("_", 1)[-1]
    return f"lot_i{size}_{algorithm}_k{k}"


def style_panels(k: int = HIGHLIGHT_K) -> list[tuple[str, str, int]]:
    """Os nove painéis do recorte de destaque: nome do arquivo, coluna e K."""

    panels = []
    for instance in INSTANCE_NAMES:
        for algorithm in ALGORITHMS:
            attribute = column_name(instance, algorithm, k)
            panels.append((f"itinerarios_{attribute}", attribute, k))
    return panels


def nesting_entries() -> list[tuple[str, str]]:
    """Os valores de `aninhamento` gravados na camada, com seus rótulos."""

    return [(NESTING_LABELS[size], NESTING_DESCRIPTIONS[NESTING_LABELS[size]])
            for size in INSTANCE_SIZES]


def instance_paths(instances_dir: Path, size: int) -> dict[str, Path]:
    """Caminhos do `.gpkg` e do `.json` de uma instância, pelo seu tamanho."""

    return {"gpkg": instances_dir / f"artesp_rmsp_{size}.gpkg",
            "json": instances_dir / f"artesp_rmsp_{size}.json"}


def read_unit_ids(instances_dir: Path) -> dict[int, list[str]]:
    """Lê `unit_ids` das três instâncias, recusando arquivo ausente."""

    unit_ids: dict[int, list[str]] = {}
    for size in INSTANCE_SIZES:
        paths = instance_paths(instances_dir, size)
        for path in paths.values():
            if not path.exists():
                raise ConfigurationError(f"instância ausente: {path}")
        unit_ids[size] = list(
            json.loads(paths["json"].read_text(encoding="utf-8"))["unit_ids"]
        )
    return unit_ids


def build_itinerarios(instances_dir: Path, aligned: pd.DataFrame) -> gpd.GeoDataFrame:
    """Monta o universo de itinerários com o aninhamento e as colunas de lote."""

    unit_ids = read_unit_ids(instances_dir)
    frame = gpd.read_file(instances_dir / f"{UNIVERSE}.gpkg", layer="itinerarios")
    missing = set(unit_ids[UNIVERSE_SIZE]) - set(frame["unit_id"])
    unknown = set(frame["unit_id"]) - set(unit_ids[UNIVERSE_SIZE])
    if missing or unknown:
        raise ConfigurationError(
            f"itinerários divergem de unit_ids; faltando {sorted(missing)}, "
            f"sobrando {sorted(unknown)}"
        )
    frame = frame[[*DESCRIPTIVE_COLUMNS, "geometry"]].copy()

    in_20 = frame["unit_id"].isin(unit_ids[20])
    in_60 = frame["unit_id"].isin(unit_ids[60])
    frame["in_20"] = in_20
    frame["in_60"] = in_60
    frame["aninhamento"] = np.where(
        in_20, NESTING_LABELS[20],
        np.where(in_60, NESTING_LABELS[60], NESTING_LABELS[150]),
    )

    for row in aligned.itertuples():
        column = column_name(row.instance, row.algorithm, int(row.k))
        if column in frame.columns:
            raise ConfigurationError(f"coluna de lote duplicada: {column}")
        size_text = row.instance.rsplit("_", 1)[-1]
        size = int(size_text) if size_text.isdigit() else None
        if size not in unit_ids:
            raise ConfigurationError(
                f"instância desconhecida em aligned: {row.instance}"
            )
        solution_aligned = list(row.solution_aligned)
        if len(solution_aligned) != len(unit_ids[size]):
            raise ConfigurationError(
                f"solução alinhada de {row.instance} tem {len(solution_aligned)} "
                f"unidades, e não {len(unit_ids[size])}"
            )
        mapping = dict(zip(unit_ids[size], solution_aligned))
        frame[column] = frame["unit_id"].map(mapping).astype("Int64")
    return frame


def build_envoltorias(
    itinerarios: gpd.GeoDataFrame,
    aligned: pd.DataFrame,
    unit_ids: dict[int, list[str]],
) -> gpd.GeoDataFrame:
    """Casco convexo dos itinerários de cada lote, calculado em CRS métrico."""

    metric = itinerarios.to_crs(METRIC_CRS).set_index("unit_id")
    records = []
    for row in aligned.itertuples():
        size = int(row.instance.rsplit("_", 1)[-1])
        labels = pd.Series(row.solution_aligned, index=unit_ids[size])
        for lot, members in labels.groupby(labels):
            geometries = metric.loc[list(members.index), "geometry"]
            hull = geometries.union_all().convex_hull
            degenerate = hull.geom_type != "Polygon"
            if degenerate:
                hull = hull.buffer(DEGENERATE_BUFFER_METERS)
            records.append({
                "instance": row.instance, "algorithm": row.algorithm,
                "k": int(row.k), "lot": int(lot), "seed": int(row.seed),
                "total_cost": float(row.total_cost),
                "scenario_id": row.scenario_id, "n_units": int(len(members)),
                "area_km2": float(hull.area / 1e6), "degenerado": bool(degenerate),
                "geometry": hull,
            })
    frame = gpd.GeoDataFrame(records, geometry="geometry", crs=METRIC_CRS)
    return frame.to_crs(GEOGRAPHIC_CRS)


def _temporary_beside(path: Path, suffix: str) -> Path:
    """Cria um arquivo temporário oculto no mesmo diretório do alvo."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=suffix
    )
    os.close(descriptor)
    return Path(name)


def atomic_write_text(path: Path, content: str) -> Path:
    """Escreve texto por temporário e `os.replace`, sem deixar meio arquivo."""

    temporary = _temporary_beside(path, ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_gpkg(path: Path, layers: dict[str, gpd.GeoDataFrame]) -> Path:
    """Escreve o GPKG multicamadas de forma atômica."""

    # Sufixo `.gpkg` no temporário: com `.tmp`, o pyogrio emite um
    # RuntimeWarning de extensão a cada camada escrita.
    temporary = _temporary_beside(path, ".gpkg")
    temporary.unlink(missing_ok=True)
    try:
        for position, (name, frame) in enumerate(layers.items()):
            frame.to_file(temporary, layer=name, driver="GPKG",
                          mode="w" if position == 0 else "a")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def geospatial_stack_versions() -> dict[str, str | None]:
    """Versões de `scipy`, `geopandas`, `pyogrio` e `shapely`.

    Registradas fora de `capture_provenance` por decisão deliberada: dos 54
    alinhamentos da B15, 10 têm atribuição ótima não única em
    `scipy.optimize.linear_sum_assignment` — outra permutação de rótulos
    empata na mesma sobreposição máxima —, e qual delas sai depende do
    desempate interno do `scipy`. Um deles, `lot_i20_aco_k5`, é um dos nove
    painéis de destaque, e a atribuição alternativa recoloriria 8 das 20
    linhas do painel. A pilha geoespacial, por sua vez, decide a geometria
    escrita no GPKG. Nenhum dos quatro entra na tupla congelada de pacotes de
    `capture_provenance`, e essa tupla não é alterada aqui.
    """

    versions: dict[str, str | None] = {}
    for package in GEOSPATIAL_PACKAGES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def build_manifest(
    runs_path: Path,
    instances_dir: Path,
    aligned: pd.DataFrame,
    *,
    generated_at: str,
    provenance: dict,
) -> dict:
    """Proveniência da exportação, na forma dos demais manifestos do projeto."""

    combinations = [
        {
            "instance": row.instance, "algorithm": row.algorithm, "k": int(row.k),
            "seed": int(row.seed), "total_cost": float(row.total_cost),
            "scenario_id": row.scenario_id,
            "column": column_name(row.instance, row.algorithm, int(row.k)),
        }
        for row in aligned.itertuples()
    ]
    references = {
        f"{row.instance}|{int(row.k)}": row.reference_algorithm
        for row in aligned.itertuples()
    }
    instances = {}
    for size in INSTANCE_SIZES:
        paths = instance_paths(instances_dir, size)
        for path in paths.values():
            if not path.exists():
                raise ConfigurationError(f"instância ausente: {path}")
        instances[f"artesp_rmsp_{size}"] = {
            "gpkg_path": str(paths["gpkg"]),
            "gpkg_sha256": file_sha256(paths["gpkg"]),
            "json_path": str(paths["json"]),
            "json_sha256": file_sha256(paths["json"]),
        }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": {"path": str(runs_path), "content_sha256": file_sha256(runs_path)},
        "instances": instances,
        "combinations": sorted(combinations, key=lambda item: item["column"]),
        "references": references,
        "provenance": {**provenance, "geospatial_stack": geospatial_stack_versions()},
    }


def instance_unit_counts(instances_dir: Path) -> dict[str, int]:
    """Número de unidades de cada instância, derivado de `unit_ids`."""

    return {f"artesp_rmsp_{size}": len(ids)
            for size, ids in read_unit_ids(instances_dir).items()}


def export(
    *,
    tables_dir: Path,
    instances_dir: Path,
    output_dir: Path,
    unit_counts: dict[str, int] | None = None,
    expected_runs: int = EXPECTED_RUNS,
    expected_seeds: int = EXPECTED_SEEDS,
    combinations: int = COMBINATIONS,
) -> dict:
    """Exporta o pacote cartográfico completo e devolve o relatório."""

    # Capturada antes de qualquer escrita de artefato: se viesse depois, o
    # próprio GPKG recém-escrito sujaria a árvore e o registro seria falso.
    # `allow_dirty=True` é deliberado — recusar a exportação por árvore suja
    # seria hostil a uma tarefa cartográfica; `git_dirty` e `dirty_sha256`
    # registram a verdade do estado sem bloquear a exportação.
    provenance = capture_provenance(REPOSITORY_ROOT, allow_dirty=True)

    runs_path = tables_dir / "benchmark_runs.parquet"
    if not runs_path.exists():
        raise ConfigurationError(f"ausente: {runs_path}")
    counts = unit_counts if unit_counts is not None else instance_unit_counts(instances_dir)
    selected = select_best_runs(
        pd.read_parquet(runs_path), unit_counts=counts,
        expected_runs=expected_runs, expected_seeds=expected_seeds,
        combinations=combinations,
    )
    aligned = align_selected(selected)
    unit_ids = read_unit_ids(instances_dir)
    itinerarios = build_itinerarios(instances_dir, aligned)
    envoltorias = build_envoltorias(itinerarios, aligned, unit_ids)
    terminais = gpd.read_file(instances_dir / f"{UNIVERSE}.gpkg", layer="terminais")

    gpkg = write_gpkg(
        output_dir / "lot_assignments.gpkg",
        {"itinerarios": itinerarios, "envoltorias": envoltorias,
         "terminais": terminais},
    )
    manifest = build_manifest(
        runs_path, instances_dir, aligned,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provenance=provenance,
    )
    manifest_path = atomic_write_text(
        output_dir / "lot_maps_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    styles = write_style_files(output_dir / "qml", panels=style_panels(),
                               nesting=nesting_entries(), writer=atomic_write_text)
    return {
        "gpkg": str(gpkg), "manifest": str(manifest_path),
        "qml": sorted(str(path) for path in styles.values()),
        "combinations": len(aligned), "envoltorias": len(envoltorias),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI de exportação: só os três diretórios são configuráveis.

    Os limiares de recusa (`expected_runs`, `expected_seeds`, `combinations`)
    não viram flags: a spec manda recusar recorte incompleto, e uma flag
    deixaria essa recusa desligável por quem chama a CLI.
    """

    parser = argparse.ArgumentParser(
        description="Exportação cartográfica dos agrupamentos (B15)"
    )
    parser.add_argument("--tables-dir", type=Path, default=Path("results/tables"))
    parser.add_argument("--instances-dir", type=Path, default=Path("data/instances"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/maps"))
    arguments = parser.parse_args(argv)
    try:
        report = export(tables_dir=arguments.tables_dir,
                        instances_dir=arguments.instances_dir,
                        output_dir=arguments.output_dir)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except ConfigurationError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
