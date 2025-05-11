# Self-Assembling Agentic AI (KFM Paradigm) - Phase 1

**Version:** 1.0 (MVP - Phase 1)  
**Date:** 2025-05-05  
**Author:** Synthesized from provided documents by Gemini

*This document covers the tasks and objectives for the first 3 days of the 1-week MVP sprint.*

## 1. Introduction & Goals (MVP)

Develop a novel conceptual framework and a Minimum Viable Product (MVP) for a self-assembling Artificial Intelligence (AI) agent. The agent's self-assembly mechanism is inspired by the 'Kill, Fuck, Marry' (KFM) metaphor, modeling principles of agentic evolution to enhance adaptability, resilience, and performance in complex environments.

* **Primary Goal:** Create agents capable of dynamically altering their composition and behavior by selectively terminating underperforming components ('Kill'), engaging in temporary goal-oriented interactions ('Fuck'), or forming stable integrations ('Marry').
* **MVP Goal (1-Week Sprint):** Demonstrate the core KFM decision-to-composition change mechanism using simplified components, rule-based logic, and basic reflection within a Python-based agent, leveraging specified tools (Python, LangGraph, Google AI Studio, Cursor).

## 2. Conceptual Framework: Agentic Evolution via KFM

The KFM metaphor provides a vocabulary for the agent's dynamic decision-making regarding internal components and external interactions.

### Key Concepts

**Kill (Discard)**
: Identifying and eliminating/deactivating underperforming, redundant, detrimental, or irrelevant components, tools, or interaction patterns. Triggered by negative performance feedback, inefficiency, or goal shifts. Corresponds to component deprecation or halting failing reasoning branches.
: *Mechanism:* Unload module, disable API access, update component registry, abandon sub-tasks.
: *Requirement tag:* KFM-Kill

**Fuck (Integrate/Utilize Temporarily)**
: Temporary, opportunistic, goal-driven utilization of external tools, services, or agents without forming lasting dependencies. Triggered by immediate task needs or exploration. Analogous to short-term collaboration or experimentation.
: *Mechanism:* Dynamic function call, temporary API client instantiation, message passing, spawning transient sub-agents.
: *Requirement tag:* KFM-Fuck

**Marry (Persist/Integrate Deeply)**
: Forming stable, long-term, synergistic integrations with components, tools, or agents. Implies deeper coupling, state sharing, and coordination. Triggered by high performance, consistent utility, and synergy. Corresponds to saving successful behaviors/tools for future use.
: *Mechanism:* Load/link module, establish persistent connection, update core configuration, commit successful code to skill library.
: *Requirement tag:* KFM-Marry

## 3. Proposed KFM Agent Architecture (MVP)

The architecture integrates standard agent components with specific KFM modules operating within a continuous loop, implemented using LangGraph.

### Core Components

* **State Monitor:** Observes agent state (simulated performance, task requirements). Gathers data for KFM evaluation.
* **Component Registry:** Catalogs predefined internal components (Python functions/classes) with metadata (interface, task type, status: active/inactive).
* **KFM Planner/Decision Unit:** Evaluates monitored data against goals/heuristics (MVP: hardcoded rules) to decide KFM actions ('Kill', 'Marry').
* **Execution Engine:** Implements KFM decisions (activating/deactivating components in Registry) and executes tasks using the current active component.
* **Reflection Module:** Analyzes outcomes of KFM actions (simulated performance) using an LLM call to generate commentary (no dynamic updates to logic in MVP).

### KFM Decision Loop (Implemented via LangGraph)

1. **Monitor Node:** Calls `StateMonitor` to get current simulated performance and task requirements. Updates state.
2. **Evaluate/Decide KFM Node:** Calls `KFMPlanner` with current state data. Determines KFM action ('Kill'/'Marry' or None). Updates state.
3. **Execute Node:** Calls `ExecutionEngine`. First, applies the KFM decision (updates `ComponentRegistry`). Then, executes the current task using the active component identified via the `ComponentRegistry`. Updates state with results and simulated performance.
4. **Reflect Node:** If a KFM action was taken and execution succeeded, calls `ReflectionModule` (LLM via API) with action and outcome. Updates state with reflection text.

