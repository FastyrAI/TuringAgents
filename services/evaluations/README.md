# Evaluations Service

The Evaluations Service is a comprehensive AI agent evaluation framework designed to assess agent performance across diverse tasks, environments, and capabilities. This service provides standardized evaluation pipelines, automated reporting, and integration with agent-specific benchmarks and datasets.

## Overview

This service enables systematic evaluation of AI agents across multiple dimensions:
- **Task Completion**: Success rates, goal achievement, multi-step reasoning
- **Tool Usage**: Tool selection accuracy, API calls, function execution
- **Planning & Reasoning**: Multi-step planning, decision-making, problem decomposition
- **Code Generation & Execution**: Programming tasks, debugging, software engineering
- **Interactive Environments**: Web navigation, game playing, simulated environments
- **Safety & Alignment**: Instruction adherence, harmful content detection, policy compliance
- **User Experience**: Response quality, helpfulness, coherence, latency

## Supported Benchmarks & Datasets

### Agent-Specific Benchmarks

#### **AgentBench**
- **Description**: Comprehensive benchmark with 8 distinct environments for LLM-as-Agent evaluation
- **Tasks**: Operating systems, databases, knowledge graphs, digital card games, lateral thinking puzzles, house-holding, web shopping, web browsing
- **Metrics**: Success rate, efficiency, reasoning quality
- **Dataset**: `thudm/agentbench` via Hugging Face

#### **SWE-bench** (Software Engineering Benchmark)
- **Description**: Real-world software engineering tasks from GitHub issues
- **Tasks**: Bug fixing, feature implementation, code review
- **Metrics**: Test pass rate, code quality, time to completion
- **Dataset**: `princeton-nlp/swe-bench` via Hugging Face

#### **WebArena**
- **Description**: Realistic web-based tasks in interactive environments
- **Tasks**: E-commerce, content management, forum navigation, collaborative software
- **Metrics**: Task completion rate, action efficiency, goal achievement
- **Dataset**: Available via official WebArena repository

#### **ToolBench**
- **Description**: Tool-use evaluation across 16,000+ real-world APIs
- **Tasks**: API discovery, parameter filling, multi-step tool usage
- **Metrics**: Tool selection accuracy, execution success, API call correctness
- **Dataset**: `toolbench/toolbench` via Hugging Face

### Planning & Reasoning

#### **PlanBench**
- **Description**: Multi-step planning tasks requiring sequential reasoning
- **Tasks**: Travel planning, resource allocation, scheduling
- **Metrics**: Plan quality, execution success, optimality
- **Dataset**: Custom benchmark with procedurally generated tasks

#### **ReAct Benchmark**
- **Description**: Reasoning and Acting tasks requiring interleaved thought and action
- **Tasks**: Question answering with tool use, fact verification, multi-hop reasoning
- **Metrics**: Reasoning quality, action appropriateness, final accuracy
- **Dataset**: `react-benchmark` via research repositories

### Code Generation & Software Engineering

#### **HumanEval-X**
- **Description**: Multi-language code generation benchmark
- **Tasks**: Function implementation in Python, JavaScript, Java, Go, C++
- **Metrics**: Pass@k, code quality, execution correctness
- **Dataset**: `THUDM/humaneval-x` via Hugging Face

#### **MBPP** (Mostly Basic Programming Problems)
- **Description**: Python programming tasks with test cases
- **Tasks**: Algorithm implementation, data structure manipulation
- **Metrics**: Test pass rate, code efficiency, style compliance
- **Dataset**: `mbpp` via Hugging Face

#### **CodeContests**
- **Description**: Competitive programming problems
- **Tasks**: Algorithm design, optimization, complex problem solving
- **Metrics**: Solution correctness, time complexity, code elegance
- **Dataset**: `deepmind/code_contests` via Hugging Face

### Interactive Environments

#### **MiniWoB++**
- **Description**: Web-based interaction tasks
- **Tasks**: Form filling, button clicking, text entry, navigation
- **Metrics**: Task success rate, action efficiency, error rate
- **Dataset**: Available via OpenAI Gym integration

