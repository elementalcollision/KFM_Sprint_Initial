"""
Tests for the state history tracking functionality.
"""

import unittest
import json
import os
import tempfile
import shutil
import time
from typing import Dict, Any, List

from src.tracing import (
    StateHistoryTracker, 
    save_state_snapshot,
    get_state_snapshot,
    list_state_snapshots,
    search_state_history,
    get_state_timeline,
    get_state_at_point,
    reset_trace_history,
    configure_tracing
)


class TestStateHistoryTracker(unittest.TestCase):
    """Tests for the StateHistoryTracker class."""
    
    def setUp(self):
        """Set up the test case."""
        # Create a temporary directory for snapshots
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a tracker instance
        self.tracker = StateHistoryTracker(max_size=10, snapshot_dir=self.temp_dir)
        
        # Create some test states
        self.test_states = [
            {"id": 1, "name": "state1", "value": 10, "nested": {"field1": "value1"}},
            {"id": 2, "name": "state2", "value": 20, "nested": {"field1": "value2"}},
            {"id": 3, "name": "state3", "value": 30, "nested": {"field1": "value3"}},
        ]
        
        # Reset any existing tracing configuration
        reset_trace_history()
        configure_tracing(history_buffer_size=10)
    
    def tearDown(self):
        """Clean up after the test case."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_buffer_size_limit(self):
        """Test that the buffer size is limited to max_size."""
        # Create a tracker with max_size=3
        tracker = StateHistoryTracker(max_size=3)
        
        # Add 5 states
        for i in range(5):
            tracker.add_state(
                node_name=f"node{i}",
                state={"id": i, "value": i * 10},
                is_input=False
            )
        
        # Check that only the last 3 states are kept
        history = tracker.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["state"]["id"], 2)
        self.assertEqual(history[1]["state"]["id"], 3)
        self.assertEqual(history[2]["state"]["id"], 4)
    
    def test_reconfigure(self):
        """Test reconfiguring the tracker."""
        # Create a tracker with max_size=5
        tracker = StateHistoryTracker(max_size=5)
        
        # Add 5 states
        for i in range(5):
            tracker.add_state(
                node_name=f"node{i}",
                state={"id": i, "value": i * 10},
                is_input=False
            )
        
        # Check that all 5 states are kept
        self.assertEqual(len(tracker.get_history()), 5)
        
        # Reconfigure to max_size=3
        tracker.reconfigure(max_size=3)
        
        # Check that only the last 3 states are kept
        history = tracker.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["state"]["id"], 2)
        self.assertEqual(history[1]["state"]["id"], 3)
        self.assertEqual(history[2]["state"]["id"], 4)
    
    def test_add_and_get_state(self):
        """Test adding and retrieving states."""
        # Add the test states
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=i % 2 == 0,  # Alternate input/output
                metadata={"test_meta": i}
            )
        
        # Get the history
        history = self.tracker.get_history()
        
        # Check that all states were added
        self.assertEqual(len(history), len(self.test_states))
        
        # Check the state values
        for i, entry in enumerate(history):
            self.assertEqual(entry["state"], self.test_states[i])
            self.assertEqual(entry["node_name"], f"node{i}")
            self.assertEqual(entry["is_input"], i % 2 == 0)
            self.assertEqual(entry["metadata"]["test_meta"], i)
    
    def test_clear(self):
        """Test clearing the history."""
        # Add the test states
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
        
        # Check that states were added
        self.assertEqual(len(self.tracker.get_history()), len(self.test_states))
        
        # Clear the history
        self.tracker.clear()
        
        # Check that the history is empty
        self.assertEqual(len(self.tracker.get_history()), 0)
    
    def test_create_and_get_snapshot(self):
        """Test creating and retrieving snapshots."""
        # Create a snapshot
        snapshot_id = self.tracker.create_snapshot(
            state=self.test_states[0],
            label="Test Snapshot",
            category="test",
            description="Test snapshot description"
        )
        
        # Check that the snapshot file was created
        snapshot_path = os.path.join(self.temp_dir, f"{snapshot_id}.json")
        self.assertTrue(os.path.exists(snapshot_path))
        
        # Get the snapshot
        snapshot = self.tracker.get_snapshot(snapshot_id)
        
        # Check the snapshot contents
        self.assertEqual(snapshot["state"], self.test_states[0])
        self.assertEqual(snapshot["metadata"]["label"], "Test Snapshot")
        self.assertEqual(snapshot["metadata"]["category"], "test")
        self.assertEqual(snapshot["metadata"]["description"], "Test snapshot description")
    
    def test_list_snapshots(self):
        """Test listing snapshots."""
        # Create snapshots in different categories
        self.tracker.create_snapshot(
            state=self.test_states[0],
            label="Test Snapshot 1",
            category="category1",
            description="Test snapshot 1"
        )
        
        self.tracker.create_snapshot(
            state=self.test_states[1],
            label="Test Snapshot 2",
            category="category1",
            description="Test snapshot 2"
        )
        
        self.tracker.create_snapshot(
            state=self.test_states[2],
            label="Test Snapshot 3",
            category="category2",
            description="Test snapshot 3"
        )
        
        # List all snapshots
        all_snapshots = self.tracker.list_snapshots()
        self.assertEqual(len(all_snapshots), 3)
        
        # List snapshots in category1
        category1_snapshots = self.tracker.list_snapshots(category="category1")
        self.assertEqual(len(category1_snapshots), 2)
        self.assertEqual(category1_snapshots[0]["label"], "Test Snapshot 2")
        self.assertEqual(category1_snapshots[1]["label"], "Test Snapshot 1")
        
        # List snapshots in category2
        category2_snapshots = self.tracker.list_snapshots(category="category2")
        self.assertEqual(len(category2_snapshots), 1)
        self.assertEqual(category2_snapshots[0]["label"], "Test Snapshot 3")
    
    def test_search_history(self):
        """Test searching the history."""
        # Add the test states
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
        
        # Search for a string
        results = self.tracker.search_history(query="value2")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["state"]["id"], 2)
        
        # Search with case sensitivity
        results = self.tracker.search_history(query="Value2", case_sensitive=False)
        self.assertEqual(len(results), 1)
        
        results = self.tracker.search_history(query="Value2", case_sensitive=True)
        self.assertEqual(len(results), 0)
        
        # Search in a specific field
        results = self.tracker.search_history(query="value3", field_path="nested.field1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["state"]["id"], 3)
    
    def test_find_state_by_condition(self):
        """Test finding states by condition."""
        # Add the test states
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
        
        # Find states where value > 15
        results = self.tracker.find_state_by_condition(
            condition=lambda state: state["value"] > 15
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["state"]["id"], 2)
        self.assertEqual(results[1]["state"]["id"], 3)
    
    def test_get_state_at_index(self):
        """Test getting a state by index."""
        # Add the test states
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
        
        # Get the first state
        state = self.tracker.get_state_at_index(0)
        self.assertEqual(state["state"]["id"], 1)
        
        # Get the last state
        state = self.tracker.get_state_at_index(-1)
        self.assertEqual(state["state"]["id"], 3)
        
        # Get a non-existent state
        state = self.tracker.get_state_at_index(10)
        self.assertIsNone(state)
    
    def test_timeline_visualization(self):
        """Test generating a timeline visualization."""
        # Add states with timestamps spaced apart
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
            # Add a small delay between states
            time.sleep(0.01)
        
        # Generate the timeline
        timeline = self.tracker.generate_timeline_visualization(width=40)
        
        # Check that the timeline contains the node names
        self.assertIn("node0", timeline)
        self.assertIn("node1", timeline)
        self.assertIn("node2", timeline)
        
        # Generate timeline with states
        timeline_with_states = self.tracker.generate_timeline_visualization(width=40, include_states=True)
        
        # Check that the timeline includes state details
        self.assertIn("State:", timeline_with_states)
        self.assertIn("id", timeline_with_states)
        self.assertIn("value", timeline_with_states)
    
    def test_helper_functions(self):
        """Test the helper functions."""
        # Configure tracing
        configure_tracing(history_buffer_size=5)
        
        # Add some test states to the global tracker
        for i, state in enumerate(self.test_states):
            self.tracker.add_state(
                node_name=f"node{i}",
                state=state,
                is_input=False
            )
        
        # Create a snapshot
        snapshot_id = save_state_snapshot(
            state=self.test_states[0],
            label="Helper Test",
            category="helper_test"
        )
        
        # Get the snapshot
        snapshot = get_state_snapshot(snapshot_id)
        self.assertEqual(snapshot["state"], self.test_states[0])
        
        # List snapshots
        snapshots = list_state_snapshots(category="helper_test")
        self.assertEqual(len(snapshots), 1)
        
        # Search state history
        # Create a new state with a unique string to search for
        unique_state = {"id": 100, "name": "unique_state_name_for_search_test"}
        self.tracker.add_state(
            node_name="search_test",
            state=unique_state,
            is_input=False
        )
        
        results = search_state_history(query="unique_state_name_for_search_test")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["state"]["id"], 100)
        
        # Generate timeline
        timeline = get_state_timeline(width=40)
        self.assertIn("Timeline", timeline)
        
        # Get state at point
        state = get_state_at_point(-1)
        self.assertEqual(state["state"]["id"], 100)


if __name__ == '__main__':
    unittest.main() 