### Dynamic Composition Mechanisms (MVP Focus)

* **Component Activation/Deactivation:** Primary MVP mechanism. `ComponentRegistry` tracks `active` status. `ExecutionEngine` modifies status based on 'Kill'/'Marry' decisions. Implements `KFM-Kill` (deactivation) and basic `KFM-Marry` (activation).
* **Interface Management Requirement:** Components must adhere to a consistent function signature for the `ExecutionEngine` to call them interchangeably based on active status.

### State Management (LangGraph State)

* **Requirement:** Robust tracking of dynamic composition and performance history is critical for loop operation and debugging.
* **State Data (`KFMAgentState` TypedDict):** `task_input`, `task_type`, `performance_data` (from Monitor), `task_requirements` (from Monitor), `kfm_decision` (from Planner), `execution_result`, `overall_performance` (from Executor), `reflection` (from Reflector), `error` (optional string).
* **Implementation:** LangGraph manages state propagation between nodes.

## 4. MVP Scope & Requirements (1-Week Sprint)

Focus on demonstrating the core KFM dynamic self-modification loop (Monitor -> Evaluate -> Decide -> Execute -> Reflect), not a fully robust or intelligent agent. Excludes 'Fuck' action type for MVP simplicity.

### Requirements

* **MVP-REQ-001:** Agent must monitor simulated performance data (e.g., accuracy, latency) for 2-3 predefined components. *(Priority: High, Verification: Logging, State Inspection)*
* **MVP-REQ-002:** Agent must apply simple, explicitly defined, rule-based KFM logic within the KFM Planner to decide 'Kill' (deactivate) or 'Marry' (activate) based on monitored data and simulated task requirements. *(Priority: High, Verification: Unit Tests (Planner), Logging, State Inspection)*
* **MVP-REQ-003:** Agent must demonstrably change the 'active' status of components within the Component Registry based on KFM decisions from the Planner. *(Priority: High, Verification: Unit Tests (Registry, Executor), Logging, State Inspection)*
* **MVP-REQ-004:** Agent must execute a simple, predefined task (e.g., 'analyze_data') by calling the function associated with the currently active component for that task type, as determined by the Component Registry. *(Priority: High, Verification: Unit Tests (Executor), Logging)*
* **MVP-REQ-005:** Agent must invoke a basic reflection step via an external LLM API call (Google AI Studio/Gemini) when a KFM action ('Kill' or 'Marry') has been successfully executed. *(Priority: Medium, Verification: Logging, API Call Verification)*
* **MVP-REQ-006:** The reflection output (LLM commentary) must be logged but will NOT dynamically update the KFM rules within the MVP. *(Priority: High, Verification: Code Review, Logging)*
* **MVP-REQ-007:** Implementation must use Python 3.x. *(Priority: High, Verification: Environment Setup)*
* **MVP-REQ-008:** Development must utilize Cursor AI IDE features (e.g., code generation, debugging assistance) to meet the sprint timeline. *(Priority: High, Verification: Developer Confirmation)*
* **MVP-REQ-009:** LLM access must be through Google AI Studio using a configured API Key for a Gemini model. *(Priority: High, Verification: Configuration Check, API Call Verification)*
* **MVP-REQ-010:** The agent's control flow and state management must be implemented using the LangGraph framework. *(Priority: High, Verification: Code Review, Framework Usage)*
* **MVP-REQ-011:** State changes, KFM decisions, component activations/deactivations, task execution attempts, and reflection outputs must be clearly logged. *(Priority: High, Verification: Log Review)*
* **MVP-REQ-012:** Basic error handling must be implemented in execution steps to prevent crashes and log errors to the state. *(Priority: Medium, Verification: Code Review, Error Injection Test)*

### Scope Details

