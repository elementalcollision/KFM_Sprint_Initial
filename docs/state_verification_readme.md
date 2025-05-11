# State Propagation Verification Framework

## Overview

The State Propagation Verification Framework is a comprehensive tool for validating, inspecting, and debugging state propagation throughout the KFM Agent's execution flow. It provides mechanisms to ensure state consistency, field validation, and proper transitions between components.

This framework was designed to help developers identify issues early in the development process, debug complex state-related bugs, and provide clear visualizations of state changes throughout the agent's execution.

## Key Features

- **Multi-level verification**: Choose from BASIC, STANDARD, DETAILED, or DIAGNOSTIC verification levels
- **Field validation**: Validate individual state fields against predefined rules
- **State validation**: Ensure overall state integrity with customizable validators
- **Transition validation**: Verify proper state transitions between components
- **Visualization**: Generate visual representations of state flow
- **Performance monitoring**: Track metrics during state propagation
- **Configurable verbosity**: Adjust logging and reporting detail based on needs
- **Integration with LangGraph**: Seamless integration with LangGraph's node architecture

## Architecture

The framework consists of several key components:

1. **Core Verification Engine** (`state_verification.py`): Provides the fundamental validation mechanisms
2. **Integration Layer** (`state_verification_integration.py`): Connects verification to the LangGraph framework
3. **Execution Tools** (`run_state_verification.py`): Provides CLI tools for verification
4. **Visualization Helpers** (`visualization_helper.py`): Enhances output visualization
5. **Test Integration** (`verification_utils.py`): Specifically for verifying e2e test execution

## Configuration

The framework is highly configurable to adapt to different use cases:

```python
from src.state_verification import (
    configure_verification_framework,
    VERIFICATION_LEVEL_STANDARD,
    reset_verification,
    register_common_validators
)

# Reset any previous configuration
reset_verification()

# Configure the framework
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_STANDARD,  # BASIC, STANDARD, DETAILED, or DIAGNOSTIC
    visualization_enabled=True,
    output_dir="logs/verification",
    log_state_size=True,
    verbosity=1  # 1=low, 2=medium, 3=high
)

# Register common validators
register_common_validators()
```

## Verification Levels

The framework supports 4 distinct verification levels, each with increasing comprehensiveness:

| Level | Constant | Value | Use Case |
|-------|----------|-------|----------|
| BASIC | `VERIFICATION_LEVEL_BASIC` | 1 | Production, minimal overhead |
| STANDARD | `VERIFICATION_LEVEL_STANDARD` | 2 | Development, general purpose |
| DETAILED | `VERIFICATION_LEVEL_DETAILED` | 3 | Debugging, comprehensive validation |
| DIAGNOSTIC | `VERIFICATION_LEVEL_DIAGNOSTIC` | 4 | Deep debugging, maximum instrumentation |

For more details on each level, see [Verbosity Levels Documentation](state_verification_verbosity.md).

## Usage Examples

### Basic Integration with LangGraph

```python
from src.state_verification_integration import (
    initialize_verification_integration,
    create_verification_graph
)

# Initialize verification integration
initialize_verification_integration()

# Create a verification-enabled graph
graph, components = create_verification_graph()

# Use the graph as normal
final_state = graph.invoke(initial_state)
```

### Custom Field Validators

```python
from src.state_verification import register_field_validator, ValidationResult

# Define a field validator
def validate_task_name(value):
    if not isinstance(value, str):
        return ValidationResult(False, f"Task name must be a string, got {type(value)}")
    if len(value) < 3:
        return ValidationResult(False, "Task name too short")
    return ValidationResult(True, "Valid task name")

# Register the validator
register_field_validator("task_name", validate_task_name)
```

### Custom State Transition Validators

```python
from src.state_verification import register_transition_validator, ValidationResult

# Define a transition validator
def validate_component_transition(from_state, to_state):
    from_comp = from_state.get("active_component")
    to_comp = to_state.get("active_component")
    
    # Define valid transitions
    allowed_transitions = {
        "parse_input": ["analyze_fast"],
        "analyze_fast": ["monitor"],
        "monitor": ["feedback"],
        "feedback": ["reflect"]
    }
    
    if from_comp in allowed_transitions and to_comp in allowed_transitions[from_comp]:
        return ValidationResult(True, f"Valid transition from {from_comp} to {to_comp}")
    
    return ValidationResult(False, f"Invalid transition from {from_comp} to {to_comp}")

# Register the validator
register_transition_validator(validate_component_transition)
```

### Running Verification Demo

The framework includes a demonstration script that shows different verification levels in action:

```bash
# Run with default (STANDARD) level
python src/run_state_verification_demo.py

# Run with BASIC level
python src/run_state_verification_demo.py --level=basic

# Run with DETAILED level
python src/run_state_verification_demo.py --level=detailed

# Compare all levels
python src/run_state_verification_demo.py --compare
```

## E2E Test Integration

The framework includes specific support for end-to-end test verification:

```python
from src.verification_utils import (
    verify_e2e_test_results,
    verify_specific_test_case
)

# Verify general e2e test results
verification_results = verify_e2e_test_results(final_state)
print(f"Test passed: {all(verification_results.values())}")

# Verify a specific test case with expected values
specific_results = verify_specific_test_case(
    final_state,
    expected_values={
        "expected_reflection_count": 1,
        "expected_kfm_action": "Monitor"
    }
)
print(f"Specific test passed: {all(specific_results.values())}")
```

## Common Use Cases

1. **Debugging complex state issues**: Use DIAGNOSTIC level to get complete state history
2. **CI/CD validation**: Use STANDARD level to verify state transitions in automated tests
3. **Performance analysis**: Use DETAILED level to track state size and performance metrics
4. **Production monitoring**: Use BASIC level for lightweight state validation

## Visualization

For more advanced visualization, use the included helper:

```bash
python src/visualization_helper.py --report=logs/verification/report.json --level=3
```

This will generate enhanced HTML visualizations and performance graphs.

## Best Practices

1. **Start with STANDARD level**: Only escalate to higher levels when needed
2. **Register custom validators early**: Add them before graph creation
3. **Keep validation functions pure**: Avoid side effects in validators
4. **Be selective with tracked fields**: Not all fields need tracking
5. **Clean up logs regularly**: Higher levels generate significant log data

## Advanced Features

### Field Tracking

Track specific fields across transitions:

```python
from src.state_verification import track_field

# Track these fields across transitions
track_field("task_name")
track_field("active_component")
track_field("kfm_action")
```

### Generating Reports

Generate rich reports of state flow:

```python
from src.state_verification_integration import generate_state_flow_report

# Generate a report after execution
report_path = generate_state_flow_report("logs/state_verification")
print(f"Report generated: {report_path}")
```

### Custom Wrapper Functions

Create custom verification functions:

```python
from src.state_verification_integration import verify_node_wrapper

def custom_node(state):
    # Node implementation...
    return updated_state

# Wrap with verification
wrapped_node = lambda state: verify_node_wrapper(
    state, 
    custom_node(state), 
    node_name="custom_node"
)
```

## Contributing

When extending the verification framework:

1. Follow the existing patterns for validators
2. Keep performance impact in mind, especially for higher levels
3. Add tests for new validators
4. Update documentation for new features

## Troubleshooting

| Issue | Solution |
|-------|----------|
| High memory usage | Lower verification level or set `log_state_size=False` |
| Missing validation | Ensure validators are registered before graph creation |
| Slow performance | Use BASIC level or selectively disable features |
| Excessive logging | Lower verbosity level or adjust logger configuration | 