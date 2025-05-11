import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any
import networkx as nx
import matplotlib.pyplot as plt

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the cursor_commands module
from src.cursor_commands import (
    handle_command,
    parse_args,
    registered_commands,
    COMMAND_PREFIX,
    command_set_breakpoint,
    command_list_breakpoints,
    command_clear_breakpoint,
    command_inspect_state,
    command_diff_states,
    command_visualize_graph
)

class TestCursorCommands(unittest.TestCase):
    """Tests for the Cursor AI Command Palette Integration."""
    
    def setUp(self):
        """Setup before each test."""
        # Reset any breakpoints from previous tests
        from src.debugging import clear_all_breakpoints
        clear_all_breakpoints()
        
        # Mock current state for testing
        import src.cursor_commands
        
        # Create a basic test state
        test_state = {
            "user": {
                "name": "Test User",
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "messages": [
                {"id": 1, "text": "Hello"},
                {"id": 2, "text": "World"}
            ],
            "settings": {
                "api_key": "test-key",
                "timeout": 30
            }
        }
        
        # Set the current_state for testing
        src.cursor_commands.current_state = test_state
        
        # Create a mock graph for visualization tests
        mock_graph = MagicMock()
        mock_graph.nodes = ["start", "process", "validate", "end"]
        src.cursor_commands.current_graph = mock_graph
        
        # Create mock execution history
        src.cursor_commands.current_execution_history = [
            {"node_name": "start", "state": {"step": 1}},
            {"node_name": "process", "state": {"step": 2}}
        ]
    
    def tearDown(self):
        """Cleanup after each test."""
        # Reset the state
        import src.cursor_commands
        src.cursor_commands.current_state = None
        src.cursor_commands.current_graph = None
        src.cursor_commands.current_execution_history = []
        
        # Clean up any breakpoints
        from src.debugging import clear_all_breakpoints
        clear_all_breakpoints()
    
    def test_parse_args(self):
        """Test argument parsing logic."""
        # Test basic arguments
        args = parse_args("--name value --flag")
        self.assertEqual(args["name"], "value")
        self.assertTrue(args["flag"])
        
        # Test quoted arguments
        args = parse_args('--message "This is a test" --path /some/path')
        self.assertEqual(args["message"], "This is a test")
        self.assertEqual(args["path"], "/some/path")
        
        # Test short forms
        args = parse_args("-n value -f")
        self.assertEqual(args["n"], "value")
        self.assertTrue(args["f"])
        
        # Test equals format
        args = parse_args('--key="test-value" --path=/some/path')
        self.assertEqual(args["key"], "test-value")
        self.assertEqual(args["path"], "/some/path")
        
        # Test positional arguments
        args = parse_args("positional1 positional2 --flag")
        self.assertTrue("_positional" in args)
        self.assertEqual(args["_positional"], ["positional1", "positional2"])
        self.assertTrue(args["flag"])
    
    @patch('src.cursor_commands._handle_help_command')
    def test_help_command(self, mock_help):
        """Test the help command handling."""
        # Set up mock return value
        mock_help.return_value = "Mock help text"
        
        # Test general help
        result = handle_command(f"{COMMAND_PREFIX} help")
        mock_help.assert_called_with("")
        self.assertEqual(result, "Mock help text")
        
        # Test specific command help
        result = handle_command(f"{COMMAND_PREFIX} help breakpoint")
        mock_help.assert_called_with("breakpoint")
        self.assertEqual(result, "Mock help text")
    
    def test_breakpoint_command(self):
        """Test the breakpoint command."""
        # Use an actual isolated test for this function
        # instead of mocking to validate the integration
        
        # Test with node parameter
        result = command_set_breakpoint(node="test_node")
        self.assertIn("test_node", result)
        self.assertIn("Breakpoint set", result)
        
        # Test with condition
        result = command_set_breakpoint(node="test_node2", condition="state['error'] != None")
        self.assertIn("test_node2", result)
        self.assertIn("Breakpoint set", result)
        
        # Test missing node parameter
        result = command_set_breakpoint()
        self.assertIn("Error", result)
        self.assertIn("required", result)
    
    def test_list_breakpoints_command(self):
        """Test the list breakpoints command."""
        # First test with no breakpoints
        # Clear any existing breakpoints
        from src.debugging import clear_all_breakpoints
        clear_all_breakpoints()
        
        result = command_list_breakpoints()
        self.assertIn("No breakpoints", result)
        
        # Now add a breakpoint and test again
        command_set_breakpoint(node="test_node")
        
        result = command_list_breakpoints()
        self.assertIn("test_node", result)
        self.assertIn("enabled", result)
        
        # Add another breakpoint with a condition
        command_set_breakpoint(node="test_node2", condition="state['error'] != None")
        
        result = command_list_breakpoints()
        self.assertIn("test_node", result)
        self.assertIn("test_node2", result)
        self.assertIn("state['error'] != None", result)
    
    def test_inspect_command(self):
        """Test the state inspection command."""
        # Test basic inspection
        result = command_inspect_state()
        self.assertIn("Current State", result)
        self.assertIn("user", result)
        self.assertIn("messages", result)
        self.assertIn("settings", result)
        
        # Test field access
        result = command_inspect_state(field="user.name")
        self.assertEqual(result, "Test User")
        
        # Test JSON format
        result = command_inspect_state(format="json")
        # Validate it's proper JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["user"]["name"], "Test User")
        
        # Test field not found
        result = command_inspect_state(field="nonexistent.field")
        self.assertIn("not found", result)
    
    @patch('src.visualization.extract_graph_structure')
    @patch('src.visualization.save_visualization')
    def test_visualize_command(self, mock_save, mock_extract):
        """Test the visualization command."""
        import matplotlib.pyplot as plt
        from src.cursor_commands import command_visualize_graph
        
        # Set up mocks
        mock_fig = plt.figure()
        mock_save.return_value = "graph_basic.png"
        
        # First test the fallback path (extraction failure)
        mock_extract.side_effect = Exception("Test error")
        
        # Test basic visualization with extraction failure
        result = command_visualize_graph(type="basic")
        
        # Verify visualization was still created and saved
        mock_save.assert_called_once()
        self.assertIn("saved to", result)
        
        # Reset mocks
        mock_save.reset_mock()
        mock_extract.reset_mock()
        
        # Now test the successful path
        mock_extract.side_effect = None
        mock_extract.return_value = nx.DiGraph()
        
        # Test with custom output
        result = command_visualize_graph(type="basic", output="custom_output.png")
        mock_extract.assert_called_once()
        mock_save.assert_called_once()
        self.assertIn("saved to", result)
        self.assertIn("custom_output.png", result)
    
    def test_command_registration(self):
        """Test that commands are properly registered."""
        # Check that essential commands are registered
        required_commands = [
            f"{COMMAND_PREFIX}_breakpoint",
            f"{COMMAND_PREFIX}_breakpoints",
            f"{COMMAND_PREFIX}_clear-breakpoint",
            f"{COMMAND_PREFIX}_inspect",
            f"{COMMAND_PREFIX}_visualize"
        ]
        
        for cmd in required_commands:
            self.assertIn(cmd, registered_commands)
            self.assertIsNotNone(registered_commands[cmd]["function"])
            self.assertIsNotNone(registered_commands[cmd]["description"])
            self.assertIsNotNone(registered_commands[cmd]["usage"])
    
    def test_error_handling(self):
        """Test command error handling."""
        # Test invalid command prefix
        result = handle_command("invalid command")
        self.assertIn("Invalid command", result)
        
        # Test unknown command
        result = handle_command(f"{COMMAND_PREFIX} unknown_command")
        self.assertIn("Unknown command", result)
        
        # Test command execution error
        with patch.dict(registered_commands, {
            f"{COMMAND_PREFIX}_test_error": {
                "name": "test_error",
                "full_command": f"{COMMAND_PREFIX} test_error",
                "description": "Test error handling",
                "usage": f"{COMMAND_PREFIX} test_error",
                "examples": [],
                "function": MagicMock(side_effect=Exception("Test error"))
            }
        }):
            result = handle_command(f"{COMMAND_PREFIX} test_error")
            self.assertIn("Error executing command", result)
            self.assertIn("Test error", result)

if __name__ == '__main__':
    unittest.main() 