#### **ALFWorld**
- **Description**: Text-based interactive environments
- **Tasks**: Household tasks, object manipulation, spatial reasoning
- **Metrics**: Task completion, step efficiency, instruction following
- **Dataset**: `alfworld/alfworld` via official repository

#### **BabyAI**
- **Description**: Gridworld environments with language instructions
- **Tasks**: Navigation, object interaction, instruction following
- **Metrics**: Success rate, sample efficiency, generalization
- **Dataset**: Available via Gym-MiniGrid

### Safety & Alignment

#### **HarmBench**
- **Description**: Safety evaluation for AI agents
- **Tasks**: Harmful request detection, policy adherence, content filtering
- **Metrics**: Safety score, false positive rate, policy compliance
- **Dataset**: `HarmBench/HarmBench` via Hugging Face

#### **TruthfulQA**
- **Description**: Truthfulness evaluation in question answering
- **Tasks**: Fact verification, misinformation detection, knowledge accuracy
- **Metrics**: Truthfulness score, informativeness, calibration
- **Dataset**: `truthful_qa` via Hugging Face

#### **Anthropic Red Team**
- **Description**: Adversarial prompts for safety testing
- **Tasks**: Jailbreak resistance, harmful content generation, alignment testing
- **Metrics**: Robustness score, safety compliance, failure modes
- **Dataset**: Custom collection of safety-focused prompts

### Data Analysis & Research

#### **InfiAgent-DABench**
- **Description**: Data analysis tasks for agent evaluation
- **Tasks**: Data exploration, visualization, statistical analysis, reporting
- **Metrics**: Analysis quality, insight generation, code correctness
- **Dataset**: `InfiAgent/InfiAgent-DABench` via Hugging Face

#### **MLAgentBench**
- **Description**: Machine learning research tasks
- **Tasks**: Model development, hyperparameter tuning, experiment design
- **Metrics**: Model performance, research methodology, reproducibility
- **Dataset**: Custom benchmark with ML research scenarios

## Key Evaluation Metrics

### Performance Metrics
- **Task Success Rate**: Percentage of successfully completed tasks
- **Goal Achievement**: Whether the agent achieved the intended objective
- **Step Efficiency**: Number of actions taken vs. optimal path
- **Time to Completion**: Latency and response time measurements
- **Resource Utilization**: Memory, compute, and API usage efficiency

### Quality Metrics
- **Instruction Adherence**: How well the agent follows given instructions
- **Tool Call Accuracy**: Correctness of tool selection and parameter usage
- **Code Quality**: Readability, efficiency, and correctness of generated code
- **Reasoning Quality**: Logical consistency and coherence of thought processes
- **Output Relevance**: Appropriateness and usefulness of responses

### Safety & Reliability Metrics
- **Hallucination Rate**: Frequency of fabricated or incorrect information
- **Toxicity Score**: Detection of harmful, biased, or inappropriate content
- **Policy Compliance**: Adherence to organizational and ethical guidelines
- **Robustness**: Performance under adversarial or edge case conditions
- **Error Recovery**: Ability to handle and recover from failures

### User Experience Metrics
- **Helpfulness**: Perceived usefulness of agent responses
- **Coherence**: Logical flow and consistency in multi-turn interactions
- **User Satisfaction**: CSAT/NPS scores from user feedback
- **Trust Score**: User confidence in agent capabilities and reliability

## Features

- **Comprehensive Agent Benchmarking**: Support for 15+ agent-specific evaluation benchmarks
- **Multi-Environment Testing**: Web, code, interactive, and simulated environments
- **Flexible Configuration**: YAML-based configuration for custom evaluation suites
- **Automated Evaluation Pipeline**: End-to-end evaluation with minimal setup
- **Real-time Monitoring**: Live tracking of agent performance during evaluation
- **Detailed Reporting**: JSON, HTML, and interactive reports with performance metrics
- **Agent Agnostic**: Support for any agent architecture or framework
- **Batch Processing**: Efficient evaluation of multiple agents and configurations
- **Result Tracking**: Integration with experiment tracking systems (W&B, MLflow)
- **Extensible Architecture**: Easy addition of new benchmarks and metrics
- **Safety Guardrails**: Built-in safety checks and content filtering
- **Performance Profiling**: Detailed analysis of agent execution patterns

