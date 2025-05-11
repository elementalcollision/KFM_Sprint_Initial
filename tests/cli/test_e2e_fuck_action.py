import pytest
import subprocess
import json
import shutil
from pathlib import Path
import os

# Define the base directory for fixtures for this test module
BASE_FIXTURE_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fuck_scenario_clear_candidate_env(tmp_path):
    """Prepares the environment for the 'Clear Fuck Candidate' E2E scenario."""
    scenario_name = "e2e_fuck_scenario_clear_candidate"
    source_fixture_dir = BASE_FIXTURE_DIR / scenario_name
    
    # Destination for logs and registry within the temp directory
    temp_logs_dir = tmp_path / "logs"
    temp_registry_dir = tmp_path / "mock_registry"
    temp_reports_dir = tmp_path / "reports"

    # Copy mock logs
    shutil.copytree(source_fixture_dir / "logs", temp_logs_dir)
    
    # Copy mock registry
    shutil.copytree(source_fixture_dir / "mock_registry", temp_registry_dir)
    
    # Copy the verifier config file to the root of tmp_path (where verifier will expect it relative to CWD)
    shutil.copy(source_fixture_dir / "test_config_fuck_clear_candidate.yaml", tmp_path / "test_config.yaml")
    
    # Ensure reports directory exists for the verifier output
    temp_reports_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_path": tmp_path / "test_config.yaml",
        "reports_dir": temp_reports_dir,
        "cwd": tmp_path
    }

@pytest.fixture
def fuck_scenario_multiple_candidates_env(tmp_path):
    """Prepares the environment for the 'Multiple Fuck Candidates' E2E scenario."""
    scenario_name = "e2e_fuck_scenario_multiple_candidates"
    source_fixture_dir = BASE_FIXTURE_DIR / scenario_name
    
    temp_logs_dir = tmp_path / "logs"
    temp_registry_dir = tmp_path / "mock_registry"
    temp_reports_dir = tmp_path / "reports"

    shutil.copytree(source_fixture_dir / "logs", temp_logs_dir)
    shutil.copytree(source_fixture_dir / "mock_registry", temp_registry_dir)
    shutil.copy(source_fixture_dir / "test_config_fuck_multiple_candidates.yaml", tmp_path / "test_config.yaml")
    temp_reports_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_path": tmp_path / "test_config.yaml",
        "reports_dir": temp_reports_dir,
        "cwd": tmp_path
    }

@pytest.fixture
def fuck_scenario_dependencies_env(tmp_path):
    """Prepares the environment for the 'Fuck Action with Dependencies' E2E scenario."""
    scenario_name = "e2e_fuck_scenario_dependencies"
    source_fixture_dir = BASE_FIXTURE_DIR / scenario_name
    
    temp_logs_dir = tmp_path / "logs"
    temp_registry_dir = tmp_path / "mock_registry"
    temp_reports_dir = tmp_path / "reports"

    shutil.copytree(source_fixture_dir / "logs", temp_logs_dir)
    shutil.copytree(source_fixture_dir / "mock_registry", temp_registry_dir)
    shutil.copy(source_fixture_dir / "test_config_fuck_dependencies.yaml", tmp_path / "test_config.yaml")
    temp_reports_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_path": tmp_path / "test_config.yaml",
        "reports_dir": temp_reports_dir,
        "cwd": tmp_path
    }

@pytest.fixture
def fuck_scenario_failure_env(tmp_path):
    """Prepares the environment for the 'Fuck Action Failure' E2E scenario."""
    scenario_name = "e2e_fuck_scenario_failure"
    source_fixture_dir = BASE_FIXTURE_DIR / scenario_name
    
    temp_logs_dir = tmp_path / "logs"
    temp_registry_dir = tmp_path / "mock_registry"
    temp_reports_dir = tmp_path / "reports"

    shutil.copytree(source_fixture_dir / "logs", temp_logs_dir)
    shutil.copytree(source_fixture_dir / "mock_registry", temp_registry_dir)
    shutil.copy(source_fixture_dir / "test_config_fuck_failure.yaml", tmp_path / "test_config.yaml")
    temp_reports_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_path": tmp_path / "test_config.yaml",
        "reports_dir": temp_reports_dir,
        "cwd": tmp_path
    }

