import pytest
import time
from unittest import mock
import logging

from src.core.resilience import retry_on_exception
from src.config.models import GlobalConfig
from src.core.exceptions import KFMVerifierError, ConfigurationError

# --- Fixtures for mock configurations ---
@pytest.fixture
def mock_config_low_retries():
    return GlobalConfig(
        log_level='INFO',
        log_file_path="logs/test_kfm_verifier.log",
        log_format='%(message)s',
        error_log_file_path="logs/test_kfm_verifier_errors.jsonl",
        error_log_format='{"message": "%(message)s"}',
        max_retries=2,  # Results in 3 total attempts (initial + 2 retries)
        retry_delay=0.01
    )

@pytest.fixture
def mock_config_no_retries():
    return GlobalConfig(
        log_level='INFO',
        log_file_path="logs/test_kfm_verifier.log",
        log_format='%(message)s',
        error_log_file_path="logs/test_kfm_verifier_errors.jsonl",
        error_log_format='{"message": "%(message)s"}',
        max_retries=0,  # Results in 1 total attempt
        retry_delay=0.01
    )

# --- Mock Service for testing ---
class MockService:
    def __init__(self):
        self.attempts = 0

    def successful_call(self):
        self.attempts += 1
        return "Success"

    def fails_once_then_succeeds(self):
        self.attempts += 1
        if self.attempts <= 1:
            raise ValueError("Transient Value Error")
        return "Success after one failure"

    def always_fails_value_error(self):
        self.attempts += 1
        raise ValueError("Persistent Value Error")

    def specific_kfm_error(self):
        self.attempts += 1
        raise KFMVerifierError("A KFM Verifier specific error")

    def call_with_args_kwargs(self, pos_arg, *, kw_arg):
        self.attempts += 1
        if self.attempts <=1: # Fail once
            raise ValueError(f"Failed with {pos_arg} and {kw_arg}")
        return f"Success with {pos_arg} and {kw_arg}"

class SpecificErrorToCatch(Exception):
    pass

class AnotherErrorNotToCatch(Exception):
    pass


