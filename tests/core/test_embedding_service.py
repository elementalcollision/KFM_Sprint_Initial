import pytest
from src.core.embedding_service import EmbeddingService
import logging

# Configure basic logging for tests to see service logs if needed
# logging.basicConfig(level=logging.INFO)

class TestEmbeddingService:

    MODEL_NAME = "all-MiniLM-L6-v2" # A commonly used and relatively small model
    EXPECTED_DIMENSIONALITY = 384 # Dimensionality for all-MiniLM-L6-v2

    @pytest.fixture(scope="class")
    def service(self) -> EmbeddingService:
        """Fixture to provide an EmbeddingService instance for the test class."""
        return EmbeddingService(model_name=self.MODEL_NAME)

    def test_init_valid_model(self, service: EmbeddingService):
        """Test if the service initializes correctly with a valid model name."""
        assert service is not None
        assert service.model is not None
        assert service.get_model_dimensionality() == self.EXPECTED_DIMENSIONALITY

    def test_init_invalid_model_name(self):
        """Test if initializing with an invalid model name raises an error."""
        with pytest.raises(Exception): # SentenceTransformer might raise various errors (OSError, ValueError, etc.)
            EmbeddingService(model_name="this-is-not-a-real-model-name-at-all")

    def test_get_embedding_valid_input(self, service: EmbeddingService):
        """Test get_embedding with a single valid text input."""
        text = "This is a test sentence."
        embedding = service.get_embedding(text)
        assert isinstance(embedding, list)
        assert len(embedding) == self.EXPECTED_DIMENSIONALITY
        assert all(isinstance(x, float) for x in embedding)

    def test_get_embeddings_valid_input(self, service: EmbeddingService):
        """Test get_embeddings with a list of valid text inputs."""
        texts = ["First test sentence.", "Second test sentence, slightly longer."]
        embeddings = service.get_embeddings(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert isinstance(embedding, list)
            assert len(embedding) == self.EXPECTED_DIMENSIONALITY
            assert all(isinstance(x, float) for x in embedding)

    def test_get_embedding_empty_string(self, service: EmbeddingService):
        """Test get_embedding with an empty string input."""
        text = ""
        embedding = service.get_embedding(text)
        # Based on current implementation, it returns an empty list for invalid input
        assert isinstance(embedding, list)
        assert len(embedding) == 0

    def test_get_embedding_none_input(self, service: EmbeddingService):
        """Test get_embedding with None as input."""
        # Pytest will show a TypeError from SentenceTransformer if not handled,
        # but our service currently catches general Exception.
        # The current service implementation logs a warning and returns [].
        embedding = service.get_embedding(None) # type: ignore 
        assert isinstance(embedding, list)
        assert len(embedding) == 0
        
    def test_get_embeddings_empty_list(self, service: EmbeddingService):
        """Test get_embeddings with an empty list input."""
        texts = []
        embeddings = service.get_embeddings(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == 0

    def test_get_embeddings_list_with_empty_string(self, service: EmbeddingService):
        """Test get_embeddings with a list containing an empty string."""
        texts = ["Valid sentence.", "", "Another valid one."]
        # SentenceTransformer might handle empty strings in a batch by producing a zero vector or similar.
        # Our service does not currently pre-filter empty strings from batches passed to model.encode()
        # Let's check the behavior.
        embeddings = service.get_embeddings(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        assert len(embeddings[0]) == self.EXPECTED_DIMENSIONALITY
        # The behavior of SentenceTransformer for an empty string within a batch needs to be confirmed.
        # It often produces a valid embedding (e.g., zeros or some other representation).
        # For now, let's just check it produces an embedding of the correct dimension.
        assert len(embeddings[1]) == self.EXPECTED_DIMENSIONALITY 
        assert len(embeddings[2]) == self.EXPECTED_DIMENSIONALITY

    def test_get_embeddings_list_with_none(self, service: EmbeddingService):
        """Test get_embeddings with a list containing None."""
        texts = ["Valid sentence.", None, "Another valid one."] # type: ignore
        # Current implementation of get_embeddings checks `all(isinstance(t, str) for t in texts)`
        embeddings = service.get_embeddings(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == 0 # Returns empty list due to the type check

    def test_get_model_dimensionality(self, service: EmbeddingService):
        """Test get_model_dimensionality returns the correct integer."""
        dimensionality = service.get_model_dimensionality()
        assert isinstance(dimensionality, int)
        assert dimensionality == self.EXPECTED_DIMENSIONALITY

