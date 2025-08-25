"""
Command-line interface for the evaluations service.
"""

import click
import yaml
from pathlib import Path
from typing import List, Optional

from .core.evaluator import EvaluationSuite
from .core.model_wrapper import ModelWrapper
from .utils.logging import setup_logging


@click.group()
@click.version_option()
def main():
    """Turing Agents LLM Evaluation Service"""
    pass


@main.command()
@click.option(
    "--model", 
    required=True, 
    help="Model name or path (HuggingFace model ID or local path)"
)
@click.option(
    "--benchmarks",
    help="Comma-separated list of benchmarks to run (e.g., mmlu,hellaswag,gsm8k)"
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to configuration YAML file"
)
@click.option(
    "--output-dir",
    default="./results",
    help="Output directory for results"
)
@click.option(
    "--batch-size",
    type=int,
    default=8,
    help="Batch size for evaluation"
)
@click.option(
    "--num-samples",
    type=int,
    help="Number of samples to evaluate (for testing)"
)
@click.option(
    "--device",
    default="auto",
    help="Device to use (auto, cpu, cuda)"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging"
)
def evaluate(
    model: str,
    benchmarks: Optional[str],
    config: Optional[str],
    output_dir: str,
    batch_size: int,
    num_samples: Optional[int],
    device: str,
    verbose: bool
):
    """Run LLM evaluation on specified benchmarks."""
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(level=log_level)
    
    try:
        # Load configuration
        if config:
            with open(config, 'r') as f:
                eval_config = yaml.safe_load(f)
        else:
            # Use default configuration
            eval_config = {
                "benchmarks": [],
                "evaluation": {
                    "batch_size": batch_size,
                    "device": device
                },
                "reporting": {
                    "output_dir": output_dir
                }
            }
        
        # Override with CLI arguments
        if benchmarks:
            benchmark_list = benchmarks.split(',')
            eval_config["benchmarks"] = [
                {"name": name.strip(), "enabled": True} 
                for name in benchmark_list
            ]
        
        if num_samples:
            for benchmark in eval_config["benchmarks"]:
                benchmark["num_samples"] = num_samples
        
        # Initialize evaluation suite
        suite = EvaluationSuite(config=eval_config)
        
        # Load model
        click.echo(f"Loading model: {model}")
        model_wrapper = ModelWrapper.from_pretrained(model, device=device)
        
        # Run evaluation
        click.echo("Starting evaluation...")
        results = suite.evaluate(model_wrapper)
        
        # Generate reports
        click.echo(f"Generating reports in {output_dir}")
        suite.generate_report(results, output_dir=output_dir)
        
        click.echo("Evaluation completed successfully!")
        
    except Exception as e:
        click.echo(f"Error during evaluation: {str(e)}", err=True)
        raise click.ClickException(str(e))


@main.command()
@click.option(
    "--benchmark",
    required=True,
    help="Benchmark name to list datasets for"
)
def list_datasets(benchmark: str):
    """List available datasets for a benchmark."""
    try:
        from .benchmarks import get_benchmark_class
        
        benchmark_class = get_benchmark_class(benchmark)
        datasets = benchmark_class.list_available_datasets()
        
        click.echo(f"Available datasets for {benchmark}:")
        for dataset in datasets:
            click.echo(f"  - {dataset}")
            
    except Exception as e:
        click.echo(f"Error listing datasets: {str(e)}", err=True)


@main.command()
def list_benchmarks():
    """List all available benchmarks."""
    try:
        from .benchmarks import list_available_benchmarks
        
        benchmarks = list_available_benchmarks()
        
        click.echo("Available benchmarks:")
        for category, benchmark_list in benchmarks.items():
            click.echo(f"\n{category.title()}:")
            for benchmark in benchmark_list:
                click.echo(f"  - {benchmark}")
                
    except Exception as e:
        click.echo(f"Error listing benchmarks: {str(e)}", err=True)


@main.command()
@click.argument("config_name")
@click.option(
    "--output",
    default="./config.yaml",
    help="Output path for generated config"
)
def generate_config(config_name: str, output: str):
    """Generate a configuration file template."""
    
    templates = {
        "basic": {
            "benchmarks": [
                {"name": "mmlu", "enabled": True, "num_samples": 1000},
                {"name": "hellaswag", "enabled": True, "num_samples": 500},
                {"name": "gsm8k", "enabled": True, "num_samples": 100}
            ],
            "evaluation": {
                "batch_size": 8,
                "max_length": 2048,
                "temperature": 0.0
            },
            "reporting": {
                "formats": ["json", "html"],
                "include_examples": True
            }
        },
        "comprehensive": {
            "benchmarks": [
                {"name": "mmlu", "enabled": True},
                {"name": "hellaswag", "enabled": True},
                {"name": "winogrande", "enabled": True},
                {"name": "gsm8k", "enabled": True},
                {"name": "humaneval", "enabled": True},
                {"name": "truthfulqa", "enabled": True}
            ],
            "evaluation": {
                "batch_size": 4,
                "max_length": 4096,
                "temperature": 0.0,
                "num_workers": 4
            },
            "reporting": {
                "formats": ["json", "html", "csv"],
                "include_examples": True,
                "generate_plots": True
            }
        }
    }
    
    if config_name not in templates:
        click.echo(f"Unknown config template: {config_name}")
        click.echo(f"Available templates: {', '.join(templates.keys())}")
        return
    
    with open(output, 'w') as f:
        yaml.dump(templates[config_name], f, default_flow_style=False, indent=2)
    
    click.echo(f"Generated {config_name} configuration template: {output}")


if __name__ == "__main__":
    main()