def run_verifier(config_path: Path, cwd: Path):
    """Runs the kfm-verifier CLI tool as a subprocess."""
    
    project_root = Path(__file__).resolve().parent.parent.parent
    script_path = project_root / "src" / "cli" / "kfm_verifier_cli.py"

    # Define the output report file path within the temp CWD for the verifier
    output_report_path = cwd / "reports" / "report.json" # Matches where the test expects it

    command = [
        "python", 
        str(script_path), 
        "--config", str(config_path),
        "--commit", "test_commit_sha",
        "--branch", "test_branch",
        "--report-output", str(output_report_path)
    ]

    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(project_root) + (os.pathsep + current_pythonpath if current_pythonpath else "")
    
    try:
        process = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=False, 
            cwd=str(cwd),
            env=env # Pass the modified environment
        )
        return process
    except FileNotFoundError:
        pytest.fail(f"kfm-verifier command not found. Ensure it is in PATH or adjust run_verifier helper. Command: {' '.join(command)}")
    except Exception as e:
        pytest.fail(f"Error running kfm-verifier: {e}. Command: {' '.join(command)}")

def test_e2e_fuck_action_clear_candidate(fuck_scenario_clear_candidate_env):
    """Tests the E2E scenario for a clear 'Fuck' candidate."""
    env_details = fuck_scenario_clear_candidate_env
    config_path = env_details["config_path"]
    reports_dir = env_details["reports_dir"]
    cwd = env_details["cwd"]

    process_result = run_verifier(config_path, cwd)

    # 1. Verifier subprocess completed successfully (or expected exit code)
    #    For now, let's assume 0 is success. This might change based on verifier behavior.
    assert process_result.returncode == 0, f"Verifier failed with exit code {process_result.returncode}. Stderr: {process_result.stderr}\nStdout: {process_result.stdout}"

    # 2. Verify the content of the generated report.
    #    The report name might be dynamic or fixed. Assuming a fixed name or single JSON report for simplicity.
    #    The verifier config specifies json format and output to ./reports
    report_files = list(reports_dir.glob("*.json"))
    assert len(report_files) == 1, f"Expected 1 JSON report, found {len(report_files)} in {reports_dir}"
    report_path = report_files[0]

    with open(report_path, 'r') as f:
        report_content = json.load(f)

    # Check overall status
    assert report_content.get("overall_status") == "PASSED", \
        f"Verifier report did not pass. Report: {json.dumps(report_content, indent=2)}"

    # Check specific criteria from the config
    expected_checks = [
        "kfm_decision_fuck_ComponentToFuck",
        "kfm_reason_ComponentToFuck",
        "execution_activate_ComponentToFuck_temporary",
        "execution_ComponentToFuck_active_temporary",
        "component_ComponentToFuck_initialized_temporary",
        "component_ComponentToFuck_task_complete",
        "execution_deactivate_ComponentToFuck_temporary"
    ]
    
    passed_checks = 0
    for check_result in report_content.get("check_results", []):
        if check_result.get("check_id") in expected_checks and check_result.get("status") == "PASSED":
            passed_checks += 1
        elif check_result.get("check_id") in expected_checks and check_result.get("status") != "PASSED":
             pytest.fail(f"Check '{check_result.get('check_id')}' did not pass. Status: {check_result.get('status')}, Details: {check_result.get('details')}")

    assert passed_checks == len(expected_checks), \
        f"Not all expected checks passed. Expected {len(expected_checks)}, Passed {passed_checks}. Report: {json.dumps(report_content, indent=2)}"

def test_e2e_fuck_action_multiple_candidates(fuck_scenario_multiple_candidates_env):
    """Tests the E2E scenario for multiple 'Fuck' candidates with ranking."""
    env_details = fuck_scenario_multiple_candidates_env
    config_path = env_details["config_path"]
    reports_dir = env_details["reports_dir"]
    cwd = env_details["cwd"]

    process_result = run_verifier(config_path, cwd)

    assert process_result.returncode == 0, f"Verifier failed with exit code {process_result.returncode}. Stderr: {process_result.stderr}\nStdout: {process_result.stdout}"

    report_files = list(reports_dir.glob("*.json"))
    assert len(report_files) == 1, f"Expected 1 JSON report, found {len(report_files)} in {reports_dir}"
    report_path = report_files[0]

    with open(report_path, 'r') as f:
        report_content = json.load(f)

    assert report_content.get("overall_status") == "PASSED", \
        f"Verifier report did not pass. Report: {json.dumps(report_content, indent=2)}"

    expected_checks = [
        "kfm_identified_multiple_candidates",
        "kfm_ranking_logic_applied",
        "kfm_decision_fuck_ComponentCandidateB",
        "kfm_reason_ComponentCandidateB_ranking",
        "execution_activate_ComponentCandidateB_temporary",
        "execution_ComponentCandidateB_active_temporary",
        "component_ComponentCandidateB_initialized_temporary",
        "component_ComponentCandidateB_task_complete",
        "execution_deactivate_ComponentCandidateB_temporary"
    ]
    
    passed_checks = 0
    for check_result in report_content.get("check_results", []):
        if check_result.get("check_id") in expected_checks and check_result.get("status") == "PASSED":
            passed_checks += 1
        elif check_result.get("check_id") in expected_checks and check_result.get("status") != "PASSED":
             pytest.fail(f"Check '{check_result.get('check_id')}' did not pass. Status: {check_result.get('status')}, Details: {check_result.get('details')}")

    assert passed_checks == len(expected_checks), \
        f"Not all expected checks passed. Expected {len(expected_checks)}, Passed {passed_checks}. Report: {json.dumps(report_content, indent=2)}"

