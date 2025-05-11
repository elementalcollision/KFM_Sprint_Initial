#!/usr/bin/env python
"""
Demonstration of the Error Suggestions Engine.

This script shows how to use the error suggestions engine to get intelligent
suggestions for resolving errors in LangGraph applications.
"""

import os
import sys
import json
import traceback
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.suggestions import (
    get_suggestions,
    submit_feedback,
    get_documentation_for_error
)

from src.error_context import (
    EnhancedError,
    capture_error_context
)

from src.recovery import (
    RecoveryMode,
    RecoveryPolicy,
    RecoveryManager,
    with_recovery
)

from src.logger import setup_logger

# Set up logging
logger = setup_logger("error_suggestions_demo")

class DemoApp:
    """Demo application to demonstrate error suggestions."""
    
    def __init__(self):
        """Initialize the demo application."""
        # Define node names
        self.nodes = [
            "process_config", 
            "validate_input", 
            "call_api",
            "process_result"
        ]
        
        # Create graph structure
        self.graph = type('Graph', (), {
            'nodes': self.nodes,
            'get_node': self.get_node
        })()
    
    def get_node(self, node_name):
        """Mock getting a node from the graph."""
        node_functions = {
            "process_config": self.process_config,
            "validate_input": self.validate_input,
            "call_api": self.call_api,
            "process_result": self.process_result
        }
        
        if node_name in node_functions:
            return {"fn": node_functions[node_name]}
        
        # Default function that passes state through
        return {"fn": lambda state: state}
    
    def process_config(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process configuration (first node)."""
        logger.info("Processing configuration...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Simulate configuration loading
        if state.get("trigger_config_error"):
            # Trigger a KeyError with missing configuration
            config = {}
            # This will raise a KeyError
            api_key = config["api_key"]
        
        # Set default configuration
        state["config"] = {
            "api_url": "https://example.com/api",
            "timeout": 30,
            "retries": 3
        }
        
        return state
    
    def validate_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data (second node)."""
        logger.info("Validating input...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Trigger a validation error if requested
        if state.get("trigger_validation_error"):
            # Trigger a TypeError with wrong input type
            user_id = state.get("user_id", "not_a_number")
            if not isinstance(user_id, int):
                raise TypeError(f"User ID must be an integer, got {type(user_id).__name__}")
        
        # Add validation results to state
        state["validation_results"] = {
            "valid": True
        }
        
        return state
    
    def call_api(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Call external API (third node)."""
        logger.info("Calling API...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Trigger an API error if requested
        if state.get("trigger_api_error"):
            # Trigger a ConnectionError or TimeoutError
            if state.get("connection_error"):
                raise ConnectionError("Failed to connect to API")
            else:
                raise TimeoutError("API request timed out")
        
        # Simulate API response
        state["api_response"] = {
            "status": "success",
            "data": {
                "result": "API response"
            }
        }
        
        return state
    
    def process_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process API response (fourth node)."""
        logger.info("Processing result...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Trigger a processing error if requested
        if state.get("trigger_processing_error"):
            # Trigger a KeyError with missing field in API response
            api_response = state.get("api_response", {})
            # This will raise an AttributeError
            result = api_response["data"]["missing_field"]["value"]
        
        # Add processing results to state
        state["processing_results"] = {
            "processed": True,
            "timestamp": "2023-01-01T12:00:00Z"
        }
        
        return state

def demonstrate_error_suggestions():
    """Demonstrate error suggestions for different error types."""
    logger.info("\n=== DEMONSTRATING ERROR SUGGESTIONS ===\n")
    
    # Create results directory
    os.makedirs("logs", exist_ok=True)
    
    # Create app
    app = DemoApp()
    
    # List of scenarios to demonstrate
    scenarios = [
        {
            "name": "Configuration Error",
            "state": {"trigger_config_error": True},
            "expected_error": KeyError,
            "recovery_policy": RecoveryPolicy(mode=RecoveryMode.ABORT)
        },
        {
            "name": "Validation Error",
            "state": {"trigger_validation_error": True, "user_id": "invalid"},
            "expected_error": TypeError,
            "recovery_policy": RecoveryPolicy(mode=RecoveryMode.ABORT)
        },
        {
            "name": "API Error",
            "state": {"trigger_api_error": True, "connection_error": True},
            "expected_error": ConnectionError,
            "recovery_policy": RecoveryPolicy(
                mode=RecoveryMode.RETRY,
                max_retries=3,
                backoff_factor=1.5
            )
        },
        {
            "name": "Processing Error",
            "state": {
                "trigger_processing_error": True,
                "api_response": {"data": {}}
            },
            "expected_error": KeyError,
            "recovery_policy": RecoveryPolicy(mode=RecoveryMode.ABORT)
        }
    ]
    
    # Results to save
    results = []
    
    # Run each scenario
    for scenario in scenarios:
        logger.info(f"\n--- Scenario: {scenario['name']} ---\n")
        
        try:
            # Run with recovery
            result = with_recovery(
                app,
                scenario["state"],
                default_policy=scenario["recovery_policy"]
            )
            
            # This should not happen as we expect errors
            logger.warning(f"Expected error but got result: {result}")
            
        except Exception as e:
            # Get the enhanced error
            if isinstance(e, EnhancedError):
                enhanced_error = e
            else:
                # Capture error context
                enhanced_error = capture_error_context(
                    e,
                    state=scenario["state"],
                    category="DEMO",
                    severity="ERROR"
                )
            
            logger.error(f"Error: {enhanced_error.formatted_message()}")
            
            # Get suggestions
            suggestions = get_suggestions(enhanced_error)
            
            # Log suggestions
            logger.info("\nSuggestions:")
            for i, suggestion in enumerate(suggestions["suggestions"], 1):
                logger.info(f"{i}. {suggestion}")
            
            # Get documentation
            documentation = get_documentation_for_error(enhanced_error)
            
            if documentation:
                logger.info("\nDocumentation:")
                for i, doc in enumerate(documentation, 1):
                    logger.info(f"{i}. {doc['title']} ({doc['path']})")
            
            # Save results
            results.append({
                "scenario": scenario["name"],
                "error_code": enhanced_error.error_code,
                "error_message": enhanced_error.message,
                "error_category": enhanced_error.category,
                "suggestions_count": len(suggestions["suggestions"]),
                "documentation_count": len(documentation)
            })
            
            # Simulate user feedback (random for demo)
            if suggestions["suggestions"]:
                # Submit positive feedback for first suggestion
                submit_feedback(
                    enhanced_error.error_code,
                    suggestions["suggestions"][0],
                    helpful=True
                )
                logger.info(f"\nFeedback submitted: The suggestion was helpful")
    
    # Save results
    with open("logs/error_suggestions_demo_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to logs/error_suggestions_demo_results.json")
    
    return results

def main():
    """Run the demonstration."""
    try:
        # Run demonstration
        results = demonstrate_error_suggestions()
        
        # Show summary
        logger.info("\n=== DEMONSTRATION SUMMARY ===\n")
        logger.info(f"Demonstrated error suggestions for {len(results)} scenarios")
        logger.info("Each scenario showed different types of errors and the")
        logger.info("suggestions provided by the Error Suggestions Engine")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 