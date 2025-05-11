#!/usr/bin/env python3
"""Test wrapper for langgraph_nodes.py to help test the call_llm_for_reflection function."""

from unittest.mock import patch, MagicMock
import importlib
import sys
import traceback


def mock_call_llm_for_reflection(state, **kwargs):
    """Wrapper function that mocks the API calls in call_llm_for_reflection.
    
    This allows tests to run without making real API calls to Google Generative AI.
    
    Args:
        state: The state to pass to call_llm_for_reflection
        
    Returns:
        The result of call_llm_for_reflection with mocked dependencies
    """
    # Import the module with the function
    try:
        if 'src.langgraph_nodes' in sys.modules:
            # Reload to ensure we get the latest version
            importlib.reload(sys.modules['src.langgraph_nodes'])
        
        from src.langgraph_nodes import call_llm_for_reflection
    except ImportError:
        print("Error importing call_llm_for_reflection:", traceback.format_exc())
        return "[ERROR] Could not import call_llm_for_reflection"
    
    # Create a mock dotenv module with load_dotenv function
    mock_dotenv = MagicMock()
    mock_dotenv.load_dotenv = MagicMock()
    
    # Define other mock objects
    mock_os = MagicMock()
    mock_genai = MagicMock()
    mock_model_class = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    
    # Create a proper mock time module that returns actual values instead of MagicMock objects
    # This prevents the f-string formatting errors with time.time()
    class MockTime:
        def __init__(self):
            self.sleep = MagicMock()
            self._counter = 100.0
            
        def time(self):
            # Increment counter to simulate time passing
            self._counter += 0.5
            return self._counter
    
    mock_time = MockTime()
    
    # Setup mock behaviors
    mock_os.getenv.return_value = "AIzaSyFakeTestAPIKey"
    mock_model_class.return_value = mock_model
    mock_response.text = "# Reflection on Test Decision\n\nThis is a mocked reflection response for testing."
    mock_model.generate_content.return_value = mock_response
    
    # Set up the patches - patch the module imports
    patches = [
        patch.dict('sys.modules', {'dotenv': mock_dotenv}),
        patch.dict('sys.modules', {'os': mock_os}),
        patch.dict('sys.modules', {'time': mock_time}),
    ]
    
    # Add specific function patches
    patches.extend([
        patch('src.langgraph_nodes.genai', mock_genai),
        patch('src.langgraph_nodes.genai.GenerativeModel', mock_model_class),
    ])
    
    # Apply all patches
    for p in patches:
        p.start()
    
    try:
        # Call the function with the patches in place
        result = call_llm_for_reflection(state, **kwargs)
        
        # Verify the mocks were called correctly
        mock_dotenv.load_dotenv.assert_called_once()
        mock_os.getenv.assert_called_with("GOOGLE_API_KEY")
        mock_genai.configure.assert_called_once()  # Just check it was called, not with what
        
        # For debugging
        from src.langgraph_nodes import reflect_logger
        reflect_logger.info("Mock validation successful")
        
        return result
    
    finally:
        # Stop all patches
        for p in patches:
            p.stop()


def mock_error_case(state, error_type="connection", **kwargs):
    """Wrapper function that mocks error cases in call_llm_for_reflection.
    
    Args:
        state: The state to pass to call_llm_for_reflection
        error_type: The type of error to simulate ("configuration", "connection", "value", "timeout", or "general")
        
    Returns:
        The result of call_llm_for_reflection when an error occurs
    """
    # Import the module with the function
    try:
        if 'src.langgraph_nodes' in sys.modules:
            # Reload to ensure we get the latest version
            importlib.reload(sys.modules['src.langgraph_nodes'])
        
        from src.langgraph_nodes import call_llm_for_reflection
    except ImportError:
        print("Error importing call_llm_for_reflection:", traceback.format_exc())
        return "[ERROR] Could not import call_llm_for_reflection"
    
    # Create a mock dotenv module with load_dotenv function
    mock_dotenv = MagicMock()
    mock_dotenv.load_dotenv = MagicMock()
    
    # Define other mock objects
    mock_os = MagicMock()
    mock_genai = MagicMock()
    mock_model_class = MagicMock()
    mock_model = MagicMock()
    
    # Create a proper mock time module that returns actual values instead of MagicMock objects
    # This prevents the f-string formatting errors with time.time()
    class MockTime:
        def __init__(self):
            self.sleep = MagicMock()
            self._counter = 100.0
            
        def time(self):
            # Increment counter to simulate time passing
            self._counter += 0.5
            return self._counter
    
    mock_time = MockTime()
    
    # Setup mock behaviors
    mock_os.getenv.return_value = "AIzaSyFakeTestAPIKey"
    mock_model_class.return_value = mock_model
    
    # Set up the patches - patch the module imports
    patches = [
        patch.dict('sys.modules', {'dotenv': mock_dotenv}),
        patch.dict('sys.modules', {'os': mock_os}),
        patch.dict('sys.modules', {'time': mock_time}),
    ]
    
    # Add specific function patches
    patches.extend([
        patch('src.langgraph_nodes.genai', mock_genai),
        patch('src.langgraph_nodes.genai.GenerativeModel', mock_model_class),
    ])
    
    # Apply all patches
    for p in patches:
        p.start()
    
    # Set up the error based on specific type after patches are applied
    if error_type == "configuration":
        # Configure the mock directly after patching
        mock_genai.configure.side_effect = ValueError("Missing API key")
    elif error_type == "connection":
        mock_model.generate_content.side_effect = ConnectionError("Failed to establish a connection")
    elif error_type == "value":
        mock_model.generate_content.side_effect = ValueError("Content blocked due to safety filters")
    elif error_type == "timeout":
        mock_model.generate_content.side_effect = TimeoutError("Request timed out")
    else:  # general error
        mock_model.generate_content.side_effect = Exception("API connection error")
    
    try:
        # Call the function with the patches in place
        result = call_llm_for_reflection(state, **kwargs)
        
        # Verify the mocks were called correctly (except in configuration error case)
        mock_dotenv.load_dotenv.assert_called_once()
        if error_type != "configuration":
            mock_os.getenv.assert_called_with("GOOGLE_API_KEY")
            mock_genai.configure.assert_called_once()
        
        return result
    
    finally:
        # Stop all patches
        for p in patches:
            p.stop() 