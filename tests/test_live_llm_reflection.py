import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import call_llm_for_reflection, configure_genai_api, generate_error_response, load_api_key


class TestLiveLLMReflection(unittest.TestCase):
    """Test cases for the live LLM reflection call."""
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    def test_load_api_key_success(self, mock_os, mock_load_dotenv, mock_logger):
        """Test successful API key loading."""
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Call the function
        api_key = load_api_key()
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify the API key is returned correctly
        self.assertEqual(api_key, "AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify logging without revealing the key
        mock_logger.debug.assert_called_with("API key loaded successfully (key not logged for security)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    def test_load_api_key_invalid_format(self, mock_os, mock_load_dotenv, mock_logger):
        """Test loading API key with invalid format."""
        # Mock API key with wrong format
        mock_os.environ.get.return_value = "InvalidKey12345"
        
        # Call the function
        api_key = load_api_key()
        
        # Verify the API key is returned despite format warning
        self.assertEqual(api_key, "InvalidKey12345")
        
        # Verify warning was logged
        mock_logger.warning.assert_called_with("API key format may be incorrect. Google API keys typically start with 'AIza'")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    def test_load_api_key_missing(self, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling when API key is missing."""
        # Mock missing API key
        mock_os.environ.get.return_value = None
        
        # Call the function - should raise ValueError
        with self.assertRaises(ValueError) as context:
            load_api_key()
        
        # Verify error message
        self.assertIn("GOOGLE_API_KEY environment variable not set", str(context.exception))
        self.assertIn("Please set this variable or create a .env file with this key", str(context.exception))
        
        # Verify error was logged
        mock_logger.error.assert_called()
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_api_key')
    @patch('src.langgraph_nodes.genai.configure')
    def test_configure_genai_api_success(self, mock_configure, mock_load_api_key, mock_logger):
        """Test successful API configuration with secure key loading."""
        # Mock API key loading
        mock_load_api_key.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Call the function
        configure_genai_api()
        
        # Verify load_api_key was called
        mock_load_api_key.assert_called_once()
        
        # Verify genai.configure was called with the right key
        mock_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify success was logged
        mock_logger.info.assert_called_with("Google Generative AI API configured successfully")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_api_key')
    @patch('src.langgraph_nodes.genai.configure')
    def test_configure_genai_api_error(self, mock_configure, mock_load_api_key, mock_logger):
        """Test error handling in API configuration."""
        # Mock API key loading to raise an error
        mock_load_api_key.side_effect = ValueError("API key not found")
        
        # Call the function - should raise ValueError
        with self.assertRaises(ValueError) as context:
            configure_genai_api()
        
        # Verify load_api_key was called
        mock_load_api_key.assert_called_once()
        
        # Verify genai.configure was not called
        mock_configure.assert_not_called()
        
        # Verify error message
        self.assertEqual(str(context.exception), "API key not found")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    @patch('src.langgraph_nodes.time')
    def test_successful_llm_call(self, mock_time, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test successful LLM API call for reflection."""
        # Create test state
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model instance and response
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        mock_response = MagicMock()
        mock_response.text = "This is a thoughtful reflection on the KFM decision..."
        mock_model.generate_content.return_value = mock_response
        
        # Set up mock time
        mock_time.time.side_effect = [100, 105]  # Start and end times for elapsed calculation
        
        # Call the function
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify model was created with correct model name and additional parameters
        self.assertEqual(mock_model_class.call_count, 1)
        args, kwargs = mock_model_class.call_args
        self.assertEqual(args[0], 'gemini-2.0-flash')
        self.assertIn('generation_config', kwargs)
        self.assertIn('safety_settings', kwargs)
        
        # Verify generate_content was called with the prompt but without timeout parameter
        mock_model.generate_content.assert_called_once()
        
        # Verify response was returned
        self.assertEqual(reflection, "This is a thoughtful reflection on the KFM decision...")
        
        # Verify proper logging
        mock_logger.info.assert_any_call("⭐ ENTER: call_llm_for_reflection")
        mock_logger.info.assert_any_call("Making LLM call for reflection...")
        mock_logger.debug.assert_any_call("API call completed in 5.00 seconds")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (successful)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    def test_generic_api_error_handling(self, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling during LLM API call for generic exceptions."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model to raise a generic exception
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        mock_model.generate_content.side_effect = Exception("API connection error")
        
        # Call the function - should handle the exception gracefully
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify model was created with correct model name
        self.assertEqual(mock_model_class.call_count, 1)
        args, kwargs = mock_model_class.call_args
        self.assertEqual(args[0], 'gemini-2.0-flash')
        
        # Verify generate_content was called
        mock_model.generate_content.assert_called_once()
        
        # Verify error response format
        self.assertIn("[LLM REFLECTION ERROR]", reflection)
        self.assertIn("kill", reflection)
        self.assertIn("analyze_fast", reflection)
        self.assertIn("API call failed with error: Unexpected error calling LLM API: API connection error", reflection)
        
        # Verify error was logged
        mock_logger.error.assert_called_with("Unexpected error calling LLM API: API connection error")
        mock_logger.exception.assert_called_with("Exception details:")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (with unexpected error)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    def test_timeout_error_handling(self, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling during LLM API call for timeout errors."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model to raise a TimeoutError
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        mock_model.generate_content.side_effect = TimeoutError("Request timed out")
        
        # Call the function - should handle the exception gracefully
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify model was created with correct model name
        self.assertEqual(mock_model_class.call_count, 1)
        args, kwargs = mock_model_class.call_args
        self.assertEqual(args[0], 'gemini-2.0-flash')
        
        # Verify generate_content was called
        mock_model.generate_content.assert_called_once()
        
        # Verify error response format
        self.assertIn("[LLM REFLECTION ERROR]", reflection)
        self.assertIn("API call failed with error: LLM API call timed out after 30 seconds", reflection)
        
        # Verify error was logged
        mock_logger.error.assert_called_with("LLM API call timed out after 30 seconds")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (with timeout error)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    @patch('src.langgraph_nodes.time')
    def test_connection_error_handling(self, mock_time, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling during LLM API call for network connection errors."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model to raise a ConnectionError
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        # Set it to fail on first attempt but succeed on retry
        mock_model.generate_content.side_effect = [
            ConnectionError("Failed to establish a connection"),
            ConnectionError("Failed to establish a connection again")
        ]
        
        # Set up mock time.sleep to do nothing
        mock_time.sleep = MagicMock()
        
        # Call the function - should handle the exception gracefully but fail after retries
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify model was created with correct model name
        self.assertEqual(mock_model_class.call_count, 1)
        args, kwargs = mock_model_class.call_args
        self.assertEqual(args[0], 'gemini-2.0-flash')
        
        # Verify generate_content was called multiple times (initial + 1 retry)
        self.assertEqual(mock_model.generate_content.call_count, 2)
        
        # Verify sleep was called once for the retry
        mock_time.sleep.assert_called_once_with(2)
        
        # Verify error response format
        self.assertIn("[LLM REFLECTION ERROR]", reflection)
        self.assertIn("API call failed with error: Network error connecting to LLM API: Failed to establish a connection again", reflection)
        
        # Verify error was logged
        mock_logger.error.assert_any_call("Network error connecting to LLM API: Failed to establish a connection")
        mock_logger.error.assert_any_call("Network error connecting to LLM API: Failed to establish a connection again")
        mock_logger.info.assert_any_call("Retrying API call (1/2)...")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (with network error)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai')
    def test_configuration_error_handling(self, mock_genai, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling for API configuration issues."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock configuration to raise an exception
        mock_genai.configure.side_effect = ValueError("Missing API key")
        
        # Call the function - should handle the exception gracefully
        reflection = call_llm_for_reflection(state)
        
        # Verify API configuration was attempted
        mock_genai.configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify error response format
        self.assertIn("[LLM REFLECTION ERROR]", reflection)
        self.assertIn("API call failed with error: Configuration error in LLM call: Missing API key", reflection)
        
        # Verify error was logged
        mock_logger.error.assert_called_with("Configuration error in LLM call: Missing API key")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (with configuration error)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    def test_content_filtering_handling(self, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test error handling for content filtering blocks."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model to raise a ValueError with blocked content message
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        mock_model.generate_content.side_effect = ValueError("Content blocked due to safety filters")
        
        # Call the function - should handle the exception gracefully
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify model was created with correct model name
        self.assertEqual(mock_model_class.call_count, 1)
        args, kwargs = mock_model_class.call_args
        self.assertEqual(args[0], 'gemini-2.0-flash')
        
        # Verify generate_content was called
        mock_model.generate_content.assert_called_once()
        
        # Verify error response format
        self.assertIn("[LLM REFLECTION ERROR]", reflection)
        self.assertIn("API call failed with error: Content was blocked by safety filters", reflection)
        
        # Verify error was logged
        mock_logger.error.assert_called_with("Content was blocked by safety filters: Content blocked due to safety filters")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (with content filtering)")
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.load_dotenv')
    @patch('src.langgraph_nodes.os')
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.genai.configure')
    @patch('src.langgraph_nodes.time')
    def test_successful_retry_after_connection_error(self, mock_time, mock_genai_configure, mock_model_class, mock_os, mock_load_dotenv, mock_logger):
        """Test successful retry after a connection error."""
        # Create test state
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock API key
        mock_os.environ.get.return_value = "AIzaSyA1B2C3D4E5F6G7H8I9J0K"
        
        # Set up mock model instance and responses
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        # First call fails with connection error, second call succeeds
        mock_response = MagicMock()
        mock_response.text = "This is a thoughtful reflection on the KFM decision..."
        mock_model.generate_content.side_effect = [
            ConnectionError("Failed to establish a connection"),
            mock_response
        ]
        
        # Set up mock time
        mock_time.time.side_effect = [100, 105]  # Start and end times for elapsed calculation
        mock_time.sleep = MagicMock()  # Mock sleep to do nothing
        
        # Call the function
        reflection = call_llm_for_reflection(state)
        
        # Verify dotenv was loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify API was configured
        mock_genai_configure.assert_called_once_with(api_key="AIzaSyA1B2C3D4E5F6G7H8I9J0K")
        
        # Verify generate_content was called twice (initial failure + successful retry)
        self.assertEqual(mock_model.generate_content.call_count, 2)
        
        # Verify sleep was called for the retry
        mock_time.sleep.assert_called_once_with(2)
        
        # Verify response from successful retry was returned
        self.assertEqual(reflection, "This is a thoughtful reflection on the KFM decision...")
        
        # Verify proper logging
        mock_logger.error.assert_called_with("Network error connecting to LLM API: Failed to establish a connection")
        mock_logger.info.assert_any_call("Retrying API call (1/2)...")
        mock_logger.info.assert_any_call("⭐ EXIT: call_llm_for_reflection (successful)")
    
    def test_generate_error_response(self):
        """Test the generate_error_response function produces correctly formatted error messages."""
        # Create test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
        }
        
        # Generate error response
        error_message = "Test error message"
        response = generate_error_response(state, error_message)
        
        # Verify response format
        self.assertIn("[LLM REFLECTION ERROR]", response)
        self.assertIn("Reflection on 'kill' decision for component 'analyze_fast'", response)
        self.assertIn("API call failed with error: Test error message", response)
        self.assertIn("execution was attempted using component 'analyze_deep'", response)
        self.assertIn("latency of 1.5s", response)
        self.assertIn("accuracy of 0.95", response)
        self.assertIn("Please check your API configuration and network connectivity", response)


if __name__ == '__main__':
    unittest.main() 