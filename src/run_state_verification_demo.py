#!/usr/bin/env python3
"""
State Verification Framework Demo Script.

This script demonstrates the State Propagation Verification Framework at different
verbosity levels using sample test states.

Usage:
    python run_state_verification_demo.py [--level=LEVEL] [--input=FILE] [--output=DIR]

Options:
    --level=LEVEL    Verification level to use (basic, standard, detailed, diagnostic)
    --input=FILE     JSON file containing test state to use (optional)
    --output=DIR     Directory to store verification output (default: logs/state_verification_demo)
    --help           Show this help message
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.state_verification import (
    configure_verification_framework,
    reset_verification,
    register_common_validators,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC,
    generate_verification_report
)
from src.state_verification_integration import (
    initialize_verification_integration,
    create_verification_graph,
    generate_state_flow_report
)
from src.logger import (
    setup_logger,
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    get_session_log_dir,
    setup_shared_file_logger
)

# Setup logger
logger = setup_logger('VerificationDemo')

def get_verification_level(level_name: str) -> int:
    """
    Convert level name to verification level constant.
    
    Args:
        level_name: Name of the verification level
        
    Returns:
        int: Verification level constant
    """
    level_map = {
        "basic": VERIFICATION_LEVEL_BASIC,
        "standard": VERIFICATION_LEVEL_STANDARD,
        "detailed": VERIFICATION_LEVEL_DETAILED,
        "diagnostic": VERIFICATION_LEVEL_DIAGNOSTIC
    }
    
    return level_map.get(level_name.lower(), VERIFICATION_LEVEL_STANDARD)

def get_level_name(level: int) -> str:
    """
    Convert verification level constant to name.
    
    Args:
        level: Verification level constant
        
    Returns:
        str: Level name
    """
    level_map = {
        VERIFICATION_LEVEL_BASIC: "basic",
        VERIFICATION_LEVEL_STANDARD: "standard",
        VERIFICATION_LEVEL_DETAILED: "detailed",
        VERIFICATION_LEVEL_DIAGNOSTIC: "diagnostic"
    }
    
    return level_map.get(level, "unknown")

def create_sample_state(task_name: str, include_error: bool = False) -> Dict[str, Any]:
    """
    Create a sample state for verification demo.
    
    Args:
        task_name: Task name for the demo
        include_error: Whether to include an error in the state
        
    Returns:
        Dict[str, Any]: Sample state dictionary
    """
    state = {
        "task_name": task_name,
        "input": {
            "query": f"Sample query for {task_name}",
            "context": "Sample context for state verification demo"
        },
        "active_component": "monitor",
        "kfm_metrics": {
            "latency": 0.5,
            "accuracy": 0.95,
            "usage": {
                "cpu": 0.3,
                "memory": 0.2
            }
        },
        "execution_performance": {
            "latency": 0.2,
            "accuracy": 0.98
        },
        "reflections": []
    }
    
    if include_error:
        state["error"] = f"Sample error for {task_name}"
    
    return state

def run_verification_demo(level: int, input_file: Optional[str] = None, 
                         output_dir: str = None) -> Dict[str, Any]:
    """
    Run verification framework demo with specified level.
    
    Args:
        level: Verification level to use
        input_file: Optional path to JSON file with test state
        output_dir: Directory to store verification output
        
    Returns:
        Dict[str, Any]: Results of the verification
    """
    level_name = get_level_name(level)
    
    # Setup output directory
    if output_dir is None:
        output_dir = os.path.join(project_root, "logs", "state_verification_demo", level_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Reset any existing verification state
    reset_verification()
    
    # Configure framework with specified level
    configure_verification_framework(
        verification_level=level,
        visualization_enabled=True,
        output_dir=output_dir,
        log_state_size=True,
        verbosity=2 if level >= VERIFICATION_LEVEL_DETAILED else 1
    )
    
    # Register common validators
    register_common_validators()
    
    # Initialize integration
    initialize_verification_integration(verification_level=level)
    
    try:
        # Create verification-enabled graph
        logger.info(f"Creating verification graph at {level_name} level")
        graph, components = create_verification_graph()
        
        # Get input state
        if input_file and os.path.exists(input_file):
            logger.info(f"Loading test state from {input_file}")
            with open(input_file, 'r') as f:
                initial_state = json.load(f)
        else:
            logger.info("Using sample test state")
            task_name = f"verification_demo_{level_name}"
            initial_state = create_sample_state(task_name)
        
        # Save initial state
        with open(os.path.join(output_dir, "initial_state.json"), 'w') as f:
            json.dump(initial_state, f, indent=2)
        
        # Start time for performance measurement
        start_time = time.time()
        
        # Run graph with verification
        logger.info(f"Running verification at {level_name} level")
        final_state = graph.invoke(initial_state)
        execution_time = time.time() - start_time
        
        # Generate report
        logger.info("Generating verification report")
        report_path = generate_state_flow_report(output_dir)
        
        # Save final state
        with open(os.path.join(output_dir, "final_state.json"), 'w') as f:
            json.dump(final_state, f, indent=2)
        
        # Collect results
        results = {
            "level": level,
            "level_name": level_name,
            "final_state": final_state,
            "execution_time": execution_time,
            "report_path": report_path,
            "success": True
        }
        
        logger.info(f"Verification at {level_name} level completed in {execution_time:.3f} seconds")
        logger.info(f"Output saved to {output_dir}")
        logger.info(f"Verification report: {report_path}")
        
        return results
        
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "level": level,
            "level_name": level_name,
            "error": str(e),
            "execution_time": time.time() - start_time if 'start_time' in locals() else 0,
            "success": False
        }

def show_verification_comparison():
    """Show a comparison of different verification levels."""
    print("\nState Verification Framework - Level Comparison")
    print("=" * 50)
    print("BASIC:")
    print("  - Minimal overhead")
    print("  - Basic state consistency checks")
    print("  - Simple transition validation")
    print("  - No field-level validation")
    print("\nSTANDARD:")
    print("  - Moderate overhead")
    print("  - Full state history tracking")
    print("  - Transition validation")
    print("  - Basic field validation")
    print("  - Simple visualization")
    print("\nDETAILED:")
    print("  - Higher overhead")
    print("  - Comprehensive field validation")
    print("  - Extended state history")
    print("  - Detailed transition analysis")
    print("  - Enhanced visualization")
    print("\nDIAGNOSTIC:")
    print("  - Maximum instrumentation")
    print("  - Complete field validation")
    print("  - Performance metrics")
    print("  - Full state history with timestamps")
    print("  - Comprehensive visualization")
    print("=" * 50)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="State Verification Framework Demo")
    parser.add_argument("--level", default="standard", help="Verification level (basic, standard, detailed, diagnostic)")
    parser.add_argument("--input", help="JSON file containing test state")
    parser.add_argument("--output", help="Directory to store verification output")
    parser.add_argument("--all", action="store_true", help="Run all levels and compare results")
    parser.add_argument("--error", action="store_true", help="Include error in test state")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error output")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up centralized logging
    log_manager = setup_centralized_logging()
    
    # Create a timestamped log directory for this verification demo
    verification_type = f"verification_demo"
    log_file = create_timestamped_log_file(verification_type)
    log_filename = os.path.basename(log_file)
    session_dir = get_session_log_dir()
    
    # Set up component-specific logging
    demo_logger = setup_component_logger(
        "verification.demo",
        log_level="DEBUG" if args.verbose else "INFO"
    )
    
    # Add a shared file logger for all components in this run
    setup_shared_file_logger(log_filename)
    
    logger.info(f"Logs will be written to session directory: {session_dir}")
    logger.info(f"Main log file: {log_filename}")
    
    # If multiple levels specified, run comparison
    if args.all:
        logger.info("Running comparison of all verification levels")
        show_verification_comparison()
        return 0
        
    # Parse verification level
    level = get_verification_level(args.level)
    level_name = get_level_name(level)
    
    # Run verification at specified level
    results = run_verification_demo(
        level, 
        input_file=args.input,
        output_dir=args.output if args.output else None
    )
    
    # Display results summary
    if results.get("success", False):
        if not args.quiet:
            print("\n" + "="*60)
            print(f"Verification Demo ({level_name} level)")
            print("="*60)
            print(f"Execution time: {results['execution_time']:.3f} seconds")
            
            if 'final_state' in results and 'result' in results['final_state']:
                print(f"Result: {results['final_state']['result']}")
                
            print(f"Report: {results['report_path']}")
            print(f"Logs: {session_dir}")
            print("="*60)
        return 0
    else:
        if not args.quiet:
            print("\n" + "="*60)
            print(f"❌ Verification Demo ({level_name} level) Failed")
            print("="*60)
            print(f"Error: {results.get('error', 'Unknown error')}")
            print(f"Logs: {session_dir}")
            print("="*60)
        return 1

if __name__ == "__main__":
    main() 