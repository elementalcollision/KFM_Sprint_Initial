"""
This module contains individual comparison functions used by the OutcomeVerificationFramework.

Each comparator function typically takes:
- actual_value: The value obtained from the system.
- expected_value: The value expected by the test case.
- options: An optional dictionary for comparison-specific settings (e.g., tolerance).

Each comparator returns a tuple: (passed: bool, message: str)
"""
from typing import Any, Optional, Tuple, Dict, Union, Callable
import re
import math

def compare_exact(actual_value: Any, expected_value: Any, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Performs an exact comparison (equality check) between actual and expected values.

    Args:
        actual_value: The actual value.
        expected_value: The expected value.
        options: Not used by this comparator.

    Returns:
        A tuple (passed: bool, message: str).
    """
    passed = actual_value == expected_value
    if passed:
        message = "Actual value matches expected value."
    else:
        message = f"Actual value '{actual_value}' does not match expected value '{expected_value}'."
    return passed, message

def compare_numeric_with_tolerance(
    actual_value: Union[int, float], 
    expected_value: Union[int, float], 
    options: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Compares two numeric values (int or float) within a specified tolerance.

    Args:
        actual_value: The actual numeric value.
        expected_value: The expected numeric value.
        options: A dictionary that can contain:
            - 'tolerance' (float): The absolute tolerance allowed for the comparison. Defaults to 1e-9.
            - 'relative_tolerance' (float): The relative tolerance allowed.
                                           If both absolute and relative are provided, the check passes
                                           if either tolerance is met.

    Returns:
        A tuple (passed: bool, message: str).
    """
    if not isinstance(actual_value, (int, float)) or not isinstance(expected_value, (int, float)):
        return False, "Both actual and expected values must be numeric (int or float)."

    options = options or {}
    abs_tolerance = options.get('tolerance', 1e-9) # Default absolute tolerance
    rel_tolerance = options.get('relative_tolerance')

    passed = False
    message = ""

    # Check absolute tolerance
    if math.isclose(actual_value, expected_value, abs_tol=abs_tolerance):
        passed = True
        message = f"Actual value {actual_value} is within absolute tolerance {abs_tolerance} of expected value {expected_value}."
    
    # If relative tolerance is provided and absolute check failed (or for more detail), check relative
    if rel_tolerance is not None:
        if math.isclose(actual_value, expected_value, rel_tol=rel_tolerance):
            if passed: # Already passed absolute, add to message
                 message += f" Also within relative tolerance {rel_tolerance}."
            else: # Passed relative but not absolute
                passed = True
                message = f"Actual value {actual_value} is within relative tolerance {rel_tolerance} of expected value {expected_value}."
        elif not passed: # Failed both
            message = (
                f"Actual value {actual_value} is not within absolute tolerance {abs_tolerance} "
                f"(diff: {abs(actual_value - expected_value)}) "
                f"or relative tolerance {rel_tolerance} (rel_diff: {abs(actual_value - expected_value) / abs(expected_value) if expected_value else 'inf'}) "
                f"of expected value {expected_value}."
            )
    elif not passed: # No relative tolerance, failed absolute
        message = (
            f"Actual value {actual_value} is not within absolute tolerance {abs_tolerance} "
            f"(diff: {abs(actual_value - expected_value)}) of expected value {expected_value}."
        )
        
    return passed, message

# Placeholder for future comparators
# def compare_regex(actual_value: str, expected_pattern: str, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass

# def compare_list_contains(actual_list: list, expected_item: Any, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass

# def compare_dict_contains_key(actual_dict: dict, expected_key: str, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass

# def compare_regex(actual_value: str, expected_pattern: str, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass

# def compare_list_contains(actual_list: list, expected_item: Any, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass

# def compare_dict_contains_key(actual_dict: dict, expected_key: str, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
#     pass 