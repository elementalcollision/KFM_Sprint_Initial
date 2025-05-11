import sys
import os
import unittest
import logging
from unittest.mock import patch, MagicMock
from typing import Dict, Any, Optional, List, Tuple
import json

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import create_kfm_agent_graph, run_kfm_agent
from src.state_types import KFMAgentState
from src.tracing import get_trace_history, reset_trace_history, configure_tracing

class CompiledGraphTestHarness(unittest.TestCase):
    """Base test class for testing the compiled graph execution."""
    
    def setUp(self):
        """Set up test fixtures, including mock components and tracing."""
        # Configure tracing for detailed execution logs
        configure_tracing(log_level=logging.DEBUG)
        reset_trace_history()
        
        # Create mock core components
        self.setup_mock_components()
        
        # Default scenario configuration
        self.default_input = {"text": "Test input data"}
        self.task_name = "test_task"
        
        # Execution tracking data
        self.node_execution_sequence = []
        self.state_transitions = []
        
    def setup_mock_components(self):
        """Set up mock components for the KFM agent."""
        # Mock registry
        self.mock_registry = MagicMock()
        
        # Mock state monitor
        self.mock_monitor = MagicMock()
        self.mock_monitor.get_performance_data.return_value = {
            'component_a': {'latency': 0.5, 'accuracy': 0.95},
            'component_b': {'latency': 0.8, 'accuracy': 0.85}
        }
        self.mock_monitor.get_task_requirements.return_value = {
            'max_latency': 1.0,
            'min_accuracy': 0.9
        }
        
        # Mock KFM planner
        self.mock_planner = MagicMock()
        self.mock_planner.decide_kfm_action.return_value = {
            'action': 'keep',
            'component': 'component_a',
            'reason': 'Good performance metrics'
        }
        
        # Mock execution engine
        self.mock_engine = MagicMock()
        self.mock_engine.apply_kfm_action.return_value = None
        self.mock_engine.get_active_component_key.return_value = 'component_a'
        self.mock_engine.execute_task.return_value = (
            {'status': 'success', 'data': {'records': 10}},
            {'latency': 0.5, 'accuracy': 0.95}
        )
    
    def create_test_graph(self, patch_components=True) -> Tuple[Any, Dict[str, Any]]:
        """Create a test graph with optional component patching.
        
        Args:
            patch_components: Whether to patch core components with mocks
            
        Returns:
            Tuple containing the compiled graph and its components
        """
        # Use patching to inject mock components
        if patch_components:
            with patch('src.factory.create_kfm_agent') as mock_factory:
                mock_factory.return_value = (
                    self.mock_registry,
                    self.mock_monitor,
                    self.mock_planner,
                    self.mock_engine
                )
                return create_kfm_agent_graph()
        else:
            return create_kfm_agent_graph()
    
    def execute_graph(self, input_data: Optional[Dict[str, Any]] = None, 
                     task_name: Optional[str] = None,
                     debug_mode: bool = True) -> Optional[Dict[str, Any]]:
        """Execute the graph with specified inputs.
        
        Args:
            input_data: The input data to use
            task_name: The task name to use
            debug_mode: Whether to run in debug mode with tracing
            
        Returns:
            The final state after execution
        """
        # Use provided values or defaults
        input_data = input_data or self.default_input
        task_name = task_name or self.task_name
        
        # Reset tracing
        reset_trace_history()
        
        # Run with component patching
        with patch('src.factory.create_kfm_agent') as mock_factory:
            mock_factory.return_value = (
                self.mock_registry,
                self.mock_monitor,
                self.mock_planner,
                self.mock_engine
            )
            
            # Execute the graph
            final_state = run_kfm_agent(
                input_data=input_data,
                task_name=task_name,
                debug_mode=debug_mode,
                trace_level=logging.DEBUG
            )
            
            # Save trace history for analysis
            self.trace_history = get_trace_history()
            
            return final_state
    
    def analyze_trace(self) -> Dict[str, Any]:
        """Analyze the trace history to extract execution metrics and sequence.
        
        Returns:
            Dictionary with analysis results
        """
        if not hasattr(self, 'trace_history'):
            return {"error": "No trace history available"}
        
        # Extract node execution sequence
        node_sequence = [entry.get('node') for entry in self.trace_history 
                        if 'node' in entry and entry.get('success', False)]
        
        # Calculate node timing
        node_timing = {}
        for entry in self.trace_history:
            if 'node' in entry and 'duration' in entry:
                node = entry['node']
                if node not in node_timing:
                    node_timing[node] = []
                node_timing[node].append(entry['duration'])
        
        # Average timing by node
        avg_timing = {
            node: sum(times) / len(times) 
            for node, times in node_timing.items()
        }
        
        # Extract state transitions
        state_transitions = []
        prev_state = None
        for i, entry in enumerate(self.trace_history):
            if 'output_state' in entry:
                current_state = entry['output_state']
                if prev_state is not None:
                    # Find differences
                    changes = {}
                    for key in set(current_state.keys()) | set(prev_state.keys()):
                        if key not in prev_state:
                            changes[key] = {'added': current_state[key]}
                        elif key not in current_state:
                            changes[key] = {'removed': prev_state[key]}
                        elif prev_state[key] != current_state[key]:
                            changes[key] = {
                                'before': prev_state[key],
                                'after': current_state[key]
                            }
                    
                    state_transitions.append({
                        'node': entry.get('node', f"unknown_node_{i}"),
                        'changes': changes
                    })
                
                prev_state = current_state
        
        return {
            'node_sequence': node_sequence,
            'node_timing': avg_timing,
            'state_transitions': state_transitions,
            'total_nodes_executed': len(node_sequence),
            'unique_nodes_executed': len(set(node_sequence))
        }
    
    def verify_node_execution_sequence(self, expected_sequence: List[str]) -> bool:
        """Verify that nodes were executed in the expected sequence.
        
        Args:
            expected_sequence: The expected node execution sequence
            
        Returns:
            True if the sequence matches expectations
        """
        trace_analysis = self.analyze_trace()
        actual_sequence = trace_analysis['node_sequence']
        
        # Print sequences for debugging
        print(f"Expected: {expected_sequence}")
        print(f"Actual:   {actual_sequence}")
        
        # Verify sequence
        for i, node in enumerate(expected_sequence):
            if i >= len(actual_sequence) or actual_sequence[i] != node:
                return False
        
        return True
    
    def verify_final_state(self, final_state: Dict[str, Any], 
                          expected_keys: List[str],
                          unexpected_keys: Optional[List[str]] = None) -> bool:
        """Verify that the final state contains expected keys and values.
        
        Args:
            final_state: The final state to verify
            expected_keys: Keys that must be present
            unexpected_keys: Keys that must not be present
            
        Returns:
            True if the state meets expectations
        """
        # Check required keys
        for key in expected_keys:
            if key not in final_state:
                print(f"Missing expected key: {key}")
                return False
        
        # Check excluded keys
        if unexpected_keys:
            for key in unexpected_keys:
                if key in final_state:
                    print(f"Found unexpected key: {key}")
                    return False
        
        return True
    
    def dump_trace_to_file(self, filename: str) -> None:
        """Dump the trace history to a file for analysis.
        
        Args:
            filename: The name of the file to write
        """
        if not hasattr(self, 'trace_history'):
            print("No trace history available")
            return
        
        # Create logs directory if needed
        log_dir = os.path.join(project_root, 'logs', 'test_traces')
        os.makedirs(log_dir, exist_ok=True)
        
        # Write to file
        file_path = os.path.join(log_dir, filename)
        with open(file_path, 'w') as f:
            json.dump(self.trace_history, f, indent=2, default=str)
        
        print(f"Trace dumped to {file_path}")


