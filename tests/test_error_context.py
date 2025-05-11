"""
Tests for the enhanced error context module.
"""

import os
import time
import json
import shutil
import unittest
from unittest.mock import patch, MagicMock

from src.error_context import (
    EnhancedError,
    generate_error_code,
    with_enhanced_error,
    capture_error_context,
    get_error_statistics,
    get_recent_errors,
    get_similar_errors,
    clear_error_registry,
    analyze_error_patterns,
    get_error_suggestions,
    normalize_error_message,
    ERROR_CATEGORIES,
    ERROR_SEVERITY
)

# Test directory for error snapshots
TEST_ERROR_SNAPSHOT_DIR = "logs/test_error_snapshots"

class TestEnhancedError(unittest.TestCase):
    """Tests for the EnhancedError class and related functions"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a test directory
        os.makedirs(TEST_ERROR_SNAPSHOT_DIR, exist_ok=True)
        
        # Clear any existing errors
        clear_error_registry()
        
        # Set up a mock state
        self.test_state = {"test_key": "test_value", "counter": 1}
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove test directory
        if os.path.exists(TEST_ERROR_SNAPSHOT_DIR):
            shutil.rmtree(TEST_ERROR_SNAPSHOT_DIR)
        
        # Clear error registry
        clear_error_registry()
    
    def test_enhanced_error_creation(self):
        """Test creating an EnhancedError"""
        # Create a basic enhanced error
        error = EnhancedError(
            message="Test error message",
            category="API_INTEGRATION",
            severity="WARNING"
        )
        
        # Check basic properties
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.category, "API_INTEGRATION")
        self.assertEqual(error.severity, "WARNING")
        self.assertIsNotNone(error.error_code)
        self.assertTrue(error.error_code.startswith("E03"))  # API_INTEGRATION category code
        self.assertIsNotNone(error.timestamp)
        self.assertIsNotNone(error.uid)
    
    def test_enhanced_error_with_original_exception(self):
        """Test creating an EnhancedError from an original exception"""
        # Create an original exception
        original = ValueError("Invalid value")
        
        # Create enhanced error from original
        error = EnhancedError(
            message="Enhanced error with original",
            original_error=original,
            category="STATE_VALIDATION"
        )
        
        # Check properties
        self.assertEqual(error.message, "Enhanced error with original")
        self.assertEqual(error.original_error, original)
        self.assertEqual(error.category, "STATE_VALIDATION")
        self.assertEqual(error.severity, "ERROR")  # Default
        self.assertTrue(error.error_code.startswith("E02"))  # STATE_VALIDATION category code
        self.assertIsNotNone(error.traceback)
    
    def test_enhanced_error_with_state(self):
        """Test creating an EnhancedError with state information"""
        # Mock the save_state_snapshot function in tracing module since it's imported at runtime
        with patch('src.tracing.save_state_snapshot') as mock_save:
            mock_save.return_value = "test_snapshot_id"
            
            # Create enhanced error with state
            error = EnhancedError(
                message="Error with state",
                category="GRAPH_EXECUTION",
                state=self.test_state
            )
            
            # Check that save_state_snapshot was called
            mock_save.assert_called_once()
            
            # Check snapshot ID is set
            self.assertEqual(error.state_snapshot_id, "test_snapshot_id")
            self.assertEqual(error.context["state_snapshot_id"], "test_snapshot_id")
    
    def test_enhanced_error_formatting(self):
        """Test the formatted output of EnhancedError"""
        # Create error
        error = EnhancedError(
            message="Test formatted error",
            category="CONFIGURATION",
            node_name="test_node"
        )
        
        # Get formatted message
        formatted = error.formatted_message()
        
        # Check content
        self.assertIn(error.error_code, formatted)
        self.assertIn("CONFIGURATION", formatted)
        self.assertIn("Test formatted error", formatted)
        self.assertIn("Node: test_node", formatted)
        self.assertIn("Time:", formatted)
    
    def test_to_dict_and_json(self):
        """Test conversion to dictionary and JSON"""
        # Create error
        error = EnhancedError(
            message="Test serialization",
            category="USER_INPUT",
            context={"test_context": "value"}
        )
        
        # Convert to dict
        error_dict = error.to_dict()
        
        # Check dict
        self.assertEqual(error_dict["message"], "Test serialization")
        self.assertEqual(error_dict["category"], "USER_INPUT")
        self.assertEqual(error_dict["context"]["test_context"], "value")
        
        # Convert to JSON
        error_json = error.to_json()
        
        # Check JSON
        error_from_json = json.loads(error_json)
        self.assertEqual(error_from_json["message"], "Test serialization")
        self.assertEqual(error_from_json["category"], "USER_INPUT")
    
    def test_save_to_file(self):
        """Test saving error to file"""
        # Create error
        error = EnhancedError(
            message="Test file saving",
            category="RESOURCE"
        )
        
        # Save to test directory
        filepath = error.save_to_file(TEST_ERROR_SNAPSHOT_DIR)
        
        # Check file exists
        self.assertTrue(os.path.exists(filepath))
        
        # Check file content
        with open(filepath, 'r') as f:
            saved_data = json.load(f)
            self.assertEqual(saved_data["message"], "Test file saving")
            self.assertEqual(saved_data["category"], "RESOURCE")
    
    def test_error_code_generation(self):
        """Test error code generation function"""
        # Generate codes for different categories and severities
        code1 = generate_error_code("GRAPH_EXECUTION", "ERROR")
        code2 = generate_error_code("STATE_VALIDATION", "WARNING")
        code3 = generate_error_code("API_INTEGRATION", "CRITICAL")
        
        # Check format
        self.assertTrue(code1.startswith("E0140"))  # GRAPH_EXECUTION(01) + ERROR(40)
        self.assertTrue(code2.startswith("E0230"))  # STATE_VALIDATION(02) + WARNING(30)
        self.assertTrue(code3.startswith("E0350"))  # API_INTEGRATION(03) + CRITICAL(50)
        
        # Check with specific code
        specific_code = generate_error_code("TIMEOUT", "INFO", 42)
        self.assertEqual(specific_code, "E0720042")  # TIMEOUT(07) + INFO(20) + 042
    
    @patch('src.error_context.error_logger')
    def test_error_logging(self, mock_logger):
        """Test error logging functionality"""
        # Create error
        error = EnhancedError(
            message="Test logging",
            severity="WARNING",
            category="PERMISSION"
        )
        
        # Log error
        error.log()
        
        # Check logger was called with appropriate level and message
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        self.assertEqual(args[0], 30)  # WARNING level
        self.assertIn("Test logging", args[1])
        self.assertIn("PERMISSION", args[1])

class TestErrorDecorator(unittest.TestCase):
    """Tests for the error decorator functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing errors
        clear_error_registry()
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear error registry
        clear_error_registry()
    
    def test_with_enhanced_error_decorator(self):
        """Test the with_enhanced_error decorator"""
        # Define a function with the decorator
        @with_enhanced_error(category="GRAPH_EXECUTION")
        def test_function(state, value):
            if value < 0:
                raise ValueError("Value must be positive")
            return state
        
        # Test successful execution
        result = test_function({"test": "data"}, 5)
        self.assertEqual(result, {"test": "data"})
        
        # Test error case
        with self.assertRaises(EnhancedError) as context:
            test_function({"test": "data"}, -1)
        
        # Check the enhanced error
        error = context.exception
        self.assertEqual(error.category, "GRAPH_EXECUTION")
        self.assertEqual(error.original_error.__class__, ValueError)
        self.assertEqual(str(error.original_error), "Value must be positive")
    
    def test_decorator_with_class_state(self):
        """Test the decorator with a class-based state"""
        # Create a simple class that mimics KFMAgentState
        class TestState:
            def __init__(self, data):
                self.data = data
            
            def to_dict(self):
                return self.data.copy()
        
        # Define decorated function
        @with_enhanced_error(category="STATE_VALIDATION")
        def process_state(state):
            if "required_field" not in state.to_dict():
                raise KeyError("Missing required field")
            return state
        
        # Create test state
        state = TestState({"other_field": "value"})
        
        # Test function with error
        with self.assertRaises(EnhancedError) as context:
            process_state(state)
        
        # Check error
        error = context.exception
        self.assertEqual(error.category, "STATE_VALIDATION")
        self.assertEqual(error.original_error.__class__, KeyError)
    
    def test_state_extraction_in_decorator(self):
        """Test state extraction in the decorator"""
        # Define a function that will print args to check what was passed
        @with_enhanced_error(category="DATA_FORMAT")
        def process_data(data):
            if not isinstance(data, dict):
                raise TypeError("Data must be a dictionary")
            return data
        
        # Test with a non-dict value
        with self.assertRaises(EnhancedError) as context:
            process_data("not a dict")
        
        # Check error
        error = context.exception
        self.assertEqual(error.category, "DATA_FORMAT")
        self.assertEqual(error.original_error.__class__, TypeError)

