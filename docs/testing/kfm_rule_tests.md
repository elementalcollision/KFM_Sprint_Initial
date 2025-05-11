# KFM Rule Condition End-to-End Tests

This document provides comprehensive documentation for the KFM (Kill, Marry, No Action) rule condition end-to-end test suite.

## Overview

The KFM rule condition tests validate that the KFM agent correctly applies decision rules based on component performance metrics. These tests cover all possible decision paths:

1. **Kill Action**: Triggered when a component performs significantly below requirements
2. **Marry Action**: Triggered when a component performs exceptionally well
3. **No Action**: Triggered when conditions don't clearly indicate Kill or Marry

## Test Suite Structure

The test suite is organized hierarchically:

```
KFMRuleTestSuite (base class)
├── TestKillActionScenarios
│   ├── test_standard_kill_scenario
│   ├── test_boundary_kill_scenario
│   ├── test_edge_case_kill_scenario
│   └── test_kill_action_with_reflection_validation
├── TestMarryActionScenarios
│   ├── test_standard_marry_scenario
│   ├── test_best_of_multiple_marry_scenario
│   ├── test_conflicting_metrics_marry_scenario
│   └── test_marry_action_with_historical_context
└── TestNoActionScenarios
    ├── test_mixed_signals_no_action_scenario
    ├── test_below_threshold_no_action_scenario
    ├── test_gradually_changing_metrics_no_action_scenario
    ├── test_no_action_with_reflection_validation
    └── test_no_action_with_multiple_components
```

## Base Test Suite

### KFMRuleTestSuite

This is the base class that all KFM rule test classes inherit from. It extends `CompiledGraphTestHarness` to provide specific utilities for testing KFM rule conditions.

Key features:
- **Configuration Methods**: Helpers to set up test scenarios with specific performance metrics
- **Mock Management**: Handles creation and configuration of mocks for component managers and performance monitors
- **Verification Methods**: Tools to verify KFM actions in the final state
- **Reporting**: Captures and saves test results and logs

## Kill Action Tests

### TestKillActionScenarios

These tests verify that the KFM agent correctly triggers the "Kill" action when performance metrics are poor.

#### Test Cases:

1. **test_standard_kill_scenario**
   - **What**: Tests a clear-cut case where a component's performance is significantly below thresholds
   - **Why**: Ensures the basic Kill action functionality works for obvious cases
   - **Specifics**: Component has 0.6 accuracy (vs 0.8 required) and 2.5s latency (vs 1.0s max)

2. **test_boundary_kill_scenario**
   - **What**: Tests a case where performance metrics are just barely below thresholds
   - **Why**: Verifies the system correctly handles boundary conditions
   - **Specifics**: Component has 0.78 accuracy (vs 0.8 required) and 1.05s latency (vs 1.0s max)

3. **test_edge_case_kill_scenario**
   - **What**: Tests extreme performance metrics with multiple underperforming components
   - **Why**: Ensures the system can handle extreme conditions and correctly choose the worst component
   - **Specifics**: Three components with varying degrees of poor performance, unusual input data

4. **test_kill_action_with_reflection_validation**
   - **What**: Tests that the reflection API correctly analyzes a Kill decision
   - **Why**: Verifies that the LLM-based reflection provides appropriate reasoning about Kill actions
   - **Specifics**: Mocks the LLM reflection call and verifies the contents are analyzed correctly

## Marry Action Tests

### TestMarryActionScenarios

These tests verify that the KFM agent correctly triggers the "Marry" action when a component performs exceptionally well.

#### Test Cases:

1. **test_standard_marry_scenario**
   - **What**: Tests a clear case where a component's performance is significantly above thresholds
   - **Why**: Ensures the basic Marry action functionality works for obvious cases
   - **Specifics**: Component has 0.95 accuracy (vs 0.8 required) and 0.3s latency (vs 1.0s max)

2. **test_best_of_multiple_marry_scenario**
   - **What**: Tests when multiple components have excellent performance
   - **Why**: Ensures the system correctly selects the best component when multiple are excellent
   - **Specifics**: Two components with excellent metrics, verifies the better one is selected

3. **test_conflicting_metrics_marry_scenario**
   - **What**: Tests when components have conflicting excellence (one better in accuracy, one in latency)
   - **Why**: Verifies correct handling of tradeoffs between different performance metrics
   - **Specifics**: One component with 0.98 accuracy/0.4s latency, another with 0.88 accuracy/0.2s latency

4. **test_marry_action_with_historical_context**
   - **What**: Tests that historical performance is considered in Marry decisions
   - **Why**: Ensures the system rewards consistent excellence, not just current performance
   - **Specifics**: Mocks historical data showing consistent excellence and verifies it's considered

## No Action Tests

### TestNoActionScenarios

These tests verify that the KFM agent correctly determines when no action is needed based on performance metrics.

#### Test Cases:

1. **test_mixed_signals_no_action_scenario**
   - **What**: Tests when a component has good accuracy but poor latency (mixed signals)
   - **Why**: Ensures ambiguous performance signals don't trigger actions prematurely
   - **Specifics**: Component with 0.85 accuracy (good) but 1.2s latency (poor)

2. **test_below_threshold_no_action_scenario**
   - **What**: Tests when all components perform below threshold but similarly
   - **Why**: Verifies the system doesn't kill arbitrarily when all options are similarly suboptimal
   - **Specifics**: Multiple components all slightly below thresholds with similar performance

