import pytest
import pytest_asyncio
import asyncio
import os
import shutil
from pathlib import Path

from src.core.reversibility.file_snapshot_storage import (
    FileSnapshotStorage, 
    SnapshotStorageError, 
    SnapshotNotFoundError,
    ChunkNotFoundError
)
from src.core.reversibility.snapshot_storage_interface import SnapshotManifest # For type hinting

# Define a temporary storage path for tests
TEST_STORAGE_BASE_PATH = "./tmp_pytest_snapshot_storage"

@pytest.fixture
def temp_storage_path():
    """Provides a clean temporary storage path for each test."""
    path = Path(TEST_STORAGE_BASE_PATH)
    if path.exists():
        shutil.rmtree(path) # Clean up from previous run if any
    path.mkdir(parents=True, exist_ok=True)
    yield str(path) # Provide the path to the test
    # Teardown: remove the directory after the test is done
    shutil.rmtree(path)

@pytest_asyncio.fixture
async def storage(temp_storage_path):
    """Provides an initialized FileSnapshotStorage instance."""
    return FileSnapshotStorage(base_storage_path=temp_storage_path)

@pytest.fixture
def sample_data_A():
    return b"Sample data for snapshot A, which is moderately long." * 200

@pytest.fixture
def sample_data_B():
    return b"Sample data for snapshot B, significantly different from A." * 250

@pytest.mark.asyncio
async def test_initialization(temp_storage_path):
    """Test that storage initializes correctly and creates directories."""
    storage_instance = FileSnapshotStorage(base_storage_path=temp_storage_path)
    assert Path(storage_instance.base_path).exists()
    assert Path(storage_instance.manifests_path).exists()
    assert Path(storage_instance.chunks_path).exists()
    assert Path(storage_instance._ref_counts_path).exists(), "Reference count file should be created"

@pytest.mark.asyncio
async def test_store_and_get_snapshot(storage: FileSnapshotStorage, sample_data_A):
    """Test storing a snapshot and then retrieving its manifest and data."""
    snapshot_id = "test_snap_001"
    metadata = {"component": "test_comp", "version": "1.0"}
    
    # Store
    stored_manifest = await storage.store_snapshot_manifest(snapshot_id, sample_data_A, metadata)
    assert stored_manifest is not None
    assert stored_manifest.snapshot_id == snapshot_id
    assert stored_manifest.metadata == metadata
    assert len(stored_manifest.chunks) > 0
    assert stored_manifest.total_original_size == len(sample_data_A)

    # Get Manifest
    retrieved_manifest = await storage.get_snapshot_manifest(snapshot_id)
    assert retrieved_manifest is not None
    assert retrieved_manifest.snapshot_id == snapshot_id
    assert retrieved_manifest.metadata == metadata
    assert len(retrieved_manifest.chunks) == len(stored_manifest.chunks)
    for i in range(len(retrieved_manifest.chunks)):
        assert retrieved_manifest.chunks[i].chunk_hash == stored_manifest.chunks[i].chunk_hash

    # Get Data
    retrieved_data = await storage.get_snapshot_data(snapshot_id)
    assert retrieved_data == sample_data_A

@pytest.mark.asyncio
async def test_list_snapshots(storage: FileSnapshotStorage, sample_data_A, sample_data_B):
    """Test listing snapshot manifests."""
    await storage.store_snapshot_manifest("snap_list_1", sample_data_A, {"tag": "A"})
    await storage.store_snapshot_manifest("snap_list_2", sample_data_B, {"tag": "B"})
    
    manifest_ids = await storage.list_snapshot_manifests()
    assert isinstance(manifest_ids, list)
    assert len(manifest_ids) == 2
    assert "snap_list_1" in manifest_ids
    assert "snap_list_2" in manifest_ids

    # Test limit and offset (basic, as current impl ignores other filters)
    limited_ids = await storage.list_snapshot_manifests(limit=1)
    assert len(limited_ids) == 1
    offset_ids = await storage.list_snapshot_manifests(limit=1, offset=1)
    assert len(offset_ids) == 1
    if limited_ids and offset_ids:
         assert limited_ids[0] != offset_ids[0]

