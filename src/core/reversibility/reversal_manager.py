"""
Manages the explicit reversal of KFM agent states.
"""
from typing import Any, Dict, Optional, List
import asyncio
import os
import json # For loading manifest JSONs if not directly getting SnapshotManifest objects
from datetime import datetime # For comparing timestamps
from pydantic import BaseModel # Added for ReversalResult
import uuid

from src.core.reversibility.snapshot_service import SnapshotService, CURRENT_AGENT_STATE_SCHEMA_VERSION
from src.core.reversibility.snapshot_storage_interface import SnapshotManifest # For type hinting
from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage # For direct access if needed and for type checking
from src.logger import setup_logger
from src.state_types import KFMAgentState

reversal_logger = setup_logger(__name__)


class ReversalResult(BaseModel):
    success: bool
    message: Optional[str] = None
    snapshot_id_used: Optional[str] = None
    original_correlation_id_used: Optional[str] = None


class ReversalManager:
    """
    Handles the logic for reverting the KFM agent to a previous snapshot.
    """

    def __init__(self, snapshot_service: SnapshotService, lifecycle_controller: Any):
        """
        Initializes the ReversalManager.

        Args:
            snapshot_service: The SnapshotService instance for loading snapshots.
            lifecycle_controller: An instance of AgentLifecycleController.
        """
        self.snapshot_service = snapshot_service
        self.lifecycle_controller = lifecycle_controller
        reversal_logger.info("ReversalManager initialized.")

    async def revert_to_snapshot(self, snapshot_id: str) -> ReversalResult:
        """
        Reverts the KFM agent to the state defined in the specified snapshot.

        Args:
            snapshot_id: The ID of the snapshot to revert to.

        Returns:
            A ReversalResult object indicating success or failure.
        """
        reversal_logger.info(f"Attempting to revert to snapshot_id: {snapshot_id}")
        
        try:
            # Step 0: Retrieve the manifest to check metadata (including schema version)
            manifest = await self.snapshot_service.storage.get_snapshot_manifest(snapshot_id)
            if not manifest:
                reversal_logger.error(f"Snapshot manifest {snapshot_id} not found.")
                return ReversalResult(success=False, message=f"Snapshot manifest {snapshot_id} not found.", snapshot_id_used=snapshot_id)
            
            snapshot_schema_version = manifest.metadata.get("agent_state_schema_version")
            reversal_logger.info(f"Snapshot {snapshot_id} has schema version: {snapshot_schema_version}. Expected: {CURRENT_AGENT_STATE_SCHEMA_VERSION}")
            if snapshot_schema_version != CURRENT_AGENT_STATE_SCHEMA_VERSION:
                error_msg = f"Schema version mismatch for snapshot {snapshot_id}. Found: '{snapshot_schema_version}', Expected: '{CURRENT_AGENT_STATE_SCHEMA_VERSION}'. Reversal aborted."
                reversal_logger.error(error_msg)
                return ReversalResult(success=False, message=error_msg, snapshot_id_used=snapshot_id)
            
            # Step 1: Load agent state data from snapshot (now that schema version is validated)
            agent_state_data_to_restore = await self.snapshot_service.load_snapshot_agent_state_data(snapshot_id)
            if agent_state_data_to_restore is None:
                reversal_logger.error(f"Snapshot {snapshot_id} not found or failed to load agent state data.")
                return ReversalResult(success=False, message=f"Snapshot {snapshot_id} not found or failed to load.", snapshot_id_used=snapshot_id)
            
            reversal_logger.info(f"Successfully loaded agent state from snapshot {snapshot_id}. Type: {type(agent_state_data_to_restore)}")

            # Step 2: Stop current agent execution using AgentLifecycleController
            await self.lifecycle_controller.stop_current_run()
            reversal_logger.info("Commanded lifecycle_controller to stop current run.")

            # Step 3: Prepare for new run with restored state using AgentLifecycleController
            await self.lifecycle_controller.prepare_for_new_run_with_state(
                run_id=f"reversal_to_{snapshot_id[:12]}_{uuid.uuid4().hex[:8]}", 
                restored_state=KFMAgentState(**agent_state_data_to_restore) # Ensure it's KFMAgentState
            )
            reversal_logger.info(f"Prepared lifecycle_controller for new run with state from snapshot {snapshot_id}.")

            # Step 4: Restart agent execution with the restored state using AgentLifecycleController
            # The start_new_run method in AgentLifecycleController does not require initial_state if it was prepared.
            result_from_run = await self.lifecycle_controller.start_new_run(initial_state=KFMAgentState(**agent_state_data_to_restore))
            
            if result_from_run and result_from_run.get("error") is None:
                reversal_logger.info(f"Agent run after reverting to snapshot {snapshot_id} completed successfully.")
                return ReversalResult(success=True, message=f"Reversal to snapshot {snapshot_id} initiated. Agent restarting with restored state.", snapshot_id_used=snapshot_id)
            else:
                reversal_logger.warning(f"Agent run after reversal to snapshot {snapshot_id} failed: {result_from_run.get('error')}")
                return ReversalResult(success=False, message=f"Agent run after reversal failed: {result_from_run.get('error')}. Snapshot ID: {snapshot_id}", snapshot_id_used=snapshot_id)

        except Exception as e:
            reversal_logger.exception(f"Error during revert_to_snapshot for {snapshot_id}: {e}")
            return ReversalResult(success=False, message=f"Reversal process failed: {str(e)}", snapshot_id_used=snapshot_id)

    async def identify_pre_fuck_action_snapshot_id(self, original_correlation_id: str) -> Optional[str]:
        """
        Identifies the snapshot ID taken just before a 'Fuck' action was executed,
        based on the original correlation ID of that execution flow.

        Args:
            original_correlation_id: The correlation_id of the agent run where the 'Fuck' action occurred.

        Returns:
            The snapshot_id if found, otherwise None.
        """
        reversal_logger.info(f"Attempting to identify pre-Fuck action snapshot for original_correlation_id: {original_correlation_id}")
        
        # Ensure the storage backend is FileSnapshotStorage to access manifests_path directly
        # This is a bit of a hack; ideally SnapshotService would provide a better query mechanism.
        storage_backend = self.snapshot_service.storage
        if not isinstance(storage_backend, FileSnapshotStorage):
            reversal_logger.error("ReversalManager currently only supports FileSnapshotStorage for identifying specific snapshots by metadata.")
            return None

        matching_manifests: List[SnapshotManifest] = []
        try:
            manifest_ids: Optional[List[str]] = None
            try:
                reversal_logger.debug(f"About to call storage_backend.list_snapshot_manifests for {storage_backend}")
                manifest_ids = await storage_backend.list_snapshot_manifests(limit=10000) 
                reversal_logger.debug(f"Found {len(manifest_ids) if manifest_ids else 0} total manifest IDs to check: {manifest_ids}")
            except Exception as e_list:
                reversal_logger.error(f"Exception during storage_backend.list_snapshot_manifests: {e_list}", exc_info=True)
                return None # Cannot proceed if listing fails

            if not manifest_ids:
                reversal_logger.info(f"No manifest IDs returned by storage_backend.list_snapshot_manifests for correlation_id: {original_correlation_id}")
                return None

            for manifest_id in manifest_ids:
                try:
                    manifest = await storage_backend.get_snapshot_manifest(manifest_id)
                    if not manifest: # Ensure manifest is loaded
                        reversal_logger.warning(f"Could not load manifest for ID: {manifest_id}. Skipping.")
                        continue

                    # Access metadata directly from manifest.metadata
                    actual_agent_run_id = manifest.metadata.get("original_correlation_id")
                    
                    # Check for style 1: trigger_event and kfm_action_details
                    is_pre_fuck_event_style1 = (
                        manifest.metadata.get("trigger_event") == "decision_post_planner" and # As set in kfm_decision_node
                        isinstance(manifest.metadata.get("kfm_action_details"), dict) and
                        manifest.metadata["kfm_action_details"].get("action") == "Fuck"
                    )
                    
                    # Check for style 2: explicit boolean flag
                    is_pre_fuck_tag_style2 = manifest.metadata.get("is_fuck_action_pre_snapshot") is True
                    
                    # DEBUG LOGGING:
                    reversal_logger.debug(f"Checking manifest {manifest_id}: corr_id_match? {actual_agent_run_id == original_correlation_id} (actual: {actual_agent_run_id}, expected: {original_correlation_id}), style1? {is_pre_fuck_event_style1}, style2? {is_pre_fuck_tag_style2}")
                    reversal_logger.debug(f"  Manifest metadata: {manifest.metadata}")

                    if actual_agent_run_id == original_correlation_id and (is_pre_fuck_event_style1 or is_pre_fuck_tag_style2):
                        matching_manifests.append(manifest)
                        reversal_logger.debug(f"Found matching pre-Fuck manifest: {manifest_id} with timestamp {manifest.timestamp}")
                except Exception as e:
                    reversal_logger.warning(f"Could not load or parse manifest {manifest_id} during search: {e}")
                    continue # Skip this manifest
            
            if not matching_manifests:
                reversal_logger.info(f"No pre-Fuck action snapshots found for correlation_id: {original_correlation_id}")
                return None

            # Sort by timestamp (string, ISO format, so direct sort should work for recency)
            # Convert to datetime for robust sorting if needed, but string sort often suffices for ISO.
            matching_manifests.sort(key=lambda m: m.timestamp, reverse=True)
            
            most_recent_manifest = matching_manifests[0]
            reversal_logger.info(f"Identified most recent pre-Fuck action snapshot: {most_recent_manifest.snapshot_id} (Timestamp: {most_recent_manifest.timestamp})")
            return most_recent_manifest.snapshot_id

        except Exception as e:
            reversal_logger.exception(f"Error while identifying pre-Fuck action snapshot: {e}")
            return None

    async def revert_last_fuck_action(self, original_correlation_id: str) -> ReversalResult:
        """
        Identifies the snapshot taken just before the last 'Fuck' action associated
        with the given original_correlation_id and attempts to revert to it.

        Args:
            original_correlation_id: The correlation ID of the agent run during which
                                     the 'Fuck' action occurred.

        Returns:
            A ReversalResult object indicating success or failure.
        """
        reversal_logger.info(f"Attempting to revert last 'Fuck' action for original_correlation_id: {original_correlation_id}")
        
        snapshot_id_to_revert = await self.identify_pre_fuck_action_snapshot_id(original_correlation_id)
        
        if snapshot_id_to_revert:
            reversal_logger.info(f"Identified pre-fuck action snapshot: {snapshot_id_to_revert} for correlation ID {original_correlation_id}. Proceeding with reversal.")
            # Pass original_correlation_id for clarity in result, though snapshot_id is primary
            reversal_outcome = await self.revert_to_snapshot(snapshot_id_to_revert)
            # Augment with original_correlation_id_used if it's not already part of revert_to_snapshot's direct result logic
            return ReversalResult(
                success=reversal_outcome.success,
                message=reversal_outcome.message,
                snapshot_id_used=reversal_outcome.snapshot_id_used,
                original_correlation_id_used=original_correlation_id
            )
        else:
            err_msg = f"Could not identify a pre-Fuck action snapshot for original_correlation_id: {original_correlation_id}"
            reversal_logger.error(err_msg)
            return ReversalResult(success=False, message=err_msg, original_correlation_id_used=original_correlation_id)

