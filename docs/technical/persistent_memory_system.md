# KFM Agent Persistent Memory System

## A. Overview

The KFM Agent Persistent Memory System enables the agent to store, retrieve, and learn from past experiences. This capability allows the agent to make more informed decisions over time by leveraging historical context. The system is designed to be modular and uses a vector database for efficient semantic search of past experiences.

**High-Level Architecture:**

The persistent memory system primarily involves the following components in a sequence:

1.  **Experience Logging:** After an action is taken and its outcome observed, an `AgentExperienceLog` is created.
2.  **`EmbeddingService`:** This service takes textual summaries of experiences and converts them into dense vector embeddings.
3.  **`ChromaMemoryManager`:** This manager interfaces with ChromaDB. It uses the `EmbeddingService` to get embeddings for new experiences and stores them along with their metadata. It also handles querying ChromaDB to retrieve relevant past experiences based on the current agent context.
4.  **ChromaDB:** A persistent vector database that stores the experience embeddings and their associated metadata, allowing for efficient similarity searches.
5.  **`KFMPlannerLlm`:** The KFM Planner incorporates retrieved memories into its decision-making process by including them in the prompt sent to its underlying language model.

**Key Benefits:**

*   **Learning from Past Successes/Failures:** Enables the agent to recall what worked or didn't in similar situations.
*   **Improved Decision Making:** Provides richer context to the planner, potentially leading to better KFM actions.
*   **Adaptability:** Allows the agent to adapt its strategies based on accumulated knowledge.

## B. Components

### 1. `EmbeddingService`

*   **Location:** `src/core/embedding_service.py`
*   **Role:** Responsible for generating vector embeddings from textual descriptions of agent experiences or query contexts. These embeddings are numerical representations that capture the semantic meaning of the text, enabling similarity comparisons.
*   **Selected Model:** The service utilizes models from the `sentence-transformers` library. The default model is typically a general-purpose model like `"all-MiniLM-L6-v2"` (or as configured in `verification_config.yaml` via `memory.embedding_model_name`). Sentence-transformer models are chosen for their balance of performance and efficiency in generating high-quality sentence and paragraph embeddings.
*   **Key Methods:**
    *   `__init__(self, model_name: str)`: Initializes the service, loading the specified sentence-transformer model.
    *   `get_embedding(self, text: str) -> list[float]`: Generates an embedding for a single input text.
    *   `get_embeddings(self, texts: list[str]) -> list[list[float]]`: Generates embeddings for a batch of input texts.
    *   `get_model_dimensionality(self) -> int | None`: Returns the dimensionality of the embeddings produced by the loaded model.

### 2. `ChromaMemoryManager`

*   **Location:** `src/core/memory/chroma_manager.py`
*   **Role:** Acts as the primary interface for the agent's long-term memory. It handles the storage of `AgentExperienceLog` instances into a persistent ChromaDB vector database and the retrieval of relevant past experiences based on semantic similarity to the current context.
*   **Database:**
    *   Uses **ChromaDB** as the vector database.
    *   Operates with a `PersistentClient`, meaning data is saved to disk at the path specified in the configuration (`memory.vector_db_path`).
    *   Organizes data within a named **collection** (configurable via `memory.collection_name`).