class TestCompiledGraphBasic(CompiledGraphTestHarness):
    """Basic tests for the compiled graph execution."""
    
    def test_graph_creation(self):
        """Test that the graph can be created successfully."""
        kfm_app, components = self.create_test_graph()
        
        # Verify graph and components
        self.assertIsNotNone(kfm_app)
        self.assertIsNotNone(components)
        self.assertIn('registry', components)
        self.assertIn('monitor', components)
        self.assertIn('planner', components)
        self.assertIn('engine', components)
    
    def test_basic_execution(self):
        """Test basic execution of the graph."""
        # Execute graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection
            mock_llm_call.return_value = "Reflection on keep decision for component_a"
            
            # Execute the graph
            final_state = self.execute_graph()
            
            # Verify execution completed
            self.assertIsNotNone(final_state)
            
            # Check if error is either not present or is None
            if 'error' in final_state:
                self.assertIsNone(final_state['error'], f"Expected no error, got: {final_state['error']}")
            
            # Verify state contains expected fields that should always be present
            expected_keys = [
                'input', 'task_name', 'performance_data', 'task_requirements',
                'active_component', 'result', 'execution_performance'
            ]
            
            # Verify validation_results if present
            if 'validation_results' in final_state:
                expected_keys.append('validation_results')
            
            # If reflections are present, check for them as well
            if 'reflections' in final_state:
                expected_keys.append('reflections')
            
            self.assertTrue(self.verify_final_state(final_state, expected_keys))
            
            # Verify execution sequence contains the necessary node implementations
            # Note: these are the function names, not the node names in the graph
            expected_sequence = ['monitor_state_node', 'kfm_decision_node', 'execute_action_node'] 
            self.assertTrue(self.verify_node_execution_sequence(expected_sequence))
            
            # Mock reflection should be called if kfm_action is set
            if final_state.get('kfm_action') is not None:
                mock_llm_call.assert_called_once()
                # If KFM action is set, verify it matches what we expect
                self.assertEqual(final_state.get('kfm_action', {}).get('action'), 'keep')


if __name__ == '__main__':
    unittest.main() 