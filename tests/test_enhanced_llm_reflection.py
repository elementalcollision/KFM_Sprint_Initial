"""
Test the enhanced error handling in call_llm_for_reflection_v2 function.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import time

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import call_llm_for_reflection_v2
from src.exceptions import (
    LLMAPIError,
    LLMNetworkError, 
    LLMTimeoutError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMServerError,
    LLMServiceUnavailableError
)


class TestEnhancedLLMReflection(unittest.TestCase):
    """Test cases for the enhanced error handling in call_llm_for_reflection_v2 function."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a valid state object
        self.test_state = {
            'kfm_action': {'action': 'keep', 'component': 'data_processor'},
            'active_component': 'data_processor',
            'result': {'accuracy': 0.85, 'latency': 0.2},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'reflections': []
        }
        
        # Set up patches
        self.patches = []
        
        # Patch reflect_logger
        logger_patch = patch('src.langgraph_nodes.reflect_logger')
        self.patches.append(logger_patch)
        self.logger_mock = logger_patch.start()
        
        # Patch get_reflection_prompt
        prompt_patch = patch('src.langgraph_nodes.get_reflection_prompt', return_value="Test reflection prompt")
        self.patches.append(prompt_patch)
        self.prompt_mock = prompt_patch.start()
        
        # Patch load_dotenv
        dotenv_patch = patch('src.langgraph_nodes.load_dotenv')
        self.patches.append(dotenv_patch)
        dotenv_patch.start()
        
        # Patch os.getenv
        os_patch = patch('src.langgraph_nodes.os.getenv', return_value="FAKE_API_KEY")
        self.patches.append(os_patch)
        self.os_getenv_mock = os_patch.start()
        
        # We're no longer mocking generate_error_reflection to test its actual implementation
        # Instead, we'll mock the generate_mock_reflection function
        mock_reflection_patch = patch('src.langgraph_nodes.generate_mock_reflection')
        self.patches.append(mock_reflection_patch)
        self.mock_reflection_mock = mock_reflection_patch.start()
        self.mock_reflection_mock.return_value = "# Mock Reflection Content\nThis is mock content."
        
        # Patch google.generativeai
        genai_patch = patch('google.generativeai')
        self.patches.append(genai_patch)
        self.genai_mock = genai_patch.start()
        
        # Set up model mock
        self.model_mock = MagicMock()
        self.genai_mock.GenerativeModel.return_value = self.model_mock
        
        # Set up successful response
        self.successful_response = MagicMock()
        self.successful_response.text = "This is a successful reflection."
    
    def tearDown(self):
        """Clean up all patches."""
        for p in self.patches:
            p.stop()
    
    def test_successful_api_call(self):
        """Test successful API call."""
        # Set up successful response
        self.model_mock.generate_content.return_value = self.successful_response
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify the model was configured
        self.genai_mock.configure.assert_called_once_with(api_key="FAKE_API_KEY")
        
        # Verify the model was called with the prompt
        self.model_mock.generate_content.assert_called_once_with("Test reflection prompt")
        
        # Verify the function returns the model's response
        self.assertEqual(result, "This is a successful reflection.")
        
        # Verify logging with regex pattern to match requests IDs
        self.logger_mock.info.assert_any_call(unittest.mock.ANY)
        log_calls = [str(call) for call in self.logger_mock.info.call_args_list]
        self.assertTrue(any('⭐ ENTER: call_llm_for_reflection_v2' in call for call in log_calls))
    
    def test_network_error_handling(self):
        """Test handling of network errors."""
        # Force generate_content to raise a ConnectionError
        self.model_mock.generate_content.side_effect = ConnectionError("Connection refused")
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify error handling uses assertIn instead of assertEqual
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("ERROR TYPE: Connection Error", result)
        self.assertIn("Connection refused", result)
        
        # Verify the model was called multiple times (retry)
        self.assertEqual(self.model_mock.generate_content.call_count, 3)
        
        # Verify error logging with regex pattern
        log_calls = [str(call) for call in self.logger_mock.error.call_args_list]
        self.assertTrue(any('Attempt 1/3: Network error connecting to LLM API: Connection refused' in call for call in log_calls))
    
    def test_rate_limit_error_handling(self):
        """Test handling of rate limit errors."""
        # Force generate_content to raise a ValueError for rate limiting
        self.model_mock.generate_content.side_effect = ValueError("Rate limit exceeded")
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify error handling
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("ERROR TYPE: RateLimit Error", result)
        self.assertIn("Rate limit exceeded", result)
    
    def test_empty_response_handling(self):
        """Test handling of empty API responses."""
        # Create a response with empty text
        empty_response = MagicMock()
        empty_response.text = ""
        self.model_mock.generate_content.return_value = empty_response
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify error handling
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("ERROR TYPE: InvalidRequest Error", result)
        self.assertIn("API returned an empty or invalid response", result)
    
    def test_content_filter_handling(self):
        """Test handling of content filter blocks."""
        # Force generate_content to raise a ValueError for safety filtering
        self.model_mock.generate_content.side_effect = ValueError("Content blocked due to safety settings")
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify error handling
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("ERROR TYPE: ContentFilter Error", result)
        self.assertIn("Content blocked due to safety settings", result)
    
    def test_missing_api_key_handling(self):
        """Test handling of missing API key."""
        # Configure mock os to return None for API key
        self.os_getenv_mock.return_value = None
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify error handling
        self.assertIn("[LLM REFLECTION ERROR]", result)
        # Note: LLMAuthenticationError is not being passed in the original code
        self.assertIn("GOOGLE_API_KEY not found in environment variables", result)
    
    def test_null_state_handling(self):
        """Test handling of null state."""
        # Call the function with None state
        result = call_llm_for_reflection_v2(None)
        
        # Verify error handling
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("Invalid state: state is None", result)
    
    def test_retry_success_after_failure(self):
        """Test successful retry after initial failures."""
        # Set up the model to fail twice, then succeed
        self.model_mock.generate_content.side_effect = [
            ConnectionError("Connection refused"),
            ConnectionError("Connection refused"),
            self.successful_response
        ]
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify the result is the successful response
        self.assertEqual(result, "This is a successful reflection.")
        
        # Verify the model was called exactly 3 times
        self.assertEqual(self.model_mock.generate_content.call_count, 3)
        
        # Verify error and success logging using patterns
        log_calls = [str(call) for call in self.logger_mock.error.call_args_list]
        self.assertTrue(any('Network error connecting to LLM API: Connection refused' in call for call in log_calls))
    
    def test_fallback_reflection_for_different_error_types(self):
        """Test that fallback reflections are customized based on error type."""
        # Create a mock state with required data
        mock_state = {
            'kfm_action': {'action': 'keep', 'component': 'test_component'},
            'active_component': 'test_component',
            'execution_performance': {'latency': 1.5, 'accuracy': 0.9}
        }
        
        # Import the function directly
        from src.langgraph_nodes import generate_error_reflection
        
        # Test authentication error fallback
        auth_reflection = generate_error_reflection(
            mock_state, 
            "Invalid API key", 
            error_type="LLMAuthenticationError"
        )
        self.assertIn("ERROR TYPE: Authentication Error", auth_reflection)
        self.assertIn("Please verify your API key is correct", auth_reflection)
        
        # Test rate limit error fallback
        rate_limit_reflection = generate_error_reflection(
            mock_state,
            "Rate limit exceeded",
            error_type="LLMRateLimitError"
        )
        self.assertIn("ERROR TYPE: RateLimit Error", rate_limit_reflection)
        self.assertIn("You've exceeded the rate limits for the API", rate_limit_reflection)
        
        # Test network error fallback
        network_reflection = generate_error_reflection(
            mock_state,
            "Connection refused",
            error_type="LLMNetworkError"
        )
        self.assertIn("ERROR TYPE: Network Error", network_reflection)
        self.assertIn("Please check your internet connection", network_reflection)
        
        # Test timeout error fallback
        timeout_reflection = generate_error_reflection(
            mock_state,
            "Request timed out",
            error_type="LLMTimeoutError"
        )
        self.assertIn("ERROR TYPE: Timeout Error", timeout_reflection)
        self.assertIn("The API request took too long to complete", timeout_reflection)
    
    def test_generate_mock_reflection_fallback(self):
        """Test that mock reflections are generated for fallback."""
        # Create a mock state with KFM action details
        mock_state = {
            'kfm_action': {'action': 'keep', 'component': 'data_processor'},
            'active_component': 'data_processor_v2',
            'execution_performance': {'latency': 1.5, 'accuracy': 0.9}
        }
        
        # Create a realistic mock for generate_mock_reflection
        mock_content = """# Reflection on Keep Decision for Component 'data_processor'

## Decision Analysis
This was a good decision.

## Execution Assessment
The execution using component 'data_processor_v2' was effective.
- Latency: 1.5
- Accuracy: 0.9

## Strengths
- Maintained system stability
- Good performance metrics

## Areas for Improvement
- Consider optimizing further

## Recommendation
Continue monitoring this component.
"""
        
        # Patch the mock reflection function to return our custom content
        with patch('src.langgraph_nodes.generate_mock_reflection', return_value=mock_content):
            # Import the functions directly
            from src.langgraph_nodes import generate_error_reflection
            
            # Generate a fallback reflection
            fallback = generate_error_reflection(
                mock_state,
                "Service unavailable",
                error_type="LLMServiceUnavailableError"
            )
            
            # Check that it contains meaningful content
            self.assertIn("[LLM REFLECTION ERROR]", fallback)
            self.assertIn("ERROR TYPE: ServiceUnavailable Error", fallback)
            self.assertIn("component 'data_processor'", fallback)
            self.assertIn("Service unavailable", fallback)
            
            # Check that it includes mock reflection content (from our mock)
            self.assertIn("Reflection on Keep Decision", fallback)
            
            # Check that the mock reflection includes the right components
            self.assertIn("latency: 1.5", fallback.lower())
            self.assertIn("accuracy: 0.9", fallback.lower())

    def test_reflection_node_graceful_degradation(self):
        """Test that reflection_node implements graceful degradation when LLM is unavailable."""
        # Import the needed modules
        from src.langgraph_nodes import reflection_node, call_llm_for_reflection_v2
        
        # Reset the static variables
        if hasattr(reflection_node, 'consecutive_failures'):
            reflection_node.consecutive_failures = 0
        if hasattr(reflection_node, 'last_success_time'):
            reflection_node.last_success_time = 0
        if hasattr(reflection_node, 'service_state'):
            reflection_node.service_state = 'AVAILABLE'
        
        # Create a mock state
        mock_state = {
            'kfm_action': {'action': 'keep', 'component': 'data_processor'},
            'active_component': 'data_processor_v2',
            'execution_performance': {'latency': 1.5, 'accuracy': 0.9},
            'reflections': []  # Initialize the reflections key
        }
        
        # Mock the LLM call to simulate failures
        with patch('src.langgraph_nodes.call_llm_for_reflection_v2', side_effect=Exception("Simulated LLM API failure")) as mock_llm_call:
            # First call should use fallback but stay in AVAILABLE or move to DEGRADED
            result1 = reflection_node(mock_state)
            self.assertIsInstance(result1, dict)
            self.assertIn('reflection', result1)
            self.assertIn('[LLM REFLECTION ERROR]', result1['reflection'])
            
            # Keep calling until we hit the retry threshold (5)
            for i in range(4):
                result = reflection_node(mock_state)
            
            # After 5 failures, state should be UNAVAILABLE
            self.assertEqual(reflection_node.service_state, 'UNAVAILABLE')
            
            # Now it should use the mock reflection directly
            result_unavailable = reflection_node(mock_state)
            self.assertIsInstance(result_unavailable, dict)
            self.assertIn('reflection', result_unavailable)
            self.assertIn('[LLM REFLECTION ERROR]', result_unavailable['reflection'])
            self.assertIn('Service currently unavailable', result_unavailable['reflection'])
            
        # Now mock a successful call after the cooldown
        with patch('src.langgraph_nodes.call_llm_for_reflection_v2', return_value="Successful reflection") as mock_llm_call:
            # Force state to HALF_OPEN by setting last_success_time to be past the cooldown
            reflection_node.last_success_time = time.time() - 700  # 700 seconds ago (past the 600s cooldown)
            
            # Next call should try the API and succeed, returning to AVAILABLE
            result_recovery = reflection_node(mock_state)
            self.assertEqual(reflection_node.service_state, 'AVAILABLE')
            self.assertEqual(reflection_node.consecutive_failures, 0)
            self.assertEqual(result_recovery['reflection'], "Successful reflection")


if __name__ == '__main__':
    unittest.main() 