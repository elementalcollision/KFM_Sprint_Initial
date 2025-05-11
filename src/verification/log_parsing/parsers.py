# Will contain BaseLogParser, JsonLineParser, RegexLineParser 

from abc import ABC, abstractmethod
from typing import Iterator, Optional, Type, List, Tuple, Pattern, Callable, Any, Dict, Literal
from .data_structures import LogEntry, LlmApiEvent, JsonLogPayload, NodeTraceEvent, ExecutionEngineEvent, KfmAgentEvent
import json
from datetime import datetime, timezone
import re
import logging

from src.core.exceptions import LogParsingError

logger = logging.getLogger(__name__)

class BaseLogParser(ABC):
    """Abstract base class for log parsers."""

    @abstractmethod
    def parse_line(self, line: str, line_number: int, source_file: Optional[str] = None) -> Optional[LogEntry]:
        """Parses a single log line and returns a LogEntry object or None if parsing fails."""
        pass

    def heuristic_matches(self, line: str) -> bool:
        """Optional: Quickly checks if this parser is likely the correct one for the given line."""
        return True # Default to True, meaning any parser could potentially match

    def parse_file(self, file_path: str) -> Iterator[LogEntry]:
        """Parses an entire log file line by line."""
        logger.info(f"Starting to parse file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line_content in enumerate(f):
                    entry = self.parse_line(line_content.strip(), line_number=i + 1, source_file=file_path)
                    if entry:
                        yield entry
            logger.info(f"Successfully finished parsing file: {file_path}")
        except FileNotFoundError as e:
            logger.error(f"Log file not found: {file_path}", exc_info=True)
            raise LogParsingError(f"Log file not found: {file_path}") from e
        except IOError as e: # Catch other IO errors like permission issues
            logger.error(f"IOError parsing file {file_path}: {e}", exc_info=True)
            raise LogParsingError(f"IOError reading log file '{file_path}': {e}") from e
        except Exception as e: # Catch any other unexpected error during file processing
            logger.error(f"Unexpected error parsing file {file_path}: {e}", exc_info=True)
            raise LogParsingError(f"Unexpected error processing log file '{file_path}': {e}") from e

from .data_structures import LlmApiEvent, JsonLogPayload

class JsonLineParser(BaseLogParser):
    """Parses logs where each line is a JSON object, potentially with nested JSON in a 'message' field."""

    def heuristic_matches(self, line: str) -> bool:
        stripped_line = line.strip()
        return stripped_line.startswith('{') and stripped_line.endswith('}')

    def parse_line(self, line: str, line_number: int, source_file: Optional[str] = None) -> Optional[LlmApiEvent]:
        if not line.strip(): # Skip genuinely empty lines silently
            return None
        try:
            outer_data = json.loads(line)
            raw_message_str = outer_data.get('message')

            if not isinstance(raw_message_str, str):
                logger.warning(f"'message' field is not a string in line {line_number} of {source_file}. Line: '{line[:100]}...'", exc_info=False) # No need for stack trace here
                return None 
            
            inner_payload_data = json.loads(raw_message_str)
            
            timestamp_str = outer_data.get('timestamp')
            parsed_timestamp: datetime
            if timestamp_str:
                try:
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    parsed_timestamp = datetime.fromisoformat(timestamp_str)
                    if parsed_timestamp.tzinfo is None:
                         parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)
                except ValueError as ve_ts:
                    logger.warning(f"Invalid timestamp format '{timestamp_str}' in {source_file}:{line_number}. Error: {ve_ts}. Using current time.")
                    parsed_timestamp = datetime.now(timezone.utc)
            else:
                logger.warning(f"Missing timestamp in {source_file}:{line_number}. Using current time.")
                parsed_timestamp = datetime.now(timezone.utc)

            log_entry_base_data = {
                "timestamp": parsed_timestamp,
                "level": outer_data.get('level', 'UNKNOWN').upper(),
                "raw_message": line, 
                "source_file": source_file,
                "source_line_number": line_number
            }
            
            json_payload = JsonLogPayload(**inner_payload_data)
            
            return LlmApiEvent(
                **log_entry_base_data, 
                llm_data=json_payload
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSONDecodeError in {source_file}:{line_number}: {e}. Line: '{line[:100]}...'")
            return None
        except Exception as e: # Catch other errors like Pydantic validation if inner_payload_data is bad
            logger.error(f"Error parsing JSON line {line_number} in {source_file}: {e}. Line: '{line[:100]}...'", exc_info=True)
            return None

# Commenting out for now due to persistent linter issues not reflecting actual syntax error.
# MatchObjectToModelCallable = Callable[
#     [
#         re.Match,             # The regex match object for the event-specific pattern
#         datetime,             # Parsed timestamp (timezone-aware)
#         str,                  # Log level from base pattern
#         str,                  # Logger name from base pattern
#         Optional[str],        # Source file path (overall file)
#         int,                  # Line number in the source file
#         Optional[str],        # Captured module name from base pattern (e.g., 'module.py')
#         Optional[int],        # Captured line number in module from base pattern
#         str                   # Raw stripped log line content
#     ],
#     Optional[LogEntry]        # Returns a LogEntry-derived model or None
# ]

class RegexLineParser(BaseLogParser):
    """Parses plain text logs using a list of configured regex patterns and constructor callbacks."""

    def __init__(self, 
                 base_log_pattern: Pattern[str], 
                 event_patterns: List[Tuple[Pattern[str], Callable[..., Optional[LogEntry]]]], # Using Callable[..., Optional[LogEntry]]
                 default_timestamp_format: str = "%Y-%m-%d %H:%M:%S"):
        """
        Args:
            base_log_pattern: A regex to capture common log line parts like timestamp, level, logger, message.
                              It MUST capture named groups: 'timestamp', 'level', 'logger_name', 'message'.
                              Optionally: 'module_py' and 'line_no' for source file info.
            event_patterns: A list of tuples. Each tuple contains:
                - A compiled regex pattern to match against the 'message' part of the log line.
                - A callback function that takes (match_object, parsed_timestamp, level, logger_name, 
                                             source_file_path, line_number_in_file, 
                                             captured_module_name, captured_line_in_module, raw_line_content) 
                  and returns a specific LogEntry model (e.g., NodeTraceEvent) or None.
            default_timestamp_format: Strptime format for parsing the 'timestamp' group from base_log_pattern.
                                      The default assumes a format like '2025-05-06 15:40:25'.
                                      Microseconds can be included with '.%f' or ',%f'.
        """
        self.base_log_pattern = base_log_pattern
        self.event_patterns = event_patterns
        self.default_timestamp_format = default_timestamp_format
        logger.debug(f"RegexLineParser initialized with base pattern: '{base_log_pattern.pattern}' and {len(event_patterns)} event patterns.")

    def heuristic_matches(self, line: str) -> bool:
        return bool(self.base_log_pattern.match(line.strip()))

    def _parse_timestamp(self, timestamp_str: str, line_number: int, source_file: Optional[str]) -> datetime:
        base_format_no_ms = self.default_timestamp_format.split('.')[0].split(',')[0]
        formats_to_try = [
            self.default_timestamp_format, # Try the provided default first
            base_format_no_ms + ".%f", 
            base_format_no_ms + ",%f", 
            base_format_no_ms
        ]
        # Remove duplicates if default_timestamp_format was already one of the generated ones
        unique_formats_to_try = list(dict.fromkeys(formats_to_try).keys()) 
        
        for fmt in unique_formats_to_try:
            try: 
                dt_naive = datetime.strptime(timestamp_str, fmt)
                return dt_naive.replace(tzinfo=timezone.utc) # Assume UTC if parsed as naive
            except ValueError: 
                continue
        logger.warning(f"Timestamp parse error in {source_file}:{line_number} for value '{timestamp_str}' using formats {unique_formats_to_try}. Using current time.")
        return datetime.now(timezone.utc)

    def parse_line(self, line: str, line_number: int, source_file: Optional[str] = None) -> Optional[LogEntry]:
        stripped_line = line.strip()
        if not stripped_line: return None
        
        base_match = self.base_log_pattern.match(stripped_line)
        if not base_match:
            logger.debug(f"Line {line_number} in {source_file} did not match base regex pattern: '{stripped_line[:100]}...'")
            return None

        base_groups = base_match.groupdict()
        timestamp_str = base_groups.get('timestamp')
        log_level = base_groups.get('level', 'INFO').upper()
        logger_name_val = base_groups.get('logger_name', 'UNKNOWN') # Renamed to avoid conflict with module logger
        message_content = base_groups.get('message', '').strip()
        
        module_py = base_groups.get('module_py')
        line_no_module_str = base_groups.get('line_no')
        parsed_line_in_module = None
        if line_no_module_str:
            try:
                parsed_line_in_module = int(line_no_module_str)
            except ValueError:
                logger.warning(f"Could not parse module line number '{line_no_module_str}' as int in {source_file}:{line_number}")
                pass 

        parsed_dt = self._parse_timestamp(timestamp_str, line_number, source_file) if timestamp_str else datetime.now(timezone.utc)
        if not timestamp_str:
             logger.warning(f"Missing timestamp in {source_file}:{line_number}. Using current time.")

        for event_pattern, constructor_callback in self.event_patterns:
            event_match = event_pattern.fullmatch(message_content) # Use fullmatch for message part
            if event_match:
                try:
                    entry = constructor_callback(
                        match=event_match, 
                        timestamp=parsed_dt, 
                        level=log_level, 
                        logger_name=logger_name_val, 
                        source_file_path=source_file, 
                        line_number_in_file=line_number,
                        captured_module_name=module_py,
                        captured_line_in_module=parsed_line_in_module,
                        raw_line_content=stripped_line
                    )
                    if entry:
                        logger.debug(f"Successfully parsed line {line_number} in {source_file} with pattern '{event_pattern.pattern}' as {entry.__class__.__name__}")
                    return entry
                except Exception as e:
                    logger.error(f"Callback error for {source_file}:{line_number} with pattern '{event_pattern.pattern}'. Error: {e}. Message: '{message_content[:100]}...'", exc_info=True)
                    # Continue to try other patterns if a callback fails, as it might be a very specific sub-pattern error
                    continue 
        
        logger.debug(f"Line {line_number} in {source_file} matched base pattern but no event patterns: '{message_content[:100]}...'")
        return None


# Base pattern for logs like: YYYY-MM-DD HH:MM:SS [LEVEL] LOGGER_NAME (module.py:line): Message
# Updated to be more robust for optional parts and timestamp variations.
GENERAL_BASE_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:[,.]\d{1,6})?)\s+\[(?P<level>\w+)\]\s+(?P<logger_name>[\w.<>:\s-]+)(?:\s+\((?P<module_py>[\w_.<>]+\.py):(?P<line_no>\d+)\))?:\s*(?P<message>.*)$"
)