* **Components:** 2-3 simple Python functions/classes (e.g., `data_analyzer_fast_inaccurate`, `data_analyzer_slow_accurate`) with simulated logic and predictable outputs/performance characteristics for testing.
* **State Monitoring:** Simple dictionary holding mock performance data (e.g., `{'component_A': {'accuracy': 0.6, 'latency': 50}, ...}`). Data can be static or follow a simple predefined pattern for reproducible testing.
* **KFM Logic:** Hardcoded `if/elif/else` rules within the `KFMPlanner`. Example: "IF task requires accuracy > 0.8 AND `analyzer_accurate` is not active THEN 'Marry' `analyzer_accurate`", "IF task requires accuracy <= 0.8 AND `analyzer_fast` is not active THEN 'Marry' `analyzer_fast`", "IF active component accuracy < 0.6 THEN 'Kill' active component".
* **Dynamic Composition:** Focus solely on toggling the `active` flag in the `ComponentRegistry`.
* **Task:** A single, simple, repeatable task type (e.g., 'analyzer') invoked with static input data.
* **Exclusions:** No 'Fuck' action implementation, no runtime code generation, no dynamic loading, no complex tool use, no multi-agent interaction, no persistent memory beyond the single run state.

## 5. Detailed Development Tasks (Phase 1: Days 1-3)

### Day 1: Setup, Core Classes & Basic Tests

1. **T1.1:** Setup: Create project structure, initialize Git repository, set up Python virtual environment (Python 3.x).
2. **T1.2:** Install Dependencies: `pip install langgraph google-generativeai python-dotenv` (or similar).
3. **T1.3:** Configure Environment: Set up `.env` file for Google AI Studio API Key. Confirm Cursor AI IDE setup.
4. **T1.4:** Define Core Class Requirements: Document expected inputs, outputs, methods, and state attributes for `ComponentRegistry`, `StateMonitor`, component functions. *(Artifact: Design Doc Snippet/Comments)*
5. **T1.5:** Implement `ComponentRegistry`: Class with methods `register_component`, `set_active`, `get_active_component_func`. Store components in a dictionary. *(Requires Unit Tests)*
6. **T1.6:** Implement `StateMonitor`: Class with `get_performance_data`, `get_task_requirements` methods returning mock/static data structures. *(Requires Unit Tests)*
7. **T1.7:** Implement Dummy Components: Create 2-3 simple Python functions (e.g., `analyze_fast`, `analyze_accurate`) adhering to a defined signature. *(Requires Unit Tests)*
8. **T1.8:** **Unit Testing (Core):** Write and pass unit tests for `ComponentRegistry` (registration, activation/deactivation logic, retrieval). Test `StateMonitor` data structure output. Test dummy component function signatures and basic return values. *(Verification: Test Suite Execution)*
9. **T1.9:** **Documentation:** Add clear docstrings to all classes and methods created. *(Verification: Code Review)*
10. **T1.10:** **Code Review:** Perform self-review or peer-review of Day 1 code focusing on structure, clarity, and initial test coverage.

### Day 2: KFM Logic, Execution & Testing

1. **T2.1:** Define KFM Rule Requirements: Explicitly document the specific `IF/THEN` rules for 'Kill' and 'Marry' decisions based on accuracy/latency thresholds and task requirements for the MVP. *(Artifact: Rules Definition in Code Comments/Doc)*
2. **T2.2:** Implement `KFMPlanner`: Class with `decide_kfm_action` method implementing the defined rule-based logic. Takes performance data and requirements, returns action dictionary or None. *(Requires Unit Tests)*
3. **T2.3:** Implement `ExecutionEngine`: Class with `apply_kfm_action` (calls `ComponentRegistry.set_active`) and `execute_task` (gets active func from Registry, calls it, returns result and simulated performance). *(Requires Unit Tests)*
4. **T2.4:** **Unit Testing (Logic & Execution):** Write and pass unit tests for `KFMPlanner` covering all defined rule conditions and expected outputs. Test `ExecutionEngine.apply_kfm_action` effects on a mock Registry. Test `ExecutionEngine.execute_task` calls the correct active component. *(Verification: Test Suite Execution)*
5. **T2.5:** **Requirements Validation:** Manually verify that the implemented `KFMPlanner` rules exactly match the documented rule requirements (T2.1). *(Verification: Manual Check)*
6. **T2.6:** **Dependency Injection:** Ensure `KFMPlanner` and `ExecutionEngine` receive the `ComponentRegistry` instance via their constructors. *(Verification: Code Review)*
7. **T2.7:** **Logging:** Add `print` statements or basic `logging` calls within Planner and Executor methods to trace input data, decisions made, and actions taken. *(Verification: Log Output Review)*

