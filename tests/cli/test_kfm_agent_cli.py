import pytest
import io
import sys
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock, call

# The CLI script to test
from src.cli import kfm_agent_cli 
# Import the service to mock its behavior and its defaults for verification
from src.transparency.local_explanation_service import DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG
from src.transparency.global_analytics_service import DEFAULT_LOG_PATTERN as DEFAULT_GLOBAL_LOG_PATTERN

@pytest.fixture
def mock_local_explanation_service():
    # This fixture provides a mock of the LocalKfmExplanationService class
    # The mock instance will be returned by LocalKfmExplanationService(...)
    with patch('src.cli.kfm_agent_cli.LocalKfmExplanationService') as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance # Yield the instance for tests to configure

@pytest.fixture
def mock_global_analytics_service():
    # This fixture mocks the GlobalAnalyticsService class
    with patch('src.cli.kfm_agent_cli.GlobalAnalyticsService') as mock_class:
        mock_instance = MagicMock()
        # Configure mock methods that are called by the CLI handler
        mock_instance.process_logs = MagicMock() 
        mock_instance.generate_report_text = MagicMock(return_value="Mocked Global Report Content")
        mock_class.return_value = mock_instance
        yield mock_instance # Yield the instance for tests to configure

class TestKfmAgentCliExplainDecision:

    def run_cli_command(self, args_list):
        """Helper to run the CLI's main function with specific args and capture stdout."""
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                kfm_agent_cli.main(raw_args=args_list)
            except SystemExit as e:
                # Capture SystemExit for cases like --help or errors handled by argparse
                # We might want to check e.code if needed
                pass
        return f.getvalue()

    def test_explain_decision_success(self, mock_local_explanation_service):
        run_id = "test_run_001"
        decision_index = 0
        expected_explanation = "Formatted explanation for test_run_001, decision 0"
        
        mock_local_explanation_service.get_kfm_decision_context.return_value = {
            "run_id": run_id, "decision_index_found": decision_index, "action": "Keep" # Min context
        }
        mock_local_explanation_service.format_decision_explanation.return_value = expected_explanation

        output = self.run_cli_command(["explain-decision", "--run-id", run_id])
        
        mock_local_explanation_service.get_kfm_decision_context.assert_called_once_with(
            run_id=run_id,
            decision_event_tag=DEFAULT_DECISION_EVENT_TAG, # Check default
            decision_index=decision_index # Check default
        )
        mock_local_explanation_service.format_decision_explanation.assert_called_once_with(
            mock_local_explanation_service.get_kfm_decision_context.return_value
        )
        assert expected_explanation in output

    def test_explain_decision_context_not_found(self, mock_local_explanation_service):
        run_id = "test_run_002"
        mock_local_explanation_service.get_kfm_decision_context.return_value = None

        output = self.run_cli_command(["explain-decision", "--run-id", run_id])

        mock_local_explanation_service.get_kfm_decision_context.assert_called_once_with(
            run_id=run_id,
            decision_event_tag=DEFAULT_DECISION_EVENT_TAG,
            decision_index=0
        )
        mock_local_explanation_service.format_decision_explanation.assert_not_called()
        assert f"Could not find decision context for run_id='{run_id}'" in output

    def test_explain_decision_with_all_args(self, mock_local_explanation_service):
        run_id = "test_run_003"
        decision_index = 1
        log_file = "custom.log"
        event_tag = "custom_event_tag"
        expected_explanation = "Custom explanation"

        mock_local_explanation_service.get_kfm_decision_context.return_value = {"key": "value"}
        mock_local_explanation_service.format_decision_explanation.return_value = expected_explanation

        # Call with custom args
        self.run_cli_command([
            "explain-decision", 
            "--run-id", run_id, 
            "--decision-index", str(decision_index),
            "--log-file", log_file,
            "--event-tag", event_tag
        ])
        
        # Assert that the LocalKfmExplanationService was instantiated with custom log_file
        # This requires a bit more care because the mock is on the class, not instance creation inside handle_explain_decision
        # kfm_agent_cli.LocalKfmExplanationService.assert_called_once_with(log_file_path=log_file) # This checks class instantiation
        # Instead, we check that the get_kfm_decision_context was called on an instance that WAS configured by this log file path.
        # Since our fixture mocks the *instance* that the class returns, we check its method calls.
        # The constructor of the service is called before get_kfm_decision_context.
        # The test for log_file implies we need to check constructor call to LocalKfmExplanationService
        # This is a bit tricky with the current fixture. The fixture replaces the class, so the constructor call IS the mock_class call.
        
        # Re-evaluating how to test the log_file_path argument: 
        # The `explainer` object in `handle_explain_decision` is `LocalKfmExplanationService(log_file_path=args.log_file)`
        # Our mock `mock_local_explanation_service` IS the instance returned by `LocalKfmExplanationService(...)`
        # So, we need to check how the class itself was called to create this instance.
        # `kfm_agent_cli.LocalKfmExplanationService.assert_called_with(log_file_path=log_file)` is the direct way if we mock the class itself.
        # The fixture `mock_local_explanation_service` yields the *instance*. `mock_class` is in the fixture scope.
        # Let's assume the instance passed to get_kfm_decision_context was correctly initialized for now and focus on method args.
        # We will check the log_file argument was used by checking the class constructor arguments.
        
        assert kfm_agent_cli.LocalKfmExplanationService.call_args_list[-1] == call(log_file_path=log_file), \
            "LocalKfmExplanationService not initialized with custom log file as expected."

        mock_local_explanation_service.get_kfm_decision_context.assert_called_with(
            run_id=run_id,
            decision_event_tag=event_tag,
            decision_index=decision_index
        )
        assert expected_explanation in self.run_cli_command(["explain-decision", "--run-id", run_id]) # Re-run to check output

    def test_explain_decision_help(self):
        output = self.run_cli_command(["explain-decision", "--help"])
        assert "usage: kfm_agent_cli.py explain-decision" in output
        assert "--run-id RUN_ID" in output
        assert "--decision-index DECISION_INDEX" in output

    def test_main_cli_no_command(self):
        output = self.run_cli_command([]) # No command
        assert "KFM Agent CLI - Tools for interacting with" in output # Part of main help
        assert "Available commands:" in output
        # Should also exit with non-zero, but SystemExit is caught

    def test_main_cli_invalid_command(self):
        # Argparse itself will handle this and print to stderr, then SystemExit
        # We may not capture stderr easily here without more complex setup.
        # For now, check that it doesn't crash and likely prints usage.
        output = self.run_cli_command(["invalid-command"])
        # The output might contain the main help or an error message from argparse about invalid choice.
        # This depends on argparse version and configuration. A basic check:
        assert "usage: kfm_agent_cli.py" in output or "invalid choice: 'invalid-command'" in output.lower() 

