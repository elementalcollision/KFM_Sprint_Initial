import os
import hashlib
import pytest
import zstandard

from src.core.reversibility.chunking_utils import (
    process_data_for_snapshot,
    ChunkingError,
    DEFAULT_MIN_CHUNK_SIZE,
    DEFAULT_AVG_CHUNK_SIZE,
    DEFAULT_MAX_CHUNK_SIZE
)

# Constants for test data generation if needed, or use fixed byte strings
KB = 1024
MB = 1024 * KB

@pytest.fixture
def sample_data_small():
    """Returns a small byte string, smaller than default min_chunk_size."""
    return b"This is very small data, much smaller than any reasonable min_chunk_size."

@pytest.fixture
def sample_data_medium():
    """Returns a medium-sized byte string with some repetition."""
    part1 = os.urandom(64 * KB) 
    part2 = os.urandom(32 * KB)
    part3 = part1[:16*KB] # Some repeated content
    return part1 + part2 + part3 + os.urandom(17) # Add some odd bytes

@pytest.fixture
def sample_data_large():
    """Returns a larger byte string, around 1MB."""
    return os.urandom(1 * MB)


def test_process_data_empty():
    """Test processing empty byte string."""
    data = b""
    chunks = process_data_for_snapshot(data)
    assert isinstance(chunks, list), "Should return a list"
    # Behavior for empty data: fastcdc might return one empty chunk or no chunks.
    # Let's assume it should produce one chunk representing the empty data, or an empty list.
    if chunks:
        assert len(chunks) == 1, "Empty data should ideally produce one (empty) chunk or no chunks"
        chunk_hash, compressed_data, offset, length = chunks[0]
        assert length == 0, "Chunk length for empty data should be 0"
        # Hash of empty string might be specific, e.g., sha256 of b''
        # assert chunk_hash == hashlib.sha256(b'').hexdigest()
        # Compressed data of empty string should also be empty or very small (zstd header)
    else:
        assert len(chunks) == 0, "Expected either one empty chunk or an empty list for empty data"

def test_process_data_small(sample_data_small):
    """Test with data smaller than min_chunk_size."""
    min_s, avg_s, max_s = 4*KB, 16*KB, 64*KB # Use smaller chunk params for this test if needed
    chunks = process_data_for_snapshot(sample_data_small, min_size=min_s, avg_size=avg_s, max_size=max_s)
    
    assert len(chunks) >= 1, "Small data should produce at least one chunk."
    
    zstd_decompressor = zstandard.ZstdDecompressor()
    reconstructed_data_list = []
    total_original_length = 0
    for ch_hash, compressed_data, orig_offset, orig_length in chunks:
        assert isinstance(ch_hash, str) and len(ch_hash) == 64, "Hash should be a SHA256 hex string"
        assert isinstance(compressed_data, bytes)
        assert isinstance(orig_offset, int) and orig_offset >= 0
        assert isinstance(orig_length, int) and orig_length > 0
        
        decompressed_data = zstd_decompressor.decompress(compressed_data)
        assert hashlib.sha256(decompressed_data).hexdigest() == ch_hash
        assert len(decompressed_data) == orig_length
        reconstructed_data_list.append((orig_offset, decompressed_data)) # Store with offset for correct reassembly
        total_original_length += orig_length

    assert total_original_length == len(sample_data_small)
    # Sort by offset before joining to ensure correct order
    reconstructed_data_list.sort(key=lambda x: x[0])
    reconstructed_data = b"".join(item[1] for item in reconstructed_data_list)
    assert reconstructed_data == sample_data_small, "Reconstructed small data does not match original."

def test_process_data_medium_default_params(sample_data_medium):
    """Test with medium data and default chunking parameters."""
    chunks = process_data_for_snapshot(sample_data_medium)
    
    assert len(chunks) >= 1
    
    zstd_decompressor = zstandard.ZstdDecompressor()
    reconstructed_data_list = []
    total_original_length = 0
    current_expected_offset = 0

    for ch_hash, compressed_data, orig_offset, orig_length in chunks:
        assert isinstance(ch_hash, str) and len(ch_hash) == 64
        assert orig_offset == current_expected_offset, f"Chunk offset mismatch. Expected {current_expected_offset}, got {orig_offset}"
        
        decompressed_data = zstd_decompressor.decompress(compressed_data)
        assert hashlib.sha256(decompressed_data).hexdigest() == ch_hash
        assert len(decompressed_data) == orig_length
        reconstructed_data_list.append(decompressed_data) # Chunks should be in order from fastcdc
        total_original_length += orig_length
        current_expected_offset += orig_length
        
    assert total_original_length == len(sample_data_medium)
    reconstructed_data = b"".join(reconstructed_data_list)
    assert reconstructed_data == sample_data_medium, "Reconstructed medium data does not match original."

