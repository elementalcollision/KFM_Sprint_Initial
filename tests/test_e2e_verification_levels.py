#!/usr/bin/env python3
"""
End-to-end tests for the State Propagation Verification Framework with different verbosity levels.

This module demonstrates how to use the verification framework at different verbosity levels
and compares the results in terms of detail, coverage, and performance.
"""

import os
import sys
import unittest
import json
import time
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.state import KFMAgentState
from src.state_verification import (
    configure_verification_framework,
    reset_verification,
    register_common_validators,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC
)
from src.state_verification_integration import (
    initialize_verification_integration,
    create_verification_graph,
    generate_state_flow_report
)
from src.logger import setup_logger

# Setup logger for the tests
logger = setup_logger('VerificationE2ETests')

class TestE2EVerificationLevels(unittest.TestCase):
    """Test end-to-end verification with different verbosity levels."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with common paths and configurations."""
        # Create test output directory
        cls.output_dir = os.path.join(project_root, "logs", "test_verification_levels")
        os.makedirs(cls.output_dir, exist_ok=True)
    
    def setUp(self):
        """Set up for each test."""
        # Reset verification state before each test
        reset_verification()
    
    def create_test_state(self, task_name: str, include_error: bool = False) -> Dict[str, Any]:
        """
        Create a test state for verification.
        
        Args:
            task_name: Task name for the test
            include_error: Whether to include an error in the state
            
        Returns:
            Dict[str, Any]: Test state dictionary
        """
        test_state = {
            "task_name": task_name,
            "input": {
                "query": f"Test query for {task_name}",
                "context": "Context for state verification testing"
            }
        }
        
        if include_error:
            test_state["error"] = f"Test error for {task_name}"
        
        return test_state
    
    def run_verification_with_level(self, level: int, task_name: str, 
                                  include_error: bool = False) -> Dict[str, Any]:
        """
        Run verification with a specific level.
        
        Args:
            level: Verification level to use
            task_name: Task name for the test
            include_error: Whether to include an error in the test state
            
        Returns:
            Dict[str, Any]: Results of the verification
        """
        level_name = {
            VERIFICATION_LEVEL_BASIC: "basic",
            VERIFICATION_LEVEL_STANDARD: "standard",
            VERIFICATION_LEVEL_DETAILED: "detailed",
            VERIFICATION_LEVEL_DIAGNOSTIC: "diagnostic"
        }.get(level, str(level))
        
        # Create test output directory for this run
        output_dir = os.path.join(self.output_dir, level_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure verification framework with the specified level
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
        
        # Create the verification-enabled graph
        graph, components = create_verification_graph()
        
        # Create test state
        test_state = self.create_test_state(task_name, include_error)
        
        # Start time for performance measurement
        start_time = time.time()
        
        try:
            # Run graph with verification
            logger.info(f"Running verification at level {level_name} for task {task_name}")
            final_state = graph.invoke(test_state)
            execution_time = time.time() - start_time
            
            # Generate report
            report_path = generate_state_flow_report(output_dir)
            
            # Collect results
            results = {
                "level": level,
                "level_name": level_name,
                "task_name": task_name,
                "final_state": final_state,
                "execution_time": execution_time,
                "report_path": report_path,
                "success": True
            }
            
            logger.info(f"Verification at level {level_name} completed in {execution_time:.3f} seconds")
            
            # Save the final state
            with open(os.path.join(output_dir, "final_state.json"), 'w') as f:
                json.dump(final_state, f, indent=2)
                
            return results
            
        except Exception as e:
            logger.error(f"Verification failed at level {level_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "level": level,
                "level_name": level_name,
                "task_name": task_name,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "success": False
            }
    
    def test_basic_verification(self):
        """Test with BASIC verification level."""
        results = self.run_verification_with_level(
            VERIFICATION_LEVEL_BASIC, 
            "basic_verification_test"
        )
        
        self.assertTrue(results["success"], "Basic verification should succeed")
        self.assertIn("final_state", results, "Should have final state")
        self.assertIn("execution_time", results, "Should track execution time")
        
        # Basic verification should have minimal validation, just checking key workflow stages
        final_state = results["final_state"]
        self.assertIn("task_name", final_state, "Final state should contain task_name")
        
        logger.info(f"Basic verification completed in {results['execution_time']:.3f} seconds")
    
    def test_standard_verification(self):
        """Test with STANDARD verification level."""
        results = self.run_verification_with_level(
            VERIFICATION_LEVEL_STANDARD, 
            "standard_verification_test"
        )
        
        self.assertTrue(results["success"], "Standard verification should succeed")
        self.assertIn("final_state", results, "Should have final state")
        
        # Standard verification should include more detailed validation
        final_state = results["final_state"]
        self.assertIn("task_name", final_state, "Final state should contain task_name")
        self.assertIn("report_path", results, "Should generate report")
        
        logger.info(f"Standard verification completed in {results['execution_time']:.3f} seconds")
    
    def test_detailed_verification(self):
        """Test with DETAILED verification level."""
        results = self.run_verification_with_level(
            VERIFICATION_LEVEL_DETAILED, 
            "detailed_verification_test"
        )
        
        self.assertTrue(results["success"], "Detailed verification should succeed")
        self.assertIn("final_state", results, "Should have final state")
        
        # Detailed verification should include field-level validation
        final_state = results["final_state"]
        self.assertIn("task_name", final_state, "Final state should contain task_name")
        self.assertIn("report_path", results, "Should generate report")
        
        logger.info(f"Detailed verification completed in {results['execution_time']:.3f} seconds")
    
    def test_diagnostic_verification(self):
        """Test with DIAGNOSTIC verification level."""
        results = self.run_verification_with_level(
            VERIFICATION_LEVEL_DIAGNOSTIC, 
            "diagnostic_verification_test"
        )
        
        self.assertTrue(results["success"], "Diagnostic verification should succeed")
        self.assertIn("final_state", results, "Should have final state")
        
        # Diagnostic verification should include full validation and performance metrics
        final_state = results["final_state"]
        self.assertIn("task_name", final_state, "Final state should contain task_name")
        self.assertIn("report_path", results, "Should generate report")
        
        logger.info(f"Diagnostic verification completed in {results['execution_time']:.3f} seconds")
    
    def test_error_detection(self):
        """Test error detection with different verbosity levels."""
        # Run with error at different levels
        basic_results = self.run_verification_with_level(
            VERIFICATION_LEVEL_BASIC, 
            "error_test_basic",
            include_error=True
        )
        
        detailed_results = self.run_verification_with_level(
            VERIFICATION_LEVEL_DETAILED, 
            "error_test_detailed",
            include_error=True
        )
        
        # Both should detect the error
        self.assertTrue(basic_results["success"], "Basic should handle errors")
        self.assertTrue(detailed_results["success"], "Detailed should handle errors")
        
        # The detailed level should provide more information about the error
        self.assertIn("error", basic_results["final_state"], "Basic should track error")
        self.assertIn("error", detailed_results["final_state"], "Detailed should track error")
        
        logger.info(f"Error detection at basic level took {basic_results['execution_time']:.3f} seconds")
        logger.info(f"Error detection at detailed level took {detailed_results['execution_time']:.3f} seconds")
    
    def test_performance_comparison(self):
        """Compare performance of different verification levels."""
        task_name = "performance_test"
        
        # Run verification at all levels
        times = {}
        for level in [
            VERIFICATION_LEVEL_BASIC,
            VERIFICATION_LEVEL_STANDARD,
            VERIFICATION_LEVEL_DETAILED,
            VERIFICATION_LEVEL_DIAGNOSTIC
        ]:
            results = self.run_verification_with_level(level, f"{task_name}_{level}")
            level_name = results["level_name"]
            times[level_name] = results["execution_time"]
        
        # Log performance comparison
        logger.info("Performance comparison:")
        for level_name, execution_time in times.items():
            logger.info(f"  {level_name.ljust(10)}: {execution_time:.3f} seconds")
        
        # Basic should be fastest, diagnostic slowest
        self.assertLessEqual(
            times["basic"], 
            times["diagnostic"], 
            "Basic verification should be faster than diagnostic"
        )

if __name__ == "__main__":
    unittest.main() 