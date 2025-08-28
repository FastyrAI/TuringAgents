"""
Simplified Hierarchical DAG Builder focused on core DAG building and orchestration.
"""

import networkx as nx
from typing import Dict, List, Set, Any, Optional, Tuple
from pathlib import Path
import yaml
from enum import Enum


class NodeType(Enum):
    """Node types in the hierarchy."""
    GOAL = "goal"
    CAPABILITY = "capability"
    TASK = "task"


class NodeInfo:
    """Simple container for node information."""
    def __init__(self, node_type: NodeType, data: Dict, has_children: bool = False):
        self.type = node_type
        self.data = data
        self.has_children = has_children
        self.metadata = data  # Alias for compatibility
        # Extract description for compatibility
        self.description = data.get('description', data.get('name', ''))


class HierarchicalDAGBuilder:
    """
    Builds and manages hierarchical DAGs for Goals -> Capabilities -> Tasks.
    Focused on core building and orchestration functionality.
    """
    
    def __init__(self, yaml_file: str, verbose: bool = False):
        """Initialize the builder with a YAML file."""
        self.yaml_file = yaml_file
        self.verbose = verbose
        
        # Core DAG structures
        self.goal_dag = nx.DiGraph()
        self.capability_dags = {}  # {goal_name: capability_dag}
        self.task_dags = {}  # {capability_name: task_dag}
        
        # Metadata
        self.node_info = {}  # {node_name: NodeInfo}
        self.cross_dependencies = {}  # {capability: {goal: [cross_dep_caps]}}
        self.orphaned_tasks = []  # For compatibility
        
        # Build the DAGs
        self._build_from_yaml()
    
    def _build_from_yaml(self):
        """Load YAML and build all DAG structures."""
        # Load YAML
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Handle different YAML structures
        if 'decomposition' in data:
            decomposition = data['decomposition']
        else:
            decomposition = data
        
        goals = decomposition.get('goals', [])
        capabilities = decomposition.get('capabilities', decomposition.get('required_capabilities', []))
        tasks = decomposition.get('tasks', [])
        
        # Build Goal DAG
        for goal in goals:
            goal_name = goal['name']
            self.goal_dag.add_node(goal_name)
            # Check if goal has capabilities
            has_caps = any(c.get('parent_goal') == goal_name for c in capabilities)
            self.node_info[goal_name] = NodeInfo(NodeType.GOAL, goal, has_children=has_caps)
            
            # Add goal dependencies
            for dep in goal.get('dependencies', []):
                self.goal_dag.add_edge(dep, goal_name)
        
        # Build Capability DAGs (one per goal)
        for goal in goals:
            goal_name = goal['name']
            self.capability_dags[goal_name] = nx.DiGraph()
        
        for cap in capabilities:
            cap_name = cap['name']
            # Check if capability has tasks
            has_tasks = any(t.get('parent_capability') == cap_name for t in tasks)
            self.node_info[cap_name] = NodeInfo(NodeType.CAPABILITY, cap, has_children=has_tasks)
            
            # Determine which goal(s) this capability belongs to
            parent_goal = cap.get('parent_goal')
            if parent_goal and parent_goal in self.capability_dags:
                cap_dag = self.capability_dags[parent_goal]
                cap_dag.add_node(cap_name)
                
                # Add regular dependencies
                for dep in cap.get('dependencies', []):
                    if dep in [c['name'] for c in capabilities]:
                        cap_dag.add_edge(dep, cap_name)
                
                # Handle cross-dependencies
                cross_deps = cap.get('cross_dependencies', [])
                if cross_deps:
                    self.cross_dependencies.setdefault(cap_name, {}).setdefault(parent_goal, []).extend(cross_deps)
                    # Add cross-dependency edges
                    for cross_dep in cross_deps:
                        if cross_dep in [c['name'] for c in capabilities]:
                            # Add the cross-dependency node to this goal's DAG if not present
                            if cross_dep not in cap_dag.nodes():
                                # Mark this node as a cross-dependency in this goal's context
                                cap_dag.add_node(cross_dep, is_cross_dep=True)
                            cap_dag.add_edge(cross_dep, cap_name)
        
        # Build Task DAGs (one per capability)
        for task in tasks:
            task_name = task['name']
            self.node_info[task_name] = NodeInfo(NodeType.TASK, task, has_children=False)
            
            parent_cap = task.get('parent_capability')
            if parent_cap:
                if parent_cap not in self.task_dags:
                    self.task_dags[parent_cap] = nx.DiGraph()
                
                task_dag = self.task_dags[parent_cap]
                task_dag.add_node(task_name)
                
                # Add task dependencies (check both top-level and interface)
                dependencies = task.get('dependencies', [])
                if not dependencies and 'interface' in task:
                    dependencies = task.get('interface', {}).get('dependencies', [])
                
                for dep in dependencies:
                    if dep in [t['name'] for t in tasks if t.get('parent_capability') == parent_cap]:
                        task_dag.add_edge(dep, task_name)
    
    # ========== Core Accessors ==========
    
    def get_goals(self) -> List[str]:
        """Get all goal names."""
        return list(self.goal_dag.nodes())
    
    def get_all_goals(self) -> List[str]:
        """Alias for get_goals for compatibility."""
        return self.get_goals()
    
    def get_capabilities_for_goal(self, goal: str) -> List[str]:
        """Get capabilities for a specific goal."""
        if goal in self.capability_dags:
            return list(self.capability_dags[goal].nodes())
        return []
    
    def get_tasks_for_capability(self, capability: str) -> List[str]:
        """Get tasks for a specific capability."""
        if capability in self.task_dags:
            return list(self.task_dags[capability].nodes())
        return []
    
    def get_goals_for_capability(self, capability: str) -> List[str]:
        """Get which goals contain a specific capability."""
        goals = []
        for goal, dag in self.capability_dags.items():
            if capability in dag.nodes():
                goals.append(goal)
        return goals
    
    def get_all_ancestors(self, node_name: str) -> Set[str]:
        """Get all ancestor nodes (nodes that must be completed before this one)."""
        ancestors = set()
        
        # Check in goal DAG
        if node_name in self.goal_dag:
            ancestors.update(nx.ancestors(self.goal_dag, node_name))
        
        # Check in capability DAGs
        for goal, dag in self.capability_dags.items():
            if node_name in dag:
                ancestors.update(nx.ancestors(dag, node_name))
        
        # Check in task DAGs
        for cap, dag in self.task_dags.items():
            if node_name in dag:
                ancestors.update(nx.ancestors(dag, node_name))
        
        return ancestors
    
    def is_cross_dependency(self, capability: str, in_goal: str) -> bool:
        """Check if a capability is a cross-dependency in a specific goal context."""
        cap_info = self.node_info.get(capability)
        if cap_info:
            parent_goal = cap_info.data.get('parent_goal')
            return parent_goal and parent_goal != in_goal
        return False
    
    def is_cross_dependency_node(self, capability: str, in_goal: str) -> bool:
        """Alias for is_cross_dependency for compatibility."""
        return self.is_cross_dependency(capability, in_goal)
    
    def get_cross_dependencies(self, capability: str) -> Dict[str, List[str]]:
        """Get cross-dependencies for a capability."""
        return self.cross_dependencies.get(capability, {})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get DAG statistics."""
        total_nodes = (len(self.goal_dag.nodes()) + 
                      sum(len(dag.nodes()) for dag in self.capability_dags.values()) +
                      sum(len(dag.nodes()) for dag in self.task_dags.values()))
        
        total_edges = (len(self.goal_dag.edges()) +
                      sum(len(dag.edges()) for dag in self.capability_dags.values()) +
                      sum(len(dag.edges()) for dag in self.task_dags.values()))
        
        goals_count = len(self.goal_dag.nodes())
        caps_count = sum(len(dag.nodes()) for dag in self.capability_dags.values())
        tasks_count = sum(len(dag.nodes()) for dag in self.task_dags.values())
        
        return {
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'total_goals': goals_count,
            'total_capabilities': caps_count,
            'total_tasks': tasks_count,
            # Compatibility aliases for visualization
            'goals': goals_count,
            'capabilities': caps_count, 
            'tasks': tasks_count,
            'is_valid': self.is_dag_valid()[0],
            'average_degree': total_edges / max(1, total_nodes),
            'density': total_edges / max(1, total_nodes * (total_nodes - 1))
        }
    
    def is_dag_valid(self) -> Tuple[bool, List]:
        """Check if all DAGs are acyclic."""
        cycles = []
        
        # Check goal DAG
        if not nx.is_directed_acyclic_graph(self.goal_dag):
            cycles.append(('goals', list(nx.simple_cycles(self.goal_dag))))
        
        # Check capability DAGs
        for goal, dag in self.capability_dags.items():
            if not nx.is_directed_acyclic_graph(dag):
                cycles.append((f'capabilities_{goal}', list(nx.simple_cycles(dag))))
        
        # Check task DAGs
        for cap, dag in self.task_dags.items():
            if not nx.is_directed_acyclic_graph(dag):
                cycles.append((f'tasks_{cap}', list(nx.simple_cycles(dag))))
        
        return len(cycles) == 0, cycles
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export the DAG structure to a dictionary."""
        return {
            'goals': [name for name in self.goal_dag.nodes()],
            'capabilities': {goal: list(dag.nodes()) for goal, dag in self.capability_dags.items()},
            'tasks': {cap: list(dag.nodes()) for cap, dag in self.task_dags.items()},
            'goal_edges': list(self.goal_dag.edges()),
            'capability_edges': {goal: list(dag.edges()) for goal, dag in self.capability_dags.items()},
            'task_edges': {cap: list(dag.edges()) for cap, dag in self.task_dags.items()},
            'node_info': {name: info.__dict__ for name, info in self.node_info.items()},
            'cross_dependencies': self.cross_dependencies
        }
    
    # ========== Execution Order ==========
    
    def get_execution_order(self, level: str, context: Optional[str] = None) -> List[str]:
        """
        Get topological execution order for a specific level.
        
        Args:
            level: 'goals', 'capabilities', or 'tasks'
            context: Goal name for capabilities, capability name for tasks
        
        Returns:
            Ordered list of nodes
        """
        try:
            if level == 'goals':
                return list(nx.topological_sort(self.goal_dag))
            elif level == 'capabilities':
                if context and context in self.capability_dags:
                    return list(nx.topological_sort(self.capability_dags[context]))
                else:
                    # Return all capabilities across all goals
                    all_caps = []
                    for goal in self.get_execution_order('goals'):
                        if goal in self.capability_dags:
                            caps = list(nx.topological_sort(self.capability_dags[goal]))
                            for cap in caps:
                                if cap not in all_caps:
                                    all_caps.append(cap)
                    return all_caps
            elif level == 'tasks':
                if context and context in self.task_dags:
                    return list(nx.topological_sort(self.task_dags[context]))
                return []
        except nx.NetworkXError:
            return []  # Cycle detected
    
    def get_complete_execution_order(self) -> List[Dict[str, Any]]:
        """
        Get complete execution order across all hierarchy levels.
        
        Returns:
            List of dicts with: name, type, level, parent
        """
        execution_order = []
        
        goal_order = self.get_execution_order('goals')
        
        for goal in goal_order:
            # Add goal
            execution_order.append({
                'name': goal,
                'type': 'goal',
                'level': 0,
                'parent': None
            })
            
            # Add capabilities for this goal
            cap_order = self.get_execution_order('capabilities', goal)
            for cap in cap_order:
                # Skip if cross-dependency from another goal
                if self.is_cross_dependency(cap, goal):
                    continue
                    
                execution_order.append({
                    'name': cap,
                    'type': 'capability', 
                    'level': 1,
                    'parent': goal
                })
                
                # Add tasks for this capability
                task_order = self.get_execution_order('tasks', cap)
                for task in task_order:
                    execution_order.append({
                        'name': task,
                        'type': 'task',
                        'level': 2,
                        'parent': cap
                    })
        
        return execution_order
    
    def format_complete_execution_order(self) -> str:
        """Get a formatted string representation of the complete execution order."""
        execution_order = self.get_complete_execution_order()
        
        lines = []
        for item in execution_order:
            indent = "  " * item['level']
            prefix = ""
            
            if item['type'] == 'goal':
                prefix = "🎯"
            elif item['type'] == 'capability':
                prefix = "📦"
            elif item['type'] == 'task':
                prefix = "✓"
            
            name_display = item['name'][:60] + "..." if len(item['name']) > 60 else item['name']
            lines.append(f"{indent}{prefix} {name_display}")
        
        return "\n".join(lines)
    
    # ========== Orchestration Strategy ==========
    
    def get_execution_waves(self, dag: nx.DiGraph) -> List[List[str]]:
        """
        Get execution waves where each wave contains nodes that can run in parallel.
        """
        if dag.number_of_nodes() == 0:
            return []
        
        waves = []
        remaining = dag.copy()
        
        while remaining.number_of_nodes() > 0:
            # Find nodes with no dependencies
            ready_nodes = [n for n in remaining.nodes() if remaining.in_degree(n) == 0]
            
            if not ready_nodes:
                break  # Cycle detected
            
            waves.append(ready_nodes)
            remaining.remove_nodes_from(ready_nodes)
        
        return waves
    
    def get_orchestration_strategy(self) -> Dict[str, Any]:
        """
        Get optimal orchestration strategy showing what can run in parallel.
        
        Returns:
            Dictionary with parallel execution opportunities at all levels
        """
        strategy = {
            'goal_waves': [],
            'capability_waves': {},
            'task_waves': {},
            'statistics': {}
        }
        
        # Goal-level parallelism
        strategy['goal_waves'] = self.get_execution_waves(self.goal_dag)
        
        # Capability-level parallelism per goal
        for goal in self.get_goals():
            if goal in self.capability_dags:
                strategy['capability_waves'][goal] = self.get_execution_waves(
                    self.capability_dags[goal]
                )
        
        # Task-level parallelism per capability  
        for cap in self.node_info:
            if cap in self.task_dags:
                strategy['task_waves'][cap] = self.get_execution_waves(
                    self.task_dags[cap]
                )
        
        # Calculate statistics
        total_goals = len(self.goal_dag.nodes())
        total_caps = sum(len(dag.nodes()) for dag in self.capability_dags.values())
        total_tasks = sum(len(dag.nodes()) for dag in self.task_dags.values())
        
        max_parallel_goals = max(len(w) for w in strategy['goal_waves']) if strategy['goal_waves'] else 0
        max_parallel_caps = 0
        if strategy['capability_waves']:
            for waves in strategy['capability_waves'].values():
                if waves:
                    max_parallel_caps = max(max_parallel_caps, max(len(w) for w in waves))
        
        max_parallel_tasks = 0
        if strategy['task_waves']:
            for waves in strategy['task_waves'].values():
                if waves:
                    max_parallel_tasks = max(max_parallel_tasks, max(len(w) for w in waves))
        
        strategy['statistics'] = {
            'total_goals': total_goals,
            'total_capabilities': total_caps,
            'total_tasks': total_tasks,
            'max_parallel_goals': max_parallel_goals,
            'max_parallel_capabilities': max_parallel_caps,
            'max_parallel_tasks': max_parallel_tasks,
            'parallelization_factor': (max_parallel_goals + max_parallel_caps + max_parallel_tasks) / 3.0
        }
        
        return strategy
    
    def get_ready_nodes(self, completed: Set[str] = None) -> Dict[str, List[str]]:
        """
        Get nodes ready to execute based on completed work.
        
        Args:
            completed: Set of completed node names
        
        Returns:
            Dict with ready goals, capabilities, and tasks
        """
        if completed is None:
            completed = set()
        
        ready = {
            'goals': [],
            'capabilities': [],
            'tasks': []
        }
        
        # Find ready goals
        for goal in self.goal_dag.nodes():
            if goal not in completed:
                deps = list(self.goal_dag.predecessors(goal))
                if all(d in completed for d in deps):
                    ready['goals'].append(goal)
        
        # Find ready capabilities
        for goal in self.goal_dag.nodes():
            # Goal must be started (ready or completed)
            if goal in completed or goal in ready['goals']:
                if goal in self.capability_dags:
                    for cap in self.capability_dags[goal].nodes():
                        if cap not in completed:
                            deps = list(self.capability_dags[goal].predecessors(cap))
                            if all(d in completed for d in deps):
                                ready['capabilities'].append(cap)
        
        # Find ready tasks
        for cap in self.task_dags:
            # Capability must be started (ready or completed)
            if cap in completed or cap in ready['capabilities']:
                for task in self.task_dags[cap].nodes():
                    if task not in completed:
                        deps = list(self.task_dags[cap].predecessors(task))
                        if all(d in completed for d in deps):
                            ready['tasks'].append(task)
        
        return ready
    
    def format_orchestration_summary(self) -> str:
        """Get a formatted summary of the orchestration strategy."""
        strategy = self.get_orchestration_strategy()
        stats = strategy['statistics']
        
        lines = [
            "=" * 50,
            "ORCHESTRATION SUMMARY",
            "=" * 50,
            f"Total Nodes: {stats['total_goals']} goals, {stats['total_capabilities']} capabilities, {stats['total_tasks']} tasks",
            f"Max Parallel: {stats['max_parallel_goals']} goals, {stats['max_parallel_capabilities']} capabilities, {stats['max_parallel_tasks']} tasks",
            f"Parallelization Factor: {stats['parallelization_factor']:.2f}",
            "",
            "Goal Execution Waves:"
        ]
        
        for i, wave in enumerate(strategy['goal_waves'], 1):
            if len(wave) > 1:
                lines.append(f"  Wave {i}: {', '.join(wave)} [PARALLEL]")
            else:
                lines.append(f"  Wave {i}: {wave[0]}")
        
        return "\n".join(lines)


def main():
    """Example usage."""
    yaml_file = Path("goals_decomp_results/capabilities_analysis/latest_final.yaml")
    if not yaml_file.exists():
        print("YAML file not found")
        return
    
    builder = HierarchicalDAGBuilder(str(yaml_file))
    
    # Show orchestration summary
    print(builder.format_orchestration_summary())
    
    # Get execution order
    print("\nComplete Execution Order:")
    order = builder.get_complete_execution_order()
    for item in order[:10]:
        indent = "  " * item['level']
        print(f"{indent}{item['type']}: {item['name'][:50]}")
    
    # Test ready nodes
    print("\nReady Nodes Simulation:")
    completed = set()
    ready = builder.get_ready_nodes(completed)
    print(f"Initially ready: {ready}")


if __name__ == "__main__":
    main()
