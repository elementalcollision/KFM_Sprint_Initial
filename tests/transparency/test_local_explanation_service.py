import pytest
import json
import os
from unittest.mock import patch, mock_open

from src.transparency.local_explanation_service import LocalKfmExplanationService, DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG

# Helper to create a dummy log file with given content
@pytest.fixture
def create_dummy_log_file(tmp_path):
    def _create_dummy_log_file(filename, lines_content):
        log_file = tmp_path / filename
        with open(log_file, 'w') as f:
            for line in lines_content:
                f.write(json.dumps(line) + '\n')
        return str(log_file)
    return _create_dummy_log_file

class TestLocalKfmExplanationService:

    def test_init_default_log_path(self):
        service = LocalKfmExplanationService()
        assert service.log_file_path == DEFAULT_SEMANTIC_LOG_FILE

    def test_init_custom_log_path(self):
        custom_path = "/custom/path/to/logs.log"
        service = LocalKfmExplanationService(log_file_path=custom_path)
        assert service.log_file_path == custom_path

    def test_get_kfm_decision_context_log_file_not_found(self):
        service = LocalKfmExplanationService(log_file_path="non_existent_log_file.log")
        context = service.get_kfm_decision_context(run_id="run_123")
        assert context is None

    def test_get_kfm_decision_context_empty_log_file(self, create_dummy_log_file):
        log_path = create_dummy_log_file("empty.log", [])
        service = LocalKfmExplanationService(log_file_path=log_path)
        context = service.get_kfm_decision_context(run_id="run_123")
        assert context is None

    def test_get_kfm_decision_context_no_matching_run_id(self, create_dummy_log_file):
        logs = [
            {"run_id": "run_other", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": {"action": "Keep"}}
        ]
        log_path = create_dummy_log_file("data.log", logs)
        service = LocalKfmExplanationService(log_file_path=log_path)
        context = service.get_kfm_decision_context(run_id="run_123")
        assert context is None

    def test_get_kfm_decision_context_no_matching_event_tag(self, create_dummy_log_file):
        logs = [
            {"run_id": "run_123", "event_tag": "some_other_event_tag", "kfm_action": {"action": "Keep"}}
        ]
        log_path = create_dummy_log_file("data.log", logs)
        service = LocalKfmExplanationService(log_file_path=log_path)
        context = service.get_kfm_decision_context(run_id="run_123")
        assert context is None

    def test_get_kfm_decision_context_malformed_json_line(self, tmp_path):
        log_file = tmp_path / "malformed.log"
        with open(log_file, 'w') as f:
            f.write('{"run_id": "run_123", "event_tag": "' + DEFAULT_DECISION_EVENT_TAG + '", "kfm_action": {"action": "Keep"}}\n') # Valid
            f.write('this is not json\n') # Invalid
            f.write('{"run_id": "run_123", "event_tag": "' + DEFAULT_DECISION_EVENT_TAG + '", "kfm_action": {"action": "Kill"}}\n') # Valid
        
        service = LocalKfmExplanationService(log_file_path=str(log_file))
        # Should get the first valid entry
        context1 = service.get_kfm_decision_context(run_id="run_123", decision_index=0)
        assert context1 is not None
        assert context1["action"] == "Keep"
        # Should get the second valid entry (which is index 1 after filtering)
        context2 = service.get_kfm_decision_context(run_id="run_123", decision_index=1)
        assert context2 is not None
        assert context2["action"] == "Kill"

    def test_get_kfm_decision_context_single_match(self, create_dummy_log_file):
        decision_data = {"action": "Keep", "component": "CompA", "reasoning": "Good", "confidence": 0.9}
        logs = [
            {"run_id": "run_123", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": decision_data, "timestamp": "ts1", "task_name": "TaskA"}
        ]
        log_path = create_dummy_log_file("data.log", logs)
        service = LocalKfmExplanationService(log_file_path=log_path)
        context = service.get_kfm_decision_context(run_id="run_123", decision_index=0)
        assert context is not None
        assert context["run_id"] == "run_123"
        assert context["action"] == "Keep"
        assert context["component"] == "CompA"
        assert context["reasoning"] == "Good"
        assert context["confidence"] == 0.9
        assert context["timestamp"] == "ts1"
        assert context["task_name"] == "TaskA"
        assert context["decision_index_found"] == 0

    def test_get_kfm_decision_context_multiple_matches_indices(self, create_dummy_log_file):
        decision1 = {"action": "Keep", "component": "CompA", "confidence": 0.9}
        decision2 = {"action": "Kill", "component": "CompB", "confidence": 0.8}
        decision3 = {"action": "Fuck", "component": "CompC", "confidence": 0.7}
        logs = [
            {"run_id": "run_multi", "event_tag": "other_event"}, 
            {"run_id": "run_multi", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": decision1, "timestamp": "ts1"},
            {"run_id": "run_other", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": {"action":"Ignore"}}, 
            {"run_id": "run_multi", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": decision2, "timestamp": "ts2"},
            {"run_id": "run_multi", "event_tag": DEFAULT_DECISION_EVENT_TAG, "kfm_action": decision3, "timestamp": "ts3"}
        ]
        log_path = create_dummy_log_file("data_multi.log", logs)
        service = LocalKfmExplanationService(log_file_path=log_path)

        context1 = service.get_kfm_decision_context(run_id="run_multi", decision_index=0)
        assert context1["action"] == "Keep"
        assert context1["decision_index_found"] == 0

        context2 = service.get_kfm_decision_context(run_id="run_multi", decision_index=1)
        assert context2["action"] == "Kill"
        assert context2["decision_index_found"] == 1

        context3 = service.get_kfm_decision_context(run_id="run_multi", decision_index=2)
        assert context3["action"] == "Fuck"
        assert context3["decision_index_found"] == 2

        context_oom = service.get_kfm_decision_context(run_id="run_multi", decision_index=3)
        assert context_oom is None
        
        # Test with decision_index=None, should default to 0
        context_none_idx = service.get_kfm_decision_context(run_id="run_multi", decision_index=None)
        assert context_none_idx["action"] == "Keep"
        assert context_none_idx["decision_index_found"] == 0

    def test_format_decision_explanation_valid_context(self):
        service = LocalKfmExplanationService()
        context = {
            "run_id": "run_fmt_1", "timestamp": "2023-01-01T12:00:00Z", "decision_index_found": 0,
            "task_name": "Formatting Task", "action": "Keep", "component": "TestComponent",
            "confidence": 0.99, "reasoning": "It works well.",
            "input_data_summary": "Input A...", "current_task_requirements_summary": "Req B..."
        }
        explanation = service.format_decision_explanation(context)
        assert "Run ID: run_fmt_1" in explanation
        assert "Logged at: 2023-01-01T12:00:00Z" in explanation
        assert "Decision #1" in explanation # 0-indexed + 1
        assert "Task: 'Formatting Task'" in explanation
        assert "action 'Keep' for component 'TestComponent'" in explanation
        assert "Confidence: 0.99" in explanation
        assert "Reasoning: \"It works well.\"" in explanation
        assert "Input Summary: Input A..." in explanation
        assert "Requirements Summary: Req B..." in explanation

    def test_format_decision_explanation_none_context(self):
        service = LocalKfmExplanationService()
        explanation = service.format_decision_explanation(None)
        assert explanation == "No decision context found to format."

    def test_format_decision_explanation_missing_fields(self):
        service = LocalKfmExplanationService()
        context = {
            "run_id": "run_fmt_2", "timestamp": "2023-01-01T12:01:00Z", "decision_index_found": 1,
            "action": "Kill" # Missing many fields
        }
        explanation = service.format_decision_explanation(context)
        assert "Run ID: run_fmt_2" in explanation
        assert "Decision #2" in explanation
        assert "action 'Kill' for component 'N/A'" in explanation # Check defaults
        assert "Confidence: N/A" in explanation
        assert "Reasoning: \"N/A\"" in explanation

    def test_format_decision_explanation_non_float_confidence(self):
        service = LocalKfmExplanationService()
        context = {
            "run_id": "run_fmt_3", "timestamp": "2023-01-01T12:02:00Z", "decision_index_found": 0,
            "action": "Keep", "component": "TestComponent",
            "confidence": "High (Mistake)", # String instead of float
            "reasoning": "Typo in log."
        }
        explanation = service.format_decision_explanation(context)
        assert "Confidence: High (Mistake)" in explanation # Should use str() fallback 