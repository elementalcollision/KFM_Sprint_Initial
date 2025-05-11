import chromadb
from chromadb.config import Settings as ChromaSettings
import logging
import os
import uuid
import json
from typing import Optional, Dict, Any, List

# Assuming models are in the same directory or accessible via path
from .models import AgentExperienceLog, ComponentMetrics, AgentQueryContext
from ..embedding_service import EmbeddingService # Adjusted import relative path

# Assuming config models are accessible, adjust import as necessary
# from src.config.models import MemoryConfig 

logger = logging.getLogger(__name__)

# Defaults moved here for clarity, actual values should come from config
DEFAULT_DB_PATH = "./kfm_chroma_db" 
DEFAULT_COLLECTION_NAME = "agent_experiences"

class ChromaMemoryManager:
    """Manages interaction with a persistent ChromaDB vector database for agent memory."""

    def __init__(self, 
                 embedding_service: EmbeddingService, 
                 db_path: str = DEFAULT_DB_PATH, 
                 collection_name: str = DEFAULT_COLLECTION_NAME):
        """
        Initializes the ChromaDB client, embedding service, and loads/creates the specified collection.

        Args:
            embedding_service (EmbeddingService): Instance of the embedding service.
            db_path (str): Path to the directory where ChromaDB should persist data.
            collection_name (str): Name of the collection to use for agent memories.
        """
        # Ensure the directory exists
        os.makedirs(db_path, exist_ok=True)
        
        self.db_path = db_path
        self.collection_name = collection_name
        self.embedding_service = embedding_service
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection: Optional[chromadb.Collection] = None
        
        # For testing purposes, we allow reset. In production, this might be configurable.
        self.chroma_settings = ChromaSettings(allow_reset=True)
        
        self._initialize_client()
        if self.client: # Only proceed if client initialization succeeded
            self._load_or_create_collection()

    def _initialize_client(self):
        """Initializes the PersistentClient."""
        try:
            self.client = chromadb.PersistentClient(
                path=self.db_path, 
                settings=self.chroma_settings 
            )
            logger.info(f"ChromaDB PersistentClient initialized at path: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB PersistentClient at {self.db_path}: {e}", exc_info=True)
            self.client = None # Ensure client is None on failure
            # Re-raising might be appropriate depending on application entry point handling
            # raise 

    def _load_or_create_collection(self):
        """Loads an existing collection or creates it if it doesn't exist."""
        if not self.client:
            logger.error("Chroma client not initialized. Cannot load/create collection.")
            return

        try:
            # Consider adding metadata like hnsw:space if needed for similarity metric choice
            # metadata={"hnsw:space": "cosine"} # l2 is default
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            logger.info(f"Successfully loaded/created Chroma collection: '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to load/create Chroma collection '{self.collection_name}': {e}", exc_info=True)
            self.collection = None # Ensure collection is None on failure
            # Re-raising might be appropriate
            # raise

    def get_collection(self) -> Optional[chromadb.Collection]:
        """Returns the managed Chroma collection object, or None if not initialized."""
        if not self.collection:
             logger.warning(f"Collection '{self.collection_name}' is not available.")
        return self.collection

    def count_items(self) -> Optional[int]:
        """Returns the number of items in the collection, or None if unavailable."""
        if self.collection:
            try:
                return self.collection.count()
            except Exception as e:
                logger.error(f"Error counting items in collection '{self.collection_name}': {e}", exc_info=True)
                return None
        logger.warning("Count failed: Collection not available.")
        return None

    def _create_embedding_summary(self, experience_data: AgentExperienceLog) -> str:
        """Creates a concise textual summary of the experience for embedding."""
        # Simplified example - needs refinement based on desired semantic capture
        parts = []
        task_req_summary = json.dumps(experience_data.current_task_requirements, sort_keys=True)
        prev_metrics_summary = experience_data.previous_component_metrics.model_dump_json() if experience_data.previous_component_metrics else "None"
        new_metrics_summary = experience_data.execution_outcome_metrics.model_dump_json() if experience_data.execution_outcome_metrics else "None"
        
        parts.append(f"Context: Task reqs {task_req_summary}. Previous component {experience_data.previous_component_name} metrics {prev_metrics_summary}.")
        parts.append(f"Action: KFM chose {experience_data.kfm_action_taken} -> selected {experience_data.selected_component_name}.")
        parts.append(f"Outcome: New metrics {new_metrics_summary}. Success: {experience_data.outcome_success}. Error: {experience_data.action_execution_error or 'None'}.")
        if experience_data.reflection_llm_output:
            parts.append(f"Reflection: {experience_data.reflection_llm_output[:100]}...") # Truncate reflection
            
        summary = " ".join(parts)
        # TODO: Consider max length for summary?
        return summary

    def add_memory_entry(self, experience_data: AgentExperienceLog) -> Optional[str]:
        """Adds a new agent experience log to the ChromaDB collection."""
        if not self.collection:
            logger.error("Cannot add memory entry: Chroma collection is not available.")
            return None
        if not self.embedding_service:
             logger.error("Cannot add memory entry: Embedding service is not available.")
             return None

        try:
            chroma_id = uuid.uuid4().hex
            
            # 1. Create summary for embedding
            experience_summary = self._create_embedding_summary(experience_data)
            if not experience_summary:
                logger.warning(f"Skipping memory entry: Could not generate summary for experience.")
                return None
                
            # 2. Get embedding
            embedding = self.embedding_service.get_embedding(experience_summary)
            if not embedding:
                logger.error(f"Skipping memory entry {chroma_id}: Failed to generate embedding.")
                return None

            # 3. Prepare metadata
            metadata = {
                "timestamp": experience_data.timestamp.isoformat(),
                "kfm_action_taken": experience_data.kfm_action_taken,
                "component_involved": experience_data.selected_component_name or experience_data.previous_component_name or "Unknown",
                "previous_component_metrics": experience_data.previous_component_metrics.model_dump_json() if experience_data.previous_component_metrics else None,
                "new_component_metrics": experience_data.execution_outcome_metrics.model_dump_json() if experience_data.execution_outcome_metrics else None,
                "task_requirements": json.dumps(experience_data.current_task_requirements, sort_keys=True),
                "planner_llm_input_preview": experience_data.planner_llm_input[:200], # Store preview
                "planner_llm_output": experience_data.planner_llm_output,
                "reflection_llm_output": experience_data.reflection_llm_output,
                "outcome_success": str(experience_data.outcome_success),
                "action_execution_error": experience_data.action_execution_error,
                # Storing the summary used for embedding in metadata can be useful for debugging/inspection
                "experience_summary_embedded": experience_summary 
            }
            # Filter out None values from metadata before storing
            metadata_cleaned = {k: v for k, v in metadata.items() if v is not None}

            # 4. Prepare document (using JSON of the whole input log)
            document = experience_data.model_dump_json()

            # 5. Add to Chroma collection
            self.collection.add(
                ids=[chroma_id],
                embeddings=[embedding],
                metadatas=[metadata_cleaned],
                documents=[document]
            )
            logger.info(f"Added memory entry with ID: {chroma_id}")
            return chroma_id

        except Exception as e:
            logger.error(f"Failed to add memory entry: {e}", exc_info=True)
            return None

    def _create_query_summary(self, query_context: AgentQueryContext) -> str:
        """Creates a concise textual summary from the query context for embedding."""
        if query_context.explicit_query_text:
            # If explicit query text is provided, use it directly
            return query_context.explicit_query_text
        
        # Otherwise, construct from context fields
        parts = []
        task_req_summary = json.dumps(query_context.current_task_requirements, sort_keys=True)
        current_metrics_summary = query_context.current_component_metrics.model_dump_json() if query_context.current_component_metrics else "None"
        
        parts.append(f"Current Situation: Task reqs {task_req_summary}.")
        if query_context.current_component_name:
             parts.append(f"Current component {query_context.current_component_name} metrics {current_metrics_summary}.")
        else:
             parts.append("No current component active.")
        
        # Add other context elements if available in AgentQueryContext
        # if query_context.last_action: parts.append(f"Last action was {query_context.last_action}.")
        
        summary = " ".join(parts)
        # TODO: Consider max length for summary?
        return summary

    def retrieve_memories(
        self,
        query_context: AgentQueryContext,
        n_results: int = 5,
        where_filter: Optional[Dict[str, Any]] = None,
        where_document_filter: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves memories similar to the provided context, with optional filtering.

        Args:
            query_context: The agent's current context used to generate the query.
            n_results: Maximum number of results to return.
            where_filter: Optional ChromaDB metadata filter (e.g., {"outcome_success": "True"}).
            where_document_filter: Optional ChromaDB document content filter (e.g., {"$contains":"error"}).

        Returns:
            A list of retrieved memories, each as a dict containing 
            {'id', 'distance', 'metadata', 'document'}, or None if retrieval fails.
        """
        if not self.collection or not self.embedding_service:
            logger.error("Cannot retrieve memories: Chroma collection or Embedding service is not available.")
            return None

        try:
            # 1. Create query text and embedding
            query_text = self._create_query_summary(query_context)
            if not query_text:
                 logger.warning("Cannot retrieve memories: Failed to generate query summary text.")
                 return None
                 
            query_embedding = self.embedding_service.get_embedding(query_text)
            if not query_embedding:
                logger.error("Cannot retrieve memories: Failed to generate query embedding.")
                return None

            # 2. Query Chroma collection
            logger.debug(f"Querying Chroma with embedding (first 5 dims): {query_embedding[:5]}..., n_results={n_results}, where={where_filter}, where_doc={where_document_filter}")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,             # Pass through the filters
                where_document=where_document_filter,
                include=["metadatas", "documents", "distances"] # Ensure we get needed fields
            )
            logger.debug(f"Chroma query returned: {results}")

            # 3. Process and format results
            if not results or not results.get('ids') or not results['ids'][0]:
                logger.info("Memory retrieval query returned no results.")
                return [] # Return empty list for no results

            # Chroma returns lists of lists, one inner list per query embedding. We have one query.
            retrieved_ids = results['ids'][0]
            distances = results.get('distances', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            documents = results.get('documents', [[]])[0]
            
            formatted_results = []
            for i, mem_id in enumerate(retrieved_ids):
                formatted_results.append({
                    "id": mem_id,
                    "distance": distances[i] if i < len(distances) else None,
                    "metadata": metadatas[i] if i < len(metadatas) else None,
                    "document": documents[i] if i < len(documents) else None,
                })
                
            logger.info(f"Retrieved {len(formatted_results)} memories.")
            return formatted_results

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}", exc_info=True)
            return None

    def reset_database(self):
        """
        Resets the entire ChromaDB database associated with the client's path.
        WARNING: This is a destructive operation and will delete ALL collections in the path.
        """
        if self.client:
            try:
                logger.warning(f"Resetting ChromaDB at path '{self.db_path}'. THIS WILL DELETE ALL COLLECTIONS IN THIS PATH.")
                self.client.reset() # Resets the entire database associated with the client
                # After reset, the collection object held is no longer valid.
                self.collection = None 
                logger.info(f"ChromaDB at '{self.db_path}' has been reset. Re-initializing collection...")
                # Attempt to re-create the primary collection immediately
                self._load_or_create_collection()
            except Exception as e:
                logger.error(f"Error resetting ChromaDB: {e}", exc_info=True)
                self.collection = None # Ensure collection is None after failed reset
        else:
            logger.warning("Chroma client not initialized. Cannot reset database.")

    # Example of how configuration would be passed in real usage:
    # @classmethod
    # def from_config(cls, config: MemoryConfig) -> 'ChromaMemoryManager':
    #     return cls(db_path=config.vector_db_path, collection_name=config.collection_name) 