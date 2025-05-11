import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.reversibility.reversal_manager import ReversalManager
from src.core.reversibility.snapshot_service import SnapshotService
from src.core.reversibility.snapshot_storage_interface import SnapshotManifest, SnapshotStorageInterface
from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage
from src.state_types import KFMAgentState
from src.core.agent_lifecycle_controller import AgentLifecycleController


@pytest.fixture
def mock_snapshot_service():
    service = MagicMock(spec=SnapshotService)
    storage_mock = MagicMock(spec=FileSnapshotStorage)
    storage_mock.list_snapshot_manifest_ids = AsyncMock()
    storage_mock.get_snapshot_manifest = AsyncMock()
    service.storage_backend = storage_mock
    
    service.load_snapshot_agent_state_data = AsyncMock()
    return service

@pytest.fixture
def mock_agent_lifecycle_controller():
    controller = MagicMock(spec=AgentLifecycleController)
    controller.stop_current_run = AsyncMock()
    controller.prepare_for_new_run_with_state = AsyncMock()
    controller.start_new_run = AsyncMock()
    return controller

@pytest.fixture
def reversal_manager(mock_snapshot_service, mock_agent_lifecycle_controller):
    return ReversalManager(snapshot_service=mock_snapshot_service, kfm_agent_instance=mock_agent_lifecycle_controller)

