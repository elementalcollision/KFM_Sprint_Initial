from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Protocol # Added Protocol for ManifestData
from pydantic import BaseModel, Field, computed_field # Added Pydantic
import time # For timestamp

# Define a Protocol for manifest_data if its structure is known and needs type hinting.
# For now, using Dict[str, Any] as a general placeholder.
ManifestData = Dict[str, Any] # Placeholder, can be refined with a TypedDict or Pydantic model


# Custom Exception Classes specific to snapshot operations
# These were being imported by FileSnapshotStorage from here, so they need to be defined.
class SnapshotStorageError(Exception):
    """Base exception for snapshot storage operations."""
    pass

class SnapshotNotFoundError(SnapshotStorageError):
    """Raised when a snapshot manifest is not found."""
    pass

class ChunkNotFoundError(SnapshotStorageError):
    """Raised when a chunk is not found."""
    pass


# Pydantic Models for Snapshot Structure
class ChunkReference(BaseModel):
    """Reference to a data chunk within a snapshot."""
    chunk_hash: str = Field(..., description="The hash (content address) of the chunk.")
    offset: int = Field(..., description="The original byte offset of this chunk within the complete state data.")
    length: int = Field(..., description="The original byte length of this chunk.")
    compressed_length: int = Field(..., description="The length of the chunk data as stored (compressed).")

class SnapshotManifest(BaseModel):
    """
    Manifest describing a snapshot, including its constituent chunks and metadata.
    """
    snapshot_id: str = Field(..., description="Unique identifier for the snapshot.")
    chunks: List[ChunkReference] = Field(..., description="List of chunk references that make up this snapshot.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata associated with the snapshot.")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of when the snapshot manifest was created.")

    @computed_field
    @property
    def total_original_size(self) -> int:
        """Calculates the total original size of the data represented by this snapshot."""
        return sum(chunk.length for chunk in self.chunks)


