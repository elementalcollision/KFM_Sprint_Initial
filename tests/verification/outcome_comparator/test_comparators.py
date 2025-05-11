"""
Unit tests for the individual comparators in outcome_comparator.comparators.
"""
import unittest
import sys
import os

# Add the project root to the path so we can import modules from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.verification.outcome_comparator.comparators import (
    compare_exact,
    compare_numeric_with_tolerance
)

class TestComparators(unittest.TestCase):
    """Test cases for comparator functions."""

    def test_compare_exact(self):
        """Tests for the compare_exact function."""
        # Matching values
        self.assertTrue(compare_exact(5, 5)[0])
        self.assertTrue(compare_exact("hello", "hello")[0])
        self.assertTrue(compare_exact(3.14, 3.14)[0])
        self.assertTrue(compare_exact(True, True)[0])
        self.assertTrue(compare_exact(None, None)[0])
        self.assertTrue(compare_exact([1, 2], [1, 2])[0])
        self.assertTrue(compare_exact({'a': 1}, {'a': 1})[0])

        # Non-matching values
        passed, message = compare_exact(5, 10)
        self.assertFalse(passed)
        self.assertIn("Actual value '5' does not match expected value '10'", message)

        passed, message = compare_exact("hello", "world")
        self.assertFalse(passed)
        self.assertIn("Actual value 'hello' does not match expected value 'world'", message)
        
        passed, message = compare_exact(3.14, 2.71)
        self.assertFalse(passed)
        self.assertIn("Actual value '3.14' does not match expected value '2.71'", message)

        passed, message = compare_exact(True, False)
        self.assertFalse(passed)
        self.assertIn("Actual value 'True' does not match expected value 'False'", message)

        passed, message = compare_exact([1, 2], [2, 1])
        self.assertFalse(passed)
        self.assertIn("Actual value '[1, 2]' does not match expected value '[2, 1]'", message)

        passed, message = compare_exact({'a': 1}, {'b': 2})
        self.assertFalse(passed)
        self.assertIn("Actual value '{'a': 1}' does not match expected value '{'b': 2}'", message)
        
        # Type mismatch
        passed, message = compare_exact(5, "5")
        self.assertFalse(passed)
        self.assertIn("Actual value '5' does not match expected value '5'", message) # Message is correct despite type diff

    def test_compare_numeric_with_tolerance_invalid_input(self):
        """Test compare_numeric_with_tolerance with invalid (non-numeric) inputs."""
        passed, message = compare_numeric_with_tolerance("not_a_number", 5)
        self.assertFalse(passed)
        self.assertEqual(message, "Both actual and expected values must be numeric (int or float).")

        passed, message = compare_numeric_with_tolerance(5, "not_a_number")
        self.assertFalse(passed)
        self.assertEqual(message, "Both actual and expected values must be numeric (int or float).")
        
        passed, message = compare_numeric_with_tolerance(None, 5)
        self.assertFalse(passed)
        self.assertEqual(message, "Both actual and expected values must be numeric (int or float).")

    def test_compare_numeric_with_tolerance_absolute(self):
        """Tests for compare_numeric_with_tolerance using absolute tolerance."""
        # Default tolerance (1e-9)
        self.assertTrue(compare_numeric_with_tolerance(5.0000000001, 5.0)[0])
        self.assertFalse(compare_numeric_with_tolerance(5.00000001, 5.0)[0]) # Outside 1e-9
        
        self.assertTrue(compare_numeric_with_tolerance(10, 10)[0])
        self.assertTrue(compare_numeric_with_tolerance(-5.0, -5.0000000001)[0])

        # Custom absolute tolerance
        options_abs_0_1 = {'tolerance': 0.1}
        self.assertTrue(compare_numeric_with_tolerance(5.05, 5.0, options_abs_0_1)[0])
        self.assertFalse(compare_numeric_with_tolerance(5.15, 5.0, options_abs_0_1)[0])
        
        options_abs_1 = {'tolerance': 1}
        self.assertTrue(compare_numeric_with_tolerance(100, 100.9, options_abs_1)[0])
        self.assertFalse(compare_numeric_with_tolerance(100, 101.1, options_abs_1)[0])
        
        # Zero values
        self.assertTrue(compare_numeric_with_tolerance(0.0, 0.00000000001, options_abs_0_1)[0])
        self.assertTrue(compare_numeric_with_tolerance(0.0, 0.0, options_abs_0_1)[0])

    def test_compare_numeric_with_tolerance_relative(self):
        """Tests for compare_numeric_with_tolerance using relative tolerance."""
        options_rel_0_01 = {'relative_tolerance': 0.01} # 1%
        
        # Within relative tolerance
        # 100 +/- 1% => 99 to 101
        self.assertTrue(compare_numeric_with_tolerance(100.5, 100.0, options_rel_0_01)[0]) 
        self.assertTrue(compare_numeric_with_tolerance(99.5, 100.0, options_rel_0_01)[0])
        
        # Outside relative tolerance, but might be within default absolute if numbers are small
        # Need to be careful with default absolute tolerance if not also specifying it as 0
        options_rel_0_01_abs_0 = {'relative_tolerance': 0.01, 'tolerance': 0.0}
        self.assertFalse(compare_numeric_with_tolerance(102.0, 100.0, options_rel_0_01_abs_0)[0])
        self.assertFalse(compare_numeric_with_tolerance(98.0, 100.0, options_rel_0_01_abs_0)[0])
        
        # Test with small numbers where relative tolerance has more impact
        self.assertTrue(compare_numeric_with_tolerance(0.01005, 0.01, options_rel_0_01_abs_0)[0])
        self.assertFalse(compare_numeric_with_tolerance(0.0102, 0.01, options_rel_0_01_abs_0)[0])

        # Test with zero expected value (relative tolerance is tricky here, relies on abs_tol in math.isclose)
        # math.isclose(a,b, rel_tol=x) is equivalent to abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
        # If b is 0, this means abs(a) <= max(rel_tol * abs(a), abs_tol) which means abs(a) <= abs_tol for small a if rel_tol < 1
        # So, for expected 0, it defaults to absolute tolerance effectively
        options_rel_only = {'relative_tolerance': 0.01, 'tolerance': 0.0} # Force rel_tol only effect
        self.assertTrue(compare_numeric_with_tolerance(0.0, 0.0, options_rel_only)[0])
        self.assertFalse(compare_numeric_with_tolerance(0.00001, 0.0, options_rel_only)[0]) # Fails as diff > 0 (abs_tol=0)
        
        # Check message content for relative failure
        _, message = compare_numeric_with_tolerance(102.0, 100.0, options_rel_0_01_abs_0)
        self.assertIn("or relative tolerance 0.01", message)
        self.assertIn("of expected value 100.0", message)

    def test_compare_numeric_with_tolerance_absolute_and_relative(self):
        """Tests for compare_numeric_with_tolerance with both tolerances."""
        # Passes due to absolute tolerance
        options_both1 = {'tolerance': 0.1, 'relative_tolerance': 0.001} # abs= +/-0.1, rel= +/-0.1% (so +/- 0.005 for 5.0)
        passed, msg = compare_numeric_with_tolerance(5.08, 5.0, options_both1)
        self.assertTrue(passed, msg)
        self.assertIn("within absolute tolerance 0.1", msg)
        self.assertNotIn("relative tolerance", msg) # Should short-circuit if abs passes first

        # Passes due to relative tolerance (fails absolute)
        options_both2 = {'tolerance': 0.01, 'relative_tolerance': 0.1} # abs= +/-0.01, rel= +/-10% (so +/- 0.5 for 5.0)
        passed, msg = compare_numeric_with_tolerance(5.4, 5.0, options_both2)
        self.assertTrue(passed, msg)
        self.assertIn("within relative tolerance 0.1", msg)
        self.assertNotIn("absolute tolerance 0.01", msg, "Message indicates it passed relative after failing absolute, this is fine.")
        # Test the case where it passes absolute then also passes relative
        options_both3 = {'tolerance': 0.5, 'relative_tolerance': 0.1} # abs= +/-0.5, rel= +/-10% (so +/- 0.5 for 5.0)
        passed, msg = compare_numeric_with_tolerance(5.4, 5.0, options_both3)
        self.assertTrue(passed, msg)
        self.assertIn("within absolute tolerance 0.5", msg)
        self.assertIn("Also within relative tolerance 0.1", msg)

        # Fails both
        options_both4 = {'tolerance': 0.01, 'relative_tolerance': 0.01} # abs= +/-0.01, rel= +/-0.1%
        passed, msg = compare_numeric_with_tolerance(5.2, 5.0, options_both4)
        self.assertFalse(passed, msg)
        self.assertIn("not within absolute tolerance 0.01", msg)
        self.assertIn("or relative tolerance 0.01", msg)

if __name__ == '__main__':
    unittest.main() 