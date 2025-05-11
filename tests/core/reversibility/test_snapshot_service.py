import pytest
import pytest_asyncio
import asyncio
import time
import uuid
from typing import Optional, Dict, Any, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.reversibility.snapshot_service import SnapshotService, SnapshotServiceError as ServiceError
from src.core.reversibility.snapshot_storage_interface import (
    SnapshotStorageInterface, 
    SnapshotManifest, 
    ChunkReference,
    SnapshotStorageError
)

# Mock KFMAgentState for testing purposes if the actual class is complex or has many dependencies
# If KFMAgentState is a Pydantic model, we can mock its .model_dump_json() method.
class MockKFMAgentStatePydantic:
    def __init__(self, data_dict):
        self.data_dict = data_dict

    def model_dump_json(self, indent=None):
        import json
        return json.dumps(self.data_dict, indent=indent)

@pytest_asyncio.fixture
async def mock_snapshot_storage() -> AsyncMock:
    """Provides an AsyncMock for SnapshotStorageInterface."""
    mock = AsyncMock(spec=SnapshotStorageInterface)
    
    async def mock_store_manifest(snapshot_id, data_to_snapshot, snapshot_metadata):
        return SnapshotManifest(
            snapshot_id=snapshot_id,
            timestamp=snapshot_metadata.get('snapshot_creation_timestamp', time.time()),
            metadata=snapshot_metadata,
            chunks=[],
            total_original_size=len(data_to_snapshot) 
        )
    mock.store_snapshot_manifest.side_effect = mock_store_manifest
    return mock

@pytest_asyncio.fixture
async def snapshot_service(mock_snapshot_storage: AsyncMock) -> SnapshotService:
    """Provides a SnapshotService instance with a mocked storage."""
    return SnapshotService(snapshot_storage=mock_snapshot_storage)

@pytest.mark.asyncio
async def test_take_snapshot_agent_state_only(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with only KFMAgentState (as dict)."""
    agent_state_dict = {"world": "state1", "cycle": 1}
    metadata_in = {"user": "test_user"}
    trigger = "manual_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_dict,
        metadata=metadata_in
    )

    assert manifest is not None
    assert manifest.snapshot_id.startswith(trigger.replace("_", "-"))
    assert manifest.metadata['trigger_event'] == trigger
    assert manifest.metadata['user'] == "test_user"
    assert manifest.metadata['kfm_agent_state_type'] == str(type(agent_state_dict))
    
    mock_snapshot_storage.store_snapshot_manifest.assert_called_once()
    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    
    assert kwargs['snapshot_id'] == manifest.snapshot_id
    import json
    expected_agent_bytes = json.dumps(agent_state_dict, indent=2).encode('utf-8')
    assert kwargs['data_to_snapshot'] == expected_agent_bytes
    assert kwargs['snapshot_metadata']['trigger_event'] == trigger

@pytest.mark.asyncio
async def test_take_snapshot_with_pydantic_agent_state(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with KFMAgentState as a Pydantic-like mock object."""
    agent_data = {"detail": "pydantic_model_data", "version": 2.0}
    pydantic_mock_state = MockKFMAgentStatePydantic(agent_data)
    metadata_in = {"source": "pydantic_test"}
    trigger = "pydantic_trigger"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=pydantic_mock_state,
        metadata=metadata_in
    )

    assert manifest is not None
    assert manifest.metadata['kfm_agent_state_type'] == str(type(pydantic_mock_state))

    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    expected_agent_bytes = pydantic_mock_state.model_dump_json(indent=2).encode('utf-8')
    assert kwargs['data_to_snapshot'] == expected_agent_bytes

@pytest.mark.asyncio
async def test_take_snapshot_agent_state_str(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with KFMAgentState as a string."""
    agent_state_str = "Simple string agent state"
    metadata_in = {"format": "string"}
    trigger = "str_state_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_str,
        metadata=metadata_in
    )
    assert manifest is not None
    assert manifest.metadata['kfm_agent_state_type'] == str(type(agent_state_str))
    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    assert kwargs['data_to_snapshot'] == agent_state_str.encode('utf-8')

@pytest.mark.asyncio
async def test_take_snapshot_agent_state_bytes(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with KFMAgentState as bytes."""
    agent_state_bytes = b"Binary agent state data"
    metadata_in = {"encoding": "binary"}
    trigger = "bytes_state_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_bytes,
        metadata=metadata_in
    )
    assert manifest is not None
    assert manifest.metadata['kfm_agent_state_type'] == str(type(agent_state_bytes))
    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    assert kwargs['data_to_snapshot'] == agent_state_bytes

