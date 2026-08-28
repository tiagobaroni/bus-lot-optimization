"""Particle Swarm Optimization combinatório com Random Keys."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np
from numpy.typing import NDArray

from metaheuristica.canonical import canonicalize_solution, validate_k, validate_solution
from metaheuristica.errors import (
    BudgetExhausted,
    ConfigurationError,
    EvaluationLimitReached,
    RepairBudgetExhausted,
    SolutionValidationError,
)
from metaheuristica.metrics import COST_TOLERANCE, OptimizationResult, RunConfig
from metaheuristica.optimizer import OptimizationContext, execute_optimizer
from metaheuristica.problem import EvaluationResult, ProblemInstance
from metaheuristica.repair import repair_empty_lots_with_evaluation


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
VELOCITY_LIMIT = 0.5


@dataclass(frozen=True, slots=True)
class PsoConfig:
    """Hiperparâmetros específicos do PSO."""

    n_particles: int
    inertia: float
    cognitive: float
    social: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.n_particles, bool)
            or not isinstance(self.n_particles, int)
            or self.n_particles <= 0
        ):
            raise ConfigurationError("n_particles deve ser um inteiro positivo")
        for name, value in (
            ("inertia", self.inertia),
            ("cognitive", self.cognitive),
            ("social", self.social),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigurationError(f"{name} deve ser numérico")
            numeric = float(value)
            if not isfinite(numeric):
                raise ConfigurationError(f"{name} deve ser finito")
            if name == "inertia" and not 0.0 <= numeric <= 1.0:
                raise ConfigurationError("inertia deve estar no intervalo [0, 1]")
            if name != "inertia" and numeric <= 0.0:
                raise ConfigurationError(f"{name} deve ser positivo")
            object.__setattr__(self, name, numeric)


@dataclass(slots=True)
class _Best:
    position: FloatArray
    solution: IntArray
    evaluation: EvaluationResult


@dataclass(slots=True)
class _Particle:
    position: FloatArray
    velocity: FloatArray
    pbest: _Best | None = None


@dataclass(frozen=True, slots=True)
class _Trial:
    position: FloatArray
    velocity: FloatArray
    position_clips: int
    velocity_clips: int


@dataclass(slots=True)
class _PsoDiagnostics:
    iterations_completed: int = 0
    particles_evaluated: int = 0
    repair_attempts: int = 0
    repairs_completed: int = 0
    repair_evaluations: int = 0
    personal_best_updates: int = 0
    global_best_updates: int = 0
    strict_global_improvements: int = 0
    position_clips: int = 0
    velocity_clips: int = 0

    def publish(self, context: OptimizationContext) -> None:
        context.update_diagnostics(
            iterations_completed=self.iterations_completed,
            particles_evaluated=self.particles_evaluated,
            repair_attempts=self.repair_attempts,
            repairs_completed=self.repairs_completed,
            repair_evaluations=self.repair_evaluations,
            personal_best_updates=self.personal_best_updates,
            global_best_updates=self.global_best_updates,
            strict_global_improvements=self.strict_global_improvements,
            position_clips=self.position_clips,
            velocity_clips=self.velocity_clips,
        )


def decode_position(position: Any, *, n_units: int, k: int) -> IntArray:
    """Decodifica chaves contínuas em rótulos, sem reparar ou canonicalizar."""

    validate_k(k, n_units)
    array = np.asarray(position)
    if array.dtype != np.dtype(np.float64):
        raise SolutionValidationError("posição deve usar dtype float64")
    if array.ndim != 1 or array.shape != (n_units,):
        raise SolutionValidationError(f"posição deve ter dimensão ({n_units},)")
    if not np.isfinite(array).all():
        raise SolutionValidationError("posição deve conter somente valores finitos")
    if np.any(array < 0.0) or np.any(array > 1.0):
        raise SolutionValidationError("posição deve estar no intervalo [0, 1]")
    labels = np.minimum(np.floor(array * k).astype(np.int64), k - 1)
    return labels


def _initial_particle(n_units: int, k: int, rng: np.random.Generator) -> _Particle:
    permutation = rng.permutation(n_units)
    labels = np.empty(n_units, dtype=np.int64)
    labels[permutation] = np.arange(n_units, dtype=np.int64) % k
    fractions = rng.random(n_units)
    position = (labels.astype(np.float64) + fractions) / k
    velocity = rng.uniform(-VELOCITY_LIMIT, VELOCITY_LIMIT, size=n_units)
    if not np.array_equal(decode_position(position, n_units=n_units, k=k), labels):
        raise ConfigurationError("posição inicial não decodifica na alocação gerada")
    return _Particle(position.copy(), velocity.astype(np.float64, copy=False).copy())


def _copy_best(
    position: FloatArray, solution: IntArray, evaluation: EvaluationResult
) -> _Best:
    return _Best(position.copy(), np.array(solution, dtype=np.int64, copy=True), evaluation)


def _best_comparison(candidate: _Best, incumbent: _Best) -> tuple[bool, bool]:
    difference = candidate.evaluation.total_cost - incumbent.evaluation.total_cost
    if difference < -COST_TOLERANCE:
        return True, True
    if abs(difference) > COST_TOLERANCE:
        return False, False
    candidate_solution = tuple(int(value) for value in candidate.solution)
    incumbent_solution = tuple(int(value) for value in incumbent.solution)
    if candidate_solution != incumbent_solution:
        return candidate_solution < incumbent_solution, False
    return tuple(candidate.position) < tuple(incumbent.position), False


def _trial_state(
    particle: _Particle,
    gbest_position: FloatArray,
    config: PsoConfig,
    rng: np.random.Generator,
) -> _Trial:
    if particle.pbest is None:
        raise ConfigurationError("partícula sem melhor pessoal")
    r1 = rng.random(particle.position.shape)
    r2 = rng.random(particle.position.shape)
    raw_velocity = (
        config.inertia * particle.velocity
        + config.cognitive * r1 * (particle.pbest.position - particle.position)
        + config.social * r2 * (gbest_position - particle.position)
    )
    velocity_clips = int(
        np.count_nonzero(
            (raw_velocity < -VELOCITY_LIMIT) | (raw_velocity > VELOCITY_LIMIT)
        )
    )
    # A velocidade saturada é a que se aplica à posição: o limite da seção 16 é do
    # passo, não apenas do estado herdado pelo termo de inércia da iteração
    # seguinte.
    velocity = np.clip(raw_velocity, -VELOCITY_LIMIT, VELOCITY_LIMIT)
    raw_position = particle.position + velocity
    position_clips = int(np.count_nonzero((raw_position < 0.0) | (raw_position > 1.0)))
    return _Trial(
        np.clip(raw_position, 0.0, 1.0),
        velocity,
        position_clips,
        velocity_clips,
    )


def _project_position(
    position: Any, original_labels: Any, repaired_solution: Any, *, k: int
) -> FloatArray:
    x = np.asarray(position, dtype=np.float64)
    original = np.asarray(original_labels, dtype=np.int64)
    repaired = np.asarray(repaired_solution, dtype=np.int64)
    if x.ndim != 1 or original.shape != x.shape or repaired.shape != x.shape:
        raise SolutionValidationError("projeção requer vetores alinhados")
    fractions = k * x - original
    fractions = np.clip(fractions, 0.0, np.nextafter(1.0, 0.0))
    projected = (repaired.astype(np.float64) + fractions) / k
    for index, label_value in enumerate(repaired):
        label = int(label_value)
        midpoint = (label + 0.5) / k
        for _ in range(16):
            decoded_label = min(int(np.floor(k * projected[index])), k - 1)
            if decoded_label == label:
                break
            projected[index] = np.nextafter(projected[index], midpoint)
        else:
            projected[index] = midpoint
    decoded = decode_position(projected, n_units=len(projected), k=k)
    if not np.array_equal(decoded, repaired):
        raise SolutionValidationError("posição projetada não decodifica a solução reparada")
    return projected


def _canonical_candidate(
    position: FloatArray, labels: IntArray, *, n_units: int, k: int
) -> tuple[FloatArray, IntArray]:
    canonical = canonicalize_solution(labels, n_units=n_units, k=k)
    if np.array_equal(labels, canonical):
        return position.copy(), canonical
    return _project_position(position, labels, canonical, k=k), canonical


def _pso_search(
    context: OptimizationContext,
    config: PsoConfig,
    *,
    instance: ProblemInstance,
    run_config: RunConfig,
) -> None:
    diagnostics = _PsoDiagnostics()
    diagnostics.publish(context)
    particles = [
        _initial_particle(instance.n_units, run_config.k, context.rng)
        for _ in range(config.n_particles)
    ]
    gbest: _Best | None = None

    for particle in particles:
        labels = decode_position(
            particle.position, n_units=instance.n_units, k=run_config.k
        )
        position, canonical = _canonical_candidate(
            particle.position, labels, n_units=instance.n_units, k=run_config.k
        )
        try:
            evaluation = context.evaluate(canonical)
        except EvaluationLimitReached as exhausted:
            evaluation = _limit_result(exhausted)
            particle.position = position
            particle.pbest = _copy_best(position, canonical, evaluation)
            candidate = _copy_best(position, canonical, evaluation)
            if gbest is None or _best_comparison(candidate, gbest)[0]:
                gbest = candidate
            diagnostics.particles_evaluated += 1
            _verify_diagnostics(context, diagnostics)
            diagnostics.publish(context)
            raise
        particle.position = position
        particle.pbest = _copy_best(position, canonical, evaluation)
        candidate = _copy_best(position, canonical, evaluation)
        if gbest is None or _best_comparison(candidate, gbest)[0]:
            gbest = candidate
        diagnostics.particles_evaluated += 1
        diagnostics.publish(context)

    if gbest is None or any(particle.pbest is None for particle in particles):
        raise ConfigurationError("população inicial sem melhores válidos")

    while True:
        gbest_snapshot = gbest.position.copy()
        trials = [
            _trial_state(particle, gbest_snapshot, config, context.rng)
            for particle in particles
        ]
        diagnostics.position_clips += sum(trial.position_clips for trial in trials)
        diagnostics.velocity_clips += sum(trial.velocity_clips for trial in trials)
        diagnostics.publish(context)

        for particle, trial in zip(particles, trials):
            decoded = decode_position(
                trial.position, n_units=instance.n_units, k=run_config.k
            )
            position = trial.position.copy()
            solution: IntArray
            reused: EvaluationResult | None = None
            if np.count_nonzero(np.bincount(decoded, minlength=run_config.k)) < run_config.k:
                diagnostics.repair_attempts += 1
                before = context.evaluations
                try:
                    repaired, reused = repair_empty_lots_with_evaluation(
                        decoded, context
                    )
                except RepairBudgetExhausted:
                    diagnostics.repair_evaluations += context.evaluations - before
                    _verify_diagnostics(context, diagnostics)
                    diagnostics.publish(context)
                    raise
                # A4: o candidato vencedor do reparo é o próprio estado final e já
                # foi avaliado pela mesma `_evaluate_labels`. Reavaliá-lo por
                # `context.evaluate` gastava uma segunda unidade de orçamento pela
                # mesma solução. A unidade reaproveitada muda de coluna, do reparo
                # para a partícula, e por isso a identidade
                # `particles_evaluated + repair_evaluations == evaluations`, que
                # `_verify_diagnostics` guarda, continua valendo.
                diagnostics.repair_evaluations += (
                    context.evaluations - before - int(reused is not None)
                )
                diagnostics.repairs_completed += 1
                position = _project_position(
                    position, decoded, repaired, k=run_config.k
                )
                solution = repaired
            else:
                position, solution = _canonical_candidate(
                    position,
                    decoded,
                    n_units=instance.n_units,
                    k=run_config.k,
                )
            validate_solution(solution, n_units=instance.n_units, k=run_config.k)
            if not np.array_equal(
                decode_position(position, n_units=instance.n_units, k=run_config.k),
                solution,
            ):
                raise SolutionValidationError("posição e solução candidata são incoerentes")
            try:
                evaluation = (
                    reused if reused is not None else context.evaluate(solution)
                )
            except EvaluationLimitReached as exhausted:
                evaluation = _limit_result(exhausted)
                _commit_candidate(
                    particle, position, trial.velocity, solution, evaluation, diagnostics
                )
                candidate = particle.pbest
                assert candidate is not None
                better, strict = _best_comparison(candidate, gbest)
                if better:
                    gbest = _copy_best(
                        candidate.position, candidate.solution, candidate.evaluation
                    )
                    diagnostics.global_best_updates += 1
                    diagnostics.strict_global_improvements += int(strict)
                diagnostics.particles_evaluated += 1
                _verify_diagnostics(context, diagnostics)
                diagnostics.publish(context)
                raise
            except BudgetExhausted:
                _verify_diagnostics(context, diagnostics)
                diagnostics.publish(context)
                raise
            _commit_candidate(
                particle, position, trial.velocity, solution, evaluation, diagnostics
            )
            candidate = particle.pbest
            assert candidate is not None
            better, strict = _best_comparison(candidate, gbest)
            if better:
                gbest = _copy_best(candidate.position, candidate.solution, candidate.evaluation)
                diagnostics.global_best_updates += 1
                diagnostics.strict_global_improvements += int(strict)
            diagnostics.particles_evaluated += 1
            diagnostics.publish(context)
        diagnostics.iterations_completed += 1
        diagnostics.publish(context)


def _commit_candidate(
    particle: _Particle,
    position: FloatArray,
    velocity: FloatArray,
    solution: IntArray,
    evaluation: EvaluationResult,
    diagnostics: _PsoDiagnostics,
) -> None:
    particle.position = position.copy()
    particle.velocity = velocity.copy()
    candidate = _copy_best(position, solution, evaluation)
    assert particle.pbest is not None
    if _best_comparison(candidate, particle.pbest)[0]:
        particle.pbest = candidate
        diagnostics.personal_best_updates += 1


def _limit_result(error: EvaluationLimitReached) -> EvaluationResult:
    if not isinstance(error.result, EvaluationResult):
        raise ConfigurationError("avaliação final não contém decomposição")
    return error.result


def _verify_diagnostics(
    context: OptimizationContext, diagnostics: _PsoDiagnostics
) -> None:
    if diagnostics.particles_evaluated + diagnostics.repair_evaluations != context.evaluations:
        raise ConfigurationError("diagnósticos do PSO divergem do contador de avaliações")


def run_pso(
    instance: ProblemInstance,
    run_config: RunConfig,
    pso_config: PsoConfig,
) -> OptimizationResult:
    """Executa PSO Random Keys pelo contrato comum dos otimizadores."""

    if not isinstance(pso_config, PsoConfig):
        raise ConfigurationError("pso_config deve ser PsoConfig")
    if pso_config.n_particles > run_config.budget:
        raise ConfigurationError("n_particles não pode exceder o orçamento")

    def search(context: OptimizationContext, config: PsoConfig) -> None:
        _pso_search(context, config, instance=instance, run_config=run_config)

    return execute_optimizer(
        instance,
        run_config,
        pso_config,
        algorithm="pso",
        search=search,
    )
