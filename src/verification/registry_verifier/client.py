from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

class ComponentRegistryClient(ABC):
    """Abstract Base Class for a client that interacts with a Component Registry."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the client, potentially with configuration like connection details, auth tokens etc.
        Args:
            config: A dictionary containing configuration for the client.
        """
        self.config = config or {}
        # print(f"Initializing {self.__class__.__name__} with config: {config is not None}")

    def connect(self) -> None:
        """Establishes a connection to the registry if needed. Can be a no-op for some clients."""
        # print(f"{self.__class__.__name__}: connect() called.")
        pass # Default implementation is no-op

    def disconnect(self) -> None:
        """Closes the connection to the registry if needed. Can be a no-op."""
        # print(f"{self.__class__.__name__}: disconnect() called.")
        pass # Default implementation is no-op

    @abstractmethod
    def get_component_state(self, component_id: str, at_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the state of a specific component.
        Args:
            component_id: The unique identifier for the component.
            at_time: Optional. If the registry supports versioning/snapshots, 
                     retrieve state at/near this specific time.
        Returns:
            A dictionary representing the component's state, or None if not found or error.
        """
        pass

    @abstractmethod
    def get_all_components_state(self, at_time: Optional[datetime] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Retrieves the state of all relevant components.
        Args:
            at_time: Optional. If the registry supports versioning/snapshots, 
                     retrieve state at/near this specific time.
        Returns:
            A dictionary where keys are component_ids and values are their states,
            or None if an error occurs.
        """
        pass

    def get_registry_snapshot(self, snapshot_identifier: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieves a full or partial snapshot of the registry if supported.
        The nature of snapshot_identifier depends on the registry implementation 
        (e.g., a timestamp, a specific snapshot ID, a transaction ID).
        Args:
            snapshot_identifier: An identifier for the desired snapshot.
        Returns:
            A dictionary representing the registry snapshot, or None.
        """
        # print(f"{self.__class__.__name__}: get_registry_snapshot() called with {snapshot_identifier}, not implemented by default.")
        return None # Default: not supported

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

# Example concrete implementation (InMemory - for testing or simple cases)
# This would typically be in its own file or a specific client module.
class InMemoryComponentRegistryClient(ComponentRegistryClient):
    """An in-memory client for testing or for direct access to an in-process registry object."""
    def __init__(self, registry_data: Dict[str, Dict[str, Any]], config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.registry_data = registry_data # This is the mock/actual in-memory registry
        # print(f"InMemoryComponentRegistryClient initialized with {len(registry_data)} components.")

    def get_component_state(self, component_id: str, at_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        # In-memory version might not support `at_time` unless data is structured for it.
        if at_time:
            # print(f"Warning: InMemoryComponentRegistryClient does not support 'at_time' for get_component_state.")
            pass
        return self.registry_data.get(component_id)

    def get_all_components_state(self, at_time: Optional[datetime] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        if at_time:
            # print(f"Warning: InMemoryComponentRegistryClient does not support 'at_time' for get_all_components_state.")
            pass
        return self.registry_data.copy() # Return a copy to prevent external modification

# --- Added for Retry Decorator Example ---
import time
import random
import logging
from src.core.resilience import retry_on_exception
from src.core.exceptions import RegistryAccessError, KFMVerifierError # Assuming these exist

logger = logging.getLogger(__name__)

class MockLiveComponentRegistryClient(ComponentRegistryClient):
    """
    A mock client that simulates live network calls and can demonstrate retry logic.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.fail_count = 0
        self.max_failures_before_success = config.get("mock_max_failures", 2) if config else 2
        self.simulated_data_source = {
            "component_A": {"status": "active", "version": "1.0.2"},
            "component_B": {"status": "inactive", "version": "0.9.0"},
        }

    @retry_on_exception(exc_to_retry=(RegistryAccessError, ConnectionError), max_attempts=3, wait_delay=1)
    def _fetch_from_registry(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Simulates a network call that might fail a few times."""
        logger.info(f"Attempting to fetch from registry endpoint: {endpoint} with params: {params}")
        
        # Simulate transient failure
        if self.fail_count < self.max_failures_before_success:
            self.fail_count += 1
            # Simulate different types of network errors randomly
            if random.random() < 0.5:
                logger.warning(f"_fetch_from_registry: Simulating ConnectionError (attempt {self.fail_count})")
                raise ConnectionError(f"Mock Connection Error to {endpoint} on attempt {self.fail_count}")
            else:
                logger.warning(f"_fetch_from_registry: Simulating RegistryAccessError (attempt {self.fail_count})")
                raise RegistryAccessError(f"Mock Registry Access Error for {endpoint} on attempt {self.fail_count}")
        
        # Simulate successful fetch
        logger.info(f"_fetch_from_registry: Successfully fetched from {endpoint}")
        # Based on endpoint/params, return some data from simulated_data_source
        # This is a very simplified mock:
        if "component_A" in endpoint:
            return self.simulated_data_source["component_A"]
        if "component_B" in endpoint:
            return self.simulated_data_source["component_B"]
        if "all" in endpoint:
            return self.simulated_data_source
        
        raise RegistryAccessError(f"Mock data not found for endpoint {endpoint}")

    def get_component_state(self, component_id: str, at_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        logger.info(f"MockLiveClient: get_component_state for {component_id}")
        self.fail_count = 0 # Reset fail count for each new top-level call
        try:
            # Construct a dummy endpoint string for the mock
            data = self._fetch_from_registry(endpoint=f"/components/{component_id}")
            return data
        except KFMVerifierError as e: # Catch specific app errors from retries
            logger.error(f"MockLiveClient: Failed to get state for {component_id} after retries: {e}")
            return None
        except Exception as e: # Catch any other unexpected error
            logger.error(f"MockLiveClient: Unexpected error for {component_id}: {e}", exc_info=True)
            return None

    def get_all_components_state(self, at_time: Optional[datetime] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        logger.info(f"MockLiveClient: get_all_components_state")
        self.fail_count = 0 # Reset fail count
        try:
            data = self._fetch_from_registry(endpoint="/components/all")
            # Ensure it returns the expected structure if _fetch_from_registry returns a dict of dicts
            if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                return data
            logger.error("MockLiveClient: _fetch_from_registry for all components returned unexpected data structure.")
            return None
        except KFMVerifierError as e:
            logger.error(f"MockLiveClient: Failed to get all states after retries: {e}")
            return None
        except Exception as e:
            logger.error(f"MockLiveClient: Unexpected error for get_all_components_state: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    # Setup basic logging for the __main__ test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    main_test_logger = logging.getLogger("__main__")

    main_test_logger.info("--- Testing MockLiveComponentRegistryClient with Retry --- ")
    
    # Test 1: Component A, should succeed after retries
    main_test_logger.info("\nTest 1: Get Component A (simulating 2 failures then success)")
    # To use config-based retries, get_config() needs to be available and configured.
    # For this test, the decorator has max_attempts=3 hardcoded.
    # If we relied on global config, we'd mock get_config() here as in resilience.py's __main__
    client_config_test1 = {"mock_max_failures": 2} 
    mock_live_client_test1 = MockLiveComponentRegistryClient(config=client_config_test1)
    state_A = mock_live_client_test1.get_component_state("component_A")
    if state_A:
        main_test_logger.info(f"Test 1 Component A state: {state_A}")
        assert state_A["status"] == "active"
    else:
        main_test_logger.error("Test 1 Failed to get Component A state")

    # Test 2: Component B, make it fail more than retry attempts
    main_test_logger.info("\nTest 2: Get Component B (simulating 3 failures, max_attempts=3, should fail)")
    client_config_test2 = {"mock_max_failures": 3} # Will fail 3 times, decorator retries up to 3 attempts total
    mock_live_client_test2 = MockLiveComponentRegistryClient(config=client_config_test2)
    state_B = mock_live_client_test2.get_component_state("component_B")
    if state_B:
        main_test_logger.error(f"Test 2 Component B state (UNEXPECTED SUCCESS): {state_B}")
    else:
        main_test_logger.info("Test 2 Correctly failed to get Component B state after all retries.")
        assert state_B is None

    # Test 3: Get all components
    main_test_logger.info("\nTest 3: Get All Components (simulating 1 failure then success)")
    client_config_test3 = {"mock_max_failures": 1}
    mock_live_client_test3 = MockLiveComponentRegistryClient(config=client_config_test3)
    all_states = mock_live_client_test3.get_all_components_state()
    if all_states:
        main_test_logger.info(f"Test 3 All states: {all_states}")
        assert "component_A" in all_states and "component_B" in all_states
    else:
        main_test_logger.error("Test 3 Failed to get all component states")

    main_test_logger.info("\nRegistry client retry tests finished.") 