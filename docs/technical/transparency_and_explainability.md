# KFM Agent Transparency and Explainability (Level 2 & 3 Features)

This document outlines features implemented to enhance the transparency and explainability of the KFM Agent, focusing on Level 2 (Observable Semantic Space) and Level 3 (Adaptation Goal Measurement & Local Explanations).

## 1. Semantic State Logging (Level 2 Foundation)

To provide a basis for transparency, detailed semantic states of the agent are logged throughout its execution graph. Key aspects of the agent's internal state are captured at various nodes.

- **Log File:** `semantic_state_details.log` (by default, located in the agent's root execution directory).
- **Format:** Each line in the log is a JSON object representing a snapshot of `KFMAgentState` at a specific event point.
- **Key Logged Fields (subset relevant for explanation):
    - `event_tag`: A string identifying the specific point in the agent's lifecycle (e.g., `kfm_decision_node_exit_with_decision`, `execute_action_node_entry`).
    - `timestamp`: UTC timestamp of the log entry.
    - `run_id`: Unique identifier for the agent run.
    - `original_correlation_id`: Identifier for the initial request or task correlation.
    - `input_data`: The input data provided to the agent for the current task.
    - `task_name`: The name of the task the agent is currently working on.
    - `current_task_requirements`: The requirements defined for the current task.
    - `kfm_action`: The Keep-Fuck-Marry decision made by the planner, including:
        - `action`: (e.g., "Keep", "Fuck", "Kill", "Marry", "No Action")
        - `component`: The target component of the action.
        - `reasoning`: The planner's stated rationale for the decision.
        - `confidence`: The planner's confidence in the decision (0.0 to 1.0).
    - `execution_performance`: Performance metrics from the execution of an action (structure depends on the component).
    - `calculated_metrics`: Additional metrics calculated by the logging system itself, such as `task_requirement_satisfaction`.
    - `error`: Any error information captured during the state.

## 2. Adaptation Goal Measurement: Task Requirement Satisfaction (Level 3)

To measure how well an executed action meets the defined task requirements, a `task_requirement_satisfaction` score (indicator string) is calculated and logged within the `calculated_metrics` field of semantic logs, specifically for `execute_action_node_exit_success` events.

- **Purpose:** Provides an at-a-glance understanding of task success from a requirements perspective.
- **Calculation (current logic in `src.langgraph_nodes.execute_action_node`):
    - Compares keys and values between `current_task_requirements` (from `KFMAgentState`) and `execution_performance` (also from `KFMAgentState`, populated by the component execution).
    - Both are expected to be dictionaries.
    - **Matching Logic:** For each key in `current_task_requirements`:
        - If the key exists in `execution_performance`, their values are compared directly (simple equality check).
        - Counts are maintained for: `num_reqs_checked`, `num_reqs_met`, `num_reqs_unmet`, `num_reqs_perf_missing` (requirement key exists, but corresponding key not in performance data).
- **Indicator String Format Examples:**
    - `"MetAll (X/X)"`: All X checked requirements were met.
    - `"MetSome (Y/X) [Details: Unmet:A, PerfMissing:B]"`: Y out of X requirements were met. A were unmet (performance value differed), B had performance data missing for the requirement key.
    - `"MetNone (0/X) [Details: Unmet:A, PerfMissing:B]"`: Zero requirements met.
    - `"ReqsDefined (X)_NoPerfData"`: X requirements were defined, but no performance data (or not a dict) was available for comparison.
    - `"PerfDataAvailable_NoTrackedReqs"`: Performance data was available, but no requirements were defined (or `task_reqs` was empty/not a dict).
    - `"NoReqsOrPerfData"`: Neither requirements nor performance data were available in the expected dictionary format.
    - `"NotApplicable"`: Default if calculation couldn't proceed (e.g., execution failed before this point).
- **Access:** This metric is available in the `semantic_state_details.log` for analysis and can be part of higher-level reporting (Level 4 features).

## 3. Local Decision Explanations (Level 3)

The `LocalKfmExplanationService` provides a way to retrieve and format human-readable explanations for specific KFM decisions using the semantic logs.

### 3.1. Service: `src.transparency.local_explanation_service.LocalKfmExplanationService`

- **Initialization:** `LocalKfmExplanationService(log_file_path: str = "semantic_state_details.log")`
    - Takes an optional path to the semantic log file.
- **Key Methods:**
    - `get_kfm_decision_context(run_id: str, decision_event_tag: str = "kfm_decision_node_exit_with_decision", decision_index: Optional[int] = 0) -> Optional[Dict[str, Any]]`:
        - Parses the log file line by line.
        - Filters log entries by `run_id` and `decision_event_tag`.
        - Retrieves the context of the Nth decision (specified by `decision_index`, 0-based) for that run.
        - Extracts relevant fields: `timestamp`, `kfm_action` details (action, component, reasoning, confidence), `task_name`, and summaries of `input_data` and `current_task_requirements`.
        - Returns a dictionary with this context or `None`.
    - `format_decision_explanation(decision_context: Optional[Dict[str, Any]]) -> str`:
        - Takes the context dictionary.
        - Formats it into a human-readable string.

### 3.2. CLI Access: `src.cli.kfm_agent_cli.py`

- **Command:** `explain-decision`
- **Usage:**
  ```bash
  python src/cli/kfm_agent_cli.py explain-decision --run-id <RUN_ID> [OPTIONS]
  ```
- **Options:**
    - `--run-id <RUN_ID>`: (Required) The `run_id` of the agent execution.
    - `--decision-index <INDEX>`: (Optional, default: `0`) The 0-based index of the KFM decision to explain within that run.
    - `--log-file <PATH>`: (Optional, default: `semantic_state_details.log`) Path to the semantic log file.
    - `--event-tag <TAG>`: (Optional, default: `kfm_decision_node_exit_with_decision`) The log event tag that identifies KFM decisions.
- **Output:** Prints a formatted explanation to the console or a "not found" message.
- **Example:**
  ```bash
  python src/cli/kfm_agent_cli.py explain-decision --run-id "some_specific_run_id"
  ```

### 3.3. API Access: `src.api.main.py`

- **Endpoint:** `GET /agent/v1/explain-decision`
- **Query Parameters:**
    - `run_id: str` (Required)
    - `decision_index: Optional[int]` (Default: `0`)
    - `log_file: Optional[str]` (Default: service default, `semantic_state_details.log`)
    - `event_tag: Optional[str]` (Default: service default, `kfm_decision_node_exit_with_decision`)
- **Responses:**
    - **`200 OK`**: `DecisionExplanationResponse`
      ```json
      {
        "run_id": "string",
        "decision_index_found": 0,
        "formatted_explanation": "string",
        "log_file_used": "string",
        "event_tag_used": "string"
      }
      ```
    - **`404 Not Found`**: If the decision context cannot be found for the given parameters.
      ```json
      {
        "detail": "Decision context not found..."
      }
      ```
    - **`500 Internal Server Error`**: For issues like log file reading errors or formatting problems.
    - **`503 Service Unavailable`**: If the `LocalKfmExplanationService` fails to initialize on the server.
- **Example Request:**
  ```
  GET /agent/v1/explain-decision?run_id=some_specific_run_id&decision_index=1
  ```

## 4. Global Analytics and Trend Reporting (Level 4)

The `GlobalAnalyticsService` aggregates data from multiple semantic log files to provide insights into long-term agent behavior, performance, and decision patterns.

### 4.1. Service: `src.transparency.global_analytics_service.GlobalAnalyticsService`

- **Initialization:** `GlobalAnalyticsService(log_files: Optional[List[str]] = None, log_dir: Optional[str] = None, log_pattern: str = "semantic_state_details.log")`
    - Can be initialized with a list of specific `log_files` or a `log_dir` (in which case `log_pattern` is used to find files).
- **Key Methods:**
    - `process_logs()`: Reads all specified log sources, parses each line, and extracts key metrics (KFM action types, confidence, component usage, task satisfaction scores, errors, "Fuck" counts).
    - `get_aggregated_metrics() -> Dict[str, Any]`: Returns a dictionary containing the aggregated statistics.
    - `generate_report_text() -> str`: Formats the aggregated metrics into a human-readable Markdown report.
- **Aggregated Metrics Include:**
    - Total log sources scanned, total entries processed, total decision events.
    - KFM action counts and percentages.
    - Component usage frequencies in KFM decisions.
    - "Fuck" action total count.
    - Total error count and error rate per log entry.
    - Average decision confidence.
    - Distribution of task requirement satisfaction scores.

### 4.2. CLI Access: `src.cli.kfm_agent_cli.py`

- **Command:** `generate-global-report`
- **Usage:**
  ```bash
  python src/cli/kfm_agent_cli.py generate-global-report [OPTIONS]
  ```
- **Options:**
    - `--log-files <file1.log,file2.log,...>`: Comma-separated list of specific log file paths.
    - `--log-dir <DIRECTORY_PATH>`: Path to a directory containing log files. The service will search for files matching `--log-pattern`.
    - `--log-pattern <PATTERN>`: (Optional, default: `semantic_state_details.log`) Glob pattern to match log files in `--log-dir`.
    - `--output-file <REPORT_PATH.md>`: (Optional) Path to save the generated Markdown report. If not specified, the report is printed to the console.
- **Output:** Prints a Markdown formatted global analytics report to the console or saves it to the specified file.
- **Example (using a directory of logs):
  ```bash
  python src/cli/kfm_agent_cli.py generate-global-report --log-dir ./all_my_agent_runs/logs/ --output-file global_summary.md
  ```

## 5. Interactive Explanatory UI (Level 5)

To provide a more accessible and interactive way to explore agent explanations and analytics, a Streamlit-based web UI has been developed.

- **Application File:** `src/transparency/ui/kfm_explain_ui.py`
- **To Launch:**
    1.  **Directly via Streamlit (from project root):**
        ```bash
        streamlit run src/transparency/ui/kfm_explain_ui.py
        ```
    2.  **Via the KFM Agent CLI (from project root):**
        ```bash
        python src/cli/kfm_agent_cli.py ui
        ```
        This command will attempt to launch the Streamlit application. Ensure Streamlit is installed (`pip install streamlit`).

### 5.1. Features

The UI provides two main sections accessible via a sidebar:

#### a. Local Decision Explanation

- **Purpose:** Allows users to retrieve and view a formatted explanation for a specific KFM decision made by the agent.
- **Inputs:**
    - `Run ID` (Required): The unique identifier for the agent run.
    - `Log File Path` (Optional): Path to the semantic log file. Defaults to `semantic_state_details.log` if left empty.
    - `Decision Index (0-based)` (Optional): The index of the decision within the run (0 for the first, etc.). Defaults to `0`.
    - `Decision Event Tag` (Optional): The log event tag identifying KFM decisions. Defaults to `kfm_decision_node_exit_with_decision`.
- **Output:**
    - Displays the formatted textual explanation for the specified decision.
    - Provides an expandable section to view the raw JSON context of the decision.
    - Shows error messages if the context is not found or if issues occur.

#### b. Global Analytics Report

- **Purpose:** Enables users to generate and view a global analytics report by processing one or more semantic log files.
- **Inputs:**
    - `Log Files (Optional, comma-separated)`: A comma-separated list of specific log file paths.
    - `Log Directory (Optional)`: A directory path. If provided, all files matching the `Log Pattern` in this directory will be processed.
    - `Log Pattern` (if Log Directory is used): The glob pattern for finding logs. Defaults to `semantic_state_details.log`.
    - (Note: At least one log source - files or directory - must be provided).
- **Output:**
    - Displays a summary of the log processing (number of sources, entries processed).
    - Renders the full Markdown global analytics report.
    - Includes optional expandable bar charts for:
        - KFM Action Distribution
        - Task Requirement Satisfaction Score Distribution
    - Shows error messages if issues occur during report generation.

### 5.2. Running the UI

- Ensure all dependencies, including `streamlit`, are installed (check `requirements.txt`).
- Use one of the launch commands mentioned above.
- A web browser should automatically open to the Streamlit application. If not, the console output from Streamlit will provide the local URL (usually `http://localhost:8501`).

## 6. Future Enhancements (Beyond current subtask)

- More sophisticated `task_requirement_satisfaction` scoring (e.g., handling ranges, weighted criteria).
- Support for `approximate_timestamp` in `LocalKfmExplanationService` for retrieving decisions.
- Integration with global analytics and trend reporting (Level 4).
- Interactive explanatory interfaces (Level 5). 

## 7. Integration and Usage Notes

The transparency and explainability features detailed above are designed to integrate with the KFM Agent's operational workflow and logging mechanisms.

- **Central Log File**: The primary data source for all explanation and analytics services is the `semantic_state_details.log` file. This file is generated by the KFM Agent during its execution and, by default, is expected to be in the directory from which the agent is run (or where its logs are configured to be stored).

- **Running CLI and UI Tools**:
    - Both the KFM Agent CLI (`src/cli/kfm_agent_cli.py`) and the Streamlit UI (`src/transparency/ui/kfm_explain_ui.py`) include Python path adjustments. This allows them to be executed directly from the project's root directory (e.g., `python src/cli/kfm_agent_cli.py ...` or `streamlit run src/transparency/ui/kfm_explain_ui.py`) and correctly import necessary modules from the `src` package.
    - It's recommended to run these tools from the project root to ensure consistent behavior.

- **Workflow**: These transparency tools are intended for post-hoc analysis. First, run the KFM Agent to perform its tasks and generate the `semantic_state_details.log`. Then, use the CLI commands or the interactive UI to inspect decisions, analyze global trends, and gain insights into the agent's behavior.

- **Dependencies**: Ensure that all dependencies, including `streamlit` for the UI, are installed as per `requirements.txt`. 