class TestRetryDecorator:

    def test_successful_on_first_attempt(self, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(config_override=mock_config_low_retries)
        def decorated_call():
            return service.successful_call()
        
        result = decorated_call()
        assert result == "Success"
        assert service.attempts == 1

    def test_succeeds_after_one_failure(self, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=ValueError, config_override=mock_config_low_retries)
        def decorated_call():
            return service.fails_once_then_succeeds()
        
        result = decorated_call()
        assert result == "Success after one failure"
        assert service.attempts == 2 # Initial call + 1 retry

    def test_fails_if_exceeds_max_retries(self, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=ValueError, config_override=mock_config_low_retries)
        def decorated_call():
            return service.always_fails_value_error()
        
        with pytest.raises(ValueError, match="Persistent Value Error"):
            decorated_call()
        assert service.attempts == 3 # Initial call + 2 retries (since max_retries=2)

    def test_no_retries_if_max_retries_is_zero(self, mock_config_no_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=ValueError, config_override=mock_config_no_retries)
        def decorated_call():
            return service.always_fails_value_error()
        
        with pytest.raises(ValueError, match="Persistent Value Error"):
            decorated_call()
        assert service.attempts == 1 # Only the initial call

    def test_catches_only_specified_exceptions(self, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=SpecificErrorToCatch, config_override=mock_config_low_retries)
        def decorated_specific_catch():
            service.attempts += 1
            if service.attempts <= 1:
                raise SpecificErrorToCatch("Caught this one!")
            raise AnotherErrorNotToCatch("Should not retry on this!")

        with pytest.raises(AnotherErrorNotToCatch, match="Should not retry on this!"):
            decorated_specific_catch()
        assert service.attempts == 2 # First call (SpecificError), retry, second call (AnotherError)

    @mock.patch('time.sleep')
    def test_retry_delay_is_applied(self, mock_sleep, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=ValueError, config_override=mock_config_low_retries)
        def decorated_call():
            return service.fails_once_then_succeeds()
        
        decorated_call()
        assert service.attempts == 2
        mock_sleep.assert_called_once_with(mock_config_low_retries.retry_delay)

    @mock.patch('src.core.resilience.logger')
    def test_custom_log_message_on_retry(self, mock_logger_resilience, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=ValueError, max_attempts=2, config_override=mock_config_low_retries)
        def decorated_call():
            return service.always_fails_value_error()

        with pytest.raises(ValueError):
            decorated_call()
        assert service.attempts == 3
        
        expected_log_parts = [
            ("Retrying decorated_call due to ValueError", "Attempt 1/3"),
            ("Retrying decorated_call due to ValueError", "Attempt 2/3")
        ]
        
        actual_logs = []
        for call_arg_tuple in mock_logger_resilience.warning.call_args_list:
            log_message = call_arg_tuple[0][0]
            actual_logs.append(log_message)

        assert len(mock_logger_resilience.warning.call_args_list) == 2

        for i, (expected_part1, expected_part2) in enumerate(expected_log_parts):
            assert expected_part1 in actual_logs[i], f"Log part '{expected_part1}' not found in log: {actual_logs[i]}"
            assert expected_part2 in actual_logs[i], f"Log part '{expected_part2}' not found in log: {actual_logs[i]}"

    def test_catches_custom_kfm_verifier_error(self, mock_config_low_retries):
        service = MockService()
        @retry_on_exception(exc_to_retry=KFMVerifierError, config_override=mock_config_low_retries)
        def decorated_call():
            return service.specific_kfm_error()

        with pytest.raises(KFMVerifierError, match="A KFM Verifier specific error"):
            decorated_call()
        assert service.attempts == 3 # Initial + 2 retries for KFMVerifierError

    def test_function_with_arguments_and_kwargs(self, mock_config_low_retries):
        service = MockService()
        
        @retry_on_exception(exc_to_retry=ValueError, config_override=mock_config_low_retries)
        def func_with_args(pos_arg, *, kw_arg):
            service.attempts += 1
            if service.attempts <=1: # Fail once
                raise ValueError(f"Failed with {pos_arg} and {kw_arg}")
            return f"Success with {pos_arg} and {kw_arg}"

        result = func_with_args("positional_val", kw_arg="keyword_val")
        assert result == "Success with positional_val and keyword_val"
        assert service.attempts == 2

    def test_works_as_direct_decorator_no_call_if_defaults_ok(self):
        # This tests if @retry_on_exception (with no arguments) works,
        # relying on its internal defaults or global config (if get_config is not mocked out)
        service = MockService()

        @retry_on_exception # No parentheses, using all defaults
        def decorated_default_retry():
            service.attempts += 1
            if service.attempts <=1:
                raise ValueError("Default retry test")
            return "Default success"
        
        # To make this test self-contained and not rely on global get_config state:
        with mock.patch('src.core.resilience.get_config') as mock_get_cfg:
            # Simulate get_config returning a config where retries are enabled
            mock_get_cfg.return_value = GlobalConfig(max_retries=2, retry_delay=0.01) 
            result = decorated_default_retry()
            assert result == "Default success"
            assert service.attempts == 2

    @mock.patch('src.core.resilience.get_config')
    def test_get_config_failure_in_decorator(self, mock_get_config_func, mock_config_low_retries):
        # This test relies on the decorator itself calling get_config when no config_override is given.
        service = MockService()
        mock_get_config_func.side_effect = ConfigurationError("Failed to load global config!")

        @retry_on_exception(exc_to_retry=ValueError) # No config_override, will try get_config
        def decorated_fail_get_config():
            service.attempts +=1 # Should not be reached if get_config fails and decorator handles it
            raise ValueError("This should not be raised if config load fails gracefully in decorator")

        # If get_config fails, the decorator should fall back to its hardcoded defaults (3 retries)
        # and log a warning. The decorated function should still be callable.
        # Let's ensure the function is called and retries happen based on defaults.
        
        # For this test, we'll make the decorated function succeed on the first try
        # to check that the config loading failure doesn't prevent execution.
        @retry_on_exception(exc_to_retry=ValueError) 
        def decorated_succeeds_despite_config_fail():
            service.attempts +=1
            return "Success despite config load fail"

        with mock.patch('src.core.resilience.logger.warning') as mock_log_warning:
            result = decorated_succeeds_despite_config_fail()
            assert result == "Success despite config load fail"
            assert service.attempts == 1 # Called once, succeeded
            mock_log_warning.assert_any_call("Could not load global config for retry settings: Failed to load global config!. Using decorator/hardcoded defaults.")

        # Test retry behavior with failed get_config (should use hardcoded defaults)
        service.attempts = 0 # Reset
        @retry_on_exception(exc_to_retry=ValueError)
        def decorated_retries_on_default_despite_config_fail():
            service.attempts += 1
            if service.attempts < 3: # Default is 3 retries (initial + 2)
                raise ValueError("Fail for default retry")
            return "Success on default retry"
        
        with mock.patch('src.core.resilience.logger.warning'): # Suppress warning
            result = decorated_retries_on_default_despite_config_fail()
            assert result == "Success on default retry"
            assert service.attempts == 3 