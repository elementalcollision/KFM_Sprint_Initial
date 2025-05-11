"""
Tests for the state field monitoring functionality.
"""

import unittest
import time
from typing import Dict, Any, List

from src.tracing import (
    StateFieldMonitor, 
    watch_field,
    remove_watch,
    clear_watches,
    list_watches,
    evaluate_watches,
    get_monitor_statistics
)

from src.debugging import (
    monitor_field,
    monitor_value_change,
    monitor_threshold,
    monitor_pattern_match,
    monitor_state_condition,
    stop_monitoring
)


class TestStateFieldMonitor(unittest.TestCase):
    """Tests for the StateFieldMonitor class."""
    
    def setUp(self):
        """Set up the test case."""
        # Create a monitor instance
        self.monitor = StateFieldMonitor()
        
        # Create some test states
        self.test_states = [
            {
                "id": 1, 
                "name": "state1", 
                "value": 10, 
                "nested": {"field1": "value1", "count": 5},
                "status": "pending"
            },
            {
                "id": 2, 
                "name": "state2", 
                "value": 20, 
                "nested": {"field1": "value2", "count": 10},
                "status": "processing"
            },
            {
                "id": 3, 
                "name": "state3", 
                "value": 30, 
                "nested": {"field1": "value3", "count": 15},
                "status": "completed"
            }
        ]
        
        # Clear all watches before each test
        clear_watches()
    
    def tearDown(self):
        """Clean up after the test case."""
        # Clear all watches after each test
        clear_watches()
    
    def test_add_and_remove_watch(self):
        """Test adding and removing watches."""
        # Add a watch
        watch_id = self.monitor.add_watch(
            field_path="value",
            expression="value > 15",
            description="Test watch",
            alert_level="WARNING"
        )
        
        # Check that the watch was added
        self.assertIn(watch_id, self.monitor.watches)
        watch = self.monitor.watches[watch_id]
        self.assertEqual(watch["field_path"], "value")
        self.assertEqual(watch["expression"], "value > 15")
        self.assertEqual(watch["description"], "Test watch")
        self.assertEqual(watch["alert_level"], "WARNING")
        
        # Remove the watch
        result = self.monitor.remove_watch(watch_id)
        self.assertTrue(result)
        self.assertNotIn(watch_id, self.monitor.watches)
        
        # Try to remove a non-existent watch
        result = self.monitor.remove_watch("non-existent")
        self.assertFalse(result)
    
    def test_enable_disable_watch(self):
        """Test enabling and disabling watches."""
        # Add a watch
        watch_id = self.monitor.add_watch(field_path="value")
        
        # Disable the watch
        result = self.monitor.disable_watch(watch_id)
        self.assertTrue(result)
        self.assertTrue(self.monitor.watches[watch_id]["disabled"])
        
        # Enable the watch
        result = self.monitor.enable_watch(watch_id)
        self.assertTrue(result)
        self.assertFalse(self.monitor.watches[watch_id]["disabled"])
        
        # Try to enable/disable a non-existent watch
        result = self.monitor.enable_watch("non-existent")
        self.assertFalse(result)
        result = self.monitor.disable_watch("non-existent")
        self.assertFalse(result)
    
    def test_get_and_list_watches(self):
        """Test getting and listing watches."""
        # Add some watches
        watch_id1 = self.monitor.add_watch(
            field_path="value", 
            alert_level="INFO"
        )
        watch_id2 = self.monitor.add_watch(
            field_path="status", 
            alert_level="WARNING"
        )
        watch_id3 = self.monitor.add_watch(
            field_path="nested.field1", 
            alert_level="ERROR"
        )
        
        # Get a watch
        watch = self.monitor.get_watch(watch_id1)
        self.assertEqual(watch["field_path"], "value")
        self.assertEqual(watch["alert_level"], "INFO")
        
        # List all watches
        watches = self.monitor.list_watches()
        self.assertEqual(len(watches), 3)
        
        # List watches by field path
        watches = self.monitor.list_watches(field_path="value")
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0]["field_path"], "value")
        
        # List watches by alert level
        watches = self.monitor.list_watches(alert_level="WARNING")
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0]["field_path"], "status")
    
    def test_evaluate_simple_change_detection(self):
        """Test evaluating watches with simple change detection."""
        # Add a watch for any change to the value field
        self.monitor.add_watch(field_path="value")
        
        # Evaluate with the first state (no previous value)
        alerts = self.monitor.evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)  # No alert on first evaluation
        
        # Evaluate with the second state (value changed)
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["field_path"], "value")
        self.assertEqual(alerts[0]["current_value"], 20)
        self.assertEqual(alerts[0]["previous_value"], 10)
        
        # Evaluate with the second state again (no change)
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 0)
    
    def test_evaluate_expression(self):
        """Test evaluating watches with expressions."""
        # Add a watch with an expression
        self.monitor.add_watch(
            field_path="value",
            expression="value > 15 and prev_value is not None"
        )
        
        # Evaluate with the first state (no previous value)
        alerts = self.monitor.evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)  # Expression is false
        
        # Evaluate with the second state (expression is true)
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 1)
        
        # Add a watch with a more complex expression
        self.monitor.add_watch(
            field_path="nested.count",
            expression="value > 10 and value > prev_value * 1.2"
        )
        
        # Evaluate with the second state (sets previous value)
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 0)  # Just setting prev_value
        
        # Evaluate with the third state (expression is true)
        alerts = self.monitor.evaluate_watches(self.test_states[2])
        self.assertEqual(len(alerts), 2)  # Both watches trigger
    
    def test_nested_fields(self):
        """Test evaluating watches on nested fields."""
        # Add a watch for a nested field
        self.monitor.add_watch(field_path="nested.field1")
        
        # Evaluate with the first state (no previous value)
        alerts = self.monitor.evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)
        
        # Evaluate with the second state (nested value changed)
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["field_path"], "nested.field1")
        self.assertEqual(alerts[0]["current_value"], "value2")
        self.assertEqual(alerts[0]["previous_value"], "value1")
    
    def test_alert_levels(self):
        """Test different alert levels."""
        # Add watches with different alert levels
        self.monitor.add_watch(
            field_path="value",
            alert_level="INFO"
        )
        self.monitor.add_watch(
            field_path="status",
            alert_level="WARNING"
        )
        self.monitor.add_watch(
            field_path="nested.count",
            alert_level="ERROR"
        )
        
        # First evaluation to set previous values
        self.monitor.evaluate_watches(self.test_states[0])
        
        # Second evaluation to trigger alerts
        alerts = self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 3)
        
        # Check alert levels
        alert_levels = [alert["alert_level"] for alert in alerts]
        self.assertIn("INFO", alert_levels)
        self.assertIn("WARNING", alert_levels)
        self.assertIn("ERROR", alert_levels)
        
        # Check statistics
        stats = self.monitor.get_statistics()
        self.assertEqual(stats["by_level"]["INFO"], 1)
        self.assertEqual(stats["by_level"]["WARNING"], 1)
        self.assertEqual(stats["by_level"]["ERROR"], 1)
    
    def test_callback_function(self):
        """Test watch callback function."""
        # Create a callback function to count alerts
        self.callback_count = 0
        self.last_alert = None
        
        def test_callback(alert):
            self.callback_count += 1
            self.last_alert = alert
        
        # Add a watch with a callback
        self.monitor.add_watch(
            field_path="value",
            callback=test_callback
        )
        
        # First evaluation to set previous value
        self.monitor.evaluate_watches(self.test_states[0])
        self.assertEqual(self.callback_count, 0)
        
        # Second evaluation to trigger the callback
        self.monitor.evaluate_watches(self.test_states[1])
        self.assertEqual(self.callback_count, 1)
        self.assertIsNotNone(self.last_alert)
        self.assertEqual(self.last_alert["field_path"], "value")
    
    def test_monitor_field_helper(self):
        """Test the monitor_field helper function."""
        # Add a watch using the helper function
        watch_id = monitor_field(
            field_path="value",
            condition="value > 15",
            level="WARNING"
        )
        
        # Check that the watch was added
        watches = list_watches()
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0]["field_path"], "value")
        self.assertEqual(watches[0]["expression"], "value > 15")
        self.assertEqual(watches[0]["alert_level"], "WARNING")
    
    def test_monitor_value_change(self):
        """Test the monitor_value_change helper function."""
        # Monitor for absolute change
        watch_id1 = monitor_value_change(
            field_path="value",
            min_change=5
        )
        
        # Monitor for percentage change
        watch_id2 = monitor_value_change(
            field_path="nested.count",
            min_change=50,
            percentage=True,
            level="WARNING"
        )
        
        # First evaluation to set previous values
        evaluate_watches(self.test_states[0])
        
        # Second evaluation to trigger alerts
        alerts = evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 2)
        
        # Verify absolute change alert
        value_alert = next(a for a in alerts if a["field_path"] == "value")
        self.assertEqual(value_alert["current_value"], 20)
        self.assertEqual(value_alert["previous_value"], 10)
        
        # Verify percentage change alert
        count_alert = next(a for a in alerts if a["field_path"] == "nested.count")
        self.assertEqual(count_alert["current_value"], 10)
        self.assertEqual(count_alert["previous_value"], 5)
    
    def test_monitor_threshold(self):
        """Test the monitor_threshold helper function."""
        # Monitor for exceeding a threshold
        watch_id = monitor_threshold(
            field_path="value",
            threshold=15,
            comparison=">",
            level="ERROR"
        )
        
        # Evaluate with a value below threshold
        alerts = evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)
        
        # Evaluate with a value above threshold
        alerts = evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["field_path"], "value")
        self.assertEqual(alerts[0]["alert_level"], "ERROR")
    
    def test_monitor_pattern_match(self):
        """Test the monitor_pattern_match helper function."""
        # Monitor for a pattern in a string
        watch_id = monitor_pattern_match(
            field_path="status",
            pattern="process",
            case_sensitive=False
        )
        
        # Evaluate with a non-matching value
        alerts = evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)
        
        # Evaluate with a matching value
        alerts = evaluate_watches(self.test_states[1])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["field_path"], "status")
        self.assertEqual(alerts[0]["current_value"], "processing")
    
    def test_monitor_state_condition(self):
        """Test the monitor_state_condition helper function."""
        # Monitor a condition on the entire state
        watch_id = monitor_state_condition(
            condition="value is not None and 'nested' in value and value['nested'].get('count', 0) > 10",
            level="WARNING"
        )
        
        # Evaluate with a state not meeting the condition
        alerts = evaluate_watches(self.test_states[0])
        self.assertEqual(len(alerts), 0)
        
        # Evaluate with a state meeting the condition
        alerts = evaluate_watches(self.test_states[2])
        self.assertEqual(len(alerts), 1)
    
    def test_statistics(self):
        """Test monitoring statistics."""
        # Add some watches
        monitor_field("value")
        monitor_threshold("nested.count", 10, ">")
        
        # Evaluate multiple times
        evaluate_watches(self.test_states[0])
        evaluate_watches(self.test_states[1])
        evaluate_watches(self.test_states[2])
        
        # Check statistics
        stats = get_monitor_statistics()
        self.assertEqual(stats["watches"], 2)
        self.assertEqual(stats["evaluations"], 3)
        self.assertEqual(stats["triggers"], 3)  # 1 for value change, 2 for threshold
        
        # Check watch details
        self.assertEqual(len(stats["watches_details"]), 2)


if __name__ == '__main__':
    unittest.main() 