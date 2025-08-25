# Evaluations Service

The Evaluations Service is a comprehensive LLM evaluation framework designed to assess Large Language Model performance across diverse benchmarks and datasets. This service provides standardized evaluation pipelines, automated reporting, and integration with popular open-source evaluation datasets.

## Overview

This service enables systematic evaluation of LLMs across multiple dimensions:
- **Language Understanding**: GLUE, SuperGLUE, MMLU
- **Reasoning**: HellaSwag, WinoGrande, BIG-bench
- **Mathematical Problem Solving**: GSM8K, MATH
- **Code Generation**: HumanEval, MBPP
- **Safety & Truthfulness**: TruthfulQA, Anthropic Red Team
- **Multimodal Understanding**: VQAv2, MMMU
- **Instruction Following**: Self-Instruct, Alpaca, MT-Bench

## Supported Benchmarks & Datasets

### Core Language Understanding
- **GLUE** (General Language Understanding Evaluation)
  - 9 tasks covering sentiment analysis, textual entailment, similarity
  - Dataset: `glue` via Hugging Face datasets
- **SuperGLUE** 
  - More challenging successor to GLUE with 8 tasks
  - Dataset: `super_glue` via Hugging Face datasets
- **MMLU** (Massive Multitask Language Understanding)
  - 57 subjects across STEM, humanities, social sciences
  - Dataset: `cais/mmlu` via Hugging Face datasets

### Reasoning & Common Sense
- **HellaSwag**
  - 70,000 multiple-choice questions about everyday situations
  - Dataset: `hellaswag` via Hugging Face datasets
- **WinoGrande**
  - 44,000 fill-in-the-blank commonsense problems
  - Dataset: `winogrande` via Hugging Face datasets
- **BIG-bench**
  - 204 diverse tasks for comprehensive evaluation
  - Dataset: `bigbench` via official repository

### Mathematical Reasoning
- **GSM8K** (Grade School Math 8K)
  - 8,500 grade-school math word problems
  - Dataset: `gsm8k` via Hugging Face datasets
- **MATH**
  - 12,000 middle/high school mathematics problems
  - Dataset: `hendrycks/math` via Hugging Face datasets

### Code Generation
- **HumanEval**
  - 164 handwritten Python programming problems
  - Dataset: `openai_humaneval` via Hugging Face datasets
- **MBPP** (Mostly Basic Programming Problems)
  - 974 Python programming tasks with test cases
  - Dataset: `mbpp` via Hugging Face datasets

### Safety & Truthfulness
- **TruthfulQA**
  - Tests truthful answer generation across 38 categories
  - Dataset: `truthful_qa` via Hugging Face datasets
- **Anthropic Red Team**
  - Adversarial prompts for safety testing
  - Dataset: Custom collection of safety-focused prompts

### Multimodal (Future Support)
- **VQAv2** (Visual Question Answering)
  - 265,000 images with 3M questions
- **MMMU** (Massive Multi-discipline Multimodal Understanding)
  - 183 subjects across various disciplines

### Instruction Following
- **Self-Instruct**
  - 52,000 instruction-following examples
  - Dataset: `yizhongw/self_instruct` via Hugging Face datasets
- **MT-Bench**
  - 80 challenging multi-turn questions for chat models
  - Dataset: `lmsys/mt_bench` via Hugging Face datasets

## Features

- **Comprehensive Benchmarking**: Support for 15+ evaluation benchmarks
- **Flexible Configuration**: YAML-based configuration for custom evaluation suites
- **Automated Evaluation Pipeline**: End-to-end evaluation with minimal setup
- **Detailed Reporting**: JSON and HTML reports with performance metrics
- **Model Agnostic**: Support for any model with text generation capabilities
- **Batch Processing**: Efficient evaluation of multiple models
- **Result Tracking**: Integration with experiment tracking systems
- **Extensible Architecture**: Easy addition of new benchmarks and metrics

## Installation

### Prerequisites
- Python 3.9+
- CUDA-compatible GPU (recommended for large models)
- At least 16GB RAM (32GB+ recommended)

### Setup
```bash
# Navigate to the evaluations service
cd services/evaluations

# Install dependencies
pip install -e .

# Download evaluation datasets (optional - will auto-download on first use)
python scripts/download_datasets.py
```

## Quick Start

### 1. Basic Evaluation
```bash
# Run MMLU evaluation on a Hugging Face model
python -m evaluations.cli evaluate \
  --model "microsoft/DialoGPT-medium" \
  --benchmarks mmlu \
  --output-dir ./results

# Run multiple benchmarks
python -m evaluations.cli evaluate \
  --model "microsoft/DialoGPT-medium" \
  --benchmarks mmlu,hellaswag,gsm8k \
  --output-dir ./results
```

### 2. Custom Configuration
```bash
# Use a custom configuration file
python -m evaluations.cli evaluate \
  --config configs/comprehensive_eval.yaml \
  --model "your-model-name" \
  --output-dir ./results
```