@pytest.mark.asyncio
async def test_take_snapshot_with_direct_component_state(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with KFMAgentState and direct_component_state_data."""
    agent_state_dict = {"world": "state2"}
    component_state_bytes = b"component_X_data_direct"
    metadata_in = {"component_id": "compX"}
    trigger = "direct_comp_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_dict,
        metadata=metadata_in,
        direct_component_state_data=component_state_bytes,
        target_component_id="compX" # Provide for metadata, though adapter won't be called
    )

    assert manifest is not None
    assert manifest.metadata['component_id'] == "compX"
    assert manifest.metadata['component_state_source'] == 'direct_input'
    
    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    import json
    expected_agent_bytes = json.dumps(agent_state_dict, indent=2).encode('utf-8')
    expected_combined_data = expected_agent_bytes + b"\n---COMPONENT_SEPARATOR---\n" + component_state_bytes
    assert kwargs['data_to_snapshot'] == expected_combined_data

@pytest.mark.asyncio
@patch('src.core.reversibility.snapshot_service.SnapshotService._get_component_state_via_adapter', new_callable=AsyncMock)
async def test_take_snapshot_with_adapter_component_state(mock_get_state_adapter: AsyncMock, snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test take_snapshot with KFMAgentState and component state fetched via mocked adapter."""
    agent_state_dict = {"world": "state3"}
    component_id = "compY"
    component_type = "typeZ"
    adapter_fetched_state = b"component_Y_data_from_adapter"
    mock_get_state_adapter.return_value = adapter_fetched_state
    
    metadata_in = {"scenario": "adapter_fetch"}
    trigger = "adapter_comp_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_dict,
        metadata=metadata_in,
        target_component_id=component_id,
        target_component_type=component_type
    )

    assert manifest is not None
    mock_get_state_adapter.assert_called_once_with(component_id, component_type)
    assert manifest.metadata['scenario'] == "adapter_fetch"
    assert manifest.metadata['target_component_id'] == component_id
    assert manifest.metadata['target_component_type'] == component_type
    assert manifest.metadata['component_state_source'] == 'adapter_registry'

    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    import json
    expected_agent_bytes = json.dumps(agent_state_dict, indent=2).encode('utf-8')
    expected_combined_data = expected_agent_bytes + b"\n---COMPONENT_SEPARATOR---\n" + adapter_fetched_state
    assert kwargs['data_to_snapshot'] == expected_combined_data

