import json
import datetime
from typing import Optional, Dict, Any, List, Union

DEFAULT_SEMANTIC_LOG_FILE = "semantic_state_details.log"
DEFAULT_DECISION_EVENT_TAG = "kfm_decision_node_exit_with_decision"

class LocalKfmExplanationService:
    """
    Service to retrieve and format explanations for KFM agent decisions
    based on structured semantic logs.
    """
    def __init__(self, log_file_path: str = DEFAULT_SEMANTIC_LOG_FILE):
        self.log_file_path = log_file_path

    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Helper to parse a single JSON log line."""
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Optionally log this error if the service had its own logger
            # print(f"Warning: Could not decode JSON from log line: {line[:100]}...")
            return None

    def get_kfm_decision_context(
        self,
        run_id: str,
        decision_event_tag: str = DEFAULT_DECISION_EVENT_TAG,
        decision_index: Optional[int] = 0 # 0-based index for the Nth decision
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the context for a specific KFM decision from semantic logs.

        Args:
            run_id: The ID of the run to search within.
            decision_event_tag: The event tag marking a KFM decision log entry.
            decision_index: The 0-based index of the decision to retrieve if multiple
                            decisions exist for the run_id. If None, tries to get the first.

        Returns:
            A dictionary containing the decision context, or None if not found.
        """
        matching_decision_logs: List[Dict[str, Any]] = []
        if decision_index is None: # Default to the first one found if index is None
            decision_index = 0

        try:
            with open(self.log_file_path, 'r') as f:
                for line in f:
                    log_entry = self._parse_log_line(line)
                    if not log_entry:
                        continue

                    if (log_entry.get("run_id") == run_id and
                        log_entry.get("event_tag") == decision_event_tag):
                        matching_decision_logs.append(log_entry)
        
        except FileNotFoundError:
            # print(f"Error: Log file not found: {self.log_file_path}")
            return None
        except Exception as e:
            # print(f"Error reading or processing log file: {e}")
            return None

        if decision_index < len(matching_decision_logs):
            target_log_entry = matching_decision_logs[decision_index]
            
            # Extract relevant information for the explanation
            kfm_action = target_log_entry.get("kfm_action", {})
            context = {
                "timestamp": target_log_entry.get("timestamp"),
                "run_id": run_id,
                "event_tag": decision_event_tag,
                "decision_index_found": decision_index,
                "action": kfm_action.get("action"),
                "component": kfm_action.get("component"),
                "reasoning": kfm_action.get("reasoning"),
                "confidence": kfm_action.get("confidence"),
                "task_name": target_log_entry.get("task_name"),
                # Summarize complex fields if necessary
                "input_data_summary": str(target_log_entry.get("input_data", {}))[:200] + "...",
                "current_task_requirements_summary": str(target_log_entry.get("current_task_requirements", {}))[:200] + "..."
            }
            return context
        else:
            # print(f"Decision with index {decision_index} not found for run_id {run_id}. Found {len(matching_decision_logs)} decisions.")
            return None

    def format_decision_explanation(self, decision_context: Optional[Dict[str, Any]]) -> str:
        """
        Formats the retrieved KFM decision context into a human-readable string.

        Args:
            decision_context: The context dictionary from get_kfm_decision_context.

        Returns:
            A human-readable explanation string.
        """
        if not decision_context:
            return "No decision context found to format."

        try:
            # Ensure each line is a distinct string literal for the f-string
            explanation = (
                f"Explanation for KFM Decision (Run ID: {decision_context.get('run_id')}, Logged at: {decision_context.get('timestamp')}, Decision #{decision_context.get('decision_index_found', 0) + 1}):\n"
                f"  Task: '{decision_context.get('task_name', 'N/A')}'\n"
                f"  Decision: Chose action '{decision_context.get('action', 'N/A')}' for component '{decision_context.get('component', 'N/A')}'\n"
                f"  Confidence: {decision_context.get('confidence', 'N/A'):.2f}\n"
                f"  Reasoning: \"{decision_context.get('reasoning', 'N/A')}\"\n"
                f"  Input Summary: {decision_context.get('input_data_summary', 'N/A')}\n"
                f"  Requirements Summary: {decision_context.get('current_task_requirements_summary', 'N/A')}"
            )
            # Handle cases where confidence might not be a float
        except TypeError: # Specifically for confidence formatting if it's not a float
             explanation = (
                f"Explanation for KFM Decision (Run ID: {decision_context.get('run_id')}, Logged at: {decision_context.get('timestamp')}, Decision #{decision_context.get('decision_index_found', 0) + 1}):\n"
                f"  Task: '{decision_context.get('task_name', 'N/A')}'\n"
                f"  Decision: Chose action '{decision_context.get('action', 'N/A')}' for component '{decision_context.get('component', 'N/A')}'\n"
                f"  Confidence: {str(decision_context.get('confidence', 'N/A'))}\n" # Format as string if not float
                f"  Reasoning: \"{decision_context.get('reasoning', 'N/A')}\"\n"
                f"  Input Summary: {decision_context.get('input_data_summary', 'N/A')}\n"
                f"  Requirements Summary: {decision_context.get('current_task_requirements_summary', 'N/A')}"
            )
        return explanation

