"""Núcleo computacional para formação de lotes operacionais."""

from metaheuristica.canonical import (
    canonicalize_solution,
    solution_key,
    validate_solution,
)
from metaheuristica.errors import (
    BudgetExhausted,
    ConfigurationError,
    InstanceDataError,
    RepairBudgetExhausted,
    SolutionValidationError,
)
from metaheuristica.evaluator import FitnessEvaluator
from metaheuristica.instances import load_artesp_instance, load_tiny_instance
from metaheuristica.greedy import GreedyResult, GreedyTraceStep, run_greedy
from metaheuristica.objective import evaluate_solution
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance
from metaheuristica.repair import repair_empty_lots

__all__ = [
    "BudgetExhausted",
    "canonicalize_solution",
    "ConfigurationError",
    "EvaluationResult",
    "evaluate_solution",
    "FitnessEvaluator",
    "GreedyResult",
    "GreedyTraceStep",
    "InstanceDataError",
    "load_artesp_instance",
    "load_tiny_instance",
    "ObjectiveWeights",
    "ProblemInstance",
    "RepairBudgetExhausted",
    "repair_empty_lots",
    "run_greedy",
    "SolutionValidationError",
    "solution_key",
    "validate_solution",
]
