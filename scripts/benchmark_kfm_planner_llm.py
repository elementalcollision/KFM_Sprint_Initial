import time
import json
import os
import sys
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Add src to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv()

# --- KFM Types (Placeholder until actual implementation is available) ---
from pydantic import BaseModel, Field, field_validator, ValidationError, FieldValidationInfo
from typing import Literal, Optional, Dict, Any, List, Union

# Attempt to import actual StateMonitor, otherwise use placeholder
try:
    from src.core.state_monitor import StateMonitor
    print("Successfully imported StateMonitor from src.core")
except ImportError:
    print("Warning: Could not import StateMonitor from src.core. Using placeholder definition.")
    class StateMonitor: # Placeholder definition
        def get_task_requirements(self, task_name: str) -> Dict[str, Any]:
            # Dummy implementation for placeholder
            print(f"Placeholder StateMonitor: get_task_requirements for {task_name}")
            return {"min_accuracy": 0.0, "max_latency": 0.0} 
        def get_performance_data(self) -> Dict[str, Any]:
            # Dummy implementation for placeholder
            print("Placeholder StateMonitor: get_performance_data")
            return {}

# LangChain components - Import all potential models
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import ChatOpenAI
    from langchain_cerebras import ChatCerebras
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_community.cache import InMemoryCache, SQLiteCache
    from langchain.globals import set_llm_cache
except ImportError as e:
    print(f"Error importing a LangChain component: {e}")
    print("Please ensure langchain-google-genai, langchain-openai, langchain-cerebras, langchain-core, langchain-community, and langchain are installed.")
    sys.exit(1)

# Import KFMDecision and KFMPlannerLlm from src.core
try:
    from src.core.kfm_planner_llm import KFMDecision, KFMPlannerLlm
    print("Successfully imported KFMDecision and KFMPlannerLlm from src.core.kfm_planner_llm")
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import KFMDecision or KFMPlannerLlm from src.core.kfm_planner_llm: {e}")
    print("Ensure the file exists and is importable, and that all its dependencies are met.")
    sys.exit(1)

# Remove local KFMDecision and KFMPlannerLlm placeholder definitions as they are now imported.

# --- Optimized KFM Prompt Templates (These are used by KFMPlannerLlm internally) ---
# These can be removed from here if KFMPlannerLlm exclusively uses its internal versions.
# For now, keeping them might not hurt, but they aren't directly used by the refactored main logic.
OPTIMIZED_KFM_SYSTEM_PROMPT = """You are KFMPlannerLlm. Decide the KFM action (marry, fuck, kill) based on task requirements and component performance. Output ONLY the specified JSON.

Rules:
1. Marry: If component meets BOTH min_accuracy AND max_latency. Tiebreaker: highest accuracy, then lowest latency.
2. Fuck: If NO component qualifies for Marry, choose if component meets EITHER min_accuracy OR max_latency. Tiebreaker: highest accuracy, then lowest latency.
3. Kill: If NO component qualifies for Marry or Fuck.

Inputs Provided:
- task_name
- min_accuracy (float)
- max_latency (float)
- components: dict {{comp_name: {{'accuracy': float, 'latency': float}}}}

Error Handling:
- Missing requirements: Kill, reason "missing requirements".
- No components: Kill, reason "no components".
- Perfect tie: Choose alphabetically first component name.

Output JSON Format (ONLY this JSON):
{{ "action": "<marry|fuck|kill>", "component_name": <"component_name_string"_or_JSON_null>, "reason": "<brief_explanation>" }}
IMPORTANT: If action is 'kill', component_name MUST be JSON null (not the string "null").
"""
# Corrected OPTIMIZED_KFM_HUMAN_PROMPT - Escaping internal curly braces
OPTIMIZED_KFM_HUMAN_PROMPT = "Task: {task_name}\nMin Accuracy: {min_accuracy}\nMax Latency: {max_latency}\nComponents:\n{components_str}"

