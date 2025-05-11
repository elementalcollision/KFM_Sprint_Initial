"""
Advanced unit tests for the ErrorClassifier in src/error_classifier.py.

This module tests the error classification functionality in detail,
including classification logic, severity assessment, and recovery recommendations.
"""

import unittest
import json
import traceback
from unittest.mock import patch, MagicMock, Mock

from src.error_classifier import ErrorClassifier, ErrorCategory
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


class TestErrorClassifierAdvanced(unittest.TestCase):
    """Advanced test suite for the ErrorClassifier class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.classifier = ErrorClassifier()
    
    def test_categorize_error_by_exceptions(self):
        """Test categorization of all defined exception types."""
        # Setup error instances for all exception types
        error_instances = {
            LLMNetworkError("Network timeout"): ErrorCategory.NETWORK,
            LLMTimeoutError("Request timed out"): ErrorCategory.TIMEOUT,
            LLMConnectionError("Connection reset"): ErrorCategory.NETWORK,
            LLMAuthenticationError("Invalid API key"): ErrorCategory.AUTHENTICATION,
            LLMRateLimitError("Rate limit exceeded"): ErrorCategory.RATE_LIMIT,
            LLMInvalidRequestError("Malformed request"): ErrorCategory.CLIENT,
            LLMServerError("Internal server error"): ErrorCategory.SERVER,
            LLMServiceUnavailableError("Service down"): ErrorCategory.SERVER,
            LLMInternalError("Unknown internal error"): ErrorCategory.INTERNAL,
            Exception("Generic exception"): ErrorCategory.UNKNOWN
        }
        
        # Test each error type
        for error, expected_category in error_instances.items():
            category = self.classifier.categorize_error(error)
            self.assertEqual(
                category, 
                expected_category, 
                f"Wrong category for {type(error).__name__}: expected {expected_category}, got {category}"
            )
    
    def test_categorize_from_error_message(self):
        """Test categorization based on error message content."""
        # Test messages with keywords
        message_tests = [
            ("Connection timed out after 10s", ErrorCategory.TIMEOUT),
            ("API rate limit exceeded (429)", ErrorCategory.RATE_LIMIT),
            ("Unauthorized: Invalid API key", ErrorCategory.AUTHENTICATION),
            ("Bad request format: Invalid JSON", ErrorCategory.CLIENT),
            ("Internal server error (500)", ErrorCategory.SERVER),
            ("Service temporarily unavailable", ErrorCategory.SERVER),
            ("Network connection error", ErrorCategory.NETWORK),
            ("Unknown error occurred", ErrorCategory.UNKNOWN)
        ]
        
        for message, expected_category in message_tests:
            # Create a generic exception with the test message
            error = Exception(message)
            category = self.classifier.categorize_error(error)
            self.assertEqual(
                category, 
                expected_category, 
                f"Wrong category for message '{message}': expected {expected_category}, got {category}"
            )
    
    def test_assess_severity(self):
        """Test severity assessment for different error categories."""
        # Create test errors with different severities
        test_cases = [
            # Error, expected severity (1-5), is_recoverable
            (LLMTimeoutError("Short timeout"), 2, True),  # Transient timeout
            (LLMTimeoutError("Persistent timeout after multiple retries"), 4, False),  # Persistent
            (LLMNetworkError("Connection refused"), 3, True),  # Network issue
            (LLMAuthenticationError("Invalid API key"), 5, False),  # Auth problem
            (LLMRateLimitError("Rate limit exceeded"), 3, True),  # Rate limiting
            (LLMServerError("Internal server error"), 4, True),  # Server error
            (LLMInvalidRequestError("Malformed JSON"), 4, False),  # Client error
            (Exception("Generic error"), 3, False)  # Unknown error
        ]
        
        for error, expected_severity, expected_recoverable in test_cases:
            # Add context about error if needed
            if isinstance(error, LLMTimeoutError) and "multiple retries" in str(error):
                # Add retry context to make it persistent
                context = {"retry_count": 5}
            elif isinstance(error, LLMRateLimitError):
                context = {"rate_limit_count": 2}
            else:
                context = {}
                
            # Assess severity
            severity, is_recoverable = self.classifier.assess_severity(error, context)
            
            # Check results
            self.assertEqual(
                severity, 
                expected_severity, 
                f"Wrong severity for {type(error).__name__}: expected {expected_severity}, got {severity}"
            )
            self.assertEqual(
                is_recoverable, 
                expected_recoverable, 
                f"Wrong recoverability for {type(error).__name__}: expected {expected_recoverable}, got {is_recoverable}"
            )
    
    def test_get_error_details_severity_based_on_context(self):
        """Test that the classifier uses context to adjust severity and recommendations."""
        # Create a rate limit error
        error = LLMRateLimitError("Rate limit exceeded")
        
        # Test with different contexts
        contexts = [
            # Context, expected severity modification, expected recommendation contains
            (
                {"rate_limit_count": 1}, 
                2,  # Lower severity for first occurrence
                "wait and retry"
            ),
            (
                {"rate_limit_count": 5}, 
                4,  # Higher severity for repeated occurrences
                "reduce request frequency"
            ),
            (
                {"rate_limit_count": 10}, 
                5,  # Critical severity for persistent issues
                "implement client-side rate limiting"
            )
        ]
        
        for context, expected_severity, expected_recommendation in contexts:
            details = self.classifier.get_error_details(error, context)
            
            # Check severity adjustment
            self.assertEqual(
                details["severity"], 
                expected_severity, 
                f"Wrong severity with context {context}: expected {expected_severity}, got {details['severity']}"
            )
            
            # Check recommendations
            self.assertIn(
                expected_recommendation.lower(),
                details["recovery_recommendations"].lower(),
                f"Missing recommendation '{expected_recommendation}' with context {context}"
            )
    
    def test_get_error_details_full_output(self):
        """Test the complete output of get_error_details."""
        # Create a test error
        error = LLMTimeoutError("Request timed out after 30s")
        context = {"retry_count": 2, "endpoint": "api/v1/generate"}
        
        # Capture the traceback for comparison
        try:
            raise error
        except Exception:
            tb_str = traceback.format_exc()
        
        # Call get_error_details
        details = self.classifier.get_error_details(error, context)
        
        # Check that all expected fields are present and correct
        self.assertEqual(details["type"], "LLMTimeoutError")
        self.assertEqual(details["message"], "Request timed out after 30s")
        self.assertEqual(details["category"], ErrorCategory.TIMEOUT.name)
        self.assertIn("severity", details)
        self.assertIn("traceback", details)
        self.assertIn("recovery_recommendations", details)
        self.assertIn("is_recoverable", details)
        self.assertIn("error_context", details)
        self.assertEqual(details["error_context"]["retry_count"], 2)
        self.assertEqual(details["error_context"]["endpoint"], "api/v1/generate")
    
    def test_custom_classification_rules(self):
        """Test adding custom classification rules."""
        # Create a custom classifier with additional rules
        custom_classifier = ErrorClassifier()
        
        # Add a custom rule for a new error type
        class CustomAPIError(Exception):
            pass
        
        custom_classifier.add_classification_rule(
            error_type=CustomAPIError,
            category=ErrorCategory.API_SPECIFIC,
            base_severity=4,
            recoverable=False
        )
        
        # Add a custom message pattern rule
        custom_classifier.add_message_pattern_rule(
            pattern="quota exceeded",
            category=ErrorCategory.QUOTA,
            base_severity=4,
            recoverable=True
        )
        
        # Test the custom error type rule
        custom_error = CustomAPIError("Custom API error occurred")
        details = custom_classifier.get_error_details(custom_error)
        self.assertEqual(details["category"], ErrorCategory.API_SPECIFIC.name)
        self.assertEqual(details["severity"], 4)
        self.assertEqual(details["is_recoverable"], False)
        
        # Test the custom message pattern rule
        quota_error = Exception("Your monthly quota exceeded for this endpoint")
        details = custom_classifier.get_error_details(quota_error)
        self.assertEqual(details["category"], ErrorCategory.QUOTA.name)
        self.assertEqual(details["severity"], 4)
        self.assertEqual(details["is_recoverable"], True)
    
    def test_error_context_affects_recommendations(self):
        """Test that error context information affects recovery recommendations."""
        # Create a network error
        error = LLMNetworkError("Connection reset by peer")
        
        # Test with different error contexts
        contexts = [
            # Context, text that should be in recommendations
            (
                {"connection_failures": 1}, 
                "retry"  # Simple retry for first occurrence
            ),
            (
                {"connection_failures": 3, "last_successful_timestamp": 1000}, 
                "backoff"  # Exponential backoff for repeated failures
            ),
            (
                {"connection_failures": 10, "service_name": "OpenAI"}, 
                "alternative"  # Suggest alternative service for persistent issues
            )
        ]
        
        for context, expected_text in contexts:
            details = self.classifier.get_error_details(error, context)
            self.assertIn(
                expected_text.lower(),
                details["recovery_recommendations"].lower(),
                f"Missing recommendation keyword '{expected_text}' with context {context}"
            )
    
    def test_serialization_to_json(self):
        """Test that error details can be serialized to JSON."""
        # Create an error with nested context
        error = LLMServerError("Internal server error")
        context = {
            "timestamps": [1234, 5678],
            "nested": {"key": "value"},
            "metrics": {"success_rate": 0.75}
        }
        
        # Get the error details
        details = self.classifier.get_error_details(error, context)
        
        # Attempt to serialize to JSON
        try:
            json_str = json.dumps(details)
            # Parse it back to verify
            parsed = json.loads(json_str)
            self.assertEqual(parsed["type"], "LLMServerError")
            self.assertEqual(parsed["category"], ErrorCategory.SERVER.name)
        except Exception as e:
            self.fail(f"Failed to serialize error details to JSON: {e}")
    
    def test_classify_multiple_errors(self):
        """Test classifying a list of errors and getting aggregated results."""
        # Create a list of errors
        errors = [
            LLMTimeoutError("Timeout 1"),
            LLMNetworkError("Network error"),
            LLMTimeoutError("Timeout 2"),
            LLMRateLimitError("Rate limit")
        ]
        
        # Call classify_multiple
        classification = self.classifier.classify_multiple(errors)
        
        # Check the results
        self.assertEqual(len(classification), len(errors))
        
        # Check counts by category
        category_counts = {}
        for result in classification:
            category = result["category"]
            category_counts[category] = category_counts.get(category, 0) + 1
        
        self.assertEqual(category_counts[ErrorCategory.TIMEOUT.name], 2)
        self.assertEqual(category_counts[ErrorCategory.NETWORK.name], 1)
        self.assertEqual(category_counts[ErrorCategory.RATE_LIMIT.name], 1)
        
        # Check that we have error details for each error
        for result in classification:
            self.assertIn("type", result)
            self.assertIn("message", result)
            self.assertIn("category", result)
            self.assertIn("severity", result)
    
    def test_get_aggregate_error_analysis(self):
        """Test generating an aggregate analysis of multiple errors."""
        # Create a list of errors
        errors = [
            LLMTimeoutError("Timeout error"),
            LLMNetworkError("Network error 1"),
            LLMNetworkError("Network error 2"),
            LLMRateLimitError("Rate limit"),
            LLMServerError("Server error")
        ]
        
        # Get aggregate analysis
        analysis = self.classifier.get_aggregate_error_analysis(errors)
        
        # Check the analysis
        self.assertIn("total_errors", analysis)
        self.assertEqual(analysis["total_errors"], 5)
        
        self.assertIn("category_counts", analysis)
        category_counts = analysis["category_counts"]
        self.assertEqual(category_counts[ErrorCategory.TIMEOUT.name], 1)
        self.assertEqual(category_counts[ErrorCategory.NETWORK.name], 2)
        self.assertEqual(category_counts[ErrorCategory.RATE_LIMIT.name], 1)
        self.assertEqual(category_counts[ErrorCategory.SERVER.name], 1)
        
        self.assertIn("most_common_category", analysis)
        self.assertEqual(analysis["most_common_category"], ErrorCategory.NETWORK.name)
        
        self.assertIn("average_severity", analysis)
        self.assertIn("highest_severity", analysis)
        self.assertIn("actionable_insights", analysis)


if __name__ == '__main__':
    unittest.main() 