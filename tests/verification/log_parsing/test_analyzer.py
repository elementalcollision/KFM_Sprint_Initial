import pytest
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from src.verification.log_parsing.analyzer import LogFileProcessor, AutomatedVerificationLogAnalyzer
from src.verification.log_parsing.parsers import JsonLineParser, RegexLineParser, GENERAL_BASE_LOG_REGEX, NODE_TRACE_PATTERNS, EXECUTION_ENGINE_PATTERNS, KFM_AGENT_PATTERNS
from src.verification.log_parsing.data_structures import LogEntry, LlmApiEvent, NodeTraceEvent, ExecutionEngineEvent, KfmAgentEvent

# Sample log content
SAMPLE_LLM_API_LOG_CONTENT = [
    '{"timestamp": "2023-11-01T10:00:00.000Z", "level": "INFO", "message": "{\\\"event\\\": \\\"llm_request\\\", \\\"context\\\": {\\\"request_id\\\": \\\"llm1\\\"}, \\\"request\\\": {\\\"prompt\\\": \\\"P1\\\"}}"}',
    '{"timestamp": "2023-11-01T10:00:01.000Z", "level": "INFO", "message": "{\\\"event\\\": \\\"llm_response\\\", \\\"context\\\": {\\\"request_id\\\": \\\"llm1\\\"}, \\\"response\\\": {\\\"text\\\": \\\"R1\\\"}}"}'
]

SAMPLE_TRACING_LOG_CONTENT = [
    "2023-11-01 10:00:02.123 [INFO] src.tracing (t.py:1): [corr:trace1] Entering node node_A (exec:1)",
    "2023-11-01 10:00:03.456 [INFO] src.tracing (t.py:2): [corr:trace1] Completed node node_A in 1.333s (exec:1)"
]

SAMPLE_EXEC_ENGINE_LOG_CONTENT = [
    "2023-11-01 10:00:04 [INFO] ExecutionEngine (ee.py:10): Executing task with input (keys): [\"input1\"]",
    "2023-11-01 10:00:05 [INFO] ExecutionEngine (ee.py:20): Task execution completed in 1.000s."
]

SAMPLE_KFM_AGENT_LOG_CONTENT = [
    "2023-11-01 10:00:06 [INFO] KFMAgent (kfm.py:30): ⚠️ CONDITIONAL RESULT: ACTION_X",
    "2023-11-01 10:00:07 [ERROR] KFMAgent (kfm.py:40): Workflow ending due to error: { \"type\": \"KfmError\" }"
]

EMPTY_LOG_CONTENT = ""
UNKNOWN_FORMAT_LOG_CONTENT = "This is some unknown log format."

@pytest.fixture
def sample_log_files(tmp_path: Path) -> Dict[str, Path]:
    files = {
        "llm_api.log": tmp_path / "llm_api.log",
        "tracing.log": tmp_path / "tracing.log",
        "exec_engine.log": tmp_path / "exec_engine.log",
        "kfm_agent.log": tmp_path / "kfm_agent.log",
        "empty.log": tmp_path / "empty.log",
        "unknown.log": tmp_path / "unknown.log"
    }
    files["llm_api.log"].write_text("\n".join(SAMPLE_LLM_API_LOG_CONTENT))
    files["tracing.log"].write_text("\n".join(SAMPLE_TRACING_LOG_CONTENT))
    files["exec_engine.log"].write_text("\n".join(SAMPLE_EXEC_ENGINE_LOG_CONTENT))
    files["kfm_agent.log"].write_text("\n".join(SAMPLE_KFM_AGENT_LOG_CONTENT))
    files["empty.log"].write_text(EMPTY_LOG_CONTENT)
    files["unknown.log"].write_text(UNKNOWN_FORMAT_LOG_CONTENT)
    return files

@pytest.fixture
def default_parsers() -> List[BaseLogParser]:
    return [
        JsonLineParser(),
        RegexLineParser(GENERAL_BASE_LOG_REGEX, NODE_TRACE_PATTERNS),
        RegexLineParser(GENERAL_BASE_LOG_REGEX, EXECUTION_ENGINE_PATTERNS),
        RegexLineParser(GENERAL_BASE_LOG_REGEX, KFM_AGENT_PATTERNS)
    ]

