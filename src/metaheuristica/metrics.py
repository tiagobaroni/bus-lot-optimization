"""Configuração, convergência e resultados comuns dos otimizadores."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from metaheuristica.canonical import canonicalize_solution
from metaheuristica.errors import ConfigurationError
from metaheuristica.problem import EvaluationResult, ObjectiveWeights


IntArray = NDArray[np.int64]
CHECKPOINT_COUNT = 100
COST_TOLERANCE = 1e-12


def checkpoint_thresholds(budget: int, count: int = CHECKPOINT_COUNT) -> tuple[int, ...]:
    """Calcula limiares igualmente espaçados usando teto e aritmética inteira."""

    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise ConfigurationError("orçamento deve ser um inteiro positivo")
    if isinstance(count, bool) or not isinstance(count, int) or count != CHECKPOINT_COUNT:
        raise ConfigurationError(f"quantidade de checkpoints deve ser {CHECKPOINT_COUNT}")
    if budget < count:
        raise ConfigurationError("orçamento deve ser pelo menos igual a 100 checkpoints")
    return tuple((index * budget + count - 1) // count for index in range(1, count + 1))


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Parâmetros comparáveis compartilhados por todas as metaheurísticas."""

    k: int
    seed: int
    budget: int
    weights: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    checkpoint_count: int = CHECKPOINT_COUNT
    cache_enabled: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.k, bool) or not isinstance(self.k, int) or self.k < 2:
            raise ConfigurationError("K deve ser um inteiro maior ou igual a 2")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ConfigurationError("seed deve ser um número inteiro")
        try:
            np.random.PCG64(self.seed)
        except (TypeError, ValueError) as error:
            raise ConfigurationError("seed inválida para PCG64") from error
        if not isinstance(self.weights, ObjectiveWeights):
            raise ConfigurationError("weights deve ser ObjectiveWeights")
        if not isinstance(self.cache_enabled, bool):
            raise ConfigurationError("cache_enabled deve ser booleano")
        checkpoint_thresholds(self.budget, self.checkpoint_count)

    @property
    def thresholds(self) -> tuple[int, ...]:
        return checkpoint_thresholds(self.budget, self.checkpoint_count)


@dataclass(frozen=True, slots=True)
class ConvergenceCheckpoint:
    """Melhor resultado acumulado em um limiar do orçamento."""

    index: int
    evaluations: int
    evaluation: EvaluationResult

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise ConfigurationError("índice do checkpoint deve ser inteiro")
        if self.index < 1 or self.index > CHECKPOINT_COUNT:
            raise ConfigurationError("índice do checkpoint deve estar entre 1 e 100")
        if isinstance(self.evaluations, bool) or not isinstance(self.evaluations, int):
            raise ConfigurationError("avaliações do checkpoint devem ser inteiras")
        if self.evaluations <= 0:
            raise ConfigurationError("avaliações do checkpoint devem ser positivas")
        if not isinstance(self.evaluation, EvaluationResult):
            raise ConfigurationError("checkpoint deve conter EvaluationResult")


