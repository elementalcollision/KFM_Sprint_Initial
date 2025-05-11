import pytest
import subprocess
import os
import json
import shutil
import sys
from pathlib import Path

# Helper function to get the project root dynamically
def get_project_root():
    # Assumes tests are run from the project root or tests/ directory
    current_path = Path(__file__).resolve()
    # Navigate up until we find a known root marker, e.g., 'src' directory or '.git'
    while not (current_path / 'src').is_dir() and not (current_path / '.git').is_dir() and current_path.parent != current_path:
        current_path = current_path.parent
    if not (current_path / 'src').is_dir() and not (current_path / '.git').is_dir():
        raise RuntimeError("Could not determine project root.")
    return current_path

PROJECT_ROOT = get_project_root()
E2E_FIXTURES_DIR = PROJECT_ROOT / "tests" / "cli" / "fixtures" / "e2e_scenario_1"
VERIFIER_CLI_SCRIPT = PROJECT_ROOT / "src" / "cli" / "kfm_verifier_cli.py" # Corrected script name

@pytest.fixture
def e2e_test_env(tmp_path):
    """Creates a temporary environment with mock logs and config for E2E test."""
    scenario_path = tmp_path / "scenario"
    
    # Copy fixture files
    shutil.copytree(E2E_FIXTURES_DIR / "logs", scenario_path / "logs")
    shutil.copytree(E2E_FIXTURES_DIR / "mock_registry", scenario_path / "mock_registry")
    shutil.copyfile(E2E_FIXTURES_DIR / "test_config.yaml", scenario_path / "test_config.yaml")
    
    # Create report output directory
    (scenario_path / "reports").mkdir()
    
    return scenario_path

def test_kfm_verifier_e2e_scenario_1(e2e_test_env):
    """Runs the kfm-verifier CLI end-to-end with a mock scenario."""
    config_path = e2e_test_env / "test_config.yaml"
    report_path = e2e_test_env / "reports" / "verification_report.json"

    # Construct the command
    # Use sys.executable to ensure we run with the same Python interpreter as pytest
    # Add PROJECT_ROOT to PYTHONPATH for imports within the script to work
    env = os.environ.copy()
    python_path = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = f"{str(PROJECT_ROOT)}{os.pathsep}{python_path}"

    command = [
        sys.executable,
        str(VERIFIER_CLI_SCRIPT),
        "--config", str(config_path),
        "--report-output", str(report_path), # Pass the full file path
        "--commit", "testcommit123",
        "--branch", "testbranch",
        # Add other necessary args if any, e.g., --verification-level
    ]

    # Run the CLI tool
    result = subprocess.run(command, capture_output=True, text=True, cwd=e2e_test_env, env=env)

    # --- Assertions ---
    
    # 1. Check exit code (should be non-zero due to expected failure)
    assert result.returncode != 0, f"Expected non-zero exit code due to verification failure, but got {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    
    # Optional: Check stderr for specific error messages if the CLI outputs them
    # assert "Verification completed with failures" in result.stderr # Example

    # 2. Check if the report file was created
    if not report_path.exists():
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert report_path.exists(), f"Expected report file {report_path} was not created."

    # 3. Load and validate the report content
    try:
        with open(report_path, 'r') as f:
            report_data = json.load(f)
    except json.JSONDecodeError:
        pytest.fail(f"Could not decode the generated JSON report at {report_path}")
    except FileNotFoundError:
         pytest.fail(f"Report file {report_path} exists check passed, but FileNotFoundError during open?")

    # Assuming report_data structure like: {"overall_status": "failed", "checks": [...]} 
    # Adjust keys based on actual report generator output (task 52.4)
    assert "overall_status" in report_data, "Report missing 'overall_status' key."
    assert report_data["overall_status"] == "failed", f"Expected overall_status 'failed', got '{report_data['overall_status']}'"
    
    assert "checks" in report_data and isinstance(report_data["checks"], list), "Report missing 'checks' list."
    
    checks_by_id = {check.get("check_id"): check for check in report_data["checks"]}

    # Expected statuses based on test_config.yaml
    expected_check_statuses = {
        "kfm_decision_a_update": "passed",
        "execution_a_success": "passed",
        "registry_a_status": "passed",
        "llm_call_made": "passed",
        "execution_b_failed_log": "passed",
        "registry_b_error_state": "failed" # This one is designed to fail
    }

    assert len(checks_by_id) == len(expected_check_statuses), \
        f"Expected {len(expected_check_statuses)} checks in report, found {len(checks_by_id)}"

    for check_id, expected_status in expected_check_statuses.items():
        assert check_id in checks_by_id, f"Check ID '{check_id}' not found in report."
        actual_check = checks_by_id[check_id]
        assert "status" in actual_check, f"Check '{check_id}' missing 'status' key."
        assert actual_check["status"] == expected_status, \
            f"Check '{check_id}': expected status '{expected_status}', got '{actual_check['status']}'"

        # Optional: Add checks for specific 'actual_value' or 'details' if needed
        if check_id == "registry_a_status":
            assert actual_check.get("details", {}).get("actual_value") == "processing", \
                f"Check '{check_id}': incorrect actual value reported."
        elif check_id == "registry_b_error_state":
             # Assuming the verifier reports the actual value found in the mock file (null/None)
            assert actual_check.get("details", {}).get("actual_value") is None, \
                 f"Check '{check_id}': incorrect actual value reported for failed check." 