from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, AwareDatetime # Use AwareDatetime for timezone-aware datetimes

class LogEntry(BaseModel):
    timestamp: AwareDatetime
    level: str
    raw_message: str
    source_file: Optional[str] = None # Name of the log file it came from
    source_line_number: Optional[int] = None # Line number in the original file, if available

class JsonLogPayload(BaseModel):
    event_type: str # e.g., llm_request, llm_response, llm_error
    context: Dict[str, Any]
    request: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None

class LlmApiEvent(LogEntry):
    event_name: Literal["llm_api_event"] = "llm_api_event" # To distinguish event types
    llm_data: JsonLogPayload

class NodeTraceEvent(LogEntry):
    event_name: Literal["node_trace_event"] = "node_trace_event"
    correlation_id: Optional[str] = None
    node_name: str
    event_status: Literal["entering", "completed", "error"]
    duration_seconds: Optional[float] = None
    error_detail: Optional[str] = None
    execution_count: Optional[int] = None # (exec:N) from trace log

class ExecutionEngineEvent(LogEntry):
    event_name: Literal["execution_engine_event"] = "execution_engine_event"
    engine_event_type: Literal["executing_task", "task_completed", "component_set", "initialized"]
    component_name: Optional[str] = None
    input_keys: Optional[List[str]] = None
    duration_seconds: Optional[float] = None # For task_completed

class KfmAgentEvent(LogEntry):
    event_name: Literal["kfm_agent_event"] = "kfm_agent_event"
    agent_event_type: Literal[
        "graph_compilation", 
        "conditional_evaluation", 
        "conditional_result", 
        "workflow_error",
        "other_info" # For generic info lines
    ]
    result: Optional[str] = None # For conditional_result
    error_payload: Optional[Dict[str, Any]] = None # For workflow_error
    details: Optional[str] = None # For other_info or compilation details

# Example of a more specific KFM decision event, if extractable
# class KfmDecisionEvent(KfmAgentEvent):
#     agent_event_type: Literal["kfm_decision"] = "kfm_decision"
#     decision_details: Dict[str, Any]


# A union type for all possible parsed log events, useful for type hinting
# ParsedLogEvent = Union[LlmApiEvent, NodeTraceEvent, ExecutionEngineEvent, KfmAgentEvent]
# We can add this later once all event types are finalized. 