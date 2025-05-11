# KFM Reversibility Module: Trigger Mechanisms Design

## 1. Introduction

This document outlines the design for trigger mechanisms within the KFM (Kill, Fuck, Marry) agent's operational cycle to enable state snapshotting for the "Fuck" action's reversibility. It details where, when, and how snapshots will be initiated.

This design corresponds to Subtask 62.3: "Trigger Mechanisms for Reversibility."

## 2. Goals

*   Define clear, unambiguous trigger points for snapshot creation.
*   Ensure necessary state information is captured at each relevant point.
*   Specify the API and integration points for invoking the snapshot service.
*   Consider performance implications and minimize overhead.
*   Allow for manual and policy-based triggers in addition to automated ones.

## 3. Identified Trigger Points & Snapshot Context

Based on the KFM agent's workflow (primarily involving `KFMAgentState` and LangGraph nodes like `monitor_state_node`, `kfm_decision_node`, `execute_action_node`, `reflection_node`), the following trigger points are identified:

### 3.1. Pre-Decision Snapshot (Proactive Safety)

*   **Trigger Point:** Before the `kfm_decision_node` (LangGraph) is executed. This is after `monitor_state_node` has updated the world state.
*   **Rationale:** Captures the complete system state *before* the KFM planner (whether rule-based or LLM-based) makes a decision. This provides a baseline that can be used for broader rollback or analysis if the decision-making process itself is flawed.
*   **Data to Capture:**
    *   Full `KFMAgentState` dump.
    *   Relevant context from the LangGraph state (e.g., current observations, historical KFM interactions if available).
    *   Configuration of the KFM planner active for this cycle.
*   **Snapshot Metadata:**
    *   `trigger_event`: "pre_kfm_decision"
    *   `timestamp`: Current system time.
    *   `kfm_cycle_id`: Identifier for the current KFM operational cycle.
    *   `component_ids_in_scope`: List of component IDs being considered.

### 3.2. Post-Decision, Pre-Execution Snapshot (Crucial for 'Fuck' Reversibility)

*   **Trigger Point:** After `kfm_decision_node` has determined an action (especially a 'Fuck' action), but *before* `execute_action_node` applies it.
*   **Rationale:** This is the primary snapshot for enabling the reversal of a 'Fuck' action. It captures the state of the targeted component *just before* modification.
*   **Condition:** Primarily triggered if the KFM decision is 'Fuck'. Could also be triggered for 'Marry' if a "pre-commitment" state is desired.
*   **Data to Capture:**
    *   Full `KFMAgentState`.
    *   The specific KFM decision made (e.g., "Fuck component_X").
    *   Detailed state of `component_X` (obtained via a state adapter – see Subtask 62.4).
    *   State of any directly dependent components if identifiable and feasible.
*   **Snapshot Metadata:**
    *   `trigger_event`: "pre_action_execution"
    *   `kfm_action`: The decided action (e.g., "Fuck", "Marry").
    *   `target_component_id`: ID of the component targeted by the action.
    *   `timestamp`: Current system time.
    *   `kfm_cycle_id`: Identifier for the current KFM operational cycle.

### 3.3. Post-Execution Snapshot (Confirmation & New Baseline)

*   **Trigger Point:** After `execute_action_node` successfully completes, particularly for a 'Fuck' action.
*   **Rationale:** Confirms the state change after a 'Fuck' action and establishes a new baseline. Useful if the 'Fuck' action itself needs to be rolled back due to later-discovered issues not immediately apparent. Less critical for direct reversibility of the *just-applied* 'Fuck', but good for longer-term state management.
*   **Data to Capture:**
    *   Full `KFMAgentState`.
    *   Detailed state of the `target_component_id` *after* the action.
    *   Outcome of the action execution (e.g., success, specific changes made).
*   **Snapshot Metadata:**
    *   `trigger_event`: "post_action_execution"
    *   `kfm_action`: The executed action.
    *   `target_component_id`: ID of the component.
    *   `execution_status`: "success"
    *   `timestamp`: Current system time.
    *   `kfm_cycle_id`: Identifier for the current KFM operational cycle.

### 3.4. Post-Execution Failure Snapshot (Diagnostics)

*   **Trigger Point:** After `execute_action_node` fails to complete an action (especially 'Fuck').
*   **Rationale:** Captures the state when an intended action failed, which can be crucial for diagnostics and for deciding if a rollback to the "pre_action_execution" snapshot is warranted.
*   **Data to Capture:**
    *   Full `KFMAgentState`.
    *   The KFM decision that was attempted.
    *   Detailed state of the `target_component_id` at the point of failure.
    *   Error messages and stack traces from the execution attempt.
*   **Snapshot Metadata:**
    *   `trigger_event`: "post_action_failure"
    *   `kfm_action`: The attempted action.
    *   `target_component_id`: ID of the component.
    *   `execution_status`: "failure"
    *   `error_details`: Captured error information.
    *   `timestamp`: Current system time.
    *   `kfm_cycle_id`: Identifier for the current KFM operational cycle.

### 3.5. Manual & Policy-Based Triggers

