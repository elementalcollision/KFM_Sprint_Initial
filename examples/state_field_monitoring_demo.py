#!/usr/bin/env python
"""
Demonstration of the state field monitoring functionality.

This script shows how to use the state field monitoring features
to monitor specific fields in the state and receive alerts when
conditions are met.
"""

import os
import sys
import json
import time
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import setup_logger
from src.debugging import (
    monitor_field,
    monitor_value_change,
    monitor_threshold,
    monitor_pattern_match,
    monitor_state_condition,
    stop_monitoring,
    stop_all_monitoring,
    get_active_monitors,
    get_monitoring_statistics
)

# Setup a logger for this demo
demo_logger = setup_logger('examples.state_field_monitoring_demo')


def simulate_state_changes():
    """
    Simulate a series of state changes to demonstrate field monitoring.
    """
    demo_logger.info("=== STATE FIELD MONITORING DEMONSTRATION ===")
    
    # Initial state
    state = {
        "id": "demo-123",
        "name": "Field Monitoring Demo",
        "counter": 0,
        "status": "initializing",
        "error_count": 0,
        "metrics": {
            "response_time": 100,
            "success_rate": 100,
            "memory_usage": 50
        },
        "flags": {
            "debug": False,
            "verbose": True
        },
        "items": []
    }
    
    # Setup field monitors
    setup_monitors()
    
    # Log initial state
    demo_logger.info("\n1. Initial state:")
    demo_logger.info(json.dumps(state, indent=2))
    
    # Simulate state changes
    demo_logger.info("\n2. Starting state change simulation")
    
    # Simulate 10 changes
    for i in range(1, 11):
        demo_logger.info(f"\n--- Change #{i} ---")
        
        # Update the state
        state = update_state(state, i)
        
        # Log key state fields
        demo_logger.info(f"Counter: {state['counter']}, Status: {state['status']}, Error count: {state['error_count']}")
        demo_logger.info(f"Metrics: response_time={state['metrics']['response_time']}ms, success_rate={state['metrics']['success_rate']}%, memory_usage={state['metrics']['memory_usage']}MB")
        
        # Small delay
        time.sleep(0.5)
    
    # Show monitoring statistics
    demo_logger.info("\n3. Monitoring statistics:")
    stats = get_monitoring_statistics()
    demo_logger.info(f"Total evaluations: {stats['evaluations']}")
    demo_logger.info(f"Total triggers: {stats['triggers']}")
    demo_logger.info(f"By level: {stats['by_level']}")
    
    # Show active monitors
    demo_logger.info("\n4. Active monitors:")
    monitors = get_active_monitors()
    for monitor in monitors:
        demo_logger.info(f"- {monitor['field_path']}: {monitor['description']} (triggered {monitor['trigger_count']} times)")
    
    # Clean up
    stop_all_monitoring()
    demo_logger.info("\n=== DEMONSTRATION COMPLETE ===")


def setup_monitors():
    """
    Set up various field monitors for the demonstration.
    """
    demo_logger.info("\nSetting up field monitors...")
    
    # 1. Simple change monitor
    monitor_field(
        field_path="status",
        description="Status change monitor"
    )
    
    # 2. Threshold monitor
    monitor_threshold(
        field_path="error_count",
        threshold=3,
        comparison=">=",
        level="ERROR"
    )
    
    # 3. Value change monitor (percentage)
    monitor_value_change(
        field_path="metrics.response_time",
        min_change=50,
        percentage=True,
        level="WARNING"
    )
    
    # 4. Value change monitor (absolute)
    monitor_value_change(
        field_path="metrics.memory_usage",
        min_change=20,
        level="INFO"
    )
    
    # 5. Pattern match monitor
    monitor_pattern_match(
        field_path="status",
        pattern="error",
        case_sensitive=False,
        level="ERROR"
    )
    
    # 6. Complex state condition
    monitor_state_condition(
        condition="'metrics' in value and value['metrics']['success_rate'] < 90",
        description="Low success rate alert",
        level="WARNING"
    )
    
    # 7. Flag change monitor
    monitor_field(
        field_path="flags.debug",
        condition="value == True",
        description="Debug mode enabled",
        level="INFO"
    )
    
    # 8. Array size monitor
    monitor_field(
        field_path="items",
        condition="len(value) > 5",
        description="Many items",
        level="INFO"
    )
    
    demo_logger.info(f"Set up {len(get_active_monitors())} monitors")


