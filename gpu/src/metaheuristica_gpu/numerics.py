"""Conformidade numérica e equivalência de trajetória contra a CPU."""

from __future__ import annotations

from dataclasses import fields
from math import isclose
from typing import Iterable

import numpy as np

from metaheuristica import (
    EvaluationResult, ObjectiveWeights, OptimizationResult, ProblemInstance,
    evaluate_solution,
)


ABS_TOL = 1e-12
REL_TOL = 1e-12


class NumericalDivergenceError(RuntimeError):
    pass


def maximum_difference(left: EvaluationResult, right: EvaluationResult) -> float:
    return max(abs(getattr(left, item.name) - getattr(right, item.name)) for item in fields(EvaluationResult))


def require_equivalent(
    left: EvaluationResult,
    right: EvaluationResult,
    *,
    abs_tol: float = ABS_TOL,
    rel_tol: float = REL_TOL,
) -> float:
    for item in fields(EvaluationResult):
        first = getattr(left, item.name)
        second = getattr(right, item.name)
        if not isclose(first, second, abs_tol=abs_tol, rel_tol=rel_tol):
            raise NumericalDivergenceError(
                f"{item.name} diverge: GPU={first!r}, CPU={second!r}"
            )
    return maximum_difference(left, right)


def require_equivalent_trajectory(
    gpu: OptimizationResult,
    cpu: OptimizationResult,
    *,
    abs_tol: float = ABS_TOL,
    rel_tol: float = REL_TOL,
) -> float:
    """Assevera a equivalência da execução inteira e devolve a maior divergência.

    F8-1, componente `M2`. A régua é a normativa de `1e-12` da seção 29.1, e
    **não** igualdade exata. Em modo oficial, isto é com `verify_every_batch`
    no padrão `False`, os checkpoints publicados carregam números do
    dispositivo e divergem já no checkpoint 1, com magnitude de 1 ulp: medido
    em `artesp_rmsp_20`, `K=5`, semente 10 e orçamento 400, os cem checkpoints
    do ACO e os cem do PSO diferem bit a bit dos da CPU, com `max |delta|` de
    `2,220e-16`, isto é 1/4503 do `abs_tol` normativo. Confundir a comparação
    bit a bit, que é metodologia da auditoria e vale para a impressão digital,
    com a régua do contrato da placa, que admite `1e-12`, foi o que fez este
    achado nascer como `D1`.

    O que passa pela tolerância são apenas os sete campos de
    `EvaluationResult`. Tudo que não depende de aritmética de ponto flutuante é
    comparado por **igualdade exata**: o orçamento consumido, os rótulos da
    solução final, a quantidade de checkpoints e, em cada um deles, o índice e
    a contagem de avaliações em que foi tomado. Um desalinhamento de
    trajetória, isto é a GPU e a CPU escolhendo soluções diferentes, é
    divergência de critério e não de último bit, e por isso reprova sem
    consultar tolerância alguma.
    """

    if gpu.evaluations != cpu.evaluations:
        raise NumericalDivergenceError(
            f"orçamento consumido diverge: GPU={gpu.evaluations}, CPU={cpu.evaluations}"
        )
    gpu_labels = np.asarray(gpu.solution).tolist()
    cpu_labels = np.asarray(cpu.solution).tolist()
    if gpu_labels != cpu_labels:
        raise NumericalDivergenceError(
            f"solução final diverge: GPU={gpu_labels}, CPU={cpu_labels}"
        )
    if len(gpu.checkpoints) != len(cpu.checkpoints):
        raise NumericalDivergenceError(
            "quantidade de checkpoints diverge: "
            f"GPU={len(gpu.checkpoints)}, CPU={len(cpu.checkpoints)}"
        )
    maximum = 0.0
    for gpu_point, cpu_point in zip(gpu.checkpoints, cpu.checkpoints):
        if (gpu_point.index, gpu_point.evaluations) != (cpu_point.index, cpu_point.evaluations):
            raise NumericalDivergenceError(
                "checkpoint desalinhado: "
                f"GPU=({gpu_point.index}, {gpu_point.evaluations}), "
                f"CPU=({cpu_point.index}, {cpu_point.evaluations})"
            )
        try:
            difference = require_equivalent(
                gpu_point.evaluation, cpu_point.evaluation,
                abs_tol=abs_tol, rel_tol=rel_tol,
            )
        except NumericalDivergenceError as error:
            raise NumericalDivergenceError(
                f"checkpoint {gpu_point.index}: {error}"
            ) from error
        maximum = max(maximum, difference)
    try:
        maximum = max(
            maximum,
            require_equivalent(
                gpu.evaluation, cpu.evaluation, abs_tol=abs_tol, rel_tol=rel_tol
            ),
        )
    except NumericalDivergenceError as error:
        raise NumericalDivergenceError(f"avaliação final: {error}") from error
    return maximum


def verify_batch(
    instance: ProblemInstance,
    solutions: np.ndarray,
    gpu_results: Iterable[EvaluationResult],
    *,
    k: int,
    weights: ObjectiveWeights,
) -> float:
    maximum = 0.0
    results = tuple(gpu_results)
    if len(results) != len(solutions):
        raise NumericalDivergenceError("quantidade de avaliações GPU divergente")
    for solution, gpu in zip(solutions, results):
        cpu = evaluate_solution(instance, solution, k=k, weights=weights)
        maximum = max(maximum, require_equivalent(gpu, cpu))
    return maximum
