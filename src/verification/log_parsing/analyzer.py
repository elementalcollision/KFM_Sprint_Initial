# Will contain LogFileProcessor and AutomatedVerificationLogAnalyzer 

from typing import List, Optional, Iterator, Dict, Type, Pattern
from .parsers import BaseLogParser, JsonLineParser, RegexLineParser # Assuming parsers.py
from .data_structures import LogEntry # Assuming data_structures.py
import os
import re # For example regexes if needed for instantiation here

# --- Import example patterns and callbacks if they are to be used for default instantiation ---
# This part might be better handled by a dedicated configuration/factory module later
from .parsers import (
    GENERAL_BASE_LOG_REGEX,
    NODE_TRACE_PATTERNS, _create_node_trace_event,
    EXECUTION_ENGINE_PATTERNS, _create_execution_engine_event,
    KFM_AGENT_PATTERNS, _create_kfm_agent_event
)


class LogFileProcessor:
    """Processes a single log file using a list of appropriate parsers."""

    def __init__(self, parsers: List[BaseLogParser]):
        """
        Args:
            parsers: A list of parser instances to try for each log file.
                     The first parser whose heuristic_matches returns True will be used.
        """
        if not parsers:
            raise ValueError("At least one parser must be provided to LogFileProcessor.")
        self.parsers = parsers

    def process_file(self, file_path: str) -> Iterator[LogEntry]:
        """
        Selects an appropriate parser based on heuristics and processes the file.
        Yields LogEntry objects.
        """
        selected_parser: Optional[BaseLogParser] = None
        try:
            # Try to find a matching parser using heuristics on the first few lines
            # This avoids reading the whole file multiple times for heuristics.
            with open(file_path, 'r', encoding='utf-8') as f:
                sample_lines = [f.readline().strip() for _ in range(min(5, sum(1 for _ in open(file_path, 'r', encoding='utf-8')))) ] # Read up to 5 lines
            
            if not any(sample_lines): # File might be empty or only newlines
                # print(f"Warning: File {file_path} is empty or contains no parsable content.")
                return iter([]) # Return empty iterator

            for parser_instance in self.parsers:
                # Heuristic check on a sample line (e.g., the first non-empty one)
                first_good_line = next((line for line in sample_lines if line), None)
                if first_good_line and parser_instance.heuristic_matches(first_good_line):
                    selected_parser = parser_instance
                    break
            
            if not selected_parser:
                # Fallback to trying the first parser if no heuristic strongly matched, 
                # or implement a more sophisticated selection/defaulting mechanism.
                # print(f"Warning: No parser strongly matched heuristics for {file_path}. Trying first parser.")
                # For now, if no specific heuristic matches, we might skip or log, 
                # or try a default (e.g., a generic RegexLineParser if one is configured as such)
                # Let's assume for now we require a heuristic match, or the list of parsers is ordered by preference.
                # If self.parsers is ordered, the first one that can handle it will be picked by its parse_file
                # if its heuristic_matches is broad or always True for generic ones.
                # For safety, if no specific match, we could try them in order or default to the first one.
                # Here, we strictly require a heuristic match from the sample lines.
                # print(f"Could not determine a specific parser for {file_path} based on heuristics.")
                return iter([]) # Or raise an error/warning

        except FileNotFoundError:
            print(f"Error: Log file not found during heuristic check: {file_path}")
            return iter([])
        except Exception as e:
            print(f"Error during heuristic check for {file_path}: {e}")
            return iter([])

        # If a parser was selected, use it to parse the entire file.
        # The parse_file method of the selected parser will handle actual parsing.
        if selected_parser:
            # print(f"Processing {file_path} with {selected_parser.__class__.__name__}")
            yield from selected_parser.parse_file(file_path)
        else:
            # This case should ideally be handled by the heuristic logic above.
            # If it's reached, it means no parser's heuristic_matches returned True for any sample line.
            # print(f"No suitable parser found for {file_path} after heuristic checks.")
            return iter([])