*   **Key Methods:**
    *   `__init__(self, embedding_service: EmbeddingService, db_path: str, collection_name: str)`: Initializes the manager, sets up the ChromaDB client, and loads or creates the specified collection.
    *   `add_memory_entry(self, experience_data: AgentExperienceLog) -> Optional[str]`:
        1.  Takes an `AgentExperienceLog` object.
        2.  Generates a textual summary of the experience using `_create_embedding_summary()`.
        3.  Uses the `EmbeddingService` to create a vector embedding from this summary.
        4.  Stores the original `AgentExperienceLog` (as JSON) as the document, the embedding, and a rich set of metadata into the ChromaDB collection. Returns the ID of the stored entry.
    *   `retrieve_memories(self, query_context: AgentQueryContext, n_results: int, where_filter: Optional[Dict], where_document_filter: Optional[Dict]) -> Optional[List[Dict[str, Any]]`:
        1.  Takes an `AgentQueryContext` object.
        2.  Generates a textual summary of the query context using `_create_query_summary()`.
        3.  Uses the `EmbeddingService` to create a vector embedding from this query summary.
        4.  Queries the ChromaDB collection for `n_results` most similar entries based on the query embedding.
        5.  Supports optional metadata (`where_filter`) and document content (`where_document_filter`) filtering.
        6.  Returns a list of retrieved memories, including their documents, metadata, and distances (similarity scores).
    *   `_create_embedding_summary(self, experience_data: AgentExperienceLog) -> str`: Internal method to create a concise textual summary of an `AgentExperienceLog` specifically for generating its embedding. This summary aims to capture the key semantic aspects of the experience.
    *   `_create_query_summary(self, query_context: AgentQueryContext) -> str`: Internal method to create a textual summary from an `AgentQueryContext` for generating the query embedding.
    *   `get_collection() -> Optional[chromadb.Collection]`: Returns the underlying ChromaDB collection object.
    *   `count_items() -> Optional[int]`: Returns the total number of items in the collection.
    *   `reset_database()`: Clears all data from the configured ChromaDB persistent storage path (used primarily for testing).
*   **Data Schema for Stored Memories (Metadata):** When an `AgentExperienceLog` is stored, the following metadata is typically saved alongside its embedding and the full log (as a JSON document):
    *   `timestamp`: ISO format timestamp of the experience.
    *   `kfm_action_taken`: The KFM action decided by the planner (e.g., "Marry", "Kill").
    *   `component_involved`: The name of the component that was primarily involved in the action.
    *   `previous_component_metrics`: JSON string of metrics for the component before the action.
    *   `new_component_metrics`: JSON string of metrics for the component after the action.
    *   `task_requirements`: JSON string of the task requirements active during the experience.
    *   `planner_llm_input_preview`: A preview of the input to the KFM planner.
    *   `planner_llm_output`: The raw JSON output from the KFM planner.
    *   `reflection_llm_output`: Output from any reflection process (if applicable).
    *   `outcome_success`: Boolean string ("True" or "False") indicating if the action was deemed successful.
    *   `action_execution_error`: Any error message from the execution of the action.
    *   `experience_summary_embedded`: The actual textual summary that was used to generate the embedding (useful for debugging).

### 3. `KFMPlannerLlm` Integration

*   **Location:** `src/core/kfm_planner_llm.py`
*   **Role in Memory System:** The `KFMPlannerLlm` is the primary consumer of the persistent memory. It leverages past experiences to inform its current decision-making process.
*   **Memory Utilization in `_generate_prompt()`:**
    1.  **`AgentQueryContext` Creation:** Before querying memory, the planner constructs an `AgentQueryContext` object. This object encapsulates the current state relevant to making a decision, including:
        *   `current_task_requirements`
        *   `all_components_performance` (current performance of available components)
        *   An `explicit_query_text` is generated summarizing this context.
    2.  **Calling `retrieve_memories()`:** The planner calls `self.memory_manager.retrieve_memories()` using the created `AgentQueryContext`.
        *   It typically filters for successful past experiences (e.g., `where_filter={"outcome_success": "True"}`).
        *   It requests a limited number of results (e.g., `n_results=3`).
    3.  **Formatting Retrieved Memories:** The list of memory dictionaries returned by `retrieve_memories()` is processed by `_format_retrieved_memories()`. This method:
        *   Extracts key information from each memory (action taken, outcome, summary, similarity).
        *   Formats this information into a human-readable string.
        *   This formatted string, prepended with a header like "Relevant Past Successful Experiences (most similar first):", is then incorporated directly into the main prompt that `KFMPlannerLlm` sends to its underlying language model.
    *   By including these past experiences in the prompt, the LLM gains additional context that can influence its reasoning and the KFM decision it produces.

## C. Data Models

Key Pydantic models supporting the memory system are defined in `src/core/memory/models.py`.

*   **`AgentExperienceLog`**: This is the central model for recording an agent's experience. It captures:
    *   `timestamp`: When the experience occurred.
    *   `current_task_requirements`: Requirements active during the experience.
    *   `previous_component_name` and `previous_component_metrics`: State before the KFM action.
    *   `planner_llm_input` and `planner_llm_output`: What the planner received and decided.
    *   `kfm_action_taken` and `selected_component_name`: The actual action and component chosen.
    *   `execution_outcome_metrics`: Performance metrics after the action was executed.
    *   `outcome_success`: A boolean indicating if the outcome was considered successful.
    *   `action_execution_error`: Any errors during action execution.
    *   `reflection_llm_output`: Any insights or reflections generated post-experience.
