#!/usr/bin/env python3
"""
Example demonstrating the enhanced error recovery functionality in call_llm_for_reflection_v3.

This example shows how to use the improved reflection function with error handling strategies.
It demonstrates normal operation, rate limiting, connection errors, and other error scenarios.
"""

import os
import sys
import time
import json
import random
from typing import Dict, Any

# Add the src directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.langgraph_nodes import call_llm_for_reflection_v3
from src.state_types import KFMAgentState
from src.exceptions import (
    LLMConnectionError, LLMRateLimitError, LLMServerError, 
    LLMTimeoutError, LLMServiceUnavailableError, LLMAuthenticationError
)

def create_sample_state() -> KFMAgentState:
    """Create a sample state for demonstration purposes."""
    return {
        "session_id": f"demo-{int(time.time())}",
        "user_id": "demo-user",
        "current_context": {
            "action_type": "process_document",
            "component": "document_processor",
            "active_component": "text_extraction",
            "previous_actions": [
                {"type": "load_document", "status": "success", "timestamp": time.time() - 60},
                {"type": "extract_metadata", "status": "success", "timestamp": time.time() - 30}
            ],
            "error_history": []
        },
        "current_action": {
            "type": "extract_text",
            "parameters": {
                "document_id": "doc-12345",
                "format": "markdown",
                "include_images": True
            },
            "status": "in_progress"
        },
        "system_metrics": {
            "response_time_ms": 235,
            "memory_usage_mb": 128,
            "cpu_usage_percent": 45
        }
    }

def simulate_error(error_type: str = None) -> Exception:
    """Create a simulated error of the specified type."""
    if error_type == "rate_limit":
        return LLMRateLimitError(
            message="API rate limit exceeded. Try again in 5 seconds.",
            retry_after=5.0,
            status_code=429
        )
    elif error_type == "connection":
        return LLMConnectionError(
            message="Connection to API endpoint failed",
            original_error=ConnectionError("Connection refused")
        )
    elif error_type == "timeout":
        return LLMTimeoutError(
            message="Request timed out after 30 seconds",
            timeout=30.0
        )
    elif error_type == "server":
        return LLMServerError(
            message="Internal server error",
            status_code=500
        )
    elif error_type == "service_unavailable":
        return LLMServiceUnavailableError(
            message="Service is currently unavailable",
            status_code=503,
            retry_after=60.0
        )
    elif error_type == "authentication":
        return LLMAuthenticationError(
            message="Invalid API key",
            status_code=401
        )
    else:
        return Exception("Unknown error")

def run_example(api_key: str = None, error_scenario: str = None):
    """
    Run an example demonstration of the error recovery capabilities.
    
    Args:
        api_key: Optional API key to use (if not provided, will use GOOGLE_API_KEY env var)
        error_scenario: Optional error scenario to simulate (None for normal operation)
    """
    # Save any existing API key
    original_api_key = os.environ.get("GOOGLE_API_KEY")
    
    # Set up API key for the example
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    elif not os.environ.get("GOOGLE_API_KEY") and error_scenario != "authentication":
        print("⚠️ No API key provided or found in environment. Running in authentication error scenario.")
        error_scenario = "authentication"
    
    # Create a sample state
    state = create_sample_state()
    
    try:
        # Modify behavior based on error scenario
        if error_scenario:
            print(f"Running with simulated '{error_scenario}' error scenario...")
            
            # Use monkeypatching to simulate various error scenarios
            if error_scenario == "rate_limit":
                # Replace TokenBucketRateLimiter.acquire with a version that always returns False
                import src.error_recovery
                original_acquire = src.error_recovery.TokenBucketRateLimiter.acquire
                src.error_recovery.TokenBucketRateLimiter.acquire = lambda self: False
                
            elif error_scenario == "service_unavailable":
                # Replace ServiceHealthMonitor.is_service_available with a version that returns False
                import src.error_recovery
                original_is_available = src.error_recovery.ServiceHealthMonitor.is_service_available
                src.error_recovery.ServiceHealthMonitor.is_service_available = lambda self: False
                
            elif error_scenario in ["connection", "timeout", "server", "authentication"]:
                # For these errors, we'll patch genai.GenerativeModel.generate_content
                import google.generativeai as genai
                original_generate = genai.GenerativeModel.generate_content
                
                def mock_generate_content(self, *args, **kwargs):
                    raise simulate_error(error_scenario)
                    
                genai.GenerativeModel.generate_content = mock_generate_content
        
        # Call the enhanced reflection function
        print("\n🔄 Calling LLM for reflection with advanced error recovery...\n")
        start_time = time.time()
        
        result = call_llm_for_reflection_v3(state)
        
        duration = time.time() - start_time
        print(f"\n✅ Call completed in {duration:.2f} seconds")
        print("\n📝 Reflection result:")
        print("-" * 80)
        print(result)
        print("-" * 80)
        
        # Check if the result contains error information
        if "error" in result.lower():
            print("\n⚠️ Error encountered during reflection")
            
            # Extract error type if present
            if "error_type" in result.lower():
                error_type = result.split("error_type:")[1].split("\n")[0].strip() if "error_type:" in result else "Unknown"
                print(f"Error type: {error_type}")
            
            # Highlight recovery strategy used
            if "recovery" in result.lower():
                recovery_info = result.split("recovery")[1].split("\n")[0].strip()
                print(f"Recovery strategy: {recovery_info}")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
    
    finally:
        # Restore any modifications we made
        if error_scenario == "rate_limit":
            src.error_recovery.TokenBucketRateLimiter.acquire = original_acquire
        elif error_scenario == "service_unavailable":
            src.error_recovery.ServiceHealthMonitor.is_service_available = original_is_available
        elif error_scenario in ["connection", "timeout", "server", "authentication"]:
            genai.GenerativeModel.generate_content = original_generate
        
        # Restore the original API key
        if original_api_key:
            os.environ["GOOGLE_API_KEY"] = original_api_key
        elif "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Demonstrate LLM error recovery strategies")
    parser.add_argument("--api-key", help="Google API key (or use GOOGLE_API_KEY env var)")
    parser.add_argument("--error", choices=[
        "rate_limit", "connection", "timeout", "server", 
        "service_unavailable", "authentication", "none"
    ], default="none", help="Error scenario to simulate")
    
    args = parser.parse_args()
    
    # Convert "none" to None for error scenario
    error_scenario = None if args.error == "none" else args.error
    
    # Run the example
    run_example(api_key=args.api_key, error_scenario=error_scenario) 