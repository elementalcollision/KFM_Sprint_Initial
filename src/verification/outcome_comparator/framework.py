"""
This module contains the main comparison orchestration logic, 
e.g., an OutcomeVerificationFramework class that uses the comparators.
"""
from typing import Dict, Any, List, Optional, Callable, Tuple, TypedDict
import dpath.util
import logging

from ..common_types import VerificationCheckResult, OverallVerificationResult
from .comparators import compare_exact, compare_numeric_with_tolerance
from src.core.exceptions import VerificationError, ConfigurationError

logger = logging.getLogger(__name__)

class VerificationCriterion(TypedDict):
    """Defines a single criterion for outcome verification."""
    check_name: str                 # A unique name for this check (e.g., "KFMDecision.ActionType")
    actual_value_path: str          # dpath-style path to the actual value in the input data (e.g., "kfm_decision.action")
    expected_value: Any             # The value the actual_value_path should resolve to
    comparator: str                 # Name of the comparator function to use (e.g., "exact", "numeric_tolerance")
    options: Optional[Dict[str, Any]] # Optional dictionary for comparator-specific options
    description: Optional[str]        # Optional human-readable description of what is being checked
    on_path_not_found: Optional[str]  # What to do if actual_value_path is not found: "fail" (default), "pass", "warn"

