# src/core/resilience.py
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, RetryError, before_sleep_log
from typing import Type, Tuple, Callable, Any, Union, Optional # Added Union, Optional
from functools import wraps

# Attempt to import get_config, handle gracefully if it causes issues during early init or testing
try:
    from src.config.config_loader import get_config
except ImportError:
    get_config = None

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 5 # seconds

def log_attempt_number(retry_state):
    """Custom logger for retries that includes function name and exception class."""
    if retry_state.outcome:
        exc = retry_state.outcome.exception()
        func_name = retry_state.fn.__name__ if retry_state.fn else 'unknown_function'
        logger.warning(
            f"Retrying {func_name} due to {exc.__class__.__name__}: {exc} "
            f"(Attempt {retry_state.attempt_number}/{retry_state.retry_object.stop.max_attempt_number}). "
            f"Waiting {retry_state.retry_object.wait.wait_fixed}s before next attempt."
        )

def retry_on_exception(
    _func: Optional[Callable] = None, # New: to capture the function if decorator used as @retry_on_exception
    *, # New: make subsequent args keyword-only to distinguish usage
    exc_to_retry: Union[Type[BaseException], Tuple[Type[BaseException], ...]] = Exception,
    max_attempts: Optional[int] = None,
    wait_delay: Optional[Union[int, float]] = None, # Allow float for delay
    log_on_retry_via_level: Optional[int] = logging.WARNING,
    config_override: Optional[Any] = None  # Added config_override (should be GlobalConfig ideally)
) -> Callable:
    """
    A decorator to automatically retry a function if it raises specified exceptions.
    Uses global configuration for default retry attempts and delay if not provided.
    Can be overridden by a specific config_override object.
    Can be used as @retry_on_exception or @retry_on_exception(...).

    Args:
        _func: Internal use. The function to decorate if used as @retry_on_exception.
        exc_to_retry: The exception or tuple of exceptions to catch and retry on.
        max_attempts: Specific number of attempts for this retry. Overrides global/provided config.
        wait_delay: Specific delay (in seconds) between retries. Overrides global/provided config.
        log_on_retry_via_level: Logging level for tenacity's default retry logger.
        config_override: An optional GlobalConfig-like object to source retry parameters from.
                         If provided, its max_retries and retry_delay are used unless specific
                         max_attempts or wait_delay are given to the decorator.
    """

    def actual_decorator(func_to_decorate: Callable) -> Callable: # Renamed from 'decorator' to 'actual_decorator', 'func' to 'func_to_decorate'
        @wraps(func_to_decorate) # Use func_to_decorate
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            resolved_max_attempts = max_attempts
            resolved_wait_delay = wait_delay
            source_config = None

            if config_override is not None:
                source_config = config_override
                # logger.debug(f"Using provided config_override for retry settings.")
            elif get_config:
                try:
                    source_config = get_config()
                    # logger.debug(f"Using global config for retry settings.")
                except Exception as e:
                    logger.warning(f"Could not load global config for retry settings: {e}. Using decorator/hardcoded defaults.")
            
            if source_config:
                if resolved_max_attempts is None:
                    # Attempt to access like source_config.global_settings.max_retries
                    # or source_config.max_retries if it's already a GlobalConfig obj
                    try:
                        resolved_max_attempts = source_config.global_settings.max_retries
                    except AttributeError:
                        try:
                            resolved_max_attempts = source_config.max_retries
                        except AttributeError:
                            logger.warning("max_retries not found in provided/global config.")
                if resolved_wait_delay is None:
                    try:
                        resolved_wait_delay = source_config.global_settings.retry_delay
                    except AttributeError:
                        try:
                            resolved_wait_delay = source_config.retry_delay
                        except AttributeError:
                            logger.warning("retry_delay not found in provided/global config.")
            
            # Fallback to hardcoded defaults if still None
            # resolved_max_attempts from config or decorator arg is the number of *retries*.
            # Tenacity's stop_after_attempt expects the *total* number of attempts.
            actual_num_retries = resolved_max_attempts if resolved_max_attempts is not None else DEFAULT_MAX_RETRIES
            tenacity_total_attempts = actual_num_retries + 1
            
            actual_wait = resolved_wait_delay if resolved_wait_delay is not None else DEFAULT_RETRY_DELAY

            # Configure tenacity retry
            retry_conditions = lambda retry_state: isinstance(retry_state.outcome.exception(), exc_to_retry)
            
            # Use custom logger if a level is provided, otherwise tenacity default or none
            before_sleep_action = None
            if log_on_retry_via_level is not None:
                # Use our custom logger that includes more details
                before_sleep_action = log_attempt_number 
            else:
                # No logging before sleep if level is None
                pass 

            tenacity_retry_decorator = retry(
                stop=stop_after_attempt(tenacity_total_attempts), # Use the calculated total attempts
                wait=wait_fixed(actual_wait),
                retry=retry_conditions,
                before_sleep=before_sleep_action,
                reraise=True
            )

            try:
                return tenacity_retry_decorator(func_to_decorate)(*args, **kwargs) # Use func_to_decorate
            except RetryError as e:
                # This block is technically not hit if reraise=True, as the original exception is raised.
                # However, it's good practice for understanding. Tenacity would have logged the final failure.
                logger.error(f"Function {func_to_decorate.__name__} failed permanently after {actual_num_retries} retries (total {tenacity_total_attempts} attempts).") # Use func_to_decorate
                raise e.last_attempt.exception # Should be original exception type
            except Exception as e: # Catch any other exception not handled by tenacity (should not happen with reraise=True)
                logger.error(f"Unexpected error in {func_to_decorate.__name__} outside of tenacity retry logic: {e}") # Use func_to_decorate
                raise

        return wrapper
    
    if _func is None:
        # Called as @retry_on_exception(...) - return the actual_decorator
        return actual_decorator
    else:
        # Called as @retry_on_exception - _func is the function to decorate
        # Apply the actual_decorator to _func with default arguments for retry_on_exception
        return actual_decorator(_func)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    main_logger = logging.getLogger(__name__)
    main_logger.info("--- Testing retry_on_exception decorator --- ")

    # --- Mocking get_config for testing ---
    class MockGlobalSettings:
        max_retries = 2
        retry_delay = 1

    class MockVerificationConfig:
        global_settings = MockGlobalSettings()

    _mock_config_instance = MockVerificationConfig()
    original_get_config = get_config
    def mock_get_config_for_resilience_test():
        main_logger.info("(Mocked get_config called for resilience test)")
        return _mock_config_instance
    get_config = mock_get_config_for_resilience_test
    # --- End Mocking ---

    fail_count_1 = 0
    @retry_on_exception(exc_to_retry=ValueError, max_attempts=3, wait_delay=0.1)
    def func_fails_then_succeeds():
        global fail_count_1
        main_logger.info(f"Calling func_fails_then_succeeds (attempt for fail_count_1={fail_count_1+1})")
        if fail_count_1 < 2:
            fail_count_1 += 1
            raise ValueError("Simulated transient ValueError")
        main_logger.info("func_fails_then_succeeds succeeded.")
        return "Success after 2 failures!"

    main_logger.info("\nTest 1: Function fails twice then succeeds (ValueError, 3 attempts, 0.1s delay)")
    try:
        result = func_fails_then_succeeds()
        main_logger.info(f"Test 1 Result: {result}")
        assert result == "Success after 2 failures!"
        assert fail_count_1 == 2
    except ValueError as e:
        main_logger.error(f"Test 1 Caught unexpected error: {e}")

    fail_always_count = 0
    @retry_on_exception(exc_to_retry=KeyError, max_attempts=2, wait_delay=0.1, log_on_retry_via_level=logging.INFO)
    def func_always_fails():
        global fail_always_count
        fail_always_count += 1
        main_logger.info(f"Calling func_always_fails (total call count: {fail_always_count})")
        raise KeyError(f"Simulated persistent KeyError on attempt {fail_always_count}")

    main_logger.info("\nTest 2: Function always fails (KeyError, 2 attempts, 0.1s delay)")
    try:
        func_always_fails()
    except KeyError as e:
        main_logger.info(f"Test 2 Caught expected KeyError after retries: {e}")
        assert fail_always_count == 2 # Initial call + 1 retry = 2 attempts
    except Exception as e:
        main_logger.error(f"Test 2 Caught unexpected error type: {type(e).__name__} - {e}")

    fail_count_config = 0
    # For this test, log_on_retry_via_level=None will disable our custom before_sleep logger
    # Tenacity might still log if its own logger is configured globally, but our specific one won't run.
    @retry_on_exception(exc_to_retry=IOError, log_on_retry_via_level=None) # Uses mocked config (2 attempts, 1s delay)
    def func_with_config_defaults_and_no_custom_log():
        global fail_count_config
        main_logger.info(f"Calling func_with_config_defaults_and_no_custom_log (fail_count_config={fail_count_config+1})")
        if fail_count_config < 1:
            fail_count_config += 1
            raise IOError("Simulated IO error for config test")
        main_logger.info("func_with_config_defaults_and_no_custom_log succeeded.")
        return "Success with config retry (no custom log)!"

    main_logger.info("\nTest 3: Function uses config defaults for retry, no custom retry logging")
    try:
        result_config = func_with_config_defaults_and_no_custom_log()
        main_logger.info(f"Test 3 Result: {result_config}")
        assert result_config == "Success with config retry (no custom log)!"
        assert fail_count_config == 1
    except IOError as e:
        main_logger.error(f"Test 3 Caught unexpected IOError: {e}")

    # Restore original get_config
    if original_get_config is not None:
        get_config = original_get_config
    main_logger.info("\nResilience tests finished.") 