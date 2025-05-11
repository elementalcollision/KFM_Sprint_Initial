"""
Unit tests for rich visualization cursor commands.
"""

import unittest
import json
import os
import sys
import networkx as nx
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.cursor_commands
from src.cursor_commands import (
    command_inspect_rich_state,
    command_search_rich_states,
    command_visualize_rich_graph,
    command_diff_rich_states,
    command_execution_replay,
    command_show_rich_timeline,
    handle_command
)

class TestRichCursorCommands(unittest.TestCase):
    """Tests for rich visualization cursor commands"""
    
    def setUp(self):
        """Set up test environment"""
        # Sample state
        self.sample_state = {
            "user": {
                "name": "Test User",
                "id": 123
            },
            "items": [1, 2, 3, 4, 5],
            "status": "active"
        }
        
        # Sample graph
        self.sample_graph = nx.DiGraph()
        self.sample_graph.add_node("start")
        self.sample_graph.add_node("process")
        self.sample_graph.add_node("end")
        self.sample_graph.add_edge("start", "process")
        self.sample_graph.add_edge("process", "end")
        
        # Sample execution history
        self.sample_history = [
            {
                "node_name": "start",
                "timestamp": "2024-06-05T10:00:00",
                "state": {"step": 1, "value": "initial"},
                "success": True,
                "duration": 0.1
            },
            {
                "node_name": "process",
                "timestamp": "2024-06-05T10:01:00",
                "state": {"step": 2, "value": "processing"},
                "success": True,
                "duration": 0.2
            },
            {
                "node_name": "end",
                "timestamp": "2024-06-05T10:02:00",
                "state": {"step": 3, "value": "complete"},
                "success": True,
                "duration": 0.1
            }
        ]
        
        # Set up global state
        src.cursor_commands.current_state = self.sample_state
        src.cursor_commands.current_graph = self.sample_graph
        src.cursor_commands.current_execution_history = self.sample_history
    
    def test_inspect_rich_state(self):
        """Test rich state inspection command"""
        # Test default format
        result = command_inspect_rich_state()
        self.assertIn("user", result)
        self.assertIn("Test User", result)
        
        # Test specific field
        result = command_inspect_rich_state(field="user.name")
        self.assertIn("Test User", result)
        self.assertNotIn("items", result)
        
        # Test different formats
        result = command_inspect_rich_state(format="json")
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))
        
        result = command_inspect_rich_state(format="table")
        self.assertIn("Key", result)
        self.assertIn("Value", result)
        
        # Test with no state
        src.cursor_commands.current_state = None
        result = command_inspect_rich_state()
        self.assertIn("No current state available", result)
        
        # Restore state
        src.cursor_commands.current_state = self.sample_state
    
    @patch('src.cursor_commands.find_states_with_value')
    def test_search_rich_states(self, mock_find):
        """Test rich search command"""
        # Mock search results
        mock_find.return_value = [
            {
                "node_name": "process",
                "index": 1,
                "timestamp": "2024-06-05T10:01:00",
                "state": {"step": 2, "value": "found_match"}
            }
        ]
        
        # Test basic search
        result = command_search_rich_states(term="match")
        self.assertIn("Found 1 states", result)
        self.assertIn("process", result)
        
        # Test with field
        result = command_search_rich_states(term="match", field="value")
        self.assertIn("in field 'value'", result)
        
        # Test with no results
        mock_find.return_value = []
        result = command_search_rich_states(term="nomatch")
        self.assertIn("No states found", result)
        
        # Test without term
        result = command_search_rich_states()
        self.assertIn("Error: Search term is required", result)
    
    @patch('src.cursor_commands.create_rich_graph_visualization')
    def test_visualize_rich_graph(self, mock_visualize):
        """Test rich graph visualization command"""
        # Mock visualization result
        mock_visualize.return_value = "Visualization created: test.png"
        
        # Test basic visualization
        result = command_visualize_rich_graph()
        self.assertEqual(result, "Visualization created: test.png")
        mock_visualize.assert_called_with(
            graph=self.sample_graph,
            visualization_type="basic",
            execution_path=["start", "process", "end"],
            node_timings={'start': 0.1, 'process': 0.2, 'end': 0.1},
            focus_node=None,
            interactive=False,
            output_path=None,
            title="Rich Graph Visualization (Basic)"
        )
        
        # Test with different options
        result = command_visualize_rich_graph(
            type="execution", 
            interactive=True, 
            focus="process"
        )
        self.assertEqual(result, "Visualization created: test.png")
        mock_visualize.assert_called_with(
            graph=self.sample_graph,
            visualization_type="execution",
            execution_path=["start", "process", "end"],
            node_timings={'start': 0.1, 'process': 0.2, 'end': 0.1},
            focus_node="process",
            interactive=True,
            output_path=None,
            title="Rich Graph Visualization (Execution)"
        )
        
        # Test with no graph
        src.cursor_commands.current_graph = None
        result = command_visualize_rich_graph()
        self.assertIn("No graph available", result)
        
        # Restore graph
        src.cursor_commands.current_graph = self.sample_graph
    
    @patch('src.cursor_commands.create_rich_diff_visualization')
    def test_diff_rich_states(self, mock_diff):
        """Test rich diff visualization command"""
        # Mock diff result
        mock_diff.return_value = "Diff Visualization Result"
        
        # Test diff command
        result = command_diff_rich_states(state1=0, state2=1)
        self.assertEqual(result, "Diff Visualization Result")
        
        # Test with invalid states
        result = command_diff_rich_states(state1=None, state2=1)
        self.assertIn("Error: Both state1 and state2 are required", result)
        
        result = command_diff_rich_states(state1=0, state2=999)
        self.assertIn("not found", result)
    
    @patch('src.cursor_commands.create_execution_replay_visualization')
    def test_execution_replay(self, mock_replay):
        """Test execution replay command"""
        # Mock replay result
        mock_replay.return_value = "Replay Visualization Result"
        
        # Test replay command
        result = command_execution_replay()
        self.assertEqual(result, "Replay Visualization Result")
        mock_replay.assert_called_with(
            execution_history=self.sample_history,
            current_index=0,
            graph=self.sample_graph,
            display_state=True,
            format="text"
        )
        
        # Test with specific options
        result = command_execution_replay(step=1, show_state=False, format="graphical")
        self.assertEqual(result, "Replay Visualization Result")
        mock_replay.assert_called_with(
            execution_history=self.sample_history,
            current_index=1,
            graph=self.sample_graph,
            display_state=False,
            format="graphical"
        )
        
        # Test with no history
        src.cursor_commands.current_execution_history = []
        result = command_execution_replay()
        self.assertIn("No execution history available", result)
        
        # Restore history
        src.cursor_commands.current_execution_history = self.sample_history
    
    @patch('src.cursor_commands.show_execution_timeline')
    def test_show_rich_timeline(self, mock_timeline):
        """Test rich timeline command"""
        # Mock timeline result
        mock_timeline.return_value = "Basic Timeline"
        
        # Test timeline command
        result = command_show_rich_timeline()
        self.assertIn("Basic Timeline", result)
        
        # Test with detailed format
        result = command_show_rich_timeline(format="detailed")
        self.assertIn("Basic Timeline", result)
        self.assertIn("State Transitions", result)
        
        # Test with no history
        src.cursor_commands.current_execution_history = []
        result = command_show_rich_timeline()
        self.assertIn("No execution history available", result)
        
        # Restore history
        src.cursor_commands.current_execution_history = self.sample_history
    
    @patch('src.cursor_commands.command_inspect_rich_state')
    def test_command_handler_for_rich_commands(self, mock_inspect):
        """Test that the command handler properly routes rich commands"""
        # Mock command result with the exact text that will be returned
        mock_inspect.return_value = "Key    | Value\n------+-------------------------------------------------------------------------\nuser   | <dict with 2 keys>\nitems  | <list with 5 items>\nstatus | \"active\""
        
        # Test handling command
        result = handle_command("/lg inspect-rich --format table")
        # Just check that the result is passed through correctly
        self.assertEqual(result, mock_inspect.return_value)
        mock_inspect.assert_called_with(format="table")

if __name__ == '__main__':
    unittest.main() 