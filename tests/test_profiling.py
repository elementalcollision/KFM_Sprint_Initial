"""
Tests for the performance profiling system.
"""

import os
import time
import json
import shutil
import unittest
from unittest.mock import patch, MagicMock

from src.profiling import (
    PerformanceProfiler,
    profile_node,
    start_profiling_run,
    end_profiling_run,
    generate_performance_report,
    compare_profiling_runs,
    configure_profiler,
    clear_profiling_data
)

# Test directory for reports
TEST_REPORT_DIR = "logs/test_performance"

class MockState:
    """Mock state class for testing"""
    def __init__(self, data=None):
        self.data = data or {"test_key": "test_value"}
        
    def to_dict(self):
        return self.data.copy()

class TestPerformanceProfiler(unittest.TestCase):
    """Tests for the PerformanceProfiler class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a profiler instance for testing
        self.profiler = PerformanceProfiler(report_dir=TEST_REPORT_DIR)
        
        # Create test directory if it doesn't exist
        os.makedirs(TEST_REPORT_DIR, exist_ok=True)
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove test directory
        if os.path.exists(TEST_REPORT_DIR):
            shutil.rmtree(TEST_REPORT_DIR)
    
    def test_start_end_run(self):
        """Test starting and ending a profiling run"""
        # Start a run
        run_id = self.profiler.start_run("test_run")
        self.assertEqual(run_id, "test_run")
        self.assertEqual(self.profiler.current_run_id, "test_run")
        self.assertIsNotNone(self.profiler.run_start_time)
        
        # Wait a bit
        time.sleep(0.01)
        
        # End the run
        summary = self.profiler.end_run()
        self.assertEqual(summary["run_id"], "test_run")
        self.assertIsNone(self.profiler.current_run_id)
        self.assertGreater(summary["total_time"], 0)
        self.assertEqual(summary["nodes_executed"], 0)
    
    def test_record_node_execution(self):
        """Test recording node execution statistics"""
        # Start a run
        self.profiler.start_run("test_run")
        
        # Record a node execution
        self.profiler.record_node_execution(
            node_name="test_node",
            execution_time=0.1,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        
        # Check that the statistics were updated
        self.assertEqual(len(self.profiler.node_timing["test_node"]), 1)
        self.assertEqual(self.profiler.node_timing["test_node"][0], 0.1)
        self.assertEqual(self.profiler.node_calls["test_node"], 1)
        self.assertEqual(self.profiler.total_nodes_executed, 1)
        self.assertEqual(len(self.profiler.execution_timeline), 1)
        
        # Record another execution of the same node
        self.profiler.record_node_execution(
            node_name="test_node",
            execution_time=0.2,
            input_state={"input": "value2"},
            output_state={"output": "result2"}
        )
        
        # Check that the statistics were updated
        self.assertEqual(len(self.profiler.node_timing["test_node"]), 2)
        self.assertEqual(self.profiler.node_timing["test_node"][1], 0.2)
        self.assertEqual(self.profiler.node_calls["test_node"], 2)
        self.assertEqual(self.profiler.total_nodes_executed, 2)
        self.assertEqual(len(self.profiler.execution_timeline), 2)
        
        # End the run
        summary = self.profiler.end_run()
        
        # Check the summary has our node
        self.assertEqual(summary["nodes_executed"], 2)
        self.assertIn("test_node", summary["node_statistics"])
        self.assertEqual(summary["node_statistics"]["test_node"]["calls"], 2)
        # Use assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(summary["node_statistics"]["test_node"]["total_time"], 0.3, places=6)
    
    def test_node_decorator(self):
        """Test the node profiling decorator"""
        # Define a test function with the decorator
        @self.profiler.profile_node
        def test_function(state):
            time.sleep(0.01)  # Simulate work
            return state
        
        # Start a run
        self.profiler.start_run("test_run")
        
        # Call the decorated function
        state = {"test": "data"}
        result = test_function(state)
        
        # Check the result
        self.assertEqual(result, state)
        
        # Check that the execution was recorded
        self.assertEqual(self.profiler.node_calls["test_function"], 1)
        self.assertGreater(self.profiler.node_timing["test_function"][0], 0)
        
        # End the run
        summary = self.profiler.end_run()
        
        # Check the summary
        self.assertEqual(summary["nodes_executed"], 1)
        self.assertIn("test_function", summary["node_statistics"])
    
    def test_node_decorator_with_class(self):
        """Test the node profiling decorator with a class instance"""
        # Define a test function with the decorator
        @self.profiler.profile_node
        def test_function(state):
            time.sleep(0.01)  # Simulate work
            return state
        
        # Start a run
        self.profiler.start_run("test_run")
        
        # Call the decorated function with a mock state class
        state = MockState({"test": "data"})
        result = test_function(state)
        
        # Check the result is the same object
        self.assertEqual(result, state)
        
        # Check that the execution was recorded
        self.assertEqual(self.profiler.node_calls["test_function"], 1)
        self.assertGreater(self.profiler.node_timing["test_function"][0], 0)
        
        # End the run
        self.profiler.end_run()
    
    def test_identify_bottlenecks(self):
        """Test bottleneck identification"""
        # Start a run
        self.profiler.start_run("test_run")
        
        # Record executions with different times
        self.profiler.record_node_execution(
            node_name="fast_node",
            execution_time=0.1,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        
        self.profiler.record_node_execution(
            node_name="slow_node",
            execution_time=1.0,  # Much slower
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        
        # End the run
        summary = self.profiler.end_run()
        
        # Check that bottlenecks were identified
        self.assertIn("bottlenecks", summary)
        # We're expecting both nodes to be identified as bottlenecks,
        # since the total runtime is so short in the test
        self.assertGreaterEqual(len(summary["bottlenecks"]), 1)
        # Check that "slow_node" is identified as a bottleneck
        slow_node_found = False
        for bottleneck in summary["bottlenecks"]:
            if bottleneck["node_name"] == "slow_node":
                slow_node_found = True
                self.assertEqual(bottleneck["severity"], "high")
                break
        self.assertTrue(slow_node_found, "slow_node should be identified as a bottleneck")
    
    def test_generate_report(self):
        """Test report generation"""
        # Start a run and record some data
        self.profiler.start_run("test_run")
        
        self.profiler.record_node_execution(
            node_name="node1",
            execution_time=0.1,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        
        self.profiler.record_node_execution(
            node_name="node2",
            execution_time=0.2,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        
        # End the run
        self.profiler.end_run()
        
        # Generate a report
        report = self.profiler.generate_report("test_run", include_graphs=True)
        
        # Check the report structure
        self.assertEqual(report["run_id"], "test_run")
        self.assertIn("run_summary", report)
        self.assertIn("node_details", report)
        self.assertIn("node1", report["node_details"])
        self.assertIn("node2", report["node_details"])
        
        # Check that the file was created
        report_path = os.path.join(TEST_REPORT_DIR, "report_test_run.json")
        self.assertTrue(os.path.exists(report_path))
        
        # Check visualizations
        self.assertIn("visualizations", report)
        self.assertIn("node_times", report["visualizations"])
        self.assertTrue(os.path.exists(report["visualizations"]["node_times"]))
    
    def test_compare_runs(self):
        """Test comparing multiple runs"""
        # Create two runs
        # Run 1
        self.profiler.start_run("run1")
        self.profiler.record_node_execution(
            node_name="common_node",
            execution_time=0.1,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.record_node_execution(
            node_name="node_run1",
            execution_time=0.2,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.end_run()
        
        # Run 2
        self.profiler.start_run("run2")
        self.profiler.record_node_execution(
            node_name="common_node",
            execution_time=0.15,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.record_node_execution(
            node_name="node_run2",
            execution_time=0.25,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.end_run()
        
        # Compare the runs
        comparison = self.profiler.compare_runs(["run1", "run2"], include_graphs=True)
        
        # Check the comparison structure
        self.assertEqual(comparison["run_ids"], ["run1", "run2"])
        self.assertIn("total_times", comparison)
        self.assertIn("nodes_executed", comparison)
        self.assertIn("node_comparisons", comparison)
        self.assertIn("common_node", comparison["node_comparisons"])
        self.assertIn("node_run1", comparison["node_comparisons"])
        self.assertIn("node_run2", comparison["node_comparisons"])
        
        # Check that the file was created
        comparison_path = os.path.join(TEST_REPORT_DIR, "comparison_run1_vs_run2.json")
        self.assertTrue(os.path.exists(comparison_path))
        
        # Check visualizations
        self.assertIn("visualizations", comparison)
        self.assertIn("total_time", comparison["visualizations"])
        self.assertTrue(os.path.exists(comparison["visualizations"]["total_time"]))
    
    def test_clear_data(self):
        """Test clearing profiling data"""
        # Create some data
        self.profiler.start_run("test_run")
        self.profiler.record_node_execution(
            node_name="node1",
            execution_time=0.1,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.end_run()
        
        # Verify data exists
        self.assertEqual(len(self.profiler.node_timing["node1"]), 1)
        self.assertEqual(len(self.profiler.historical_runs), 1)
        
        # Clear data keeping historical
        self.profiler.clear_data(keep_historical=True)
        
        # Check current data is cleared but historical remains
        self.assertEqual(len(self.profiler.node_timing["node1"]), 0)
        self.assertEqual(len(self.profiler.historical_runs), 1)
        
        # Create more data
        self.profiler.start_run("test_run2")
        self.profiler.record_node_execution(
            node_name="node2",
            execution_time=0.2,
            input_state={"input": "value"},
            output_state={"output": "result"}
        )
        self.profiler.end_run()
        
        # Clear all data
        self.profiler.clear_data(keep_historical=False)
        
        # Check everything is cleared
        self.assertEqual(len(self.profiler.node_timing["node1"]), 0)
        self.assertEqual(len(self.profiler.node_timing["node2"]), 0)
        self.assertEqual(len(self.profiler.historical_runs), 0)

class TestGlobalFunctions(unittest.TestCase):
    """Tests for the global profiling functions"""
    
    def setUp(self):
        """Set up test environment"""
        # Configure the profiler for testing
        configure_profiler(report_dir=TEST_REPORT_DIR)
        
        # Create test directory if it doesn't exist
        os.makedirs(TEST_REPORT_DIR, exist_ok=True)
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear all profiling data
        clear_profiling_data()
        
        # Remove test directory
        if os.path.exists(TEST_REPORT_DIR):
            shutil.rmtree(TEST_REPORT_DIR)
    
    def test_profile_node_decorator(self):
        """Test the global profile_node decorator"""
        # Define a test function with the decorator
        @profile_node
        def test_function(state):
            time.sleep(0.01)  # Simulate work
            return state
        
        # Start a run
        run_id = start_profiling_run("test_run")
        self.assertEqual(run_id, "test_run")
        
        # Call the decorated function
        state = {"test": "data"}
        result = test_function(state)
        
        # Check the result
        self.assertEqual(result, state)
        
        # End the run
        summary = end_profiling_run()
        
        # Check the summary
        self.assertEqual(summary["nodes_executed"], 1)
        self.assertIn("test_function", summary["node_statistics"])
    
    def test_reporting_functions(self):
        """Test the global reporting functions"""
        # Start a run and record some data
        start_profiling_run("test_run")
        
        # Define a function to test
        @profile_node
        def test_function(state):
            time.sleep(0.01)
            return state
        
        # Call the function a few times
        test_function({"data": 1})
        test_function({"data": 2})
        
        # End the run
        end_profiling_run()
        
        # Generate a report
        report = generate_performance_report("test_run")
        
        # Check the report
        self.assertEqual(report["run_id"], "test_run")
        self.assertIn("node_details", report)
        self.assertIn("test_function", report["node_details"])
        
        # Start another run
        start_profiling_run("test_run2")
        test_function({"data": 3})
        end_profiling_run()
        
        # Compare runs
        comparison = compare_profiling_runs(["test_run", "test_run2"])
        
        # Check the comparison
        self.assertEqual(comparison["run_ids"], ["test_run", "test_run2"])
        self.assertIn("node_comparisons", comparison)
        self.assertIn("test_function", comparison["node_comparisons"])

if __name__ == "__main__":
    unittest.main() 