class TestKfmAgentCliGlobalReport:
    # Re-use run_cli_command helper from TestKfmAgentCliExplainDecision
    # If it's not inherited or accessible, define it here or move to a shared conftest.py
    # For simplicity, let's assume it can be called if methods are part of the same file for now,
    # or just redefine it if they are separate test classes not inheriting.
    # Better: move run_cli_command to a fixture or a base class if needed by multiple test classes.
    # For now, directly using the one from the other class for brevity as if it was a shared helper.
    # This is not ideal if they are truly separate. Let's copy it for clarity.

    def run_cli_command(self, args_list):
        """Helper to run the CLI's main function with specific args and capture stdout."""
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                kfm_agent_cli.main(raw_args=args_list)
            except SystemExit:
                pass # Capture SystemExit for --help or argparse errors
        return f.getvalue()

    def test_generate_global_report_with_log_dir(self, mock_global_analytics_service):
        log_dir = "./dummy_logs"
        expected_report_content = "Mocked Global Report Content for dir"
        mock_global_analytics_service.generate_report_text.return_value = expected_report_content

        output = self.run_cli_command(["generate-global-report", "--log-dir", log_dir])

        # Check GlobalAnalyticsService was instantiated correctly
        kfm_agent_cli.GlobalAnalyticsService.assert_called_once_with(
            log_files=None,
            log_dir=log_dir,
            log_pattern=DEFAULT_GLOBAL_LOG_PATTERN # Check default pattern
        )
        mock_global_analytics_service.process_logs.assert_called_once()
        mock_global_analytics_service.generate_report_text.assert_called_once()
        assert expected_report_content in output

    def test_generate_global_report_with_log_files(self, mock_global_analytics_service):
        log_files_str = "log1.txt,path/to/log2.json"
        log_files_list = ["log1.txt", "path/to/log2.json"]
        custom_pattern = "*.jsonlog"
        expected_report_content = "Mocked Global Report Content for files"
        mock_global_analytics_service.generate_report_text.return_value = expected_report_content

        output = self.run_cli_command([
            "generate-global-report", 
            "--log-files", log_files_str,
            "--log-pattern", custom_pattern # This pattern would be used if --log-dir was also given
        ])

        kfm_agent_cli.GlobalAnalyticsService.assert_called_once_with(
            log_files=log_files_list,
            log_dir=None,
            log_pattern=custom_pattern
        )
        mock_global_analytics_service.process_logs.assert_called_once()
        assert expected_report_content in output

    @patch('builtins.open', new_callable=MagicMock)
    def test_generate_global_report_with_output_file(self, mock_open_file, mock_global_analytics_service):
        log_dir = "./logs"
        output_f = "report.md"
        report_text = "Report to file"
        mock_global_analytics_service.generate_report_text.return_value = report_text

        # Mock the file writing part
        mock_file_handle = MagicMock()
        mock_open_file.return_value.__enter__.return_value = mock_file_handle

        cli_output = self.run_cli_command([
            "generate-global-report", 
            "--log-dir", log_dir, 
            "--output-file", output_f
        ])
        
        mock_open_file.assert_called_once_with(output_f, 'w')
        mock_file_handle.write.assert_called_once_with(report_text)
        assert f"Global report saved to: {output_f}" in cli_output

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_generate_global_report_output_file_io_error(self, mock_open_file, mock_global_analytics_service):
        log_dir = "./logs"
        output_f = "report.md"
        report_text = "Report during IO error"
        mock_global_analytics_service.generate_report_text.return_value = report_text

        cli_output = self.run_cli_command([
            "generate-global-report", 
            "--log-dir", log_dir, 
            "--output-file", output_f
        ])
        
        mock_open_file.assert_called_once_with(output_f, 'w')
        # Check that the error message is printed to stderr (harder to check directly)
        # Check that the report is printed to stdout as fallback
        assert f"Error writing report to file '{output_f}'" in cli_output # This print goes to stdout in the CLI code
        assert report_text in cli_output # Fallback print

    def test_generate_global_report_help(self):
        output = self.run_cli_command(["generate-global-report", "--help"])
        assert "usage: kfm_agent_cli.py generate-global-report" in output
        assert "--log-files LOG_FILES" in output
        assert "--log-dir LOG_DIR" in output 