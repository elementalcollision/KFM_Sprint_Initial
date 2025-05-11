import pytest
import json
import os
import shutil # For cleaning up dummy directories
from collections import Counter

from src.transparency.global_analytics_service import GlobalAnalyticsService, DEFAULT_LOG_PATTERN

@pytest.fixture
def create_dummy_log_files(tmp_path):
    """Creates a temporary directory with dummy log files for testing."""
    dummy_dir = tmp_path / "global_analytics_logs"
    dummy_dir.mkdir()

    log_contents = {
        "run1_semantic_state_details.log": [
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run1", "kfm_action": {"action": "Keep", "component": "CompA", "confidence": 0.9}},
            {"event_tag": "execute_action_node_exit_success", "run_id": "run1", "calculated_metrics": {"task_requirement_satisfaction": "MetAll (2/2)"}},
            {"event_tag": "some_other_event", "run_id": "run1", "error": "An error occurred"},
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run1", "kfm_action": {"action": "Fuck", "component": "CompB", "confidence": 0.5}},
        ],
        "run2_semantic_state_details.log": [
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "kfm_action": {"action": "Keep", "component": "CompA", "confidence": 0.95}},
            {"event_tag": "execute_action_node_exit_success", "run_id": "run2", "calculated_metrics": {"task_requirement_satisfaction": "MetSome (1/2) [Details: Unmet:1]"}},
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "kfm_action": {"action": "Marry", "component": "CompC", "confidence": 0.88}},
            {"event_tag": "execute_action_node_exit_success", "run_id": "run2", "calculated_metrics": {"task_requirement_satisfaction": "MetAll (3/3)"}},
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run2", "error": "Bad thing"} # Decision event can also have an error
        ],
        "malformed.log": [
            "this is not json",
            {"event_tag": "kfm_decision_node_exit_with_decision", "run_id": "run3", "kfm_action": {"action": "Kill", "component": "CompD", "confidence": 0.7}}
        ],
        "empty.log": []
    }

    file_paths = []
    for filename, entries in log_contents.items():
        file_path = dummy_dir / filename
        with open(file_path, 'w') as f:
            for entry in entries:
                if isinstance(entry, str): # For malformed line
                    f.write(entry + '\n')
                else:
                    f.write(json.dumps(entry) + '\n')
        file_paths.append(str(file_path))
    
    yield str(dummy_dir), file_paths # Yield dir path and list of created file paths

    # Teardown: remove the dummy directory
    # shutil.rmtree(dummy_dir) # Pytest tmp_path handles cleanup

class TestGlobalAnalyticsService:

    def test_init_with_log_files(self, create_dummy_log_files):
        _, file_paths = create_dummy_log_files
        service = GlobalAnalyticsService(log_files=[file_paths[0]])
        assert len(service.log_sources) == 1
        assert file_paths[0] in service.log_sources

    def test_init_with_log_dir(self, create_dummy_log_files):
        log_dir, _ = create_dummy_log_files
        service = GlobalAnalyticsService(log_dir=log_dir, log_pattern="*.log") # Match all logs in dir
        assert len(service.log_sources) >= 3 # run1, run2, malformed, empty
        # Check if at least one expected file is found (glob order can vary)
        assert any("run1_semantic_state_details.log" in s for s in service.log_sources)

    def test_init_no_sources(self):
        service = GlobalAnalyticsService() # No files, no dir
        assert not service.log_sources
        # Check for console warning (tricky to assert directly without capturing stdout)

    def test_init_bad_log_dir(self):
        service = GlobalAnalyticsService(log_dir="/non/existent/path/to/mars")
        assert not service.log_sources
        # Check for console warning

    def test_process_logs_and_get_aggregated_metrics(self, create_dummy_log_files):
        log_dir, _ = create_dummy_log_files
        service = GlobalAnalyticsService(log_dir=log_dir, log_pattern="*.log")
        service.process_logs()
        metrics = service.get_aggregated_metrics()

        assert metrics["total_log_sources_scanned"] == 4 # run1, run2, malformed, empty
        assert metrics["total_log_entries_processed"] == 9 # 4 from run1, 5 from run2, 1 valid from malformed (invalid line ignored)
        assert metrics["total_decision_events"] == 5 # 2 from run1, 2 from run2, 1 from malformed
        
        assert metrics["kfm_action_counts"] == Counter({"Keep": 2, "Fuck": 1, "Marry": 1, "Kill": 1})
        assert metrics["component_usage_counts"] == Counter({"CompA": 2, "CompB": 1, "CompC": 1, "CompD": 1})
        assert metrics["fuck_action_count"] == 1
        assert metrics["error_count"] == 2 # One in run1, one in run2 (associated with a decision)
        assert metrics["average_decision_confidence"] == pytest.approx((0.9 + 0.5 + 0.95 + 0.88 + 0.7) / 5, 0.001)
        assert metrics["task_requirement_satisfaction_distribution"] == Counter({
            "MetAll (2/2)": 1,
            "MetSome (1/2) [Details: Unmet:1]": 1,
            "MetAll (3/3)": 1
        })

    def test_process_logs_non_existent_file_in_list(self, tmp_path):
        valid_file = tmp_path / "valid.log"
        with open(valid_file, "w") as f: f.write(json.dumps({"event_tag": "kfm_decision_node_exit_with_decision", "kfm_action": {"action":"Keep"}})+"\n")
        
        service = GlobalAnalyticsService(log_files=[str(valid_file), "does_not_exist.log"])
        service.process_logs()
        metrics = service.get_aggregated_metrics()
        assert metrics["total_log_entries_processed"] == 1
        assert metrics["total_decision_events"] == 1

    def test_generate_report_text(self, create_dummy_log_files):
        log_dir, _ = create_dummy_log_files
        service = GlobalAnalyticsService(log_dir=log_dir, log_pattern="*.log")
        service.process_logs()
        report = service.generate_report_text()

        assert "# KFM Agent Global Analytics Report" in report
        assert "Total Log Entries Processed: 9" in report
        assert "Total KFM Decision Events: 5" in report
        assert "Average Decision Confidence: 0.786" in report # (0.9+0.5+0.95+0.88+0.7)/5 = 3.93/5 = 0.786
        assert "Keep: 2 (40.0%)" in report
        assert "Fuck: 1 (20.0%)" in report
        assert "CompA: 2 (40.0%)" in report # (2 / (2+1+1+1)) * 100
        assert "MetAll (2/2): 1 (33.3%)" in report
        assert "Total Errors Logged: 2" in report
        assert f"Error Rate (per log entry): {(2/9*100):.2f}%" in report

    def test_generate_report_no_data(self):
        service = GlobalAnalyticsService() # No logs
        service.process_logs()
        report = service.generate_report_text()
        assert "Total Log Entries Processed: 0" in report
        assert "Total KFM Decision Events: 0" in report
        assert "Average Decision Confidence: 0.000" in report # Avoid division by zero
        assert "No decision actions recorded." in report
        assert "No component usage recorded in decisions." in report
        assert "No task requirement satisfaction data recorded." in report 