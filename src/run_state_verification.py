#!/usr/bin/env python3
"""
Command-line utility to run and test the State Propagation Verification Framework.

This script provides a simple interface to:
1. Run a KFM agent graph with state verification enabled
2. Generate verification reports and visualizations
3. Test with different inputs and verification levels
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Any, Optional, Tuple
import matplotlib

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.verification.framework import (
    configure_verification_framework,
    reset_verification,
    register_common_validators,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC
)
from src.verification.state_flow import generate_state_flow_report
from src.verification.graph import create_verification_graph
from src.logger import (
    setup_logger, 
    setup_shared_file_logger, 
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    get_session_log_dir
)
from src.core.state import KFMAgentState

# Set up logger
logger = setup_logger('state_verification')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the KFM Agent with State Propagation Verification"
    )
    
    parser.add_argument(
        "--input", "-i",
        help="Path to JSON file with input state data",
        default=None
    )
    
    parser.add_argument(
        "--level", "-l",
        help="Verification level (0=basic, 1=standard, 2=detailed, 3=diagnostic)",
        type=int,
        choices=[0, 1, 2, 3],
        default=1
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        help="Directory for output files",
        default="logs/verification"
    )
    
    parser.add_argument(
        "--task", "-t",
        help="Task name for the execution",
        default="default"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        help="Reduce output verbosity",
        action="store_true"
    )
    
    parser.add_argument(
        "--disable-visualization",
        help="Disable generation of state flow visualization",
        action="store_true"
    )
    
    return parser.parse_args()

def load_input_state(input_file: Optional[str], task_name: str) -> Dict[str, Any]:
    """
    Load input state from file or create a default one.
    
    Args:
        input_file: Path to JSON file with input state, or None for default
        task_name: Task name for the execution
        
    Returns:
        Dict[str, Any]: Input state for the graph
    """
    if input_file and os.path.exists(input_file):
        try:
            with open(input_file, 'r') as f:
                state_data = json.load(f)
                logger.info(f"Loaded input state from {input_file}")
                return state_data
        except Exception as e:
            logger.error(f"Error loading input from {input_file}: {e}")
            logger.info("Using default input state instead")
    
    # Create default input state
    return {
        "task_name": task_name,
        "input": {
            "query": f"Test query for {task_name}",
            "context": "This is a test context for state verification."
        }
    }

def create_sample_input_file(filepath: str) -> None:
    """
    Create a sample input file with default values.
    
    Args:
        filepath: Path where to create the sample file
    """
    sample_data = {
        "task_name": "sample_task",
        "input": {
            "query": "What is the weather like today?",
            "context": "The user is asking about the current weather conditions."
        }
    }
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(sample_data, f, indent=2)
        logger.info(f"Created sample input file at {filepath}")
    except Exception as e:
        logger.error(f"Error creating sample input file: {e}")

def setup_verification(level: int, output_dir: str, disable_visualization: bool) -> None:
    """
    Set up the verification framework with the specified options.
    
    Args:
        level: Verification level
        output_dir: Output directory
        disable_visualization: Whether to disable visualization
    """
    # Configure framework
    configure_verification_framework(
        verification_level=level,
        visualization_enabled=not disable_visualization,
        output_dir=output_dir,
        log_state_size=True,
        verbosity=2 if level >= VERIFICATION_LEVEL_DETAILED else 1
    )
    
    # Register common validators
    register_common_validators()
    
    level_names = {
        VERIFICATION_LEVEL_BASIC: "BASIC",
        VERIFICATION_LEVEL_STANDARD: "STANDARD",
        VERIFICATION_LEVEL_DETAILED: "DETAILED",
        VERIFICATION_LEVEL_DIAGNOSTIC: "DIAGNOSTIC"
    }
    
    logger.info(f"Verification framework configured with level {level} ({level_names.get(level, 'UNKNOWN')})")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Visualization enabled: {not disable_visualization}")

def run_verification(input_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Run the KFM agent with verification enabled.
    
    Args:
        input_state: Input state for the graph
        
    Returns:
        Optional[Dict[str, Any]]: Final state after execution, or None if error
    """
    try:
        # Create verification-enabled graph
        graph, components = create_verification_graph()
        
        logger.info("Starting execution with verification...")
        
        # Execute the graph with the input state
        final_state = graph.invoke(input_state)
        
        logger.info("Execution completed successfully")
        return final_state
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main entry point."""
    # Parse arguments
    args = parse_args()
    
    # Set up centralized logging
    log_manager = setup_centralized_logging()
    
    # Create a timestamped log directory for this verification run
    verification_type = f"verification_{args.level}"
    log_file = create_timestamped_log_file(verification_type)
    log_filename = os.path.basename(log_file)
    session_dir = get_session_log_dir()
    
    # Set up component-specific logging
    verification_logger = setup_component_logger(
        f"verification.level{args.level}",
        log_level="DEBUG" if not args.quiet else "WARNING"
    )
    
    # Add a shared file logger for all components in this run
    setup_shared_file_logger(log_filename)
    
    # Set logging level for the main logger
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)
    
    logger.info(f"Logs will be written to session directory: {session_dir}")
    logger.info(f"Main log file: {log_filename}")
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # If no input file is provided and not in quiet mode, create a sample one
    if not args.input and not args.quiet:
        sample_path = os.path.join(args.output_dir, "sample_input.json")
        create_sample_input_file(sample_path)
        logger.info(f"You can use this sample with: --input {sample_path}")
    
    # Load input state
    input_state = load_input_state(args.input, args.task)
    
    # Setup and reset verification
    reset_verification()
    setup_verification(args.level, args.output_dir, args.disable_visualization)
    
    # Run verification
    logger.info("Running KFM agent with state verification...")
    verification_logger.info(f"Starting verification at level {args.level}")
    verification_logger.info(f"Input state: {json.dumps(input_state, indent=2)}")
    
    final_state = run_verification(input_state)
    
    if final_state:
        # Generate report
        report_path = generate_state_flow_report(args.output_dir)
        verification_logger.info(f"Generated report at {report_path}")
        
        # Print summary
        if not args.quiet:
            print("\n" + "="*60)
            print("State Verification Summary")
            print("="*60)
            
            if "error" in final_state and final_state["error"]:
                print(f"❌ Execution ended with error: {final_state['error']}")
                verification_logger.error(f"Execution ended with error: {final_state['error']}")
            else:
                print("✅ Execution completed successfully")
                verification_logger.info("Execution completed successfully")
                
                if "result" in final_state:
                    print(f"\nResult: {final_state['result']}")
                    verification_logger.info(f"Result: {final_state['result']}")
                    
                if "active_component" in final_state:
                    print(f"Active component: {final_state['active_component']}")
                    verification_logger.info(f"Active component: {final_state['active_component']}")
            
            print(f"\nFull report: {report_path}")
            
            if not args.disable_visualization:
                viz_path = os.path.join(args.output_dir, "state_flow.png")
                if os.path.exists(viz_path):
                    print(f"Visualization: {viz_path}")
                    verification_logger.info(f"Generated visualization at {viz_path}")
            
            print(f"Logs: {session_dir}")
            print("="*60)
        
        verification_logger.info("Verification completed successfully")
        return 0  # Success
    else:
        verification_logger.error("Verification failed")
        
        if not args.quiet:
            print("\n" + "="*60)
            print("❌ State Verification Failed")
            print("="*60)
            print(f"See logs in: {session_dir}")
            print("="*60)
        
        return 1  # Error

if __name__ == "__main__":
    sys.exit(main()) 