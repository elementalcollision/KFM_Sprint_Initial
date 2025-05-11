# LLM Logging Test Runbook

This document provides practical instructions for executing, debugging, and extending the test suites for the LLM logging functionality implemented in Task 49.5.

## Quick Start Guide

### Running Tests Locally

1. **Setup your environment**:
   ```bash
   # Activate virtual environment (if using one)
   source venv/bin/activate
   
   # Make sure dependencies are installed
   pip install -r requirements.txt
   ```

2. **Run all tests**:
   ```bash
   python -m unittest discover tests "test_*.py"
   ```

3. **Run specific test files**:
   ```bash
   # Test the core logging module
   python -m unittest tests/test_llm_logging.py
   
   # Test the enhanced reflection function
   python -m unittest tests/test_enhanced_llm_reflection_v2.py
   ```

4. **Run a specific test method**:
   ```bash
   python -m unittest tests.test_llm_logging.TestLLMLogging.test_log_api_error
   ```

5. **Run with verbose output**:
   ```bash
   python -m unittest -v tests/test_llm_logging.py
   ```

### Code Coverage

1. **Install coverage tool** (if not already installed):
   ```bash
   pip install coverage
   ```

2. **Run tests with coverage**:
   ```bash
   coverage run -m unittest discover tests "test_*.py"
   ```

3. **View coverage report**:
   ```bash
   # Console summary
   coverage report -m
   
   # Detailed HTML report
   coverage html
   ```

## Test Structure

### Test Organization

- **`TestLLMLogging`** class in `test_llm_logging.py`
  - Tests for all utility functions in `llm_logging.py`
  - Focuses on individual function behavior

- **`TestEnhancedLLMReflectionV2`** class in `test_enhanced_llm_reflection_v2.py`
  - Tests for `call_llm_for_reflection_v2` function in `langgraph_nodes.py`
  - Focuses on integration and error handling

### Test Environment

All tests use a controlled environment with:
- Mocked loggers to prevent file system writes
- Mocked API client to avoid real network calls
- Mocked time functions for deterministic testing

## Debugging Test Failures

### Common Failure Patterns

1. **Missing Mock Expectations**
   - **Symptom**: `AssertionError: Expected 'info' to have been called X times`
   - **Cause**: Logger mock not receiving expected calls
   - **Solution**: Check if log calls changed in implementation

2. **JSON Structure Assertions**
   - **Symptom**: `KeyError` or `AssertionError` when accessing log data
   - **Cause**: JSON structure changed or malformed
   - **Solution**: Print the actual log output during test and compare to expected structure

3. **Mock Side Effects**
   - **Symptom**: Unexpected behavior in retry logic or error handling
   - **Cause**: Mock side effects not configured correctly
   - **Solution**: Verify side effect returns and exceptions match test expectations

### Debugging Techniques

1. **Add Temporary Debug Output**:
   ```python
   # Add to test method temporarily
   print("Debug - Mock log call:", mock_logger.info.call_args)
   ```

2. **Use Debugger**:
   ```bash
   # Run test with debugger
   python -m pdb -c continue -m unittest tests/test_llm_logging.py
   ```

3. **Increase Unittest Verbosity**:
   ```bash
   python -m unittest -v tests/test_llm_logging.py
   ```

## Test Maintenance

### Adding New Test Cases

1. Add a new method to the appropriate test class:
   ```python
   def test_new_functionality(self):
       """Test description of what you're testing."""
       # Setup test conditions
       # ...
       
       # Call the function under test
       result = my_function()
       
       # Assert expected outcomes
       self.assertEqual(result, expected_value)
   ```

2. Ensure the new test:
   - Has a clear docstring explaining what's being tested
   - Follows the naming convention `test_what_is_being_tested`
   - Exercises both successful and error paths

### Updating Existing Tests

When updating tests to match implementation changes:

1. Update the test's expected values/behaviors
2. Maintain backward compatibility when possible
3. Consider adding additional tests for new behavior
4. Update test documentation if behavior changes significantly

## Test Data Reference

### Common Test Fixtures

Test fixtures are initialized in the `setUp` method of each test class:

1. In `TestLLMLogging`:
   - `self.test_context`: Contains standard test context with known request ID
   - `self.test_request`: Contains sample request data
   - `self.test_error`: Sample LLM error object

2. In `TestEnhancedLLMReflectionV2`:
   - `self.test_state`: Simulated KFM agent state
   - `self.successful_response`: Mock successful API response
   - Various mocks for dependencies

### Mock Configuration Reference

Each test file has specific mock configuration patterns:

1. `test_llm_logging.py` primarily mocks:
   - Logger objects to verify logging calls
   - Time functions to provide deterministic timing

2. `test_enhanced_llm_reflection_v2.py` mocks:
   - All external dependencies (API client, environment, etc.)
   - All internal logging utilities
   - Various response scenarios (success, errors, retries)

## Troubleshooting Guide

| Issue | Possible Cause | Resolution |
|-------|---------------|------------|
| `ModuleNotFoundError` | Missing dependencies | Verify requirements are installed |
| Unexpected log format | Log format changed | Update test assertions to match new format |
| Tests pass but real code fails | Mocks don't match real behavior | Test with integration tests |
| Mock not called | Code path changed | Debug with print statements |
| Tests timeout | Retry logic issue | Check for infinite loops |

## Future Test Improvements

Consider these improvements to the test suite:

1. **Integration Tests**: Add tests that use actual file system for logging
2. **Parameterized Tests**: Use parameterized tests for multiple similar test cases
3. **Fuzz Testing**: Add property-based testing for input validation
4. **Performance Tests**: Add benchmarks for logging operations
5. **CI Integration**: Add GitHub Actions workflow for automated testing 