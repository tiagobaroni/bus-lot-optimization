"""Particionamento operacional imutável do benchmark principal."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.scenarios import Scenario, canonical_json, expand_scenarios


BATCH_SEEDS: tuple[tuple[int, ...], ...] = tuple(
    tuple(range(start, start + 6)) for start in (10, 16, 22, 28, 34)
)


@dataclass(frozen=True, slots=True)
class BenchmarkSelection:
    batch: int
    seeds: tuple[int, ...]
    scenarios: tuple[Scenario, ...]
    algorithm: str | None = None
    instance: str | None = None
    k: int | None = None

    @property
    def subgroup(self) -> bool:
        return self.algorithm is not None

    @property
    def name(self) -> str:
        if not self.subgroup:
            return f"batch-{self.batch:02d}"
        return f"batch-{self.batch:02d}_{self.algorithm}_{self.instance}_k{self.k}"

    @property
    def ids_sha256(self) -> str:
        return sha256(
            canonical_json(sorted(item.scenario_id for item in self.scenarios))
        ).hexdigest()


def _batch_seeds(batch: int) -> tuple[int, ...]:
    if isinstance(batch, bool) or not isinstance(batch, int) or not 1 <= batch <= 5:
        raise ConfigurationError("lote deve ser inteiro entre 1 e 5")
    return BATCH_SEEDS[batch - 1]


def select_benchmark(
    config: CampaignConfig,
    *,
    batch: int,
    algorithm: str | None = None,
    instance: str | None = None,
    k: int | None = None,
) -> BenchmarkSelection:
    """Seleciona um lote completo ou um subgrupo completo de seis seeds."""
    if config.purpose != "benchmark":
        raise ConfigurationError("seleção em lotes exige finalidade benchmark")
    filters = (algorithm, instance, k)
    if any(value is not None for value in filters) and not all(
        value is not None for value in filters
    ):
        raise ConfigurationError(
            "subgrupo exige conjuntamente algoritmo, instância e K"
        )
    seeds = _batch_seeds(batch)
    all_scenarios = expand_scenarios(config)
    configured_seeds = {item.payload["seed"] for item in all_scenarios}
    if not set(seeds) <= configured_seeds:
        raise ConfigurationError(f"seeds do lote {batch} ausentes da configuração")
    selected = tuple(
        item for item in all_scenarios
        if item.payload["seed"] in seeds
        and (algorithm is None or item.payload["algorithm"] == algorithm)
        and (instance is None or item.payload["instance"]["name"] == instance)
        and (k is None or item.payload["k"] == k)
    )
    expected = 6 if algorithm is not None else 324
    if len(selected) != expected:
        kind = "subgrupo" if algorithm is not None else "lote"
        raise ConfigurationError(
            f"{kind} incompleto: esperado {expected}, obtido {len(selected)}"
        )
    return BenchmarkSelection(batch, seeds, selected, algorithm, instance, k)


def benchmark_subgroups(config: CampaignConfig, batch: int) -> tuple[BenchmarkSelection, ...]:
    batch_selection = select_benchmark(config, batch=batch)
    grouped: dict[tuple[str, str, int], list[Scenario]] = {}
    for scenario in batch_selection.scenarios:
        key = (
            scenario.payload["algorithm"],
            scenario.payload["instance"]["name"],
            scenario.payload["k"],
        )
        grouped.setdefault(key, []).append(scenario)
    groups = tuple(
        BenchmarkSelection(
            batch, batch_selection.seeds, tuple(grouped[key]), key[0], key[1], key[2]
        )
        for key in sorted(grouped)
    )
    if len(groups) != 54:
        raise ConfigurationError(f"lote deve conter 54 subgrupos, obteve {len(groups)}")
    if any(len(group.scenarios) != 6 for group in groups):
        raise ConfigurationError("lote contém subgrupo incompleto")
    return groups


def validate_benchmark_partition(config: CampaignConfig) -> dict[str, object]:
    scenarios = expand_scenarios(config)
    if len(scenarios) != 1_620:
        raise ConfigurationError(
            f"benchmark deve conter 1620 cenários, obteve {len(scenarios)}"
        )
    batches = tuple(select_benchmark(config, batch=index) for index in range(1, 6))
    flattened = [item.scenario_id for batch in batches for item in batch.scenarios]
    expected = {item.scenario_id for item in scenarios}
    if len(flattened) != len(set(flattened)) or set(flattened) != expected:
        raise ConfigurationError("lotes não formam partição exata do benchmark")
    subgroups = tuple(
        subgroup for index in range(1, 6) for subgroup in benchmark_subgroups(config, index)
    )
    subgroup_ids = [item.scenario_id for group in subgroups for item in group.scenarios]
    if len(subgroup_ids) != len(set(subgroup_ids)) or set(subgroup_ids) != expected:
        raise ConfigurationError("subgrupos não formam partição exata do benchmark")
    return {
        "scenarios": len(scenarios),
        "batches": len(batches),
        "scenarios_per_batch": 324,
        "subgroups": len(subgroups),
        "subgroups_per_batch": 54,
        "scenarios_per_subgroup": 6,
        "scenario_ids_sha256": sha256(canonical_json(sorted(expected))).hexdigest(),
    }


def order_selection(
    selection: BenchmarkSelection, ordered: Iterable[Scenario]
) -> BenchmarkSelection:
    ordered_tuple = tuple(ordered)
    if {item.scenario_id for item in ordered_tuple} != {
        item.scenario_id for item in selection.scenarios
    } or len(ordered_tuple) != len(selection.scenarios):
        raise ConfigurationError("ordenação não corresponde exatamente à seleção")
    return BenchmarkSelection(
        selection.batch, selection.seeds, ordered_tuple,
        selection.algorithm, selection.instance, selection.k,
    )
