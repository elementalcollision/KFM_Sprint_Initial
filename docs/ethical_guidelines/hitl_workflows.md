# Human-in-the-Loop (HITL) Workflow Guidelines for KFM Agent

## 1. Introduction

This document outlines the Human-in-the-Loop (HITL) workflows designed to ensure safe, transparent, and accountable operations of the Kill-Fuck-Marry (KFM) autonomous agent. These workflows are triggered at critical decision points where human judgment is deemed necessary to supplement or override the agent\'s autonomous decisions.

## 2. General HITL Workflow Structure

All HITL interventions will follow a general structure:

1.  **Trigger & Context Generation:**
    *   The KFM agent identifies a decision scenario matching predefined HITL criteria.
    *   The agent compiles a "Review Package" containing:
        *   Proposed action (Kill, Fuck, Marry).
        *   Target component(s)/process(es).
        *   Agent\'s reasoning and confidence score.
        *   Relevant performance metrics (current and historical).
        *   Impact assessment (e.g., dependencies, resource forecasts).
        *   Relevant ethical considerations or policy violations flagged.

2.  **Notification & Presentation:**
    *   The designated human reviewer(s) are notified via the defined communication channel (e.g., dashboard alert, email, messaging system).
    *   The Review Package is presented to the reviewer in a clear, understandable format.

3.  **Human Review & Decision:**
    *   The human reviewer assesses the situation using the provided context and their expertise.
    *   Available decisions for the reviewer typically include:
        *   **Approve:** The agent proceeds with the proposed action.
        *   **Override:** The reviewer specifies an alternative action (e.g., change "Kill" to "Monitor", or select a different component for "Marry").
        *   **Reject/Veto:** The agent\'s proposed action is blocked, and it typically defaults to "No Action" or a predefined safe state.
        *   **Defer/Request More Information:** The decision is postponed pending further data or analysis. The agent may be tasked with gathering this information.
    *   The reviewer must provide a rationale for their decision, especially for overrides and rejections.

4.  **Action Execution & Logging:**
    *   The agent executes the action dictated by the human reviewer\'s decision.
    *   The entire HITL interaction is logged, including:
        *   Timestamp of the event.
        *   The agent\'s initial proposed action and Review Package.
        *   The human reviewer(s) involved.
        *   The reviewer\'s decision and rationale.
        *   The final action taken.

5.  **Feedback & System Improvement:**
    *   Logged HITL events are periodically reviewed to:
        *   Identify patterns or recurring issues.
        *   Refine HITL triggers and criteria.
        *   Improve the agent\'s decision-making models and ethical ontologies.
        *   Update training materials for human reviewers.

## 3. KFM Action-Specific HITL Triggers

### 3.1. "Kill" Actions

A "Kill" action involves terminating a component or process.

*   **HITL Triggers:**
    1.  **Criticality & Impact:** Proposed "Kill" on a component/process designated as "critical" (e.g., core infrastructure, high-dependency service) or if the kill action would significantly impact system stability or a large number of users/dependent services.
    2.  **Low Confidence:** Agent\'s confidence in the "Kill" decision falls below a predefined threshold (e.g., < 0.75), especially if alternative interpretations of data exist. (Note: A stricter, automated veto might exist for even lower confidence, e.g., <0.9 on certain components as per `EthicalConfigManagerMock`.)
    3.  **Threshold Breach (Configurable Severity):**
        *   Exceeding predefined operational thresholds (e.g., latency, cost, error rate) for a component, where the breach is:
            *   Of a high severity level (e.g., major cost overrun vs. minor latency spike).
            *   Persistent over a defined observation window.
            *   A first-time occurrence for an otherwise stable component, suggesting an anomaly.
    4.  **Ethical Policy Violation:** The proposed "Kill" action, even if seemingly justified by performance, might conflict with higher-level ethical policies (e.g., disproportionate impact on a specific user group if the component serves them uniquely).

*   **Information for Reviewer (Review Package Additions):**
    *   Specific threshold(s) breached and magnitude/duration of breach.
    *   List of dependent services/processes and potential impact of termination.
    *   Historical performance and stability record of the component.
    *   Alternative actions considered by the agent (e.g., restart, rollback, resource scaling) and why "Kill" was chosen.