class ConvergenceRecorder:
    """Mantém incumbente e checkpoints de uma única execução."""

    __slots__ = (
        "_checkpoints",
        "_incumbent_evaluation",
        "_incumbent_solution",
        "_next_threshold",
        "_thresholds",
    )

    def __init__(self, thresholds: tuple[int, ...]) -> None:
        if len(thresholds) != CHECKPOINT_COUNT:
            raise ConfigurationError("registrador requer exatamente 100 limiares")
        if any(left >= right for left, right in zip(thresholds, thresholds[1:])):
            raise ConfigurationError("limiares devem ser estritamente crescentes")
        self._thresholds = thresholds
        self._next_threshold = 0
        self._checkpoints: list[ConvergenceCheckpoint] = []
        self._incumbent_solution: tuple[int, ...] | None = None
        self._incumbent_evaluation: EvaluationResult | None = None

    @property
    def checkpoints(self) -> tuple[ConvergenceCheckpoint, ...]:
        return tuple(self._checkpoints)

    @property
    def incumbent_solution(self) -> tuple[int, ...] | None:
        return self._incumbent_solution

    @property
    def incumbent_evaluation(self) -> EvaluationResult | None:
        return self._incumbent_evaluation

    def observe(
        self,
        evaluations: int,
        solution: tuple[int, ...] | None,
        evaluation: EvaluationResult,
        eligible: bool,
    ) -> None:
        if eligible:
            if solution is None:
                raise ConfigurationError("avaliação elegível deve informar solução")
            if self._is_better(solution, evaluation):
                self._incumbent_solution = solution
                self._incumbent_evaluation = evaluation
        while (
            self._next_threshold < len(self._thresholds)
            and evaluations >= self._thresholds[self._next_threshold]
        ):
            if self._incumbent_evaluation is None:
                raise ConfigurationError(
                    "checkpoint alcançado antes de existir incumbente viável"
                )
            index = self._next_threshold + 1
            self._checkpoints.append(
                ConvergenceCheckpoint(
                    index=index,
                    evaluations=self._thresholds[self._next_threshold],
                    evaluation=self._incumbent_evaluation,
                )
            )
            self._next_threshold += 1

    def _is_better(
        self, solution: tuple[int, ...], evaluation: EvaluationResult
    ) -> bool:
        current = self._incumbent_evaluation
        if current is None:
            return True
        # Comparação exata: a banda de 1e-12 fazia a janela deslizar a cada empate
        # e o desvio acumular sem limite, contra a seção 9, que exige curva não
        # crescente. O desempate lexicográfico sobrevive apenas na igualdade exata,
        # onde não há valor a deslocar.
        if evaluation.total_cost < current.total_cost:
            return True
        if evaluation.total_cost == current.total_cost:
            assert self._incumbent_solution is not None
            return solution < self._incumbent_solution
        return False


class TerminationReason(StrEnum):
    """Motivos normais e documentados de encerramento."""

    BUDGET_EXHAUSTED = "budget_exhausted"


JsonScalar = str | int | float | bool | None
FrozenDiagnostic = JsonScalar | tuple["FrozenDiagnostic", ...] | Mapping[str, "FrozenDiagnostic"]


def _freeze_diagnostic(value: Any) -> FrozenDiagnostic:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ConfigurationError("diagnóstico contém valor não finito")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_diagnostic(item) for item in value)
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenDiagnostic] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationError("chaves de diagnósticos devem ser textos")
            frozen[key] = _freeze_diagnostic(item)
        return MappingProxyType(frozen)
    raise ConfigurationError(
        f"diagnóstico contém tipo não serializável: {type(value).__name__}"
    )


def _json_diagnostic(value: FrozenDiagnostic) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_diagnostic(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_diagnostic(item) for item in value]
    return value


def _evaluation_dict(value: EvaluationResult) -> dict[str, float]:
    return {
        "total_cost": value.total_cost,
        "c_demand": value.c_demand,
        "c_production": value.c_production,
        "c_territorial": value.c_territorial,
        "c_affinity": value.c_affinity,
        "cv_demand": value.cv_demand,
        "cv_production": value.cv_production,
    }