# --- Define constructor callbacks for each event type ---

def _create_node_trace_event(match: re.Match, timestamp: datetime, level: str, logger_name: str, 
                             source_file_path: Optional[str], line_number_in_file: int, 
                             captured_module_name: Optional[str], captured_line_in_module: Optional[int],
                             raw_line_content: str) -> Optional[NodeTraceEvent]:
    groups = match.groupdict()
    status_map = {"Entering": "entering", "Completed": "completed", "Error in": "error"}
    event_status_key = groups.get("status_keyword")
    
    # Handle cases where duration might be captured as duration or duration_error
    duration_str = groups.get("duration") or groups.get("duration_error")
    duration_val = float(duration_str.rstrip('s')) if duration_str else None

    if event_status_key not in status_map:
        return None
    
    return NodeTraceEvent(
        timestamp=timestamp, level=level, raw_message=raw_line_content,
        source_file=source_file_path, source_line_number=line_number_in_file,
        correlation_id=groups.get("corr_id"),
        node_name=groups.get("node_name"),
        event_status=status_map[event_status_key],
        duration_seconds=duration_val,
        error_detail=groups.get("error_detail"),
        execution_count=int(groups["exec_count"]) if groups.get("exec_count") and groups["exec_count"].isdigit() else None
    )

def _create_execution_engine_event(match: re.Match, timestamp: datetime, level: str, logger_name: str, 
                                   source_file_path: Optional[str], line_number_in_file: int,
                                   captured_module_name: Optional[str], captured_line_in_module: Optional[int],
                                   raw_line_content: str) -> Optional[ExecutionEngineEvent]:
    groups = match.groupdict()
    message_content = match.string # This is the message part that the event_pattern matched

    engine_event_type: Optional[Literal["executing_task", "task_completed", "component_set", "initialized"]] = None
    component_name_val = groups.get("component_name")
    input_keys_str = groups.get("input_keys")
    duration_val_str = groups.get("duration")

    if groups.get('keyword_executing_task'): engine_event_type = "executing_task"
    elif groups.get('keyword_task_completed'): engine_event_type = "task_completed"
    elif groups.get('keyword_initialized'): engine_event_type = "initialized"
    elif groups.get('keyword_using_component'): engine_event_type = "component_set"
    else:
        return None # Should not happen if regex is specific enough

    input_keys_list = None
    if input_keys_str:
        try:
            import ast
            input_keys_list = ast.literal_eval(input_keys_str)
        except (ValueError, SyntaxError):
            input_keys_list = [k.strip(" '\"") for k in input_keys_str.strip("[]").split(',') if k.strip()]

    return ExecutionEngineEvent(
        timestamp=timestamp, level=level, raw_message=raw_line_content,
        source_file=source_file_path, source_line_number=line_number_in_file,
        engine_event_type=engine_event_type,
        component_name=component_name_val,
        input_keys=input_keys_list,
        duration_seconds=float(duration_val_str.rstrip('s')) if duration_val_str else None
    )

