import asyncio
import time
import uuid
import json
from typing import Optional, Dict, Any, List, Union

# Assuming KFMAgentState will be defined elsewhere and can be imported
# from ...somewhere import KFMAgentState # Placeholder
# For now, using Any as a type hint for kfm_agent_state
# KFMAgentState = Any 
from src.state_types import KFMAgentState # Import the actual KFMAgentState

from .snapshot_storage_interface import SnapshotStorageInterface, SnapshotManifest, ChunkReference
# from .state_adapter_registry import StateAdapterRegistry # To be implemented in 62.4

# Constant for the current agent state schema version
CURRENT_AGENT_STATE_SCHEMA_VERSION = "kfm_agent_state_v1.0"

class SnapshotServiceError(Exception):
    """Custom exception for errors within the SnapshotService."""
    pass

class SnapshotService:
    """
    Service responsible for orchestrating the creation and management of state snapshots.
    It uses a SnapshotStorageInterface for persistence and will use a
    StateAdapterRegistry for fetching component-specific states.
    """

    def __init__(
        self,
        snapshot_storage: SnapshotStorageInterface,
        # state_adapter_registry: StateAdapterRegistry # Uncomment when 62.4 is done
    ):
        self.storage = snapshot_storage
        # self.adapter_registry = state_adapter_registry # Uncomment when 62.4 is done
        # For now, component state fetching is a placeholder
        print(f"SnapshotService initialized with storage: {type(snapshot_storage).__name__}")


    async def _get_component_state_via_adapter(
        self,
        component_id: str,
        component_type: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Placeholder for fetching component-specific state using the StateAdapterRegistry.
        This will be fully implemented as part of Subtask 62.4.
        """
        # if not self.adapter_registry:
        #     print(f"Warning: StateAdapterRegistry not available in SnapshotService. Cannot fetch component state for {component_id}.")
        #     return None
        # try:
        #     return await self.adapter_registry.get_component_state(component_id, component_type)
        # except Exception as e:
        #     print(f"Error fetching state for component {component_id} via adapter: {e}")
        #     return None
        print(f"Placeholder: _get_component_state_via_adapter called for {component_id} (type: {component_type}). Returning None as registry is not yet implemented.")
        return None


    async def take_snapshot(
        self,
        trigger: str,
        kfm_agent_state: Optional[KFMAgentState] = None,
        component_system_state: Optional[Dict[str, Any]] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
        custom_snapshot_id: Optional[str] = None
    ) -> Optional[str]: # Returns snapshot_id or None if failed
        """
        Takes a snapshot of the current state, including agent state and component system state.
        Delegates chunking, manifest creation, and storage to the configured storage backend.

        Args:
            trigger: The event or reason for taking the snapshot (e.g., 'pre_kfm_decision', 'post_fuck_action').
            kfm_agent_state: The current state of the KFM agent (e.g., its internal variables, decision context).
            component_system_state: The current state of relevant components or the broader system.
            additional_metadata: Any other custom metadata to include with the snapshot.
            custom_snapshot_id: Optional custom ID for the snapshot.

        Returns:
            Optional[str]: The ID of the created snapshot if successful, None otherwise.
        """
        snapshot_id = custom_snapshot_id or f"{trigger.replace(' ', '_').lower()}-{uuid.uuid4()}-{int(time.time())}"
        print(f"Attempting to take snapshot: {snapshot_id} triggered by: {trigger}")

        snapshot_metadata_dict = {
            "trigger": trigger,
            "timestamp_service_call": time.time(),
            "agent_state_schema_version": CURRENT_AGENT_STATE_SCHEMA_VERSION,
            **(additional_metadata or {})
        }

        # Consolidate data to be snapshot into a single structure
        # The storage backend will handle chunking this byte stream.
        # We need to ensure this combined_data can be reliably serialized to bytes.
        # JSON is a good candidate for this intermediate representation before bytes.
        combined_data_for_snapshot_dict = {
            "kfm_agent_state": kfm_agent_state,
            "component_system_state": component_system_state,
            "snapshot_metadata_from_service": snapshot_metadata_dict # Include service-level metadata here too
        }

        try:
            # Serialize the combined data dictionary to a JSON string, then encode to bytes
            final_data_to_snapshot_json = json.dumps(combined_data_for_snapshot_dict, default=str, sort_keys=True)
            final_data_to_snapshot_bytes = final_data_to_snapshot_json.encode('utf-8')
        except TypeError as e_serialize:
            print(f"Error serializing data for snapshot {snapshot_id}: {e_serialize}")
            # If serialization fails, we cannot proceed with snapshotting this data.
            # Log the error and potentially return None or raise a specific error.
            # For now, we'll print and then try to snapshot component_system_state if agent_state failed.
            # This part of the logic might need refinement based on how critical each part is.
            
            # Fallback: try to snapshot only component_system_state if kfm_agent_state serialization failed
            if component_system_state is not None:
                print(f"Fallback: Attempting to snapshot only component_system_state for {snapshot_id}")
                try:
                    component_state_json = json.dumps(component_system_state, default=str, sort_keys=True)
                    final_data_to_snapshot_bytes = component_state_json.encode('utf-8')
                    snapshot_metadata_dict["warning"] = "kfm_agent_state serialization failed; only component_system_state included."
                except TypeError as e_serialize_component:
                    print(f"Error serializing component_system_state for snapshot {snapshot_id} (fallback): {e_serialize_component}")
                    print(f"Error: No data available to snapshot for {snapshot_id}. KFMAgentState serialization failed and component_system_state also failed or was None.")
                    return None # Cannot proceed if all critical data fails to serialize
            else:
                print(f"Error: No data available to snapshot for {snapshot_id}. KFMAgentState serialization failed and no component data.")
                return None # Cannot proceed

        if not final_data_to_snapshot_bytes:
            print(f"Warning: No data serialized for snapshot {snapshot_id}. Skipping storage.")
            return None

        try:
            print(f"Storing manifest for snapshot {snapshot_id} (data length: {len(final_data_to_snapshot_bytes)} bytes) via storage interface.")
            
            # Delegate chunking, manifest creation, and storage to the backend
            # The backend's store_snapshot_manifest should handle everything from raw bytes.
            stored_manifest = await self.storage.store_snapshot_manifest(
                snapshot_id=snapshot_id,
                state_data=final_data_to_snapshot_bytes, # Pass raw bytes
                metadata=snapshot_metadata_dict         # Pass combined metadata
            )

            if stored_manifest:
                print(f"Successfully stored snapshot: {snapshot_id} with manifest details.") # Consider logging manifest.total_original_size
                return snapshot_id
            else:
                # This case should ideally not be reached if store_snapshot_manifest raises on failure as per interface intent.
                print(f"Warning: Storage backend reported successful call but returned no manifest for {snapshot_id}.")
                return None # Or snapshot_id if partial success is acceptable and logged by backend
        
        except SnapshotStorageError as sse:
            print(f"SnapshotStorageError for snapshot {snapshot_id}: {sse}")
            # This implies the storage backend itself had an issue (e.g., disk full, DB error)
            # Already logged by the storage layer, but we can log it here too.
            # No specific rollback needed here as the service layer didn't create partial state in storage.
            raise SnapshotServiceError(f"Storage operation failed for snapshot {snapshot_id}: {sse}") from sse
        except Exception as e_store:
            # Catch any other unexpected errors during the storage call
            print(f"Critical error storing snapshot {snapshot_id} via storage interface: {e_store}")
            raise SnapshotServiceError(f"Unexpected failure during storage of snapshot {snapshot_id}: {e_store}") from e_store

    async def load_snapshot_agent_state_data(self, snapshot_id: str) -> Optional[KFMAgentState]:
        """
        Loads the full KFM agent state data from a given snapshot ID.

        Args:
            snapshot_id: The ID of the snapshot to load data from.

        Returns:
            The KFMAgentState object if found and deserialized successfully, else None.
        """
        print(f"SnapshotService: Attempting to load agent state data for snapshot_id: {snapshot_id}")
        try:
            # Step 1: Get the raw bytes from the storage backend
            # This directly calls the method on the storage interface, assuming it's implemented.
            # For FileSnapshotStorage, this calls its get_snapshot_data method.
            raw_snapshot_data_bytes = await self.storage.get_snapshot_data(snapshot_id)
            if raw_snapshot_data_bytes is None:
                print(f"SnapshotService: No data returned by storage backend for snapshot {snapshot_id}.")
                return None

            # Step 2: Deserialize the bytes (decode UTF-8 then json.loads())
            try:
                snapshot_content_json_str = raw_snapshot_data_bytes.decode('utf-8')
                snapshot_content_dict = json.loads(snapshot_content_json_str)
            except (UnicodeDecodeError, json.JSONDecodeError) as e_deserialize:
                print(f"SnapshotService: Error deserializing snapshot content for {snapshot_id}: {e_deserialize}")
                raise SnapshotServiceError(f"Failed to deserialize snapshot data for {snapshot_id}") from e_deserialize

            # Step 3: Extract the kfm_agent_state part
            kfm_agent_state_from_snapshot = snapshot_content_dict.get("kfm_agent_state")
            if kfm_agent_state_from_snapshot is None:
                print(f"SnapshotService: 'kfm_agent_state' key not found in deserialized snapshot content for {snapshot_id}.")
                # This might be an old snapshot or one that only had component state.
                # Depending on policy, either return None or an empty/default KFMAgentState.
                return None 
            
            # Step 4: Reconstruct KFMAgentState if it's a Pydantic model or specific class
            # If KFMAgentState is a Pydantic model, use model_validate.
            # If it was stored as a simple dict and is expected as such, this step might be simpler.
            try:
                # This assumes KFMAgentState has a .model_validate() class method (Pydantic V2)
                # or similar parsing mechanism if it's another class.
                # If KFMAgentState is just `Any` or expected to be a dict, this might just be:
                # reconstructed_agent_state = kfm_agent_state_from_snapshot
                if isinstance(kfm_agent_state_from_snapshot, dict) and hasattr(KFMAgentState, 'model_validate'):
                    reconstructed_agent_state = KFMAgentState.model_validate(kfm_agent_state_from_snapshot)
                    print(f"SnapshotService: Successfully loaded and reconstructed KFMAgentState for snapshot {snapshot_id}.")
                    return reconstructed_agent_state
                elif isinstance(kfm_agent_state_from_snapshot, dict):
                     # If it's a dict and KFMAgentState is not strictly Pydantic or no model_validate, return as dict
                    print(f"SnapshotService: Loaded kfm_agent_state as dict for snapshot {snapshot_id} (KFMAgentState type might not be Pydantic or lacks model_validate).")
                    return kfm_agent_state_from_snapshot # type: ignore
                else:
                    # This case might occur if kfm_agent_state_from_snapshot is not a dict (e.g. was stored as a primitive)
                    # Or if KFMAgentState is a Pydantic model but the stored data is not a dict suitable for model_validate
                    print(f"SnapshotService: kfm_agent_state_from_snapshot is not a dict or KFMAgentState structure mismatch for {snapshot_id}. Type: {type(kfm_agent_state_from_snapshot)}")
                    # Potentially try to coerce or return as is if KFMAgentState allows it.
                    # For safety, if it's not a dict and we expect to reconstruct an object, this might be an issue.
                    return kfm_agent_state_from_snapshot # This might need KFMAgentState = Any for type checker if it's not a dict

            except Exception as e_reconstruct: # Broad exception for reconstruction issues (e.g. Pydantic validation error)
                print(f"SnapshotService: Error reconstructing KFMAgentState from snapshot {snapshot_id}: {e_reconstruct}")
                raise SnapshotServiceError(f"Failed to reconstruct KFMAgentState for {snapshot_id}") from e_reconstruct

        except SnapshotNotFoundError:
            print(f"SnapshotService: Snapshot {snapshot_id} not found in storage backend.")
            return None
        except SnapshotStorageError as sse:
            print(f"SnapshotService: Storage error while loading snapshot {snapshot_id}: {sse}")
            # Re-raise or handle as per service policy
            raise
        except SnapshotServiceError: # Catch re-raised errors from deserialization/reconstruction
            raise
        except Exception as e_main:
            print(f"SnapshotService: Unexpected error loading agent state for snapshot {snapshot_id}: {e_main}")
            raise SnapshotServiceError(f"Unexpected error loading agent state for {snapshot_id}") from e_main

# Example Usage (Conceptual - requires a KFMAgentState mock and a SnapshotStorage mock/instance)
async def main_example():
    # Mock SnapshotStorage
    class MockSnapshotStorage(SnapshotStorageInterface):
        async def store_snapshot_manifest(self, snapshot_id: str, data_to_snapshot: bytes, snapshot_metadata: Dict[str, Any]) -> Optional[SnapshotManifest]:
            print(f"MockStorage: Storing manifest {snapshot_id}, data length {len(data_to_snapshot)}, metadata: {snapshot_metadata}")
            # Create a dummy manifest
            return SnapshotManifest(
                snapshot_id=snapshot_id,
                timestamp=time.time(),
                metadata=snapshot_metadata,
                chunks=[], # Simplified for mock
                total_original_size=len(data_to_snapshot)
            )
        # Implement other abstract methods as needed for a runnable mock, or mark with pass
        async def get_snapshot_manifest(self, snapshot_id: str) -> Optional[SnapshotManifest]: pass
        async def list_snapshot_manifests(self, component_id: Optional[str] = None, component_type: Optional[str] = None, timestamp_from: Optional[float] = None, timestamp_to: Optional[float] = None, tags: Optional[List[str]] = None, limit: int = 100, offset: int = 0) -> List[str]: pass # type: ignore
        async def delete_snapshot_manifest(self, snapshot_id: str) -> bool: pass
        async def get_snapshot_data(self, snapshot_id: str) -> Optional[bytes]: pass
        async def store_chunk(self, chunk_hash: str, chunk_data: bytes) -> None: pass
        async def get_chunk(self, chunk_hash: str) -> Optional[bytes]: pass
        async def chunk_exists(self, chunk_hash: str) -> bool: pass
        async def delete_chunk(self, chunk_hash: str) -> bool: pass
        async def increment_chunk_reference(self, chunk_hash: str) -> None: pass
        async def decrement_chunk_reference(self, chunk_hash: str) -> int: pass
        async def get_chunk_reference_count(self, chunk_hash: str) -> int: pass
        async def garbage_collect_orphaned_chunks(self, dry_run: bool = True) -> list[str]: pass
        def get_storage_overview(self) -> Dict[str, Any]: pass


    mock_storage = MockSnapshotStorage()
    # state_registry_mock = StateAdapterRegistry() # When available
    service = SnapshotService(snapshot_storage=mock_storage) #, state_adapter_registry=state_registry_mock)

    # Mock KFMAgentState (can be a simple dict for this example if KFMAgentState type is Any)
    mock_kfm_state = {
        "world_model": {"components": ["compA", "compB"]},
        "cycle_id": "run123",
        "current_observations": ["obs1", "obs2"]
    }
    
    # Example 1: Pre-decision snapshot
    print("\n--- Example 1: Pre-decision snapshot ---")
    manifest1 = await service.take_snapshot(
        trigger="pre_kfm_decision",
        kfm_agent_state=mock_kfm_state,
        component_system_state=mock_kfm_state,
        additional_metadata={
            "kfm_cycle_id": mock_kfm_state["cycle_id"],
            "description": "Snapshot before KFM planning starts"
        }
    )
    if manifest1:
        print(f"Manifest 1 created: {manifest1}")

    # Example 2: Pre-Fuck action snapshot for a specific component
    print("\n--- Example 2: Pre-Fuck action snapshot ---")
    # Let's assume component_system_state would be fetched by adapter or passed directly
    mock_component_A_state = b"This is the detailed state of component A before being 'Fucked'."
    manifest2 = await service.take_snapshot(
        trigger="pre_action_execution",
        kfm_agent_state=mock_kfm_state, # Could be a slightly updated state
        component_system_state=mock_kfm_state, # Pass the updated state
        additional_metadata={
            "kfm_cycle_id": mock_kfm_state["cycle_id"],
            "kfm_action": "Fuck",
            "target_component_id": "component_A",
            "description": "Snapshot of component_A just before 'Fuck' action"
        },
        custom_snapshot_id="pre-fuck-componentA"
    )
    if manifest2:
        print(f"Manifest 2 created: {manifest2}")

    # Example 3: Snapshot with only agent state (e.g., manual trigger)
    print("\n--- Example 3: Manual agent state snapshot ---")
    manifest3 = await service.take_snapshot(
        trigger="manual_agent_snapshot",
        kfm_agent_state=mock_kfm_state,
        component_system_state=mock_kfm_state,
        additional_metadata={
            "triggered_by": "user_admin",
            "reason": "Ad-hoc backup of agent state"
        }
    )
    if manifest3:
        print(f"Manifest 3 created: {manifest3}")

if __name__ == "__main__":
    asyncio.run(main_example()) 