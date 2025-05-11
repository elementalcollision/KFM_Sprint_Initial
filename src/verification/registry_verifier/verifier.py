from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging # Added
from .client import ComponentRegistryClient # client.py in the same directory
from ..common_types import VerificationCheckResult, OverallVerificationResult # From src/verification/common_types.py
import dpath.util # For deep dictionary path access and comparison
from src.core.exceptions import RegistryAccessError, VerificationError # Added

logger = logging.getLogger(__name__) # Added

class RegistryStateVerifier:
    """Verifies component registry states against expected criteria."""

    def __init__(self, client: ComponentRegistryClient):
        """
        Args:
            client: An instance of a ComponentRegistryClient implementation.
        """
        self.client = client
        logger.debug(f"RegistryStateVerifier initialized with client: {client.__class__.__name__}")

    def verify_component_attributes(
        self, 
        component_id: str, 
        expected_attributes: Dict[str, Any], 
        at_time: Optional[datetime] = None,
        check_prefix: str = "ComponentState"
    ) -> List[VerificationCheckResult]:
        """
        Verifies specific attributes of a single component against expected values.

        Args:
            component_id: The ID of the component to check.
            expected_attributes: A dictionary where keys are attribute paths (e.g., 'status', 'config.value')
                                 and values are the expected values for those attributes.
                                 Uses dpath-style paths for nested attributes.
            at_time: Optional datetime to fetch component state at a specific time.
            check_prefix: Prefix for the check_name in VerificationCheckResult.

        Returns:
            A list of VerificationCheckResult objects, one for each attribute checked.
        """
        results: List[VerificationCheckResult] = []
        logger.info(f"Verifying attributes for component: {component_id}")
        
        actual_component_state: Optional[Dict[str, Any]] = None
        component_found = True
        try:
            actual_component_state = self.client.get_component_state(component_id, at_time=at_time)
            if actual_component_state is None:
                component_found = False
                logger.warning(f"Component '{component_id}' not found in registry.")
                results.append(VerificationCheckResult(
                    check_name=f"{check_prefix}.{component_id}.Exists",
                    passed=False,
                    component_id=component_id,
                    message=f"Component '{component_id}' not found in registry."
                ))
        except RegistryAccessError as e:
            component_found = False
            logger.error(f"RegistryAccessError while fetching component '{component_id}': {e}", exc_info=True)
            results.append(VerificationCheckResult(
                check_name=f"{check_prefix}.{component_id}.Exists",
                passed=False,
                component_id=component_id,
                message=f"Failed to access registry for component '{component_id}': {e}"
            ))
        except Exception as e: # Catch any other unexpected error from the client
            component_found = False
            logger.error(f"Unexpected error while fetching component '{component_id}' from client: {e}", exc_info=True)
            # Wrap this in a VerificationError as it's an issue with the verification process itself
            # This indicates a problem beyond just data access, possibly with the client implementation.
            results.append(VerificationCheckResult(
                check_name=f"{check_prefix}.{component_id}.ClientError",
                passed=False,
                component_id=component_id,
                message=f"Client error fetching component '{component_id}': {e}"
            ))
            # We could also raise VerificationError here if this is considered a critical failure for the verifier itself
            # For now, just record it as a failed check.

        if not component_found:
            # If component wasn't found or client error, all attribute checks for it effectively fail
            for attr_path, expected_val in expected_attributes.items():
                results.append(VerificationCheckResult(
                    check_name=f"{check_prefix}.{component_id}.{attr_path}",
                    passed=False,
                    component_id=component_id,
                    attribute_checked=attr_path,
                    expected_value=expected_val,
                    actual_value=None,
                    message=f"Attribute check failed: Component '{component_id}' could not be retrieved."
                ))
            return results

        # Component was found (actual_component_state is not None here)
        for attr_path, expected_val in expected_attributes.items():
            check_name = f"{check_prefix}.{component_id}.{attr_path}"
            actual_val = None
            passed = False
            message = ""
            
            try:
                # dpath.util.get can raise KeyError if path is not found
                # or other errors if the object is not dict-like at some path segment.
                actual_val = dpath.util.get(actual_component_state, attr_path, separator='.')
                if actual_val == expected_val:
                    passed = True
                    message = f"Attribute '{attr_path}' matches expected value."
                    logger.debug(f"Check PASSED for {component_id} - '{attr_path}': Expected '{expected_val}', Got '{actual_val}'")
                else:
                    message = f"Attribute '{attr_path}' mismatch."
                    logger.warning(f"Check FAILED for {component_id} - '{attr_path}': Expected '{expected_val}', Got '{actual_val}'")
            except KeyError:
                message = f"Attribute '{attr_path}' not found in component '{component_id}'."
                logger.warning(f"Check FAILED for {component_id}: Attribute '{attr_path}' not found.")
            except Exception as e:
                # This could be dpath raising something other than KeyError, or other unexpected issues.
                message = f"Error accessing attribute '{attr_path}' in component '{component_id}': {str(e)}"
                logger.error(f"Error during attribute access for {component_id} - '{attr_path}': {e}", exc_info=True)
                # Consider wrapping this in VerificationError as well, if it's not a dpath specific error we expect.
                # For now, just record as a failed check with the error message.

            results.append(VerificationCheckResult(
                check_name=check_name,
                passed=passed,
                component_id=component_id,
                attribute_checked=attr_path,
                expected_value=expected_val,
                actual_value=actual_val,
                message=message
            ))
        logger.info(f"Finished verifying attributes for component: {component_id}. Results: {len(results)} checks.")
        return results

    def verify_multiple_components(
        self,
        expected_states_criteria: Dict[str, Dict[str, Any]],
        at_time: Optional[datetime] = None,
        check_prefix: str = "RegistryOverallState"
    ) -> OverallVerificationResult:
        """
        Verifies attributes of multiple components based on a criteria dictionary.

        Args:
            expected_states_criteria: A dictionary where keys are component_ids, 
                                      and values are dictionaries of expected attributes for that component
                                      (e.g., {"comp_A": {"status": "active"}, "comp_B": {"count": 10}}).
            at_time: Optional datetime to fetch states.
            check_prefix: Prefix for individual check names.

        Returns:
            An OverallVerificationResult object.
        """
        logger.info(f"Starting verification for multiple components. Criteria count: {len(expected_states_criteria)}")
        all_check_results: List[VerificationCheckResult] = []
        overall_passed = True
        error_count = 0 # Counts failed checks, not system errors
        warning_count = 0 # Could add if we had a WARN status for checks

        for component_id, expected_attrs in expected_states_criteria.items():
            component_check_results = self.verify_component_attributes(
                component_id=component_id,
                expected_attributes=expected_attrs,
                at_time=at_time,
                check_prefix=check_prefix
            )
            all_check_results.extend(component_check_results)
            for res in component_check_results:
                if not res.passed:
                    overall_passed = False
                    error_count +=1 
        
        if overall_passed:
            summary_message = f"Registry state verification: All {len(all_check_results)} checks passed."
            logger.info(summary_message)
        else:
            summary_message = f"Registry state verification: {error_count} issue(s) found out of {len(all_check_results)} checks."
            logger.warning(summary_message)

        return OverallVerificationResult(
            overall_passed=overall_passed,
            checks=all_check_results,
            summary=summary_message,
            error_count=error_count,
            warning_count=warning_count # Add if implemented
        )

    # Potential future method for snapshot-based verification:
    # def verify_registry_snapshot(
    #     self, 
    #     snapshot_identifier: Any, 
    #     expected_snapshot_criteria: Dict[str, Any] # Simplified criteria for snapshot
    # ) -> OverallVerificationResult:
    #     actual_snapshot = self.client.get_registry_snapshot(snapshot_identifier)
    #     # ... comparison logic for snapshot ...
    #     pass 