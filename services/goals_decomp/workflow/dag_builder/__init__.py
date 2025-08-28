"""
DAG Architecture Package

A modular architecture for building and visualizing hierarchical DAGs.
Separates graph construction logic from visualization concerns.
"""

from .hierarchical_dag_builder import (
    HierarchicalDAGBuilder,
    NodeType,
    NodeInfo
)

from .create_interactive_hierarchical_dags import InteractiveDAGVisualizer

__all__ = [
    'HierarchicalDAGBuilder',
    'NodeType', 
    'NodeInfo',
    'InteractiveDAGVisualizer'
]

__version__ = '1.0.0'