class OutcomeVerificationFramework:
    """
    Orchestrates the comparison of actual outcomes against expected criteria using defined comparators.
    """

    DEFAULT_COMPARATORS: Dict[str, Callable[..., Tuple[bool, str]]] = {
        "exact": compare_exact,
        "numeric_with_tolerance": compare_numeric_with_tolerance,
        # Future comparators will be registered here
        # "regex_match": compare_regex,
        # "list_contains": compare_list_contains,
    }

    def __init__(self, custom_comparators: Optional[Dict[str, Callable[..., Tuple[bool, str]]]] = None):
        """
        Initializes the framework, optionally with custom comparators.

        Args:
            custom_comparators: A dictionary to extend or override default comparators.
        """
        self.comparators = self.DEFAULT_COMPARATORS.copy()
        if custom_comparators:
            self.comparators.update(custom_comparators)
        logger.debug(f"OutcomeVerificationFramework initialized with {len(self.comparators)} comparators.")

    def verify(self, actual_data: Dict[str, Any], criteria: List[VerificationCriterion]) -> OverallVerificationResult:
        """
        Verifies the actual_data against a list of criteria.

        Args:
            actual_data: A dictionary containing the actual data to be verified.
            criteria: A list of VerificationCriterion objects defining the checks.

        Returns:
            An OverallVerificationResult object.
        """
        logger.info(f"Starting outcome verification for {len(criteria)} criteria.")
        all_check_results: List[VerificationCheckResult] = []
        overall_passed = True
        error_count = 0
        warning_count = 0

        if not criteria:
            logger.info("No verification criteria provided. Returning success.")
            return OverallVerificationResult(
                overall_passed=True, 
                checks=[], 
                summary="No verification criteria provided."
            )

        for i, criterion in enumerate(criteria):
            # Basic validation of criterion structure (could be more extensive or rely on Pydantic upstream)
            if not all(k in criterion for k in ['check_name', 'actual_value_path', 'expected_value', 'comparator']):
                msg = f"Criterion at index {i} is malformed (missing essential keys). Skipping."
                logger.error(msg)
                # Optionally, add a failed check result for this malformed criterion
                all_check_results.append(VerificationCheckResult(
                    check_name=criterion.get('check_name', f"MalformedCriterion_{i}"),
                    passed=False,
                    message=msg,
                    attribute_checked="N/A - Malformed Criterion"
                ))
                overall_passed = False
                error_count += 1
                continue # Skip this criterion

            check_name = criterion['check_name']
            actual_value_path = criterion['actual_value_path']
            expected_value = criterion['expected_value']
            comparator_name = criterion['comparator']
            options = criterion.get('options') 
            description = criterion.get('description', '') # Default to empty string
            on_path_not_found = criterion.get('on_path_not_found', 'fail').lower()

            logger.debug(f"Processing criterion '{check_name}': Path='{actual_value_path}', Comparator='{comparator_name}', Expected='{str(expected_value)[:50]}...'")

            actual_value: Any = None
            path_found = True
            current_check_passed = False
            specific_message = ""

            try:
                actual_value = dpath.util.get(actual_data, actual_value_path, separator='.')
                logger.debug(f"  Path '{actual_value_path}' resolved to actual value: '{str(actual_value)[:50]}...'")
            except KeyError:
                path_found = False
                msg_log = f"Path '{actual_value_path}' not found in actual data for check '{check_name}'."
                if on_path_not_found == 'pass':
                    current_check_passed = True
                    specific_message = f"Path not found, but configured to pass."
                    logger.info(f"{msg_log} Configured to PASS.")
                elif on_path_not_found == 'warn':
                    warning_count += 1
                    current_check_passed = False # A warning is not a pass for the check itself
                    specific_message = f"Path not found, configured as a warning."
                    logger.warning(f"{msg_log} Configured as WARN.")
                else: # Default to 'fail'
                    current_check_passed = False
                    specific_message = f"Path not found."
                    logger.error(f"{msg_log} Configured to FAIL.")
            except Exception as e:
                path_found = False
                current_check_passed = False
                specific_message = f"Error accessing path '{actual_value_path}': {type(e).__name__} - {str(e)}"
                logger.error(f"Error accessing path '{actual_value_path}' for check '{check_name}': {e}", exc_info=True)
                # This is an unexpected error during path access, potentially a VerificationError

            if path_found:
                comparator_func = self.comparators.get(comparator_name)
                if not comparator_func:
                    current_check_passed = False
                    specific_message = f"Comparator '{comparator_name}' not found."
                    logger.error(f"Comparator '{comparator_name}' for check '{check_name}' not found in registered comparators.")
                    # This is a configuration/setup error
                else:
                    try:
                        logger.debug(f"  Applying comparator '{comparator_name}' with options: {options}")
                        current_check_passed, specific_message = comparator_func(actual_value, expected_value, options)
                        logger.debug(f"  Comparator '{comparator_name}' result: Passed={current_check_passed}, Msg='{specific_message}'")
                    except Exception as e:
                        current_check_passed = False
                        specific_message = f"Error during comparison with '{comparator_name}': {type(e).__name__} - {str(e)}"
                        logger.error(f"Error during comparison for check '{check_name}' using '{comparator_name}': {e}", exc_info=True)
                        # This could be a VerificationError if the comparator itself has a bug or misuse
            
            if not current_check_passed and not (path_found is False and on_path_not_found == 'warn'):
                # Don't count path-not-found warnings as errors for overall_passed or error_count
                overall_passed = False
                error_count +=1
            
            final_message = f"Check '{check_name}' (Path: '{actual_value_path}'): {specific_message}"
            if description:
                final_message = f"{description} (Check: '{check_name}', Path: '{actual_value_path}'): {specific_message}"

            all_check_results.append(VerificationCheckResult(
                check_name=check_name,
                passed=current_check_passed,
                component_id=None, 
                attribute_checked=actual_value_path,
                expected_value=expected_value,
                actual_value=actual_value if path_found else None,
                message=final_message,
                discrepancies=None 
            ))

        summary_message_log: str
        if overall_passed and error_count == 0:
            summary_message = f"Outcome verification: All {len(criteria)} checks passed ({warning_count} warning(s))."
            summary_message_log = f"Outcome verification completed: All {len(criteria)} checks PASSED with {warning_count} warning(s)."
            logger.info(summary_message_log)
        else:
            summary_message = f"Outcome verification: {error_count} error(s) and {warning_count} warning(s) found out of {len(criteria)} checks."
            summary_message_log = f"Outcome verification completed: {error_count} FAILED check(s) and {warning_count} warning(s) out of {len(criteria)} total checks."
            logger.warning(summary_message_log)

        return OverallVerificationResult(
            overall_passed=overall_passed,
            checks=all_check_results,
            summary=summary_message,
            error_count=error_count,
            warning_count=warning_count
        ) 