if __name__ == '__main__':
    # This is a placeholder for basic testing or demonstration
    # In a real scenario, you'd mock SnapshotService and kfm_agent_instance

    class MockSnapshotService:
        def __init__(self, storage_backend):
            self.storage_backend = storage_backend

        async def load_snapshot_agent_state(self, snapshot_id: str):
            print(f"[MockSnapshotService] load_snapshot_agent_state called for {snapshot_id}")
            if snapshot_id == "valid_pre_fuck_snap_id_001":
                # Simulate returning just the agent state part
                return {"task_name": "test_task", "kfm_action": {"action": "fuck", "component": "comp_X"}, "input": {"data": "some_input"}}
            return None

    class MockFileSnapshotStorage:
        def __init__(self, manifests_path_str: str):
            self.manifests_path = manifests_path_str # Not a Path object for this mock
            self.mock_manifests_data = {
                "snap_generic_001.json": SnapshotManifest(
                    snapshot_id="snap_generic_001", 
                    chunks=[], 
                    metadata={"trigger_metadata": {"agent_run_id": "corr_id_123", "trigger_event": "monitor_entry"}},
                    timestamp=datetime.utcnow().isoformat()
                ),
                "pre_fuck_snap_001.json": SnapshotManifest(
                    snapshot_id="valid_pre_fuck_snap_id_001", 
                    chunks=[], 
                    metadata={"trigger_metadata": {"agent_run_id": "corr_id_for_revert", "trigger_event": "decision_post_planner_pre_fuck", "is_fuck_action_pre_snapshot": True}},
                    timestamp=datetime(2023, 1, 1, 12, 0, 0).isoformat() # Older
                ),
                 "pre_fuck_snap_002.json": SnapshotManifest(
                    snapshot_id="valid_pre_fuck_snap_id_002", 
                    chunks=[], 
                    metadata={"trigger_metadata": {"agent_run_id": "corr_id_for_revert", "trigger_event": "decision_post_planner_pre_fuck"}},
                    timestamp=datetime(2023, 1, 1, 12, 5, 0).isoformat() # Newer
                )
            }

        async def list_snapshot_manifests(self, limit: int = 100, offset: int = 0) -> List[str]:
            print(f"[MockFileSnapshotStorage] list_snapshot_manifests called")
            ids = [name.replace(".json", "") for name in self.mock_manifests_data.keys()]
            return ids[offset:offset+limit]

        async def get_snapshot_manifest(self, snapshot_id: str) -> Optional[SnapshotManifest]:
            print(f"[MockFileSnapshotStorage] get_snapshot_manifest called for {snapshot_id}")
            return self.mock_manifests_data.get(f"{snapshot_id}.json")

    class MockKFMAgent:
        async def stop_current_run(self):
            print("[MockKFMAgent] stop_current_run called")
            await asyncio.sleep(0.01)

        async def reset_to_state(self, new_state_data: Dict):
            print(f"[MockKFMAgent] reset_to_state called with {new_state_data}")
            await asyncio.sleep(0.01)

        async def start_new_run(self, initial_state: Dict):
            print(f"[MockKFMAgent] start_new_run called with {initial_state}")
            await asyncio.sleep(0.01)

    async def main_test():
        print("Testing ReversalManager...")
        mock_file_storage = MockFileSnapshotStorage("./dummy_manifests")
        mock_snapshot_service = MockSnapshotService(storage_backend=mock_file_storage)
        mock_kfm_agent = MockKFMAgent()

        reversal_manager = ReversalManager(
            snapshot_service=mock_snapshot_service, # type: ignore
            lifecycle_controller=mock_kfm_agent
        )

        # Test identify pre-Fuck action snapshot
        print("\n--- Testing identify_pre_fuck_action_snapshot_id ---")
        snapshot_id_found = await reversal_manager.identify_pre_fuck_action_snapshot_id("corr_id_for_revert")
        print(f"Identified pre-Fuck action snapshot ID: {snapshot_id_found}")
        assert snapshot_id_found == "valid_pre_fuck_snap_id_002", f"Expected valid_pre_fuck_snap_id_002, got {snapshot_id_found}"
        
        snapshot_id_not_found = await reversal_manager.identify_pre_fuck_action_snapshot_id("corr_id_non_existent")
        print(f"Identified pre-Fuck action snapshot ID (non-existent correlation): {snapshot_id_not_found}")
        assert snapshot_id_not_found is None

        # Test revert_last_fuck_action
        print("\n--- Testing revert_last_fuck_action ---")
        result_revert_fuck = await reversal_manager.revert_last_fuck_action("corr_id_for_revert")
        print(f"Revert last fuck action result: {result_revert_fuck}")
        # This will now depend on the mock agent's start_new_run behavior
        assert result_revert_fuck.success # Expecting success if mock agent methods are called
        assert result_revert_fuck.snapshot_id_used == "valid_pre_fuck_snap_id_002"
        assert result_revert_fuck.original_correlation_id_used == "corr_id_for_revert"
        
        # Test revert_to_snapshot
        print("\n--- Testing revert_to_snapshot ---")
        result_revert_direct = await reversal_manager.revert_to_snapshot("valid_pre_fuck_snap_id_001")
        print(f"Revert to snapshot result: {result_revert_direct}")
        assert result_revert_direct.success # Expecting success
        assert result_revert_direct.snapshot_id_used == "valid_pre_fuck_snap_id_001"

    asyncio.run(main_test()) 