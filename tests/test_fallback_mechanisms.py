"""
Unit tests for fallback mechanisms in src/langgraph_nodes.py.

This module tests the fallback and graceful degradation mechanisms
that handle error scenarios when LLM API calls fail.
"""

import unittest
import json
from unittest.mock import patch, MagicMock, Mock

from src.langgraph_nodes import (
    generate_error_reflection,
    format_error_info
)
from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
    LLMServerError,
    LLMServiceUnavailableError,
    LLMInternalError
)


class TestFallbackMechanisms(unittest.TestCase):
    """Test suite for fallback mechanisms."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.test_state = {
            "session_id": "test-session-123",
            "user_id": "test-user-456",
            "current_context": {
                "action_type": "test_action",
                "component": "test_component",
                "active_component": "test_active_component",
                "previous_actions": [],
                "error_history": []
            }
        }
    
    def test_format_error_info(self):
        """Test the format_error_info function."""
        error_info = format_error_info(
            error_type="TestError",
            message="Test error message",
            category="TEST_CATEGORY",
            severity=2,
            traceback_info="Test traceback",
            recoverable=True,
            details={"additional": "info"}
        )
        
        # Check that the error info contains the expected fields
        self.assertEqual(error_info["type"], "TestError")
        self.assertEqual(error_info["message"], "Test error message")
        self.assertEqual(error_info["category"], "TEST_CATEGORY")
        self.assertEqual(error_info["severity"], 2)
        self.assertEqual(error_info["traceback"], "Test traceback")
        self.assertEqual(error_info["recoverable"], True)
        self.assertEqual(error_info["details"], {"additional": "info"})
        self.assertIn("timestamp", error_info)
    
    def test_generate_error_reflection_with_rate_limit(self):
        """Test generate_error_reflection with rate limit error."""
        error = LLMRateLimitError("Rate limit exceeded")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Rate limit exceeded",
            error_type="RateLimit",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("Rate limit exceeded", reflection)
        self.assertIn("RateLimit", reflection)
        self.assertIn("test_action", reflection)
        self.assertIn("test_component", reflection)
    
    def test_generate_error_reflection_with_authentication_error(self):
        """Test generate_error_reflection with authentication error."""
        error = LLMAuthenticationError("Invalid API key")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Invalid API key",
            error_type="Authentication",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("Invalid API key", reflection)
        self.assertIn("Authentication", reflection)
        self.assertIn("API key", reflection.lower())
    
    def test_generate_error_reflection_with_network_error(self):
        """Test generate_error_reflection with network error."""
        error = LLMNetworkError("Connection failed")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Connection failed",
            error_type="Network",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("Connection failed", reflection)
        self.assertIn("Network", reflection)
        self.assertIn("connection", reflection.lower())
    
    def test_generate_error_reflection_with_timeout_error(self):
        """Test generate_error_reflection with timeout error."""
        error = LLMTimeoutError("Request timed out")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Request timed out",
            error_type="Timeout",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("timed out", reflection.lower())
        self.assertIn("Timeout", reflection)
    
    def test_generate_error_reflection_with_server_error(self):
        """Test generate_error_reflection with server error."""
        error = LLMServerError("Internal server error")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Internal server error",
            error_type="Server",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("server error", reflection.lower())
        self.assertIn("Server", reflection)
    
    def test_generate_error_reflection_with_invalid_request(self):
        """Test generate_error_reflection with invalid request error."""
        error = LLMInvalidRequestError("Invalid request parameters")
        
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Invalid request parameters",
            error_type="InvalidRequest",
            error_obj=error
        )
        
        # Check for expected content in the reflection
        self.assertIn("Invalid request", reflection)
        self.assertIn("InvalidRequest", reflection)
    
    def test_generate_error_reflection_with_generic_error(self):
        """Test generate_error_reflection with generic error."""
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Unknown error occurred",
            error_type="Unknown"
        )
        
        # Check for expected content in the reflection
        self.assertIn("Unknown error", reflection)
        self.assertIn("Unknown", reflection)
    
    def test_generate_error_reflection_with_context(self):
        """Test generate_error_reflection with additional context."""
        # Add more context to the state
        state_with_context = self.test_state.copy()
        state_with_context["previous_errors"] = [
            {"type": "RateLimit", "message": "Previous rate limit"}
        ]
        state_with_context["additional_context"] = {
            "api_version": "v1.0",
            "environment": "test"
        }
        
        reflection = generate_error_reflection(
            state=state_with_context,
            error_message="New error with context",
            error_type="ContextError"
        )
        
        # Check that context is included in the reflection
        self.assertIn("New error with context", reflection)
        self.assertIn("ContextError", reflection)
        self.assertIn("test_action", reflection)
        self.assertIn("test_component", reflection)
    
    def test_reflection_includes_recovery_suggestions(self):
        """Test that error reflections include recovery suggestions."""
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Service unavailable",
            error_type="ServiceUnavailable",
            error_obj=LLMServiceUnavailableError("Service unavailable")
        )
        
        # Check for recovery suggestions
        self.assertIn("suggest", reflection.lower())
        self.assertIn("recovery", reflection.lower())
    
    def test_reflection_format(self):
        """Test the format of the error reflection."""
        reflection = generate_error_reflection(
            state=self.test_state,
            error_message="Format test error",
            error_type="FormatTest"
        )
        
        # Check that the reflection has the expected format
        lines = reflection.strip().split('\n')
        
        # Should have a heading with error type
        self.assertIn("FormatTest Error", lines[0])
        
        # Should mention the component and action
        component_line = next((line for line in lines if "Component" in line), None)
        self.assertIsNotNone(component_line)
        self.assertIn("test_component", component_line)
        
        action_line = next((line for line in lines if "Action" in line), None)
        self.assertIsNotNone(action_line)
        self.assertIn("test_action", action_line)


if __name__ == '__main__':
    unittest.main() 