import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.debugging import (
    debug_node_execution, 
    diff_states, 
    wrap_node_for_debug, 
    debug_graph_execution
)


class TestDebugUtilities(unittest.TestCase):
    """Test cases for the debugging utilities."""
    
    def test_diff_states(self):
        """Test the diff_states function."""
        # Test states with different values
        state1 = {"a": 1, "b": 2, "c": 3}
        state2 = {"a": 1, "b": 4, "d": 5}
        
        changes = diff_states(state1, state2)
        
        # Check that b was changed
        self.assertIn("b", changes)
        self.assertEqual(changes["b"]["before"], 2)
        self.assertEqual(changes["b"]["after"], 4)
        
        # Check that c was removed
        self.assertIn("c", changes)
        self.assertEqual(changes["c"]["before"], 3)
        self.assertEqual(changes["c"]["after"], None)
        
        # Check that d was added
        self.assertIn("d", changes)
        self.assertEqual(changes["d"]["before"], None)
        self.assertEqual(changes["d"]["after"], 5)
        
        # Check that a is not in changes (unchanged)
        self.assertNotIn("a", changes)
    
    @patch('src.debugging.debug_logger')
    def test_debug_node_execution(self, mock_logger):
        """Test the debug_node_execution function."""
        node_name = "test_node"
        state_before = {"a": 1, "b": 2}
        state_after = {"a": 1, "b": 3}
        
        debug_node_execution(node_name, state_before, state_after)
        
        # Verify logging calls
        mock_logger.info.assert_any_call(f"\n--- DEBUG: {node_name} ---")
        # Check that we log the changes
        for call_args in mock_logger.info.call_args_list:
            args, _ = call_args
            if "Changes:" in args[0]:
                self.assertIn('"b"', args[0])
    
    @patch('src.debugging.debug_logger')
    def test_wrap_node_for_debug(self, mock_logger):
        """Test the wrap_node_for_debug function."""
        # Create a mock node function
        def mock_node(state):
            state["processed"] = True
            return state
        
        # Wrap it with debug wrapper
        wrapped_node = wrap_node_for_debug(mock_node, "test_node")
        
        # Execute the wrapped node
        state = {"input": "test"}
        result = wrapped_node(state)
        
        # Verify the node function was called
        self.assertTrue(result["processed"])
        
        # Verify logging calls
        mock_logger.info.assert_any_call("Entering node: test_node")
    
    @patch('src.debugging.debug_logger')
    def test_wrap_node_for_debug_exception(self, mock_logger):
        """Test the wrap_node_for_debug function with an exception."""
        # Create a mock node function that raises an exception
        def mock_node(state):
            raise ValueError("Test error")
        
        # Wrap it with debug wrapper
        wrapped_node = wrap_node_for_debug(mock_node, "error_node")
        
        # Execute the wrapped node and verify it re-raises the exception
        with self.assertRaises(ValueError):
            wrapped_node({"input": "test"})
        
        # Verify error logging
        mock_logger.error.assert_called_with("Error in node error_node: Test error")
    
    @patch('src.debugging.debug_logger')
    def test_debug_graph_execution(self, mock_logger):
        """Test the debug_graph_execution function."""
        # Create a mock graph
        mock_app = MagicMock()
        mock_app.invoke.return_value = {"result": "success", "done": True}
        
        # Execute with debug
        initial_state = {"input": "test"}
        result = debug_graph_execution(mock_app, initial_state)
        
        # Verify the graph was invoked
        mock_app.invoke.assert_called_once_with(initial_state)
        
        # Verify result
        self.assertEqual(result["result"], "success")
        
        # Verify logging calls
        mock_logger.info.assert_any_call("Starting debug graph execution")
        mock_logger.info.assert_any_call("Graph execution completed successfully")
    
    @patch('src.debugging.debug_logger')
    def test_debug_graph_execution_error(self, mock_logger):
        """Test the debug_graph_execution function with an error."""
        # Create a mock graph that raises an exception
        mock_app = MagicMock()
        mock_app.invoke.side_effect = ValueError("Test graph error")
        
        # Execute with debug
        initial_state = {"input": "test"}
        result = debug_graph_execution(mock_app, initial_state)
        
        # Verify result is None
        self.assertIsNone(result)
        
        # Verify error logging
        mock_logger.error.assert_called_with("Error during graph execution: Test graph error")


if __name__ == '__main__':
    unittest.main() 