@pytest.mark.asyncio
@patch('src.core.reversibility.snapshot_service.SnapshotService._get_component_state_via_adapter', new_callable=AsyncMock)
async def test_take_snapshot_adapter_returns_none(mock_get_state_adapter: AsyncMock, snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test when adapter for component state returns None."""
    mock_get_state_adapter.return_value = None
    agent_state_dict = {"world": "state_adapter_none"}
    trigger = "adapter_none_test"

    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=agent_state_dict,
        metadata={},
        target_component_id="compZ"
    )
    assert manifest is not None # Should still snapshot agent state
    assert 'component_state_warning' in manifest.metadata
    mock_get_state_adapter.assert_called_once()
    
    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    import json
    expected_agent_bytes = json.dumps(agent_state_dict, indent=2).encode('utf-8')
    # Only agent state should be in the snapshot data as component state was None
    assert kwargs['data_to_snapshot'] == expected_agent_bytes

@pytest.mark.asyncio
async def test_take_snapshot_id_generation(snapshot_service: SnapshotService):
    """Test snapshot ID generation variations."""
    agent_state = "test"
    trigger = "id_gen_test"
    expected_base_id1 = trigger.lower().replace("_", "-")
    
    manifest1 = await snapshot_service.take_snapshot(trigger, agent_state, {})
    assert manifest1 is not None
    assert manifest1.snapshot_id.startswith(expected_base_id1)
    
    parts1 = manifest1.snapshot_id.split('-')
    # Expected format: base-id-parts-UUID-timestamp
    # UUID itself has 4 hyphens, so it accounts for 5 parts.
    # Example: prefix-u1-u2-u3-u4-u5-ts (prefix can have hyphens)
    # We need to reconstruct the UUID from the parts that form it.
    # The UUID is located before the last part (timestamp).
    # The number of parts in the base_id can vary.
    num_base_id_parts = len(expected_base_id1.split('-'))
    uuid_parts_from_snapshot = parts1[num_base_id_parts:-1] # All parts between base_id and timestamp
    extracted_uuid_str = "-".join(uuid_parts_from_snapshot)
    assert len(extracted_uuid_str) == 36 # Standard UUID string length with hyphens
    assert str(uuid.UUID(extracted_uuid_str)) == extracted_uuid_str # Check if it's a valid UUID

    custom_prefix = "my-snap-prefix" # Using a prefix with hyphens to test splitting
    manifest2 = await snapshot_service.take_snapshot(trigger, agent_state, {}, snapshot_id_prefix=custom_prefix)
    assert manifest2 is not None
    assert manifest2.snapshot_id.startswith(custom_prefix)
    
    parts2 = manifest2.snapshot_id.split('-')
    num_custom_prefix_parts = len(custom_prefix.split('-'))
    uuid_parts_from_snapshot2 = parts2[num_custom_prefix_parts:-1]
    extracted_uuid_str2 = "-".join(uuid_parts_from_snapshot2)
    assert len(extracted_uuid_str2) == 36
    assert str(uuid.UUID(extracted_uuid_str2)) == extracted_uuid_str2

@pytest.mark.asyncio
async def test_take_snapshot_storage_failure(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test that ServiceError is raised if storage.store_snapshot_manifest fails."""
    mock_snapshot_storage.store_snapshot_manifest.side_effect = SnapshotStorageError("Disk full")
    
    with pytest.raises(ServiceError, match="Storage operation failed.*Disk full"):
        await snapshot_service.take_snapshot("fail_test", "agent_data", {})

@pytest.mark.asyncio
async def test_take_snapshot_agent_state_serialization_failure_fallback(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test fallback serialization if KFMAgentState is an unhandled complex type."""
    class UnserializableObject:
        def __str__(self):
            return "UnserializableObjectInstance"
    
    unserializable_state = UnserializableObject()
    trigger = "serialize_fallback_test"
    manifest = await snapshot_service.take_snapshot(trigger, unserializable_state, {})

    assert manifest is not None
    assert manifest.metadata['kfm_agent_state_type'] == str(type(unserializable_state))
    assert 'kfm_agent_state_error' not in manifest.metadata # Fallback to str() doesn't populate this error

    args, kwargs = mock_snapshot_storage.store_snapshot_manifest.call_args
    expected_bytes = str(unserializable_state).encode('utf-8')
    assert kwargs['data_to_snapshot'] == expected_bytes

@pytest.mark.asyncio
async def test_take_snapshot_no_data_at_all(snapshot_service: SnapshotService, mock_snapshot_storage: AsyncMock):
    """Test scenario where KFMAgentState serialization fails AND no component data is available."""
    # To simulate KFMAgentState serialization failure that prevents data from being added to combined_data_parts,
    # we can patch the serialization part to raise an exception and ensure no component data is passed.
    
    # For this test, we'll make the KFMAgentState an object that causes an error *before* str() fallback
    # by mocking its model_dump_json to raise an error.
    faulty_agent_state = MagicMock(spec=MockKFMAgentStatePydantic) # Use MagicMock to mock methods
    faulty_agent_state.model_dump_json.side_effect = TypeError("Simulated serialization error")
    # Ensure it doesn't fall into other isinstance checks before the hasattr check
    cast(MagicMock, faulty_agent_state).__class__ = MockKFMAgentStatePydantic # Make it look like our pydantic mock

    trigger = "no_data_test"
    manifest = await snapshot_service.take_snapshot(
        trigger_event=trigger,
        kfm_agent_state=faulty_agent_state,
        metadata={},
        target_component_id=None, # Ensure no adapter call
        direct_component_state_data=None # Ensure no direct data
    )

    assert manifest is None # Expect None because no data could be gathered
    mock_snapshot_storage.store_snapshot_manifest.assert_not_called() 