#!/usr/bin/env python3
"""
Simple Class-Based Decomposition Workflow

A straightforward class where each method represents a workflow step.
"""

import sys
import yaml
import re
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add llm-batch-client to path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'llm-batch-client'))
from llm_batch_client import LLMBatchClient


class DecompositionWorkflow:
    """Simple workflow class with each method as a pipeline step."""
    
    def __init__(self, model: str = None):
        self.model = model or os.environ.get("MODEL_NAME", "anthropic/claude-opus-4-1-20250805")
        self.llm_client = None
        self.workflow_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Results storage
        self.user_problem = None
        self.initial_decomposition_result = None
        self.collected_context = None
        self.refined_decomposition_result = None
        self.analysis_result = None
        self.saved_files = {}
    
    def initialize_llm(self):
        """Initialize the LLM client."""
        try:
            self.llm_client = LLMBatchClient(model=self.model, temperature=1.0, max_tokens=16384)
            print(f"✅ LLM Client initialized with model: {self.model}")
        except Exception as e:
            print(f"❌ Failed to initialize LLM client: {e}")
            raise
    
    def initial_decomposition(self, user_problem: str) -> Dict[str, Any]:
        """Step 1: Perform initial decomposition of user problem."""
        print("\n" + "="*80)
        print("STEP 1: INITIAL DECOMPOSITION")
        print("="*80)
        print("Decomposing your problem into goals, capabilities, and tasks...")
        
        self.user_problem = user_problem
        
        # Load system prompt template
        prompt_data = self._load_yaml_file('prompts/system_prompt_2.yaml')
        if not prompt_data:
            raise Exception("Could not load prompt from prompts/system_prompt_2.yaml")
        
        system_prompt_template = prompt_data.get('system_prompt', '')
        full_prompt = system_prompt_template.replace("{{USER_PROBLEM}}", user_problem)
        messages = [{"role": "user", "content": full_prompt}]
        
        # Make LLM call
        response = self.llm_client.single_completion_with_retry(
            messages=messages, temperature=1.0, max_tokens=16384
        )
        
        # Extract YAML from response
        parsed_yaml = self._extract_yaml_from_response(response)
        if not parsed_yaml:
            raise Exception("Could not extract YAML from decomposition response")
        
        result = {
            'raw_response': response,
            'parsed_yaml': parsed_yaml,
            'timestamp': datetime.now().isoformat()
        }
        
        self.initial_decomposition_result = result
        
        print("✅ Initial decomposition complete")
        print(f"   • Goals: {len(parsed_yaml.get('goals', []))}")
        print(f"   • Capabilities: {len(parsed_yaml.get('required_capabilities', []))}")
        print(f"   • Tasks: {len(parsed_yaml.get('tasks', []))}")
        
        return result
    
    def context_collection(self) -> Dict[str, Dict[str, str]]:
        """Step 2: Collect user context through simple input prompts."""
        print("\n" + "="*80)
        print("STEP 2: CONTEXT COLLECTION")
        print("="*80)
        
        if not self.initial_decomposition_result:
            raise Exception("Must run initial_decomposition first")
        
        context_requirements = self._extract_context_requirements(
            self.initial_decomposition_result['parsed_yaml']
        )
        
        if not context_requirements:
            print("No additional context required.")
            self.collected_context = {}
            return {}
        
        print("\nThe system needs some additional information to refine the solution.")
        print("Please provide the requested context for each goal.")
        print("(Type 'skip' if you don't have the information)\n")
        
        collected_context = {}
        
        for req in context_requirements:
            goal_name = req['goal_name']
            contexts = req['contexts']
            
            print(f"\n{'='*60}")
            print(f"Goal: {goal_name}")
            print(f"{'='*60}")
            
            goal_context = {}
            for i, context_item in enumerate(contexts, 1):
                print(f"\n[{i}/{len(contexts)}] {context_item}")
                print("-"*60)
                print("(Enter multiple lines if needed, type 'END' on a new line when finished)")
                
                lines = []
                while True:
                    try:
                        line = input()
                    except EOFError:
                        line = 'skip'
                        
                    if line.strip().upper() == 'END':
                        break
                    if line.strip().lower() == 'skip':
                        lines = ['skip']
                        break
                    lines.append(line)
                
                user_input = '\n'.join(lines).strip()
                
                if user_input.lower() != 'skip' and user_input:
                    goal_context[context_item] = user_input
            
            if goal_context:
                collected_context[goal_name] = goal_context
        
        self.collected_context = collected_context
        return collected_context
    
    def contextual_refinement(self) -> Dict[str, Any]:
        """Step 3: Refine the decomposition with collected user context."""
        print("\n" + "="*80)
        print("STEP 3: CONTEXTUAL REFINEMENT")
        print("="*80)
        print("Refining decomposition with your provided context...")
        
        if not self.initial_decomposition_result or self.collected_context is None:
            raise Exception("Must run initial_decomposition and context_collection first")
        
        # Load refinement prompt
        prompt_data = self._load_yaml_file('prompts/system_prompt_refinement.yaml')
        if not prompt_data:
            raise Exception("Could not load refinement prompt")
        
        system_prompt_template = prompt_data.get('system_prompt', '')
        
        # Format user context for the prompt
        context_text = ""
        if self.collected_context:
            for goal_name, goal_context in self.collected_context.items():
                context_text += f"\nFor goal '{goal_name}':\n"
                for context_item, value in goal_context.items():
                    context_text += f"  - {context_item}: {value}\n"
        else:
            context_text = "No additional context was provided."
        
        # Format existing decomposition
        decomposition_text = yaml.dump(
            self.initial_decomposition_result['parsed_yaml'], 
            default_flow_style=False, sort_keys=False
        )
        
        # Replace placeholders
        full_prompt = system_prompt_template.replace("{{USER_PROBLEM}}", self.user_problem)
        full_prompt = full_prompt.replace("{{USER_CONTEXT}}", context_text)
        full_prompt = full_prompt.replace("{{EXISTING_DECOMPOSITION}}", decomposition_text)
        
        messages = [{"role": "user", "content": full_prompt}]
        
        # Make LLM call
        response = self.llm_client.single_completion_with_retry(
            messages=messages, temperature=1.0, max_tokens=16384
        )
        
        # Extract refined YAML
        refined_yaml = self._extract_yaml_from_response(response)
        if not refined_yaml:
            print("Warning: Could not extract refined YAML from response.")
            print("Using original decomposition.")
            refined_yaml = self.initial_decomposition_result['parsed_yaml']
        
        result = {
            'raw_response': response,
            'refined_yaml': refined_yaml,
            'timestamp': datetime.now().isoformat()
        }
        
        self.refined_decomposition_result = result
        print("✅ Decomposition refined with context")
        
        return result
    
    def capabilities_analysis(self) -> Dict[str, Any]:
        """Step 4: Analyze required capabilities against core capabilities."""
        print("\n" + "="*80)
        print("STEP 4: CAPABILITIES ANALYSIS")
        print("="*80)
        print("Analyzing required capabilities against core capabilities...")
        
        if not self.refined_decomposition_result:
            raise Exception("Must run contextual_refinement first")
        
        # Load core capabilities and analysis prompt
        core_capabilities = self._load_yaml_file('prompts/_core_capabilities.yaml')
        prompt_data = self._load_yaml_file('prompts/prompt_analyze_capabilities.yaml')
        
        if not core_capabilities or not prompt_data:
            raise Exception("Could not load core capabilities or analysis prompt")
        
        system_prompt_template = prompt_data.get('system_prompt', '')
        decomposition = self.refined_decomposition_result['refined_yaml']
        
        # Extract required capabilities
        required_capabilities = self._extract_required_capabilities(decomposition)
        if not required_capabilities:
            print("Warning: No required capabilities found in decomposition.")
            return {'analysis_timestamp': datetime.now().isoformat(), 'error': 'No capabilities found'}
        
        print(f"Found {len(required_capabilities)} required capabilities to analyze")
        
        # Format data for prompt
        decomposition_yaml = yaml.dump(decomposition, default_flow_style=False, sort_keys=False)
        core_capabilities_yaml = yaml.dump(core_capabilities, default_flow_style=False, sort_keys=False)
        required_capabilities_text = self._format_capabilities_for_prompt(required_capabilities)
        
        # Replace placeholders
        prompt = system_prompt_template.replace("{{USER_PROBLEM}}", self.user_problem)
        prompt = prompt.replace("{{EXISTING_DECOMPOSITION}}", decomposition_yaml)
        prompt = prompt.replace("{{CORE_CAPABILITIES}}", core_capabilities_yaml)
        prompt = prompt.replace("{{REQUIRED_CAPABILITIES}}", required_capabilities_text)
        
        messages = [{"role": "user", "content": prompt}]
        
        # Make LLM call
        print("Making LLM call for capabilities analysis...")
        response = self.llm_client.single_completion_with_retry(
            messages=messages, temperature=1.0, max_tokens=16384
        )
        
        # Extract YAML from both XML sections
        analysis_yaml = self._extract_yaml_from_xml_section(response, 'analysis')
        updated_decomposition_yaml = self._extract_yaml_from_xml_section(response, 'updated_decomposition')
        
        # Validate results
        if analysis_yaml:
            print("✅ Successfully parsed analysis")
            if 'analyses' in analysis_yaml:
                print(f"   Found {len(analysis_yaml['analyses'])} capability analyses")
        else:
            print("⚠️ Could not parse analysis section")
        
        if updated_decomposition_yaml:
            print("✅ Successfully parsed updated decomposition")
            if 'goals' in updated_decomposition_yaml:
                print(f"   Found {len(updated_decomposition_yaml['goals'])} goals")
            if 'capabilities' in updated_decomposition_yaml:
                print(f"   Found {len(updated_decomposition_yaml['capabilities'])} capabilities")
            if 'tasks' in updated_decomposition_yaml:
                print(f"   Found {len(updated_decomposition_yaml['tasks'])} tasks")
        else:
            print("⚠️ Could not parse updated decomposition section")
        
        result = {
            'analysis_timestamp': datetime.now().isoformat(),
            'user_problem': self.user_problem,
            'required_capabilities_count': len(required_capabilities),
            'raw_response': response,
            'parsed_analysis': analysis_yaml,
            'updated_decomposition': updated_decomposition_yaml
        }
        
        self.analysis_result = result
        print("✅ Capabilities analysis complete")
        
        return result
    
    def save_results(self) -> Dict[str, str]:
        """Step 5: Save all workflow results to appropriate directories."""
        print("\n" + "="*80)
        print("SAVING RESULTS")
        print("="*80)
        
        saved_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directories
        base_dir = 'goals_decomp_results'
        output_dirs = [
            f'{base_dir}/initial_decomp',
            f'{base_dir}/contextual_refinement',
            f'{base_dir}/capabilities_analysis',
            f'{base_dir}/sessions'
        ]
        for dir_path in output_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # Save initial decomposition
        if self.initial_decomposition_result:
            initial_data = {
                'workflow_id': self.workflow_id,
                'timestamp': self.initial_decomposition_result['timestamp'],
                'user_problem': self.user_problem,
                'decomposition': self.initial_decomposition_result['parsed_yaml']
            }
            initial_file = f'{base_dir}/initial_decomp/decomposition_{self.workflow_id}_{timestamp}.yaml'
            latest_initial = f'{base_dir}/initial_decomp/latest.yaml'
            if self._save_yaml_file(initial_file, initial_data):
                saved_files['initial_decomposition'] = initial_file
                self._save_yaml_file(latest_initial, initial_data)
        
        # Save refined decomposition
        if self.refined_decomposition_result:
            refined_data = {
                'workflow_id': self.workflow_id,
                'timestamp': self.refined_decomposition_result['timestamp'],
                'user_problem': self.user_problem,
                'decomposition': self.refined_decomposition_result['refined_yaml']
            }
            refined_file = f'{base_dir}/contextual_refinement/decomposition_{self.workflow_id}_{timestamp}.yaml'
            latest_refined = f'{base_dir}/contextual_refinement/latest.yaml'
            if self._save_yaml_file(refined_file, refined_data):
                saved_files['refined_decomposition'] = refined_file
                self._save_yaml_file(latest_refined, refined_data)
        
        # Save capabilities analysis
        if self.analysis_result and self.analysis_result.get('parsed_analysis'):
            analysis_data = {
                'workflow_id': self.workflow_id,
                'timestamp': self.analysis_result['analysis_timestamp'],
                'user_problem': self.user_problem,
                'parsed_analysis': self.analysis_result['parsed_analysis']
            }
            analysis_file = f'{base_dir}/capabilities_analysis/analysis_{self.workflow_id}_{timestamp}.yaml'
            latest_analysis = f'{base_dir}/capabilities_analysis/latest_analysis.yaml'
            if self._save_yaml_file(analysis_file, analysis_data):
                saved_files['analysis'] = analysis_file
                self._save_yaml_file(latest_analysis, analysis_data)
        
        # Save final decomposition
        if self.analysis_result and self.analysis_result.get('updated_decomposition'):
            final_data = {
                'workflow_id': self.workflow_id,
                'timestamp': self.analysis_result['analysis_timestamp'],
                'user_problem': self.user_problem,
                'source': 'Capabilities analysis with core capability mapping',
                'decomposition': self.analysis_result['updated_decomposition']
            }
            final_file = f'{base_dir}/capabilities_analysis/final_decomposition_{self.workflow_id}_{timestamp}.yaml'
            latest_final = f'{base_dir}/capabilities_analysis/latest_final.yaml'
            if self._save_yaml_file(final_file, final_data):
                saved_files['final_decomposition'] = final_file
                self._save_yaml_file(latest_final, final_data)
        
        # Save session log
        session_data = {
            'workflow_id': self.workflow_id,
            'timestamp': datetime.now().isoformat(),
            'user_problem': self.user_problem,
            'saved_files': saved_files
        }
        session_file = f'{base_dir}/sessions/session_{self.workflow_id}_{timestamp}.yaml'
        if self._save_yaml_file(session_file, session_data):
            saved_files['session'] = session_file
        
        self.saved_files = saved_files
        print(f"✅ All results saved ({len(saved_files)} files)")
        
        return saved_files
    
    def run_full_workflow(self, user_problem: str) -> Dict[str, Any]:
        """Run the complete workflow pipeline."""
        print("\n" + "="*80)
        print("🚀 DECOMPOSITION WORKFLOW PIPELINE")
        print("="*80)
        print(f"\n🔑 Workflow ID: {self.workflow_id}")
        print(f"📝 Processing: {user_problem[:100]}..." if len(user_problem) > 100 else f"📝 Processing: {user_problem}")
        
        self.initialize_llm()
        
        # Run all steps
        self.initial_decomposition(user_problem)
        self.context_collection()
        self.contextual_refinement()
        self.capabilities_analysis()
        self.save_results()
        
        # Print summary
        self._print_summary()
        
        return {
            'workflow_id': self.workflow_id,
            'user_problem': user_problem,
            'saved_files': self.saved_files,
            'final_decomposition': self.analysis_result.get('updated_decomposition') if self.analysis_result else None
        }
    
    # Utility methods (kept from original script)
    
    def _load_yaml_file(self, filepath: str) -> Any:
        """Load a YAML file and return its contents."""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Error: File {filepath} not found.")
            return None
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {filepath}: {e}")
            return None
    
    def _save_yaml_file(self, filepath: str, data: Any) -> bool:
        """Save data to a YAML file."""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, default_flow_style=False, allow_unicode=True, 
                         sort_keys=False, width=120)
            return True
        except Exception as e:
            print(f"Error saving YAML file {filepath}: {e}")
            return False
    
    def _extract_yaml_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract YAML content from LLM response text."""
        if not response or not isinstance(response, str):
            return None
        
        # Pattern 1: Look for ```yaml ... ``` blocks
        yaml_pattern = r'```ya?ml\s*\n(.*?)```'
        yaml_matches = re.findall(yaml_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if yaml_matches:
            try:
                yaml_content = max(yaml_matches, key=len).strip()
                parsed_yaml = yaml.safe_load(yaml_content)
                if parsed_yaml and isinstance(parsed_yaml, dict):
                    return parsed_yaml
            except yaml.YAMLError as e:
                print(f"Warning: Failed to parse YAML block: {e}")
        
        # Pattern 2: Look for standalone YAML
        lines = response.split('\n')
        yaml_candidates = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
                
            yaml_indicators = ['goals:', 'tasks:', 'required_capabilities:', 'capabilities:']
            if any(stripped.startswith(indicator) for indicator in yaml_indicators):
                yaml_candidates.append(i)
        
        for yaml_start in yaml_candidates:
            yaml_end = len(lines)
            
            for i in range(yaml_start + 1, len(lines)):
                line = lines[i]
                stripped = line.strip()
                
                if (stripped.startswith('```') or 
                    stripped.startswith('##') or
                    re.match(r'^[A-Z][a-z].*[.!?]$', stripped)):
                    yaml_end = i
                    break
            
            try:
                yaml_content = '\n'.join(lines[yaml_start:yaml_end]).strip()
                if yaml_content:
                    parsed_yaml = yaml.safe_load(yaml_content)
                    if parsed_yaml and isinstance(parsed_yaml, dict):
                        return parsed_yaml
            except yaml.YAMLError:
                continue
        
        return None
    
    def _extract_yaml_from_xml_section(self, response: str, section_name: str) -> Optional[Dict[str, Any]]:
        """Extract and parse YAML content from a specific XML section."""
        if not response or not isinstance(response, str):
            return None
        
        xml_pattern = f'<{section_name}>(.*?)</{section_name}>'
        xml_match = re.search(xml_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if not xml_match:
            print(f"Warning: Could not find <{section_name}> section in response")
            return None
        
        section_content = xml_match.group(1).strip()
        return self._extract_yaml_from_response(section_content)
    
    def _extract_context_requirements(self, parsed_yaml: Dict) -> List[Dict[str, Any]]:
        """Extract user_context_required from parsed YAML."""
        context_requirements = []
        
        if not parsed_yaml or 'goals' not in parsed_yaml:
            return context_requirements
        
        for goal in parsed_yaml.get('goals', []):
            goal_name = goal.get('name', 'Unknown Goal')
            user_context = goal.get('user_context_required', [])
            
            if user_context and user_context not in ['None', 'Null', None]:
                if isinstance(user_context, str):
                    user_context = [user_context]
                elif not isinstance(user_context, list):
                    user_context = []
                
                if user_context:
                    context_requirements.append({
                        'goal_name': goal_name,
                        'contexts': user_context
                    })
        
        return context_requirements
    
    def _extract_required_capabilities(self, decomposition: Dict) -> List[Dict]:
        """Extract required capabilities from the decomposition."""
        if not decomposition or 'required_capabilities' not in decomposition:
            return []
        return decomposition.get('required_capabilities', [])
    
    def _format_capabilities_for_prompt(self, capabilities: List[Dict]) -> str:
        """Format capabilities list into a readable string for the prompt."""
        if not capabilities:
            return "No required capabilities found."
        
        formatted = ""
        for i, cap in enumerate(capabilities, 1):
            formatted += f"\n{i}. Capability: {cap.get('name', 'Unknown')}\n"
            formatted += f"   Description: {cap.get('description', 'N/A')}\n"
            
            if 'constraints' in cap:
                formatted += f"   Constraints: {cap['constraints']}\n"
            
            if 'interface' in cap:
                interface = cap['interface']
                formatted += f"   Interface:\n"
                formatted += f"     - Inputs: {interface.get('inputs', 'N/A')}\n"
                formatted += f"     - Outputs: {interface.get('outputs', 'N/A')}\n"
            
            if 'tasks' in cap:
                formatted += f"   Tasks: {', '.join(cap['tasks'])}\n"
            
            formatted += "\n"
        
        return formatted
    
    def _print_summary(self):
        """Print workflow summary."""
        print("\n" + "="*80)
        print("WORKFLOW SUMMARY")
        print("="*80)
        
        print(f"\n📝 User Problem:")
        display_problem = self.user_problem[:100] + "..." if len(self.user_problem) > 100 else self.user_problem
        print(f"   {display_problem}")
        
        if self.analysis_result and self.analysis_result.get('updated_decomposition'):
            decomp = self.analysis_result['updated_decomposition']
            print(f"\n📊 Final Decomposition:")
            print(f"   • Goals: {len(decomp.get('goals', []))}")
            print(f"   • Capabilities: {len(decomp.get('capabilities', []))}")
            print(f"   • Tasks: {len(decomp.get('tasks', []))}")
        
        print(f"\n📁 Output Files:")
        for key, filepath in self.saved_files.items():
            print(f"   • {key}: {filepath}")
        
        print(f"\n💡 Next Steps:")
        if 'final_decomposition' in self.saved_files:
            print(f"   1. Review the final decomposition: {self.saved_files['final_decomposition']}")
            print(f"   2. Use the decomposition to implement your solution")
        
        print("\n" + "="*80)
        print("✅ WORKFLOW COMPLETE")
        print("="*80)


def main():
    """Main function to run the workflow."""
    parser = argparse.ArgumentParser(description='Simple class-based decomposition workflow')
    parser.add_argument('--query', '-q', type=str, help='User query to process')
    parser.add_argument('--model', type=str, help='LLM model to use')
    
    args = parser.parse_args()
    
    # Get user query
    if args.query:
        user_problem = args.query
    else:
        print("Please enter your problem/query:")
        print("(Enter multiple lines if needed, type 'END' on a new line when finished)")
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
            except EOFError:
                break
        user_problem = '\n'.join(lines).strip()
        
        if not user_problem:
            print("Error: No query provided")
            sys.exit(1)
    
    # Create workflow and run
    try:
        workflow = DecompositionWorkflow(model=args.model)
        
        # Option 1: Run full workflow at once
        result = workflow.run_full_workflow(user_problem)
        
        # Option 2: Run steps individually (commented out)
        # workflow.initialize_llm()
        # workflow.initial_decomposition(user_problem)
        # workflow.context_collection()
        # workflow.contextual_refinement()
        # workflow.capabilities_analysis()
        # workflow.save_results()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Workflow interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()