class SnapshotStorageInterface(ABC):
    """
    Abstract Base Class defining the interface for snapshot storage backends.

    This interface supports content-addressed storage for chunks and manifest-based
    management for snapshots.
    """

    @abstractmethod
    async def store_chunk(self, chunk_hash: str, chunk_data: bytes) -> None:
        """
        Stores a data chunk, typically compressed, indexed by its hash.

        Implementations should handle content-addressing, meaning if a chunk
        with the same hash already exists, this operation might be a no-op
        or simply update metadata (e.g., reference count if applicable).

        Args:
            chunk_hash (str): The unique hash (content address) of the chunk.
            chunk_data (bytes): The binary data of the chunk (should be pre-compressed by caller if desired).
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If writing the chunk fails for other reasons.
        """
        pass

    @abstractmethod
    async def get_chunk(self, chunk_hash: str) -> Optional[bytes]:
        """
        Retrieves a data chunk by its hash.

        Args:
            chunk_hash (str): The hash of the chunk to retrieve.

        Returns:
            Optional[bytes]: The binary data of the chunk if found, else None.
                             The data should be returned as stored (e.g., compressed).
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageReadError: If reading the chunk fails for other reasons.
        """
        pass

    @abstractmethod
    async def chunk_exists(self, chunk_hash: str) -> bool:
        """
        Checks if a chunk with the given hash exists in the storage.

        Args:
            chunk_hash (str): The hash of the chunk to check.

        Returns:
            bool: True if the chunk exists, False otherwise.

        Raises:
            StorageConnectionError: If connection to the backend fails.
        """
        pass

    @abstractmethod
    async def store_snapshot_manifest(
        self,
        snapshot_id: str,
        state_data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SnapshotManifest:
        """
        Processes state data into chunks, stores them, and then stores the manifest
        for a snapshot, indexed by the snapshot ID.

        Args:
            snapshot_id (str): The unique identifier for the snapshot.
            state_data (bytes): The raw byte data of the state to be snapshot.
            metadata (Optional[Dict[str, Any]]): Arbitrary metadata for the snapshot.
        
        Returns:
            SnapshotManifest: The manifest object that was created and stored.

        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If writing the manifest or chunks fails.
        """
        pass

    @abstractmethod
    async def get_snapshot_manifest(self, snapshot_id: str) -> Optional[SnapshotManifest]:
        """
        Retrieves a snapshot manifest by its ID.
        Note: Implementations should return the full SnapshotManifest object.
        If only ManifestData (dict) was stored, it should be parsed into SnapshotManifest.

        Args:
            snapshot_id (str): The ID of the snapshot manifest to retrieve.

        Returns:
            Optional[SnapshotManifest]: The SnapshotManifest object if found, else None.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageReadError: If reading or parsing the manifest fails.
        """
        pass

    @abstractmethod
    async def list_snapshot_manifests(
        self,
        component_id: Optional[str] = None,
        component_type: Optional[str] = None,
        timestamp_from: Optional[float] = None,
        timestamp_to: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[str]:
        """
        Lists snapshot manifest IDs, optionally filtered by various criteria.
        Should return a list of snapshot manifest IDs matching the criteria.

        Args:
            component_id (Optional[str]): Filter by component ID.
            component_type (Optional[str]): Filter by component type.
            timestamp_from (Optional[float]): Filter snapshots taken after this timestamp.
            timestamp_to (Optional[float]): Filter snapshots taken before this timestamp.
            tags (Optional[List[str]]): Filter by tags present in snapshot metadata.
            limit (int): Maximum number of manifests to return.
            offset (int): Offset for pagination.

        Returns:
            List[str]: A list of snapshot manifest IDs matching the criteria.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
        """
        pass

    @abstractmethod
    async def delete_snapshot_manifest(self, snapshot_id: str) -> bool:
        """
        Deletes a snapshot manifest by its ID.
        This operation should typically trigger a check for orphaned chunks
        if reference counting is implemented by the backend.

        Args:
            snapshot_id (str): The ID of the snapshot manifest to delete.

        Returns:
            bool: True if deletion was successful, False if the manifest was not found.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If deletion fails for other reasons.
        """
        pass

    @abstractmethod
    async def increment_chunk_reference(self, chunk_hash: str) -> None:
        """
        Increments the reference count for a given chunk.
        Called when a snapshot manifest referencing this chunk is stored.

        Args:
            chunk_hash (str): The hash of the chunk to increment reference for.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If updating reference count fails.
        """
        pass

    @abstractmethod
    async def decrement_chunk_reference(self, chunk_hash: str) -> int:
        """
        Decrements the reference count for a given chunk.
        Called when a snapshot manifest referencing this chunk is deleted.
        If the reference count drops to zero, the chunk may be eligible for garbage collection.

        Args:
            chunk_hash (str): The hash of the chunk to decrement reference for.

        Returns:
            int: The new reference count for the chunk.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If updating reference count fails.
        """
        pass

    @abstractmethod
    async def get_chunk_reference_count(self, chunk_hash: str) -> int:
        """
        Gets the current reference count for a given chunk.

        Args:
            chunk_hash (str): The hash of the chunk.

        Returns:
            int: The current reference count. Returns 0 if chunk or its reference info doesn't exist.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
        """
        pass

    @abstractmethod
    async def garbage_collect_orphaned_chunks(self, dry_run: bool = True) -> List[str]:
        """
        Identifies and optionally deletes chunks whose reference count is zero.

        Args:
            dry_run (bool): If True, returns a list of chunk hashes that would be deleted
                            but does not actually delete them. If False, deletes them.

        Returns:
            List[str]: A list of chunk hashes that were (or would be) deleted.
        
        Raises:
            StorageConnectionError: If connection to the backend fails.
            StorageWriteError: If deletion fails during a non-dry run.
        """
        pass

# Consider adding custom exception classes for storage errors
class StorageError(Exception):
    """Base class for storage-related errors."""
    pass

class StorageConnectionError(StorageError):
    """Raised when connection to the storage backend fails."""
    pass

class StorageWriteError(StorageError):
    """Raised when a write operation to the storage backend fails."""
    pass

class StorageReadError(StorageError):
    """Raised when a read operation from the storage backend fails."""
    pass 