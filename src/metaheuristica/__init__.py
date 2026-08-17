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
from metaheuristica.metrics import (
    ConvergenceCheckpoint,
    OptimizationResult,
    RunConfig,
    TerminationReason,
    checkpoint_thresholds,
)
from metaheuristica.objective import evaluate_solution
from metaheuristica.optimizer import OptimizationContext, execute_optimizer
from metaheuristica.problem import EvaluationResult, ObjectiveWeights, ProblemInstance
from metaheuristica.repair import repair_empty_lots
from metaheuristica.tabu import TabuConfig, TabuMove, run_tabu

__all__ = [
    "BudgetExhausted",
    "canonicalize_solution",
    "ConfigurationError",
    "ConvergenceCheckpoint",
    "EvaluationResult",
    "evaluate_solution",
    "FitnessEvaluator",
    "GreedyResult",
    "GreedyTraceStep",
    "InstanceDataError",
    "load_artesp_instance",
    "load_tiny_instance",
    "ObjectiveWeights",
    "OptimizationContext",
    "OptimizationResult",
    "ProblemInstance",
    "RepairBudgetExhausted",
    "repair_empty_lots",
    "run_greedy",
    "run_tabu",
    "RunConfig",
    "SolutionValidationError",
    "solution_key",
    "TerminationReason",
    "TabuConfig",
    "TabuMove",
    "validate_solution",
    "checkpoint_thresholds",
    "execute_optimizer",
]