# --- Test Scenarios (Simplified from test_kfm_planner.py for benchmark focus) ---
# (Same scenarios as before, but add 'expected_outcome')
scenarios = [
    {
        "name": "test_marry_single_candidate",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {"comp_a": {"accuracy": 0.95, "latency": 50}},
        "expected_outcome": {"action": "marry", "component": "comp_a"}
    },
    {
        "name": "test_marry_best_of_multiple",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.92, "latency": 60},
            "comp_b": {"accuracy": 0.95, "latency": 50},
            "comp_c": {"accuracy": 0.90, "latency": 70}
        },
        "expected_outcome": {"action": "marry", "component": "comp_b"}
    },
    {
        "name": "test_marry_tie_breaker_latency",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.95, "latency": 50},
            "comp_b": {"accuracy": 0.95, "latency": 60}
        },
        "expected_outcome": {"action": "marry", "component": "comp_a"}
    },
    {
        "name": "test_fuck_accuracy_only",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {"comp_a": {"accuracy": 0.92, "latency": 120}},
        "expected_outcome": {"action": "fuck", "component": "comp_a"}
    },
    {
        "name": "test_fuck_latency_only",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {"comp_a": {"accuracy": 0.85, "latency": 80}},
        "expected_outcome": {"action": "fuck", "component": "comp_a"}
    },
    {
        "name": "test_fuck_best_of_multiple",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.88, "latency": 70}, 
            "comp_b": {"accuracy": 0.85, "latency": 80}, 
            "comp_c": {"accuracy": 0.70, "latency": 120}
        },
        "expected_outcome": {"action": "fuck", "component": "comp_a"}
    },
    {
        "name": "test_fuck_tie_breaker_latency_among_fucks",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.85, "latency": 70}, 
            "comp_b": {"accuracy": 0.85, "latency": 80}
        },
        "expected_outcome": {"action": "fuck", "component": "comp_a"}
    },
    {
        "name": "test_marry_preferred_over_fuck",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.91, "latency": 90}, 
            "comp_b": {"accuracy": 0.95, "latency": 110}
        },
        "expected_outcome": {"action": "marry", "component": "comp_a"}
    },
    {
        "name": "test_kill_no_components",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {},
        "expected_outcome": {"action": "kill", "component": None}
    },
    {
        "name": "test_kill_all_fail_requirements",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {
            "comp_a": {"accuracy": 0.8, "latency": 120},
            "comp_b": {"accuracy": 0.7, "latency": 110}
        },
        "expected_outcome": {"action": "kill", "component": None}
    },
    {
        "name": "test_custom_req_speed_critical",
        "requirements": {"min_accuracy": 0.8, "max_latency": 50},
        "components": {
            "comp_fast": {"accuracy": 0.85, "latency": 40}, 
            "comp_accurate": {"accuracy": 0.95, "latency": 100}
        },
        "expected_outcome": {"action": "marry", "component": "comp_fast"}
    },
    {
        "name": "test_custom_req_accuracy_critical",
        "requirements": {"min_accuracy": 0.95, "max_latency": 150},
        "components": {
            "comp_fast": {"accuracy": 0.85, "latency": 40},
            "comp_accurate": {"accuracy": 0.96, "latency": 100}
        },
        "expected_outcome": {"action": "marry", "component": "comp_accurate"}
    },
    { # KFMPlannerLlm currently returns kill for missing metrics, reason "LLM chain failed..." due to strict Pydantic or other error
        "name": "test_missing_metrics_component",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {"comp_a": {"latency": 50}},
        "expected_outcome": {"action": "kill", "component": None} # Or specific reasoning
    },
    {
        "name": "test_zero_latency_component",
        "requirements": {"min_accuracy": 0.9, "max_latency": 100},
        "components": {"comp_a": {"accuracy": 0.95, "latency": 0}},
        "expected_outcome": {"action": "marry", "component": "comp_a"}
    },
    {
        "name": "test_zero_min_accuracy_req", # Marry if meets latency
        "requirements": {"min_accuracy": 0.0, "max_latency": 100},
        "components": {"comp_a": {"accuracy": 0.01, "latency": 50}},
        "expected_outcome": {"action": "marry", "component": "comp_a"}
    },
    { # KFMPlannerLlm currently returns kill for missing reqs, reason "LLM chain failed..."
        "name": "test_incomplete_requirements_no_latency",
        "requirements": {"min_accuracy": 0.9}, # Missing max_latency
        "components": {"comp_a": {"accuracy": 0.95, "latency": 50}},
        "expected_outcome": {"action": "kill", "component": None} # Or specific reasoning
    }
]

