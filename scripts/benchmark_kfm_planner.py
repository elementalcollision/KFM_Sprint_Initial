import time
from unittest.mock import MagicMock
import sys
import os

# Add src to PYTHONPATH to allow importing KFMPlanner and StateMonitor
# This assumes the script is run from the project root directory (KFM_Sprint1)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.core.kfm_planner import KFMPlanner
    from src.core.state_monitor import StateMonitor
except ImportError as e:
    print(f"Error: Could not import KFMPlanner or StateMonitor: {e}")
    print("Please ensure the script is run from the project root (KFM_Sprint1) or src is in PYTHONPATH.")
    # Define minimal versions if not importable (fallback for isolated execution if needed)
    # This is a simplified mock for the purpose of running the script if imports fail
    class KFMPlanner:
        def __init__(self, state_monitor, execution_engine):
            self.state_monitor = state_monitor
            self.execution_engine = execution_engine
            self.KFM_ACTIONS = {"kill": "kill", "fuck": "fuck", "marry": "marry"}
            self.NO_ACTION = {"action": "kill", "component": None}

        def decide_kfm_action(self, task_name="default"):
            requirements = self.state_monitor.get_task_requirements(task_name)
            if not requirements or not all(k in requirements for k in ['min_accuracy', 'max_latency']):
                # print(f"Error: Task '{task_name}' requirements are incomplete or missing.")
                return None 
            
            all_components_performance = self.state_monitor.get_performance_data()
            if not all_components_performance:
                return self.NO_ACTION
            
            min_accuracy = requirements['min_accuracy']
            max_latency = requirements['max_latency']
            
            marry_candidates = []
            fuck_candidates = []

            for name, metrics in all_components_performance.items():
                accuracy = metrics.get('accuracy', 0.0) 
                latency = metrics.get('latency', float('inf')) 
                
                meets_accuracy = accuracy >= min_accuracy
                meets_latency = latency <= max_latency

                if meets_accuracy and meets_latency:
                    marry_candidates.append((name, accuracy, latency))
                elif meets_accuracy or meets_latency:
                    fuck_candidates.append((name, accuracy, latency))
            
            if marry_candidates:
                marry_candidates.sort(key=lambda x: (-x[1], x[2]))
                return {"action": self.KFM_ACTIONS["marry"], "component": marry_candidates[0][0]}
            
            if fuck_candidates:
                fuck_candidates.sort(key=lambda x: (-x[1], x[2]))
                return {"action": self.KFM_ACTIONS["fuck"], "component": fuck_candidates[0][0]}
                
            return self.NO_ACTION

    class StateMonitor: 
        def get_performance_data(self): return {}
        def get_task_requirements(self, task_name='default'): return {'min_accuracy': 0.0, 'max_latency': 1.0}


def get_default_task_requirements():
    return {
        'default': {'min_accuracy': 0.8, 'max_latency': 1.0},
        'speed_critical': {'min_accuracy': 0.6, 'max_latency': 0.5},
        'accuracy_critical': {'min_accuracy': 0.95, 'max_latency': 2.0},
        'zero_acc': {'min_accuracy': 0.0, 'max_latency': 1.0}
    }

