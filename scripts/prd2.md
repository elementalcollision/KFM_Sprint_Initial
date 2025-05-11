# Self-Assembling Agentic AI (KFM Paradigm) - Phase 2
**Version:** 1.0 (MVP - Phase 2)
**Date:** 2025-05-05
**Author:** Synthesized from provided documents by Gemini

**Description:** This document covers the tasks and objectives for Days 4 and 5 of the 1-week MVP sprint, building upon the completion of Phase 1.

**Prerequisites:** Completion of Phase 1 PRD (ID: kfm_agent_prd_phase1_json) including functional core classes, KFM logic, and basic LangGraph structure.

---

## Introduction & Goals (MVP - Phase 2 Focus) (ID: 1_Introduction)

This phase focuses on completing the LangGraph loop integration, implementing state management, adding the live reflection component, and performing end-to-end testing of the KFM Agent MVP.

- **Phase 2 Goal:** Integrate all components into a functioning LangGraph application, enable state propagation, implement the LLM reflection call, and conduct thorough end-to-end testing to verify all MVP requirements.

---

## Proposed KFM Agent Architecture (MVP - Completion) (ID: 3_ProposedArchitecture)

This phase completes the implementation of the architecture defined in Phase 1, focusing on the interaction between LangGraph nodes and the reflection module.

### KFM Decision Loop (Implemented via LangGraph)

1. **Monitor Node:** (Completed in Phase 1)
2. **Evaluate/Decide KFM Node:** (Completed in Phase 1)
3. **Execute Node:** (Completed in Phase 1 - Requires testing within full loop)
4. **Reflect Node:** Implement live LLM call and state update based on KFM action and execution outcome.
### State Management (LangGraph State)

- **Requirement:** Verify robust tracking and propagation of the full `KFMAgentState` through the compiled LangGraph application.
- **State Data (`KFMAgentState` TypedDict):** Ensure all fields (`task_input`, `task_type`, `performance_data`, `task_requirements`, `kfm_decision`, `execution_result`, `overall_performance`, `reflection`, `error`) are correctly populated and accessed by relevant nodes.

---

## MVP Scope & Requirements (Phase 2 Focus) (ID: 4_MVP_Scope)

Phase 2 completes the implementation within the overall MVP scope defined previously, specifically focusing on loop execution, reflection, and testing.

### Requirements

| ID | Description | Priority | Verification |
|---|---|---|---|
| MVP-REQ-005 | Agent must invoke a basic reflection step via an external LLM API call (Google AI Studio/Gemini) when a KFM action ('Kill' or 'Marry') has been successfully executed. | Medium | Logging, API Call Verification (Focus of Phase 2) |
| MVP-REQ-009 | LLM access must be through Google AI Studio using a configured API Key for a Gemini model. | High | Configuration Check, API Call Verification (Focus of Phase 2) |
| MVP-REQ-010 | The agent's control flow and state management must be implemented using the LangGraph framework. | High | Code Review, Framework Usage, E2E Testing (Focus of Phase 2) |
| MVP-REQ-011 | State changes, KFM decisions, component activations/deactivations, task execution attempts, and reflection outputs must be clearly logged. | High | Log Review (Focus of Phase 2) |
| MVP-REQ-012 | Basic error handling must be implemented in execution steps to prevent crashes and log errors to the state. | Medium | Code Review, Error Injection Test (Focus of Phase 2) |

### Scope Details

- **Focus:** LangGraph compilation, state propagation, reflection node implementation (with live LLM call), error handling within the loop, end-to-end testing.

---

## Detailed Development Tasks (Phase 2: Days 4-5) (ID: 5_DevelopmentTasks)

### Day 4: State Management, Loop Execution & Basic Reflection