*   **`ComponentMetrics`**: A simple model to structure component performance data (accuracy, latency, cost, reliability).
*   **`AgentQueryContext`**: Defines the information used to query the memory. This includes:
    *   `current_task_requirements`: The requirements for the current decision-making context.
    *   `current_component_name` (Optional) and `current_component_metrics` (Optional): Performance of the currently active component, if any.
    *   `all_components_performance` (Optional): Performance of all available components.
    *   `explicit_query_text` (Optional): Allows for a direct textual query to override summary generation from other context fields.

## D. Configuration

The persistent memory system is configured via `verification_config.yaml` and corresponding Pydantic models in `src/config/models.py`.

**1. `verification_config.yaml`:**

Under the `memory:` key, you can configure:

```yaml
memory:
  embedding_model_name: "all-MiniLM-L6-v2"  # Name of the sentence-transformer model
  vector_db_path: "./kfm_chroma_db_prod"      # Directory to store ChromaDB persistent data
  collection_name: "agent_experiences_prod" # Name of the ChromaDB collection
  # Add other memory-related configs here if needed
```

*   `embedding_model_name`: Specifies the model to be loaded by `EmbeddingService`. Ensure this model is compatible with the `sentence-transformers` library.
*   `vector_db_path`: The file system path where ChromaDB will create and store its database files. This directory will be created if it doesn't exist.
*   `collection_name`: The name of the collection within ChromaDB where agent experiences will be stored.

**2. `src/config/models.py`:**

The `MemoryConfig` Pydantic model in this file defines the structure for memory configuration and is used to load and validate the settings from `verification_config.yaml`.

```python
class MemoryConfig(BaseModel):
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_db_path: str = "./kfm_chroma_db"
    collection_name: str = "agent_experiences"
    # ... any other memory config fields
```

**Changing Configuration:**

To change the embedding model, database location, or collection name, modify the respective values in your `verification_config.yaml` file. The application will pick up these changes upon the next restart and re-initialization of the memory system components (typically via `src/factory.py`).

## E. Setup & Initialization

**1. Dependencies:**

The memory system relies on the following key Python libraries, which should be listed in your `requirements.txt` file:

*   `sentence-transformers`: For loading embedding models and generating embeddings.
*   `chromadb-client`: The client library for interacting with ChromaDB.

Ensure these are installed in your project's environment.

**2. Initialization in `src/factory.py`:**

The primary components of the memory system (`EmbeddingService` and `ChromaMemoryManager`) are typically instantiated within the `create_kfm_agent()` function in `src/factory.py`. The process is generally as follows:

*   The main `VerificationConfig` (which includes `MemoryConfig`) is loaded from `verification_config.yaml`.
*   An `EmbeddingService` instance is created, passing the `embedding_model_name` from the configuration.
*   A `ChromaMemoryManager` instance is created, receiving:
    *   The `EmbeddingService` instance.
    *   The `vector_db_path` from the configuration.
    *   The `collection_name` from the configuration.
*   This `ChromaMemoryManager` instance is then passed to the `KFMPlannerLlm` during its initialization.

This setup ensures that the planner has access to the configured memory system when it starts.

## F. Usage / How it Works Flow

The persistent memory system operates in a cycle of recording experiences and retrieving them to inform future decisions:

1.  **Agent Acts & Observes Outcome:** The KFM agent, through its planner and execution engine, takes an action with a selected component based on current task requirements and component performance.
2.  **Experience Logging (`AgentExperienceLog` Creation):**
    *   After the action is executed, an `AgentExperienceLog` object is populated. This object captures a comprehensive snapshot of the context before the action, the action itself, the outcome, and any reflections.
    *   *(Currently, in the test setup, this log is often created manually. In a full agent loop, a dedicated "Reflector" component or the main agent orchestrator would be responsible for assembling this log.)*