def format_component_data(components: Dict[str, Any]) -> str:
    if not components:
        return "No components available."
    return "\n".join([f"{name}: Acc={data.get('accuracy', 'N/A')}, Lat={data.get('latency', 'N/A')}" for name, data in components.items()])

def main(provider_model_str: Optional[str] = None): # Made argument optional
    print(f"Benchmarking KFMPlannerLlm with fallback priority.")
    
    # --- Initialize Caching --- 
    # Cache can be based on the KFMPlannerLlm class or a generic name if desired
    cache_dir = ".cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    db_path = os.path.join(cache_dir, "kfm_planner_llm_benchmark_cache.sqlite")
    print(f"Initializing LLM cache (SQLiteCache at {db_path})...")
    set_llm_cache(SQLiteCache(database_path=db_path))
    print("LLM Caching is ACTIVE.")

    # --- Mock StateMonitor and initialize KFMPlannerLlm from src.core ---
    mock_state_monitor = MagicMock(spec=StateMonitor)
    
    # Define the priority list for KFMPlannerLlm
    # This is the fallback chain we want to test.
    llm_priority = ["cerebras", "google", "openai_3_5"] 
    print(f"Initializing KFMPlannerLlm from src.core with priority: {llm_priority}")
    try:
        planner = KFMPlannerLlm(state_monitor=mock_state_monitor, priority=llm_priority)
        print("KFMPlannerLlm initialized successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to initialize KFMPlannerLlm from src.core: {e}")
        sys.exit(1)

    # --- Run Benchmarks ---
    results = []
    total_latency_scenario = 0 # Renamed to avoid conflict with KFMPlannerLlm internal latencies if exposed
    successful_calls = 0
    validation_passes = 0
    validation_fails = 0
    # Token and cost tracking will be harder without direct LLM calls here.
    # KFMPlannerLlm would need to expose this metadata if desired per call.
    # For now, we focus on decision quality and overall latency.

    print(f"\nRunning {len(scenarios)} scenarios using KFMPlannerLlm's decide_kfm_action...")
    for i, scenario_data in enumerate(scenarios):
        task_name = scenario_data["name"]
        requirements = scenario_data["requirements"]
        components = scenario_data["components"]
        expected = scenario_data["expected_outcome"]
        
        start_time = time.time()
        decision_obj: Optional[KFMDecision] = None # Ensure it's KFMDecision from src.core
        decision_dict_for_log = {}
        log_message_prefix = f"  {i+1}/{len(scenarios)}: {task_name}"

        try:
            decision_obj = planner.decide_kfm_action(
                task_name=task_name,
                requirements=requirements,
                components=components
            )
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            total_latency_scenario += latency_ms
            successful_calls += 1
            
            decision_dict_for_log = decision_obj.model_dump() # Use .model_dump() for Pydantic v2

            # Validation
            is_pass = True
            if decision_obj.action != expected["action"]:
                is_pass = False
            # Only check component if expected action is not 'kill'
            if expected["action"] != "kill" and decision_obj.component != expected["component"]:
                 is_pass = False
            elif expected["action"] == "kill" and decision_obj.component is not None: # Ensure component is None for kill
                 is_pass = False


            if is_pass:
                validation_passes += 1
                status_msg = "PASS"
            else:
                validation_fails += 1
                status_msg = f"FAIL (Expected: {expected}, Got: {{'action': '{decision_obj.action}', 'component': '{decision_obj.component}'}})"

            results.append({
                "scenario": task_name,
                "decision": decision_dict_for_log,
                "expected": expected,
                "status": status_msg,
                "latency_ms": latency_ms,
                "reasoning": decision_obj.reasoning, # Add reasoning to results
                "confidence": decision_obj.confidence # Add confidence
            })
            print(f"{log_message_prefix} -> {decision_obj.action} (Comp: {decision_obj.component or 'N/A'}) - {status_msg} ({latency_ms:.2f}ms)")

        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            validation_fails+=1 # Count errors as validation fails
            print(f"{log_message_prefix} -> ERROR ({latency_ms:.2f}ms): {e}")
            results.append({
                "scenario": task_name,
                "decision": {"action": "error", "reasoning": str(e), "component": None, "confidence": 0.0},
                "expected": expected,
                "status": f"ERROR (Expected: {expected})",
                "latency_ms": latency_ms,
                "reasoning": str(e),
                "confidence": 0.0
            })

    print("\n--- Benchmark Summary ---")
    print(f"KFMPlannerLlm with priority: {llm_priority}")
    if successful_calls > 0:
        avg_latency = total_latency_scenario / successful_calls
        print(f"Total Scenarios: {len(scenarios)}\n")
        print(f"--- Decision Quality ---")
        print(f"Validation Passes: {validation_passes}")
        print(f"Validation Fails:  {validation_fails}")
        pass_rate = (validation_passes / len(scenarios)) * 100 if len(scenarios) > 0 else 0
        print(f"Pass Rate:         {pass_rate:.2f}%\n")
        
        print(f"--- Performance ---")
        print(f"Successful KFMPlannerLlm Calls: {successful_calls}")
        print(f"Average Latency (Successful): {avg_latency:.2f} ms")
        # Min/Max latency calculation needs adjustment if results can contain errors
        successful_results = [r for r in results if r['status'] != 'ERROR']
        if successful_results:
            min_lat_res = min(successful_results, key=lambda x: x['latency_ms'])
            max_lat_res = max(successful_results, key=lambda x: x['latency_ms'])
            print(f"Min Latency (Successful): {min_lat_res['latency_ms']:.2f} ms (Scenario: {min_lat_res['scenario']})")
            print(f"Max Latency (Successful): {max_lat_res['latency_ms']:.2f} ms (Scenario: {max_lat_res['scenario']})")
        else:
            print("No successful calls to calculate Min/Max latency.")

        # Token/Cost information is not directly available per call in this refactor
        print("\nToken and cost information is not tracked in this version of the benchmark script,")
        print("as KFMPlannerLlm encapsulates the direct LLM calls and their metadata.")
        print("Consider enhancing KFMPlannerLlm or using callbacks if this data is required.")

    else:
        print("No successful KFMPlannerLlm calls.")

    # --- Detailed Results ---
    print("\n--- Detailed Scenario Results ---")
    for res in results:
        # Use 'component' from decision dict, which comes from KFMDecision.component
        component_val = res['decision'].get('component', 'N/A') if isinstance(res['decision'], dict) else 'N/A'
        reasoning_val = res['decision'].get('reasoning', 'N/A') if isinstance(res['decision'], dict) else 'N/A'
        confidence_val = res['decision'].get('confidence', 'N/A') if isinstance(res['decision'], dict) else 'N/A'
        
        print(f"- Scenario: {res['scenario']}")
        print(f"  Status:    {res['status']}")
        print(f"  Decision:  {res['decision'].get('action', 'error')} (Component: {component_val}, Confidence: {confidence_val})")
        print(f"  Reasoning: \"{reasoning_val}\"")
        print(f"  Latency:   {res['latency_ms']:.2f}ms")
        print("-" * 20)


if __name__ == "__main__":
    # Removed the provider_model_arg, main will use the hardcoded priority for KFMPlannerLlm
    main()