## Installation

### Prerequisites
- Python 3.9+
- Docker (for containerized environments)
- At least 16GB RAM (32GB+ recommended for complex agents)
- CUDA-compatible GPU (optional, for model-based agents)

### Setup
```bash
# Navigate to the evaluations service
cd services/evaluations

# Install dependencies
pip install -e .

# Install optional dependencies for specific benchmarks
pip install -e ".[web]"      # For web-based evaluations
pip install -e ".[code]"     # For code generation tasks
pip install -e ".[safety]"   # For safety evaluations

# Download evaluation datasets (optional - will auto-download on first use)
python scripts/download_datasets.py
```

## Quick Start

### 1. Basic Agent Evaluation
```bash
# Run AgentBench evaluation on your agent
python -m evaluations.cli evaluate \
  --agent-config configs/my_agent.yaml \
  --benchmarks agentbench \
  --output-dir ./results

# Run multiple benchmarks
python -m evaluations.cli evaluate \
  --agent-config configs/my_agent.yaml \
  --benchmarks agentbench,swe-bench,toolbench \
  --output-dir ./results
```

### 2. Custom Configuration
```bash
# Use a custom evaluation configuration
python -m evaluations.cli evaluate \
  --config configs/comprehensive_agent_eval.yaml \
  --agent-config configs/my_agent.yaml \
  --output-dir ./results
```

### 3. API Usage
```python
from evaluations import AgentEvaluationSuite
from evaluations.agents import AgentWrapper

# Initialize evaluation suite
suite = AgentEvaluationSuite(config_path="configs/agent_eval.yaml")

# Wrap your agent
agent = AgentWrapper(
    agent_class=MyAgent,
    config={"model": "gpt-4", "tools": ["calculator", "web_search"]}
)

# Run evaluations
results = suite.evaluate(agent)

# Generate report
suite.generate_report(results, output_dir="./results")
```

## Configuration

### Agent Configuration (`configs/my_agent.yaml`)
```yaml
agent:
  name: "MyAgent"
  type: "tool_using"  # tool_using, code_generating, web_navigating, etc.
  
  # Agent initialization
  class_path: "my_agents.MyAgent"
  init_params:
    model: "gpt-4-turbo"
    temperature: 0.1
    max_tokens: 4096
  
  # Available tools
  tools:
    - name: "web_search"
      config: {"api_key": "${SEARCH_API_KEY}"}
    - name: "calculator"
    - name: "code_executor"
      config: {"timeout": 30}
  
  # Safety settings
  safety:
    content_filter: true
    max_iterations: 50
    timeout: 300
```

### Evaluation Configuration (`configs/agent_eval.yaml`)
```yaml
benchmarks:
  - name: agentbench
    enabled: true
    environments: ["os", "db", "kg", "web"]
    num_samples: 100
  
  - name: swe_bench
    enabled: true
    difficulty: ["easy", "medium"]  # easy, medium, hard
    num_samples: 50
  
  - name: toolbench
    enabled: true
    categories: ["search", "calculator", "weather"]
    num_samples: 200

evaluation:
  parallel_workers: 4
  timeout_per_task: 600  # seconds
  max_retries: 3
  save_trajectories: true

safety:
  enable_content_filter: true
  enable_safety_classifier: true
  max_harmful_outputs: 0

reporting:
  formats: ["json", "html", "interactive"]
  include_trajectories: true
  include_error_analysis: true
  generate_plots: true
```

## Architecture

