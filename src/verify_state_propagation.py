#!/usr/bin/env python3
"""
Run a verification test of state propagation in the KFM Agent.

This script demonstrates how to use the State Propagation Verification Framework
to verify the flow of state through the KFM Agent graph.
"""

import os
import sys
import json
import argparse
import logging
from typing import Dict, Any, Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.logger import setup_logger
from src.state_verification import (
    configure_verification_framework,
    register_common_validators,
    reset_verification,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC
)
from src.state_verification_integration import (
    initialize_verification_integration,
    create_verification_graph,
    generate_state_flow_report,
    register_node_specific_validators
)

# Setup logger for main script
logger = setup_logger('VerifyStatePropagation')

def create_test_input(task_name: str) -> Dict[str, Any]:
    """
    Create a test input state for the KFM Agent.
    
    Args:
        task_name: Task name to use
        
    Returns:
        Dict[str, Any]: Input state dictionary
    """
    return {
        "task_name": task_name,
        "input": {
            "query": f"Test query for {task_name}",
            "context": "Test context for state verification"
        }
    }

def run_verification_test(input_state: Dict[str, Any], output_dir: str) -> bool:
    """
    Run a verification test with the given input.
    
    Args:
        input_state: Input state to use
        output_dir: Directory for output files
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize the verification framework
        reset_verification()
        initialize_verification_integration(
            verification_level=VERIFICATION_LEVEL_DETAILED
        )
        
        # Register specific validators for the KFM pipeline
        register_node_specific_validators()
        
        # Create a verification-enabled graph
        logger.info("Creating verification-enabled graph...")
        graph, components = create_verification_graph()
        
        # Run the graph
        logger.info("Running KFM agent with verification...")
        result = graph.invoke(input_state)
        
        # Generate report
        logger.info("Generating verification report...")
        report_path = generate_state_flow_report(output_dir)
        
        # Print success message
        if "error" in result and result["error"] is not None:
            logger.error(f"Execution failed with error: {result['error']}")
            return False
            
        logger.info("Verification test completed successfully")
        logger.info(f"Report saved to {report_path}")
        
        # Also save the result to a file
        result_path = os.path.join(output_dir, "verification_result.json")
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Final result saved to {result_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Verification test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Verify state propagation in the KFM Agent"
    )
    parser.add_argument(
        "--task",
        default="verification_test",
        help="Task name for the test"
    )
    parser.add_argument(
        "--output-dir",
        default="logs/verification",
        help="Directory for output files"
    )
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create test input
    input_state = create_test_input(args.task)
    
    # Run verification test
    success = run_verification_test(input_state, args.output_dir)
    
    # Print summary
    print("\n" + "="*60)
    if success:
        print("✅ State Propagation Verification Successful")
    else:
        print("❌ State Propagation Verification Failed")
    print("="*60)
    print(f"Task: {args.task}")
    print(f"Output directory: {args.output_dir}")
    print("="*60)
    
    # Return status
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 