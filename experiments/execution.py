"""Planejamento e execução retomável de campanhas."""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import multiprocessing
from pathlib import Path
from typing import Any

from metaheuristica.errors import ConfigurationError

from experiments.config import CampaignConfig
from experiments.provenance import capture_provenance
from experiments.scenarios import Scenario, expand_scenarios, select_scenario
from experiments.storage import (
    ScenarioState, artifact_paths, atomic_write_json, build_result_document,
    classify, record_failure,
)


@dataclass(frozen=True, slots=True)
class CampaignPlan:
    expected: int
    completed: int
    failed: int
    pending: int
    selected: tuple[Scenario, ...]
    by_algorithm: dict[str, int]
    by_instance: dict[str, int]
    by_k: dict[int, int]


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    expected: int
    selected: int
    skipped: int
    succeeded: int
    failed: int
    interrupted: bool = False


def build_plan(
    config: CampaignConfig,
    *,
    scenario_id: str | None = None,
    max_runs: int | None = None,
) -> CampaignPlan:
    if max_runs is not None and (
        isinstance(max_runs, bool) or not isinstance(max_runs, int) or max_runs <= 0
    ):
        raise ConfigurationError("max-runs deve ser inteiro positivo")
    scenarios = expand_scenarios(config)
    if scenario_id is not None:
        selected_scope = (select_scenario(scenarios, scenario_id),)
    else:
        selected_scope = scenarios
    output_root = config.repository_root / config.output_root
    states = {
        scenario.scenario_id: classify(
            artifact_paths(output_root, config.purpose, scenario), scenario
        )
        for scenario in scenarios
    }
    pending_selected = tuple(
        scenario for scenario in selected_scope
        if states[scenario.scenario_id] is not ScenarioState.COMPLETED
    )
    if max_runs is not None:
        pending_selected = pending_selected[:max_runs]
    by_algorithm: dict[str, int] = {}
    by_instance: dict[str, int] = {}
    by_k: dict[int, int] = {}
    for scenario in scenarios:
        algorithm = scenario.payload["algorithm"]
        instance = scenario.payload["instance"]["name"]
        k = scenario.payload["k"]
        by_algorithm[algorithm] = by_algorithm.get(algorithm, 0) + 1
        by_instance[instance] = by_instance.get(instance, 0) + 1
        by_k[k] = by_k.get(k, 0) + 1
    return CampaignPlan(
        expected=len(scenarios),
        completed=sum(state is ScenarioState.COMPLETED for state in states.values()),
        failed=sum(state is ScenarioState.FAILED for state in states.values()),
        pending=sum(state is ScenarioState.PENDING for state in states.values()),
        selected=pending_selected,
        by_algorithm=by_algorithm,
        by_instance=by_instance,
        by_k=by_k,
    )


def _publish_success(
    config: CampaignConfig,
    scenario: Scenario,
    worker_output: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    combined_provenance = dict(provenance)
    combined_provenance["thread_limits"] = worker_output["thread_limits"]
    document = build_result_document(
        scenario, worker_output["result"], combined_provenance,
        started_at=worker_output["started_at"],
        finished_at=worker_output["finished_at"],
    )
    paths = artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    )
    atomic_write_json(paths.result, document)


def execute_campaign(
    config: CampaignConfig,
    *,
    workers: int = 1,
    scenario_id: str | None = None,
    max_runs: int | None = None,
    fail_fast: bool = False,
    allow_dirty: bool = False,
    allow_unversioned: bool = False,
) -> ExecutionSummary:
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ConfigurationError("workers deve ser inteiro positivo")
    plan = build_plan(config, scenario_id=scenario_id, max_runs=max_runs)
    provenance = capture_provenance(
        config.repository_root,
        allow_dirty=allow_dirty,
        allow_unversioned=allow_unversioned,
    )
    succeeded = 0
    failures = 0
    output_root = config.repository_root / config.output_root

    if workers == 1:
        from experiments.worker import run_scenario
        for scenario in plan.selected:
            try:
                output = run_scenario(scenario, str(config.repository_root))
                _publish_success(config, scenario, output, provenance)
                succeeded += 1
            except KeyboardInterrupt:
                return ExecutionSummary(
                    plan.expected, len(plan.selected), plan.completed,
                    succeeded, failures, True,
                )
            except Exception as error:
                record_failure(
                    artifact_paths(output_root, config.purpose, scenario), scenario, error
                )
                failures += 1
                if fail_fast:
                    break
    else:
        context = multiprocessing.get_context("spawn")
        from experiments.worker import run_scenario
        with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
            futures: dict[Future[dict[str, Any]], Scenario] = {
                executor.submit(run_scenario, scenario, str(config.repository_root)): scenario
                for scenario in plan.selected
            }
            try:
                for future in as_completed(futures):
                    scenario = futures[future]
                    try:
                        _publish_success(config, scenario, future.result(), provenance)
                        succeeded += 1
                    except Exception as error:
                        record_failure(
                            artifact_paths(output_root, config.purpose, scenario),
                            scenario, error,
                        )
                        failures += 1
                        if fail_fast:
                            for pending in futures:
                                pending.cancel()
                            break
            except KeyboardInterrupt:
                for future in futures:
                    future.cancel()
                return ExecutionSummary(
                    plan.expected, len(plan.selected), plan.completed,
                    succeeded, failures, True,
                )
    return ExecutionSummary(
        plan.expected, len(plan.selected), plan.completed,
        succeeded, failures, False,
    )
