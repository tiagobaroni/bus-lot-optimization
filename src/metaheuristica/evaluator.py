"""Avaliação com orçamento estrito e cache opcional por cenário."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from metaheuristica.canonical import (
    _canonicalize_labels,
    canonicalize_solution,
    validate_k,
)
from metaheuristica.errors import BudgetExhausted, ConfigurationError
from metaheuristica.objective import (
    _evaluate_labels,
    _evaluate_partial_assignment,
    _evaluate_provisional_solution,
    _provisional_labels,
)
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance


EvaluationObserver = Callable[
    [int, tuple[int, ...] | None, EvaluationResult, bool], None
]


def viable_key(
    instance: ProblemInstance, solution: Any, *, k: int
) -> tuple[int, ...] | None:
    """Chave canônica de um estado de reparo, ou `None` se algum lote está vazio.

    A3: o estado que entra no reparo pode ter lote vazio por construção, que é
    exatamente o caso que `_evaluate_provisional_solution` existe para tratar,
    logo esta função não pode delegar a decisão a `validate_solution`, que
    recusa lote vazio com exceção. A ocupação é conferida antes, e só o estado
    integralmente viável produz chave.

    O nome é público porque a função é contrato entre o núcleo e a réplica em
    placa gráfica desde o pacote A3, e nome privado importado de fora do módulo
    é contrato sem declaração.

    F1-06: `solution_key` validava esta mesma solução uma segunda vez, sobre o
    mesmo vetor que `_provisional_labels` acabou de validar. A canonicalização
    passa a ser feita direto por `_canonicalize_labels`, que é o corpo de
    `canonicalize_solution` depois da validação. Nenhuma das condições de
    exceção de `validate_solution` sobrevive à conferência acima: dimensão,
    forma, `dtype` inteiro não booleano e intervalo `0 <= rótulo < k` são
    conferidos por `_provisional_labels`, e lote vazio pelo `np.bincount`
    seguinte. Os rótulos que entram na renomeação são os mesmos `int64` na
    mesma ordem, logo os bits não mudam. `canonicalize_solution` e
    `solution_key` permanecem intactas como funções públicas.
    """

    labels = _provisional_labels(solution, n_units=instance.n_units, k=k)
    if np.count_nonzero(np.bincount(labels, minlength=k)) < k:
        return None
    canonical = _canonicalize_labels(labels, n_units=instance.n_units)
    return tuple(int(label) for label in canonical)


class FitnessEvaluator:
    """Contexto exclusivo de avaliação para uma instância, K, pesos e orçamento."""

    __slots__ = (
        "_budget",
        "_cache",
        "_cache_enabled",
        "_cache_hits",
        "_evaluations",
        "_instance",
        "_k",
        "_observer",
        "_weights",
    )

    def __init__(
        self,
        instance: ProblemInstance,
        *,
        k: int,
        budget: int,
        weights: ObjectiveWeights | None = None,
        cache_enabled: bool = False,
        observer: EvaluationObserver | None = None,
    ) -> None:
        validate_k(k, instance.n_units)
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ConfigurationError("orçamento deve ser um inteiro positivo")
        if not isinstance(cache_enabled, bool):
            raise ConfigurationError("cache_enabled deve ser booleano")
        if observer is not None and not callable(observer):
            raise ConfigurationError("observer deve ser chamável")
        self._instance = instance
        self._k = k
        self._budget = budget
        self._weights = weights or ObjectiveWeights()
        self._cache_enabled = cache_enabled
        self._observer = observer
        self._evaluations = 0
        self._cache_hits = 0
        self._cache: dict[tuple[int, ...], EvaluationResult] = {}

    @property
    def instance(self) -> ProblemInstance:
        return self._instance

    @property
    def k(self) -> int:
        return self._k

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def weights(self) -> ObjectiveWeights:
        return self._weights

    @property
    def cache_enabled(self) -> bool:
        return self._cache_enabled

    @property
    def evaluations(self) -> int:
        return self._evaluations

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    @property
    def remaining(self) -> int:
        return self._budget - self._evaluations

    def _consume(self) -> None:
        if self._evaluations >= self._budget:
            raise BudgetExhausted(
                f"orçamento esgotado: {self._evaluations}/{self._budget} avaliações"
            )
        self._evaluations += 1

    def evaluate(self, solution: Any) -> EvaluationResult:
        # F1-06: `solution_key` já canonicalizava e validava, e `evaluate_solution`
        # validava a mesma solução uma segunda vez. A canonicalização é feita uma
        # única vez aqui e o vetor canônico segue direto para `_evaluate_labels`,
        # que é o corpo de `evaluate_solution` depois da validação. A chave de
        # cache continua sendo a tupla canônica, e os rótulos que entram no
        # somatório são os mesmos `int64` na mesma ordem, logo os bits não mudam.
        # `evaluate_solution` permanece intacta: é a função pública usada pelo
        # espelho GPU e pela conferência normativa.
        canonical = canonicalize_solution(
            solution, n_units=self._instance.n_units, k=self._k
        )
        key = tuple(int(label) for label in canonical)
        self._consume()
        if self._cache_enabled and key in self._cache:
            self._cache_hits += 1
            result = self._cache[key]
        else:
            result = _evaluate_labels(
                self._instance,
                canonical,
                k=self._k,
                weights=self._weights,
            )
            if self._cache_enabled:
                self._cache[key] = result
        self._notify(key, result, eligible=True)
        return result

    def evaluate_provisional_for_repair(self, solution: Any) -> EvaluationResult:
        """Avalia um estado possivelmente vazio sem cache, somente para reparo."""

        self._consume()
        # A3: avaliação de reparo integralmente viável compete pelo incumbente.
        # Marcá-la inelegível descartava, por construção, solução viável mais
        # barata que a incumbente, sem justificativa normativa. O gravador
        # precisa da solução para registrar, então a chave canônica substitui o
        # `None` anterior. Estado com lote vazio continua inelegível e sem chave.
        key = viable_key(self._instance, solution, k=self._k)
        if key is None:
            result = _evaluate_provisional_solution(
                self._instance,
                solution,
                k=self._k,
                weights=self._weights,
            )
        else:
            # O estado integralmente viável é uma solução, e passa a ser avaliado
            # sobre o vetor canônico, pelo mesmo caminho de `evaluate`. Sem isto o
            # par publicado deixaria de ser autoconsistente: renomear lotes permuta
            # os totais de `np.bincount` e a soma em outra ordem move os últimos
            # bits de `c_demand`, `c_production` e dos dois coeficientes de
            # variação, de modo que a reavaliação da solução canônica publicada
            # não reproduziria a avaliação publicada. É o mesmo invariante que o
            # pacote B6 estabeleceu para o guloso.
            result = _evaluate_labels(
                self._instance,
                np.array(key, dtype=np.int64),
                k=self._k,
                weights=self._weights,
            )
        self._notify(key, result, eligible=key is not None)
        return result

    def evaluate_partial_for_greedy(
        self, processed_indices: Any, labels: Any
    ) -> EvaluationResult:
        """Avalia um subproblema induzido sem cache, somente para o baseline."""

        self._consume()
        result = _evaluate_partial_assignment(
            self._instance,
            processed_indices,
            labels,
            k=self._k,
            weights=self._weights,
        )
        self._notify(None, result, eligible=False)
        return result

    def _notify(
        self,
        solution: tuple[int, ...] | None,
        result: EvaluationResult,
        *,
        eligible: bool,
    ) -> None:
        if self._observer is not None:
            self._observer(self._evaluations, solution, result, eligible)
