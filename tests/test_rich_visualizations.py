"""
Unit tests for rich visualization helpers.
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

from src.rich_visualizations import (
    format_rich_state,
    format_field_path,
    create_rich_graph_visualization,
    create_rich_diff_visualization,
    create_execution_replay_visualization
)

class TestRichVisualizations(unittest.TestCase):
    """Tests for rich visualization helpers"""
    
    def test_format_rich_state(self):
        """Test formatting state in different ways"""
        test_state = {
            "user": {
                "name": "Test User",
                "id": 123
            },
            "items": [1, 2, 3, 4, 5],
            "status": "active"
        }
        
        # Test different formats
        pretty_output = format_rich_state(test_state, format_type='pretty')
        self.assertIn("user", pretty_output)
        self.assertIn("Test User", pretty_output)
        
        json_output = format_rich_state(test_state, format_type='json')
        parsed = json.loads(json_output)
        self.assertEqual(parsed["user"]["name"], "Test User")
        
        table_output = format_rich_state(test_state, format_type='table')
        self.assertIn("Key", table_output)
        self.assertIn("Value", table_output)
        
        compact_output = format_rich_state(test_state, format_type='compact')
        self.assertIn("user", compact_output)
        self.assertIn("items", compact_output)
    
    def test_format_field_path(self):
        """Test formatting specific fields"""
        test_state = {
            "user": {
                "name": "Test User",
                "id": 123,
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "items": [1, 2, 3, 4, 5],
            "nested": {
                "level1": {
                    "level2": {
                        "level3": "deep value"
                    }
                }
            }
        }
        
        # Test various field paths
        simple_field = format_field_path(test_state, "user.name")
        self.assertIn("Test User", simple_field)
        
        nested_field = format_field_path(test_state, "nested.level1.level2.level3")
        self.assertIn("deep value", nested_field)
        
        list_field = format_field_path(test_state, "items")
        self.assertIn("1", list_field)
        self.assertIn("5", list_field)
        
        # Test nonexistent field
        nonexistent = format_field_path(test_state, "nonexistent.field")
        self.assertIn("not found", nonexistent)
    
    @patch('src.visualization.save_visualization')
    def test_create_rich_graph_visualization(self, mock_save):
        """Test creating different graph visualizations"""
        # Setup mocks
        mock_save.return_value = "graph_test.png"
        
        # Create a simple test graph
        G = nx.DiGraph()
        G.add_node("start")
        G.add_node("process")
        G.add_node("end")
        G.add_edge("start", "process")
        G.add_edge("process", "end")
        
        # Test basic visualization
        basic_result = create_rich_graph_visualization(
            G, 
            visualization_type='basic', 
            output_path='test_basic.png'
        )
        self.assertIn("Visualization saved", basic_result)
        
        # Test execution visualization
        exec_result = create_rich_graph_visualization(
            G, 
            visualization_type='execution',
            execution_path=["start", "process"],
            output_path='test_exec.png'
        )
        self.assertIn("Visualization saved", exec_result)
        
        # Test focus visualization
        focus_result = create_rich_graph_visualization(
            G, 
            visualization_type='focus',
            focus_node="process",
            output_path='test_focus.png'
        )
        self.assertIn("Visualization saved", focus_result)
        
        # Test fallback when graph extraction fails
        # Our implementation actually handles broken graphs by creating a minimal graph
        # So we expect a saved visualization, not an ASCII representation
        broken_graph = MagicMock()
        broken_graph.nodes = ["node1", "node2"]
        broken_result = create_rich_graph_visualization(
            broken_graph, 
            visualization_type='basic'
        )
        self.assertIn("Visualization saved", broken_result)
    
    def test_create_rich_diff_visualization(self):
        """Test creating difference visualizations"""
        # Create two sample states with differences
        state1 = {
            "name": "Original",
            "count": 5,
            "active": True,
            "items": [1, 2, 3]
        }
        
        state2 = {
            "name": "Modified",
            "count": 7,
            "active": True,
            "items": [1, 2, 3, 4],
            "new_field": "added"
        }
        
        # Test color diff
        color_diff = create_rich_diff_visualization(
            state1, state2, format='color'
        )
        self.assertIn("Modified", color_diff)
        
        # Test table diff
        table_diff = create_rich_diff_visualization(
            state1, state2, format='table'
        )
        self.assertIn("Path", table_diff)
        self.assertIn("Change", table_diff)
        
        # Test side-by-side diff
        side_diff = create_rich_diff_visualization(
            state1, state2, format='side-by-side',
            labels=('Original', 'Changed')
        )
        self.assertIn("Original", side_diff)
        self.assertIn("Changed", side_diff)
    
    def test_execution_replay_visualization(self):
        """Test creating execution replay visualization"""
        # Create test execution history
        history = [
            {
                "node_name": "start",
                "timestamp": "2024-06-05T10:00:00",
                "state": {"step": 1, "value": "initial"},
                "success": True
            },
            {
                "node_name": "process",
                "timestamp": "2024-06-05T10:01:00",
                "state": {"step": 2, "value": "processing"},
                "success": True
            },
            {
                "node_name": "validate",
                "timestamp": "2024-06-05T10:02:00",
                "state": {"step": 3, "value": "validating"},
                "success": True
            },
            {
                "node_name": "end",
                "timestamp": "2024-06-05T10:03:00",
                "state": {"step": 4, "value": "complete"},
                "success": True
            }
        ]
        
        # Create a simple graph for visualization
        G = nx.DiGraph()
        for entry in history:
            G.add_node(entry["node_name"])
        
        for i in range(len(history) - 1):
            G.add_edge(history[i]["node_name"], history[i+1]["node_name"])
        
        # Test replay at different steps
        for step in range(len(history)):
            replay_result = create_execution_replay_visualization(
                history,
                current_index=step,
                graph=G,
                display_state=True
            )
            self.assertIn(f"({step + 1}/{len(history)})", replay_result)
            self.assertIn(history[step]["node_name"], replay_result)
        
        # Test without state display
        no_state_result = create_execution_replay_visualization(
            history,
            current_index=1,
            display_state=False
        )
        self.assertIn("process", no_state_result)
        self.assertNotIn("processing", no_state_result)
        
        # Test with graphical format
        graphical_result = create_execution_replay_visualization(
            history,
            current_index=2,
            graph=G,
            format="graphical"
        )
        self.assertIn("validate", graphical_result)
        self.assertIn("Graph visualization", graphical_result)

if __name__ == '__main__':
    unittest.main() 