def update_state(state, iteration):
    """
    Update the state for a given iteration to demonstrate various monitoring scenarios.
    
    Args:
        state: Current state to update
        iteration: Current iteration number
        
    Returns:
        Updated state
    """
    # Create a new state to avoid modifying the original
    new_state = json.loads(json.dumps(state))
    
    # Always increment counter
    new_state["counter"] = iteration
    
    # Update based on iteration
    if iteration == 1:
        # Change status
        new_state["status"] = "running"
        
    elif iteration == 2:
        # Small response time change (won't trigger alert)
        new_state["metrics"]["response_time"] = 120
        
    elif iteration == 3:
        # Big response time change (triggers percentage alert)
        new_state["metrics"]["response_time"] = 200
        
    elif iteration == 4:
        # Memory usage increase
        new_state["metrics"]["memory_usage"] = 75
        
    elif iteration == 5:
        # Trigger error alert
        new_state["error_count"] = 3
        new_state["status"] = "error"
        new_state["metrics"]["success_rate"] = 70
        
    elif iteration == 6:
        # Recovery attempt
        new_state["status"] = "recovering"
        
    elif iteration == 7:
        # Debug mode enabled
        new_state["flags"]["debug"] = True
        
    elif iteration == 8:
        # Add items
        new_state["items"] = ["item1", "item2", "item3", "item4", "item5", "item6"]
        
    elif iteration == 9:
        # Success rate improves
        new_state["metrics"]["success_rate"] = 95
        new_state["status"] = "stable"
        
    elif iteration == 10:
        # Final state
        new_state["status"] = "completed"
        new_state["metrics"]["memory_usage"] = 40
    
    return new_state


def demonstrate_advanced_usage():
    """Demonstrate some advanced monitoring scenarios."""
    demo_logger.info("\n=== ADVANCED MONITORING SCENARIOS ===")
    
    # Custom callback function
    def on_alert(alert):
        demo_logger.info(f"CALLBACK: Alert received for {alert['field_path']}")
        # You could perform custom actions here, like sending an email or webhook
    
    # Clear any existing monitors
    stop_all_monitoring()
    
    # Use callback for important alert
    from src.tracing import watch_field
    watch_id = watch_field(
        field_path="critical_metric",
        expression="value > 95",
        description="Critical threshold exceeded",
        alert_level="CRITICAL",
        callback=on_alert
    )
    
    # Custom complex expression
    monitor_field(
        field_path="metrics",
        condition="'success_rate' in value and 'response_time' in value and value['success_rate'] < 80 and value['response_time'] > 200",
        description="Poor performance detected",
        level="ERROR"
    )
    
    # Dynamic reference to other fields
    monitor_state_condition(
        condition="'counter' in value and 'threshold' in value and value['counter'] > value['threshold']",
        description="Counter exceeded dynamic threshold",
        level="WARNING"
    )
    
    # Test the monitors
    test_state = {
        "critical_metric": 96,
        "metrics": {
            "success_rate": 75,
            "response_time": 250
        },
        "counter": 15,
        "threshold": 10
    }
    
    from src.tracing import evaluate_watches
    alerts = evaluate_watches(test_state)
    
    demo_logger.info(f"Advanced monitoring triggered {len(alerts)} alerts:")
    for alert in alerts:
        demo_logger.info(f"- {alert['alert_level']}: {alert['description']}")
    
    # Clean up
    stop_all_monitoring()
    demo_logger.info("=== ADVANCED DEMONSTRATION COMPLETE ===")


if __name__ == "__main__":
    simulate_state_changes()
    demonstrate_advanced_usage() 