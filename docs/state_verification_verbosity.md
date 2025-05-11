# State Verification Framework: Verbosity Levels

This document explains the different verbosity levels available in the State Propagation Verification Framework and when to use each level.

## Overview

The State Verification Framework supports multiple verbosity levels to provide flexibility in balancing between:
- Performance overhead
- Verification detail
- Visualization richness
- Log output verbosity

These levels allow you to choose the right amount of verification based on your current needs - from lightweight checks during normal operation to comprehensive diagnostics during debugging.

## Available Verification Levels

The framework offers four verification levels, each with increasing comprehensiveness:

### 1. BASIC Level

**Constant:** `VERIFICATION_LEVEL_BASIC` (value: 1)

**Characteristics:**
- Minimal overhead
- Only essential state consistency checks
- Simple transition validation
- No field-level validation
- Minimal logging

**Best for:**
- Production environments
- Performance-sensitive scenarios
- High-throughput systems
- Initial testing phases

**Example configuration:**
```python
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_BASIC,
    visualization_enabled=False,
    output_dir="logs/verification",
    verbosity=1
)
```

### 2. STANDARD Level (Default)

**Constant:** `VERIFICATION_LEVEL_STANDARD` (value: 2)

**Characteristics:**
- Moderate overhead
- Full state history tracking
- Basic field validation
- Transition validation
- Standard logging output
- Simple visualization

**Best for:**
- Development environments
- Testing environments
- General purpose verification
- CI/CD pipelines

**Example configuration:**
```python
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_STANDARD,
    visualization_enabled=True,
    output_dir="logs/verification",
    verbosity=1
)
```

### 3. DETAILED Level

**Constant:** `VERIFICATION_LEVEL_DETAILED` (value: 3)

**Characteristics:**
- Higher overhead
- Comprehensive field validation
- Extended state history
- Detailed transition analysis
- Enhanced visualization
- Verbose logging

**Best for:**
- Debugging sessions
- Integration testing
- Finding complex state bugs
- When standard verification misses issues

**Example configuration:**
```python
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_DETAILED,
    visualization_enabled=True,
    output_dir="logs/verification",
    log_state_size=True,
    verbosity=2
)
```

### 4. DIAGNOSTIC Level

**Constant:** `VERIFICATION_LEVEL_DIAGNOSTIC` (value: 4)

**Characteristics:**
- Maximum instrumentation
- Complete field validation with detailed results
- Performance metrics collection
- Full state history with timestamps
- Comprehensive visualization
- Maximum verbosity logging

**Best for:**
- Deep debugging of complex issues
- Performance analysis
- State flow optimization
- In-depth analysis of component interactions

**Example configuration:**
```python
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_DIAGNOSTIC,
    visualization_enabled=True,
    output_dir="logs/verification",
    log_state_size=True,
    verbosity=3
)
```

## Performance Considerations

Higher verification levels add more overhead to the system. Here's a general guideline:

| Level | Typical Overhead | State Size Impact | Log Volume |
|-------|------------------|-------------------|------------|
| BASIC | <5% | Minimal | Low |
| STANDARD | 5-15% | Moderate | Medium |
| DETAILED | 15-30% | Significant | High |
| DIAGNOSTIC | 30-50%+ | Maximum | Very High |

## Choosing the Right Level

- **For development**: Start with `STANDARD` level as a default
- **For troubleshooting**: Escalate to `DETAILED` when you need more information
- **For critical bugs**: Use `DIAGNOSTIC` to capture every detail
- **For production**: Consider `BASIC` to minimize overhead

## Command-line Usage

The verification framework can be run with different verbosity levels using the provided demo script:

```bash
# Run with default (STANDARD) level
python src/run_state_verification_demo.py

# Run with BASIC level
python src/run_state_verification_demo.py --level=basic

# Run with DETAILED level
python src/run_state_verification_demo.py --level=detailed

# Run with DIAGNOSTIC level
python src/run_state_verification_demo.py --level=diagnostic

# Compare all levels
python src/run_state_verification_demo.py --compare
```

## Setting Verbosity Programmatically

```python
from src.state_verification import (
    configure_verification_framework,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC
)

# Configure for a specific level
configure_verification_framework(
    verification_level=VERIFICATION_LEVEL_DETAILED,
    visualization_enabled=True,
    output_dir="logs/verification",
    log_state_size=True,
    verbosity=2  # Verbosity: 1=low, 2=medium, 3=high
)
```

## Example: Visualization Differences

The visualization output becomes more detailed with higher verification levels:

- **BASIC**: Simple state flow diagram with minimal node details
- **STANDARD**: State flow with transition information and basic state content
- **DETAILED**: Detailed state flow with validation results and state diffs
- **DIAGNOSTIC**: Comprehensive visualization with timestamps, performance metrics, and full validation details

## Best Practices

1. **Layer your verification**: Use BASIC/STANDARD for regular tests, DETAILED/DIAGNOSTIC for specific troubleshooting
2. **Monitor performance impact**: Watch memory usage with higher levels
3. **Limit log storage**: Higher levels generate significant log volume
4. **Use visualization selectively**: Only enable it when needed at higher levels
5. **Rotate logs frequently**: Especially with DIAGNOSTIC level

## Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| High memory usage | Lower verification level or implement custom state filters |
| Slow performance | Reduce level or add custom verification for specific fields only |
| Excessive logging | Adjust verbosity parameter independent of verification level |
| False positives | Fine-tune validators at DETAILED level before using DIAGNOSTIC |

## Additional Resources

- See `examples/test_states/` for sample test states
- Check `tests/test_e2e_verification_levels.py` for examples of running with different levels
- Run the demo script with `--compare` flag to see performance differences 