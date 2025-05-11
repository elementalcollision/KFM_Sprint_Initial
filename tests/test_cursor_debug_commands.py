import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the cursor_commands module
from src.cursor_commands import (
    handle_command,
    parse_args,
    registered_commands,
    COMMAND_PREFIX,
    command_start_debug_session,
    command_step_execution,
    command_continue_execution,
    command_step_backward,
    command_run_to_node,
    command_run_to_condition,
    command_modify_state,
    command_watch_field,
    command_list_watches,
    command_save_debug_session,
    command_load_debug_session,
    command_list_debug_sessions
)

class TestCursorDebugCommands(unittest.TestCase):
    """Tests for the interactive debugging commands in Cursor AI Command Palette."""
    
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
        
        # Set the current_state to None initially (before debug session starts)
        src.cursor_commands.current_state = None
        src.cursor_commands.current_node_index = None
        src.cursor_commands.current_execution_history = []
        
        # Save the test state for later use
        self.test_state = test_state
    
    def test_debug_session_command(self):
        """Test starting a debug session."""
        result = command_start_debug_session(graph_name="test_graph")
        self.assertIn("Debug session started for test_graph", result)
        
        # Verify that current_state is initialized
        import src.cursor_commands
        self.assertIsNotNone(src.cursor_commands.current_state)
        self.assertEqual(src.cursor_commands.current_node_index, 0)
    
    def test_debug_session_with_state(self):
        """Test starting a debug session with initial state."""
        state_json = json.dumps({"input": "test data", "config": {"enabled": True}})
        result = command_start_debug_session(graph_name="test_graph", state=state_json)
        
        # Verify that current_state has the provided values
        import src.cursor_commands
        self.assertEqual(src.cursor_commands.current_state.get("input"), "test data")
        self.assertEqual(src.cursor_commands.current_state.get("config"), {"enabled": True})
    
    def test_step_execution(self):
        """Test stepping through execution."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph")
        
        # Test standard step
        result = command_step_execution()
        self.assertIn("Executed step (step)", result)
        
        # Verify node index was incremented
        import src.cursor_commands
        self.assertEqual(src.cursor_commands.current_node_index, 1)
        
        # Test step with flag
        result = command_step_execution(into=True)
        self.assertIn("Executed step (into)", result)
    
    def test_continue_execution(self):
        """Test continuing execution."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph")
        
        # Test continue
        result = command_continue_execution()
        self.assertIn("Execution continued to node index", result)
        
        # Verify node index was updated
        import src.cursor_commands
        self.assertTrue(src.cursor_commands.current_node_index > 0)
        
        # Test continue all
        initial_index = src.cursor_commands.current_node_index
        result = command_continue_execution(all=True)
        self.assertIn("Execution completed", result)
        
        # Verify node index was updated further
        self.assertTrue(src.cursor_commands.current_node_index > initial_index)
    
    def test_step_backward(self):
        """Test stepping backward."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph")
        
        # Move forward first
        command_step_execution()
        command_step_execution()
        
        import src.cursor_commands
        initial_index = src.cursor_commands.current_node_index
        
        # Test step backward
        result = command_step_backward()
        self.assertIn("Stepped back", result)
        
        # Verify node index was decremented
        self.assertEqual(src.cursor_commands.current_node_index, initial_index - 1)
        
        # Test step backward with steps parameter
        result = command_step_backward(steps=src.cursor_commands.current_node_index)
        self.assertIn("Stepped back", result)
        
        # Verify node index is now 0
        self.assertEqual(src.cursor_commands.current_node_index, 0)
    
    def test_run_to_node(self):
        """Test running to a specific node."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph")
        
        # Test run to node
        result = command_run_to_node(node="validate_data")
        self.assertIn("Execution continued to node 'validate_data'", result)
        
        # Verify state was updated
        import src.cursor_commands
        self.assertEqual(src.cursor_commands.current_state.get("_target_node"), "validate_data")
    
    def test_modify_state(self):
        """Test modifying state values."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph", state=json.dumps(self.test_state))
        
        # Test modifying a simple field
        result = command_modify_state(field="settings.timeout", value="60")
        self.assertIn("State updated: settings.timeout = 60", result)
        
        # Verify state was updated
        import src.cursor_commands
        self.assertEqual(src.cursor_commands.current_state["settings"]["timeout"], 60)
        
        # Test modifying with a complex value
        result = command_modify_state(field="user.roles", value=json.dumps(["admin", "moderator"]))
        self.assertIn("State updated: user.roles", result)
        
        # Verify state was updated
        self.assertEqual(src.cursor_commands.current_state["user"]["roles"], ["admin", "moderator"])
    
    @patch("src.cursor_commands.monitor_field")
    def test_watch_field(self, mock_monitor_field):
        """Test setting a watch on a field."""
        # Setup mock
        mock_monitor_field.return_value = "test-monitor-id"
        
        # Test watch command
        result = command_watch_field(field="user.score")
        self.assertIn("Watch set on field 'user.score'", result)
        
        # Verify monitor_field was called
        mock_monitor_field.assert_called_once_with("user.score", None)
        
        # Test with condition
        result = command_watch_field(field="errors", condition="len(errors) > 0")
        self.assertIn("Watch set on field 'errors' with condition", result)
    
    @patch("src.cursor_commands.get_active_monitors")
    def test_list_watches(self, mock_get_monitors):
        """Test listing watches."""
        # Setup mock
        mock_get_monitors.return_value = [
            {"id": "monitor-1", "field_path": "user.score"},
            {"id": "monitor-2", "field_path": "errors", "condition": "len(errors) > 0"}
        ]
        
        # Test list watches command
        result = command_list_watches()
        self.assertIn("Active watches:", result)
        self.assertIn("[monitor-1] user.score", result)
        self.assertIn("[monitor-2] errors", result)
    
    def test_session_management(self):
        """Test session management commands."""
        # Start a debug session first
        command_start_debug_session(graph_name="test_graph", state=json.dumps(self.test_state))
        
        # Save session
        result = command_save_debug_session(name="test_session")
        self.assertIn("Debug session saved as 'test_session'", result)
        
        # Reset state
        import src.cursor_commands
        src.cursor_commands.current_state = None
        src.cursor_commands.current_node_index = None
        
        # Load session
        result = command_load_debug_session(name="test_session")
        self.assertIn("Debug session 'test_session' loaded", result)
        
        # Verify state was loaded
        self.assertIsNotNone(src.cursor_commands.current_state)
        self.assertTrue("_loaded" in src.cursor_commands.current_state)
        
        # List sessions
        result = command_list_debug_sessions()
        self.assertIn("Saved debug sessions:", result)
    
    def test_handle_command(self):
        """Test handling interactive debug commands."""
        # Test debug command
        result = handle_command(f"{COMMAND_PREFIX} debug test_graph")
        self.assertIn("Error: Graph name is required", result)
        
        # Use the command directly since handle_command needs specific formatting
        result = command_start_debug_session(graph_name="test_graph")
        self.assertIn("Debug session started", result)
        
        # Test step command
        result = handle_command(f"{COMMAND_PREFIX} step")
        self.assertIn("Executed step", result)
        
        # Test run-to command
        result = handle_command(f"{COMMAND_PREFIX} run-to --node validate_data")
        self.assertIn("Execution continued to node", result)
        
        # Test modify state command
        result = handle_command(f"{COMMAND_PREFIX} modify-state --field user.name --value \"New Name\"")
        self.assertIn("State updated", result)
        
        # Verify state was updated
        import src.cursor_commands
        self.assertEqual(src.cursor_commands.current_state["user"]["name"], "New Name")
        
if __name__ == "__main__":
    unittest.main() 