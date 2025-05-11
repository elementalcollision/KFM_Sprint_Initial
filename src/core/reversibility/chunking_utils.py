import io
import hashlib
import zstandard
import tempfile
import os
from typing import Callable, Optional # Added Callable, Optional
from fastcdc import fastcdc

# Default chunk sizes (can be tuned based on performance and deduplication rates)
DEFAULT_MIN_CHUNK_SIZE = 16 * 1024  # 16KB
DEFAULT_AVG_CHUNK_SIZE = 64 * 1024  # 64KB
DEFAULT_MAX_CHUNK_SIZE = 256 * 1024 # 256KB

class ChunkingError(Exception):
    """Custom exception for errors during chunking or compression."""
    pass

def process_data_for_snapshot(
    data_bytes: bytes,
    min_size: int = DEFAULT_MIN_CHUNK_SIZE,
    avg_size: int = DEFAULT_AVG_CHUNK_SIZE,
    max_size: int = DEFAULT_MAX_CHUNK_SIZE,
    fat: bool = True,
    # Changed hf to be a callable (hash constructor) defaulting to hashlib.sha256
    # The type hint hashlib._Hash might need adjustment based on precise hashlib internals
    # but Callable[[], Any] or Callable[[], hashlib._Hash] should work.
    hf: Optional[Callable] = hashlib.sha256
) -> list[tuple[str, bytes, int, int]]:
    """
    Processes input data bytes by performing content-defined chunking,
    compressing each chunk, and calculating its hash.

    Args:
        data_bytes: The raw byte data to process.
        min_size: Minimum chunk size for FastCDC.
        avg_size: Average target chunk size for FastCDC.
        max_size: Maximum chunk size for FastCDC.
        fat: Parameter for fastcdc, True to get full Chunk objects.
        hf: Hash function constructor to use (e.g., hashlib.sha256). If None, no hash is computed by fastcdc's Chunk object directly.

    Returns:
        A list of tuples, where each tuple contains:
        (chunk_hash_hex, compressed_chunk_data, original_offset, original_length)

    Raises:
        ChunkingError: If any error occurs during chunking or compression.
    """
    if not data_bytes: # Handle empty input explicitly
        return []

    processed_chunks = []
    temp_file_path = None

    try:
        # Create a named temporary file to pass to fastcdc
        # delete=False is important so we can pass the name and delete it manually
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(data_bytes)
            temp_file_path = tmp_file.name
        
        # fastcdc works with file paths or file-like objects that support fileno()
        # We now pass the path to the temporary file.
        # hf is now the callable hash constructor (e.g., hashlib.sha256)
        cdc = fastcdc(
            temp_file_path, # Pass the file path
            min_size=min_size, 
            avg_size=avg_size, 
            max_size=max_size, 
            fat=fat,
            hf=hf  # Pass the callable hash constructor
        )

        zstd_compressor = zstandard.ZstdCompressor()

        # print(f"DEBUG_CHUNK_UTIL: Iterating chunks from fastcdc with hf={hf}")

        for chunk in cdc:
            # The chunk object from fastcdc (with fat=True) should have:
            # chunk.data: The actual bytes of the chunk from the input file.
            # chunk.hash: The hex digest string of the hash if hf was provided to fastcdc.
            # chunk.offset: The offset of this chunk in the original file.
            # chunk.length: The length of this chunk.

            if chunk.data is None:
                raise ChunkingError(f"FastCDC chunk at offset {chunk.offset} did not contain data.")
            
            actual_chunk_data = chunk.data
            
            if chunk.hash is None:
                # This would happen if hf=None was passed to fastcdc
                # For our use case, we require a hash.
                # If hf in process_data_for_snapshot defaults to hashlib.sha256, this block should not be hit.
                raise ChunkingError(f"FastCDC chunk at offset {chunk.offset} did not produce a hash. Ensure 'hf' is provided.")

            chunk_hash_hex = chunk.hash # chunk.hash should be the hex string directly

            if not chunk_hash_hex or len(chunk_hash_hex) < 2:
                 raise ChunkingError(f"Invalid or too short chunk hash ('{chunk_hash_hex}') for chunk at offset {chunk.offset}.")

            try:
                compressed_chunk_data = zstd_compressor.compress(actual_chunk_data)
            except Exception as e:
                raise ChunkingError(f"Failed to compress chunk at offset {chunk.offset}: {e}") from e

            processed_chunks.append((
                chunk_hash_hex,
                compressed_chunk_data,
                chunk.offset,
                chunk.length
            ))

        return processed_chunks

    except Exception as e:
        raise ChunkingError(f"Error during data chunking/compression: {e}") from e
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as e:
                print(f"Warning: Failed to delete temporary file {temp_file_path}: {e}")


