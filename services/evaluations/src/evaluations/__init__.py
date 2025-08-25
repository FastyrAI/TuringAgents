"""
Turing Agents Evaluations Service

A comprehensive LLM evaluation framework supporting multiple benchmarks and datasets.
"""

__version__ = "0.1.0"
__author__ = "Turing Agents Team"

from .core.evaluator import EvaluationSuite
from .core.model_wrapper import ModelWrapper
from .core.metrics import MetricsCalculator

__all__ = [
    "EvaluationSuite",
    "ModelWrapper", 
    "MetricsCalculator",
]