*   **Trigger Point:** Asynchronous, initiated by a human operator or an external policy/monitoring system.
*   **Rationale:** Allows for ad-hoc snapshots for debugging, testing, or based on external system health indicators not directly tied to the KFM cycle.
*   **Data to Capture:**
    *   Full `KFMAgentState`.
    *   State of specified components (if any).
    *   Reason/source of the manual trigger.
*   **Snapshot Metadata:**
    *   `trigger_event`: "manual_snapshot" or "policy_snapshot"
    *   `source`: Identifier of the human operator or policy engine.
    *   `reason`: Textual reason for the snapshot.
    *   `target_component_ids`: Optional list of specific components.
    *   `timestamp`: Current system time.

## 4. Snapshot Service API & Integration

A `SnapshotService` will be responsible for orchestrating the snapshot process. This service will be called from the identified trigger points within the KFM agent's LangGraph nodes.

### 4.1. Service Interface (Conceptual)

```python
class SnapshotService:
    async def take_snapshot(
        self,
        snapshot_id: str, # Potentially auto-generated or context-derived
        trigger_event: str,
        kfm_agent_state: KFMAgentState, # Core agent state
        target_component_id: Optional[str] = None,
        component_state_data: Optional[bytes] = None, # Serialized state from adapter
        metadata: Dict[str, Any]
    ) -> Optional[SnapshotManifest]:
        """
        Orchestrates taking a snapshot.
        - Fetches component-specific state if target_component_id and adapter are available.
        - Combines kfm_agent_state and component_state_data.
        - Stores the combined data via SnapshotStorageInterface.
        """
        pass

    async def get_component_state(
        self,
        component_id: str,
        component_type: Optional[str] = None # To help select the adapter
    ) -> Optional[bytes]:
        """
        Uses the State Adapter Registry to get the current state of a component.
        """
        pass
```

### 4.2. Integration with LangGraph Nodes

*   Each relevant LangGraph node (`monitor_state_node`, `kfm_decision_node`, `execute_action_node`) will be modified to conditionally call `SnapshotService.take_snapshot()`.
*   The call will be asynchronous to avoid blocking the main KFM agent loop significantly.
*   Error handling within the snapshotting process must ensure that failures in taking a snapshot do not halt the primary KFM operations, though errors should be logged for later review.

**Example (Conceptual within a LangGraph node):**

```python
# In kfm_decision_node, before returning the decision
if kfm_decision.action == "Fuck":
    # ... (gather pre-execution component state using state adapter) ...
    component_data_to_snapshot = await snapshot_service.get_component_state(kfm_decision.target_component_id)
    await snapshot_service.take_snapshot(
        snapshot_id=f"pre_fuck_{kfm_decision.target_component_id}_{timestamp}",
        trigger_event="pre_action_execution",
        kfm_agent_state=current_kfm_agent_state,
        target_component_id=kfm_decision.target_component_id,
        component_state_data=component_data_to_snapshot,
        metadata={
            "kfm_action": "Fuck",
            "target_component_id": kfm_decision.target_component_id,
            # ... other metadata
        }
    )
```

## 5. Data to be Snapshotted

*   **Core KFM Agent State:** This includes the `KFMAgentState` Pydantic model, which contains the world model, component registry, ethical framework state, etc. This will be serialized (e.g., to JSON).
*   **Target Component State:** For 'Fuck' actions, the specific state of the targeted component is crucial. This will be retrieved via the "State Adapter Registry" (Subtask 62.4) and should be in a byte format (e.g., serialized representation, raw data dump).
*   **Snapshot Manifest:** The manifest will include metadata about the snapshot (trigger event, timestamp, involved components, etc.) and references to the stored data chunks.

The `SnapshotStorageInterface` will handle the chunking and storage of the combined serialized `KFMAgentState` and the `component_state_data`.

## 6. Performance Considerations

*   **Asynchronous Operations:** Snapshotting should be performed asynchronously to minimize impact on the KFM agent's main processing loop.
*   **Efficient Serialization:** Use efficient serialization formats (e.g., Pydantic's JSON for `KFMAgentState`, potentially optimized binary formats for component states if applicable).
*   **Content-Defined Chunking:** The underlying `FileSnapshotStorage` already uses content-defined chunking and compression, which will help manage storage space and reduce I/O for repeated states.
*   **Selective Snapshotting:** Consider policies to avoid excessive snapshotting (e.g., don't snapshot if state hasn't changed significantly since the last snapshot of the same type, unless it's a critical trigger like "pre_action_execution"). This can be a future optimization.

## 7. Error Handling

*   Snapshotting failures should be logged comprehensively but should not, by default, halt the primary KFM agent operations.
*   A "best-effort" approach will be taken initially, with options for more critical error handling (e.g., halting before a 'Fuck' if pre-snapshot fails) to be configured by policy.

## 8. Future Considerations

*   **Conditional Snapshotting based on State Diff:** Only take a snapshot if the relevant state has changed beyond a certain threshold since the last snapshot.
*   **Configurable Snapshot Frequency/Policy:** Allow administrators to define policies for how often and under what specific conditions snapshots are taken for different trigger events.
*   **Integration with Monitoring/Alerting:** Alerts if snapshotting fails consistently or if storage capacity is low.

This design provides a foundational approach to triggering snapshots. The implementation will involve modifying the KFM agent's core logic and integrating the `SnapshotService`. 