class AutomatedVerificationLogAnalyzer:
    """Analyzes multiple log files to extract and aggregate structured log events."""

    def __init__(self, parser_config: Optional[Dict[str, List[BaseLogParser]]] = None):
        """
        Args:
            parser_config: A dictionary mapping log file name patterns (regex) to a list of 
                           BaseLogParser instances configured for that log type. 
                           If None, a default configuration will be attempted.
        """
        if parser_config:
            self.parser_config: Dict[Pattern[str], List[BaseLogParser]] = { 
                re.compile(pattern): parsers for pattern, parsers in parser_config.items()
            }
        else:
            self.parser_config = self._get_default_parser_config()
        
        self.all_log_events: List[LogEntry] = []

    def _get_default_parser_config(self) -> Dict[Pattern[str], List[BaseLogParser]]:
        """Provides a basic default configuration for known log types."""
        # This is where we would instantiate our parsers with specific regexes/configs
        # Note: Order in the list matters if heuristics are not perfectly disjoint.
        # The first parser in the list whose heuristic matches will be chosen.
        
        # For llm_api.log (JSONL)
        llm_api_parser = JsonLineParser()

        # For src.tracing.log (Regex based)
        tracing_parser = RegexLineParser(
            base_log_pattern=GENERAL_BASE_LOG_REGEX, # Defined in parsers.py
            event_patterns=NODE_TRACE_PATTERNS # Defined in parsers.py
        )

        # For ExecutionEngine.log (Regex based)
        exec_engine_parser = RegexLineParser(
            base_log_pattern=GENERAL_BASE_LOG_REGEX,
            event_patterns=EXECUTION_ENGINE_PATTERNS
        )

        # For KFMAgent.log (Regex based)
        kfm_agent_parser = RegexLineParser(
            base_log_pattern=GENERAL_BASE_LOG_REGEX,
            event_patterns=KFM_AGENT_PATTERNS
        )
        
        # This config maps filename patterns to a list of parsers to try for that file type.
        # More specific patterns should come first.
        return {
            re.compile(r"llm_api\.log$"): [llm_api_parser],
            re.compile(r"src\.tracing\.log$"): [tracing_parser],
            re.compile(r"ExecutionEngine\.log$"): [exec_engine_parser],
            re.compile(r"KFMAgent\.log$"): [kfm_agent_parser],
            # Add a more generic fallback for *.log if needed, e.g., with a generic Regex parser
            # re.compile(r".*\.log$"): [some_generic_regex_parser, llm_api_parser] # Order matters
        }

    def process_log_source(self, source_path: str) -> None:
        """
        Processes a single log file or all log files in a directory (non-recursive).
        Appends parsed LogEntry objects to self.all_log_events.
        """
        if os.path.isfile(source_path):
            self._process_single_file(source_path)
        elif os.path.isdir(source_path):
            for item in os.listdir(source_path):
                item_path = os.path.join(source_path, item)
                if os.path.isfile(item_path):
                    self._process_single_file(item_path)
        else:
            print(f"Warning: Log source path does not exist or is not a file/directory: {source_path}")

    def _get_parsers_for_file(self, file_path: str) -> List[BaseLogParser]:
        """Returns a list of parsers suitable for the given file_path based on filename patterns."""
        file_name = os.path.basename(file_path)
        for pattern, parsers_list in self.parser_config.items():
            if pattern.search(file_name): # Use search to allow partial matches like endswith
                return parsers_list
        # print(f"Debug: No specific parser configuration found for {file_name}. Returning empty list.")
        return [] # No specific config, LogFileProcessor might try its own defaults or skip

    def _process_single_file(self, file_path: str) -> None:
        configured_parsers = self._get_parsers_for_file(file_path)
        if not configured_parsers:
            # print(f"No parser configuration for {file_path}, skipping.")
            return

        # Use LogFileProcessor with the specifically configured parsers for this file type
        processor = LogFileProcessor(parsers=configured_parsers)
        try:
            for entry in processor.process_file(file_path):
                self.all_log_events.append(entry)
        except Exception as e:
            print(f"Error processing file {file_path} with AutomatedVerificationLogAnalyzer: {e}")

    def get_all_events(self, sort_by_timestamp: bool = True) -> List[LogEntry]:
        if sort_by_timestamp:
            return sorted(self.all_log_events, key=lambda x: x.timestamp)
        return self.all_log_events

    def filter_events(self, event_type: Optional[Type[LogEntry]] = None, **kwargs) -> List[LogEntry]:
        """
        Filters collected log events by type and/or other attributes.
        Example: analyzer.filter_events(event_type=NodeTraceEvent, node_name="reflection_node")
        """
        filtered = self.get_all_events(sort_by_timestamp=True) # Start with sorted list
        
        if event_type:
            filtered = [event for event in filtered if isinstance(event, event_type)]
        
        for key, value in kwargs.items():
            filtered = [event for event in filtered if getattr(event, key, None) == value]
            
        return filtered

    def clear_events(self) -> None:
        self.all_log_events = [] 