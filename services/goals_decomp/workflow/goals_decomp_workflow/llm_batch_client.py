#!/usr/bin/env python3
"""
Standalone LLM Batch Client

Features:
- Single and batch LLM calls via LiteLLM
- Parallel processing with ThreadPoolExecutor
- Retry logic with exponential backoff
- Progress tracking with tqdm
"""

import os
import time
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv
import litellm
from tqdm import tqdm

# Load environment variables from multiple possible locations
# First try to load from llm-batch-client/.env, then from root .env
current_dir = Path(__file__).parent
env_path = current_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try loading from project root
    load_dotenv()
#litellm._turn_on_debug()
# Default configuration
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "anthropic/claude-opus-4-1-20250805")
DEFAULT_MAX_WORKERS = 32
DEFAULT_MAX_RETRIES = 3
DEFAULT_TEMPERATURE = 1 #required for thinking
DEFAULT_MAX_TOKENS = 16384


class LLMBatchClient:
    """Client for handling single and batch LLM requests with parallel processing."""
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_workers: int = DEFAULT_MAX_WORKERS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ):
        """
        Initialize the LLM batch client.
        
        Args:
            model: LLM model identifier (e.g., "openai/gpt-4", "anthropic/claude-3")
            max_workers: Maximum number of parallel workers for batch processing
            max_retries: Maximum retry attempts for failed requests
            temperature: Default temperature for LLM responses
            max_tokens: Default max tokens for LLM responses
        """
        self.model = model
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
    
    def single_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
        **kwargs
    ) -> str:
        """
        Make a single LLM completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            enable_thinking: Whether to enable thinking mode (default: True)
            **kwargs: Additional arguments for litellm.completion
            
        Returns:
            String content of the LLM response
        """
        if temperature is None:
            temperature = self.default_temperature
        if max_tokens is None:
            max_tokens = self.default_max_tokens
        
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Only add thinking parameter if enabled
        if enable_thinking:
            completion_kwargs["thinking"] = {"type": "enabled", "budget_tokens": 8192}
            
        response = litellm.completion(**completion_kwargs)
        #print(response)
        return response.choices[0].message.content.strip()
    
    def single_completion_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Make a single LLM completion with retry logic.
        
        Args:
            messages: List of message dicts
            temperature: Override default temperature
            max_tokens: Override default max tokens
            max_retries: Override default max retries
            **kwargs: Additional arguments for litellm.completion
            
        Returns:
            String content of the LLM response
            
        Raises:
            Exception: If all retry attempts fail
        """
        if max_retries is None:
            max_retries = self.max_retries
            
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.single_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = 0.5 * (2 ** attempt)
                    time.sleep(sleep_time)
                    continue
                    
        raise last_error or Exception("All retry attempts failed")
    
    def batch_completions(
        self,
        message_batches: List[List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
        **kwargs
    ) -> List[str]:
        """
        Process multiple LLM requests in parallel.
        
        Args:
            message_batches: List of message lists for each request
            temperature: Override default temperature
            max_tokens: Override default max tokens
            max_workers: Override default max workers
            show_progress: Whether to show progress bar
            **kwargs: Additional arguments for litellm.completion
            
        Returns:
            List of response strings in the same order as input
        """
        if not message_batches:
            return []
            
        if max_workers is None:
            max_workers = min(self.max_workers, len(message_batches))
            
        results = [None] * len(message_batches)  # Pre-allocate to maintain order
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(
                    self.single_completion_with_retry,
                    messages,
                    temperature,
                    max_tokens,
                    **kwargs
                ): i
                for i, messages in enumerate(message_batches)
            }
            
            # Collect results with optional progress bar
            iterator = as_completed(future_to_index)
            if show_progress:
                iterator = tqdm(iterator, total=len(message_batches), desc="Processing")
                
            for future in iterator:
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception as e:
                    print(f"Error processing request {index}: {e}")
                    results[index] = None  # Or handle error as needed
                    
        return results
    
    def batch_process_with_function(
        self,
        items: List[Any],
        process_fn: Callable[[Any], List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Process items through a function that generates messages, then batch LLM calls.
        
        Args:
            items: List of items to process
            process_fn: Function that converts item to messages list
            temperature: Override default temperature
            max_tokens: Override default max tokens
            max_workers: Override default max workers
            show_progress: Whether to show progress bar
            **kwargs: Additional arguments for litellm.completion
            
        Returns:
            List of dicts with 'item', 'messages', and 'response' keys
        """
        if not items:
            return []
            
        if max_workers is None:
            max_workers = min(self.max_workers, len(items))
            
        results = []
        
        def process_single_item(item: Any) -> Dict[str, Any]:
            """Process a single item through the pipeline."""
            try:
                messages = process_fn(item)
                response = self.single_completion_with_retry(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                return {
                    "item": item,
                    "messages": messages,
                    "response": response,
                    "success": True
                }
            except Exception as e:
                return {
                    "item": item,
                    "messages": None,
                    "response": None,
                    "error": str(e),
                    "success": False
                }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = [executor.submit(process_single_item, item) for item in items]
            
            # Collect results with optional progress bar
            iterator = as_completed(futures)
            if show_progress:
                iterator = tqdm(iterator, total=len(items), desc="Processing items")
                
            for future in iterator:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Error in batch processing: {e}")
                    
        # Sort results to maintain original order if needed
        # Note: This assumes items are hashable for sorting
        try:
            item_to_index = {item: i for i, item in enumerate(items)}
            results.sort(key=lambda x: item_to_index.get(x["item"], float('inf')))
        except:
            pass  # If items aren't hashable, keep results in completion order
            
        return results


# Convenience functions for simple use cases
def simple_llm_call(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Simple wrapper for a single LLM call with just a prompt.
    
    Args:
        prompt: The prompt string
        model: LLM model to use
        
    Returns:
        The LLM response string
    """
    client = LLMBatchClient(model=model)
    messages = [{"role": "user", "content": prompt}]
    return client.single_completion(messages)


def batch_llm_calls(
    prompts: List[str],
    model: str = DEFAULT_MODEL,
    max_workers: int = DEFAULT_MAX_WORKERS
) -> List[str]:
    """
    Simple wrapper for batch LLM calls with a list of prompts.
    
    Args:
        prompts: List of prompt strings
        model: LLM model to use
        max_workers: Number of parallel workers
        
    Returns:
        List of response strings
    """
    client = LLMBatchClient(model=model, max_workers=max_workers)
    message_batches = [[{"role": "user", "content": prompt}] for prompt in prompts]
    return client.batch_completions(message_batches)


if __name__ == "__main__":
    # Example usage
    print("Testing LLM Batch Client...")
    
    #Test single call
    print("\n1. Single LLM call:")
    response = simple_llm_call("What is 2+2?")
    print(f"Response: {response}")
    
    # Test batch calls
    # print("\n2. Batch LLM calls:")
    # test_prompts = [
    #     "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    #      "What is the capital of France?",
    #     "What is 10 * 5?",
    #     "Name a primary color.",
    # ]
    
    # responses = batch_llm_calls(test_prompts, max_workers=3)
    # for prompt, response in zip(test_prompts, responses):
    #     print(f"Q: {prompt}")
    #     print(f"A: {response}\n")
    
    # Test with custom processing function
    print("\n3. Custom processing function:")
    client = LLMBatchClient()
    
    def create_messages(topic: str) -> List[Dict[str, str]]:
        return [{"role": "user", "content": f"Write a one-sentence fact about {topic}"}]
    
    # topics = ["Python", "JavaScript", "Rust"]
    # results = client.batch_process_with_function(
    #     items=topics,
    #     process_fn=create_messages,
    #     max_workers=3
    # )
    
    # for result in results:
    #     if result["success"]:
    #         print(f"Topic: {result['item']}")
    #         print(f"Response: {result['response']}\n")

