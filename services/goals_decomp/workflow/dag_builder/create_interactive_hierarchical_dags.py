"""
Interactive Hierarchical DAG Visualizer
Creates an interactive HTML visualization using the HierarchicalDAGBuilder.
Focuses purely on visualization aspects.
"""

import json
import webbrowser
import os
import sys
from typing import Dict, Any
from pathlib import Path
import networkx as nx

# Add parent directory and goals_decomp_workflow to path for imports
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'goals_decomp_workflow'))
from llm_batch_client import LLMBatchClient

# Import the DAG builder
try:
    from .hierarchical_dag_builder import HierarchicalDAGBuilder, NodeType
except ImportError:
    # When running as script, not as module
    from hierarchical_dag_builder import HierarchicalDAGBuilder, NodeType


class InteractiveDAGVisualizer:
    """
    Creates interactive visualizations for hierarchical DAGs.
    Consumes DAGs built by HierarchicalDAGBuilder.
    """
    
    def __init__(self, dag_builder: HierarchicalDAGBuilder, use_llm_keywords: bool = True):
        """
        Initialize the visualizer with a pre-built DAG.
        
        Args:
            dag_builder: An instance of HierarchicalDAGBuilder with DAGs already built
            use_llm_keywords: Whether to use LLM for keyword extraction
        """
        self.builder = dag_builder
        self.use_llm_keywords = use_llm_keywords
        
        # Initialize LLM client for keyword extraction if needed
        if use_llm_keywords:
            self.llm_client = LLMBatchClient(
                temperature=0.3,
                max_tokens=20
            )
            self.keyword_cache = {}
        
        # Extract labels for all nodes
        self.labels = {}
        self._extract_all_labels()
    
    def _extract_keyword(self, text: str) -> str:
        """Extract a short keyword from node name."""
        if not self.use_llm_keywords:
            # Simple extraction without LLM
            words = text.replace('_', ' ').replace('task', '').replace('capability', '').split()[:2]
            return ' '.join(words)[:20]
        
        # Check cache first
        if text in self.keyword_cache:
            return self.keyword_cache[text]
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a keyword extractor. Extract a 1-2 word keyword that captures the essence of the text. Return ONLY the keyword(s)."
                },
                {
                    "role": "user",
                    "content": f"Extract keyword from: {text}"
                }
            ]
            
            keyword = self.llm_client.single_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=20,
                enable_thinking=False
            )
            
            keyword = keyword.strip().strip('"').strip("'").strip()
            words = keyword.split()
            if len(words) > 2:
                keyword = ' '.join(words[:2])
            
            self.keyword_cache[text] = keyword
            print(f"  LLM: '{text[:40]}...' → '{keyword}'")
            
            return keyword
            
        except Exception as e:
            print(f"  Warning: LLM failed for '{text[:40]}...': {e}")
            fallback = ' '.join(text.replace('_', ' ').split()[:2])
            self.keyword_cache[text] = fallback
            return fallback
    
    def _extract_all_labels(self):
        """Extract labels for all nodes in the DAG."""
        print("Extracting node labels...")
        
        for node_name, node_info in self.builder.node_info.items():
            self.labels[node_name] = self._extract_keyword(node_name)
    
    def _get_plotly_layout(self, nodes: list) -> Dict:
        """Calculate node positions for Plotly visualization."""
        if len(nodes) == 0:
            return {}
        elif len(nodes) == 1:
            return {nodes[0]: (0, 0)}
        else:
            # Create a temporary graph for layout calculation
            G = nx.DiGraph()
            G.add_nodes_from(nodes)
            return nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    def _prepare_dag_data_for_js(self) -> Dict[str, Any]:
        """Prepare all DAG data for JavaScript consumption."""
        data = {
            'goal_dag': self._prepare_single_dag('goals'),
            'capability_dags': {},
            'task_dags': {},
            'labels': self.labels,
            'node_info': {},
            'orphanedTasksCount': len(self.builder.orphaned_tasks)
        }
        
        # Prepare node info
        for name, info in self.builder.node_info.items():
            data['node_info'][name] = {
                'type': info.type.value,
                'description': info.description,
                'has_children': info.has_children,
                'metadata': info.metadata
            }
        
        # Prepare goal DAG
        data['goal_dag'] = self._prepare_dag_with_layout(
            list(self.builder.goal_dag.nodes()),
            list(self.builder.goal_dag.edges()),
            'goal'
        )
        
        # Prepare capability DAGs for each goal
        for goal_name, cap_dag in self.builder.capability_dags.items():
            if cap_dag.number_of_nodes() > 0:
                # Identify cross-dependency nodes
                cross_dep_nodes = set()
                for node in cap_dag.nodes():
                    # Check if this node is marked as cross-dependency in the DAG
                    node_data = cap_dag.nodes[node]
                    if node_data.get('is_cross_dep', False):
                        cross_dep_nodes.add(node)
                
                dag_data = self._prepare_dag_with_layout(
                    list(cap_dag.nodes()),
                    list(cap_dag.edges()),
                    'capability'
                )
                # Add cross-dependency information
                dag_data['cross_dep_nodes'] = list(cross_dep_nodes)
                data['capability_dags'][goal_name] = dag_data
        
        # Prepare task DAGs for each capability
        for cap_name, task_dag in self.builder.task_dags.items():
            if task_dag.number_of_nodes() > 0:
                data['task_dags'][cap_name] = self._prepare_dag_with_layout(
                    list(task_dag.nodes()),
                    list(task_dag.edges()),
                    'task'
                )
        
        return data
    
    def _prepare_dag_with_layout(self, nodes: list, edges: list, node_type: str) -> Dict:
        """Prepare a single DAG with layout positions."""
        if not nodes:
            return {'nodes': {}, 'edges': [], 'labels': {}, 'metadata': {}}
        
        # Create temporary graph for layout
        G = nx.DiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        
        # Calculate positions
        if G.number_of_nodes() == 1:
            pos = {list(G.nodes())[0]: (0, 0)}
        else:
            pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # Format nodes with positions
        nodes_with_pos = {}
        for node in nodes:
            if node in pos:
                nodes_with_pos[node] = {
                    'x': pos[node][0],
                    'y': pos[node][1]
                }
        
        # Get metadata for nodes
        metadata = {}
        for node in nodes:
            if node in self.builder.node_info:
                info = self.builder.node_info[node]
                metadata[node] = {
                    'has_capabilities': info.has_children if info.type == NodeType.GOAL else False,
                    'has_tasks': info.has_children if info.type == NodeType.CAPABILITY else False
                }
        
        return {
            'nodes': nodes_with_pos,
            'edges': edges,
            'labels': {n: self.labels.get(n, n[:30]) for n in nodes},
            'metadata': metadata
        }
    
    def _prepare_single_dag(self, level: str) -> Dict:
        """Prepare a single level DAG for visualization."""
        if level == 'goals':
            nodes = list(self.builder.goal_dag.nodes())
            edges = list(self.builder.goal_dag.edges())
        else:
            return {'nodes': {}, 'edges': [], 'labels': {}, 'metadata': {}}
        
        return self._prepare_dag_with_layout(nodes, edges, level)
    
    def create_interactive_html(self, output_file: str = 'interactive_hierarchical_dag.html') -> str:
        """
        Create the interactive HTML visualization.
        
        Args:
            output_file: Name of the output HTML file
            
        Returns:
            Path to the created HTML file
        """
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Interactive Hierarchical DAG Navigator</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .navigation {
            background: #f5f5f5;
            padding: 15px;
            border-bottom: 2px solid #ddd;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .breadcrumb {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-grow: 1;
        }
        .breadcrumb-item {
            padding: 8px 15px;
            background: white;
            border-radius: 5px;
            cursor: pointer;
            border: 2px solid #ddd;
            transition: all 0.3s;
        }
        .breadcrumb-item:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        .breadcrumb-separator {
            color: #999;
            font-weight: bold;
        }
        #plotDiv {
            height: 700px;
            padding: 20px;
        }
        .info-panel {
            background: #f9f9f9;
            padding: 20px;
            border-top: 2px solid #ddd;
        }
        .info-title {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }
        .legend {
            display: flex;
            gap: 20px;
            justify-content: center;
            padding: 15px;
            background: #fafafa;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 3px;
            border: 2px solid #333;
        }
        .back-button {
            padding: 8px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.3s;
        }
        .back-button:hover {
            background: #764ba2;
        }
        .back-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .stats {
            background: #e8f4f8;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔄 Interactive Hierarchical DAG Navigator</h1>
            <p>Click on nodes to navigate through the hierarchy</p>
        </div>
        
        <div class="navigation">
            <button id="backButton" class="back-button" onclick="goBack()" disabled>← Back</button>
            <div class="breadcrumb" id="breadcrumb">
                <span class="breadcrumb-item" onclick="showGoals()">Goals</span>
            </div>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #FFD700;"></div>
                <span>Goals</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #87CEEB;"></div>
                <span>Capabilities (Same Goal)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #FF9999;"></div>
                <span>Capabilities (Cross-Goal)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #98FB98;"></div>
                <span>Tasks</span>
            </div>
        </div>
        
        <div id="plotDiv"></div>
        
        <div class="info-panel">
            <div class="info-title">ℹ️ Navigation Instructions:</div>
            <ul>
                <li><strong>Click</strong> on a goal node (gold) to view its capabilities</li>
                <li><strong>Click</strong> on a capability node (blue) to view its tasks</li>
                <li>Use the <strong>Back button</strong> or <strong>breadcrumb navigation</strong> to go back</li>
                <li><strong>Hover</strong> over nodes to see details</li>
                <li><strong>Hover</strong> over edges to see the dependency relationship</li>
                <li>Nodes with a <strong>★</strong> symbol have child elements to explore</li>
                <li>Nodes with a <strong>⇄</strong> symbol are cross-goal dependencies</li>
                <li><strong>Pink/Red nodes</strong> indicate capabilities from other goals (cross-dependencies)</li>
                <li><strong>Edge colors</strong> group dependencies by source node for clarity</li>
                <li><strong>Curved edges</strong> prevent overlapping for better visibility</li>
            </ul>
            
            <div class="stats" id="statsPanel">
                <!-- Stats will be populated by JavaScript -->
            </div>
        </div>
    </div>
    
    <script>
        // Data will be injected here
        const dagData = ___DAG_DATA___;
        
        let navigationHistory = [];
        let currentView = 'goals';
        let currentParent = null;
        
        function createPlotlyGraph(nodes, edges, labels, nodeType, metadata) {
            // Group edges by source node for color coding
            const edgesBySource = {};
            edges.forEach(edge => {
                const source = edge[0];
                if (!edgesBySource[source]) {
                    edgesBySource[source] = [];
                }
                edgesBySource[source].push(edge);
            });
            
            // Color palette for different edge groups
            const edgeColors = [
                '#FF6B6B', // Red
                '#4ECDC4', // Teal
                '#45B7D1', // Blue
                '#96CEB4', // Green
                '#FECA57', // Yellow
                '#B983FF', // Purple
                '#FD79A8', // Pink
                '#A29BFE', // Lavender
                '#6C5CE7', // Violet
                '#00B894'  // Mint
            ];
            
            // Create separate edge traces for each source node (different colors)
            const edgeTraces = [];
            const annotations = [];
            let colorIndex = 0;
            
            // Track edge pairs for curve adjustment
            const edgePairs = {};
            
            Object.entries(edgesBySource).forEach(([source, sourceEdges]) => {
                const edgeColor = edgeColors[colorIndex % edgeColors.length];
                colorIndex++;
                
                const edge_trace = {
                    x: [],
                    y: [],
                    mode: 'lines',
                    line: {
                        width: 2.5,
                        color: edgeColor,
                        shape: 'spline'  // Smooth curves
                    },
                    hoverinfo: 'text',
                    hovertext: [],
                    showlegend: false,
                    opacity: 0.7
                };
                
                sourceEdges.forEach((edge, idx) => {
                    const x0 = nodes[edge[0]].x;
                    const y0 = nodes[edge[0]].y;
                    const x1 = nodes[edge[1]].x;
                    const y1 = nodes[edge[1]].y;
                    
                    // Check if there's a parallel edge (bidirectional)
                    const reverseEdgeKey = `${edge[1]}-${edge[0]}`;
                    const edgeKey = `${edge[0]}-${edge[1]}`;
                    
                    let curveOffset = 0;
                    if (edgePairs[reverseEdgeKey]) {
                        // This is the second edge of a bidirectional pair
                        curveOffset = 0.15;
                    } else {
                        edgePairs[edgeKey] = true;
                        // Check if nodes are at similar height (parallel edges)
                        if (Math.abs(y1 - y0) < 0.3) {
                            curveOffset = 0.1 * (idx % 2 === 0 ? 1 : -1);
                        }
                    }
                    
                    // Add curved path via control point
                    if (curveOffset !== 0) {
                        const midX = (x0 + x1) / 2;
                        const midY = (y0 + y1) / 2;
                        // Calculate perpendicular offset
                        const perpX = -(y1 - y0) * curveOffset;
                        const perpY = (x1 - x0) * curveOffset;
                        
                        // Create curved path with intermediate points
                        const steps = 10;
                        for (let i = 0; i <= steps; i++) {
                            const t = i / steps;
                            // Quadratic Bezier curve
                            const px = (1-t)*(1-t)*x0 + 2*(1-t)*t*(midX + perpX) + t*t*x1;
                            const py = (1-t)*(1-t)*y0 + 2*(1-t)*t*(midY + perpY) + t*t*y1;
                            edge_trace.x.push(px);
                            edge_trace.y.push(py);
                            edge_trace.hovertext.push(`${labels[edge[0]]} → ${labels[edge[1]]}`);
                        }
                        edge_trace.x.push(null);
                        edge_trace.y.push(null);
                        edge_trace.hovertext.push('');
                    } else {
                        // Straight edge
                        edge_trace.x.push(x0, x1, null);
                        edge_trace.y.push(y0, y1, null);
                        edge_trace.hovertext.push(
                            `${labels[edge[0]]} → ${labels[edge[1]]}`,
                            `${labels[edge[0]]} → ${labels[edge[1]]}`,
                            ''
                        );
                    }
                    
                    // Calculate arrow position
                    const dx = x1 - x0;
                    const dy = y1 - y0;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    const nodeRadius = nodeType === 'goal' ? 0.15 : 
                                      nodeType === 'capability' ? 0.13 : 0.11;
                    
                    // Adjust arrow position for curved edges
                    let arrowX = x1 - (dx / dist) * nodeRadius;
                    let arrowY = y1 - (dy / dist) * nodeRadius;
                    let arrowStartX = x0 + (dx / dist) * 0.1;
                    let arrowStartY = y0 + (dy / dist) * 0.1;
                    
                    if (curveOffset !== 0) {
                        // Adjust arrow for curved edge
                        const t = 0.9; // Position along curve
                        const midX = (x0 + x1) / 2;
                        const midY = (y0 + y1) / 2;
                        const perpX = -(y1 - y0) * curveOffset;
                        const perpY = (x1 - x0) * curveOffset;
                        
                        arrowStartX = (1-t)*(1-t)*x0 + 2*(1-t)*t*(midX + perpX) + t*t*x1;
                        arrowStartY = (1-t)*(1-t)*y0 + 2*(1-t)*t*(midY + perpY) + t*t*y1;
                    }
                    
                    // Add arrow annotation with matching color
                    annotations.push({
                        ax: arrowStartX,
                        ay: arrowStartY,
                        x: arrowX,
                        y: arrowY,
                        xref: 'x',
                        yref: 'y',
                        axref: 'x',
                        ayref: 'y',
                        showarrow: true,
                        arrowhead: 3,
                        arrowsize: 1.3,
                        arrowwidth: 2,
                        arrowcolor: edgeColor,
                        opacity: 0.8
                    });
                });
                
                if (edge_trace.x.length > 0) {
                    edgeTraces.push(edge_trace);
                }
            });
            
            // Check if this is a capability DAG and get cross-dependency nodes
            const crossDepNodes = new Set();
            const currentDagData = nodeType === 'capability' && currentParent ?
                dagData.capability_dags[Object.keys(dagData.goal_dag.labels).find(g => 
                    dagData.goal_dag.labels[g] === currentParent || g === currentParent
                )] : null;
            
            if (currentDagData && currentDagData.cross_dep_nodes) {
                currentDagData.cross_dep_nodes.forEach(node => crossDepNodes.add(node));
            }
            
            // Create node trace
            const node_trace = {
                x: Object.values(nodes).map(n => n.x),
                y: Object.values(nodes).map(n => n.y),
                mode: 'markers+text',
                text: Object.keys(nodes).map(name => {
                    const label = labels[name];
                    const meta = metadata[name];
                    const hasChildren = meta && (meta.has_capabilities || meta.has_tasks);
                    const isCrossDep = crossDepNodes.has(name);
                    return (hasChildren ? label + ' ★' : label) + (isCrossDep ? ' ⇄' : '');
                }),
                textposition: 'middle center',
                textfont: {
                    size: 12,
                    color: 'black',
                    family: 'Arial Black'
                },
                customdata: Object.keys(nodes),
                hovertemplate: Object.keys(nodes).map(name => {
                    const isCrossDep = crossDepNodes.has(name);
                    return isCrossDep ? 
                        `%{customdata}<br><b>Cross-Goal Dependency</b><extra></extra>` : 
                        '%{customdata}<br><extra></extra>';
                }),
                marker: {
                    size: nodeType === 'goal' ? 80 : 
                          nodeType === 'capability' ? 70 : 60,
                    color: Object.keys(nodes).map(name => {
                        if (nodeType === 'goal') return '#FFD700';
                        if (nodeType === 'task') return '#98FB98';
                        // For capabilities, use different color for cross-dependencies
                        return crossDepNodes.has(name) ? '#FF9999' : '#87CEEB';
                    }),
                    line: {
                        color: Object.keys(nodes).map(name => {
                            return crossDepNodes.has(name) ? '#CC0000' : 'black';
                        }),
                        width: Object.keys(nodes).map(name => {
                            return crossDepNodes.has(name) ? 4 : 3;
                        })
                    }
                },
                showlegend: false
            };
            
            const layout = {
                title: {
                    text: nodeType === 'goal' ? 'Goal Dependencies' :
                          nodeType === 'capability' ? `Capabilities for: ${currentParent}` :
                          `Tasks for: ${currentParent}`,
                    font: { size: 20 }
                },
                showlegend: false,
                hovermode: 'closest',
                xaxis: {
                    showgrid: false,
                    zeroline: false,
                    showticklabels: false
                },
                yaxis: {
                    showgrid: false,
                    zeroline: false,
                    showticklabels: false
                },
                dragmode: 'pan',
                margin: { t: 50, b: 20, l: 20, r: 20 },
                annotations: annotations  // Add arrow annotations to layout
            };
            
            const config = {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                toImageButtonOptions: {
                    format: 'png',
                    filename: `dag_${nodeType}_${currentParent || 'main'}`
                }
            };
            
            // Combine all traces: edge traces first, then node trace
            const allTraces = [...edgeTraces, node_trace];
            Plotly.newPlot('plotDiv', allTraces, layout, config);
            
            // Add click handler for nodes
            document.getElementById('plotDiv').on('plotly_click', function(eventData) {
                if (eventData.points && eventData.points.length > 0) {
                    const point = eventData.points[0];
                    // Only handle clicks on nodes (not edges)
                    if (point.data.mode && point.data.mode.includes('markers')) {
                        const nodeName = point.customdata;
                        handleNodeClick(nodeName, nodeType);
                    }
                }
            });
            
            // Update stats panel
            updateStats(nodeType, Object.keys(nodes).length, edges.length);
        }
        
        function updateStats(nodeType, nodeCount, edgeCount) {
            const statsPanel = document.getElementById('statsPanel');
            const typeCapitalized = nodeType.charAt(0).toUpperCase() + nodeType.slice(1);
            statsPanel.innerHTML = `
                <strong>Current View:</strong> ${typeCapitalized}s | 
                <strong>Nodes:</strong> ${nodeCount} | 
                <strong>Connections:</strong> ${edgeCount}
                ${dagData.orphanedTasksCount > 0 ? `| <strong style="color: orange;">Orphaned Tasks:</strong> ${dagData.orphanedTasksCount}` : ''}
            `;
        }
        
        function handleNodeClick(nodeName, nodeType) {
            if (nodeType === 'goal') {
                const goalData = dagData.capability_dags[nodeName];
                if (goalData && goalData.nodes && Object.keys(goalData.nodes).length > 0) {
                    showCapabilities(nodeName);
                } else {
                    alert('No capabilities defined for this goal');
                }
            } else if (nodeType === 'capability') {
                const taskData = dagData.task_dags[nodeName];
                if (taskData && taskData.nodes && Object.keys(taskData.nodes).length > 0) {
                    showTasks(nodeName);
                } else {
                    alert('No tasks defined for this capability');
                }
            }
        }
        
        function showGoals() {
            currentView = 'goals';
            currentParent = null;
            updateBreadcrumb();
            createPlotlyGraph(
                dagData.goal_dag.nodes,
                dagData.goal_dag.edges,
                dagData.goal_dag.labels,
                'goal',
                dagData.goal_dag.metadata
            );
        }
        
        function showCapabilities(goalName) {
            navigationHistory.push({ view: 'goals', parent: null });
            currentView = 'capabilities';
            currentParent = dagData.labels[goalName] || goalName;
            updateBreadcrumb();
            
            const capData = dagData.capability_dags[goalName];
            createPlotlyGraph(
                capData.nodes,
                capData.edges,
                capData.labels,
                'capability',
                capData.metadata
            );
        }
        
        function showTasks(capabilityName) {
            navigationHistory.push({ view: currentView, parent: currentParent });
            currentView = 'tasks';
            currentParent = dagData.labels[capabilityName] || capabilityName;
            updateBreadcrumb();
            
            const taskData = dagData.task_dags[capabilityName];
            createPlotlyGraph(
                taskData.nodes,
                taskData.edges,
                taskData.labels,
                'task',
                taskData.metadata
            );
        }
        
        function goBack() {
            if (navigationHistory.length > 0) {
                const prev = navigationHistory.pop();
                if (prev.view === 'goals') {
                    showGoals();
                } else if (prev.view === 'capabilities') {
                    // Find the goal name from parent
                    for (let goalName in dagData.goal_dag.labels) {
                        if (dagData.goal_dag.labels[goalName] === prev.parent || goalName === prev.parent) {
                            showCapabilities(goalName);
                            navigationHistory.pop(); // Remove the entry added by showCapabilities
                            break;
                        }
                    }
                }
            }
        }
        
        function updateBreadcrumb() {
            const breadcrumb = document.getElementById('breadcrumb');
            const backButton = document.getElementById('backButton');
            
            let html = '<span class="breadcrumb-item" onclick="showGoals()">Goals</span>';
            
            if (currentView === 'capabilities' || currentView === 'tasks') {
                html += ' <span class="breadcrumb-separator">→</span> ';
                html += `<span class="breadcrumb-item">${currentParent}</span>`;
            }
            
            breadcrumb.innerHTML = html;
            backButton.disabled = navigationHistory.length === 0;
        }
        
        // Initialize with goal view
        showGoals();
    </script>
</body>
</html>
"""
        
        # Prepare and inject data
        dag_data = self._prepare_dag_data_for_js()
        html_content = html_content.replace('___DAG_DATA___', json.dumps(dag_data))
        
        # Save HTML file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✅ Interactive visualization created: {output_file}")
        print(f"📂 Full path: {os.path.abspath(output_file)}")
        
        return os.path.abspath(output_file)


def main():
    """Main function to demonstrate the separated architecture."""
    print("\n" + "="*60)
    print("INTERACTIVE DAG VISUALIZATION")
    print("="*60)
    
    # Check if plotly is installed
    try:
        import plotly
        print("✅ Plotly is installed")
    except ImportError:
        print("❌ Plotly is not installed. Installing...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'plotly'])
        print("✅ Plotly installed successfully")
    
    # Use the consolidated workflow YAML file
    parent_dir = Path(__file__).parent.parent
    yaml_file = parent_dir / "goals_decomp_results" / "capabilities_analysis" / "latest_final.yaml"
    
    if not yaml_file.exists():
        # not found, stop execution
        print(f"❌ Error: No decomposition YAML found.")
        return
    
    yaml_file = str(yaml_file)
    
    print(f"\n📄 Loading: {yaml_file}")
    
    try:
        # Step 1: Build the DAG using the builder
        print("\n1️⃣ Building DAG structure...")
        dag_builder = HierarchicalDAGBuilder(yaml_file, verbose=True)
        
        # Get statistics
        stats = dag_builder.get_statistics()
        # print(f"\n📊 DAG Statistics:")
        # print(f"   • Total nodes: {stats['total_nodes']}")
        # print(f"   • Total edges: {stats['total_edges']}")
        # print(f"   • Goals: {stats['goals']}")
        # print(f"   • Capabilities: {stats['capabilities']}")
        # print(f"   • Tasks: {stats['tasks']}")
        # print(f"   • Valid DAG: {stats['is_valid']}")
        
        # Step 2: Create visualization
        print("\n2️⃣ Creating interactive visualization...")
        print("🤖 Extracting keywords for node labels...")
        
        visualizer = InteractiveDAGVisualizer(dag_builder, use_llm_keywords=True)
        html_file = visualizer.create_interactive_html()
        
        # Open in browser
        webbrowser.open(f'file://{html_file}')
        
        print("\n" + "="*60)
        print("SUCCESS!")
        print("="*60)
        print("\n📋 Architecture:")
        print("  • DAG Builder: Handles all graph construction and traversal")
        print("  • Visualizer: Focuses purely on interactive visualization")
        print("\n📋 Instructions:")
        print("  • Click on goal nodes (gold) to see capabilities")
        print("  • Click on capability nodes (blue) to see tasks")
        print("  • Use Back button or breadcrumbs to navigate")
        print("  • Nodes with ★ have child elements")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()