3. **test_gradually_changing_metrics_no_action_scenario**
   - **What**: Tests performance metrics that are slowly changing over time
   - **Why**: Ensures the system doesn't overreact to gradual changes
   - **Specifics**: Historical data showing slowly decreasing accuracy and increasing latency

4. **test_no_action_with_reflection_validation**
   - **What**: Tests that the reflection API correctly analyzes a No Action decision
   - **Why**: Verifies that the LLM-based reflection provides appropriate reasoning about No Action
   - **Specifics**: Mocks the LLM reflection call and verifies the analysis is appropriate

5. **test_no_action_with_multiple_components**
   - **What**: Tests when multiple components all perform adequately (neither excellent nor poor)
   - **Why**: Ensures the system maintains status quo when all components are performing adequately
   - **Specifics**: Three components all meeting thresholds but not excelling

## Test Reporter

The test suite includes a `TestReporter` class that generates detailed reports and visualizations:

- **Summary Reports**: Overall test statistics and pass/fail counts
- **Detailed Reports**: Comprehensive test results with timestamps and logs
- **Visualizations**: Charts showing test results by category
- **CI Integration**: Reports suitable for continuous integration environments

## Running the Tests

You can run the tests using the provided script:

```bash
# Run all KFM rule tests
python scripts/run_kfm_rule_tests.py

# Run only Kill action tests
python scripts/run_kfm_rule_tests.py --test-category kill

# Run only Marry action tests
python scripts/run_kfm_rule_tests.py --test-category marry

# Run only No Action tests
python scripts/run_kfm_rule_tests.py --test-category no_action

# Generate visualizations
python scripts/run_kfm_rule_tests.py --visualize

# Run in CI mode
python scripts/run_kfm_rule_tests.py --ci-mode

# Generate a summary report
python scripts/run_kfm_rule_tests.py --summarize

# Generate an HTML summary report
python scripts/run_kfm_rule_tests.py --summarize --html-summary

# Generate a summary report including only the last 3 test runs
python scripts/run_kfm_rule_tests.py --summarize --last-n=3
```

### Command Line Options

- `--output-dir PATH`: Directory to save test reports (default: 'test_reports/kfm_rules')
- `--test-category CATEGORY`: Which test category to run ('kill', 'marry', 'no_action', 'all')
- `--visualize`: Generate visualizations of test results
- `--ci-mode`: Run in CI mode, generating CI-friendly reports
- `--summarize`: Generate a summary report after running tests
- `--html-summary`: Generate an HTML summary report instead of markdown
- `--last-n N`: Include only the last N test runs in the summary report

## Summary Reporting

The test suite includes a comprehensive summary reporting mechanism that aggregates results from multiple test runs:

### Summary Report Features

1. **Multi-Run Aggregation**: Combines results from multiple test runs to show trends
2. **Category Statistics**: Shows pass rates and average durations by test category
3. **Individual Test Case Analysis**: Provides metrics for each test case
4. **Visualizations**: Generates charts showing pass/fail rates and execution times
5. **HTML and Markdown Formats**: Supports both formats for different environments

### Running the Summary Generator Independently

You can generate a summary report without running tests by using the summarize script directly:

```bash
python scripts/summarize_kfm_test_results.py --report-dir=/path/to/reports --last-n=5
```

Options:
- `--report-dir PATH`: Directory containing test reports
- `--output FILENAME`: Output file name (default: 'test_summary.md' or 'test_summary.html')
- `--last-n N`: Include only the last N test runs in the summary
- `--html`: Generate HTML output instead of markdown

### Example Summary Report

The summary report includes:

- Overall statistics (total tests, pass rate, duration)
- Category-level statistics (tests per category, pass rates, durations)
- Individual test case statistics (runs, pass rates, average durations)
- List of included test reports with timestamps
- Visualizations showing pass/fail rates and execution times by category

## Interpreting Test Results

The test results are saved in JSON format with these components:

1. **Individual Test Results**: Detailed information about each test run
2. **Summary Report**: Overall statistics about the test suite execution
3. **Visualizations**: Charts showing pass/fail rates and execution times by category

### Test Success Criteria

A test is considered successful if:

1. The KFM agent applies the correct action ('kill', 'marry', or 'none')
2. The action is applied to the correct component
3. The action includes appropriate reasoning
4. The reflection contains relevant analysis of the decision

## Extending the Test Suite

To add new test cases:

1. Identify the appropriate test class based on the action to test
2. Add a new test method with descriptive name and docstring
3. Configure the scenario using the appropriate configuration method
4. Define expected log patterns
5. Execute and verify the scenario
6. Add specific assertions for the test case

Example:

```python
def test_new_kill_scenario(self):
    """
    Test a new Kill scenario under specific conditions.
    
    This test verifies that...
    """
    # Configure the scenario
    self.configure_kill_scenario(custom_param=True)
    
    # Define expected log patterns
    expected_log_patterns = [...]
    
    # Execute and verify
    final_state = self.execute_and_verify_scenario(
        expected_action="kill",
        expected_log_patterns=expected_log_patterns,
        scenario_name="new_kill_scenario"
    )
    
    # Add specific assertions
    self.assertEqual(...)
``` 