scenarios = [
    {
        "name": "test_marry_single_candidate", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 0.5}}
    },
    {
        "name": "test_marry_best_of_multiple", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.85, 'latency': 0.8}, 'comp_b': {'accuracy': 0.95, 'latency': 0.7}, 'comp_c': {'accuracy': 0.95, 'latency': 0.6}, 'comp_d': {'accuracy': 0.7, 'latency': 0.6}}
    },
    {
        "name": "test_marry_tie_breaker_latency", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 0.8}, 'comp_b': {'accuracy': 0.9, 'latency': 0.6}}
    },
    {
        "name": "test_fuck_accuracy_only", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 1.5}}
    },
    {
        "name": "test_fuck_latency_only", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.7, 'latency': 0.5}}
    },
    {
        "name": "test_fuck_best_of_multiple", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.6, 'latency': 1.5}, 'comp_b': {'accuracy': 0.7, 'latency': 0.5}, 'comp_c': {'accuracy': 0.9, 'latency': 1.2}, 'comp_d': {'accuracy': 0.85, 'latency': 1.1}}
    },
    {
        "name": "test_fuck_tie_breaker_latency", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 1.8}, 'comp_b': {'accuracy': 0.9, 'latency': 1.2}, 'comp_c': {'accuracy': 0.7, 'latency': 0.5}}
    },
    {
        "name": "test_marry_preferred_over_fuck", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 1.5}, 'comp_b': {'accuracy': 0.85, 'latency': 0.8}}
    },
    {
        "name": "test_kill_no_components", "task_name": "default", "performance_data": {}
    },
    {
        "name": "test_kill_all_fail", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.7, 'latency': 1.5}, 'comp_b': {'accuracy': 0.6, 'latency': 2.0}}
    },
    {
        "name": "test_custom_req_speed_critical", "task_name": "speed_critical",
        "performance_data": {'comp_fast': {'accuracy': 0.7, 'latency': 0.4}, 'comp_slow': {'accuracy': 0.9, 'latency': 0.8}}
    },
    {
        "name": "test_custom_req_accuracy_critical", "task_name": "accuracy_critical",
        "performance_data": {'comp_accurate': {'accuracy': 0.96, 'latency': 1.8}, 'comp_fast_inaccurate': {'accuracy': 0.8, 'latency': 0.5}}
    },
    {
        "name": "test_missing_metrics", "task_name": "default",
        "performance_data": {'comp_a': {'latency': 0.5}, 'comp_b': {'accuracy': 0.9}, 'comp_c': {'accuracy': 0.99, 'latency': 0.1}}
    },
    {
        "name": "test_zero_latency", "task_name": "default",
        "performance_data": {'comp_a': {'accuracy': 0.9, 'latency': 0.0}}
    },
    {
        "name": "test_zero_min_accuracy_req", "task_name": "zero_acc",
        "performance_data": {'comp_a': {'accuracy': 0.1, 'latency': 0.5}}
    },
    {
        "name": "test_incomplete_requirements", "task_name": "incomplete_req_task",
        "performance_data": {'comp_a': {'accuracy': 0.95, 'latency': 0.5}},
        "task_requirements_override": {'min_accuracy': 0.9} 
    }
]

if __name__ == "__main__":
    print("KFMPlanner Latency Measurements (Original):")
    all_latencies = {}

    for scenario in scenarios:
        mock_state_monitor = MagicMock(spec=StateMonitor)
        default_reqs = get_default_task_requirements()

        mock_state_monitor.get_performance_data.return_value = scenario["performance_data"]

        if "task_requirements_override" in scenario:
            mock_state_monitor.get_task_requirements.return_value = scenario["task_requirements_override"]
        else:
            # Closure to capture current scenario's task_name for the lambda
            def get_reqs_for_task(task_name_in_scenario, default_requirements_map):
                return lambda task_name_arg: default_requirements_map.get(task_name_arg, default_requirements_map['default'])
            
            mock_state_monitor.get_task_requirements.side_effect = get_reqs_for_task(scenario["task_name"], default_reqs)

        mock_execution_engine = MagicMock()
        planner_instance = KFMPlanner(mock_state_monitor, mock_execution_engine)

        # Ensure the correct task_name is used by the mock when decide_kfm_action is called
        # For scenarios not overriding requirements, the lambda will use the task_name passed to decide_kfm_action
        # For the override case, it's fixed.

        # Pre-call get_task_requirements once if using side_effect to ensure it's correctly set for the upcoming task_name
        # This is mostly for complex side_effect logic; here it should be okay as decide_kfm_action passes task_name
        # which then is used by the lambda.

        start_time = time.perf_counter()
        planner_instance.decide_kfm_action(task_name=scenario["task_name"])
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        all_latencies[scenario['name']] = latency_ms
        print(f"- {scenario['name']}: {latency_ms:.4f} ms")

    print("\\n--- Summary ---")
    if all_latencies:
        avg_latency = sum(all_latencies.values()) / len(all_latencies)
        min_latency = min(all_latencies.values())
        max_latency = max(all_latencies.values())
        print(f"Average Latency: {avg_latency:.4f} ms")
        print(f"Min Latency: {min_latency:.4f} ms (Scenario: {min(all_latencies, key=all_latencies.get)})")
        print(f"Max Latency: {max_latency:.4f} ms (Scenario: {max(all_latencies, key=all_latencies.get)})")
    
    print("\\nNote: These latencies are for the original KFMPlanner's logic.") 