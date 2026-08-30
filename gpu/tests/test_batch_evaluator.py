from pathlib import Path

import numpy as np
import pytest

from metaheuristica import (
    RunConfig, load_artesp_instance, load_tiny_instance, solution_key,
)
from metaheuristica import canonical as canonical_module
from metaheuristica.errors import BudgetExhausted
from metaheuristica_gpu import evaluator as evaluator_module
from metaheuristica_gpu.evaluator import HybridEvaluator
from metaheuristica_gpu.objective import GpuBatchObjective


ROOT = Path(__file__).parents[2]


class _RegistroEspiao:
    """Encaminha tudo ao gravador real e anota as chaves que passam por ele."""

    def __init__(self, gravador, registradas):
        self._gravador = gravador
        self._registradas = registradas

    def observe(self, evaluations, solution, result, eligible):
        self._registradas.append(solution)
        return self._gravador.observe(evaluations, solution, result, eligible)

    def __getattr__(self, nome):
        return getattr(self._gravador, nome)


@pytest.mark.parametrize("remaining,expected", [(1, 1), (39, 39), (40, 40), (41, 40)])
def test_lote_respeita_orcamento_sem_padding(remaining, expected):
    instance = load_tiny_instance(ROOT / "data/instances/tiny_manual.json")
    solutions = [np.array([0, 0, 1, 1], dtype=np.int64)] * 40
    with GpuBatchObjective(instance, k=2) as objective:
        evaluator = HybridEvaluator(instance, RunConfig(k=2, seed=0, budget=100), objective)
        evaluator.evaluations = 100 - remaining
        batch = evaluator.evaluate_batch(solutions)
        assert len(batch.results) == expected
        assert evaluator.evaluations == 100 - remaining + expected
        if remaining <= 40:
            assert batch.exhausted
            with pytest.raises(BudgetExhausted):
                evaluator.evaluate_batch(solutions)


def test_o_lote_paga_uma_validacao_por_avaliacao_e_a_chave_e_a_publica():
    """F1-06 na réplica: a chave registrada revalidava o mesmo vetor.

    `evaluate_batch` já valida cada item do lote, e a chave registrada chamava
    `solution_key`, que valida de novo por dentro de `canonicalize_solution`. O
    núcleo paga **uma** validação e uma renomeação por avaliação desde o pacote
    B6; a réplica passou a pagar **duas** validações e uma renomeação ao seguir a
    forma literal que o F8-10 prescreveu. É o padrão que o F1-06 removeu do
    núcleo, reintroduzido aqui.

    O caso mede o número de validações por item do lote contando as duas portas
    por onde elas podem entrar: o nome que o próprio avaliador da réplica importa
    e o nome que `canonicalize_solution` usa por dentro. E assevera, na mesma
    execução, que a chave registrada continua sendo bit a bit a do caminho
    público, porque a afirmação central da mudança é que ela é neutra em bits.
    """

    instance = load_artesp_instance(ROOT / "data/instances", 20)
    k = 5
    # Estado não canônico, para que a renomeação da chave tenha o que fazer e o
    # caso não passe por vácuo.
    solutions = [
        np.array(
            [(3 * index + deslocamento) % k for index in range(instance.n_units)],
            dtype=np.int64,
        )
        for deslocamento in (4, 1, 3)
    ]

    contagem = {"validacoes": 0}
    original = canonical_module.validate_solution

    def espia(solution, *, n_units, k):
        contagem["validacoes"] += 1
        return original(solution, n_units=n_units, k=k)

    registradas = []
    canonical_module.validate_solution = espia
    evaluator_module.validate_solution = espia
    try:
        with GpuBatchObjective(instance, k=k) as objective:
            evaluator = HybridEvaluator(
                instance, RunConfig(k=k, seed=0, budget=100), objective
            )
            evaluator.recorder = _RegistroEspiao(evaluator.recorder, registradas)
            batch = evaluator.evaluate_batch(solutions)
    finally:
        canonical_module.validate_solution = original
        evaluator_module.validate_solution = original

    assert len(batch.results) == len(solutions)
    assert contagem["validacoes"] == len(solutions)

    # A chave registrada é a do caminho público, bit a bit.
    esperadas = [
        solution_key(item, n_units=instance.n_units, k=k) for item in solutions
    ]
    # Denominador do caso: a renomeação de fato permuta os rótulos, logo a
    # igualdade acima não é trivial.
    assert any(
        list(chave) != item.tolist() for chave, item in zip(esperadas, solutions)
    )
    assert registradas == esperadas
