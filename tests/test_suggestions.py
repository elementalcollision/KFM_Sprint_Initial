"""
Tests for the Error Suggestions Engine.

This module contains tests for the suggestions.py module,
which provides intelligent suggestions for error resolution.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import shutil

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.suggestions import (
    SuggestionsEngine,
    SuggestionEntry,
    ErrorPattern,
    DocumentationReference,
    get_suggestions,
    submit_feedback,
    get_documentation_for_error
)

from src.error_context import (
    EnhancedError,
    clear_error_registry
)

class TestSuggestionEntry(unittest.TestCase):
    """Tests for the SuggestionEntry class."""
    
    def test_to_from_dict(self):
        """Test converting to and from dictionary."""
        entry = SuggestionEntry(
            suggestion="Test suggestion",
            confidence=0.8,
            example="Example code",
            documentation_link="doc/link.md",
            feedback_score=4.5,
            feedback_count=10,
            tags=["tag1", "tag2"]
        )
        
        # Convert to dict
        entry_dict = entry.to_dict()
        
        # Convert back to SuggestionEntry
        new_entry = SuggestionEntry.from_dict(entry_dict)
        
        # Check values
        self.assertEqual(entry.suggestion, new_entry.suggestion)
        self.assertEqual(entry.confidence, new_entry.confidence)
        self.assertEqual(entry.example, new_entry.example)
        self.assertEqual(entry.documentation_link, new_entry.documentation_link)
        self.assertEqual(entry.feedback_score, new_entry.feedback_score)
        self.assertEqual(entry.feedback_count, new_entry.feedback_count)
        self.assertEqual(entry.tags, new_entry.tags)

class TestErrorPattern(unittest.TestCase):
    """Tests for the ErrorPattern class."""
    
    def test_matches_string(self):
        """Test matching string patterns."""
        pattern = ErrorPattern(
            pattern="error message",
            regex=False
        )
        
        # Should match
        self.assertTrue(pattern.matches("This is an error message"))
        self.assertTrue(pattern.matches("ERROR MESSAGE found"))
        
        # Should not match
        self.assertFalse(pattern.matches("No match here"))
    
    def test_matches_regex(self):
        """Test matching regex patterns."""
        pattern = ErrorPattern(
            pattern=r"error \d+",
            regex=True
        )
        
        # Should match
        self.assertTrue(pattern.matches("Found error 123"))
        self.assertTrue(pattern.matches("error 456 occurred"))
        
        # Should not match
        self.assertFalse(pattern.matches("Error occurred"))
        self.assertFalse(pattern.matches("error message"))
    
    def test_to_from_dict(self):
        """Test converting to and from dictionary."""
        pattern = ErrorPattern(
            pattern="error pattern",
            regex=True,
            category="TEST",
            tags=["tag1", "tag2"],
            suggestions=[
                SuggestionEntry(suggestion="Suggestion 1"),
                SuggestionEntry(suggestion="Suggestion 2")
            ]
        )
        
        # Convert to dict
        pattern_dict = pattern.to_dict()
        
        # Convert back to ErrorPattern
        new_pattern = ErrorPattern.from_dict(pattern_dict)
        
        # Check values
        self.assertEqual(pattern.pattern, new_pattern.pattern)
        self.assertEqual(pattern.regex, new_pattern.regex)
        self.assertEqual(pattern.category, new_pattern.category)
        self.assertEqual(pattern.tags, new_pattern.tags)
        self.assertEqual(len(pattern.suggestions), len(new_pattern.suggestions))
        self.assertEqual(pattern.suggestions[0].suggestion, new_pattern.suggestions[0].suggestion)
        self.assertEqual(pattern.suggestions[1].suggestion, new_pattern.suggestions[1].suggestion)

class TestDocumentationReference(unittest.TestCase):
    """Tests for the DocumentationReference class."""
    
    def test_to_from_dict(self):
        """Test converting to and from dictionary."""
        doc = DocumentationReference(
            title="Test Doc",
            path="docs/test.md",
            url="http://example.com/doc",
            description="Test description",
            tags=["tag1", "tag2"],
            error_patterns=["error1", "error2"]
        )
        
        # Convert to dict
        doc_dict = doc.to_dict()
        
        # Convert back to DocumentationReference
        new_doc = DocumentationReference.from_dict(doc_dict)
        
        # Check values
        self.assertEqual(doc.title, new_doc.title)
        self.assertEqual(doc.path, new_doc.path)
        self.assertEqual(doc.url, new_doc.url)
        self.assertEqual(doc.description, new_doc.description)
        self.assertEqual(doc.tags, new_doc.tags)
        self.assertEqual(doc.error_patterns, new_doc.error_patterns)

class TestSuggestionsEngine(unittest.TestCase):
    """Tests for the SuggestionsEngine class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.kb_dir = os.path.join(self.temp_dir, "kb")
        self.feedback_dir = os.path.join(self.temp_dir, "feedback")
        self.docs_dir = os.path.join(self.temp_dir, "docs")
        
        os.makedirs(self.kb_dir, exist_ok=True)
        os.makedirs(self.feedback_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)
        
        # Create patches
        self.kb_patch = patch("src.suggestions.KNOWLEDGE_BASE_DIR", self.kb_dir)
        self.feedback_patch = patch("src.suggestions.FEEDBACK_DIR", self.feedback_dir)
        self.docs_patch = patch("src.suggestions.DOCUMENTATION_DIR", self.docs_dir)
        
        # Start patches
        self.kb_patch.start()
        self.feedback_patch.start()
        self.docs_patch.start()
        
        # Clear error registry
        clear_error_registry()
        
        # Create test errors
        self.test_error = EnhancedError(
            message="Test error message with KeyError problem",
            original_error=KeyError("missing_key"),
            category="STATE_VALIDATION",
            severity="ERROR"
        )
        
        self.test_error2 = EnhancedError(
            message="Connection failed with timeout",
            original_error=TimeoutError("Connection timed out"),
            category="API_INTEGRATION",
            severity="ERROR"
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop patches
        self.kb_patch.stop()
        self.feedback_patch.stop()
        self.docs_patch.stop()
        
        # Remove temp directory
        shutil.rmtree(self.temp_dir)
        
        # Clear error registry
        clear_error_registry()
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = SuggestionsEngine()
        
        # Should create knowledge base
        self.assertGreater(len(engine.knowledge_base), 0)
        
        # Should create documentation index
        self.assertGreater(len(engine.documentation_index), 0)
    
    def test_get_suggestions_for_error(self):
        """Test getting suggestions for an error."""
        engine = SuggestionsEngine()
        
        # Get suggestions for KeyError
        result = engine.get_suggestions_for_error(self.test_error)
        
        # Check basic structure
        self.assertIn("error_code", result)
        self.assertIn("category", result)
        self.assertIn("message", result)
        self.assertIn("suggestions", result)
        self.assertIn("documentation", result)
        
        # Should contain suggestions
        self.assertGreater(len(result["suggestions"]), 0)
        
        # Should contain either KeyError specific or STATE_VALIDATION specific suggestions
        has_key_error_suggestion = False
        for suggestion in result["suggestions"]:
            if "key" in suggestion.lower() or "state" in suggestion.lower():
                has_key_error_suggestion = True
                break
        
        self.assertTrue(has_key_error_suggestion, "Should contain relevant suggestions")
    
    def test_apply_error_heuristics(self):
        """Test applying heuristics to errors."""
        engine = SuggestionsEngine()
        
        # Create test error with state
        error_with_state = EnhancedError(
            message="KeyError for missing 'username'",
            original_error=KeyError("username"),
            category="STATE_VALIDATION",
            state={"user_id": 123, "email": "test@example.com", "usernam": "typo"}
        )
        
        # Apply heuristics
        suggestions = engine._apply_error_heuristics(error_with_state)
        
        # Should find similar keys
        has_similar_key_suggestion = False
        for suggestion in suggestions:
            if "usernam" in suggestion.suggestion:
                has_similar_key_suggestion = True
                break
        
        self.assertTrue(has_similar_key_suggestion, "Should suggest similar keys")
    
    def test_feedback_submission(self):
        """Test submitting feedback."""
        engine = SuggestionsEngine()
        
        # Submit feedback
        engine.add_feedback(
            error_code=self.test_error.error_code,
            suggestion="Check if the key exists",
            helpful=True
        )
        
        # Should have feedback data
        self.assertIn(self.test_error.error_code, engine.feedback_data)
        self.assertEqual(len(engine.feedback_data[self.test_error.error_code]), 1)
        self.assertTrue(engine.feedback_data[self.test_error.error_code][0]["helpful"])

class TestSuggestionsFunctions(unittest.TestCase):
    """Tests for the global suggestion functions."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test errors
        self.test_error = EnhancedError(
            message="Test error with missing key",
            original_error=KeyError("config"),
            category="CONFIGURATION",
            severity="ERROR"
        )
    
    def tearDown(self):
        """Clean up after tests."""
        clear_error_registry()
    
    def test_get_suggestions(self):
        """Test get_suggestions function."""
        # Get suggestions
        result = get_suggestions(self.test_error)
        
        # Should return suggestions
        self.assertIn("suggestions", result)
        self.assertGreater(len(result["suggestions"]), 0)
    
    def test_get_documentation(self):
        """Test get_documentation_for_error function."""
        # Get documentation
        docs = get_documentation_for_error(self.test_error)
        
        # Should return a list (even if empty)
        self.assertIsInstance(docs, list)
    
    def test_submit_feedback(self):
        """Test submit_feedback function."""
        # Submit feedback
        submit_feedback(
            error_code=self.test_error.error_code,
            suggestion="Check configuration file",
            helpful=True
        )
        
        # Function should not raise exceptions
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main() 