def _create_kfm_agent_event(match: re.Match, timestamp: datetime, level: str, logger_name: str, 
                            source_file_path: Optional[str], line_number_in_file: int,
                            captured_module_name: Optional[str], captured_line_in_module: Optional[int],
                            raw_line_content: str) -> Optional[KfmAgentEvent]:
    groups = match.groupdict()
    parsed_agent_event_type: Literal["graph_compilation", "conditional_evaluation", "conditional_result", "workflow_error", "other_info"] = "other_info"
    details_val: Optional[str] = raw_line_content # Default to full raw line for 'other_info' or if no specific detail extracted
    result_val, error_payload_json_str = groups.get("cond_result"), groups.get("error_payload_json")
    error_payload_dict: Optional[Dict[str, Any]] = None

    if groups.get("keyword_cond_eval"): parsed_agent_event_type, details_val = "conditional_evaluation", None
    elif result_val: parsed_agent_event_type, details_val = "conditional_result", None
    elif error_payload_json_str:
        parsed_agent_event_type, details_val = "workflow_error", None
        try: error_payload_dict = json.loads(error_payload_json_str)
        except json.JSONDecodeError: error_payload_dict = {"raw_error_string": error_payload_json_str}
    elif groups.get("keyword_graph_creating") or groups.get("keyword_graph_compiled"): 
        parsed_agent_event_type = "graph_compilation"
        details_val = raw_line_content # Keep full message for compilation details
    elif groups.get("other_message_content") and parsed_agent_event_type == "other_info":
        details_val = groups.get("other_message_content")
    
    return KfmAgentEvent(
        timestamp=timestamp, level=level, raw_message=raw_line_content,
        source_file=source_file_path, source_line_number=line_number_in_file,
        agent_event_type=parsed_agent_event_type,
        result=result_val,
        error_payload=error_payload_dict,
        details=details_val
    )