### 3. API Usage
```python
from evaluations import EvaluationSuite, ModelWrapper

# Initialize evaluation suite
suite = EvaluationSuite(config_path="configs/basic_eval.yaml")

# Wrap your model
model = ModelWrapper.from_huggingface("microsoft/DialoGPT-medium")

# Run evaluations
results = suite.evaluate(model)

# Generate report
suite.generate_report(results, output_dir="./results")
```

## Configuration

### Basic Configuration (`configs/basic_eval.yaml`)
```yaml
benchmarks:
  - name: mmlu
    enabled: true
    num_samples: 1000  # Use subset for faster evaluation
  - name: hellaswag
    enabled: true
    num_samples: 500
  - name: gsm8k
    enabled: true
    num_samples: 100

evaluation:
  batch_size: 8
  max_length: 2048
  temperature: 0.0
  top_p: 1.0

reporting:
  formats: ["json", "html"]
  include_examples: true
  num_examples: 10
```

### Comprehensive Configuration (`configs/comprehensive_eval.yaml`)
```yaml
benchmarks:
  # Language Understanding
  - name: glue
    enabled: true
    tasks: ["sst2", "mrpc", "qqp", "mnli", "qnli", "rte", "wnli"]
  - name: mmlu
    enabled: true
    subjects: ["all"]  # or specify specific subjects
  
  # Reasoning
  - name: hellaswag
    enabled: true
  - name: winogrande
    enabled: true
  
  # Math
  - name: gsm8k
    enabled: true
  - name: math
    enabled: true
    subjects: ["algebra", "geometry", "probability"]
  
  # Code
  - name: humaneval
    enabled: true
  - name: mbpp
    enabled: true
  
  # Safety
  - name: truthfulqa
    enabled: true

evaluation:
  batch_size: 4
  max_length: 4096
  temperature: 0.0
  num_workers: 4

reporting:
  formats: ["json", "html", "csv"]
  include_examples: true
  generate_plots: true
```

## Architecture

```
evaluations/
├── src/evaluations/
│   ├── __init__.py
│   ├── cli.py                 # Command-line interface
│   ├── core/
│   │   ├── evaluator.py       # Main evaluation engine
│   │   ├── model_wrapper.py   # Model abstraction layer
│   │   └── metrics.py         # Evaluation metrics
│   ├── benchmarks/
│   │   ├── base.py           # Base benchmark class
│   │   ├── language/         # Language understanding benchmarks
│   │   ├── reasoning/        # Reasoning benchmarks
│   │   ├── math/            # Mathematical reasoning
│   │   ├── code/            # Code generation
│   │   └── safety/          # Safety and truthfulness
│   ├── datasets/
│   │   ├── loader.py        # Dataset loading utilities
│   │   └── preprocessor.py  # Data preprocessing
│   ├── reporting/
│   │   ├── generator.py     # Report generation
│   │   └── templates/       # HTML templates
│   └── utils/
│       ├── config.py        # Configuration management
│       └── logging.py       # Logging utilities
├── tests/                   # Unit and integration tests
├── configs/                 # Configuration files
├── scripts/                 # Utility scripts
└── docs/                   # Documentation
```

## Development

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/benchmarks/
pytest tests/integration/

# Run with coverage
pytest --cov=evaluations tests/
```

### Adding New Benchmarks
1. Create a new benchmark class inheriting from `BaseBenchmark`
2. Implement required methods: `load_dataset()`, `evaluate()`, `compute_metrics()`
3. Add configuration schema
4. Add tests
5. Update documentation

Example:
```python
from evaluations.benchmarks.base import BaseBenchmark

class MyBenchmark(BaseBenchmark):
    def load_dataset(self):
        # Load your dataset
        pass
    
    def evaluate(self, model, dataset):
        # Run evaluation
        pass
    
    def compute_metrics(self, predictions, references):
        # Compute metrics
        pass
```

### Code Style
- Follow PEP 8
- Use type hints
- Document all public methods
- Run `black` and `isort` for formatting

## Performance Considerations

- **Memory Usage**: Large models may require significant GPU memory
- **Evaluation Time**: Full benchmark suites can take hours to complete
- **Dataset Size**: Some datasets are large (MMLU: ~1GB, BIG-bench: ~10GB)
- **Parallelization**: Use multiple workers for faster evaluation

## Troubleshooting

### Common Issues

1. **Out of Memory Errors**
   - Reduce batch size
   - Use model sharding
   - Enable gradient checkpointing

2. **Slow Evaluation**
   - Use subset sampling for development
   - Enable parallel processing
   - Use faster hardware

3. **Dataset Download Issues**
   - Check internet connection
   - Verify Hugging Face credentials
   - Use manual download scripts

### Getting Help

- Check the [documentation](docs/)
- Review [examples](docs/examples/)
- Open an issue on GitHub
- Join our Discord community

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas for Contribution
- New benchmark implementations
- Performance optimizations
- Documentation improvements
- Bug fixes and testing
- Integration with new model types

## License

This project is licensed under the MIT License. See [LICENSE](../../LICENSE) for details.

## Acknowledgments

This service builds upon the excellent work of:
- Hugging Face Datasets and Transformers
- OpenAI for HumanEval
- Anthropic for safety evaluation frameworks
- The broader ML evaluation community

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