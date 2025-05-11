# tests/cli/test_kfm_verifier_cli.py
import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import argparse # For creating Namespace objects in tests

# Adjust path to import from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Updated import: removed load_config
from src.cli.kfm_verifier_cli import parse_arguments, main_cli, \
                                        EXIT_CODE_SUCCESS, EXIT_CODE_VERIFICATION_ISSUES, \
                                        EXIT_CODE_CLI_ERROR, EXIT_CODE_REPORTING_ERROR
# Import for new config system
from src.config.config_loader import load_verification_config # Used by main_cli internally
from src.config.models import VerificationConfig, CliDefaultConfig, GlobalConfig # For test instances
from src.core.exceptions import ConfigurationError # For testing error paths

class TestKfmVerifierCli(unittest.TestCase):

    def setUp(self):
        # Create a default VerificationConfig instance that can be returned by mocks
        self.mock_default_verification_config = VerificationConfig()
        # Create default CliDefaultConfig for parse_arguments
        self.cli_defaults = CliDefaultConfig()


    def test_parse_arguments_required(self):
        """Test parsing with all required arguments."""
        args_list = [
            "--commit", "testcommit123",
            "--branch", "main",
            "--report-output", "report.json"
        ]
        # parse_arguments now gets defaults from a CliDefaultConfig instance
        parsed = parse_arguments(args_list, cli_config_defaults=self.cli_defaults)
        self.assertEqual(parsed.commit, "testcommit123")
        self.assertEqual(parsed.branch, "main")
        self.assertEqual(parsed.report_output, "report.json")
        self.assertIsNone(parsed.config) # Default
        self.assertEqual(parsed.verification_level, self.cli_defaults.verification_level) # Check against actual default
        self.assertIsNone(parsed.junit_report) # Default

    def test_parse_arguments_all_options(self):
        """Test parsing with all optional arguments provided."""
        args_list = [
            "--commit", "optcommit",
            "--branch", "develop",
            "--report-output", "out.json",
            "--config", "conf.yaml",
            "--verification-level", "detailed",
            "--junit-report", "junit.xml"
        ]
        parsed = parse_arguments(args_list, cli_config_defaults=self.cli_defaults)
        self.assertEqual(parsed.config, "conf.yaml")
        self.assertEqual(parsed.verification_level, "detailed")
        self.assertEqual(parsed.junit_report, "junit.xml")

    def test_parse_arguments_missing_required(self):
        """Test that SystemExit is raised if a required argument is missing."""
        args_list_missing_commit = [
            "--branch", "main",
            "--report-output", "report.json"
        ]
        with self.assertRaises(SystemExit) as cm_commit:
            parse_arguments(args_list_missing_commit, cli_config_defaults=self.cli_defaults)
        self.assertEqual(cm_commit.exception.code, 2)

        args_list_missing_branch = [
            "--commit", "testcommit123",
            "--report-output", "report.json"
        ]
        with self.assertRaises(SystemExit) as cm_branch:
            parse_arguments(args_list_missing_branch, cli_config_defaults=self.cli_defaults)
        self.assertEqual(cm_branch.exception.code, 2)

        args_list_missing_report = [
            "--commit", "testcommit123",
            "--branch", "main"
        ]
        with self.assertRaises(SystemExit) as cm_report:
            parse_arguments(args_list_missing_report, cli_config_defaults=self.cli_defaults)
        self.assertEqual(cm_report.exception.code, 2)
    
    def test_parse_arguments_invalid_choice_verification_level(self):
        """Test invalid choice for verification-level."""
        args_list = [
            "--commit", "testcommit123",
            "--branch", "main",
            "--report-output", "report.json",
            "--verification-level", "super_detailed" # Invalid choice
        ]
        with self.assertRaises(SystemExit) as cm:
            parse_arguments(args_list, cli_config_defaults=self.cli_defaults)
        self.assertEqual(cm.exception.code, 2)

    # Old test_load_config_* methods are removed as load_config is removed.
    # Configuration loading is now tested in tests/config/test_config_loader.py

    # --- Tests for main_cli --- 

    @patch('src.cli.kfm_verifier_cli.write_junit_xml_report')
    @patch('src.cli.kfm_verifier_cli.write_structured_report')
    @patch('src.cli.kfm_verifier_cli.run_core_verification_engine')
    @patch('src.config.config_loader.load_verification_config') # Patched new location
    @patch('src.cli.kfm_verifier_cli.parse_arguments')
    @patch('src.cli.kfm_verifier_cli.setup_logging') # Mock logging setup
    def test_main_cli_success_flow_no_config_no_junit(self, mock_setup_logging, mock_parse_args, mock_load_verification_cfg, mock_run_engine, mock_write_struct, mock_write_junit):
        """Test main_cli successful flow: no config from args, no junit, verification pass."""
        mock_args_namespace = argparse.Namespace(
            commit="testcommit", branch="main", report_output="report.json",
            config=None, verification_level="standard", junit_report=None
        )
        mock_parse_args.return_value = mock_args_namespace
        
        # load_verification_config returns a VerificationConfig instance
        mock_load_verification_cfg.return_value = self.mock_default_verification_config
        
        mock_engine_results = {
            "engine_status": "simulation_complete",
            "findings": [{"status": "PASS"}],
            "overall_recommendation": "Proceed with deployment."
        }
        mock_run_engine.return_value = mock_engine_results
        mock_write_struct.return_value = True

        # Simulate raw_args that would lead to config=None for the temp_parser in main_cli
        raw_args_for_main = ["--commit", "testcommit", "--branch", "main", "--report-output", "report.json"]
        exit_code = main_cli(raw_args_for_main) 

        # parse_arguments is called by main_cli after config is loaded
        mock_parse_args.assert_called_once() 
        # load_verification_config is called with path from initial parse (None here) and force_reload=True
        mock_load_verification_cfg.assert_called_once_with(None, force_reload=True)
        mock_run_engine.assert_called_once_with(
            "testcommit", "main", "report.json", # Direct args
            verification_config=self.mock_default_verification_config, # Config object
            verification_level_cli="standard", junit_report_path_cli=None # Args from full parse
        )
        mock_write_struct.assert_called_once_with(mock_engine_results, "report.json")
        mock_write_junit.assert_not_called()
        self.assertEqual(exit_code, EXIT_CODE_SUCCESS)
        mock_setup_logging.assert_called_once()


    @patch('src.cli.kfm_verifier_cli.write_junit_xml_report')
    @patch('src.cli.kfm_verifier_cli.write_structured_report')
    @patch('src.cli.kfm_verifier_cli.run_core_verification_engine')
    @patch('src.config.config_loader.load_verification_config') 
    @patch('src.cli.kfm_verifier_cli.parse_arguments')
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_with_config_and_junit_verification_fail(self, mock_setup_logging, mock_parse_args, mock_load_verification_cfg, mock_run_engine, mock_write_struct, mock_write_junit):
        """Test main_cli with specified config, junit, and verification failure."""
        mock_args_namespace = argparse.Namespace(
            commit="testfail", branch="develop", report_output="fail_report.json",
            config="myconf.yaml", verification_level="detailed", junit_report="junit_fail.xml"
        )
        mock_parse_args.return_value = mock_args_namespace
        
        # Simulate a config loaded with some specific setting
        specific_config = VerificationConfig(global_settings=GlobalConfig(log_level="DEBUG"))
        mock_load_verification_cfg.return_value = specific_config
        
        mock_engine_results_fail = {
            "engine_status": "simulation_complete",
            "findings": [{"status": "PASS"}, {"status": "FAIL"}], 
            "overall_recommendation": "Review required."
        }
        mock_run_engine.return_value = mock_engine_results_fail
        mock_write_struct.return_value = True
        mock_write_junit.return_value = True

        raw_args_for_main = ["--config", "myconf.yaml", "--commit", "testfail", "--branch", "develop", "--report-output", "fail_report.json", "--junit-report", "junit_fail.xml"]
        exit_code = main_cli(raw_args_for_main)

        mock_parse_args.assert_called_once()
        mock_load_verification_cfg.assert_called_once_with("myconf.yaml", force_reload=True)
        mock_run_engine.assert_called_once_with(
            "testfail", "develop", "fail_report.json",
            verification_config=specific_config, 
            verification_level_cli="detailed", junit_report_path_cli="junit_fail.xml"
        )
        mock_write_struct.assert_called_once_with(mock_engine_results_fail, "fail_report.json")
        mock_write_junit.assert_called_once_with(mock_engine_results_fail, "junit_fail.xml")
        self.assertEqual(exit_code, EXIT_CODE_VERIFICATION_ISSUES)
        mock_setup_logging.assert_called_once()

    @patch('src.cli.kfm_verifier_cli.write_junit_xml_report')
    @patch('src.cli.kfm_verifier_cli.write_structured_report')
    @patch('src.cli.kfm_verifier_cli.run_core_verification_engine')
    @patch('src.config.config_loader.load_verification_config')
    @patch('src.cli.kfm_verifier_cli.parse_arguments')
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_reporting_error(self, mock_setup_logging, mock_parse_args, mock_load_verification_cfg, mock_run_engine, mock_write_struct, mock_write_junit):
        mock_args_namespace = argparse.Namespace(
            commit="reporterror", branch="main", report_output="report_err.json",
            config=None, verification_level="standard", junit_report=None
        )
        mock_parse_args.return_value = mock_args_namespace
        mock_load_verification_cfg.return_value = self.mock_default_verification_config
        mock_engine_results_ok = {
            "engine_status": "simulation_complete",
            "findings": [{"status": "PASS"}],
            "overall_recommendation": "Proceed with deployment."
        }
        mock_run_engine.return_value = mock_engine_results_ok
        mock_write_struct.return_value = False # Simulate report writing failure

        raw_args_for_main = ["--commit", "reporterror", "--branch", "main", "--report-output", "report_err.json"]
        exit_code = main_cli(raw_args_for_main)
        self.assertEqual(exit_code, EXIT_CODE_REPORTING_ERROR)
        mock_setup_logging.assert_called_once()


    @patch('src.cli.kfm_verifier_cli.write_junit_xml_report')
    @patch('src.cli.kfm_verifier_cli.write_structured_report')
    @patch('src.cli.kfm_verifier_cli.run_core_verification_engine')
    @patch('src.config.config_loader.load_verification_config')
    @patch('src.cli.kfm_verifier_cli.parse_arguments')
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_junit_reporting_error(self, mock_setup_logging, mock_parse_args, mock_load_verification_cfg, mock_run_engine, mock_write_struct, mock_write_junit):
        mock_args_namespace = argparse.Namespace(
            commit="juniterror", branch="main", report_output="report_ok.json",
            config=None, verification_level="standard", junit_report="junit_err.xml"
        )
        mock_parse_args.return_value = mock_args_namespace
        mock_load_verification_cfg.return_value = self.mock_default_verification_config
        mock_engine_results_ok = { "findings": [{"status": "PASS"}] }
        mock_run_engine.return_value = mock_engine_results_ok
        mock_write_struct.return_value = True 
        mock_write_junit.return_value = False 

        raw_args_for_main = ["--commit", "juniterror", "--branch", "main", "--report-output", "report_ok.json", "--junit-report", "junit_err.xml"]
        exit_code = main_cli(raw_args_for_main)
        self.assertEqual(exit_code, EXIT_CODE_REPORTING_ERROR)
        mock_setup_logging.assert_called_once()

    @patch('src.config.config_loader.load_verification_config')
    # No need to patch parse_arguments for this test as it should fail before full parsing
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_config_load_failure_filenotfound(self, mock_setup_logging, mock_load_verification_cfg):
        mock_load_verification_cfg.side_effect = FileNotFoundError("Config file not found by loader")
        
        # Provide raw args that include a --config path to trigger the mocked error
        raw_args = ["--config", "bad_conf.yaml", "--commit", "c", "--branch", "b", "--report-output", "r.json"]
        exit_code = main_cli(raw_args)
        
        mock_load_verification_cfg.assert_called_once_with("bad_conf.yaml", force_reload=True)
        self.assertEqual(exit_code, EXIT_CODE_CLI_ERROR)
        # setup_logging should not be called if config load fails so fundamentally
        mock_setup_logging.assert_not_called()

    @patch('src.config.config_loader.load_verification_config')
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_config_load_failure_validationerror(self, mock_setup_logging, mock_load_verification_cfg):
        # This mock will be for the load_verification_config inside main_cli
        mock_load_verification_cfg.side_effect = ConfigurationError("Pydantic validation failed")

        raw_args = ["--config", "invalid_conf.yaml", "--commit", "c", "--branch", "b", "--report-output", "r.json"]
        exit_code = main_cli(raw_args)
        
        mock_load_verification_cfg.assert_called_once_with("invalid_conf.yaml", force_reload=True)
        self.assertEqual(exit_code, EXIT_CODE_CLI_ERROR)
        mock_setup_logging.assert_not_called() # Logging setup might not be reached

    @patch('src.cli.kfm_verifier_cli.parse_arguments')
    @patch('src.config.config_loader.load_verification_config')
    @patch('src.cli.kfm_verifier_cli.setup_logging')
    def test_main_cli_argparse_error(self, mock_setup_logging, mock_load_verification_cfg, mock_parse_args):
        # Simulate parse_arguments (the one inside main_cli, after config load) failing
        mock_parse_args.side_effect = SystemExit(2) 
        
        # load_verification_config must succeed for this path
        mock_load_verification_cfg.return_value = self.mock_default_verification_config
        
        # Minimal args to get past initial temp_parser in main_cli
        raw_args = ["--commit", "c", "--branch", "b", "--report-output", "r.json"]
        exit_code = main_cli(raw_args)
        
        self.assertEqual(exit_code, 2)
        mock_setup_logging.assert_called_once() # Logging setup should have happened
        mock_load_verification_cfg.assert_called_once() # Config load should have happened
        mock_parse_args.assert_called_once() # Full argument parsing was attempted

if __name__ == '__main__':
    unittest.main() 