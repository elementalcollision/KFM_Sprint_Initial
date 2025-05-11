# Compiled Graph Integration Testing Framework

This document describes the comprehensive test framework for the KFM Agent compiled graph execution. The framework is designed to verify the proper integration of all nodes, trace execution paths, and validate state transformations throughout the workflow.

## Test Framework Structure

### Core Components

1. **CompiledGraphTestHarness** (`tests/test_compiled_graph_execution.py`)
   - Base test class providing utilities for all compiled graph tests
   - Handles mock component setup
   - Provides graph execution utilities
   - Includes tracing and analysis tools
   - Implements verification helpers

2. **Test Scenarios** (`tests/test_scenarios.py`)
   - Defines standardized test scenarios to use across tests
   - Each scenario includes:
     - Input data
     - Expected node execution sequence
     - Expected outputs and state fields
     - Mock component configuration

3. **End-to-End Test Suite** (`tests/test_e2e_compiled_graph.py`)
   - Tests full graph execution with different scenarios
   - Verifies entire workflow execution including all nodes
   - Tests both happy paths and error scenarios

4. **Reflection Integration Tests** (`tests/test_reflection_compiled_integration.py`)
   - Specifically tests the integration of the reflection node
   - Verifies mocked LLM calls work correctly in the graph context
   - Tests extraction and analysis of reflection insights
   - Validates proper error handling in reflection

## Test Coverage

### Node Execution Sequence

The framework verifies that nodes are executed in the correct order:

```
monitor → decide → execute → reflect
```

Each test case traces the full execution path and validates that:
- All expected nodes are executed
- Nodes are executed in the expected order
- Each node receives the expected input state
- Each node produces the expected output state

### State Transformations

The framework tracks and verifies state transformations between nodes:

1. **Initial State** → **Monitored State**
   - Verifies performance data is added
   - Verifies task requirements are added

2. **Monitored State** → **Decision State**
   - Verifies KFM action is added
   - Verifies action includes component and reason

3. **Decision State** → **Execution State**
   - Verifies active component is set
   - Verifies execution results are added
   - Verifies execution performance metrics are added

4. **Execution State** → **Reflection State**
   - Verifies reflection text is added
   - Verifies reflection insights are extracted
   - Verifies reflection analysis is performed

### KFM Action Types

The framework tests all three KFM action types:

- **Keep** - Continue using the current component
- **Kill** - Stop using a problematic component
- **Marry** - Commit to a high-performing component

Each action type is tested to ensure:
- The action is correctly reflected in the state
- Appropriate components are selected
- Reflection properly addresses the action type

### Error Handling

The framework tests error handling at different stages:

1. **Execution Errors**
   - Tests errors during task execution
   - Verifies error is captured in state
   - Verifies workflow completes gracefully

2. **Reflection Errors**
   - Tests errors during LLM reflection
   - Verifies fallback error message
   - Ensures execution results are preserved

3. **Validation Errors**
   - Tests invalid KFM actions
   - Tests missing required fields
   - Verifies appropriate error messages

## Mock Implementation

The framework uses mock implementations for all external components:

1. **Mock Registry** - Configuration and component registry
2. **Mock Monitor** - Performance monitoring and requirements
3. **Mock Planner** - KFM decision making
4. **Mock Execution Engine** - Task execution
5. **Mock LLM** - Reflection generation

Each mock is configured for different test scenarios to simulate various real-world conditions.

## Tracing and Analysis

The framework includes sophisticated tracing and analysis tools:

1. **Trace History** - Captures detailed execution trace
2. **State Diff Analysis** - Identifies changes between states
3. **Execution Metrics** - Measures timing and performance
4. **Trace Visualization** - Creates human-readable execution path

Trace logs are saved to the `logs/test_traces/` directory for inspection and debugging.

## Running the Tests

To run the full test suite:

```bash
python -m unittest discover -s tests -p "test_*compiled*.py"
```

To run specific test files:

```bash
python -m unittest tests/test_e2e_compiled_graph.py
python -m unittest tests/test_reflection_compiled_integration.py
```

## Extending the Test Suite

To add new test scenarios:

1. Add scenario definitions to `tests/test_scenarios.py`
2. Create test methods in the appropriate test class
3. Configure mocks for the new scenario
4. Implement verification for expected outcomes

## Test Reports

The test framework generates detailed execution reports including:

1. Node execution sequence
2. State transformations
3. Performance metrics
4. Validation results

These reports are available in the test output and trace files.

## Coverage Requirements

The test suite ensures comprehensive coverage of:

- All node implementations
- All execution paths
- All KFM action types
- All error handling
- Edge cases and boundary conditions

This testing approach ensures the compiled graph operates correctly in various scenarios and provides proper error handling. 