@pytest.mark.asyncio
async def test_get_non_existent_snapshot(storage: FileSnapshotStorage):
    """Test retrieving a non-existent snapshot raises SnapshotNotFoundError."""
    with pytest.raises(SnapshotNotFoundError):
        await storage.get_snapshot_manifest("non_existent_snap")
    with pytest.raises(SnapshotNotFoundError): # get_snapshot_data also relies on get_snapshot_manifest
        await storage.get_snapshot_data("non_existent_snap")

@pytest.mark.asyncio
async def test_deduplication_of_chunks(storage: FileSnapshotStorage, sample_data_A):
    """Test that identical data results in shared chunks (deduplication)."""
    manifest1 = await storage.store_snapshot_manifest("dedup_snap1", sample_data_A, {"set": "dedup"})
    manifest2 = await storage.store_snapshot_manifest("dedup_snap2", sample_data_A, {"set": "dedup"}) # Identical data

    assert manifest1.snapshot_id != manifest2.snapshot_id
    assert len(manifest1.chunks) == len(manifest2.chunks)
    for i in range(len(manifest1.chunks)):
        assert manifest1.chunks[i].chunk_hash == manifest2.chunks[i].chunk_hash, \
            f"Chunk hash mismatch at index {i} for identical data implies no deduplication."
    
    # Check reference counts for one of the shared chunks
    shared_chunk_hash = manifest1.chunks[0].chunk_hash
    ref_count = await storage.get_chunk_reference_count(shared_chunk_hash)
    assert ref_count == 2, "Reference count for shared chunk should be 2 after storing two manifests"

    overview = storage.get_storage_overview()
    # Expect 2 manifests, but chunk count on disk should reflect deduplication
    # (e.g., if sample_data_A resulted in N chunks, disk count is N, not 2N)
    assert overview["manifests_count"] == 2
    assert overview["chunks_count_on_disk"] == len(manifest1.chunks)
    assert overview["referenced_chunks_count"] == len(manifest1.chunks)

@pytest.mark.asyncio
async def test_delete_snapshot_manifest_and_gc(storage: FileSnapshotStorage, sample_data_A, sample_data_B):
    """Test deleting manifests and garbage collection of orphaned chunks."""
    # Store three snapshots
    mani_A1 = await storage.store_snapshot_manifest("gc_snap_A1", sample_data_A, {"data_type": "A"})
    mani_A2 = await storage.store_snapshot_manifest("gc_snap_A2", sample_data_A, {"data_type": "A"}) # Shares chunks with A1
    mani_B1 = await storage.store_snapshot_manifest("gc_snap_B1", sample_data_B, {"data_type": "B"}) # Different chunks

    chunks_A = {c.chunk_hash for c in mani_A1.chunks} # Should be same for mani_A2
    chunks_B = {c.chunk_hash for c in mani_B1.chunks}
    assert len(chunks_A.intersection(chunks_B)) == 0, "Sample A and B should not share chunks for this test"

    # Initial ref counts
    for ch_hash in chunks_A:
        assert await storage.get_chunk_reference_count(ch_hash) == 2
    for ch_hash in chunks_B:
        assert await storage.get_chunk_reference_count(ch_hash) == 1

    # Delete gc_snap_A1
    deleted_A1 = await storage.delete_snapshot_manifest("gc_snap_A1")
    assert deleted_A1
    for ch_hash in chunks_A:
        assert await storage.get_chunk_reference_count(ch_hash) == 1, "Ref count for A chunks should be 1 after deleting A1"
    for ch_hash in chunks_B: # B chunks unaffected
        assert await storage.get_chunk_reference_count(ch_hash) == 1

    # Try deleting non-existent manifest
    deleted_non_existent = await storage.delete_snapshot_manifest("non_existent_snap_for_delete")
    assert not deleted_non_existent

    # Delete gc_snap_A2 - now chunks_A should be orphaned
    deleted_A2 = await storage.delete_snapshot_manifest("gc_snap_A2")
    assert deleted_A2
    for ch_hash in chunks_A:
        assert await storage.get_chunk_reference_count(ch_hash) == 0, "Ref count for A chunks should be 0 after deleting A2"

    # Run GC (dry run first)
    orphaned_dry_run = await storage.garbage_collect_orphaned_chunks(dry_run=True)
    assert sorted(list(chunks_A)) == sorted(orphaned_dry_run), "Dry run GC should identify orphaned A chunks"

    # Check chunks still exist physically after dry run
    for ch_hash in chunks_A:
        assert await storage.chunk_exists(ch_hash)

    # Actual GC run
    orphaned_actual = await storage.garbage_collect_orphaned_chunks(dry_run=False)
    assert sorted(list(chunks_A)) == sorted(orphaned_actual), "Actual GC should delete orphaned A chunks"

    # Check chunks_A are now gone, chunks_B remain
    for ch_hash in chunks_A:
        assert not await storage.chunk_exists(ch_hash), f"Chunk {ch_hash} from set A should be deleted by GC"
        assert await storage.get_chunk_reference_count(ch_hash) == 0
    for ch_hash in chunks_B:
        assert await storage.chunk_exists(ch_hash), f"Chunk {ch_hash} from set B should still exist"
        assert await storage.get_chunk_reference_count(ch_hash) == 1
    
    # Check manifest B1 data is still retrievable
    retrieved_B1_data = await storage.get_snapshot_data("gc_snap_B1")
    assert retrieved_B1_data == sample_data_B