- **T4.1:** Verify State Propagation: Ensure data (performance, decision, results) flows correctly between nodes via the `KFMAgentState` object within the graph. (Testing: Requires Debugging/Tracing)
- **T4.2:** Compile LangGraph App: Call `workflow.compile()` to create the runnable application. (Testing: Requires E2E Tests)
- **T4.3:** Implement Reflection Node Structure: Create `reflection_node` function. Add initial logic to check if `kfm_decision` exists in state and `error` is None. (Testing: Requires E2E Tests)
- **T4.4:** Implement `call_llm_for_reflection` function shell: Include prompt formatting using state data, but initially return a mock string instead of making a real API call. (Testing: Requires Unit Test for prompt formatting)
- **T4.5:** Integrate Reflection Call (Mocked): Call the mocked `call_llm_for_reflection` from `reflection_node` and update the state. (Testing: Requires E2E Tests)
- **T4.6:** **Integration Testing (Compiled Graph):** Invoke the compiled `kfm_app` with an initial input state. Trace the execution flow through all nodes (including mocked reflection). Verify the final state contains expected values. (Verification: Debugging, Log Review, Final State Inspection)
- **T4.7:** **Debugging:** Utilize Cursor AI features and print/logging statements to step through the graph execution and diagnose state propagation issues. (Verification: Manual Debugging Session)
- **T4.8:** **Error Handling:** Implement basic `try...except` blocks within the `execute_action_node` to catch potential errors during component execution. Update the `error` field in the state if an exception occurs. (Verification: Code Review, Error Injection Test)
- **T4.9:** **Logging:** Refine logging to clearly show entry/exit of each node and key state values being passed/modified. (Verification: Log Review)
### Day 5: Live Reflection & End-to-End Testing

- **T5.1:** Define Reflection Prompt Requirements: Finalize the exact text and structure of the prompt sent to the LLM, ensuring it clearly states the KFM action and outcome. (Artifact: Prompt String in Code)
- **T5.2:** Implement Live LLM Call: Replace the mock response in `call_llm_for_reflection` with the actual `google.generativeai` API call using the configured API key. (Testing: Requires Live API Test)
- **T5.3:** Add Error Handling for API Call: Include `try...except` around the LLM API call to handle potential network or API errors gracefully, logging the error. (Testing: Requires Mocking API Errors)
- **T5.4:** **API Key Management:** Verify API key is loaded securely from environment variables and not hardcoded. (Verification: Code Review, Security Check)
- **T5.5:** **End-to-End Testing (Live Reflection):** Run the full `kfm_app` multiple times with different initial inputs designed to trigger various KFM rule conditions ('Kill', 'Marry', No Action). (Verification: Test Execution & Log Review)
- **T5.6:** **Verification Steps (E2E):** For each test run: (a) Verify the correct KFM decision is logged. (b) Verify the Component Registry state reflects the decision. (c) Verify the correct component function is logged as being executed. (d) Verify the reflection node is triggered appropriately. (e) Verify the LLM reflection output is logged (or skipped correctly). (f) Verify the final state is as expected. (Verification: Manual Checklist against Logs/State)
- **T5.7:** **Requirements Validation (MVP-REQ Check):** Systematically check if each MVP requirement (MVP-REQ-001 to MVP-REQ-012) is met by the completed implementation and verified by tests. (Artifact: Requirements Traceability Matrix/Checklist)

---

## MVP Evaluation Metrics (Final) (ID: 6_EvaluationMetrics)

Evaluation focuses on verifying the KFM mechanism's functionality, traceability, and adherence to requirements within the completed MVP.

### Metrics

| Metric | Description | Target | Verification |
|---|---|---|---|
| Functionality (Loop Completion) | Agent successfully completes the full Monitor -> Evaluate -> Decide -> Execute -> Reflect cycle for various input scenarios without unhandled exceptions. | 100% completion for defined test scenarios | E2E Test Execution Logs |
| KFM Decision Rule Accuracy | The `KFMPlanner` outputs the KFM decision ('Kill', 'Marry', None) that exactly matches the expected outcome based on the predefined rules for given mock inputs. | 100% accuracy on unit test cases covering all rules | Unit Test Suite Results (`KFMPlanner`) |
| Dynamic Composition Verification | The `active` status in the `ComponentRegistry` is correctly updated following a KFM decision, and the `ExecutionEngine` demonstrably calls the component matching the updated active status. | Correct component usage logged in 100% of E2E tests involving KFM actions | E2E Test Logs, State Inspection |
| State Traceability & Logging | Key state transitions, KFM decisions, component changes, execution results, and reflection outputs are clearly and accurately logged. | All key events logged per test scenario | Manual Log Review against E2E tests |
| Reflection Trigger Logic | The LLM reflection call is triggered if and only if a KFM action ('Kill' or 'Marry') was decided AND the execution step completed without error. | Correct trigger behavior in 100% of E2E test scenarios | E2E Test Logs |
| Requirements Compliance | All defined MVP requirements (MVP-REQ-001 to MVP-REQ-012) are met. | 100% compliance | Requirements Traceability Checklist (T5.7) |

---

## Future Directions (Beyond MVP) (ID: 7_FutureDirections)

Refer to Phase 1 PRD (ID: kfm_agent_prd_phase1_json) for full list of future directions.

--- 