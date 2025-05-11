# KFM Rule Condition Test Suite

## Overview

This directory contains end-to-end tests for the KFM (Kill, Marry, No Action) rule conditions. These tests verify that the KFM agent correctly applies rules based on component performance metrics.

## Test Files

- `test_e2e_kfm_rules.py`: The main test file containing all KFM rule condition tests
- `test_utils/test_reporter.py`: Utility for generating detailed test reports and visualizations

## Quick Start

### Running the Tests

```bash
# Run all KFM rule tests
python scripts/run_kfm_rule_tests.py

# Run specific categories of tests
python scripts/run_kfm_rule_tests.py --test-category kill
python scripts/run_kfm_rule_tests.py --test-category marry
python scripts/run_kfm_rule_tests.py --test-category no_action

# Run tests with visualizations
python scripts/run_kfm_rule_tests.py --visualize

# Run in CI mode
python scripts/run_kfm_rule_tests.py --ci-mode

# Specify custom output directory
python scripts/run_kfm_rule_tests.py --output-dir my_reports

# Generate a summary report after running tests
python scripts/run_kfm_rule_tests.py --summarize

# Generate an HTML summary report
python scripts/run_kfm_rule_tests.py --summarize --html-summary
```

### Test Reports

Test reports are generated in the following locations:

- `test_reports/kfm_rules/`: Default location for test reports and visualizations
- `logs/test_verification_levels/detailed/kfm_rules/`: Detailed test logs and trace data

## Test Categories

The test suite covers three main categories of KFM actions:

1. **Kill Action Tests**: Verify that components with poor performance are correctly identified for removal
2. **Marry Action Tests**: Verify that exceptional components are correctly selected for exclusive use
3. **No Action Tests**: Verify that ambiguous or adequate performance correctly results in no action

## Summary Reporting

The test suite includes a powerful summary reporting mechanism that aggregates results across multiple test runs:

### Generating Summary Reports

```bash
# Generate a summary after running tests
python scripts/run_kfm_rule_tests.py --summarize

# Generate an HTML summary report
python scripts/run_kfm_rule_tests.py --summarize --html-summary

# Generate a summary of only the last 3 test runs
python scripts/run_kfm_rule_tests.py --summarize --last-n=3

# Generate a summary without running tests
python scripts/summarize_kfm_test_results.py
```

### Summary Report Contents

- Overall test statistics (total tests, pass rates, duration)
- Category-level statistics (tests per category, pass rates, durations)
- Individual test case statistics (runs, pass rates, average durations)
- Visualizations of pass/fail rates and execution times
- List of included test reports with timestamps

### Summary Report Formats

- **Markdown**: Default format, suitable for version control and documentation
- **HTML**: Interactive format with color-coding and improved readability

## Documentation

For comprehensive documentation of the test suite, see:

- [KFM Rule Tests Documentation](../docs/testing/kfm_rule_tests.md): Detailed explanation of the test suite and test cases

## Adding New Tests

To add new tests:

1. Identify the correct test class based on the action you want to test
2. Add a new test method with thorough docstring documentation
3. Use the configuration methods to set up the test scenario
4. Define expected outcomes and log patterns
5. Execute the scenario and verify the results

See the [documentation](../docs/testing/kfm_rule_tests.md#extending-the-test-suite) for more details on adding new tests. 