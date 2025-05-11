import pytest
from datetime import datetime, timezone
import re
from typing import Optional, List, Tuple, Pattern, Callable, Any, Dict

from src.verification.log_parsing.parsers import (
    JsonLineParser, 
    RegexLineParser, 
    GENERAL_BASE_LOG_REGEX,
    NODE_TRACE_PATTERNS, _create_node_trace_event,
    EXECUTION_ENGINE_PATTERNS, _create_execution_engine_event,
    KFM_AGENT_PATTERNS, _create_kfm_agent_event
)
from src.verification.log_parsing.data_structures import (
    LogEntry, 
    LlmApiEvent, 
    JsonLogPayload,
    NodeTraceEvent,
    ExecutionEngineEvent,
    KfmAgentEvent
)

NOW_AWARE = datetime.now(timezone.utc)

# --- Tests for JsonLineParser ---
class TestJsonLineParser:
    @pytest.fixture
    def parser(self):
        return JsonLineParser()

    def test_heuristic_matches_valid(self, parser):
        assert parser.heuristic_matches('{"key": "value"}') == True

    def test_heuristic_matches_invalid(self, parser):
        assert parser.heuristic_matches('not a json line') == False
        assert parser.heuristic_matches('{"key": "value"') == False # Missing brace

    def test_parse_llm_request_event(self, parser):
        log_line = (
            '{"timestamp": "2023-10-26T10:00:00.123Z", "level": "INFO", "logger": "llm_api", "message": "{\\\"event\\\": \\\"llm_request\\\", \\\"context\\\": {\\\"request_id\\\": \\\"req1\\\"}, \\\"request\\\": {\\\"prompt\\\": \\\"Test prompt\\\"}}"}'
        )
        entry = parser.parse_line(log_line, 1, "sample_llm.log")
        assert isinstance(entry, LlmApiEvent)
        assert entry.level == "INFO"
        assert entry.llm_data.event_type == "llm_request"
        assert entry.llm_data.context["request_id"] == "req1"
        assert entry.llm_data.request["prompt"] == "Test prompt"
        assert entry.timestamp == datetime(2023, 10, 26, 10, 0, 0, 123000, tzinfo=timezone.utc)

    def test_parse_llm_response_event(self, parser):
        log_line = (
            '{"timestamp": "2023-10-26T10:00:05.456Z", "level": "DEBUG", "message": "{\\\"event\\\": \\\"llm_response\\\", \\\"context\\\": {\\\"request_id\\\": \\\"req2\\\"}, \\\"response\\\": {\\\"text\\\": \\\"Test response\\\"}, \\\"metrics\\\": {\\\"duration_seconds\\\": 0.5}}"}'
        )
        entry = parser.parse_line(log_line, 2, "sample_llm.log")
        assert isinstance(entry, LlmApiEvent)
        assert entry.level == "DEBUG"
        assert entry.llm_data.event_type == "llm_response"
        assert entry.llm_data.response["text"] == "Test response"
        assert entry.llm_data.metrics["duration_seconds"] == 0.5

    def test_parse_llm_error_event(self, parser):
        log_line = (
            '{"timestamp": "2023-10-26T10:00:10.789Z", "level": "ERROR", "message": "{\\\"event\\\": \\\"llm_error\\\", \\\"context\\\": {\\\"request_id\\\": \\\"req3\\\"}, \\\"error\\\": {\\\"type\\\": \\\"APIError\\\", \\\"message\\\": \\\"Service unavailable\\\"}}"}'
        )
        entry = parser.parse_line(log_line, 3, "sample_llm.log")
        assert isinstance(entry, LlmApiEvent)
        assert entry.level == "ERROR"
        assert entry.llm_data.event_type == "llm_error"
        assert entry.llm_data.error["type"] == "APIError"

    def test_parse_invalid_json_line(self, parser):
        assert parser.parse_line("not json", 1) is None
        assert parser.parse_line('{"message": "{\\\"event\\\": \\\"valid_inner\\\"}", "timestamp": "invalid-ts"}', 1) # Valid JSON, invalid inner TS
        # For the above, it should still parse the JSON but use datetime.now() for timestamp.
        entry = parser.parse_line('{"message": "{\\\"event\\\": \\\"valid_inner\\\"}", "timestamp": "invalid-ts", "level": "INFO"}', 1)
        assert isinstance(entry, LlmApiEvent)
        assert entry.timestamp.tzinfo is timezone.utc # Should fallback to now_utc

    def test_parse_message_not_string(self, parser):
        log_line = '{"timestamp": "2023-10-26T10:00:00Z", "level": "INFO", "message": {"event": "not_a_string"}}'
        assert parser.parse_line(log_line, 1) is None

    def test_parse_inner_json_invalid(self, parser):
        log_line = '{"timestamp": "2023-10-26T10:00:00Z", "level": "INFO", "message": "not_valid_json_at_all"}'
        assert parser.parse_line(log_line, 1) is None