@dataclass(frozen=True, slots=True, eq=False)
class OptimizationResult:
    """Resultado uniforme, imutável e serializável de uma metaheurística."""

    algorithm: str
    k: int
    seed: int
    budget: int
    weights: ObjectiveWeights
    solution: IntArray
    evaluation: EvaluationResult
    evaluations: int
    cache_hits: int
    checkpoints: tuple[ConvergenceCheckpoint, ...]
    runtime_seconds: float
    termination_reason: TerminationReason
    diagnostics: Mapping[str, FrozenDiagnostic] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.algorithm, str) or not self.algorithm.strip():
            raise ConfigurationError("algoritmo deve ser um texto não vazio")
        config = RunConfig(
            k=self.k,
            seed=self.seed,
            budget=self.budget,
            weights=self.weights,
            cache_enabled=False,
        )
        canonical = canonicalize_solution(
            self.solution, n_units=len(self.solution), k=self.k
        )
        checkpoints = tuple(self.checkpoints)
        if len(checkpoints) != CHECKPOINT_COUNT:
            raise ConfigurationError("resultado deve conter exatamente 100 checkpoints")
        for index, (checkpoint, threshold) in enumerate(
            zip(checkpoints, config.thresholds), start=1
        ):
            if checkpoint.index != index or checkpoint.evaluations != threshold:
                raise ConfigurationError("checkpoint não corresponde ao limiar esperado")
        if self.evaluations != self.budget:
            raise ConfigurationError("resultado por orçamento deve consumir todo o limite")
        if (
            isinstance(self.cache_hits, bool)
            or not isinstance(self.cache_hits, int)
            or self.cache_hits < 0
            or self.cache_hits > self.evaluations
        ):
            raise ConfigurationError("quantidade de cache hits inválida")
        if (
            isinstance(self.runtime_seconds, bool)
            or not isinstance(self.runtime_seconds, (int, float))
            or not isfinite(float(self.runtime_seconds))
            or self.runtime_seconds < 0
        ):
            raise ConfigurationError("tempo de otimização deve ser finito e não negativo")
        if self.termination_reason is not TerminationReason.BUDGET_EXHAUSTED:
            raise ConfigurationError("motivo de parada não suportado")
        last = checkpoints[-1].evaluation
        if not _same_evaluation(last, self.evaluation):
            raise ConfigurationError("avaliação final diverge do último checkpoint")
        frozen = _freeze_diagnostic(self.diagnostics)
        assert isinstance(frozen, Mapping)
        object.__setattr__(self, "solution", canonical)
        object.__setattr__(self, "checkpoints", checkpoints)
        object.__setattr__(self, "runtime_seconds", float(self.runtime_seconds))
        object.__setattr__(self, "diagnostics", frozen)

    def to_dict(self) -> dict[str, Any]:
        """Converte o resultado para tipos compatíveis com JSON."""

        return {
            "algorithm": self.algorithm,
            "k": self.k,
            "seed": self.seed,
            "budget": self.budget,
            "weights": {
                "demand": self.weights.demand,
                "production": self.weights.production,
                "territorial": self.weights.territorial,
                "affinity": self.weights.affinity,
            },
            "solution": [int(label) for label in self.solution],
            "evaluation": _evaluation_dict(self.evaluation),
            "evaluations": self.evaluations,
            "cache_hits": self.cache_hits,
            "checkpoints": [
                {
                    "index": checkpoint.index,
                    "evaluations": checkpoint.evaluations,
                    "evaluation": _evaluation_dict(checkpoint.evaluation),
                }
                for checkpoint in self.checkpoints
            ],
            "runtime_seconds": self.runtime_seconds,
            "termination_reason": self.termination_reason.value,
            "diagnostics": _json_diagnostic(self.diagnostics),
        }

    def reproducible_data(self) -> dict[str, Any]:
        """Campos que devem coincidir em repetições, excluindo somente o tempo."""

        data = self.to_dict()
        del data["runtime_seconds"]
        return data


def _evaluation_tuple(value: EvaluationResult) -> tuple[float, ...]:
    return (
        value.total_cost,
        value.c_demand,
        value.c_production,
        value.c_territorial,
        value.c_affinity,
        value.cv_demand,
        value.cv_production,
    )


def _same_evaluation(left: EvaluationResult, right: EvaluationResult) -> bool:
    """Compara as duas publicações do incumbente por igualdade exata.

    A tolerância anterior de `1e-12` admitia divergência real entre a tabela
    principal da seção 9 e a tabela de checkpoints da seção 27, que descrevem a
    mesma execução e precisam carregar o mesmo número.
    """

    return left is right or all(
        float(a).hex() == float(b).hex()
        for a, b in zip(_evaluation_tuple(left), _evaluation_tuple(right))
    )