if __name__ == '__main__':
    import zstandard # For the test decompression
    print("Testing chunking_utils.py...")

    # Create some test data
    test_data_part1 = os.urandom(128 * 1024)  # 128KB
    test_data_part2 = os.urandom(64 * 1024)   # 64KB
    test_data_part3 = test_data_part1[:32*1024] # Create some duplication
    test_data_full = test_data_part1 + test_data_part2 + test_data_part3 + os.urandom(100)

    print(f"Original data size: {len(test_data_full)} bytes")

    try:
        min_s, avg_s, max_s = 4*1024, 16*1024, 64*1024
        # Test with default hf (hashlib.sha256)
        print("\nTesting with default hf (sha256)...")
        chunks_sha256 = process_data_for_snapshot(test_data_full, min_size=min_s, avg_size=avg_s, max_size=max_s)
        print(f"Processed into {len(chunks_sha256)} chunks with sha256.")
        # Basic check on first chunk hash
        if chunks_sha256:
            assert len(chunks_sha256[0][0]) == 64, "SHA256 hash length should be 64"

        # Test with hf=None (should raise an error in our modified code, or chunk.hash would be None)
        # print("\nTesting with hf=None...")
        # try:
        #     process_data_for_snapshot(test_data_full, min_size=min_s, avg_size=avg_s, max_size=max_s, hf=None)
        #     print("Error: process_data_for_snapshot with hf=None did not raise ChunkingError as expected.")
        # except ChunkingError as ce:
        #     if "did not produce a hash" in str(ce) or "'NoneType' object has no attribute 'hexdigest'" in str(ce):
        #         print(f"Correctly caught error for hf=None: {ce}")
        #     else:
        #         raise # Re-raise unexpected ChunkingError
        # except Exception as e_hf_none:
        #     print(f"Unexpected error during hf=None test: {e_hf_none}")
        #     raise

        # Re-run original verification logic for the default (sha256) case
        print("\nVerifying sha256 chunks...")
        total_compressed_size = 0
        total_original_size_from_chunks = 0
        zstd_decompressor = zstandard.ZstdDecompressor()
        reconstructed_data_parts = {}

        for i, (ch_hash, compressed_data, orig_offset, orig_length) in enumerate(chunks_sha256):
            print(f"  Chunk {i}: Hash={ch_hash}, Offset={orig_offset}, Orig_Len={orig_length}, Comp_Len={len(compressed_data)}")
            total_compressed_size += len(compressed_data)
            total_original_size_from_chunks += orig_length
            decompressed_data = zstd_decompressor.decompress(compressed_data)
            
            # For sha256, we expect chunk.hash from fastcdc to be the final hex digest
            assert hashlib.sha256(decompressed_data).hexdigest() == ch_hash, \
                f"Hash mismatch for chunk {i}. Expected hash of decompressed data to match stored hash. Stored: {ch_hash}, Calculated: {hashlib.sha256(decompressed_data).hexdigest()}"
            assert len(decompressed_data) == orig_length, f"Decompressed length mismatch for chunk {i}"
            reconstructed_data_parts[orig_offset] = decompressed_data

        print(f"Total original size from chunk lengths: {total_original_size_from_chunks} bytes")
        print(f"Total compressed size: {total_compressed_size} bytes")
        compression_ratio = total_original_size_from_chunks / total_compressed_size if total_compressed_size > 0 else 0
        print(f"Effective compression ratio: {compression_ratio:.2f}:1")
        assert total_original_size_from_chunks == len(test_data_full), "Sum of original chunk lengths does not match original data size."
        reconstructed_full_data_list = []
        for offset in sorted(reconstructed_data_parts.keys()):
            reconstructed_full_data_list.append(reconstructed_data_parts[offset])
        reconstructed_full_data = b"".join(reconstructed_full_data_list)
        assert reconstructed_full_data == test_data_full, "Reconstructed data does not match original data."
        print("Data reconstruction successful for sha256.")

        # Test with very small data (smaller than min_size)
        small_data = b"this is very small data, much smaller than min_chunk_size"
        print(f"\nTesting with small data ({len(small_data)} bytes)...")
        small_chunks = process_data_for_snapshot(small_data, min_size=min_s, avg_size=avg_s, max_size=max_s)
        print(f"Processed small data into {len(small_chunks)} chunk(s).")
        assert len(small_chunks) >= 1, "Small data should still produce at least one chunk."
        small_reconstructed_list = []
        for _, comp_data, _, _ in small_chunks:
            small_reconstructed_list.append(zstd_decompressor.decompress(comp_data))
        assert b"".join(small_reconstructed_list) == small_data, "Small data reconstruction failed."
        print("Small data processing successful.")

        print("\nchunking_utils.py tests passed!")

    except ChunkingError as e:
        print(f"Chunking Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}") 