@pytest.mark.asyncio
async def test_storage_overwrite_protection(storage: FileSnapshotStorage, sample_data_A):
    """Test that storing a snapshot with an existing ID raises an error."""
    await storage.store_snapshot_manifest("overwrite_test", sample_data_A)
    with pytest.raises(SnapshotStorageError, match="already exists. Overwriting not yet supported safely."):
        await storage.store_snapshot_manifest("overwrite_test", sample_data_A) # Attempt to store again

@pytest.mark.asyncio
async def test_chunk_operations_direct(storage: FileSnapshotStorage):
    """Test individual chunk operations like store_chunk, get_chunk, chunk_exists, delete_chunk (indirectly via GC)."""
    chunk_hash_test = "a0123456789abcdefa0123456789abcdefa0123456789abcdefa0123456789abcdef"
    chunk_data_test = b"this is some test chunk data for direct operations"

    assert not await storage.chunk_exists(chunk_hash_test)
    
    # store_chunk is not directly part of the high-level flow for FileSnapshotStorage,
    # as chunks are stored during store_snapshot_manifest. However, we can test parts of it.
    # For FileSnapshotStorage, store_chunk might be a no-op if chunk exists, or store it.
    # We'll simulate its effect as part of manifest storage for ref counting.

    # Test get_chunk for non-existent chunk
    with pytest.raises(ChunkNotFoundError):
        await storage.get_chunk("non_existent_chunk_hash_direct")

    # The delete_chunk method is also primarily for GC. We tested GC extensively.
    # Direct deletion of a referenced chunk should ideally be prevented or handled carefully.
    # The current FileSnapshotStorage.delete_chunk has a safety check.

    # For FileSnapshotStorage, increment/decrement are used by manifest ops.
    await storage.increment_chunk_reference(chunk_hash_test)
    assert await storage.get_chunk_reference_count(chunk_hash_test) == 1
    count_after_decrement = await storage.decrement_chunk_reference(chunk_hash_test)
    assert count_after_decrement == 0
    assert await storage.get_chunk_reference_count(chunk_hash_test) == 0

# Further tests could include:
# - Error handling for file system issues (e.g., permissions, disk full) - requires mocking.
# - Concurrency tests if FileSnapshotStorage is expected to be used by multiple async tasks concurrently modifying ref counts.
# - More elaborate filtering for list_snapshot_manifests once implemented.
# - Behavior of _load_ref_counts with corrupted JSON. 