3.  **Storing the Experience (`ChromaMemoryManager.add_memory_entry()`):**
    *   The populated `AgentExperienceLog` is passed to `memory_manager.add_memory_entry()`.
    *   The `ChromaMemoryManager` internally calls `_create_embedding_summary()` to generate a concise textual summary of the experience.
    *   This summary is then passed to the `EmbeddingService` to obtain a vector embedding.
    *   The original `AgentExperienceLog` (serialized to JSON) is stored as the main document in ChromaDB, along with its vector embedding and a rich set of metadata (as detailed in Section B.2).
4.  **Planner Faces a New Decision (`KFMPlannerLlm.decide_kfm_action()`):**
    *   When the `KFMPlannerLlm` is invoked to make a new decision, it prepares to consult its memory.
5.  **Formulating a Memory Query (`AgentQueryContext`):**
    *   The planner creates an `AgentQueryContext` object, filling it with details about the current task requirements, performance of available components, etc.
6.  **Retrieving Relevant Memories (`ChromaMemoryManager.retrieve_memories()`):**
    *   The planner calls `memory_manager.retrieve_memories()`, passing the `AgentQueryContext`.
    *   The `ChromaMemoryManager` generates a query summary and then a query embedding from this context using the `EmbeddingService`.
    *   It then queries ChromaDB for entries with embeddings most similar to the query embedding. It can also apply filters (e.g., to fetch only successful past experiences).
7.  **Incorporating Memories into Prompt (`KFMPlannerLlm._generate_prompt()`):**
    *   The retrieved memories (typically a list of documents and metadata) are formatted by the planner's `_format_retrieved_memories()` method into a human-readable string.
    *   This string, highlighting key aspects of relevant past experiences, is inserted into the prompt that the `KFMPlannerLlm` sends to its underlying Large Language Model.
8.  **Informed Decision:** The LLM, now having access to both the current problem and relevant past experiences, generates a KFM decision. This decision is then parsed and returned by the `KFMPlannerLlm`.

This cycle allows the agent to continuously learn and refine its behavior based on a growing history of interactions.

## G. Testing

The persistent memory system is validated through a combination of unit and integration tests:

*   **Unit Tests:**
    *   `tests/core/test_embedding_service.py`: Contains tests for the `EmbeddingService`, verifying model loading and embedding generation for single and batch inputs.
    *   `tests/core/memory/test_chroma_manager.py`: Includes unit tests for `ChromaMemoryManager`, covering aspects like client/collection initialization, adding memory entries (mocking the embedding part), retrieving entries (mocking embeddings), counting items, and database reset functionality.
*   **Integration Test:**
    *   `tests/core/test_kfm_planner_llm.py::test_decide_kfm_action_with_memory_integration`: This is a key integration test that verifies the interaction between `KFMPlannerLlm`, a real `ChromaMemoryManager` (with a temporary, test-specific database), and a real `EmbeddingService`.
        *   It seeds the test database with sample `AgentExperienceLog` entries.
        *   It then invokes `KFMPlannerLlm.decide_kfm_action()`.
        *   It asserts that the prompt generated by the planner (and sent to its mocked internal LLM) correctly includes formatted information from the seeded past experiences.
        *   This test ensures that the end-to-end flow of memory retrieval and its inclusion in the planner's context is working as expected.

To run these tests, you can use `pytest` commands, targeting the specific files or test functions. For example:
`PYTHONPATH=. pytest tests/core/memory/test_chroma_manager.py`
`PYTHONPATH=. pytest tests/core/test_kfm_planner_llm.py -k test_decide_kfm_action_with_memory_integration`

## H. Future Considerations (Optional)

*   **Automated Experience Logging:** Implementing a robust mechanism within the main agent loop or a dedicated "Reflector" component to automatically create and log `AgentExperienceLog` instances after each KFM cycle.
*   **Advanced Reflection:** Enhancing the reflection process, potentially using an LLM to generate more insightful summaries or analyses of experiences before they are stored.
*   **Sophisticated Querying/Filtering:** Exploring more advanced query types, metadata filtering combinations, or context-augmentation techniques for memory retrieval.
*   **Memory Pruning/Summarization:** For very long-running agents, strategies for pruning, summarizing, or tiering memories might become necessary to manage database size and retrieval efficiency.
*   **Dynamic `n_results`:** Adjusting the number of retrieved memories (`n_results`) dynamically based on context or confidence. 