class TestLogFileProcessor:
    def test_process_file_selects_correct_parser(self, sample_log_files, default_parsers):
        # Test with a specific parser for JSON
        json_parser = JsonLineParser()
        processor_json = LogFileProcessor(parsers=[json_parser])
        events = list(processor_json.process_file(str(sample_log_files["llm_api.log"])))
        assert len(events) == 2
        assert all(isinstance(e, LlmApiEvent) for e in events)

        # Test with a specific parser for NodeTrace (Regex based)
        node_trace_parser_instance = RegexLineParser(GENERAL_BASE_LOG_REGEX, NODE_TRACE_PATTERNS)
        processor_trace = LogFileProcessor(parsers=[node_trace_parser_instance])
        events_trace = list(processor_trace.process_file(str(sample_log_files["tracing.log"])))
        assert len(events_trace) == 2
        assert all(isinstance(e, NodeTraceEvent) for e in events_trace)
    
    def test_process_empty_file(self, default_parsers, sample_log_files):
        processor = LogFileProcessor(parsers=default_parsers)
        events = list(processor.process_file(str(sample_log_files["empty.log"])))
        assert len(events) == 0

    def test_process_unknown_format_file(self, default_parsers, sample_log_files):
        # Relies on heuristic_matches not finding a suitable parser
        # Current LogFileProcessor might return empty if no heuristic matches strictly
        processor = LogFileProcessor(parsers=default_parsers) # default_parsers list
        # The RegexLineParser with GENERAL_BASE_LOG_REGEX might match the line if it vaguely looks like a log
        # but then fail to match specific event_patterns. This will result in 0 events.
        events = list(processor.process_file(str(sample_log_files["unknown.log"])))
        assert len(events) == 0 

    def test_process_file_not_found(self, default_parsers):
        processor = LogFileProcessor(parsers=default_parsers)
        events = list(processor.process_file("non_existent_file.log"))
        assert len(events) == 0


class TestAutomatedVerificationLogAnalyzer:
    @pytest.fixture
    def analyzer(self) -> AutomatedVerificationLogAnalyzer:
        # Uses default config which sets up parsers for known log types
        return AutomatedVerificationLogAnalyzer()

    def test_initialization_default_config(self, analyzer):
        assert analyzer.parser_config is not None
        assert len(analyzer.parser_config) > 0 # Default config should have entries
        assert len(analyzer.all_log_events) == 0

    def test_process_single_known_log_file(self, analyzer, sample_log_files):
        analyzer.process_log_source(str(sample_log_files["llm_api.log"]))
        events = analyzer.get_all_events()
        assert len(events) == 2
        assert isinstance(events[0], LlmApiEvent)

    def test_process_directory(self, analyzer, sample_log_files, tmp_path):
        # tmp_path already contains all sample_log_files
        analyzer.process_log_source(str(tmp_path))
        events = analyzer.get_all_events()
        # Expected: 2 llm + 2 trace + 2 exec_engine + 2 kfm_agent = 8 events
        # empty.log and unknown.log should yield 0 events from configured parsers
        assert len(events) == 8
        
        event_types = [type(e) for e in events]
        assert event_types.count(LlmApiEvent) == 2
        assert event_types.count(NodeTraceEvent) == 2
        assert event_types.count(ExecutionEngineEvent) == 2
        assert event_types.count(KfmAgentEvent) == 2

    def test_clear_events(self, analyzer, sample_log_files):
        analyzer.process_log_source(str(sample_log_files["llm_api.log"]))
        assert len(analyzer.get_all_events()) > 0
        analyzer.clear_events()
        assert len(analyzer.get_all_events()) == 0

    def test_filter_events_by_type(self, analyzer, sample_log_files, tmp_path):
        analyzer.process_log_source(str(tmp_path))
        llm_events = analyzer.filter_events(event_type=LlmApiEvent)
        assert len(llm_events) == 2
        assert all(isinstance(e, LlmApiEvent) for e in llm_events)

        node_trace_events = analyzer.filter_events(event_type=NodeTraceEvent)
        assert len(node_trace_events) == 2
        assert all(isinstance(e, NodeTraceEvent) for e in node_trace_events)

    def test_filter_events_by_attribute(self, analyzer, sample_log_files, tmp_path):
        analyzer.process_log_source(str(tmp_path))
        
        # Filter NodeTraceEvents with node_name='node_A'
        node_a_events = analyzer.filter_events(event_type=NodeTraceEvent, node_name="node_A")
        assert len(node_a_events) == 2 
        assert node_a_events[0].node_name == "node_A"
        assert node_a_events[1].node_name == "node_A"

        # Filter LlmApiEvents with specific request_id from context
        # This requires a bit more careful attribute checking as request_id is nested
        # For this simple filter, we assume direct attribute or a more complex filter function if needed.
        # Let's test filtering by a direct attribute like 'level' for simplicity here.
        info_llm_events = analyzer.filter_events(event_type=LlmApiEvent, level="INFO")
        assert len(info_llm_events) == 2 # Both sample LLM events are INFO

    def test_get_all_events_sorting(self, analyzer, sample_log_files, tmp_path):
        analyzer.process_log_source(str(tmp_path))
        events_sorted = analyzer.get_all_events(sort_by_timestamp=True)
        events_unsorted = analyzer.get_all_events(sort_by_timestamp=False)

        assert len(events_sorted) == 8
        if len(events_sorted) > 1:
            for i in range(len(events_sorted) - 1):
                assert events_sorted[i].timestamp <= events_sorted[i+1].timestamp
        
        # Check if unsorted is different; this is not guaranteed if files processed in order
        # but good to have the option.
        assert len(events_unsorted) == 8

    def test_process_non_existent_source(self, analyzer, capsys):
        analyzer.process_log_source("non_existent_dir_or_file")
        captured = capsys.readouterr()
        assert "Warning: Log source path does not exist" in captured.out
        assert len(analyzer.get_all_events()) == 0 