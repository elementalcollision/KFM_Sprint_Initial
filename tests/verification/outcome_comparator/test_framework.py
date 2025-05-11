"""
Unit tests for the OutcomeVerificationFramework in outcome_comparator.framework.
"""
import unittest
import sys
import os
from typing import List, Dict, Any, Callable, Tuple

# Add the project root to the path so we can import modules from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.verification.outcome_comparator.framework import (
    OutcomeVerificationFramework,
    VerificationCriterion
)
from src.verification.common_types import OverallVerificationResult, VerificationCheckResult

# Mock comparator for testing error handling
def mock_error_comparator(actual: Any, expected: Any, options: Dict[str, Any] = None) -> Tuple[bool, str]:
    raise ValueError("Mock comparator error")

class TestOutcomeVerificationFramework(unittest.TestCase):
    """Test cases for the OutcomeVerificationFramework class."""

    def setUp(self):
        """Set up test environment before each test method."""
        self.framework = OutcomeVerificationFramework()
        self.actual_data = {
            "name": "TestObject",
            "count": 10,
            "value": 3.14159,
            "status": {
                "code": 200,
                "message": "OK"
            },
            "items": ["a", "b", "c"],
            "metadata": None
        }

    def test_verify_no_criteria(self):
        """Test verification with an empty list of criteria."""
        result = self.framework.verify(self.actual_data, [])
        self.assertTrue(result.overall_passed)
        self.assertEqual(len(result.checks), 0)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.summary, "No verification criteria provided.")

    def test_verify_single_passing_criterion_exact(self):
        """Test with a single criterion that passes using 'exact' comparator."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "NameCheck",
                "actual_value_path": "name",
                "expected_value": "TestObject",
                "comparator": "exact"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertTrue(result.overall_passed)
        self.assertEqual(len(result.checks), 1)
        self.assertTrue(result.checks[0].passed)
        self.assertEqual(result.checks[0].check_name, "NameCheck")
        self.assertEqual(result.checks[0].actual_value, "TestObject")
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.summary, "Outcome verification: All 1 checks passed (0 warning(s)).")

    def test_verify_single_failing_criterion_exact(self):
        """Test with a single criterion that fails using 'exact' comparator."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "NameMismatch",
                "actual_value_path": "name",
                "expected_value": "WrongObject",
                "comparator": "exact"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertFalse(result.overall_passed)
        self.assertEqual(len(result.checks), 1)
        self.assertFalse(result.checks[0].passed)
        self.assertEqual(result.checks[0].check_name, "NameMismatch")
        self.assertEqual(result.checks[0].actual_value, "TestObject")
        self.assertIn("does not match expected value 'WrongObject'", result.checks[0].message)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertIn("1 error(s) and 0 warning(s) found", result.summary)

    def test_verify_numeric_tolerance_passing(self):
        """Test numeric comparison with tolerance that passes."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "ValueCheck",
                "actual_value_path": "value",
                "expected_value": 3.1415,
                "comparator": "numeric_with_tolerance",
                "options": {"tolerance": 0.0001}
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertTrue(result.overall_passed)
        self.assertTrue(result.checks[0].passed)
        self.assertEqual(result.error_count, 0)

    def test_verify_nested_path_access(self):
        """Test accessing a value from a nested path."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "StatusCodeCheck",
                "actual_value_path": "status.code", # dpath uses / by default, but we set to .
                "expected_value": 200,
                "comparator": "exact"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertTrue(result.overall_passed)
        self.assertTrue(result.checks[0].passed)
        self.assertEqual(result.checks[0].actual_value, 200)
        self.assertEqual(result.error_count, 0)

    def test_path_not_found_default_fail(self):
        """Test behavior when actual_value_path is not found (default to fail)."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "MissingPathCheck",
                "actual_value_path": "nonexistent.path",
                "expected_value": "any",
                "comparator": "exact"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertFalse(result.overall_passed)
        self.assertFalse(result.checks[0].passed)
        self.assertIn("Path 'nonexistent.path' not found", result.checks[0].message)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 0)

    def test_path_not_found_option_pass(self):
        """Test behavior with on_path_not_found: 'pass'."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "MissingPathPassCheck",
                "actual_value_path": "nonexistent.path",
                "expected_value": "any",
                "comparator": "exact",
                "on_path_not_found": "pass"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertTrue(result.overall_passed) # Overall passes because the only check is configured to pass on missing path
        self.assertTrue(result.checks[0].passed)
        self.assertIn("configured to pass on missing path", result.checks[0].message)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0) # Not a warning if it passes

    def test_path_not_found_option_warn(self):
        """Test behavior with on_path_not_found: 'warn'."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "MissingPathWarnCheck",
                "actual_value_path": "nonexistent.path",
                "expected_value": "any",
                "comparator": "exact",
                "on_path_not_found": "warn"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertTrue(result.overall_passed) # A warning doesn't fail overall_passed by itself
        self.assertFalse(result.checks[0].passed) # The specific check is marked as not passed
        self.assertIn("configured as a warning", result.checks[0].message)
        self.assertEqual(result.error_count, 0) # Warnings don't count as errors
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.summary, "Outcome verification: All 1 checks passed (1 warning(s)).")

    def test_unknown_comparator(self):
        """Test behavior when a specified comparator is not found."""
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "UnknownComparatorCheck",
                "actual_value_path": "name",
                "expected_value": "TestObject",
                "comparator": "nonexistent_comparator"
            }
        ]
        result = self.framework.verify(self.actual_data, criteria)
        self.assertFalse(result.overall_passed)
        self.assertFalse(result.checks[0].passed)
        self.assertIn("Comparator 'nonexistent_comparator' not found", result.checks[0].message)
        self.assertEqual(result.error_count, 1)

    def test_comparator_raises_exception(self):
        """Test behavior when a comparator function raises an exception."""
        custom_framework = OutcomeVerificationFramework(custom_comparators={"error_comp": mock_error_comparator})
        criteria: List[VerificationCriterion] = [
            {
                "check_name": "ComparatorErrorCheck",
                "actual_value_path": "name",
                "expected_value": "TestObject",
                "comparator": "error_comp"
            }
        ]
        result = custom_framework.verify(self.actual_data, criteria)
        self.assertFalse(result.overall_passed)
        self.assertFalse(result.checks[0].passed)
        self.assertIn("Error during comparison with 'error_comp': Mock comparator error", result.checks[0].message)
        self.assertEqual(result.error_count, 1)

    def test_multiple_criteria_mix(self):
        """Test with multiple criteria, including passes, fails, and warnings."""
        criteria: List[VerificationCriterion] = [
            {"check_name": "C1_PassExactName", "actual_value_path": "name", "expected_value": "TestObject", "comparator": "exact"},
            {"check_name": "C2_FailExactCount", "actual_value_path": "count", "expected_value": 5, "comparator": "exact"},
            {"check_name": "C3_PassNumericValue", "actual_value_path": "value", "expected_value": 3.141, "comparator": "numeric_with_tolerance", "options": {"tolerance": 0.01}},
            {"check_name": "C4_WarnMissingPath", "actual_value_path": "optional_field", "expected_value": True, "comparator": "exact", "on_path_not_found": "warn"},
            {"check_name": "C5_FailUnknownComp", "actual_value_path": "name", "expected_value": "TestObject", "comparator": "bad_comp"},
            {"check_name": "C6_PassMissingPath", "actual_value_path": "another_optional", "expected_value": True, "comparator": "exact", "on_path_not_found": "pass"},
        ]
        result = self.framework.verify(self.actual_data, criteria)
        
        self.assertFalse(result.overall_passed) # Due to C2 and C5
        self.assertEqual(len(result.checks), 6)
        
        # C1
        self.assertTrue(result.checks[0].passed)
        # C2
        self.assertFalse(result.checks[1].passed)
        # C3
        self.assertTrue(result.checks[2].passed)
        # C4
        self.assertFalse(result.checks[3].passed) # Warn means check itself is False
        self.assertIn("configured as a warning", result.checks[3].message)
        # C5
        self.assertFalse(result.checks[4].passed)
        # C6
        self.assertTrue(result.checks[5].passed)
        
        self.assertEqual(result.error_count, 2) # C2 (FailExactCount) and C5 (FailUnknownComp)
        self.assertEqual(result.warning_count, 1) # C4 (WarnMissingPath)
        self.assertIn("2 error(s) and 1 warning(s) found out of 6 checks", result.summary)

    def test_summary_messages(self):
        """Test the summary messages for different outcomes."""
        # All pass, no warnings
        criteria_all_pass: List[VerificationCriterion] = [
            {"check_name": "P1", "actual_value_path": "name", "expected_value": "TestObject", "comparator": "exact"}
        ]
        result = self.framework.verify(self.actual_data, criteria_all_pass)
        self.assertEqual(result.summary, "Outcome verification: All 1 checks passed (0 warning(s)).")

        # All pass, with warnings
        criteria_pass_warn: List[VerificationCriterion] = [
            {"check_name": "P1", "actual_value_path": "name", "expected_value": "TestObject", "comparator": "exact"},
            {"check_name": "W1", "actual_value_path": "missing", "expected_value": True, "comparator": "exact", "on_path_not_found": "warn"}
        ]
        result = self.framework.verify(self.actual_data, criteria_pass_warn)
        self.assertEqual(result.summary, "Outcome verification: All 2 checks passed (1 warning(s)).")

if __name__ == '__main__':
    unittest.main() 