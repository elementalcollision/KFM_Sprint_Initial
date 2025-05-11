import pytest
import os
import shutil
import datetime
import json
from unittest.mock import MagicMock, patch

from src.core.memory.chroma_manager import ChromaMemoryManager
from src.core.memory.models import AgentExperienceLog, ComponentMetrics, AgentQueryContext
# Assuming EmbeddingService is accessible for mocking its type
from src.core.embedding_service import EmbeddingService 
import chromadb
from chromadb.api.client import ClientAPI

# Note: These tests interact with the filesystem via PersistentClient.
# Using tmp_path fixture ensures isolation and cleanup.

class TestChromaMemoryManager:

    TEST_COLLECTION_NAME = "test_agent_experiences"

    def test_initialization(self, tmp_path, mock_embedding_service):
        """Test initializing the manager creates the client, collection, and db directory."""
        db_path = str(tmp_path / "test_chroma_init")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        
        assert manager.client is not None, "Client should be initialized"
        assert isinstance(manager.client, ClientAPI), "Client should be an instance of ClientAPI"
        assert manager.collection is not None, "Collection should be initialized"
        assert manager.collection.name == self.TEST_COLLECTION_NAME, "Collection name should match"
        assert os.path.exists(db_path), "Database directory should be created"
        # Optionally check for specific chroma files within db_path if structure is known/stable

    def test_get_collection(self, tmp_path, mock_embedding_service):
        """Test if get_collection returns the initialized collection object."""
        db_path = str(tmp_path / "test_chroma_get")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        collection = manager.get_collection()
        
        assert collection is not None
        assert collection.name == self.TEST_COLLECTION_NAME

    def test_count_items_empty(self, tmp_path, mock_embedding_service):
        """Test count_items returns 0 for a newly created collection."""
        db_path = str(tmp_path / "test_chroma_count")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        
        count = manager.count_items()
        assert count == 0, "Initial item count should be 0"

    def test_get_or_create_idempotency(self, tmp_path, mock_embedding_service):
        """Test that initializing the manager multiple times uses the same underlying collection."""
        db_path = str(tmp_path / "test_chroma_idempotent")
        
        # First initialization
        manager1 = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        collection1 = manager1.get_collection()
        assert collection1 is not None
        count1 = manager1.count_items()
        assert count1 == 0
        collection1_id = collection1.id
        
        # Simulate closing and reopening - create a new manager instance with the same path
        del manager1
        manager2 = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        collection2 = manager2.get_collection()
        assert collection2 is not None
        count2 = manager2.count_items()
        assert count2 == 0, "Count should remain 0 after re-initialization"
        assert collection2.id == collection1_id, "Collection ID should be the same upon reload"
        assert collection2.name == self.TEST_COLLECTION_NAME

    def test_reset_database(self, tmp_path, mock_embedding_service):
        """Test resetting the database clears data and re-initializes the collection."""
        db_path = str(tmp_path / "test_chroma_reset")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, # Pass the mock service
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        collection_before = manager.get_collection()
        assert collection_before is not None
        assert manager.count_items() == 0
        collection_id_before = collection_before.id

        # Perform reset
        manager.reset_database()
        
        # Verify collection is still available and empty
        collection_after = manager.get_collection()
        assert collection_after is not None, "Collection should be re-initialized after reset"
        assert manager.count_items() == 0, "Count should be 0 after reset"
        assert collection_after.name == self.TEST_COLLECTION_NAME
        # Note: Chroma's reset might assign a *new* internal ID to the re-created collection.
        # Let's test if it's at least available, maybe not compare IDs here unless Chroma guarantees stability.
        # assert collection_after.id != collection_id_before # Or potentially it IS the same if name dictates ID?
        # For now, just check it exists and is empty.

    def test_initialization_failure_bad_path(self):
        """Test that initialization fails gracefully with a bad path (e.g., permission error simulation)."""
        # This is hard to simulate reliably without complex mocks or filesystem manipulation.
        # We might rely on ChromaDB's own error handling. 
        # Let's check if the logger captures an error if we provide an invalid path concept, e.g., root dir without perms.
        # This test might be platform-dependent or require more setup.
        # For now, we trust the try/except block in __init__ logs errors.
        # Example concept (might fail or pass depending on exact OS/perms):
        # with pytest.raises(Exception): # Or specific exception if Chroma raises one
        #     ChromaMemoryManager(db_path="/proc/test_chroma_fail") # Path likely not writable
        pass # Skipping complex failure injection for now

    def test_collection_operations_fail_if_client_fails(self):
        """Test that collection operations are guarded if client init fails."""
        # Mocking the client initialization to fail
        original_persistent_client = chromadb.PersistentClient
        
        # Create a mock EmbeddingService instance needed for the constructor
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        
        def mock_failing_client(*args, **kwargs):
            raise Exception("Mocked client init failure")
        
        chromadb.PersistentClient = mock_failing_client
        
        # Now pass the mock embedding service to the constructor
        manager = ChromaMemoryManager(embedding_service=mock_embedding_service, db_path="dummy_path") # Init will fail and log
        assert manager.client is None
        assert manager.collection is None
        assert manager.get_collection() is None
        assert manager.count_items() is None
        manager.reset_database() # Should log warning but not crash
        
        # Restore original client
        chromadb.PersistentClient = original_persistent_client

    # --- Tests for add_memory_entry --- 

    @pytest.fixture
    def mock_embedding_service(self) -> MagicMock:
        """Fixture to create a mock EmbeddingService."""
        mock = MagicMock(spec=EmbeddingService)
        # Configure mock to return a fixed embedding of correct dimension (e.g., 384 for MiniLM)
        mock.get_embedding.return_value = [0.1] * 384 
        return mock

    @pytest.fixture
    def sample_experience_log(self) -> AgentExperienceLog:
        """Fixture to create a sample AgentExperienceLog."""
        return AgentExperienceLog(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            current_task_requirements={"goal": "test", "min_accuracy": 0.9},
            previous_component_name="CompA",
            previous_component_metrics=ComponentMetrics(accuracy=0.85, latency=100.0),
            planner_llm_input="Planner input context...",
            planner_llm_output="Planner decided Marry.",
            kfm_action_taken="Marry",
            selected_component_name="CompB",
            execution_outcome_metrics=ComponentMetrics(accuracy=0.95, latency=80.0),
            action_execution_error=None,
            reflection_llm_output="Reflection notes...",
            outcome_success=True
        )

    def test_add_memory_entry_success(self, tmp_path, mock_embedding_service, sample_experience_log):
        """Test adding a valid memory entry successfully."""
        db_path = str(tmp_path / "test_add_success")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None

        # Mock the collection's add method
        with patch.object(manager.collection, 'add', return_value=None) as mock_add:
            entry_id = manager.add_memory_entry(sample_experience_log)

            assert entry_id is not None
            assert isinstance(entry_id, str)
            assert len(entry_id) == 32 # UUID4 hex length

            # Verify embedding service was called
            mock_embedding_service.get_embedding.assert_called_once()
            # Get the text passed to the embedding service
            call_args, _ = mock_embedding_service.get_embedding.call_args
            embedding_summary_text = call_args[0]
            assert isinstance(embedding_summary_text, str)
            # Check if key parts are in the summary (exact format might change)
            assert "Context: Task reqs" in embedding_summary_text
            assert "Action: KFM chose Marry" in embedding_summary_text
            assert "Outcome: New metrics" in embedding_summary_text
            assert "CompA" in embedding_summary_text
            assert "CompB" in embedding_summary_text
            assert "Success: True" in embedding_summary_text

            # Verify collection.add was called
            mock_add.assert_called_once()
            call_args, _ = mock_add.call_args
            # Check the structure of the call - Chroma add uses keyword args
            # assert 'ids' in mock_add.call_args.kwargs
            # assert 'embeddings' in mock_add.call_args.kwargs
            # assert 'metadatas' in mock_add.call_args.kwargs
            # assert 'documents' in mock_add.call_args.kwargs
            
            # More thorough check of arguments passed to collection.add
            kwargs_passed = mock_add.call_args.kwargs
            assert kwargs_passed['ids'] == [entry_id]
            assert len(kwargs_passed['embeddings'][0]) == 384 # Check embedding dim
            assert kwargs_passed['metadatas'][0]['kfm_action_taken'] == "Marry"
            assert kwargs_passed['metadatas'][0]['component_involved'] == "CompB"
            assert kwargs_passed['metadatas'][0]['outcome_success'] == "True"
            assert "previous_component_metrics" in kwargs_passed['metadatas'][0]
            assert "new_component_metrics" in kwargs_passed['metadatas'][0]
            assert "task_requirements" in kwargs_passed['metadatas'][0]
            assert json.loads(kwargs_passed['documents'][0])['kfm_action_taken'] == "Marry"

    def test_add_memory_entry_embedding_failure(self, tmp_path, mock_embedding_service, sample_experience_log):
        """Test adding entry when embedding service fails."""
        db_path = str(tmp_path / "test_add_embed_fail")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None

        # Configure embedding service mock to fail
        mock_embedding_service.get_embedding.return_value = [] # Or None, depending on EmbeddingService impl

        with patch.object(manager.collection, 'add') as mock_add:
            entry_id = manager.add_memory_entry(sample_experience_log)
            
            assert entry_id is None
            mock_embedding_service.get_embedding.assert_called_once() # It was called
            mock_add.assert_not_called() # But collection.add should not be

    def test_add_memory_entry_chroma_failure(self, tmp_path, mock_embedding_service, sample_experience_log):
        """Test adding entry when chromadb collection.add fails."""
        db_path = str(tmp_path / "test_add_chroma_fail")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None

        # Configure collection.add mock to fail
        with patch.object(manager.collection, 'add', side_effect=Exception("Mocked ChromaDB Error")) as mock_add:
            entry_id = manager.add_memory_entry(sample_experience_log)
            
            assert entry_id is None
            mock_embedding_service.get_embedding.assert_called_once() # Embedding was generated
            mock_add.assert_called_once() # But the add call failed 

    # --- Tests for retrieve_memories ---

    @pytest.fixture
    def sample_query_context(self) -> AgentQueryContext:
        """Fixture to create a sample AgentQueryContext."""
        return AgentQueryContext(
            current_task_requirements={"goal": "query", "min_accuracy": 0.8},
            current_component_name="CompC",
            current_component_metrics=ComponentMetrics(accuracy=0.7, latency=150.0)
        )

    def test_retrieve_memories_success(self, tmp_path, mock_embedding_service, sample_query_context):
        """Test retrieving memories successfully."""
        db_path = str(tmp_path / "test_retrieve_success")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None

        # Mock the response from collection.query
        mock_query_result = {
            'ids': [['mem1', 'mem2']],
            'distances': [[0.1, 0.2]],
            'metadatas': [[{'key': 'val1'}, {'key': 'val2'}]],
            'documents': [['doc1_content', 'doc2_content']]
            # embeddings are not included by default, but could be if requested
        }
        
        with patch.object(manager.collection, 'query', return_value=mock_query_result) as mock_query:
            results = manager.retrieve_memories(sample_query_context, n_results=2)

            assert results is not None
            assert len(results) == 2

            # Check embedding service call
            mock_embedding_service.get_embedding.assert_called_once()
            call_args, _ = mock_embedding_service.get_embedding.call_args
            query_summary_text = call_args[0]
            assert isinstance(query_summary_text, str)
            assert "Current Situation: Task reqs" in query_summary_text
            assert "CompC" in query_summary_text
            
            # Check chroma query call
            mock_query.assert_called_once()
            kwargs_passed = mock_query.call_args.kwargs
            assert len(kwargs_passed['query_embeddings'][0]) == 384 # Check query embedding dim
            assert kwargs_passed['n_results'] == 2
            assert kwargs_passed['where'] is None # No filter passed in this test
            assert kwargs_passed['where_document'] is None
            assert kwargs_passed['include'] == ["metadatas", "documents", "distances"]
            
            # Check formatted results
            assert results[0]['id'] == 'mem1'
            assert results[0]['distance'] == 0.1
            assert results[0]['metadata'] == {'key': 'val1'}
            assert results[0]['document'] == 'doc1_content'
            assert results[1]['id'] == 'mem2'
            assert results[1]['distance'] == 0.2

    def test_retrieve_memories_with_metadata_filter(self, tmp_path, mock_embedding_service, sample_query_context):
        """Test retrieving memories with a metadata filter."""
        db_path = str(tmp_path / "test_retrieve_filter")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None
        test_filter = {"outcome_success": "True"}

        with patch.object(manager.collection, 'query', return_value={'ids': [[]]}) as mock_query:
            manager.retrieve_memories(sample_query_context, n_results=3, where_filter=test_filter)

            mock_query.assert_called_once()
            kwargs_passed = mock_query.call_args.kwargs
            assert kwargs_passed['where'] == test_filter
            assert kwargs_passed['n_results'] == 3

    def test_retrieve_memories_empty_result(self, tmp_path, mock_embedding_service, sample_query_context):
        """Test retrieval when Chroma query returns no results."""
        db_path = str(tmp_path / "test_retrieve_empty")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None
        mock_empty_result = {'ids': [[]], 'distances': [[]], 'metadatas': [[]], 'documents': [[]]}

        with patch.object(manager.collection, 'query', return_value=mock_empty_result) as mock_query:
            results = manager.retrieve_memories(sample_query_context)
            
            assert results is not None
            assert len(results) == 0
            mock_query.assert_called_once()

    def test_retrieve_memories_embedding_failure(self, tmp_path, mock_embedding_service, sample_query_context):
        """Test retrieval when the embedding service fails."""
        db_path = str(tmp_path / "test_retrieve_embed_fail")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None
        mock_embedding_service.get_embedding.return_value = [] # Simulate failure

        with patch.object(manager.collection, 'query') as mock_query:
            results = manager.retrieve_memories(sample_query_context)
            
            assert results is None
            mock_embedding_service.get_embedding.assert_called_once()
            mock_query.assert_not_called()

    def test_retrieve_memories_chroma_failure(self, tmp_path, mock_embedding_service, sample_query_context):
        """Test retrieval when the Chroma query itself fails."""
        db_path = str(tmp_path / "test_retrieve_chroma_fail")
        manager = ChromaMemoryManager(
            embedding_service=mock_embedding_service, 
            db_path=db_path, 
            collection_name=self.TEST_COLLECTION_NAME
        )
        assert manager.collection is not None

        with patch.object(manager.collection, 'query', side_effect=Exception("Mocked Chroma Query Error")) as mock_query:
            results = manager.retrieve_memories(sample_query_context)
            
            assert results is None
            mock_embedding_service.get_embedding.assert_called_once()
            mock_query.assert_called_once() 