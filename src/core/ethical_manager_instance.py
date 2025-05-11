from .ethical_config_manager_mock import EthicalConfigManagerMock
from typing import Optional

# Initialize with a default mock ontology.
# This can be made configurable later (e.g., via environment variables or a main config file for the agent)
# if we want to test different mock ontologies.
active_ontology_config_id = "kfm_baseline_v1.0_mock" 

# Global instance, initialized with a default mock
# In a real application, this might be None by default and initialized by the app setup.
ecm_instance = EthicalConfigManagerMock(active_ontology_id="kfm_baseline_v1.0_mock_global")
print(f"Global ECM Mock Instance created with ontology: {ecm_instance.get_active_ontology_id()}")

def get_ecm_instance() -> EthicalConfigManagerMock:
    """Returns the global ECM instance."""
    global ecm_instance
    # Optionally, add logic here to initialize if ecm_instance is None,
    # though for now it's globally initialized.
    if ecm_instance is None:
        # This case should ideally not be hit if the global is always initialized.
        # If it can be None, then a default initialization here might be needed.
        print("Warning: Global ECM instance was None, re-initializing with default mock.")
        ecm_instance = EthicalConfigManagerMock(active_ontology_id="kfm_baseline_v1.0_mock_fallback")
    return ecm_instance

def set_ecm_instance(new_instance: Optional[EthicalConfigManagerMock]):
    """Sets the global ECM instance. Used for testing or dynamic configuration."""
    global ecm_instance
    if new_instance is not None:
        print(f"Global ECM instance being OVERWRITTEN. New instance type: {type(new_instance)}, Ontology: {new_instance.get_active_ontology_id() if hasattr(new_instance, 'get_active_ontology_id') else 'N/A'}")
    else:
        print("Global ECM instance being RESET to None.")
    ecm_instance = new_instance 