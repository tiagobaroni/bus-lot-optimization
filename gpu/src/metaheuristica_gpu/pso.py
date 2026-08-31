"""PSO híbrido Random Keys com avaliações finais em lotes GPU."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import NamedTuple

import cupy as cp
import numpy as np

from metaheuristica import (
    EvaluationResult, OptimizationResult, ProblemInstance, PsoConfig, RunConfig,
    TerminationReason, evaluate_solution, validate_solution,
)
from metaheuristica.errors import RepairBudgetExhausted, SolutionValidationError
# F8-12. O estado da partícula, a comparação de melhores, a tentativa, a
# canonicalização do candidato e a partícula inicial deixam de ser cópias locais
# e passam a ser **os mesmos objetos** do caminho normativo, pelo mecanismo que
# o pacote B5 usou para o estado parcial da construção do ACO e o B20 para a
# decodificação e a projeção. A duplicação é ruído de manutenção sob um regime
# que já a protege contra divergência silenciosa, e não vetor de corrupção
# despercebida: `execute_scenario` chama `_cpu_readiness()` antes de cada um dos
# 60 cenários, e essa verificação re-hasheia os catorze arquivos de
# `src/metaheuristica/` que o manifesto de congelamento da CPU protege.
#
# **A restrição dura foi respeitada: nenhuma ordem de somatório mudou.** As
# cinco funções unificadas têm corpo aritmético idêntico ao da cópia que
# substituem, termo a termo, e o que elas acrescentam são conferências que o
# núcleo já fazia: `_trial_state` recusa partícula sem melhor pessoal por
# exceção em vez de `assert`, e `_initial_particle` confere que a posição
# sorteada decodifica na alocação gerada. As três estruturas de dados não
# carregam aritmética alguma.
from metaheuristica.pso import (
    VELOCITY_LIMIT, _Best, _Particle, _Trial, _best_comparison,
    _canonical_candidate, _copy_best, _initial_particle, _project_position,
    _trial_state, decode_position,
)
from metaheuristica.repair import repair_empty_lots_with_evaluation

from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.numerics import require_equivalent
from metaheuristica_gpu.objective import GpuBatchObjective


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


def _project(
    position: np.ndarray, original: np.ndarray, repaired: np.ndarray, k: int
) -> np.ndarray:
    return _project_position(position, original, repaired, k=k)


# F8-12, o que **não** foi unificado, e por quê. O laço do enxame de
# `run_pso_gpu`, com `_Pending`, `flush`, `commit` e `close_trial`, permanece
# duplicado de propósito: o núcleo avalia **um** candidato por vez, por
# `context.evaluate`, e o caminho da placa acumula tentativas e as submete em
# lote, truncando pelo orçamento restante dentro de `flush`. Não existe forma de
# importar o laço do núcleo sem reescrevê-lo em torno do lote, e reescrevê-lo é
# exatamente o que a restrição dura proíbe. Pela mesma razão os contadores de
# diagnóstico ficam como estão, e não como `_PsoDiagnostics`: aquela estrutura
# publica por `context.update_diagnostics`, e aqui não existe contexto.
# **Metade duplicada com motivo escrito é o resultado aceitável deste pacote;
# identidade quebrada não é.**


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
        if particle.pbest is None or _best_comparison(candidate, particle.pbest)[0]:
            particle.pbest = candidate
        assert particle.pbest is not None
        if gbest is None or _best_comparison(particle.pbest, gbest)[0]:
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
            position, solution = _canonical_candidate(
                particle.position, labels, n_units=instance.n_units, k=run_config.k
            )
            initial.append(_Pending(particle, position, particle.velocity, solution))
        if flush(initial):
            raise StopIteration
        assert gbest is not None

        while evaluator.remaining:
            snapshot = gbest.position.copy()
            trials = [_trial_state(particle, snapshot, config, rng) for particle in particles]
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
                    position, solution = _canonical_candidate(
                        trial.position, decoded, n_units=instance.n_units, k=run_config.k
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
