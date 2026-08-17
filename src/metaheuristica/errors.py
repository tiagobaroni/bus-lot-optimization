"""Erros de domínio do núcleo de otimização."""


class MetaheuristicaError(Exception):
    """Classe-base para erros esperados do domínio."""


class InstanceDataError(MetaheuristicaError, ValueError):
    """Indica dados ausentes, inconsistentes ou inválidos em uma instância."""


class SolutionValidationError(MetaheuristicaError, ValueError):
    """Indica que uma solução não respeita os invariantes do cenário."""


class ConfigurationError(MetaheuristicaError, ValueError):
    """Indica pesos, K, orçamento ou outra configuração inválida."""


class BudgetExhausted(MetaheuristicaError, RuntimeError):
    """Indica que uma nova avaliação ultrapassaria o orçamento."""


class EvaluationLimitReached(BudgetExhausted):
    """Indica que uma avaliação concluída consumiu a última unidade do orçamento."""

    def __init__(self, result: object, message: str) -> None:
        super().__init__(message)
        self.result = result


class RepairBudgetExhausted(BudgetExhausted):
    """Indica que o orçamento terminou durante um reparo."""