class TestErrorContextCapture(unittest.TestCase):
    """Tests for error context capture functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing errors
        clear_error_registry()
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear error registry
        clear_error_registry()
    
    @patch('src.tracing.get_trace_history')
    def test_capture_error_context(self, mock_get_trace):
        """Test capturing error context"""
        # Mock trace history
        mock_get_trace.return_value = [
            {
                "node": "test_node",
                "success": False,
                "error": "Original error in trace",
                "timestamp": time.time()
            }
        ]
        
        # Create an exception
        original_error = RuntimeError("Test runtime error")
        
        # Capture context
        enhanced = capture_error_context(
            error=original_error,
            state={"state_key": "value"},
            node_name="context_test_node",
            category="API_INTEGRATION"
        )
        
        # Check the enhanced error
        self.assertIsInstance(enhanced, EnhancedError)
        self.assertEqual(enhanced.message, "Test runtime error")
        self.assertEqual(enhanced.original_error, original_error)
        self.assertEqual(enhanced.category, "API_INTEGRATION")
        self.assertEqual(enhanced.node_name, "context_test_node")
        
        # Check context was added
        self.assertIn("trace_entry", enhanced.context)
        self.assertIn("caller", enhanced.context)
    
    def test_normalize_error_message(self):
        """Test normalizing error messages for pattern matching"""
        # Test with various message patterns
        msg1 = "Error processing item 12345"
        msg2 = "Error processing item 67890"
        msg3 = "Error at timestamp 2023-05-15T12:34:56"
        msg4 = "Cannot find file /path/to/file.txt"
        
        # Normalize messages
        norm1 = normalize_error_message(msg1)
        norm2 = normalize_error_message(msg2)
        norm3 = normalize_error_message(msg3)
        norm4 = normalize_error_message(msg4)
        
        # Check normalizations
        self.assertEqual(norm1, "Error processing item NUM")
        self.assertEqual(norm2, "Error processing item NUM")  # Should match norm1
        self.assertEqual(norm3, "Error at timestamp TIMESTAMP")
        self.assertEqual(norm4, "Cannot find file PATH")

class TestErrorRegistry(unittest.TestCase):
    """Tests for the error registry and statistics"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing errors
        clear_error_registry()
        
        # Create some test errors
        self.error1 = EnhancedError(
            message="Test error 1",
            category="GRAPH_EXECUTION",
            severity="ERROR"
        )
        
        self.error2 = EnhancedError(
            message="Test error 2",
            category="API_INTEGRATION",
            severity="WARNING"
        )
        
        self.error3 = EnhancedError(
            message="Similar to error 1",
            category="GRAPH_EXECUTION",
            severity="ERROR",
            node_name="same_node"
        )
        
        self.error4 = EnhancedError(
            message="Test error with number 12345",
            category="GRAPH_EXECUTION",
            severity="ERROR",
            node_name="same_node"
        )
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear error registry
        clear_error_registry()
    
    def test_get_error_statistics(self):
        """Test getting error statistics"""
        # Get statistics
        stats = get_error_statistics()
        
        # Check basics
        self.assertIn("total_errors", stats)
        self.assertIn("by_category", stats)
        self.assertIn("by_severity", stats)
        
        # Check category counts
        self.assertEqual(stats["by_category"]["GRAPH_EXECUTION"], 3)
        self.assertEqual(stats["by_category"]["API_INTEGRATION"], 1)
        
        # Check severity counts
        self.assertEqual(stats["by_severity"]["ERROR"], 3)
        self.assertEqual(stats["by_severity"]["WARNING"], 1)
    
    def test_get_recent_errors(self):
        """Test getting recent errors"""
        # Get recent errors
        recent = get_recent_errors(2)
        
        # Should return 2 most recent errors
        self.assertEqual(len(recent), 2)
        
        # Most recent should be error4
        self.assertEqual(recent[0]["message"], "Test error with number 12345")
    
    def test_similar_errors(self):
        """Test finding similar errors"""
        # The error registry should have identified similar errors
        similar = get_similar_errors(self.error3.error_code)
        
        # Should find at least one similar error (error4)
        self.assertGreaterEqual(len(similar), 1)
    
    def test_clear_registry(self):
        """Test clearing the error registry"""
        # Verify we have errors first
        stats_before = get_error_statistics()
        self.assertGreater(stats_before["total_errors"], 0)
        
        # Clear registry
        clear_error_registry()
        
        # Check statistics after clearing
        stats_after = get_error_statistics()
        self.assertEqual(stats_after["total_errors"], 0)
        
        # Check recent errors
        recent = get_recent_errors()
        self.assertEqual(len(recent), 0)