if __name__ == '__main__':
    # Example Usage (assuming semantic_state_details.log exists and has data)
    explainer = LocalKfmExplanationService() # Uses default log file

    # --- Create dummy log entries for testing ---
    # This part is for local testing; in real use, the log file is generated by the agent.
    dummy_log_entries = [
        {
            "event_tag": "kfm_decision_node_exit_with_decision", "timestamp": "2023-10-26T10:00:00Z", 
            "run_id": "run_123", "task_name": "ProcessData",
            "kfm_action": {"action": "Kill", "component": "OldComponent", "reasoning": "Outdated and performing poorly.", "confidence": 0.95},
            "input_data": {"data_id": "xyz", "user_prefs": {"theme": "dark"}}, 
            "current_task_requirements": {"min_accuracy": 0.9, "max_latency_ms": 500}
        },
        {
            "event_tag": "some_other_event", "timestamp": "2023-10-26T10:00:05Z",
            "run_id": "run_123", "task_name": "ProcessData", 
            "active_component": "NewComponent"
        },
        {
            "event_tag": "kfm_decision_node_exit_with_decision", "timestamp": "2023-10-26T10:01:00Z",
            "run_id": "run_123", "task_name": "ProcessData",
            "kfm_action": {"action": "Fuck", "component": "TempComponent", "reasoning": "Need a quick fix while main is down.", "confidence": 0.70},
            "input_data": {"data_id": "abc", "user_prefs": {"theme": "light"}},
            "current_task_requirements": {"min_accuracy": 0.8, "max_latency_ms": 1000}
        },
        {
            "event_tag": "kfm_decision_node_exit_with_decision", "timestamp": "2023-10-26T10:02:00Z",
            "run_id": "run_456", "task_name": "AnalyzeReport",
            "kfm_action": {"action": "Keep", "component": "StableComponent", "reasoning": "Performing well.", "confidence": 0.99},
            "input_data": {"report_id": "def"},
            "current_task_requirements": {"processing_time_max_s": 30}
        }
    ]
    try:
        with open(DEFAULT_SEMANTIC_LOG_FILE, 'w') as f_dummy:
            for entry in dummy_log_entries:
                f_dummy.write(json.dumps(entry) + '\n')
        print(f"Created dummy log file: {DEFAULT_SEMANTIC_LOG_FILE}\n")
    except IOError as e:
        print(f"Could not write dummy log file: {e}\n")
    # --- End of dummy log creation ---


    # Test 1: Get the first decision for run_123
    print("Test 1: First decision for run_123")
    context1 = explainer.get_kfm_decision_context(run_id="run_123", decision_index=0)
    if context1:
        print("Raw Context:")
        # print(json.dumps(context1, indent=2))
        print("\nFormatted Explanation:")
        print(explainer.format_decision_explanation(context1))
    else:
        print("No context found.")
    print("\n---\n")

    # Test 2: Get the second decision for run_123
    print("Test 2: Second decision for run_123")
    context2 = explainer.get_kfm_decision_context(run_id="run_123", decision_index=1)
    if context2:
        print("Raw Context:")
        # print(json.dumps(context2, indent=2))
        print("\nFormatted Explanation:")
        print(explainer.format_decision_explanation(context2))
    else:
        print("No context found.")
    print("\n---\n")

    # Test 3: Get a decision for run_456
    print("Test 3: First decision for run_456")
    context3 = explainer.get_kfm_decision_context(run_id="run_456") # Defaults to decision_index=0
    if context3:
        print("Raw Context:")
        # print(json.dumps(context3, indent=2))
        print("\nFormatted Explanation:")
        print(explainer.format_decision_explanation(context3))
    else:
        print("No context found.")
    print("\n---\n")

    # Test 4: Non-existent run_id
    print("Test 4: Non-existent run_id")
    context4 = explainer.get_kfm_decision_context(run_id="run_non_existent")
    if context4:
        print(explainer.format_decision_explanation(context4))
    else:
        print("No context found (as expected).")
    print("\n---\n")

    # Test 5: Decision index out of bounds
    print("Test 5: Decision index out of bounds for run_123")
    context5 = explainer.get_kfm_decision_context(run_id="run_123", decision_index=5)
    if context5:
        print(explainer.format_decision_explanation(context5))
    else:
        print("No context found (as expected).")
    print("\n---\n")
    
    # Test 6: Using a different event tag (expect no results with default log)
    print("Test 6: Different event tag (expect no results with default log)")
    context6 = explainer.get_kfm_decision_context(run_id="run_123", decision_event_tag="execute_action_node_exit_success")
    if context6:
        print(explainer.format_decision_explanation(context6))
    else:
        print("No context found (as expected for this tag with dummy data).")
    print("\n---\n") 