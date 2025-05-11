#!/usr/bin/env python
"""
Demonstration of the recovery mechanisms for graph execution.

This script shows how to use the recovery features to handle error conditions
during graph execution, including state rollback, node retry, graceful failure,
and partial execution resumption.
"""

import os
import sys
import time
import json
import random
import traceback
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.recovery import (
    RecoveryMode,
    RecoveryPolicy,
    RecoveryManager,
    resume_execution_from_node,
    verify_safe_resumption,
    create_fallback_state,
    with_recovery
)

from src.tracing import (
    configure_tracing,
    reset_trace_history,
    get_trace_history,
    get_state_history_tracker
)

from src.logger import setup_logger

# Set up logging
logger = setup_logger("recovery_demo")

class DemoLangGraphApp:
    """Mock LangGraph application for demonstrating recovery mechanisms."""
    
    def __init__(self):
        """Initialize the demo application with sample nodes."""
        # Define node names
        self.nodes = [
            "load_data", 
            "validate_input", 
            "process_data", 
            "transform_content", 
            "generate_output"
        ]
        
        # Create graph structure
        self.graph = type('Graph', (), {
            'nodes': self.nodes,
            'get_node': self.get_node
        })()
    
    def get_node(self, node_name):
        """Mock getting a node from the graph."""
        node_functions = {
            "load_data": self.load_data,
            "validate_input": self.validate_input,
            "process_data": self.process_data,
            "transform_content": self.transform_content,
            "generate_output": self.generate_output
        }
        
        if node_name in node_functions:
            return {"fn": node_functions[node_name]}
        
        # Default function that passes state through
        return {"fn": lambda state: state}
    
    def load_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Load sample data (first node)."""
        logger.info("Loading data...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Simulate loading data
        state["data"] = {
            "records": [
                {"id": 1, "value": "sample 1"},
                {"id": 2, "value": "sample 2"},
                {"id": 3, "value": "sample 3"}
            ],
            "metadata": {
                "source": "demo",
                "timestamp": time.time()
            }
        }
        
        state["load_time"] = time.time()
        
        return state
    
    def validate_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data (second node)."""
        logger.info("Validating input...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Get data from state
        data = state.get("data", {})
        records = data.get("records", [])
        
        # Simulated validation check
        if not records:
            # Demonstrate error handling - empty records
            raise ValueError("No records found in input data")
        
        # Optionally fail with 30% probability for retry demonstration
        if state.get("should_fail_validation") and random.random() < 0.3:
            raise ValueError("Random validation failure (for demonstration)")
        
        # Add validation results to state
        state["validation_results"] = {
            "valid": True,
            "record_count": len(records),
            "validation_time": time.time()
        }
        
        return state
    
    def process_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the validated data (third node)."""
        logger.info("Processing data...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Get data from state
        data = state.get("data", {})
        records = data.get("records", [])
        
        # Simulate processing - capitalize values
        processed_records = []
        for record in records:
            processed_record = record.copy()
            processed_record["value"] = processed_record["value"].upper()
            processed_records.append(processed_record)
        
        # Add processed data to state
        state["processed_data"] = {
            "records": processed_records,
            "processing_time": time.time()
        }
        
        # Always fail with catalog error if flag is set
        # This demonstrates error categories and custom handlers
        if state.get("trigger_catalog_error"):
            raise ValueError("CATALOG_ERROR: Item not found in catalog")
        
        return state
    
    def transform_content(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Transform the processed data (fourth node)."""
        logger.info("Transforming content...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Get processed data from state
        processed_data = state.get("processed_data", {})
        records = processed_data.get("records", [])
        
        # Simulate transformation - add prefix to values
        transformed_records = []
        for record in records:
            transformed_record = record.copy()
            transformed_record["value"] = f"TRANSFORMED_{transformed_record['value']}"
            transformed_records.append(transformed_record)
        
        # Add transformed data to state
        state["transformed_data"] = {
            "records": transformed_records,
            "transformation_time": time.time()
        }
        
        # Simulate a complex error that would benefit from rollback
        if state.get("trigger_transform_error"):
            logger.warning("Simulating transform error that requires rollback")
            raise RuntimeError("Transform error: incompatible data format")
        
        return state
    
    def generate_output(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final output (fifth node)."""
        logger.info("Generating output...")
        
        # Copy state to avoid modifying the original
        state = state.copy()
        
        # Get transformed data from state
        transformed_data = state.get("transformed_data", {})
        records = transformed_data.get("records", [])
        
        # Simulate output generation
        output = {
            "results": records,
            "summary": {
                "record_count": len(records),
                "generation_time": time.time(),
                "process_successful": True
            }
        }
        
        # Add output to state
        state["output"] = output
        
        return state

def demonstrate_normal_execution():
    """Demonstrate normal execution flow without errors."""
    logger.info("\n=== DEMONSTRATING NORMAL EXECUTION ===\n")
    
    # Create app and initial state
    app = DemoLangGraphApp()
    initial_state = {}
    
    # Configure tracing
    configure_tracing(log_level="INFO", history_buffer_size=100, enable_profiling=True)
    reset_trace_history()
    
    # Set up default recovery policies
    default_policy = RecoveryPolicy(mode=RecoveryMode.ABORT)
    
    # Execute with recovery
    start_time = time.time()
    result = with_recovery(app, initial_state, default_policy=default_policy)
    elapsed_time = time.time() - start_time
    
    # Show results
    logger.info(f"Execution completed in {elapsed_time:.2f} seconds")
    logger.info(f"Final state keys: {list(result.keys())}")
    logger.info(f"Output summary: {result.get('output', {}).get('summary', {})}")
    
    return result

def demonstrate_retry_recovery():
    """Demonstrate retry recovery for transient errors."""
    logger.info("\n=== DEMONSTRATING RETRY RECOVERY ===\n")
    
    # Create app and initial state
    app = DemoLangGraphApp()
    initial_state = {
        "should_fail_validation": True  # This will cause random failures in validation
    }
    
    # Configure tracing
    configure_tracing(log_level="INFO", history_buffer_size=100, enable_profiling=True)
    reset_trace_history()
    
    # Set up recovery policies
    default_policy = RecoveryPolicy(mode=RecoveryMode.ABORT)
    policies = {
        "validate_input": RecoveryPolicy(
            mode=RecoveryMode.RETRY,
            max_retries=5,
            backoff_factor=1.5
        )
    }
    
    # Execute with recovery
    start_time = time.time()
    result = with_recovery(app, initial_state, policies=policies, default_policy=default_policy)
    elapsed_time = time.time() - start_time
    
    # Show results
    logger.info(f"Execution completed in {elapsed_time:.2f} seconds")
    logger.info(f"Final state keys: {list(result.keys())}")
    logger.info(f"Output summary: {result.get('output', {}).get('summary', {})}")
    
    return result

def demonstrate_rollback_recovery():
    """Demonstrate rollback recovery for data consistency errors."""
    logger.info("\n=== DEMONSTRATING ROLLBACK RECOVERY ===\n")
    
    # Create app and initial state
    app = DemoLangGraphApp()
    initial_state = {
        "trigger_transform_error": True  # This will cause an error in the transform node
    }
    
    # Configure tracing
    configure_tracing(log_level="INFO", history_buffer_size=100, enable_profiling=True)
    reset_trace_history()
    
    # Create recovery manager for checkpointing
    recovery_manager = RecoveryManager()
    
    # Execute with manual checkpointing and recovery
    logger.info("Starting execution with manual checkpoints")
    
    # Load data
    state = app.load_data(initial_state)
    cp1 = recovery_manager.create_checkpoint(state, "After load_data")
    logger.info(f"Created checkpoint after load_data: {cp1}")
    
    # Validate input
    state = app.validate_input(state)
    cp2 = recovery_manager.create_checkpoint(state, "After validate_input")
    logger.info(f"Created checkpoint after validate_input: {cp2}")
    
    # Process data
    state = app.process_data(state)
    cp3 = recovery_manager.create_checkpoint(state, "After process_data")
    logger.info(f"Created checkpoint after process_data: {cp3}")
    
    # Transform content (this will fail)
    try:
        state = app.transform_content(state)
    except Exception as e:
        logger.error(f"Error in transform_content: {str(e)}")
        logger.info(f"Rolling back to checkpoint after process_data: {cp3}")
        state = recovery_manager.rollback_to_checkpoint(cp3)
        
        # Retry with error fixed
        logger.info("Retrying with error fixed")
        state["trigger_transform_error"] = False
        state = app.transform_content(state)
    
    # Generate output
    state = app.generate_output(state)
    
    # Show results
    logger.info(f"Final state keys: {list(state.keys())}")
    logger.info(f"Output summary: {state.get('output', {}).get('summary', {})}")
    
    return state

def demonstrate_skip_recovery():
    """Demonstrate skip recovery for non-critical errors."""
    logger.info("\n=== DEMONSTRATING SKIP RECOVERY ===\n")
    
    # Create app and initial state
    app = DemoLangGraphApp()
    initial_state = {
        "trigger_catalog_error": True  # This will cause an error in the process node
    }
    
    # Configure tracing
    configure_tracing(log_level="INFO", history_buffer_size=100, enable_profiling=True)
    reset_trace_history()
    
    # Set up recovery policies
    default_policy = RecoveryPolicy(mode=RecoveryMode.ABORT)
    policies = {
        "process_data": RecoveryPolicy(
            mode=RecoveryMode.SKIP,
            error_categories=["CATALOG_ERROR"]  # This category is detected from the error message
        )
    }
    
    # Add custom error handler
    def catalog_error_handler(error, state, node_name):
        logger.warning(f"Custom handler for catalog error in {node_name}")
        # Add placeholder processed data so downstream nodes can continue
        state = state.copy()
        state["processed_data"] = {
            "records": state.get("data", {}).get("records", []),
            "processing_time": time.time(),
            "warning": "Processed with placeholder data due to catalog error"
        }
        return RecoveryMode.SKIP, state
    
    # Update policy with custom handler
    policies["process_data"].custom_handler = catalog_error_handler
    
    # Execute with recovery
    start_time = time.time()
    result = with_recovery(app, initial_state, policies=policies, default_policy=default_policy)
    elapsed_time = time.time() - start_time
    
    # Show results
    logger.info(f"Execution completed in {elapsed_time:.2f} seconds")
    logger.info(f"Final state keys: {list(result.keys())}")
    logger.info(f"Output summary: {result.get('output', {}).get('summary', {})}")
    logger.info(f"Warning: {result.get('processed_data', {}).get('warning', 'No warning')}")
    
    return result

def demonstrate_resumption():
    """Demonstrate resumption of execution from a specific node."""
    logger.info("\n=== DEMONSTRATING RESUMPTION FROM NODE ===\n")
    
    # Create app and initial state
    app = DemoLangGraphApp()
    
    # Execute first two steps manually to create a partial state
    initial_state = {}
    state = app.load_data(initial_state)
    state = app.validate_input(state)
    
    # Configure tracing
    configure_tracing(log_level="INFO", history_buffer_size=100, enable_profiling=True)
    reset_trace_history()
    
    # Resume execution from process_data
    logger.info("Resuming execution from process_data")
    result = resume_execution_from_node(app, state, "process_data")
    
    # Show results
    logger.info(f"Final state keys: {list(result.keys())}")
    logger.info(f"Output summary: {result.get('output', {}).get('summary', {})}")
    
    return result

def main():
    """Run all demonstrations."""
    # Create directories if they don't exist
    os.makedirs("logs/checkpoints", exist_ok=True)
    
    try:
        # Run demos
        normal_result = demonstrate_normal_execution()
        retry_result = demonstrate_retry_recovery()
        rollback_result = demonstrate_rollback_recovery()
        skip_result = demonstrate_skip_recovery()
        resumption_result = demonstrate_resumption()
        
        # Get execution traces
        traces = get_trace_history()
        
        # Save execution results
        results = {
            "normal_execution": {
                "output_summary": normal_result.get("output", {}).get("summary", {}),
                "trace_count": len(traces)
            },
            "retry_recovery": {
                "output_summary": retry_result.get("output", {}).get("summary", {}),
                "retry_attempted": "error" in retry_result
            },
            "rollback_recovery": {
                "output_summary": rollback_result.get("output", {}).get("summary", {})
            },
            "skip_recovery": {
                "output_summary": skip_result.get("output", {}).get("summary", {}),
                "had_warning": "warning" in skip_result.get("processed_data", {})
            },
            "resumption": {
                "output_summary": resumption_result.get("output", {}).get("summary", {})
            }
        }
        
        # Save results to file
        os.makedirs("logs", exist_ok=True)
        with open("logs/recovery_demo_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info("\n=== DEMO SUMMARY ===\n")
        logger.info(f"All demonstrations completed successfully")
        logger.info(f"Results saved to logs/recovery_demo_results.json")
        
    except Exception as e:
        logger.error(f"Error running demonstrations: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 