# Define specific regex patterns for the 'message' part of different log types

# For src.tracing.log
NODE_TRACE_PATTERNS = [
    (re.compile(r"^\[corr:(?P<corr_id>[^]]+)\]\s+(?P<status_keyword>Entering|Completed|Error in) node (?P<node_name>\S+)(?:(?:\s+in|\s+after)\s+(?P<duration>[\d.]+s))?(?:\s*:\s*(?P<error_detail>.+?))?\s+\(exec:(?P<exec_count>\d+)\)$"), _create_node_trace_event)
]

# For ExecutionEngine.log
EXECUTION_ENGINE_PATTERNS = [
    (re.compile(r"^(?P<keyword_executing_task>Executing task with input \(keys\)):\s+(?P<input_keys>\[.*?\])$"), _create_execution_engine_event),
    (re.compile(r"^(?P<keyword_task_completed>Task execution completed in)\s+(?P<duration>[\d.]+)s\.$"), _create_execution_engine_event),
    (re.compile(r"^(?P<keyword_initialized>ExecutionEngine initialized\. Active component):\s+(?P<component_name>\S+)$"), _create_execution_engine_event),
    (re.compile(r"^(?P<keyword_using_component>Using active component):\s+(?P<component_name>\S+)$"), _create_execution_engine_event)
]

# For KFMAgent.log
KFM_AGENT_PATTERNS = [
    (re.compile(r"^(?P<keyword_cond_eval>⚠️ CONDITIONAL: Evaluating workflow continuation)$"), _create_kfm_agent_event),
    (re.compile(r"^⚠️ CONDITIONAL RESULT:\s+(?P<cond_result>\S+)$"), _create_kfm_agent_event),
    (re.compile(r"^Workflow ending due to error:\s+(?P<error_payload_json>\{.*\})$"), _create_kfm_agent_event),
    (re.compile(r"^(?P<keyword_graph_creating>Creating KFM Agent graph\.\.\.)$"), _create_kfm_agent_event),
    (re.compile(r"^(?P<keyword_graph_compiled>LangGraph application successfully compiled)$"), _create_kfm_agent_event),
    (re.compile(r"^(?P<other_message_content>.*)$"), _create_kfm_agent_event), 
]

# --- RegexLineParser will be added below --- 