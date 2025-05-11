# LLM Logging Architecture & Test Implementation

This document explains the architecture of the LLM logging system implemented in task 49.5 and how it has been tested.

## System Architecture

### Core Components

The LLM logging system consists of several key components:

1. **Logging Utilities** (`src/llm_logging.py`):
   - Specialized logging functions for LLM API calls
   - Context management for request/response correlation
   - Structured JSON logging with sanitization
   - Performance metrics calculation

2. **Enhanced LLM Reflection** (`src/langgraph_nodes.py`):
   - Integration of logging into the reflection process
   - Error handling and classification
   - Retry mechanisms with proper logging
   - Fallback to error reflection when needed

### Key Features

#### 1. Request Context Management

```python
context = create_request_context(
    operation_type="reflection",
    model_name="gemini-2.0-flash",
    session_id="optional-session-id",
    user_id="optional-user-id"
)
```

Each API interaction gets a unique context containing:
- Unique request ID for request-response correlation
- Timestamp for temporal tracking
- Operation type and model information
- Optional session and user identifiers

#### 2. Structured Logging

```python
log_request(context, request_data, additional_context)
log_response(context, response_data, duration, status, additional_metrics)
log_api_error(context, error, duration, attempt, max_attempts, retry_after, request_data)
```

All logging functions:
- Generate structured JSON for machine readability
- Create human-readable logs for console/file output
- Include rich contextual information for debugging
- Sanitize sensitive information like API keys

#### 3. Performance Tracking

```python
start_time, get_elapsed = create_timer()
# ... perform operation ...
duration = get_elapsed()
metrics = calculate_performance_metrics(prompt_length, response_length, duration)
```

The system tracks:
- Total operation duration
- Estimated token usage and rates
- Character processing rates
- Attempt counts for retries

#### 4. Error Handling & Retry Logic

The system provides:
- Typed error classification with detailed attributes
- Retry tracking with attempt counts
- Contextual logging of errors with stack traces
- Fallback mechanisms for graceful degradation

## Test Implementation

### Test Architecture

The test suite consists of two main parts:

1. **Unit Tests for Logging Utilities** (`tests/test_llm_logging.py`):
   - Tests each function in isolation
   - Verifies correct behavior for normal and error paths
   - Validates data sanitization and truncation

2. **Integration Tests for Enhanced Reflection** (`tests/test_enhanced_llm_reflection_v2.py`):
   - Tests the integration of logging into the LLM reflection function
   - Verifies error handling, retries, and fallbacks
   - Ensures proper contextual logging

### Test Design Patterns

#### Dependency Injection for Testability

The system uses dependency injection to enable effective testing:

```python
# In production code
from src.llm_logging import log_request, log_response

# In test code
@patch('src.langgraph_nodes.log_request')
@patch('src.langgraph_nodes.log_response')
def test_method(self, mock_log_response, mock_log_request):
    # Test implementation
```

This allows:
- Verifying logging calls without actual logging
- Testing error scenarios safely
- Controlling timing and external dependencies

#### Context Managers for Resource Control

Tests use context managers for patching:

```python
# Setup patches
self.patcher_dotenv = patch('src.langgraph_nodes.load_dotenv')
self.patcher_logger = patch('src.langgraph_nodes.reflect_logger')

# Start patches in setUp
self.mock_dotenv = self.patcher_dotenv.start()
self.mock_logger = self.patcher_logger.start()

# Stop patches in tearDown
patch.stopall()
```

This ensures:
- Clean test isolation
- Proper resource management
- No test interference

#### Behavioral Verification

Tests verify not just results but also behaviors:

```python
# Verify request was logged
self.mock_log_request.assert_called_once()

# Verify error was logged with correct params
_, kwargs = self.mock_log_error.call_args
self.assertIsInstance(kwargs['error'], LLMTimeoutError)
```

This ensures:
- Side effects are correctly implemented
- Structured logging follows expected patterns
- Error handling behaves as designed

### Test Coverage Strategy

#### 1. Function-level Coverage

Each public function has dedicated test cases:

```python
def test_create_request_context(self):
    """Test that create_request_context returns a valid context dictionary."""
    # Test implementation

def test_create_timer(self):
    """Test that create_timer returns a usable timer."""
    # Test implementation
```

#### 2. Scenario-based Coverage

Tests cover specific business scenarios:

```python
def test_api_timeout_logs_error_and_retries(self):
    """Test that API timeout error logs and retries properly."""
    # Configure timeout then success
    # Test implementation
```

#### 3. Error Path Coverage

Tests deliberately trigger and verify error handling:

```python
def test_none_state_logs_error(self):
    """Test that None state logs an error."""
    # Pass None state
    # Verify error logging
```

## Expected Behaviors

### Logging Behavior

#### Request Logging

Every LLM API request should produce:

1. **JSON Log**: Structured entry with request context, parameters, sanitized prompt
2. **Standard Log**: Human-readable summary with request ID, operation type

#### Response Logging

Every LLM API response should produce:

1. **JSON Log**: Structured entry with response details, metrics, status
2. **Standard Log**: Human-readable summary with request ID, timing information

#### Error Logging

Every LLM API error should produce:

1. **JSON Log**: Structured entry with error type, message, traceback, retry information
2. **Standard Log**: Human-readable summary with error type, retry information

### Retry Behavior

When errors occur, the system should:

1. Log the error with attempt number
2. Wait appropriate backoff time
3. Retry the request (for retryable errors)
4. Log the attempt resolution (success or failure)
5. Fall back to error reflection after max attempts

### Performance Tracking Behavior

The system should calculate and log:

1. Total operation duration
2. Estimated token usage
3. Processing rates (tokens/sec, chars/sec)
4. Retry metrics if applicable

## Future Work and Improvements

### Testing Improvements

1. **Property-based Testing**: Add property-based tests for more comprehensive validation
2. **Integration Tests**: Add tests with real file system interactions
3. **Load Testing**: Test performance under high logging volume

### Architecture Improvements

1. **Asynchronous Logging**: Improve performance with non-blocking logging
2. **Structured Log Schema**: Formalize JSON schema for log entries
3. **Log Rotation**: Add log rotation capabilities for production use
4. **Log Analytics**: Integrate with log analytics platforms 