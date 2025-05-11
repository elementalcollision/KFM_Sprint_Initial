import os
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import zstandard

from .snapshot_storage_interface import (
    SnapshotStorageInterface,
    SnapshotManifest,
    ChunkReference,
    SnapshotStorageError,
    SnapshotNotFoundError,
    ChunkNotFoundError
)
from .chunking_utils import process_data_for_snapshot, ChunkingError

# File to store reference counts for chunks
REF_COUNT_FILE = "chunk_ref_counts.json"

class FileSnapshotStorage(SnapshotStorageInterface):
    """
    A file-system based implementation of the SnapshotStorageInterface.

    Stores snapshots as manifests (JSON files) and data as compressed,
    content-addressed chunks in a structured directory layout.
    Implements reference counting for garbage collection of unused chunks.
    """

    def __init__(self, base_storage_path: str):
        """
        Initializes the FileSnapshotStorage.

        Args:
            base_storage_path: The root directory where snapshots will be stored.
        
        Raises:
            SnapshotStorageError: If the base path cannot be created or accessed.
        """
        self.base_path = Path(base_storage_path)
        self.manifests_path = self.base_path / "manifests"
        self.chunks_path = self.base_path / "chunks"
        self._ref_counts_path = self.base_path / REF_COUNT_FILE
        self._ref_counts: Dict[str, int] = {}

        try:
            self.manifests_path.mkdir(parents=True, exist_ok=True)
            self.chunks_path.mkdir(parents=True, exist_ok=True)
            self._load_ref_counts()
        except OSError as e:
            raise SnapshotStorageError(f"Failed to initialize storage at {self.base_path}: {e}") from e

    def _load_ref_counts(self):
        """Loads chunk reference counts from the JSON file."""
        if self._ref_counts_path.exists():
            try:
                with open(self._ref_counts_path, 'r') as f:
                    self._ref_counts = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                # If loading fails, it's safer to start with empty counts
                # or log a warning and proceed carefully.
                # For now, we'll proceed with empty, assuming a corrupted or new store.
                print(f"Warning: Could not load reference counts from {self._ref_counts_path}: {e}. Starting fresh.")
                self._ref_counts = {}
        else:
            self._ref_counts = {}
            self._save_ref_counts() # Create an empty one if it doesn't exist

    def _save_ref_counts(self):
        """Saves chunk reference counts to the JSON file."""
        try:
            with open(self._ref_counts_path, 'w') as f:
                json.dump(self._ref_counts, f, indent=2)
        except IOError as e:
            # This is more critical, as failure to save means lost ref counts.
            # Depending on strategy, could raise an error or log severely.
            print(f"Critical Warning: Failed to save reference counts to {self._ref_counts_path}: {e}")
            # Consider raising SnapshotStorageError here if consistency is paramount

    def _get_chunk_path(self, chunk_hash: str) -> Path:
        """Determines the file path for a given chunk hash."""
        if len(chunk_hash) < 2:
            # This should not happen with SHA256, but good practice
            raise ValueError("Chunk hash is too short to create a directory structure.")
        return self.chunks_path / chunk_hash[:2] / chunk_hash

    async def increment_chunk_reference(self, chunk_hash: str) -> None:
        """Increments the reference count for a given chunk."""
        self._ref_counts[chunk_hash] = self._ref_counts.get(chunk_hash, 0) + 1
        # Potentially save ref counts immediately or batch, for now, it's saved by other operations
        # self._save_ref_counts() # Consider if this should be async or if save should be more resilient

    async def decrement_chunk_reference(self, chunk_hash: str) -> int:
        """Decrements the reference count for a given chunk. Returns the new count."""
        if chunk_hash in self._ref_counts:
            self._ref_counts[chunk_hash] -= 1
            if self._ref_counts[chunk_hash] <= 0:
                del self._ref_counts[chunk_hash]
                # self._save_ref_counts() # Consider if this should be async
                return 0
            # self._save_ref_counts() # Consider if this should be async
            return self._ref_counts[chunk_hash]
        return -1 # Or 0 if preferred for non-existent chunk, interface implies current count

    async def get_chunk_reference_count(self, chunk_hash: str) -> int:
        """Gets the current reference count for a given chunk."""
        return self._ref_counts.get(chunk_hash, 0)

    async def store_chunk(self, chunk_hash: str, chunk_data: bytes) -> None:
        chunk_path = self._get_chunk_path(chunk_hash)
        try:
            if not chunk_path.exists(): # Store only if not already present
                chunk_path.parent.mkdir(parents=True, exist_ok=True)
                with open(chunk_path, 'wb') as f:
                    f.write(chunk_data)
            # NB: Reference count is incremented when a manifest uses this chunk,
            # not necessarily on every call to store_chunk if the chunk already exists.
            # The logic for calling _increment_ref_count will be in store_snapshot_manifest.
        except OSError as e:
            raise SnapshotStorageError(f"Failed to store chunk {chunk_hash}: {e}") from e

    async def get_chunk(self, chunk_hash: str) -> bytes:
        chunk_path = self._get_chunk_path(chunk_hash)
        if not chunk_path.exists():
            raise ChunkNotFoundError(f"Chunk {chunk_hash} not found.")
        try:
            with open(chunk_path, 'rb') as f:
                return f.read()
        except OSError as e:
            raise SnapshotStorageError(f"Failed to read chunk {chunk_hash}: {e}") from e

    async def chunk_exists(self, chunk_hash: str) -> bool:
        """Checks if a chunk with the given hash exists in the storage."""
        chunk_path = self._get_chunk_path(chunk_hash)
        return chunk_path.exists()

    async def delete_chunk(self, chunk_hash: str) -> bool:
        # This method is typically called by a garbage collection process
        # after confirming the chunk's reference count is zero.
        if self._ref_counts.get(chunk_hash, 0) > 0:
            # Safety check: do not delete if still referenced.
            # This might indicate an issue with the GC logic calling this.
            print(f"Warning: Attempted to delete chunk {chunk_hash} with ref count {self._ref_counts[chunk_hash]}.")
            return False

        chunk_path = self._get_chunk_path(chunk_hash)
        if chunk_path.exists():
            try:
                os.remove(chunk_path)
                # Try to remove the parent directory if it's empty (e.g., chunks_path/xx/)
                try:
                    chunk_path.parent.rmdir()
                except OSError:
                    pass # Directory not empty, which is fine
                return True
            except OSError as e:
                raise SnapshotStorageError(f"Failed to delete chunk {chunk_hash}: {e}") from e
        return False # Chunk didn't exist

    async def store_snapshot_manifest(self, snapshot_id: str, state_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> SnapshotManifest:
        manifest_path = self.manifests_path / f"{snapshot_id}.json"
        if manifest_path.exists():
            # Behavior for existing snapshot ID: overwrite or error?
            # For now, let's assume overwrite is acceptable, but this might need a strategy.
            # If overwriting, we need to decrement ref counts for chunks in the old manifest.
            # This is complex; a simpler initial approach is to disallow overwriting by ID.
            # Let's error if exists for now.
            raise SnapshotStorageError(f"Snapshot manifest {snapshot_id} already exists. Overwriting not yet supported safely.")

        try:
            processed_chunk_tuples = process_data_for_snapshot(state_data)
        except ChunkingError as e:
            raise SnapshotStorageError(f"Failed to process data for snapshot {snapshot_id}: {e}") from e

        chunk_references = []
        newly_stored_chunk_hashes = []

        for chunk_hash, compressed_data, offset, length in processed_chunk_tuples:
            # Store the chunk if it's not already effectively stored by this operation
            # (it might exist from a previous snapshot, which is good for deduplication)

            chunk_path = self._get_chunk_path(chunk_hash)
            if not await self.chunk_exists(chunk_hash):
                # Ensure the subdirectory exists (e.g., /ab/)
                chunk_path.parent.mkdir(parents=True, exist_ok=True)
                with open(chunk_path, 'wb') as f:
                    f.write(compressed_data)
            
            # Increment ref count for this chunk as it's part of this new manifest
            # self._increment_ref_count(chunk_hash) # Old internal call
            await self.increment_chunk_reference(chunk_hash) # Use the interface method
            newly_stored_chunk_hashes.append(chunk_hash)
            
            chunk_references.append(ChunkReference(
                chunk_hash=chunk_hash,
                offset=offset,
                length=length,
                compressed_length=len(compressed_data)
            ))
        
        # Persist reference counts *after* successful chunk processing and manifest creation attempt
        # This is a critical section. If manifest saving fails, we need to roll back ref counts.

        manifest = SnapshotManifest(
            snapshot_id=snapshot_id,
            chunks=chunk_references,
            metadata=metadata or {},
            # timestamp will be set by Pydantic default_factory
            # total_original_size will be calculated by Pydantic @computed_field
        )

        try:
            with open(manifest_path, 'w') as f:
                f.write(manifest.model_dump_json(indent=2))
            self._save_ref_counts() # Save ref counts only after manifest is successfully written
            return manifest
        except (IOError, TypeError) as e: # TypeError for model_dump_json issues
            # Rollback reference counts for chunks added by this failed manifest
            for ch_hash in newly_stored_chunk_hashes:
                # self._decrement_ref_count(ch_hash) # Old internal call
                await self.decrement_chunk_reference(ch_hash) # Use the interface method
            # Potentially delete chunks if they were newly written and their ref count is now 0
            # This is complex rollback logic, for now, just save rolled-back ref counts.
            self._save_ref_counts()
            raise SnapshotStorageError(f"Failed to save manifest for snapshot {snapshot_id}: {e}") from e
        except Exception as e: # Catch-all for other unexpected errors
            # Attempt rollback as above
            for ch_hash in newly_stored_chunk_hashes:
                # self._decrement_ref_count(ch_hash) # Old internal call
                await self.decrement_chunk_reference(ch_hash) # Use the interface method
            self._save_ref_counts()
            raise SnapshotStorageError(f"Unexpected error saving manifest for snapshot {snapshot_id}: {e}") from e


    async def get_snapshot_manifest(self, snapshot_id: str) -> SnapshotManifest:
        manifest_path = self.manifests_path / f"{snapshot_id}.json"
        if not manifest_path.exists():
            raise SnapshotNotFoundError(f"Snapshot manifest {snapshot_id} not found.")
        try:
            with open(manifest_path, 'r') as f:
                data = json.load(f)
                return SnapshotManifest(**data)
        except (IOError, json.JSONDecodeError, TypeError) as e: # TypeError for Pydantic validation
            raise SnapshotStorageError(f"Failed to load or parse manifest {snapshot_id}: {e}") from e

    async def list_snapshot_manifests(
        self,
        component_id: Optional[str] = None, # Added from interface
        component_type: Optional[str] = None, # Added from interface
        timestamp_from: Optional[float] = None, # Added from interface
        timestamp_to: Optional[float] = None, # Added from interface
        tags: Optional[List[str]] = None, # Added from interface
        limit: int = 100, # Added from interface
        offset: int = 0 # Added from interface
    ) -> List[str]:
        # Basic implementation: returns all manifest IDs (stems of .json files)
        # Ignores filtering parameters for now, but they are present for interface compatibility.
        # A more advanced implementation would parse manifests to filter by metadata.
        try:
            all_manifest_ids = [f.stem for f in self.manifests_path.iterdir() if f.is_file() and f.suffix == '.json']
            # Apply offset and limit after fetching all, for simplicity. Filtering would be more efficient if done before/during listing.
            return all_manifest_ids[offset : offset + limit]
        except OSError as e:
            raise SnapshotStorageError(f"Failed to list snapshot manifests: {e}") from e
            
    async def delete_snapshot_manifest(self, snapshot_id: str) -> bool:
        manifest_path = self.manifests_path / f"{snapshot_id}.json"
        if not manifest_path.exists():
            return False # Or raise SnapshotNotFoundError depending on desired strictness

        try:
            # Load manifest to get chunk hashes for decrementing ref counts
            manifest = await self.get_snapshot_manifest(snapshot_id)
            
            os.remove(manifest_path) # Delete the manifest file

            # Decrement reference counts for all chunks in this manifest
            # And collect hashes of chunks whose ref count dropped to zero
            orphaned_chunk_hashes = []
            for chunk_ref in manifest.chunks:
                # ref_count_after_decrement = self._decrement_ref_count(chunk_ref.chunk_hash)
                ref_count_after_decrement = await self.decrement_chunk_reference(chunk_ref.chunk_hash)
                if ref_count_after_decrement == 0:
                    orphaned_chunk_hashes.append(chunk_ref.chunk_hash)
            
            self._save_ref_counts() # Save updated ref counts

            # Optional: Immediately delete orphaned chunks (Garbage Collection)
            # This could also be a separate GC process. For simplicity, let's do it here.
            # for chunk_hash_to_delete in orphaned_chunk_hashes:
            #     try:
            #         await self.delete_chunk(chunk_hash_to_delete) # delete_chunk already checks ref count as safety
            #     except SnapshotStorageError as gc_err:
            #         print(f"Error during GC of chunk {chunk_hash_to_delete} for snapshot {snapshot_id}: {gc_err}")
            #         # Decide if this error should propagate or just be logged

            return True
        except SnapshotNotFoundError: # Should not happen if we checked exists, but for safety
             return False
        except (OSError, SnapshotStorageError) as e:
            # If deleting manifest or updating ref counts fails, it's a partial failure state.
            # Log this. For now, re-raise as a storage error.
            raise SnapshotStorageError(f"Failed to delete snapshot manifest {snapshot_id} or update/GC chunks: {e}") from e


    # --- Advanced/Helper methods ---

    async def get_snapshot_data(self, snapshot_id: str) -> bytes:
        """
        Retrieves and reassembles the complete original data for a snapshot.
        """
        manifest = await self.get_snapshot_manifest(snapshot_id)
        
        # Chunks might not be stored in order in the manifest if it was constructed
        # from an arbitrary set of chunk references. We need to reassemble them
        # based on their original offsets.
        # Sort chunk references by their original offset.
        sorted_chunk_refs = sorted(manifest.chunks, key=lambda cr: cr.offset)
        
        reassembled_data = bytearray()
        current_offset = 0
        
        compressor = zstandard.ZstdDecompressor()

        for chunk_ref in sorted_chunk_refs:
            if chunk_ref.offset < current_offset:
                raise SnapshotStorageError(f"Snapshot {snapshot_id} has overlapping chunks. Offset {chunk_ref.offset} < current offset {current_offset}")
            
            # Fill gaps if any (should not happen if snapshots are contiguous)
            if chunk_ref.offset > current_offset:
                # This indicates missing data or a sparse snapshot.
                # Depending on requirements, fill with zeros or raise error.
                # For now, assume contiguous or error on first gap.
                # If sparse snapshots are allowed, this logic needs to change.
                raise SnapshotStorageError(f"Snapshot {snapshot_id} has a gap at offset {current_offset}. Chunk starts at {chunk_ref.offset}.")

            compressed_chunk_data = await self.get_chunk(chunk_ref.chunk_hash)
            try:
                original_chunk_data = compressor.decompress(compressed_chunk_data)
            except zstandard.ZstdError as e:
                raise SnapshotStorageError(f"Failed to decompress chunk {chunk_ref.chunk_hash} for snapshot {snapshot_id}: {e}") from e

            if len(original_chunk_data) != chunk_ref.length:
                raise SnapshotStorageError(
                    f"Decompressed chunk {chunk_ref.chunk_hash} length mismatch for snapshot {snapshot_id}. "
                    f"Expected {chunk_ref.length}, got {len(original_chunk_data)}."
                )
            
            reassembled_data.extend(original_chunk_data)
            current_offset = chunk_ref.offset + chunk_ref.length
            
        # Verify total size if manifest has it (it will via Pydantic computed field)
        if manifest.total_original_size != len(reassembled_data):
             raise SnapshotStorageError(
                f"Reassembled data size mismatch for snapshot {snapshot_id}. "
                f"Expected {manifest.total_original_size}, got {len(reassembled_data)}."
            )
            
        return bytes(reassembled_data)

    async def garbage_collect_orphaned_chunks(self, dry_run: bool = True) -> List[str]:
        """
        Scans all stored chunks and deletes any that are no longer referenced
        by any snapshot manifest (i.e., their reference count is zero or missing).
        If dry_run is True, returns a list of chunk hashes that would be deleted
        but does not actually delete them. If False, deletes them.

        Returns:
            A list of chunk hashes that were (or would be) deleted.
        """
        all_physical_chunk_hashes = set()
        try:
            for dir_prefix in self.chunks_path.iterdir():
                if dir_prefix.is_dir() and len(dir_prefix.name) == 2: # e.g., /ab/
                    for chunk_file in dir_prefix.iterdir():
                        if chunk_file.is_file():
                            all_physical_chunk_hashes.add(chunk_file.name)
        except OSError as e:
            raise SnapshotStorageError(f"GC: Error listing chunk files: {e}")

        orphaned_hashes_to_delete = []
        
        # Identify chunks with zero or missing reference count
        for chunk_hash in all_physical_chunk_hashes:
            if self._ref_counts.get(chunk_hash, 0) == 0:
                orphaned_hashes_to_delete.append(chunk_hash)
            elif chunk_hash not in self._ref_counts:
                # This means a chunk file exists but has no entry in _ref_counts.
                # It's effectively orphaned.
                # A safer GC might rebuild ref_counts from all manifests first if discrepancy is found.
                # For now, we assume if it's not in _ref_counts loaded at start, it's orphaned.
                print(f"GC: Found chunk {chunk_hash} on disk with no entry in reference counts.")
                orphaned_hashes_to_delete.append(chunk_hash)

        if dry_run:
            print(f"GC (Dry Run): Would delete {len(orphaned_hashes_to_delete)} orphaned chunks.")
            # Also identify stale ref_counts for dry_run reporting
            stale_ref_counts_dry_run = [ch_hash for ch_hash in self._ref_counts if not self._get_chunk_path(ch_hash).exists()]
            if stale_ref_counts_dry_run:
                print(f"GC (Dry Run): Would prune {len(stale_ref_counts_dry_run)} stale reference counts.")
            return orphaned_hashes_to_delete

        # Actual deletion phase (if not dry_run)
        deleted_chunk_hashes = []
        for chunk_hash in orphaned_hashes_to_delete:
            try:
                chunk_path = self._get_chunk_path(chunk_hash)
                if chunk_path.exists():
                    os.remove(chunk_path)
                    deleted_chunk_hashes.append(chunk_hash)
                    print(f"GC: Deleted orphaned chunk {chunk_hash}")
                    try:
                        chunk_path.parent.rmdir() # Try to remove parent dir if empty
                    except OSError:
                        pass # Directory not empty, which is fine
                else:
                    print(f"GC: Orphaned chunk {chunk_hash} not found on disk during deletion attempt.")
            except OSError as e:
                print(f"GC: Error deleting orphaned chunk {chunk_hash}: {e}")
                # Decide if this should be a hard error or just logged

        # Prune any entries in _ref_counts that don't have corresponding chunk files
        stale_ref_counts_to_prune = [ch_hash for ch_hash in list(self._ref_counts.keys()) if not self._get_chunk_path(ch_hash).exists()]
        if stale_ref_counts_to_prune:
            for ch_hash in stale_ref_counts_to_prune:
                print(f"GC: Pruning stale reference count for non-existent chunk file: {ch_hash}")
                del self._ref_counts[ch_hash]
            self._save_ref_counts() # Save ref_counts after pruning stale entries
        
        return deleted_chunk_hashes

    def get_storage_overview(self) -> Dict[str, Any]:
        """Provides an overview of the storage usage."""
        num_manifests = len(list(self.manifests_path.glob('*.json')))
        
        num_chunks = 0
        total_chunks_size_compressed = 0
        chunk_dirs = [d for d in self.chunks_path.iterdir() if d.is_dir()]
        for chunk_dir in chunk_dirs:
            for chunk_file in chunk_dir.iterdir():
                if chunk_file.is_file():
                    num_chunks += 1
                    total_chunks_size_compressed += chunk_file.stat().st_size
        
        return {
            "base_path": str(self.base_path),
            "manifests_count": num_manifests,
            "chunks_count_on_disk": num_chunks, # Physical chunks
            "referenced_chunks_count": len(self._ref_counts), # Chunks with ref_count > 0
            "total_chunks_size_compressed_bytes": total_chunks_size_compressed,
        }

# Example usage (illustrative, real usage would be async)
if __name__ == '__main__':
    import asyncio

    async def main_test():
        print("Testing FileSnapshotStorage...")
        # Create a temporary directory for testing
        test_storage_path = "./tmp_snapshot_storage"
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path) # Clean up from previous test

        storage = FileSnapshotStorage(base_storage_path=test_storage_path)

        sample_data1 = b"Hello, this is the first state of our important component." * 100
        sample_data2 = b"Hello, this is the first state of our important component." * 100 # Identical data
        sample_data3 = b"And now, a completely different state for the component after some operations." * 120
        
        try:
            # --- Test Store Manifest and Chunks ---
            print("\n--- Storing snapshots ---")
            manifest1 = await storage.store_snapshot_manifest("snap001", sample_data1, {"component_id": "compA", "version": 1})
            print(f"Stored manifest1: ID={manifest1.snapshot_id}, Chunks={len(manifest1.chunks)}, Total Size={manifest1.total_original_size}")
            
            manifest2 = await storage.store_snapshot_manifest("snap002", sample_data2, {"component_id": "compA", "version": 1, "note": "identical data to snap001"})
            print(f"Stored manifest2: ID={manifest2.snapshot_id}, Chunks={len(manifest2.chunks)}, Total Size={manifest2.total_original_size}")
            # Check for deduplication: chunk hashes in manifest1 and manifest2 for identical data should be the same
            if manifest1.chunks and manifest2.chunks and all(c1.chunk_hash == c2.chunk_hash for c1, c2 in zip(manifest1.chunks, manifest2.chunks)):
                print("Deduplication check: manifest1 and manifest2 share chunk hashes as expected.")
            else:
                print("Deduplication check: FAILED. Chunks are different for identical data.")


            manifest3 = await storage.store_snapshot_manifest("snap003", sample_data3, {"component_id": "compA", "version": 2})
            print(f"Stored manifest3: ID={manifest3.snapshot_id}, Chunks={len(manifest3.chunks)}, Total Size={manifest3.total_original_size}")

            print(f"Reference Counts after 3 stores: {storage._ref_counts}")
            overview = storage.get_storage_overview()
            print(f"Storage Overview after stores: {overview}")


            # --- Test Get Manifest and Data ---
            print("\n--- Retrieving snapshots ---")
            ret_manifest1 = await storage.get_snapshot_manifest("snap001")
            print(f"Retrieved manifest1: ID={ret_manifest1.snapshot_id}, Metadata={ret_manifest1.metadata}")
            ret_data1 = await storage.get_snapshot_data("snap001")
            assert ret_data1 == sample_data1, "Data mismatch for snap001"
            print(f"Retrieved data for snap001 matches original (Size: {len(ret_data1)}).")

            ret_data3 = await storage.get_snapshot_data("snap003")
            assert ret_data3 == sample_data3, "Data mismatch for snap003"
            print(f"Retrieved data for snap003 matches original (Size: {len(ret_data3)}).")

            # --- Test List Manifests ---
            print("\n--- Listing snapshots ---")
            manifest_ids = await storage.list_snapshot_manifests()
            print(f"Available snapshot IDs: {manifest_ids}")
            assert sorted(manifest_ids) == sorted(["snap001", "snap002", "snap003"])

            # --- Test Delete Manifest and GC ---
            print("\n--- Deleting snapshot snap002 ---")
            deleted_snap002 = await storage.delete_snapshot_manifest("snap002")
            assert deleted_snap002
            print(f"Deleted snap002. Ref Counts: {storage._ref_counts}")
            # Chunks shared by snap001 and snap002 should still have ref_count > 0 from snap001

            print("\n--- Deleting snapshot snap001 ---")
            deleted_snap001 = await storage.delete_snapshot_manifest("snap001")
            assert deleted_snap001
            print(f"Deleted snap001. Ref Counts: {storage._ref_counts}")
            # Now chunks from snap001/snap002 should have ref_count 0 (or be removed from dict)
            # and be eligible for GC (though delete_snapshot_manifest might not GC immediately by default)

            print("\n--- Running explicit garbage collector ---")
            # gc_results = await storage.run_garbage_collector() # Old call
            gc_deleted_dry_run = await storage.garbage_collect_orphaned_chunks(dry_run=True)
            print(f"GC Results (Dry Run): Would delete {len(gc_deleted_dry_run)} chunks: {gc_deleted_dry_run}")
            gc_deleted_actual = await storage.garbage_collect_orphaned_chunks(dry_run=False)
            print(f"GC Results (Actual Run): Deleted {len(gc_deleted_actual)} chunks: {gc_deleted_actual}")
            print(f"Ref Counts after GC: {storage._ref_counts}")
            
            overview_after_gc = storage.get_storage_overview()
            print(f"Storage Overview after GC: {overview_after_gc}")
            # Expected: Chunks only referenced by snap001 & snap002 are gone. Chunks for snap003 remain.

            # --- Test non-existent snapshot ---
            print("\n--- Testing non-existent snapshot ---")
            try:
                await storage.get_snapshot_manifest("snap999")
            except SnapshotNotFoundError:
                print("Correctly raised SnapshotNotFoundError for snap999.")
            
            # Verify snap003 data is still intact
            ret_data3_after_gc = await storage.get_snapshot_data("snap003")
            assert ret_data3_after_gc == sample_data3, "Data mismatch for snap003 after GC"
            print(f"Retrieved data for snap003 post-GC matches original (Size: {len(ret_data3_after_gc)}).")


        except SnapshotStorageError as e:
            print(f"Storage Test Error: {e}")
        except Exception as e:
            print(f"Unexpected Test Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up test directory
            # shutil.rmtree(test_storage_path)
            # print(f"Cleaned up {test_storage_path}")
            print(f"Test finished. Storage directory at {test_storage_path} (not cleaned up for inspection).")


    asyncio.run(main_test())
 