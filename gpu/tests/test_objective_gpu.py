from pathlib import Path

import numpy as np

from metaheuristica import ObjectiveWeights, load_artesp_instance, load_tiny_instance
from metaheuristica_gpu.numerics import verify_batch
from metaheuristica_gpu.objective import GpuBatchObjective


ROOT = Path(__file__).parents[2]


def _solutions(n: int, k: int, count: int) -> np.ndarray:
    return np.stack([
        np.roll(np.arange(n, dtype=np.int64) % k, shift)
        for shift in range(count)
    ])


def test_gpu_objective_matches_cpu_on_all_instances() -> None:
    instances = [
        load_tiny_instance(ROOT / "data/instances/tiny_manual.json"),
        *(load_artesp_instance(ROOT / "data/instances", size) for size in (20, 60, 150)),
    ]
    for instance in instances:
        k = 2 if instance.n_units < 20 else 5
        solutions = _solutions(instance.n_units, k, 2)
        with GpuBatchObjective(instance, k=k) as objective:
            results = objective.evaluate(solutions)
        assert verify_batch(
            instance, solutions, results, k=k, weights=ObjectiveWeights()
        ) <= 1e-12


def test_gpu_objective_preserves_batch_order_and_size_40() -> None:
    instance = load_artesp_instance(ROOT / "data/instances", 20)
    solutions = _solutions(20, 5, 40)
    with GpuBatchObjective(instance, k=5) as objective:
        results = objective.evaluate(solutions)
    assert len(results) == 40
    assert verify_batch(instance, solutions, results, k=5, weights=ObjectiveWeights()) <= 1e-12


def test_a_avaliacao_provisoria_da_replica_delega_ao_caminho_normativo() -> None:
    """F8-12: a réplica de `evaluate_provisional_cpu` deixa de existir.

    A igualdade de valores sozinha **não** prende a unificação, porque ela já
    valia antes: as duas implementações eram bit a bit iguais. O que prende é o
    espião, que exige que o caminho normativo tenha sido de fato percorrido.
    """

    import metaheuristica_gpu.objective as modulo
    from metaheuristica.objective import _evaluate_provisional_solution

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    chamadas = 0
    real = modulo._evaluate_provisional_solution

    def espiao(*args, **extras):
        nonlocal chamadas
        chamadas += 1
        return real(*args, **extras)

    rotulos = np.zeros(20, dtype=np.int64)
    rotulos[-1] = 1
    esperada = _evaluate_provisional_solution(
        instance, rotulos, k=5, weights=ObjectiveWeights()
    )
    import pytest

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(modulo, "_evaluate_provisional_solution", espiao)
        obtida = modulo.evaluate_provisional_cpu(
            instance, rotulos, k=5, weights=ObjectiveWeights()
        )

    assert chamadas == 1, "denominador do caso: o caminho normativo foi percorrido"
    from dataclasses import fields

    from metaheuristica import EvaluationResult

    for campo in fields(EvaluationResult):
        assert float(getattr(obtida, campo.name)).hex() == float(
            getattr(esperada, campo.name)
        ).hex()
    # A entrada tem lote vazio, que é o uso real desta função: sem isso o caso
    # exercitaria o caminho viável, que nem sequer a chama.
    assert np.count_nonzero(np.bincount(rotulos, minlength=5)) < 5


def test_a_avaliacao_provisoria_preserva_o_contrato_de_recusa_da_replica() -> None:
    """F8-12: a recusa continua sendo `RuntimeError`, e a razão é operacional.

    O caminho normativo levanta `SolutionValidationError`, que herda de
    `ValueError` e **não** de `RuntimeError`. `run.py` depende do contrário em
    dois pontos: a CLI devolve código 2 pelo `except (..., RuntimeError)`, e a
    sessão de um cenário interrompido é gravada como `interrupted`, e não como
    `failed`, pelo mesmo teste. O eixo negativo está aqui dentro: o caso mede
    que o núcleo **não** levanta `RuntimeError` para as mesmas entradas, de modo
    que sem o reembalo o comportamento mudaria em silêncio.
    """

    import pytest

    from metaheuristica.objective import _evaluate_provisional_solution
    from metaheuristica_gpu.objective import GpuObjectiveError, evaluate_provisional_cpu

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    invalidas = (
        np.zeros(5, dtype=np.int64),
        np.zeros(20, dtype=np.float64),
        np.full(20, 9, dtype=np.int64),
        np.full(20, -1, dtype=np.int64),
    )
    for entrada in invalidas:
        with pytest.raises(GpuObjectiveError) as capturado:
            evaluate_provisional_cpu(instance, entrada, k=3, weights=ObjectiveWeights())
        assert isinstance(capturado.value, RuntimeError)
        with pytest.raises(Exception) as normativo:
            _evaluate_provisional_solution(
                instance, entrada, k=3, weights=ObjectiveWeights()
            )
        assert not isinstance(normativo.value, RuntimeError)