def test_e2e_fuck_action_with_dependencies(fuck_scenario_dependencies_env):
    """Tests the E2E scenario for 'Fuck' action with component dependencies."""
    env_details = fuck_scenario_dependencies_env
    config_path = env_details["config_path"]
    reports_dir = env_details["reports_dir"]
    cwd = env_details["cwd"]

    process_result = run_verifier(config_path, cwd)

    assert process_result.returncode == 0, f"Verifier failed with exit code {process_result.returncode}. Stderr: {process_result.stderr}\nStdout: {process_result.stdout}"

    report_files = list(reports_dir.glob("*.json"))
    assert len(report_files) == 1, f"Expected 1 JSON report, found {len(report_files)} in {reports_dir}"
    report_path = report_files[0]

    with open(report_path, 'r') as f:
        report_content = json.load(f)

    assert report_content.get("overall_status") == "PASSED", \
        f"Verifier report did not pass. Report: {json.dumps(report_content, indent=2)}"

    expected_checks = [
        "kfm_decision_fuck_ComponentToFuckWithDeps",
        "kfm_identified_dependency",
        "kfm_dependency_available",
        "executor_ensuring_dependency",
        "execution_verifying_dependency_access",
        "execution_activate_ComponentToFuckWithDeps_temporary",
        "execution_ComponentToFuckWithDeps_active_with_dependency_note",
        "component_ComponentToFuckWithDeps_initialized_temporary",
        "component_ComponentToFuckWithDeps_accessing_dependency",
        "component_ComponentToFuckWithDeps_task_complete",
        "execution_deactivate_ComponentToFuckWithDeps_temporary"
    ]
    
    passed_checks = 0
    for check_result in report_content.get("check_results", []):
        if check_result.get("check_id") in expected_checks and check_result.get("status") == "PASSED":
            passed_checks += 1
        elif check_result.get("check_id") in expected_checks and check_result.get("status") != "PASSED":
             pytest.fail(f"Check '{check_result.get('check_id')}' did not pass. Status: {check_result.get('status')}, Details: {check_result.get('details')}")

    assert passed_checks == len(expected_checks), \
        f"Not all expected checks passed. Expected {len(expected_checks)}, Passed {passed_checks}. Report: {json.dumps(report_content, indent=2)}"

def test_e2e_fuck_action_failure(fuck_scenario_failure_env):
    """Tests the E2E scenario for 'Fuck' action failure and error logging."""
    env_details = fuck_scenario_failure_env
    config_path = env_details["config_path"]
    reports_dir = env_details["reports_dir"]
    cwd = env_details["cwd"]

    process_result = run_verifier(config_path, cwd)

    # Even if errors are logged, the verifier itself should execute correctly.
    assert process_result.returncode == 0, f"Verifier failed with exit code {process_result.returncode}. Stderr: {process_result.stderr}\nStdout: {process_result.stdout}"

    report_files = list(reports_dir.glob("*.json"))
    assert len(report_files) == 1, f"Expected 1 JSON report, found {len(report_files)} in {reports_dir}"
    report_path = report_files[0]

    with open(report_path, 'r') as f:
        report_content = json.load(f)

    # In a failure scenario, the verifier might still PASS if all *expected error logs* are found.
    # This depends on the verifier's logic and config. Adjust if overall_status should be FAILED.
    assert report_content.get("overall_status") == "PASSED", \
        f"Verifier report did not pass as expected for a failure scenario. Report: {json.dumps(report_content, indent=2)}"

    expected_checks = [
        "kfm_decision_fuck_ComponentToFail",
        "kfm_executor_reports_failure",
        "execution_engine_reports_activation_failure",
        "component_logs_initialization_failure"
    ]
    
    passed_checks = 0
    for check_result in report_content.get("check_results", []):
        if check_result.get("check_id") in expected_checks and check_result.get("status") == "PASSED":
            # PASSED here means the *expected log (which is an error log in this case)* was found.
            passed_checks += 1
        elif check_result.get("check_id") in expected_checks and check_result.get("status") != "PASSED":
             pytest.fail(f"Check '{check_result.get('check_id')}' for expected error did not pass. Status: {check_result.get('status')}, Details: {check_result.get('details')}")

    assert passed_checks == len(expected_checks), \
        f"Not all expected failure checks passed. Expected {len(expected_checks)}, Passed {passed_checks}. Report: {json.dumps(report_content, indent=2)}" 