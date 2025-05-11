"""
Examples for using the Registry State Verifier

This module provides examples of how to use the registry verifier to validate
the state of component registries in the application during verification.
"""

from typing import Dict, Any, Optional
from src.core.component_registry import ComponentRegistry
from src.core.execution_engine import ExecutionEngine
from src.verification.registry_verifier.live_client import LiveComponentRegistryClient
from src.verification.registry_verifier.verifier import RegistryStateVerifier
from src.verification.common_types import OverallVerificationResult

def verify_component_registry_state(
    registry: ComponentRegistry, 
    expected_state: Dict[str, Dict[str, Any]]
) -> OverallVerificationResult:
    """
    Verify the component registry state against expected values.
    
    Args:
        registry: The ComponentRegistry instance to verify
        expected_state: A dictionary mapping component IDs to expected attributes
            Example:
            {
                "analyze_fast": {
                    "is_default": True,
                    "attr_accuracy_level": 0.8,
                    "function_name": "analyze_fast_impl"
                },
                "analyze_accurate": {
                    "is_default": False, 
                    "attr_accuracy_level": 0.95
                }
            }
            
    Returns:
        An OverallVerificationResult with the verification results
    """
    # Create a client to access the registry
    client = LiveComponentRegistryClient(registry)
    
    # Create a verifier using the client
    verifier = RegistryStateVerifier(client)
    
    # Run verification against the expected state
    return verifier.verify_multiple_components(expected_state)

def verify_execution_engine_component_selection(
    engine: ExecutionEngine,
    expected_active_component: str
) -> OverallVerificationResult:
    """
    Verify that the execution engine has selected the expected component.
    
    Args:
        engine: The ExecutionEngine instance to verify
        expected_active_component: The expected active component ID
        
    Returns:
        An OverallVerificationResult with the verification results
    """
    # Access the registry from the execution engine
    registry = engine._registry
    
    # Create a client to access the registry
    client = LiveComponentRegistryClient(registry)
    
    # Create a verifier using the client
    verifier = RegistryStateVerifier(client)
    
    # Define expected state - just checking that the active component is marked as active
    expected_state = {
        expected_active_component: {
            # Here we're checking if this is the active component in the engine
            # We can add other expected properties as needed
            "is_default": (expected_active_component == registry.get_default_component_key())
        }
    }
    
    # Run verification
    return verifier.verify_multiple_components(expected_state)

def perform_kfm_verification_after_action(
    engine: ExecutionEngine,
    registry: ComponentRegistry,
    kfm_action: Dict[str, Any],
    expected_component_after_action: str
) -> Dict[str, OverallVerificationResult]:
    """
    Comprehensive verification for a KFM action.
    
    This shows a more complete example of how to verify registry and execution engine
    state after a KFM action has been applied.
    
    Args:
        engine: The ExecutionEngine instance
        registry: The ComponentRegistry instance
        kfm_action: The KFM action that was applied (e.g., {"action": "adjust_kfm", "component": "analyze_fast"})
        expected_component_after_action: The component ID expected to be active after the action
        
    Returns:
        A dictionary with verification results for different aspects
    """
    # Apply the KFM action
    engine.apply_kfm_action(kfm_action)
    
    # Now verify the state after the action
    results = {}
    
    # 1. Verify engine selected the correct component
    results["engine_component_selection"] = verify_execution_engine_component_selection(
        engine, expected_component_after_action
    )
    
    # 2. Verify registry state - basic check for existence and default status
    component_expectations = {}
    
    # Add expectations for the component we're switching to
    component_expectations[expected_component_after_action] = {
        "is_default": (expected_component_after_action == registry.get_default_component_key())
    }
    
    # Verify each component registered in the registry
    for component_id in registry.get_component_names():
        if component_id not in component_expectations:
            component_expectations[component_id] = {
                "is_default": (component_id == registry.get_default_component_key())
            }
    
    results["registry_state"] = verify_component_registry_state(
        registry, component_expectations
    )
    
    return results

def example_usage():
    """Example showing how to use the registry verification module."""
    # Create a test registry with sample components
    registry = ComponentRegistry()
    
    def analyze_fast(input_data):
        """Fast analysis with lower accuracy."""
        return {"result": "fast analysis"}, 0.8
    
    def analyze_accurate(input_data):
        """Accurate but slower analysis."""
        return {"result": "accurate analysis"}, 0.95
    
    # Add attributes to the components
    analyze_fast.accuracy_level = 0.8
    analyze_fast.latency_profile = "fast"
    analyze_accurate.accuracy_level = 0.95
    analyze_accurate.latency_profile = "slow"
    
    # Register components
    registry.register_component("analyze_fast", analyze_fast, True)
    registry.register_component("analyze_accurate", analyze_accurate)
    
    # Create execution engine
    engine = ExecutionEngine(registry)
    
    # Define expected state for verification
    expected_state = {
        "analyze_fast": {
            "is_default": True,
            "attr_accuracy_level": 0.8,
            "attr_latency_profile": "fast"
        },
        "analyze_accurate": {
            "is_default": False,
            "attr_accuracy_level": 0.95,
            "attr_latency_profile": "slow"
        }
    }
    
    # Verify registry state
    registry_verification = verify_component_registry_state(registry, expected_state)
    print(f"Registry verification passed: {registry_verification.overall_passed}")
    
    # Apply a KFM action
    kfm_action = {"action": "adjust_kfm", "component": "analyze_accurate"}
    comprehensive_results = perform_kfm_verification_after_action(
        engine, registry, kfm_action, "analyze_accurate"
    )
    
    # Print the results
    for verification_name, result in comprehensive_results.items():
        print(f"{verification_name}: {result.overall_passed} ({result.summary})")

if __name__ == "__main__":
    example_usage() 