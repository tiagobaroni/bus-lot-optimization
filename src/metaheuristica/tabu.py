"""Busca Tabu com movimentos de realocação entre lotes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from metaheuristica.canonical import canonicalize_solution, validate_k, validate_solution
from metaheuristica.errors import ConfigurationError, SolutionValidationError
from metaheuristica.metrics import COST_TOLERANCE, OptimizationResult, RunConfig
from metaheuristica.optimizer import OptimizationContext, execute_optimizer
from metaheuristica.problem import EvaluationResult, ProblemInstance


IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class TabuConfig:
    """Hiperparâmetros específicos da Busca Tabu."""

    tabu_tenure: int
    neighborhood_size: int
    stagnation_limit: int

    def __post_init__(self) -> None:
        for name, value in (
            ("tabu_tenure", self.tabu_tenure),
            ("neighborhood_size", self.neighborhood_size),
            ("stagnation_limit", self.stagnation_limit),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"{name} deve ser um inteiro positivo")


@dataclass(frozen=True, slots=True, order=True)
class TabuMove:
    """Realocação de uma unidade entre dois lotes estáveis."""

    unit_index: int
    source_lot: int
    target_lot: int

    def reversed(self) -> TabuMove:
        return TabuMove(self.unit_index, self.target_lot, self.source_lot)


@dataclass(frozen=True, slots=True)
class _EvaluatedCandidate:
    move: TabuMove
    solution: IntArray
    canonical_key: tuple[int, ...]
    evaluation: EvaluationResult
    was_tabu: bool
    aspiration: bool

    @property
    def admissible(self) -> bool:
        return not self.was_tabu or self.aspiration


class _TabuMemory:
    """Expirações de reversões medidas em movimentos aceitos."""

    __slots__ = ("_expirations",)

    def __init__(self) -> None:
        self._expirations: dict[TabuMove, int] = {}

    def register(self, move: TabuMove, *, accepted_moves: int, tenure: int) -> None:
        self._expirations[move.reversed()] = accepted_moves + tenure

    def purge(self, *, accepted_moves: int) -> None:
        expired = sorted(
            move
            for move, expiration in self._expirations.items()
            if expiration <= accepted_moves
        )
        for move in expired:
            del self._expirations[move]

    def is_tabu(self, move: TabuMove, *, accepted_moves: int) -> bool:
        return self._expirations.get(move, accepted_moves) > accepted_moves

    def clear(self) -> None:
        self._expirations.clear()

    @property
    def entries(self) -> tuple[tuple[TabuMove, int], ...]:
        return tuple(sorted(self._expirations.items()))


def _balanced_random_solution(
    n_units: int, k: int, rng: np.random.Generator
) -> IntArray:
    validate_k(k, n_units)
    permutation = rng.permutation(n_units)
    solution = np.empty(n_units, dtype=np.int64)
    solution[permutation] = np.arange(n_units, dtype=np.int64) % k
    return solution


def _enumerate_valid_moves(solution: Any, *, k: int) -> tuple[TabuMove, ...]:
    labels = validate_solution(solution, n_units=len(solution), k=k)
    lot_sizes = np.bincount(labels, minlength=k)
    moves: list[TabuMove] = []
    for unit_index, source_value in enumerate(labels):
        source = int(source_value)
        if lot_sizes[source] <= 1:
            continue
        for target in range(k):
            if target != source:
                moves.append(TabuMove(unit_index, source, target))
    return tuple(moves)


def _sample_moves(
    moves: tuple[TabuMove, ...], size: int, rng: np.random.Generator
) -> tuple[TabuMove, ...]:
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ConfigurationError("tamanho da vizinhança deve ser um inteiro positivo")
    count = min(size, len(moves))
    if count == 0:
        return ()
    positions = rng.permutation(len(moves))[:count]
    return tuple(moves[int(position)] for position in positions)


def _apply_move(solution: Any, move: TabuMove, *, k: int) -> IntArray:
    labels = validate_solution(solution, n_units=len(solution), k=k)
    if not isinstance(move, TabuMove):
        raise SolutionValidationError("movimento deve ser TabuMove")
    if move.unit_index < 0 or move.unit_index >= len(labels):
        raise SolutionValidationError("índice da unidade fora do intervalo")
    if move.source_lot < 0 or move.source_lot >= k:
        raise SolutionValidationError("lote de origem fora do intervalo")
    if move.target_lot < 0 or move.target_lot >= k:
        raise SolutionValidationError("lote de destino fora do intervalo")
    if move.source_lot == move.target_lot:
        raise SolutionValidationError("origem e destino devem ser diferentes")
    if int(labels[move.unit_index]) != move.source_lot:
        raise SolutionValidationError("unidade não pertence ao lote de origem informado")
    if int(np.count_nonzero(labels == move.source_lot)) <= 1:
        raise SolutionValidationError("movimento esvaziaria o lote de origem")
    candidate = np.array(labels, dtype=np.int64, copy=True)
    candidate[move.unit_index] = move.target_lot
    return candidate


def _candidate_is_better(
    candidate: _EvaluatedCandidate, incumbent: _EvaluatedCandidate
) -> bool:
    difference = candidate.evaluation.total_cost - incumbent.evaluation.total_cost
    if difference < -COST_TOLERANCE:
        return True
    if abs(difference) <= COST_TOLERANCE:
        if candidate.canonical_key != incumbent.canonical_key:
            return candidate.canonical_key < incumbent.canonical_key
        return candidate.move < incumbent.move
    return False


def _select_best_admissible(
    candidates: list[_EvaluatedCandidate],
) -> _EvaluatedCandidate | None:
    best: _EvaluatedCandidate | None = None
    for candidate in candidates:
        if not candidate.admissible:
            continue
        if best is None or _candidate_is_better(candidate, best):
            best = candidate
    return best


@dataclass(slots=True)
class _TabuDiagnostics:
    iterations_completed: int = 0
    accepted_moves: int = 0
    restarts: int = 0
    aspiration_acceptances: int = 0
    tabu_candidates_evaluated: int = 0
    global_improvements: int = 0

    def publish(self, context: OptimizationContext) -> None:
        context.update_diagnostics(
            iterations_completed=self.iterations_completed,
            accepted_moves=self.accepted_moves,
            restarts=self.restarts,
            aspiration_acceptances=self.aspiration_acceptances,
            tabu_candidates_evaluated=self.tabu_candidates_evaluated,
            global_improvements=self.global_improvements,
        )


def _strict_improvement(before: float | None, after: float | None) -> bool:
    return before is not None and after is not None and after < before - COST_TOLERANCE


def _aspiration_applies(
    *, was_tabu: bool, candidate_cost: float, global_best_cost: float | None
) -> bool:
    return (
        was_tabu
        and global_best_cost is not None
        and candidate_cost < global_best_cost - COST_TOLERANCE
    )


def _incumbent_cost(context: OptimizationContext) -> float | None:
    incumbent = context.incumbent_evaluation
    return None if incumbent is None else incumbent.total_cost


def _tabu_search(
    context: OptimizationContext,
    config: TabuConfig,
    *,
    n_units: int,
    k: int,
) -> None:
    diagnostics = _TabuDiagnostics()
    diagnostics.publish(context)
    memory = _TabuMemory()
    stagnation = 0

    current = _balanced_random_solution(n_units, k, context.rng)
    context.evaluate(current)

    def evaluate_restart() -> IntArray:
        nonlocal stagnation
        restart = _balanced_random_solution(n_units, k, context.rng)
        before = _incumbent_cost(context)
        evaluations_before = context.evaluations
        try:
            context.evaluate(restart)
        finally:
            if context.evaluations > evaluations_before:
                after = _incumbent_cost(context)
                if _strict_improvement(before, after):
                    diagnostics.global_improvements += 1
                diagnostics.publish(context)
        memory.clear()
        stagnation = 0
        diagnostics.restarts += 1
        diagnostics.iterations_completed += 1
        diagnostics.publish(context)
        return restart

    while True:
        memory.purge(accepted_moves=diagnostics.accepted_moves)
        moves = _enumerate_valid_moves(current, k=k)
        sampled = _sample_moves(moves, config.neighborhood_size, context.rng)
        if not sampled:
            current = evaluate_restart()
            continue

        candidates: list[_EvaluatedCandidate] = []
        iteration_improved = False
        for move in sampled:
            candidate_solution = _apply_move(current, move, k=k)
            was_tabu = memory.is_tabu(
                move, accepted_moves=diagnostics.accepted_moves
            )
            before = _incumbent_cost(context)
            evaluations_before = context.evaluations
            try:
                evaluation = context.evaluate(candidate_solution)
            finally:
                if context.evaluations > evaluations_before:
                    if was_tabu:
                        diagnostics.tabu_candidates_evaluated += 1
                    after = _incumbent_cost(context)
                    if _strict_improvement(before, after):
                        diagnostics.global_improvements += 1
                        iteration_improved = True
                    diagnostics.publish(context)
            aspiration = _aspiration_applies(
                was_tabu=was_tabu,
                candidate_cost=evaluation.total_cost,
                global_best_cost=before,
            )
            canonical = canonicalize_solution(
                candidate_solution, n_units=n_units, k=k
            )
            candidates.append(
                _EvaluatedCandidate(
                    move=move,
                    solution=candidate_solution,
                    canonical_key=tuple(int(label) for label in canonical),
                    evaluation=evaluation,
                    was_tabu=was_tabu,
                    aspiration=aspiration,
                )
            )

        winner = _select_best_admissible(candidates)
        if winner is None:
            current = evaluate_restart()
            continue

        current = winner.solution
        diagnostics.accepted_moves += 1
        memory.register(
            winner.move,
            accepted_moves=diagnostics.accepted_moves,
            tenure=config.tabu_tenure,
        )
        if winner.was_tabu and winner.aspiration:
            diagnostics.aspiration_acceptances += 1
        stagnation = 0 if iteration_improved else stagnation + 1
        diagnostics.iterations_completed += 1
        diagnostics.publish(context)

        if stagnation >= config.stagnation_limit:
            current = evaluate_restart()


def run_tabu(
    instance: ProblemInstance,
    run_config: RunConfig,
    tabu_config: TabuConfig,
) -> OptimizationResult:
    """Executa a Busca Tabu pelo contrato comum dos otimizadores."""

    if not isinstance(tabu_config, TabuConfig):
        raise ConfigurationError("tabu_config deve ser TabuConfig")

    def search(context: OptimizationContext, config: TabuConfig) -> None:
        _tabu_search(
            context,
            config,
            n_units=instance.n_units,
            k=run_config.k,
        )

    return execute_optimizer(
        instance,
        run_config,
        tabu_config,
        algorithm="tabu",
        search=search,
    )