@pytest.mark.asyncio
async def test_example_placeholder():
    # This is a placeholder to ensure the file is created and fixtures can be resolved
    assert True

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_found(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_123"
    snapshot_ids = ["snap1", "snap2_fuck", "snap3"]
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = snapshot_ids
    
    manifest1 = SnapshotManifest(snapshot_id="snap1", timestamp=100.0, metadata={}, chunks=[], total_original_size=0)
    manifest2_fuck = SnapshotManifest(
        snapshot_id="snap2_fuck", 
        timestamp=200.0, 
        metadata={
            "original_correlation_id": corr_id,
            "trigger_event": "decision_post_planner",
            "kfm_action_details": {"action": "Fuck"}
        }, 
        chunks=[], 
        total_original_size=0
    )
    manifest3 = SnapshotManifest(snapshot_id="snap3", timestamp=300.0, metadata={}, chunks=[], total_original_size=0)

    async def get_manifest_side_effect(s_id):
        if s_id == "snap1": return manifest1
        if s_id == "snap2_fuck": return manifest2_fuck
        if s_id == "snap3": return manifest3
        return None
    mock_snapshot_service.storage_backend.get_snapshot_manifest.side_effect = get_manifest_side_effect
    
    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id == "snap2_fuck"
    mock_snapshot_service.storage_backend.list_snapshot_manifests.assert_called_once()
    assert mock_snapshot_service.storage_backend.get_snapshot_manifest.call_count >= 1 

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_found_with_is_fuck_action_flag(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_456"
    snapshot_ids = ["snap_A", "snap_B_fuck_flag"]
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = snapshot_ids
    
    manifest_A = SnapshotManifest(snapshot_id="snap_A", timestamp=100.0, metadata={}, chunks=[], total_original_size=0)
    manifest_B_fuck_flag = SnapshotManifest(
        snapshot_id="snap_B_fuck_flag", 
        timestamp=200.0, 
        metadata={
            "original_correlation_id": corr_id,
            "is_fuck_action_pre_snapshot": True
        }, 
        chunks=[], 
        total_original_size=0
    )

    async def get_manifest_side_effect(s_id):
        if s_id == "snap_A": return manifest_A
        if s_id == "snap_B_fuck_flag": return manifest_B_fuck_flag
        return None
    mock_snapshot_service.storage_backend.get_snapshot_manifest.side_effect = get_manifest_side_effect
    
    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id == "snap_B_fuck_flag"

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_not_found_no_match(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_no_match"
    snapshot_ids = ["snap_X", "snap_Y"]
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = snapshot_ids
    
    manifest_X = SnapshotManifest(snapshot_id="snap_X", timestamp=100.0, metadata={"original_correlation_id": "other_id"}, chunks=[], total_original_size=0)
    manifest_Y = SnapshotManifest(snapshot_id="snap_Y", timestamp=200.0, metadata={"original_correlation_id": corr_id, "kfm_action_details": {"action": "Kill"}}, chunks=[], total_original_size=0)

    async def get_manifest_side_effect(s_id):
        if s_id == "snap_X": return manifest_X
        if s_id == "snap_Y": return manifest_Y
        return None
    mock_snapshot_service.storage_backend.get_snapshot_manifest.side_effect = get_manifest_side_effect

    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id is None

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_empty_manifests(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_empty"
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = []
    
    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id is None
    mock_snapshot_service.storage_backend.get_snapshot_manifest.assert_not_called()

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_manifest_load_fails(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_load_fail"
    snapshot_ids = ["snap_Z"]
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = snapshot_ids
    mock_snapshot_service.storage_backend.get_snapshot_manifest.return_value = None # Simulate manifest not found or load error

    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id is None

@pytest.mark.asyncio
async def test_identify_pre_fuck_action_snapshot_id_multiple_matches_returns_latest(reversal_manager, mock_snapshot_service):
    corr_id = "test_corr_id_multi"
    snapshot_ids = ["snap_early_fuck", "snap_other", "snap_late_fuck"]
    mock_snapshot_service.storage_backend.list_snapshot_manifests.return_value = snapshot_ids

    manifest_early = SnapshotManifest(
        snapshot_id="snap_early_fuck", timestamp=100.0, 
        metadata={"original_correlation_id": corr_id, "trigger_event": "decision_post_planner", "kfm_action_details": {"action": "Fuck"}}, 
        chunks=[], total_original_size=0
    )
    manifest_other = SnapshotManifest(snapshot_id="snap_other", timestamp=150.0, metadata={}, chunks=[], total_original_size=0)
    manifest_late = SnapshotManifest(
        snapshot_id="snap_late_fuck", timestamp=200.0, 
        metadata={"original_correlation_id": corr_id, "is_fuck_action_pre_snapshot": True}, 
        chunks=[], total_original_size=0
    )

    async def get_manifest_side_effect(s_id):
        if s_id == "snap_early_fuck": return manifest_early
        if s_id == "snap_other": return manifest_other
        if s_id == "snap_late_fuck": return manifest_late
        return None
    mock_snapshot_service.storage_backend.get_snapshot_manifest.side_effect = get_manifest_side_effect
    
    found_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(corr_id)
    assert found_id == "snap_late_fuck"

@pytest.mark.asyncio
async def test_revert_last_fuck_action_success(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    corr_id = "test_corr_id_revert_success"
    target_snapshot_id = "pre_fuck_snap_for_revert"
    
    reversal_manager.identify_pre_fuck_action_snapshot_id = AsyncMock(return_value=target_snapshot_id)
    
    mock_kfm_agent_state = MagicMock(spec=KFMAgentState)
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = mock_kfm_agent_state
    
    result = await reversal_manager.revert_last_fuck_action(corr_id)
    
    assert result["success"] is True
    assert result["message"] == f"Reversal to snapshot {target_snapshot_id} initiated. Agent restarting with restored state."

@pytest.mark.asyncio
async def test_revert_last_fuck_action_snapshot_not_identified(reversal_manager):
    corr_id = "test_corr_id_revert_not_found"
    reversal_manager.identify_pre_fuck_action_snapshot_id = AsyncMock(return_value=None)

    result = await reversal_manager.revert_last_fuck_action(corr_id)

    assert result["success"] is False
    assert "Could not identify a pre-Fuck action snapshot" in result["error"]
    reversal_manager.identify_pre_fuck_action_snapshot_id.assert_awaited_once_with(corr_id)

@pytest.mark.asyncio
async def test_revert_to_snapshot_success(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    snapshot_id = "any_snapshot_id"
    mock_kfm_agent_state = MagicMock(spec=KFMAgentState)
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = mock_kfm_agent_state
    
    result = await reversal_manager.revert_to_snapshot(snapshot_id)
    
    assert result["success"] is True
    assert result["message"] == f"Reversal to snapshot {snapshot_id} initiated. Agent restarting with restored state."

@pytest.mark.asyncio
async def test_revert_to_snapshot_load_fails(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    snapshot_id = "snap_load_fail"
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = None

    result = await reversal_manager.revert_to_snapshot(snapshot_id)

    assert result["success"] is False
    assert "not found or failed to load" in result["error"]
    mock_snapshot_service.load_snapshot_agent_state_data.assert_awaited_once_with(snapshot_id)
    mock_agent_lifecycle_controller.stop_current_run.assert_not_awaited() # Should not proceed to agent control

@pytest.mark.asyncio
async def test_revert_to_snapshot_agent_stop_fails(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    snapshot_id = "snap_stop_fail"
    mock_kfm_agent_state = MagicMock(spec=KFMAgentState)
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = mock_kfm_agent_state
    mock_agent_lifecycle_controller.stop_current_run.side_effect = RuntimeError("Agent stop failed")

    result = await reversal_manager.revert_to_snapshot(snapshot_id)

    assert result["success"] is False
    assert "Agent stop failed" in result["error"]
    mock_snapshot_service.load_snapshot_agent_state_data.assert_awaited_once_with(snapshot_id)
    mock_agent_lifecycle_controller.stop_current_run.assert_awaited_once()
    mock_agent_lifecycle_controller.prepare_for_new_run_with_state.assert_not_awaited()

@pytest.mark.asyncio
async def test_revert_to_snapshot_agent_prepare_fails(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    snapshot_id = "snap_prepare_fail"
    mock_kfm_agent_state = MagicMock(spec=KFMAgentState)
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = mock_kfm_agent_state
    mock_agent_lifecycle_controller.prepare_for_new_run_with_state.side_effect = RuntimeError("Agent prepare failed")

    result = await reversal_manager.revert_to_snapshot(snapshot_id)

    assert result["success"] is False
    assert "Agent prepare failed" in result["error"]
    mock_snapshot_service.load_snapshot_agent_state_data.assert_awaited_once_with(snapshot_id)
    mock_agent_lifecycle_controller.stop_current_run.assert_awaited_once()
    mock_agent_lifecycle_controller.prepare_for_new_run_with_state.assert_awaited_once_with(mock_kfm_agent_state)
    mock_agent_lifecycle_controller.start_new_run.assert_not_awaited()

@pytest.mark.asyncio
async def test_revert_to_snapshot_agent_start_fails(reversal_manager, mock_snapshot_service, mock_agent_lifecycle_controller):
    snapshot_id = "snap_start_fail"
    mock_kfm_agent_state = MagicMock(spec=KFMAgentState)
    mock_snapshot_service.load_snapshot_agent_state_data.return_value = mock_kfm_agent_state
    mock_agent_lifecycle_controller.start_new_run.side_effect = RuntimeError("Agent start failed")

    result = await reversal_manager.revert_to_snapshot(snapshot_id)

    assert result["success"] is False
    assert "Agent start failed" in result["error"]
    mock_snapshot_service.load_snapshot_agent_state_data.assert_awaited_once_with(snapshot_id)
    mock_agent_lifecycle_controller.stop_current_run.assert_awaited_once()
    mock_agent_lifecycle_controller.prepare_for_new_run_with_state.assert_awaited_once_with(mock_kfm_agent_state)
    mock_agent_lifecycle_controller.start_new_run.assert_awaited_once() 