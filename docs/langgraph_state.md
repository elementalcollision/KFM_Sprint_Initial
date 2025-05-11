# LangGraph State Definition

## Overview
This document defines the structure of the `KFMAgentState` that flows between nodes in the LangGraph implementation.
Refer to [`src/state_types.py`](mdc:src/state_types.py) for the concrete `TypedDict` definition.

## State Keys

### Input Data
- `input`: The input data to process (dictionary)
- `task_name`: Name of the current task (string)

### Performance and Requirements Data
- `performance_data`: Component performance metrics (dictionary of component names to metric dictionaries)
- `task_requirements`: Requirements for the current task (dictionary of metric names to threshold values)

### KFM Decision
- `kfm_action`: The KFM action to apply (dictionary with 'action' and 'component' keys)

### Execution Results
- `active_component`: Name of the active component (string)
- `result`: Result from executing the task (dictionary)
- `execution_performance`: Performance of the execution (dictionary of metric names to values)

### Control Flow
- `error`: Error message if something went wrong (string)
- `done`: Whether the workflow is complete (boolean)

## State Flow Between Nodes (Planned)

1.  **monitor_state_node**:
    -   Reads: `input`, `task_name`
    -   Writes: `performance_data`, `task_requirements`

2.  **kfm_decision_node**:
    -   Reads: `performance_data`, `task_requirements`
    -   Writes: `kfm_action`

3.  **execute_action_node**:
    -   Reads: `kfm_action`, `input`
    -   Writes: `active_component`, `result`, `execution_performance`, `done` 