### 3.2. "Fuck" Actions

A "Fuck" action involves a significant, potentially experimental or risky, modification to a component/process to improve its short-term usefulness or explore new configurations.

*   **HITL Triggers:**
    1.  **High Potential Risk/Impact:** The proposed modification (e.g., state transition, data injection, configuration change) carries a high risk of:
        *   Causing instability in the target component or connected systems.
        *   Significant, unpredicted resource consumption (CPU, memory, cost).
        *   Data corruption or loss.
        *   Security vulnerabilities.
    2.  **Experimental Nature:** The proposed modification is highly experimental, lacks precedent, or uses unverified techniques/data.
    3.  **Target Sensitivity:** The target component is critical, sensitive (e.g., handles PII), or has a history of instability.
    4.  **Resource Intensive:** The proposed "Fuck" action itself (the process of modification) is highly resource-intensive.
    5.  **Ethical Concerns:** The modification could lead to biased outputs, unfair treatment, or other ethically undesirable outcomes.

*   **Information for Reviewer (Review Package Additions):**
    *   Detailed description of the proposed modification.
    *   Expected benefits and metrics for success.
    *   Identified risks and mitigation strategies (if any).
    *   Rollback plan if the modification fails or has negative consequences.
    *   Resource requirements for the modification and subsequent operation.

### 3.3. "Marry" Actions

A "Marry" action involves a long-term commitment to a component/process, making it a standard, reliable part of the system.

*   **HITL Triggers:**
    1.  **New or Unproven Component:** Proposing to "Marry" a component that is relatively new, has limited operational history, or lacks extensive validation in the current environment.
    2.  **Significant Resource Commitment:** The "Marry" decision implies a long-term, significant allocation of resources (e.g., infrastructure, maintenance effort, licensing costs).
    3.  **Lock-in Risk:** Committing to the component might significantly restrict future architectural choices or make it difficult to adopt potentially better alternatives later.
    4.  **Vendor/Technology Dependency:** The component introduces a new, critical dependency on a specific vendor or technology with potential long-term strategic implications.
    5.  **High Initial Integration Cost/Effort:** The process of fully integrating the "Married" component is substantial.

*   **Information for Reviewer (Review Package Additions):**
    *   Comprehensive performance and reliability data (accuracy, latency, cost, TTPT, TPOT, uptime) over a significant period.
    *   Comparison with alternative components/solutions considered.
    *   Estimated Total Cost of Ownership (TCO).
    *   Security assessment and compliance status.
    *   Support and maintenance plan.

### 3.4. "No Action" (Exception-Based HITL)

Generally, "No Action" decisions do not require HITL intervention as they represent a steady or optimal state.

*   **HITL Triggers (Exceptional):**
    1.  **Prolonged Stagnation with Declining Context:** The agent consistently chooses "No Action" for a specific task or system area despite subtle, slowly degrading performance metrics or changing external conditions that might warrant adaptation.
    2.  **Repeated Failure to Improve:** After multiple "Fuck" or "Kill/Replace" cycles that fail to yield improvement, continued "No Action" might indicate the agent is stuck or missing a fundamental issue, requiring human strategic review.
    3.  **Alert from External Monitoring:** An external system monitoring overall system health or user satisfaction flags an issue that the KFM agent is not addressing (i.e., defaulting to "No Action" inappropriately).

*   **Information for Reviewer (Review Package Additions):**
    *   Trend data showing performance metrics over time.
    *   History of recent agent actions (or lack thereof) related to the area of concern.
    *   Contextual information about changing requirements or environment.

## 4. Review and Updates to HITL Guidelines

These HITL guidelines and specific triggers are subject to review and refinement based on:
*   Operational experience and logged HITL events.
*   Evolution of the KFM agent\'s capabilities and autonomy.
*   Changes in business requirements or ethical standards.
*   Feedback from human reviewers and stakeholders.

Regular audits of the HITL process will be conducted to ensure its effectiveness and efficiency. 