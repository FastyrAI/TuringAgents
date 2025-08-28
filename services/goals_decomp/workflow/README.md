# Goals Decomposition and DAG Creation (Minimum Implementation)

## Quick Start

### Run Query Router

```bash
python queryRouter.py --query "<your-query-here>"
```

Returns either a direct LLM response or executes the goals decomposition workflow based on query complexity.

### Configuration

Create `.env` file under `goals_decomp_workflow/`:

```env
MODEL_NAME=anthropic/claude-opus-4-1-20250805
ANTHROPIC_API_KEY=<your-api-key>
```

### Installation

```bash
pip install -r requirements.txt
```

## Project Structure

- `/prompts/` - All prompt templates
- `/goals_decomp_results/` - Workflow outputs
  - `capabilities_analysis/latest_final.yaml` - Final decomposition

## Visualization

```bash
python dag_builder/create_interactive_dags.py
```

Creates interactive DAG visualization using NetworkX.