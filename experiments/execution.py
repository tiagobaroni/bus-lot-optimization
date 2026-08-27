"""Planejamento e execução retomável de campanhas."""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
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
    classify, record_failure, record_interrupted,
)
from experiments.provenance import utc_now


@dataclass(frozen=True, slots=True)
class CampaignPlan:
    expected: int
    completed: int
    failed: int
    pending: int
    skipped: int
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
    selected_scenarios: tuple[Scenario, ...] | None = None,
) -> CampaignPlan:
    if max_runs is not None and (
        isinstance(max_runs, bool) or not isinstance(max_runs, int) or max_runs <= 0
    ):
        raise ConfigurationError("max-runs deve ser inteiro positivo")
    scenarios = expand_scenarios(config)
    if scenario_id is not None and selected_scenarios is not None:
        raise ConfigurationError("scenario-id e seleção explícita são incompatíveis")
    if scenario_id is not None:
        selected_scope = (select_scenario(scenarios, scenario_id),)
    elif selected_scenarios is not None:
        known = {item.scenario_id: item for item in scenarios}
        identifiers = [item.scenario_id for item in selected_scenarios]
        if len(identifiers) != len(set(identifiers)):
            raise ConfigurationError("seleção explícita contém IDs duplicados")
        if any(identifier not in known for identifier in identifiers):
            raise ConfigurationError("seleção explícita contém cenário desconhecido")
        selected_scope = tuple(known[identifier] for identifier in identifiers)
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
        # `completed` conta a campanha inteira e `skipped` conta apenas o escopo
        # selecionado: são números diferentes sempre que a seleção é um lote, e
        # confundi-los faz o diário operacional registrar cenários que a sessão
        # nunca teve diante de si.
        skipped=sum(
            states[scenario.scenario_id] is ScenarioState.COMPLETED
            for scenario in selected_scope
        ),
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
    if config.frozen_parameters_sha256 is not None:
        combined_provenance["frozen_parameters_sha256"] = (
            config.frozen_parameters_sha256
        )
    document = build_result_document(
        scenario, worker_output["result"], combined_provenance,
        started_at=worker_output["started_at"],
        finished_at=worker_output["finished_at"],
    )
    paths = artifact_paths(
        config.repository_root / config.output_root, config.purpose, scenario
    )
    atomic_write_json(paths.result, document)


def _write_interruption_report(config: CampaignConfig, *, workers: int) -> None:
    plan = build_plan(config)
    output_root = config.repository_root / config.output_root
    temporary_files = sorted(
        str(path.relative_to(config.repository_root))
        for directory in (
            output_root / "raw" / config.purpose,
            output_root / "failures" / config.purpose,
        )
        if directory.exists()
        for path in directory.glob("*.tmp")
    )
    scenarios = expand_scenarios(config)
    states = {
        scenario.scenario_id: classify(
            artifact_paths(output_root, config.purpose, scenario), scenario
        ).value
        for scenario in scenarios
    }
    atomic_write_json(
        output_root / "operational" / config.name / "interruption.json",
        {
            "schema_version": 1,
            "campaign": config.name,
            "purpose": config.purpose,
            "at": utc_now(),
            "workers": workers,
            "expected": plan.expected,
            "completed": plan.completed,
            "failed": plan.failed,
            "pending": plan.pending,
            "states": states,
            "temporary_files": temporary_files,
        },
    )


def execute_campaign(
    config: CampaignConfig,
    *,
    workers: int = 1,
    scenario_id: str | None = None,
    max_runs: int | None = None,
    selected_scenarios: tuple[Scenario, ...] | None = None,
    fail_fast: bool = False,
    allow_dirty: bool = False,
    allow_unversioned: bool = False,
) -> ExecutionSummary:
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ConfigurationError("workers deve ser inteiro positivo")
    plan = build_plan(
        config, scenario_id=scenario_id, max_runs=max_runs,
        selected_scenarios=selected_scenarios,
    )
    provenance = capture_provenance(
        config.repository_root,
        allow_dirty=allow_dirty,
        allow_unversioned=allow_unversioned,
    )
    provenance["campaign_workers"] = workers
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
                _write_interruption_report(config, workers=workers)
                return ExecutionSummary(
                    plan.expected, len(plan.selected), plan.skipped,
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
        executor = ProcessPoolExecutor(max_workers=workers, mp_context=context)
        interrupted = False
        broken = False
        try:
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
                    except BrokenProcessPool as error:
                        # Morte de worker por sinal ou pelo matador por falta de
                        # memória não é falha algorítmica do cenário: registra
                        # interrupção, sem consumir a tentativa única, e encerra
                        # o lote para que a retomada reexecute os pendentes.
                        record_interrupted(
                            artifact_paths(output_root, config.purpose, scenario),
                            scenario, error,
                        )
                        broken = True
                        break
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
                interrupted = True
                for future in futures:
                    future.cancel()
                terminate = getattr(executor, "terminate_workers", None)
                if terminate is not None:
                    terminate()
                else:
                    executor.shutdown(wait=False, cancel_futures=True)
                _write_interruption_report(config, workers=workers)
                return ExecutionSummary(
                    plan.expected, len(plan.selected), plan.skipped,
                    succeeded, failures, True,
                )
        finally:
            if not interrupted:
                executor.shutdown(wait=True, cancel_futures=False)
        if broken:
            _write_interruption_report(config, workers=workers)
            return ExecutionSummary(
                plan.expected, len(plan.selected), plan.skipped,
                succeeded, failures, True,
            )
    return ExecutionSummary(
        plan.expected, len(plan.selected), plan.skipped,
        succeeded, failures, False,
    )
