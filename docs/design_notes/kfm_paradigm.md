# KFM (Kill, Fuck, Marry) Paradigm Design

## Overview

The KFM paradigm is a decision-making framework used by the KFMPlanner agent to manage components dynamically based on task requirements and component performance. It involves three core actions:

*   **Marry:** Permanently adopt or integrate a component that optimally meets the current task's requirements (e.g., high accuracy, low latency).
*   **Fuck:** Temporarily activate or repurpose a sub-optimal but available component when no ideal ('Marry') candidate exists. This provides immediate functionality but acknowledges a potential compromise.
*   **Kill:** Deactivate or remove a component that is underperforming, obsolete, or no longer needed.

This document details the rationale, logic, and implications of each action, with a particular focus on the 'Fuck' action.

## Core Actions

### 1. Marry Action

*   **Goal:** Long-term integration of the best-fitting component.
*   **Trigger:** A component significantly meets or exceeds all primary task requirements (e.g., both `min_accuracy` and `max_latency`).
*   **Selection:** If multiple candidates meet 'Marry' criteria, the highest-scoring component (based on a weighted combination of performance metrics) is chosen.
*   **Execution:** The `ExecutionEngine` applies the 'Marry' action, typically setting the component as the default or active component for relevant tasks.
*   **State:** `KFMAgentState.current_activation_type` is set to `'marry'`.
*   **Implication:** Represents a stable, preferred state for the system's architecture regarding the specific capability.

### 2. Fuck Action (Temporary Usage / Repurposing)

*   **Goal:** Provide immediate functionality using a readily available but sub-optimal component when no ideal component can be 'Married'.
*   **Rationale:** Addresses situations where waiting for an ideal component is not feasible or where a temporary solution is sufficient. It prioritizes progress over perfection in the short term.
*   **Trigger:** No component meets the criteria for a 'Marry' action, but one or more available components partially meet the requirements (e.g., meets `min_accuracy` OR `max_latency`, but not both).
*   **Selection Logic:**
    *   Identify all available components that meet at least one primary requirement but not all.
    *   Rank these 'Fuck' candidates based on a scoring system. The default ranking prioritizes accuracy first, then latency (lower is better): `score = (accuracy, -latency)`.
    *   The highest-scoring 'Fuck' candidate is selected.
*   **Execution:**
    *   The `ExecutionEngine` applies the 'Fuck' action by calling `ComponentRegistry.set_default_component()` with the chosen component key.
    *   The action is logged with a `WARNING` level to highlight the temporary/compromise nature.
*   **State:** `KFMAgentState.current_activation_type` is set to `'fuck'`.
*   **Implications:**
    *   **Temporary:** This activation is not considered permanent. The `KFMPlanner` will re-evaluate components in subsequent cycles.
    *   **Performance:** The system may operate with sub-optimal performance (e.g., higher latency or lower accuracy) while a 'Fuck' component is active. This performance is monitored by `StateMonitor`.
    *   **Replanning:** Poor performance from a 'Fucked' component can trigger the `KFMPlanner` to seek alternatives (potentially 'Marry' a newly suitable component or even 'Kill' the 'Fucked' one if it performs *too* poorly) in later cycles.
    *   **Dependencies:** If the chosen component has dependencies, the `ExecutionEngine` verifies their accessibility before activation.
*   **Non-Permanence (Implicit via Re-evaluation):** 
    *   The 'Fuck' action is inherently temporary due to the KFM agent's continuous planning loop. There is **no explicit \"Unfuck\" action or command**.
    *   In each cycle, the `KFMPlanner` re-evaluates *all* available components against the *current* task requirements and *latest* performance data provided by the `StateMonitor`.
    *   This means a component activated via 'Fuck' in one cycle can be superseded in the next cycle if:
        *   Its own performance improves enough to meet 'Marry' criteria.
        *   A different component becomes available or improves to meet 'Marry' criteria.
        *   A different component becomes available or improves to become a *better* 'Fuck' candidate.
        *   The original 'Fucked' component's performance degrades significantly, potentially leading to a 'Kill' decision if no other suitable options exist.
    *   The system doesn't "remember" that a component was previously 'Fucked'; decisions are always based on the current state assessment.

### 3. Kill Action

*   **Goal:** Remove underperforming, unnecessary, or problematic components.
*   **Trigger:**
    *   No suitable component meets 'Marry' or 'Fuck' criteria.
    *   An active component is consistently underperforming based on `StateMonitor` data.
    *   A component is explicitly marked for removal.
*   **Selection:** The specific component to be killed is identified based on the trigger condition.
*   **Execution:** The `ExecutionEngine` applies the 'Kill' action, typically deactivating the component and potentially removing it from the registry (depending on implementation details).
*   **State:** `KFMAgentState.current_activation_type` can be set to `'kill'` to indicate the last action taken.
*   **Implication:** Removes a component from active use, potentially freeing resources or simplifying the system state.

## Decision Hierarchy

The `KFMPlanner` evaluates actions in a specific order:

1.  **Check for 'Marry' candidates:** If one or more components meet all primary requirements, select the best one and propose 'Marry'.
2.  **Check for 'Fuck' candidates:** If no 'Marry' candidates exist, check for components meeting at least one requirement. If found, select the best one (based on ranking) and propose 'Fuck'.
3.  **Propose 'Kill' or No Action:** If neither 'Marry' nor 'Fuck' candidates are suitable, consider proposing 'Kill' for an underperforming active component, or propose no action if the current state is acceptable or unchangeable.

## Logging and Verification

Each KFM action generates specific log messages:
*   `KFM Decision: [MARRY|FUCK|KILL] component '{component_name}'. Reason: {reason}. Score: {score}.` (Planner, typically INFO or WARNING for FUCK)
*   `KFM Action [MARRY|FUCK|KILL]: Component '{component_name}' ...` (ExecutionEngine, typically INFO or WARNING for FUCK)
*   `Task executed via [marry|fuck]: Component '{component_name}' used with performance {performance:.2f}.` (LangGraph Node, INFO)
*   `Reflection context: Processing '[marry|fuck|kill]' action for component '{component_name}'.` (LangGraph Node, INFO)

The `kfm-verifier` tool uses these log patterns (defined in its configuration) to validate that the KFM actions occurred as expected during a system run. See `docs/cli/kfm_verifier_readme.md` for details. 