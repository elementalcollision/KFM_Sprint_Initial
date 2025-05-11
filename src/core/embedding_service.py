from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name: str):
        """
        Initializes the embedding service with a specified sentence-transformer model.

        Args:
            model_name (str): The name of the sentence-transformer model to use.
        """
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Successfully loaded SentenceTransformer model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model '{model_name}': {e}")
            # Potentially re-raise or handle appropriately depending on desired resilience
            raise

    def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for the given text.

        Args:
            text (str): The input text to embed.

        Returns:
            list[float]: The embedding vector, or an empty list if an error occurs.
        """
        if not text or not isinstance(text, str):
            logger.warning("Invalid input text for embedding. Must be a non-empty string.")
            # Depending on strictness, could return None, raise ValueError, or return a zero vector.
            # Returning empty list for now as a placeholder for error/invalid state.
            return [] 
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()  # Convert numpy array to list
        except Exception as e:
            logger.error(f"Error generating embedding for text \"{text[:50]}...\": {e}")
            return []

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a list of texts.

        Args:
            texts (list[str]): A list of input texts to embed.

        Returns:
            list[list[float]]: A list of embedding vectors. Returns empty list for invalid inputs or errors.
        """
        if not texts or not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            logger.warning("Invalid input texts for embedding. Must be a non-empty list of strings.")
            return []
        try:
            embeddings = self.model.encode(texts)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error generating embeddings for batch of {len(texts)} texts: {e}")
            return []

    def get_model_dimensionality(self) -> int | None:
        """
        Gets the dimensionality of the embeddings produced by the loaded model.

        Returns:
            int | None: The dimensionality, or None if the model is not loaded properly.
        """
        try:
            return self.model.get_sentence_embedding_dimension()
        except AttributeError:
            logger.error("Model not loaded or does not have 'get_sentence_embedding_dimension' method.")
            return None 