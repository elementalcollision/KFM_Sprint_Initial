# KFM Tests CI/CD Integration Guide

This document explains how to integrate the KFM rule condition tests with CI/CD systems.

## Overview

The KFM test suite is designed to be easily integrated with Continuous Integration (CI) and Continuous Deployment (CD) pipelines. The tests generate machine-readable reports, visualizations, and summary documents that can be included in CI artifacts.

## Running Tests in CI Environment

### Basic CI Integration

For basic CI integration, run:

```bash
python scripts/run_kfm_rule_tests.py --ci-mode
```

This will:
1. Run all KFM rule condition tests
2. Generate a CI-friendly JSON report 
3. Exit with an appropriate status code (0 for success, 1 for failure)

### Complete CI Integration

For a comprehensive CI integration with summary reports:

```bash
python scripts/run_kfm_rule_tests.py --ci-mode --visualize --summarize --html-summary
```

This will:
1. Run all tests
2. Generate detailed JSON reports
3. Create visualizations
4. Produce a CI-friendly JSON report
5. Generate an HTML summary report
6. Exit with an appropriate status code

## Report Locations

- **Test Results**: `test_reports/kfm_rules/test_results_*.json`
- **CI Report**: `test_reports/kfm_rules/ci_report.json`
- **Summary Report**: `test_reports/kfm_rules/test_summary.html`
- **Visualizations**: `test_reports/kfm_rules/*.png`

## CI Report Structure

The CI report (`ci_report.json`) contains:

```json
{
  "total_tests": 12,
  "passed_tests": 12,
  "failed_tests": 0,
  "total_duration": 15.5,
  "start_time": 1622548800,
  "end_time": 1622548815.5,
  "pass_rate": 1.0,
  "status": "PASS",
  "timestamp": 1622548815.5,
  "timestamp_iso": "2021-06-01T12:00:15.500000",
  "test_categories": {
    "kill": {
      "total": 4,
      "passed": 4,
      "failed": 0,
      "duration": 5.2
    },
    "marry": {
      "total": 4,
      "passed": 4,
      "failed": 0,
      "duration": 4.8
    },
    "no_action": {
      "total": 4,
      "passed": 4,
      "failed": 0,
      "duration": 5.5
    }
  }
}
```

## Integration Examples

### GitHub Actions

```yaml
name: KFM Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    
    - name: Run KFM tests
      run: python scripts/run_kfm_rule_tests.py --ci-mode --visualize --summarize --html-summary
    
    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: test-results
        path: |
          test_reports/kfm_rules/test_results_*.json
          test_reports/kfm_rules/ci_report.json
          test_reports/kfm_rules/test_summary.html
          test_reports/kfm_rules/*.png
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Test') {
            steps {
                sh 'python scripts/run_kfm_rule_tests.py --ci-mode --visualize --summarize --html-summary'
            }
        }
        
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'test_reports/kfm_rules/**', fingerprint: true
                publishHTML target: [
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'test_reports/kfm_rules',
                    reportFiles: 'test_summary.html',
                    reportName: 'KFM Test Report'
                ]
            }
        }
    }
}
```

### GitLab CI/CD

```yaml
kfm_tests:
  stage: test
  script:
    - pip install -r requirements.txt
    - python scripts/run_kfm_rule_tests.py --ci-mode --visualize --summarize --html-summary
  artifacts:
    paths:
      - test_reports/kfm_rules/
    reports:
      junit: test_reports/kfm_rules/ci_report.json
```

## Monitoring Trends

For long-term monitoring of test trends:

1. Save test reports in a persistent location
2. Generate summary reports including historical data
3. Track key metrics like pass rates and execution times
4. Visualize trends over time

Example:

```bash
# Daily CI job to generate trend report
python scripts/summarize_kfm_test_results.py --report-dir=/persistent/reports --last-n=30 --output=trend_report.html
```

## Extracting Metrics for Dashboards

For integration with dashboards, extract key metrics from the CI report:

```python
import json

# Load CI report
with open('test_reports/kfm_rules/ci_report.json', 'r') as f:
    ci_report = json.load(f)

# Extract metrics
pass_rate = ci_report['pass_rate']  # 0.0 to 1.0
total_duration = ci_report['total_duration']  # seconds
kill_pass_rate = ci_report['test_categories']['kill']['pass_rate']
marry_pass_rate = ci_report['test_categories']['marry']['pass_rate']
no_action_pass_rate = ci_report['test_categories']['no_action']['pass_rate']

# Push to your metrics system
# ...
```

## Notifications and Alerts

To set up alerts based on test results:

```python
import json
import requests

# Load CI report
with open('test_reports/kfm_rules/ci_report.json', 'r') as f:
    ci_report = json.load(f)

# Check for failures
if ci_report['status'] != 'PASS':
    # Send alert
    webhook_url = 'https://your-webhook-url'
    payload = {
        'text': f"⚠️ KFM Test Failure: {ci_report['failed_tests']} tests failed. Pass rate: {ci_report['pass_rate']*100:.1f}%"
    }
    requests.post(webhook_url, json=payload)
```

## Conclusion

The KFM test suite provides comprehensive CI/CD integration through:

1. Machine-readable reports for automated processing
2. Human-readable summaries for easy interpretation
3. Visualizations for quick assessment
4. Exit codes for pipeline control flow
5. Categorized metrics for detailed analysis

By leveraging these features, you can build robust CI/CD pipelines that automatically validate KFM rule conditions and provide visibility into test results. 