def test_process_data_custom_chunk_sizes(sample_data_medium):
    """Test with custom (smaller) chunking parameters."""
    min_s, avg_s, max_s = 1*KB, 4*KB, 16*KB
    chunks_custom = process_data_for_snapshot(sample_data_medium, min_size=min_s, avg_size=avg_s, max_size=max_s)
    chunks_default = process_data_for_snapshot(sample_data_medium) # Using default params

    # Expect more chunks with smaller avg_size, assuming data is large enough
    if len(sample_data_medium) > max_s * 2: # Heuristic: if data is reasonably larger than max chunk size
        assert len(chunks_custom) > len(chunks_default), \
            f"Expected more chunks with smaller avg size. Custom: {len(chunks_custom)}, Default: {len(chunks_default)}"

    zstd_decompressor = zstandard.ZstdDecompressor()
    reconstructed_data_list = []
    total_original_length = 0
    current_expected_offset = 0
    for ch_hash, compressed_data, orig_offset, orig_length in chunks_custom:
        assert isinstance(ch_hash, str) and len(ch_hash) == 64
        assert orig_offset == current_expected_offset, f"Chunk offset mismatch. Expected {current_expected_offset}, got {orig_offset}"

        decompressed_data = zstd_decompressor.decompress(compressed_data)
        assert hashlib.sha256(decompressed_data).hexdigest() == ch_hash
        assert len(decompressed_data) == orig_length
        reconstructed_data_list.append(decompressed_data)
        total_original_length += orig_length
        current_expected_offset += orig_length
        
    assert total_original_length == len(sample_data_medium)
    reconstructed_data = b"".join(reconstructed_data_list)
    assert reconstructed_data == sample_data_medium, "Reconstructed medium data (custom params) does not match original."

def test_process_data_hash_consistency(sample_data_medium):
    """Test that the same data content produces the same chunk hashes."""
    # Process the same data twice
    chunks1 = process_data_for_snapshot(sample_data_medium)
    chunks2 = process_data_for_snapshot(sample_data_medium)

    assert len(chunks1) == len(chunks2), "Processing same data should yield same number of chunks"
    for i in range(len(chunks1)):
        assert chunks1[i][0] == chunks2[i][0], f"Chunk hash mismatch for chunk {i} on identical data input"
        assert chunks1[i][2] == chunks2[i][2], f"Chunk offset mismatch for chunk {i} on identical data input"
        assert chunks1[i][3] == chunks2[i][3], f"Chunk length mismatch for chunk {i} on identical data input"


def test_process_data_different_hf_types():
    """Test that we can pass hashlib.md5 as hf, expecting different hash length."""
    data = b"test data for md5 hashing"
    # Note: process_data_for_snapshot's default is sha256. We're testing if providing a different one works.
    # The `hf` parameter of `fastcdc` itself expects a callable (constructor). Our wrapper ensures this.
    chunks_md5 = process_data_for_snapshot(data, hf=hashlib.md5)
    assert len(chunks_md5) >= 1
    for ch_hash, _, _, _ in chunks_md5:
        assert isinstance(ch_hash, str) and len(ch_hash) == 32, "MD5 hash length should be 32"

    # Verify MD5 hash content (optional, but good for sanity)
    zstd_decompressor = zstandard.ZstdDecompressor()
    reconstructed_data_list = []
    for ch_hash, compressed_data, _, _ in chunks_md5:
        decompressed_data = zstd_decompressor.decompress(compressed_data)
        assert hashlib.md5(decompressed_data).hexdigest() == ch_hash
        reconstructed_data_list.append(decompressed_data)
    assert b"".join(reconstructed_data_list) == data

# Potential for ChunkingError (though hard to deterministically trigger without mocking file ops)
# For now, assume ChunkingError is implicitly tested by successful runs.
# If specific error conditions within chunking_utils need testing (e.g., disk full during temp file write),
# that would require mocking. 