class TestErrorAnalysis(unittest.TestCase):
    """Tests for error analysis and suggestions"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing errors
        clear_error_registry()
        
        # Create a variety of test errors
        for i in range(5):
            EnhancedError(
                message=f"Database connection failed with error code {i}",
                category="API_INTEGRATION",
                severity="ERROR",
                node_name="db_connector"
            )
        
        for i in range(3):
            EnhancedError(
                message=f"Invalid state format at node {i}",
                category="STATE_VALIDATION",
                severity="WARNING",
                node_name=f"validator_{i}"
            )
        
        # Create a different type of error with original exception
        try:
            x = {}
            x["missing_key"]
        except KeyError as e:
            self.key_error = EnhancedError(
                message="Failed to access required key",
                original_error=e,
                category="GRAPH_EXECUTION",
                severity="ERROR",
                node_name="processor"
            )
    
    def tearDown(self):
        """Clean up after tests"""
        # Clear error registry
        clear_error_registry()
    
    def test_analyze_error_patterns(self):
        """Test analyzing error patterns"""
        # Run pattern analysis
        analysis = analyze_error_patterns()
        
        # Check structure
        self.assertIn("frequent_errors", analysis)
        self.assertIn("error_clusters", analysis)
        self.assertIn("recent_patterns", analysis)
        
        # Should identify API_INTEGRATION errors as frequent
        found_api_errors = False
        for error in analysis["frequent_errors"]:
            if error["category"] == "API_INTEGRATION" and error["count"] >= 5:
                found_api_errors = True
                break
        
        self.assertTrue(found_api_errors, "Should identify API_INTEGRATION errors as frequent")
        
        # Check recent patterns
        has_recent_pattern = False
        for pattern in analysis["recent_patterns"]:
            if pattern["count"] >= 3:  # We created at least 3 of multiple types
                has_recent_pattern = True
                break
        
        self.assertTrue(has_recent_pattern, "Should identify recent error patterns")
    
    def test_get_error_suggestions(self):
        """Test getting error suggestions"""
        # Get suggestions for the KeyError
        suggestions = get_error_suggestions(self.key_error)
        
        # Check basic structure
        self.assertIn("error_code", suggestions)
        self.assertIn("category", suggestions)
        self.assertIn("message", suggestions)
        self.assertIn("suggestions", suggestions)
        
        # Should have KeyError specific suggestions
        found_key_suggestion = False
        for suggestion in suggestions["suggestions"]:
            if "key exists" in suggestion.lower():
                found_key_suggestion = True
                break
        
        self.assertTrue(found_key_suggestion, "Should provide KeyError specific suggestions")
        
        # Get suggestions by error code
        code_suggestions = get_error_suggestions(self.key_error.error_code)
        self.assertEqual(code_suggestions["error_code"], self.key_error.error_code)
        
        # Try with invalid error code
        invalid_suggestions = get_error_suggestions("INVALID_CODE")
        self.assertIn("error", invalid_suggestions)
        self.assertEqual(len(invalid_suggestions["suggestions"]), 0)

if __name__ == "__main__":
    unittest.main() 