### Day 3: LangGraph Framework Integration

1. **T3.1:** Define LangGraph State Requirements: Finalize the structure of the `KFMAgentState` TypedDict, ensuring all necessary fields for inter-node communication are present. *(Artifact: TypedDict Definition)*
2. **T3.2:** Implement `KFMAgentState` TypedDict in the main agent script. *(Testing note: Static type checking)*
3. **T3.3:** Define LangGraph Node Requirements: Document the specific state keys each node reads and writes. *(Artifact: Node Function Docstrings)*
4. **T3.4:** Implement LangGraph Nodes: Create functions (`monitor_state_node`, `kfm_decision_node`, `execute_action_node`) that take `KFMAgentState`, call the corresponding core class methods (Monitor, Planner, Executor), and return the updated state. *(Requires Integration Tests)*
5. **T3.5:** Define LangGraph Edge Requirements: Specify the exact sequence of node execution (Monitor -> Decide -> Execute -> Reflect -> END). *(Artifact: Graph Definition Code)*
6. **T3.6:** Build the Graph: Instantiate `StateGraph`, add nodes, set entry point, add edges according to the defined flow. *(Requires Integration Tests)*
7. **T3.7:** **Initial Integration Testing:** Test each node function individually by providing a sample input state dictionary and verifying the output state dictionary. Mock dependencies (like LLM calls) if necessary at this stage. *(Verification: Manual Test Execution)*
8. **T3.8:** **Documentation:** Add comments explaining the graph structure and the role of each node within the LangGraph definition. *(Verification: Code Review)*

## 6. MVP Evaluation Metrics (Relevant after Phase 1)

Evaluation focuses on verifying the KFM mechanism's functionality, traceability, and adherence to requirements within the MVP. Some metrics can be partially verified after Phase 1.

* **Functionality (Core Components):** Core classes (`ComponentRegistry`, `StateMonitor`, `KFMPlanner`, `ExecutionEngine`) pass unit tests. *(Target: 100% pass rate, Verification: Unit Test Suite Results)*
* **KFM Decision Rule Accuracy:** The `KFMPlanner` outputs the KFM decision ('Kill', 'Marry', None) that exactly matches the expected outcome based on the predefined rules for given mock inputs. *(Target: 100% accuracy on unit test cases covering all rules, Verification: Unit Test Suite Results (`KFMPlanner`))*
* **Basic Integration:** LangGraph nodes can be instantiated and call the correct core class methods. *(Target: Successful execution in initial integration tests (T3.7), Verification: Manual Test Execution Logs)*
* **Requirements Compliance (Partial):** Requirements related to core classes, KFM logic, and basic framework setup (subset of MVP-REQ-001 to MVP-REQ-012) are met. *(Target: Compliance for Day 1-3 tasks, Verification: Requirements Checklist Update)*

## 7. Future Directions (Beyond MVP)

* **Implement 'Fuck' Action:** Add capability for temporary tool/API usage.
* **Enhanced KFM Logic:** Replace rules with LLM reasoning, Reinforcement Learning, or multi-objective optimization considering cost/reliability.
* **True Self-Assembly:** Explore runtime code generation (LLMs) or dynamic module loading (`importlib`) for 'Marry' actions, including robust dependency and security management.
* **Persistent Memory:** Integrate vector databases (FAISS, Chroma) or knowledge graphs to allow the agent to learn and retain successful strategies/code across runs ('Marry' persistence).
* **Multi-Agent KFM Systems:** Extend KFM to agent populations using ACLs (e.g., FIPA-ACL via SPADE) and coordination frameworks (e.g., AutoGen, ADK).
* **Robustness & Scalability:** Improve dependency management, error handling, recovery; explore deployment on scalable platforms (e.g., Vertex AI Agent Engine).
* **Advanced Reflection:** Enable reflection output to dynamically update KFM heuristics or agent prompts.
* **Ethical Considerations:** Develop safeguards, oversight mechanisms, and ethical guidelines for autonomous component/agent modification and termination. 