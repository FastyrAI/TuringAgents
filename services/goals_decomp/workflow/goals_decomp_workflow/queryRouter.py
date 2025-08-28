#!/usr/bin/env python3
"""
Query Router

A top-level class that routes queries to either simple LLM API calls
or complex workflow decomposition based on query complexity.
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

from goals_decomp import DecompositionWorkflow


class QueryRouter:
    """
    Top-level query router that determines whether to route queries to
    simple LLM API calls or complex workflow decomposition.
    """
    
    def __init__(self):
        self.model = os.environ.get("MODEL_NAME", "anthropic/claude-opus-4-1-20250805")
        self.llm_client = None
        self.workflow = None
    
    def initialize_llm(self):
        """Initialize the LLM client."""
        try:
            self.llm_client = LLMBatchClient(model=self.model, temperature=0.3, max_tokens=1024)
            print(f"✅ Query Router LLM Client initialized with model: {self.model}")
        except Exception as e:
            print(f"❌ Failed to initialize LLM client for router: {e}")
            raise
    
    def route_query(self, user_query: str) -> str:
        """
        Determine routing path for the user query.
        
        Returns:
            'simple_llm_api_call' or 'workflow_decomposition'
        """
        print("\n" + "="*80)
        print("🔍 QUERY ROUTING ANALYSIS")
        print("="*80)
        print(f"Analyzing query complexity: {user_query[:100]}..." if len(user_query) > 100 else f"Analyzing query: {user_query}")
        
        # Load router prompt
        prompt_data = self._load_yaml_file('prompts/prompt_query_router.yaml')
        if not prompt_data:
            print("⚠️ Could not load router prompt. Defaulting to simple API call.")
            return 'simple_llm_api_call'
        
        system_prompt_template = prompt_data.get('system_prompt', '')
        full_prompt = system_prompt_template.replace("{{USER_QUERY}}", user_query)
        messages = [{"role": "user", "content": full_prompt}]
        
        try:
            # Make LLM call for routing decision
            response = self.llm_client.single_completion(
                messages=messages, temperature=0.3, max_tokens=1024, enable_thinking=False
            )
            
            # Extract routing decision
            routing_decision = self._extract_routing_decision(response)
            #justification = self._extract_justification(response)
            
            print(f"\n📊 Routing Decision: {routing_decision}")
            #print(f"📋 Justification: {justification}")
            
            return routing_decision
            
        except Exception as e:
            print(f"⚠️ Error during routing analysis: {e}")
            print("Defaulting to simple API call.")
            return 'simple_llm_api_call'
    
    def simple_llm_api_call(self, user_query: str) -> str:
        """
        Handle simple queries with direct LLM API call.
        
        Args:
            user_query: The user's query
            
        Returns:
            LLM response string
        """
        print("\n" + "="*80)
        print("💬 SIMPLE LLM API CALL")
        print("="*80)
        print("Processing query with direct LLM call...")
        
        try:
            if not self.llm_client:
                self.initialize_llm()
            
            messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
            messages.append({"role": "user", "content": user_query})
            
            response = self.llm_client.single_completion(
                messages=messages, temperature=0.7, max_tokens=4096, enable_thinking=False
            )
            
            print("✅ Simple query processed successfully")
            return response
            
        except Exception as e:
            error_msg = f"❌ Error processing simple query: {e}"
            print(error_msg)
            return error_msg
    
    def workflow_decomposition(self, user_query: str) -> Dict[str, Any]:
        """
        Handle complex queries with full workflow decomposition.
        
        Args:
            user_query: The user's query
            
        Returns:
            Workflow result dictionary
        """
        print("\n" + "="*80)
        print("🔄 WORKFLOW DECOMPOSITION")
        print("="*80)
        print("Processing complex query with full workflow...")
        
        try:
            # Initialize workflow if needed
            if not self.workflow:
                self.workflow = DecompositionWorkflow()
            
            # Run full workflow
            result = self.workflow.run_full_workflow(user_query)
            
            print("✅ Complex query processed through workflow")
            return result
            
        except Exception as e:
            error_msg = f"❌ Error processing complex query: {e}"
            print(error_msg)
            return {'error': error_msg, 'user_query': user_query}
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Main method to process any user query through appropriate routing.
        
        Args:
            user_query: The user's query
            
        Returns:
            Dictionary containing processing results and metadata
        """
        print("\n" + "="*80)
        print("🚀 QUERY ROUTER - INTELLIGENT PROCESSING")
        print("="*80)
        
        # Initialize LLM client
        if not self.llm_client:
            self.initialize_llm()
        
        start_time = datetime.now()
        
        # Step 1: Route the query
        routing_decision = self.route_query(user_query)
        
        # Step 2: Process based on routing decision
        if routing_decision == 'simple_llm_api_call':
            response = self.simple_llm_api_call(user_query)
            result = {
                'routing_decision': routing_decision,
                'response_type': 'simple',
                'response': response,
                'user_query': user_query,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
        else:  # workflow_decomposition
            workflow_result = self.workflow_decomposition(user_query)
            result = {
                'routing_decision': routing_decision,
                'response_type': 'workflow',
                'workflow_result': workflow_result,
                'user_query': user_query,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
        
        # Print final summary
        self._print_final_summary(result)
        
        return result
    
    # Utility methods
    
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
    
    def _extract_routing_decision(self, response: str) -> str:
        """Extract routing decision from LLM response."""
        if not response:
            return 'simple_llm_api_call'
        
        # Look for routing decision in XML tags
        decision_pattern = r'<routing_decision>\s*(.*?)\s*</routing_decision>'
        decision_match = re.search(decision_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if decision_match:
            decision = decision_match.group(1).strip()
            if decision in ['simple_llm_api_call', 'workflow_decomposition']:
                return decision
        
        # Fallback: look for keywords in response
        if 'workflow_decomposition' in response.lower():
            return 'workflow_decomposition'
        
        # Default to simple call
        return 'simple_llm_api_call'
    
    def _extract_justification(self, response: str) -> str:
        """Extract justification from LLM response."""
        if not response:
            return "No justification provided."
        
        # Look for justification in XML tags
        justification_pattern = r'<justification>\s*(.*?)\s*</justification>'
        justification_match = re.search(justification_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if justification_match:
            return justification_match.group(1).strip()
        
        return "Justification not found in response."
    
    def _print_final_summary(self, result: Dict[str, Any]):
        """Print final processing summary."""
        print("\n" + "="*80)
        print("📋 FINAL PROCESSING SUMMARY")
        print("="*80)
        
        print(f"\n📝 Query: {result['user_query'][:100]}..." if len(result['user_query']) > 100 else f"\n📝 Query: {result['user_query']}")
        print(f"🔀 Routing Decision: {result['routing_decision']}")
        print(f"⚡ Processing Time: {result['processing_time']:.2f} seconds")
        
        if result['response_type'] == 'simple':
            print(f"💬 Response Type: Simple LLM Call")
            print(f"📄 Response Length: {len(result['response'])} characters")
        else:
            print(f"🔄 Response Type: Workflow Decomposition")
            workflow_result = result.get('workflow_result', {})
            if 'saved_files' in workflow_result:
                print(f"📁 Files Generated: {len(workflow_result['saved_files'])}")
            if 'workflow_id' in workflow_result:
                print(f"🔑 Workflow ID: {workflow_result['workflow_id']}")
        
        print("\n" + "="*80)
        print("✅ QUERY PROCESSING COMPLETE")
        print("="*80)


def main():
    """Main function to run the query router."""
    parser = argparse.ArgumentParser(
        description='Intelligent Query Router with Decomposition Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python query_router.py
  python query_router.py --query "What is the capital of France?"
  python query_router.py --query "Help me build a customer analytics system"
        """
    )
    
    parser.add_argument('--query', '-q', type=str, help='User query to process')
    
    args = parser.parse_args()
    
    # Get user query
    if args.query:
        user_query = args.query
    else:
        print("\n" + "="*80)
        print("🤖 INTELLIGENT QUERY ROUTER")
        print("="*80)
        print("\nThis system automatically routes your query to the appropriate processing method:")
        print("• Simple queries → Direct LLM API call")
        print("• Complex queries → Full decomposition workflow")
        print("\nPlease enter your query:")
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
        user_query = '\n'.join(lines).strip()
        
        if not user_query:
            print("Error: No query provided")
            sys.exit(1)
    
    # Create router and process query
    try:
        router = QueryRouter()
        result = router.process_query(user_query)
        
        # Display results based on type
        if result['response_type'] == 'simple':
            print("\n" + "="*80)
            print("📝 SIMPLE RESPONSE")
            print("="*80)
            print(result['response'])
        else:
            print("\n" + "="*80)
            print("🎯 WORKFLOW RESULTS")
            print("="*80)
            workflow_result = result.get('workflow_result', {})
            
            if 'error' in workflow_result:
                print(f"❌ Workflow Error: {workflow_result['error']}")
            else:
                print("✅ Workflow completed successfully!")
                if 'saved_files' in workflow_result:
                    print(f"📁 Generated {len(workflow_result['saved_files'])} output files")
                    print("📂 Check 'goals_decomp_results/' directory for detailed results")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Processing interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()