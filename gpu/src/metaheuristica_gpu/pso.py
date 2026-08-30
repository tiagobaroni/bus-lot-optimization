"""PSO híbrido Random Keys com avaliações finais em lotes GPU."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from time import perf_counter
from typing import NamedTuple

import cupy as cp
import numpy as np

from metaheuristica import (
    EvaluationResult, OptimizationResult, ProblemInstance, PsoConfig, RunConfig,
    TerminationReason, canonicalize_solution, evaluate_solution,
    validate_solution,
)
from metaheuristica.errors import RepairBudgetExhausted, SolutionValidationError
from metaheuristica.pso import _project_position, decode_position
from metaheuristica.repair import repair_empty_lots_with_evaluation
from metaheuristica.metrics import COST_TOLERANCE

from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.numerics import require_equivalent
from metaheuristica_gpu.objective import GpuBatchObjective


VELOCITY_LIMIT = 0.5


@dataclass(slots=True)
class _Best:
    position: np.ndarray
    solution: np.ndarray
    evaluation: EvaluationResult


@dataclass(slots=True)
class _Particle:
    position: np.ndarray
    velocity: np.ndarray
    pbest: _Best | None = None


@dataclass(frozen=True, slots=True)
class _Trial:
    position: np.ndarray
    velocity: np.ndarray
    position_clips: int
    velocity_clips: int


class _Pending(NamedTuple):
    """Tentativa à espera do lote, com o que sua avaliação vai fechar.

    B21, espelho do núcleo. O laço de tentativas do espelho **não** avalia: ele
    enfileira, e quem avalia é `flush`, que trunca o lote pelo orçamento
    restante e descarta em silêncio o que sobra. Contar as saturações no laço
    contaria tentativas que o lote nunca avaliou, que é exatamente o padrão
    antigo que este pacote remove do núcleo. Por isso as saturações da tentativa
    e a marca de fechamento de iteração viajam com o item e são contabilizadas
    dentro de `flush`, sobre os itens de fato avaliados.
    """

    particle: _Particle
    position: np.ndarray
    velocity: np.ndarray
    solution: np.ndarray
    position_clips: int = 0
    velocity_clips: int = 0
    closes_iteration: bool = False


# F8-10: a decodificação e a projeção passam a ser as do caminho normativo, e
# não cópias locais. A cópia conferia apenas a dimensão, e deixava passar
# `dtype` diferente de `float64`, valor não finito e chave fora de `[0, 1]`, que
# o núcleo recusa em `decode_position`; e a cópia da projeção retinha o recuo
# silencioso ao ponto médio que o núcleo converteu em falha explícita, com a
# fração interna que a seção 16 manda preservar sendo descartada sem
# diagnóstico. Delegar é a mesma decisão que o pacote B5 tomou para o estado
# parcial da construção do ACO: a aritmética do caminho feliz é idêntica e uma
# alteração futura não pode atingir só um dos dois lados.
def _decode(position: np.ndarray, n: int, k: int) -> np.ndarray:
    return decode_position(position, n_units=n, k=k)


def _initial_particle(n: int, k: int, rng: np.random.Generator) -> _Particle:
    permutation = rng.permutation(n)
    labels = np.empty(n, dtype=np.int64)
    labels[permutation] = np.arange(n, dtype=np.int64) % k
    position = (labels.astype(np.float64) + rng.random(n)) / k
    velocity = rng.uniform(-VELOCITY_LIMIT, VELOCITY_LIMIT, size=n)
    return _Particle(position.copy(), velocity.astype(np.float64, copy=False).copy())


def _copy_best(position: np.ndarray, solution: np.ndarray, evaluation: EvaluationResult) -> _Best:
    return _Best(position.copy(), solution.copy(), evaluation)


def _better(candidate: _Best, incumbent: _Best) -> bool:
    difference = candidate.evaluation.total_cost - incumbent.evaluation.total_cost
    if difference < -COST_TOLERANCE:
        return True
    if abs(difference) > COST_TOLERANCE:
        return False
    candidate_solution = tuple(int(value) for value in candidate.solution)
    incumbent_solution = tuple(int(value) for value in incumbent.solution)
    if candidate_solution != incumbent_solution:
        return candidate_solution < incumbent_solution
    return tuple(candidate.position) < tuple(incumbent.position)


def _trial(
    particle: _Particle, gbest: np.ndarray, config: PsoConfig,
    rng: np.random.Generator,
) -> _Trial:
    assert particle.pbest is not None
    r1 = rng.random(particle.position.shape)
    r2 = rng.random(particle.position.shape)
    raw_velocity = (
        config.inertia * particle.velocity
        + config.cognitive * r1 * (particle.pbest.position - particle.position)
        + config.social * r2 * (gbest - particle.position)
    )
    velocity_clips = int(
        np.count_nonzero((raw_velocity < -VELOCITY_LIMIT) | (raw_velocity > VELOCITY_LIMIT))
    )
    # A velocidade saturada é a que se aplica à posição: o limite da seção 16 é do
    # passo, não apenas do estado herdado pelo termo de inércia da iteração
    # seguinte. Espelha `metaheuristica.pso._trial_state`, corrigida no pacote A1.
    velocity = np.clip(raw_velocity, -VELOCITY_LIMIT, VELOCITY_LIMIT)
    raw_position = particle.position + velocity
    position_clips = int(np.count_nonzero((raw_position < 0.0) | (raw_position > 1.0)))
    return _Trial(
        np.clip(raw_position, 0.0, 1.0),
        velocity,
        position_clips,
        velocity_clips,
    )


def _project(
    position: np.ndarray, original: np.ndarray, repaired: np.ndarray, k: int
) -> np.ndarray:
    return _project_position(position, original, repaired, k=k)


def _canonical(position: np.ndarray, labels: np.ndarray, n: int, k: int) -> tuple[np.ndarray, np.ndarray]:
    canonical = canonicalize_solution(labels, n_units=n, k=k)
    if np.array_equal(labels, canonical):
        return position.copy(), canonical
    return _project(position, labels, canonical, k), canonical


def run_pso_gpu(
    instance: ProblemInstance,
    run_config: RunConfig,
    config: PsoConfig,
    *,
    verify_every_batch: bool = False,
    guard: Callable[[], None] | None = None,
) -> OptimizationResult:
    rng = np.random.Generator(np.random.PCG64(run_config.seed))
    # F8-14: a construção do objetivo em lote faz trabalho de CPU e cinco
    # transferências para o dispositivo, e ficava fora de todo campo publicado.
    # O cronômetro oficial **não** se move, porque a comparabilidade com as
    # execuções já medidas depende de o campo principal manter a definição; o
    # custo de preparação passa a ter campo próprio.
    preparation_start = perf_counter()
    objective = GpuBatchObjective(instance, k=run_config.k, weights=run_config.weights)
    cp.cuda.get_current_stream().synchronize()
    start = perf_counter()
    device_preparation = start - preparation_start
    evaluator = HybridEvaluator(
        instance, run_config, objective, verify_every_batch=verify_every_batch,
        guard=guard,
    )
    particles = [_initial_particle(instance.n_units, run_config.k, rng) for _ in range(config.n_particles)]
    gbest: _Best | None = None
    iterations = particles_evaluated = repair_attempts = repair_evaluations = 0
    position_clips = velocity_clips = 0

    def commit(
        particle: _Particle, position: np.ndarray, velocity: np.ndarray,
        solution: np.ndarray, evaluation: EvaluationResult,
    ) -> None:
        nonlocal gbest, particles_evaluated
        particle.position = position.copy(); particle.velocity = velocity.copy()
        candidate = _copy_best(position, solution, evaluation)
        if particle.pbest is None or _better(candidate, particle.pbest):
            particle.pbest = candidate
        assert particle.pbest is not None
        if gbest is None or _better(particle.pbest, gbest):
            gbest = _copy_best(
                particle.pbest.position, particle.pbest.solution, particle.pbest.evaluation
            )
        particles_evaluated += 1

    def close_trial(item: _Pending) -> None:
        nonlocal position_clips, velocity_clips, iterations
        position_clips += item.position_clips
        velocity_clips += item.velocity_clips
        if item.closes_iteration:
            iterations += 1

    def flush(items: list[_Pending]) -> bool:
        if not items or evaluator.remaining <= 0:
            return evaluator.remaining == 0
        batch = evaluator.evaluate_batch([item.solution for item in items])
        for item, solution, evaluation in zip(items, batch.solutions, batch.results):
            commit(item.particle, item.position, item.velocity, solution, evaluation)
            close_trial(item)
        items.clear()
        return batch.exhausted

    try:
        initial: list[_Pending] = []
        for particle in particles:
            labels = _decode(particle.position, instance.n_units, run_config.k)
            position, solution = _canonical(particle.position, labels, instance.n_units, run_config.k)
            initial.append(_Pending(particle, position, particle.velocity, solution))
        if flush(initial):
            raise StopIteration
        assert gbest is not None

        while evaluator.remaining:
            snapshot = gbest.position.copy()
            trials = [_trial(particle, snapshot, config, rng) for particle in particles]
            pending: list[_Pending] = []
            for index, (particle, trial) in enumerate(zip(particles, trials)):
                last_trial = index == len(trials) - 1
                decoded = _decode(trial.position, instance.n_units, run_config.k)
                if np.count_nonzero(np.bincount(decoded, minlength=run_config.k)) < run_config.k:
                    if flush(pending):
                        raise StopIteration
                    repair_attempts += 1
                    before = evaluator.evaluations
                    try:
                        repaired, reused = repair_empty_lots_with_evaluation(
                            decoded, evaluator
                        )
                    except RepairBudgetExhausted:
                        repair_evaluations += evaluator.evaluations - before
                        raise StopIteration
                    # A4, espelho da CPU: a unidade reaproveitada muda da coluna
                    # de reparo para a de partículas, e a partícula reparada é
                    # comprometida direto, sem entrar no lote da GPU, porque sua
                    # avaliação já existe.
                    repair_evaluations += (
                        evaluator.evaluations - before - int(reused is not None)
                    )
                    position = _project(trial.position, decoded, repaired, run_config.k)
                    # O ramo alternativo, que enfileirava a partícula reparada
                    # para o lote da GPU quando o reparo não devolvia avaliação
                    # reaproveitável, era **morto**: o bloco só é alcançado
                    # quando a decodificação deixa lote vazio, e nesse caso
                    # `repair_empty_lots_with_evaluation` sempre consome ao
                    # menos uma unidade de orçamento e devolve o vencedor da
                    # última rodada. `None` só ocorre para estado já viável.
                    if reused is None:
                        raise SolutionValidationError(
                            "reparo de estado com lote vazio devolveu estado "
                            "sem avaliação reaproveitável"
                        )
                    # A partícula reparada passa pela mesma validação normativa
                    # que o ramo vizinho aplica, e que a CPU aplica nos dois: o
                    # `commit` não passa pelo gravador, logo sem esta conferência
                    # um estado inválido entraria no melhor pessoal e no melhor
                    # global sem nunca ser recusado.
                    validate_solution(repaired, n_units=instance.n_units, k=run_config.k)
                    commit(particle, position, trial.velocity, repaired, reused)
                    # A partícula reparada não entra no lote, logo o fechamento
                    # da tentativa é feito aqui, antes da conferência da
                    # fronteira, no mesmo ponto em que o núcleo o faz.
                    close_trial(
                        _Pending(
                            particle, position, trial.velocity, repaired,
                            trial.position_clips, trial.velocity_clips, last_trial,
                        )
                    )
                    if evaluator.remaining == 0:
                        raise StopIteration
                else:
                    position, solution = _canonical(
                        trial.position, decoded, instance.n_units, run_config.k
                    )
                    validate_solution(solution, n_units=instance.n_units, k=run_config.k)
                    pending.append(
                        _Pending(
                            particle, position, trial.velocity, solution,
                            trial.position_clips, trial.velocity_clips, last_trial,
                        )
                    )
            if flush(pending):
                raise StopIteration
    except StopIteration:
        pass
    finally:
        cp.cuda.get_current_stream().synchronize()
        runtime = perf_counter() - start
        objective.close()
    assert evaluator.incumbent_solution is not None and evaluator.incumbent_evaluation is not None
    final_cpu = evaluate_solution(
        instance, evaluator.incumbent_solution, k=run_config.k, weights=run_config.weights
    )
    require_equivalent(evaluator.incumbent_evaluation, final_cpu)
    return OptimizationResult(
        algorithm="pso_gpu", k=run_config.k, seed=run_config.seed,
        budget=run_config.budget, weights=run_config.weights,
        solution=np.asarray(evaluator.incumbent_solution, dtype=np.int64),
        # Publica o mesmo objeto que a tabela de checkpoints carrega. A
        # conferência de conformidade contra a CPU continua sendo feita acima,
        # por `require_equivalent`, que é contrato do projeto.
        evaluation=evaluator.incumbent_evaluation,
        evaluations=evaluator.evaluations, cache_hits=0,
        checkpoints=evaluator.checkpoints, runtime_seconds=runtime,
        termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        diagnostics={
            "iterations_completed": iterations, "particles_evaluated": particles_evaluated,
            "repair_attempts": repair_attempts, "repair_evaluations": repair_evaluations,
            "position_clips": position_clips, "velocity_clips": velocity_clips,
            "device_preparation_seconds": device_preparation,
            "gpu_timing": evaluator.timing.to_dict(),
            "max_numerical_difference": evaluator.max_numerical_difference,
        },
    )