# --- Tests for RegexLineParser ---

# Mock Callbacks for testing RegexLineParser directly if needed, though testing via full patterns is better.

def _mock_callback_returns_logentry(match, timestamp, level, logger_name, source_file_path, line_number_in_file, captured_module_name, captured_line_in_module, raw_line_content):
    return LogEntry(timestamp=timestamp, level=level, raw_message=raw_line_content, source_file=source_file_path, source_line_number=line_number_in_file)

def _mock_callback_returns_none(match, timestamp, level, logger_name, source_file_path, line_number_in_file, captured_module_name, captured_line_in_module, raw_line_content):
    return None

class TestRegexLineParser:
    BASE_TIMESTAMP = "2023-10-26 10:00:00"
    BASE_TIMESTAMP_MS_DOT = "2023-10-26 10:00:00.123456"
    BASE_TIMESTAMP_MS_COMMA = "2023-10-26 10:00:00,123"

    @pytest.fixture
    def base_regex(self):
        return GENERAL_BASE_LOG_REGEX # From parsers.py

    def test_parse_timestamp_helper(self, base_regex):
        # This tests a hypothetical _parse_timestamp, assuming RegexLineParser instance
        # Actual testing happens via parse_line
        parser_instance = RegexLineParser(base_regex, []) # Dummy event_patterns
        
        dt = parser_instance._parse_timestamp(self.BASE_TIMESTAMP, 1, "test.log")
        assert dt == datetime(2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc)

        dt_ms_dot = parser_instance._parse_timestamp(self.BASE_TIMESTAMP_MS_DOT, 1, "test.log")
        assert dt_ms_dot == datetime(2023, 10, 26, 10, 0, 0, 123456, tzinfo=timezone.utc)

        dt_ms_comma = parser_instance._parse_timestamp(self.BASE_TIMESTAMP_MS_COMMA, 1, "test.log")
        assert dt_ms_comma == datetime(2023, 10, 26, 10, 0, 0, 123000, tzinfo=timezone.utc)
        
        dt_invalid = parser_instance._parse_timestamp("invalid date", 1, "test.log")
        assert (datetime.now(timezone.utc) - dt_invalid).total_seconds() < 1 # Should be very recent

    def test_heuristic_matches(self, base_regex):
        parser = RegexLineParser(base_regex, [])
        assert parser.heuristic_matches(f"{self.BASE_TIMESTAMP} [INFO] my.logger: Test message") == True
        assert parser.heuristic_matches("Not a matchable log line") == False

    # --- Test NodeTraceEvent parsing ---
    @pytest.fixture
    def node_trace_parser(self, base_regex):
        return RegexLineParser(base_regex, NODE_TRACE_PATTERNS)

    def test_parse_node_trace_entering(self, node_trace_parser):
        log_line = f"{self.BASE_TIMESTAMP_MS_DOT} [INFO] src.tracing (tracing.py:301): [corr:abc-123] Entering node my_node (exec:1)"
        entry = node_trace_parser.parse_line(log_line, 1, "trace.log")
        assert isinstance(entry, NodeTraceEvent)
        assert entry.event_name == "node_trace_event"
        assert entry.correlation_id == "abc-123"
        assert entry.node_name == "my_node"
        assert entry.event_status == "entering"
        assert entry.execution_count == 1
        assert entry.timestamp == datetime(2023,10,26,10,0,0,123456,tzinfo=timezone.utc)
        assert entry.raw_message == log_line

    def test_parse_node_trace_completed(self, node_trace_parser):
        log_line = f"{self.BASE_TIMESTAMP} [DEBUG] my.logger (module.py:10): [corr:def-456] Completed node other_node in 0.123s (exec:2)"
        entry = node_trace_parser.parse_line(log_line, 1, "trace.log")
        assert isinstance(entry, NodeTraceEvent)
        assert entry.correlation_id == "def-456"
        assert entry.node_name == "other_node"
        assert entry.event_status == "completed"
        assert entry.duration_seconds == 0.123
        assert entry.execution_count == 2

    def test_parse_node_trace_error(self, node_trace_parser):
        log_line = f"{self.BASE_TIMESTAMP_MS_COMMA} [ERROR] my.logger: [corr:ghi-789] Error in node error_node after 0.005s: Some error detail (exec:3)"
        entry = node_trace_parser.parse_line(log_line, 1, "trace.log")
        assert isinstance(entry, NodeTraceEvent)
        assert entry.correlation_id == "ghi-789"
        assert entry.node_name == "error_node"
        assert entry.event_status == "error"
        assert entry.duration_seconds == 0.005 # duration_error should be captured as duration
        assert entry.error_detail == "Some error detail"
        assert entry.execution_count == 3

    # --- Test ExecutionEngineEvent parsing ---
    @pytest.fixture
    def exec_engine_parser(self, base_regex):
        return RegexLineParser(base_regex, EXECUTION_ENGINE_PATTERNS)

    def test_parse_exec_engine_executing(self, exec_engine_parser):
        log_line = f"{self.BASE_TIMESTAMP} [INFO] ExecutionEngine (ee.py:50): Executing task with input (keys): [\"key1\", \"key2\"]"
        entry = exec_engine_parser.parse_line(log_line, 1, "ee.log")
        assert isinstance(entry, ExecutionEngineEvent)
        assert entry.engine_event_type == "executing_task"
        assert entry.input_keys == ["key1", "key2"]

    def test_parse_exec_engine_completed(self, exec_engine_parser):
        log_line = f"{self.BASE_TIMESTAMP} [INFO] ExecutionEngine: Task execution completed in 0.0012s."
        entry = exec_engine_parser.parse_line(log_line, 1, "ee.log")
        assert isinstance(entry, ExecutionEngineEvent)
        assert entry.engine_event_type == "task_completed"
        assert entry.duration_seconds == 0.0012

    # --- Test KfmAgentEvent parsing ---
    @pytest.fixture
    def kfm_agent_parser(self, base_regex):
        return RegexLineParser(base_regex, KFM_AGENT_PATTERNS)
    
    def test_parse_kfm_agent_conditional_result(self, kfm_agent_parser):
        log_line = f"{self.BASE_TIMESTAMP} [INFO] KFMAgent: ⚠️ CONDITIONAL RESULT: MY_ACTION"
        entry = kfm_agent_parser.parse_line(log_line, 1, "kfm.log")
        assert isinstance(entry, KfmAgentEvent)
        assert entry.agent_event_type == "conditional_result"
        assert entry.result == "MY_ACTION"

    def test_parse_kfm_agent_workflow_error(self, kfm_agent_parser):
        log_line = f"{self.BASE_TIMESTAMP} [ERROR] KFMAgent (agent.py:100): Workflow ending due to error: {{ \"type\": \"TestError\", \"message\": \"Something bad happened\" }}"
        entry = kfm_agent_parser.parse_line(log_line, 1, "kfm.log")
        assert isinstance(entry, KfmAgentEvent)
        assert entry.agent_event_type == "workflow_error"
        assert entry.error_payload == {"type": "TestError", "message": "Something bad happened"}

    def test_parse_kfm_agent_other_info(self, kfm_agent_parser):
        log_line = f"{self.BASE_TIMESTAMP} [DEBUG] KFMAgent: Some other informational message"
        entry = kfm_agent_parser.parse_line(log_line, 1, "kfm.log")
        assert isinstance(entry, KfmAgentEvent)
        assert entry.agent_event_type == "other_info"
        assert entry.details == "Some other informational message"
        assert entry.raw_message == log_line # Check raw message is preserved

    def test_no_match_returns_none(self, kfm_agent_parser):
        log_line = f"{self.BASE_TIMESTAMP} [INFO] SomeOtherLogger: This won\'t match KFM agent specific patterns"
        entry = kfm_agent_parser.parse_line(log_line, 1, "kfm.log")
        # This will be None because the message part "This won't match..." doesn't match any KFM_AGENT_PATTERNS
        # including the fallback (.*) because it is designed to be the last resort for KFMAgent logger.
        # If GENERAL_BASE_LOG_REGEX matches but specific message patterns don't, parse_line returns None.
        assert entry is None 

    def test_base_log_no_match(self, kfm_agent_parser):
        log_line = "This is not a standard log line format at all"
        entry = kfm_agent_parser.parse_line(log_line, 1, "kfm.log")
        assert entry is None 