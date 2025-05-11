import json
import os
import glob
from typing import List, Dict, Any, Optional
from collections import Counter
import datetime # For potential future use with log timestamps

# Assuming semantic logs are named somewhat consistently, e.g., semantic_state_details.log
# or semantic_state_*.log
DEFAULT_LOG_PATTERN = "semantic_state_details.log" # Could be more generic like "*.log"

class GlobalAnalyticsService:
    """
    Service to aggregate KFM agent behavior and performance metrics from multiple
    semantic log files to provide global analytics and trend insights.
    """
    def __init__(self, log_files: Optional[List[str]] = None, log_dir: Optional[str] = None, log_pattern: str = DEFAULT_LOG_PATTERN):
        """
        Initializes the service with log sources.

        Args:
            log_files: A list of specific log file paths to process.
            log_dir: A directory path. If provided, all files matching log_pattern in this directory will be processed.
            log_pattern: The glob pattern to use when searching for logs in log_dir.
        """
        self.log_sources: List[str] = []
        if log_files:
            self.log_sources.extend(log_files)
        if log_dir:
            if not os.path.isdir(log_dir):
                # Consider raising an error or logging a warning
                print(f"Warning: Log directory '{log_dir}' not found.") # Simple print for now
            else:
                self.log_sources.extend(glob.glob(os.path.join(log_dir, log_pattern)))
        
        if not self.log_sources:
            # Consider raising an error if no logs are found/specified
            print("Warning: No log sources specified or found.")

        # Initialize aggregated metrics storage
        self.total_log_entries_processed: int = 0
        self.total_decision_entries: int = 0
        self.kfm_action_counts: Counter = Counter()
        self.component_usage_counts: Counter = Counter()
        self.task_requirement_satisfaction_counts: Counter = Counter()
        self.fuck_action_count: int = 0
        self.error_count: int = 0
        self.summed_confidence: float = 0.0
        self.decision_event_tag: str = "kfm_decision_node_exit_with_decision" # From LocalKfmExplanationService
        self.execution_success_tag: str = "execute_action_node_exit_success"

    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Helper to parse a single JSON log line, returns None if malformed."""
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Optionally log this error to a separate debug log or increment a malformed_line_counter
            return None

    def _extract_metrics_from_entry(self, log_entry: Dict[str, Any]):
        """Extracts and aggregates metrics from a single valid log entry."""
        self.total_log_entries_processed += 1

        event_tag = log_entry.get("event_tag")
        kfm_action_details = log_entry.get("kfm_action")

        if event_tag == self.decision_event_tag and isinstance(kfm_action_details, dict):
            self.total_decision_entries += 1
            action_type = kfm_action_details.get("action")
            component = kfm_action_details.get("component")
            confidence = kfm_action_details.get("confidence")

            if action_type:
                self.kfm_action_counts[action_type] += 1
                if action_type.lower() == "fuck": # Case-insensitive for "Fuck"
                    self.fuck_action_count += 1
            
            if component:
                self.component_usage_counts[component] += 1
            
            if isinstance(confidence, (int, float)):
                self.summed_confidence += confidence
        
        if event_tag == self.execution_success_tag:
            calculated_metrics = log_entry.get("calculated_metrics")
            if isinstance(calculated_metrics, dict):
                satisfaction_score = calculated_metrics.get("task_requirement_satisfaction")
                if satisfaction_score:
                    self.task_requirement_satisfaction_counts[satisfaction_score] += 1

        if log_entry.get("error"): # Checks if the error field is present and not None/empty
            self.error_count += 1

    def process_logs(self) -> None:
        """Processes all specified log sources and aggregates metrics."""
        if not self.log_sources:
            print("No logs to process.")
            return

        for log_file_path in self.log_sources:
            if not os.path.exists(log_file_path):
                print(f"Warning: Log file '{log_file_path}' not found. Skipping.")
                continue
            try:
                with open(log_file_path, 'r') as f:
                    for line in f:
                        log_entry = self._parse_log_line(line)
                        if log_entry:
                            self._extract_metrics_from_entry(log_entry)
            except Exception as e:
                print(f"Error processing log file '{log_file_path}': {e}")
        
        print(f"Finished processing {len(self.log_sources)} log source(s). Processed {self.total_log_entries_processed} total entries.")

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Returns a dictionary of the aggregated metrics."""
        average_confidence = (self.summed_confidence / self.total_decision_entries) if self.total_decision_entries > 0 else 0
        
        return {
            "total_log_sources_scanned": len(self.log_sources),
            "total_log_entries_processed": self.total_log_entries_processed,
            "total_decision_events": self.total_decision_entries,
            "kfm_action_counts": dict(self.kfm_action_counts),
            "component_usage_counts": dict(self.component_usage_counts),
            "fuck_action_count": self.fuck_action_count,
            "error_count": self.error_count,
            "average_decision_confidence": round(average_confidence, 3),
            "task_requirement_satisfaction_distribution": dict(self.task_requirement_satisfaction_counts),
        }

    def generate_report_text(self) -> str:
        """Generates a human-readable text/Markdown report of the aggregated metrics."""
        metrics = self.get_aggregated_metrics()
        report_lines = []

        report_lines.append("# KFM Agent Global Analytics Report")
        report_lines.append(f"- Date Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"- Log Sources Scanned: {metrics['total_log_sources_scanned']}")
        report_lines.append(f"- Total Log Entries Processed: {metrics['total_log_entries_processed']}")
        report_lines.append(f"- Total KFM Decision Events: {metrics['total_decision_events']}")
        report_lines.append("---")

        report_lines.append("## KFM Decision Analytics")
        report_lines.append(f"- Average Decision Confidence: {metrics['average_decision_confidence']:.3f}")
        report_lines.append(f"- 'Fuck' Actions Count: {metrics['fuck_action_count']}")
        report_lines.append("### Action Type Distribution:")
        if metrics['kfm_action_counts']:
            for action, count in sorted(metrics['kfm_action_counts'].items()):
                percentage = (count / metrics['total_decision_events'] * 100) if metrics['total_decision_events'] > 0 else 0
                report_lines.append(f"  - {action}: {count} ({percentage:.1f}%)")
        else:
            report_lines.append("  - No decision actions recorded.")
        report_lines.append("---")

        report_lines.append("## Component Usage Analytics")
        report_lines.append("### Component Target Frequencies (in KFM Decisions):")
        total_component_refs = sum(metrics['component_usage_counts'].values())
        if metrics['component_usage_counts']:
            for component, count in sorted(metrics['component_usage_counts'].items(), key=lambda item: item[1], reverse=True):
                percentage = (count / total_component_refs * 100) if total_component_refs > 0 else 0
                report_lines.append(f"  - {component}: {count} ({percentage:.1f}%)")
        else:
            report_lines.append("  - No component usage recorded in decisions.")
        report_lines.append("---")

        report_lines.append("## Task Performance Analytics")
        report_lines.append("### Task Requirement Satisfaction Score Distribution:")
        total_satisfaction_events = sum(metrics['task_requirement_satisfaction_distribution'].values())
        if metrics['task_requirement_satisfaction_distribution']:
            for score, count in sorted(metrics['task_requirement_satisfaction_distribution'].items()):
                percentage = (count / total_satisfaction_events * 100) if total_satisfaction_events > 0 else 0
                report_lines.append(f"  - \"{score}\": {count} ({percentage:.1f}%)")
        else:
            report_lines.append("  - No task requirement satisfaction data recorded.")
        report_lines.append("---")
        
        report_lines.append("## Agent Health & Errors")
        report_lines.append(f"- Total Errors Logged: {metrics['error_count']}")
        error_rate_per_entry = (metrics['error_count'] / metrics['total_log_entries_processed'] * 100) if metrics['total_log_entries_processed'] > 0 else 0
        report_lines.append(f"- Error Rate (per log entry): {error_rate_per_entry:.2f}%")

        return "\n".join(report_lines)

# Example Usage (for testing purposes):
if __name__ == '__main__':
    # Create some dummy log files for testing
    dummy_log_dir = "dummy_global_logs"
    os.makedirs(dummy_log_dir, exist_ok=True)
    log_file1_path = os.path.join(dummy_log_dir, "semantic_state_details_run1.log")
    log_file2_path = os.path.join(dummy_log_dir, "semantic_state_details_run2.log")

    dummy_logs1 = [
        {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run1", "kfm_action": {"action": "Keep", "component": "CompA", "confidence": 0.9}},
        {"event_tag": "execute_action_node_exit_success", "run_id": "run1", "calculated_metrics": {"task_requirement_satisfaction": "MetAll (2/2)"}},
        {"event_tag": "some_other_event", "run_id": "run1", "error": "An error occurred"},
        {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run1", "kfm_action": {"action": "Fuck", "component": "CompB", "confidence": 0.5}},
    ]
    dummy_logs2 = [
        {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "kfm_action": {"action": "Keep", "component": "CompA", "confidence": 0.95}},
        {"event_tag": "execute_action_node_exit_success", "run_id": "run2", "calculated_metrics": {"task_requirement_satisfaction": "MetSome (1/2) [Details: Unmet:1]"}},
        {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "kfm_action": {"action": "Marry", "component": "CompC", "confidence": 0.88}},
        {"event_tag": "execute_action_node_exit_success", "run_id": "run2", "calculated_metrics": {"task_requirement_satisfaction": "MetAll (3/3)"}},
        {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "error": "Bad thing"}
    ]

    with open(log_file1_path, 'w') as f1:
        for entry in dummy_logs1:
            f1.write(json.dumps(entry) + '\n')
    with open(log_file2_path, 'w') as f2:
        for entry in dummy_logs2:
            f2.write(json.dumps(entry) + '\n')

    print(f"Created dummy logs in {dummy_log_dir}")

    # Test with specific files
    service_files = GlobalAnalyticsService(log_files=[log_file1_path, log_file2_path])
    service_files.process_logs()
    report_files = service_files.generate_report_text()
    print("\n--- Report from Specific Files ---")
    print(report_files)

    # Test with directory
    service_dir = GlobalAnalyticsService(log_dir=dummy_log_dir, log_pattern="*.log")
    service_dir.process_logs()
    report_dir = service_dir.generate_report_text()
    print("\n--- Report from Directory Scan ---")
    print(report_dir)

    # Clean up dummy logs
    # import shutil
    # shutil.rmtree(dummy_log_dir)
    # print(f"Cleaned up {dummy_log_dir}") 