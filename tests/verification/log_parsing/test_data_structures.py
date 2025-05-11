import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from src.verification.log_parsing.data_structures import (
    LogEntry,
    JsonLogPayload,
    LlmApiEvent,
    NodeTraceEvent,
    ExecutionEngineEvent,
    KfmAgentEvent
)

# Get a current aware datetime for testing
NOW_AWARE = datetime.now(timezone.utc)

def test_log_entry_creation():
    entry = LogEntry(
        timestamp=NOW_AWARE,
        level="INFO",
        raw_message="This is a raw message.",
        source_file="test.log",
        source_line_number=10
    )
    assert entry.timestamp == NOW_AWARE
    assert entry.level == "INFO"
    assert entry.raw_message == "This is a raw message."
    assert entry.source_file == "test.log"
    assert entry.source_line_number == 10

def test_log_entry_required_fields():
    with pytest.raises(ValidationError):
        LogEntry(timestamp=NOW_AWARE, level="INFO") # raw_message is missing
    with pytest.raises(ValidationError):
        LogEntry(level="INFO", raw_message="msg") # timestamp is missing
    with pytest.raises(ValidationError):
        LogEntry(timestamp=NOW_AWARE, raw_message="msg") # level is missing

def test_json_log_payload_creation():
    payload = JsonLogPayload(
        event_type="llm_request",
        context={"request_id": "123"},
        request={"prompt": "Hello"}
    )
    assert payload.event_type == "llm_request"
    assert payload.context == {"request_id": "123"}
    assert payload.request == {"prompt": "Hello"}
    assert payload.response is None

def test_llm_api_event_creation():
    payload = JsonLogPayload(event_type="llm_response", context={}, response={"text": "World"})
    event = LlmApiEvent(
        timestamp=NOW_AWARE,
        level="DEBUG",
        raw_message="{}",
        llm_data=payload
    )
    assert event.event_name == "llm_api_event"
    assert event.llm_data.response == {"text": "World"}
    assert event.level == "DEBUG"

def test_node_trace_event_creation():
    event = NodeTraceEvent(
        timestamp=NOW_AWARE,
        level="INFO",
        raw_message="trace message",
        correlation_id="corr-456",
        node_name="reflection_node",
        event_status="entering"
    )
    assert event.event_name == "node_trace_event"
    assert event.node_name == "reflection_node"
    assert event.event_status == "entering"
    assert event.correlation_id == "corr-456"

def test_execution_engine_event_creation():
    event = ExecutionEngineEvent(
        timestamp=NOW_AWARE,
        level="INFO",
        raw_message="exec message",
        engine_event_type="executing_task",
        component_name="my_component",
        input_keys=["key1", "key2"]
    )
    assert event.event_name == "execution_engine_event"
    assert event.engine_event_type == "executing_task"
    assert event.component_name == "my_component"

def test_kfm_agent_event_creation():
    event = KfmAgentEvent(
        timestamp=NOW_AWARE,
        level="WARN",
        raw_message="kfm message",
        agent_event_type="conditional_result",
        result="CONTINUE"
    )
    assert event.event_name == "kfm_agent_event"
    assert event.agent_event_type == "conditional_result"
    assert event.result == "CONTINUE" 