```
evaluations/
├── src/evaluations/
│   ├── __init__.py
│   ├── cli.py                    # Command-line interface
│   ├── core/
│   │   ├── evaluator.py          # Main evaluation engine
│   │   ├── agent_wrapper.py      # Agent abstraction layer
│   │   ├── metrics.py            # Evaluation metrics
│   │   └── safety.py             # Safety checks and filters
│   ├── benchmarks/
│   │   ├── base.py              # Base benchmark class
│   │   ├── agentbench/          # AgentBench implementation
│   │   ├── swe_bench/           # Software engineering tasks
│   │   ├── webarena/            # Web interaction tasks
│   │   ├── toolbench/           # Tool usage evaluation
│   │   ├── planning/            # Planning and reasoning
│   │   └── safety/              # Safety evaluations
│   ├── environments/
│   │   ├── web.py               # Web-based environments
│   │   ├── code.py              # Code execution environments
│   │   ├── interactive.py       # Interactive environments
│   │   └── simulated.py         # Simulated environments
│   ├── agents/
│   │   ├── base.py              # Base agent interface
│   │   ├── wrapper.py           # Agent wrapper utilities
│   │   └── registry.py          # Agent registry
│   ├── datasets/
│   │   ├── loader.py            # Dataset loading utilities
│   │   └── preprocessor.py      # Data preprocessing
│   ├── reporting/
│   │   ├── generator.py         # Report generation
│   │   ├── visualizer.py        # Data visualization
│   │   └── templates/           # HTML templates
│   └── utils/
│       ├── config.py            # Configuration management
│       ├── logging.py           # Logging utilities
│       └── safety.py            # Safety utilities
├── tests/                       # Unit and integration tests
├── configs/                     # Configuration files
├── scripts/                     # Utility scripts
└── docs/                       # Documentation
```

## Development

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/benchmarks/
pytest tests/agents/
pytest tests/integration/

# Run with coverage
pytest --cov=evaluations tests/
```

### Adding New Benchmarks
1. Create a new benchmark class inheriting from `BaseBenchmark`
2. Implement required methods: `setup()`, `run_task()`, `evaluate()`, `cleanup()`
3. Add configuration schema
4. Add tests
5. Update documentation

Example:
```python
from evaluations.benchmarks.base import BaseBenchmark

class MyBenchmark(BaseBenchmark):
    def setup(self):
        # Initialize benchmark environment
        pass
    
    def run_task(self, agent, task):
        # Execute task with agent
        pass
    
    def evaluate(self, results):
        # Compute metrics
        pass
    
    def cleanup(self):
        # Clean up resources
        pass
```

### Adding New Agents
1. Implement the `BaseAgent` interface
2. Register your agent in the agent registry
3. Create configuration schema
4. Add tests

Example:
```python
from evaluations.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, config):
        self.config = config
    
    def act(self, observation, available_actions=None):
        # Generate action based on observation
        return action
    
    def reset(self):
        # Reset agent state
        pass
```

## Performance Considerations

- **Evaluation Time**: Agent evaluations can be time-intensive (hours for comprehensive suites)
- **Resource Usage**: Interactive environments may require significant compute resources
- **Parallelization**: Use multiple workers for faster evaluation
- **Caching**: Enable result caching to avoid re-running expensive evaluations
- **Timeouts**: Set appropriate timeouts to prevent hanging evaluations

## Troubleshooting

### Common Issues

1. **Agent Timeout Errors**
   - Increase timeout values in configuration
   - Check agent implementation for infinite loops
   - Monitor resource usage

2. **Environment Setup Failures**
   - Verify Docker installation for containerized environments
   - Check API keys and credentials
   - Ensure required dependencies are installed

3. **Evaluation Errors**
   - Check agent interface implementation
   - Verify benchmark dataset availability
   - Review error logs for specific issues

### Getting Help

- Check the [documentation](docs/)
- Review [examples](docs/examples/)
- Open an issue on GitHub
- Join our Discord community

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas for Contribution
- New benchmark implementations
- Agent interface improvements
- Performance optimizations
- Documentation improvements
- Bug fixes and testing
- Safety and alignment features

## License

This project is licensed under the MIT License. See [LICENSE](../../LICENSE) for details.

## Acknowledgments

This service builds upon excellent work from:
- AgentBench team for comprehensive agent evaluation
- SWE-bench for software engineering benchmarks
- WebArena for web interaction evaluation
- ToolBench for tool usage assessment
- The broader AI agent research community

## Citation

If you use this evaluation service in your research, please cite:

```bibtex
@software{turing_agents_evaluations,
  title={Turing Agents Evaluations Service},
  author={Turing Agents Team},
  year={2024},
  url={https://github.com/your-org/turing-agents-monorepo}
}
```