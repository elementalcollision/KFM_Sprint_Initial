import pytest
import json
import logging
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Project component imports
from src.core.kfm_planner_llm import KFMPlannerLlm
from src.core.memory.chroma_manager import ChromaMemoryManager
from src.core.embedding_service import EmbeddingService
from src.core.component_registry import ComponentRegistry
from src.core.execution_engine import ExecutionEngine
from src.core.memory.models import AgentExperienceLog, ComponentMetrics

# Configure logging for tests if needed
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Test Fixture for E2E Setup ---

@pytest.fixture(scope="function") # Function scope ensures clean DB for each test
def kfm_e2e_setup():
    """
    Sets up the E2E test environment:
    - Temporary ChromaDB instance
    - Real EmbeddingService
    - Real ChromaMemoryManager
    - KFMPlannerLlm with real memory manager and mocked registry
    - Mocked ExecutionEngine
    Yields components and handles teardown.
    """
    temp_db_path = tempfile.mkdtemp()
    embedding_model_name = "all-MiniLM-L6-v2" # Use a standard small model
    test_collection_name = "kfm_e2e_test_collection"
    
    components = {}
    try:
        logger.info(f"Setting up E2E test environment in {temp_db_path}")
        
        # 1. Real Embedding Service
        embedding_service = EmbeddingService(model_name=embedding_model_name)
        components['embedding_service'] = embedding_service
        
        # 2. Real Memory Manager with Temp DB
        memory_manager = ChromaMemoryManager(
            embedding_service=embedding_service,
            db_path=temp_db_path,
            collection_name=test_collection_name
        )
        if memory_manager.get_collection() is None:
             raise RuntimeError(f"Failed to initialize collection '{test_collection_name}' in fixture.")
        components['memory_manager'] = memory_manager

        # 3. Mocked Component Registry
        mock_registry = MagicMock(spec=ComponentRegistry)
        # Configure mock registry behavior if needed by planner initialization or test logic
        components['mock_registry'] = mock_registry

        # 4. KFM Planner with real memory manager and mock registry
        #    Need to patch the internal LLM call for controlled testing initially
        mock_llm_internal = MagicMock() 
        mock_response = MagicMock()
        mock_response.text = json.dumps({"action": "No Action", "component": None, "reasoning": "Default mock LLM response for E2E", "confidence": 0.5})
        mock_llm_internal.generate_content = MagicMock(return_value=mock_response)
        
        with patch('google.generativeai.GenerativeModel', return_value=mock_llm_internal):
            planner = KFMPlannerLlm(
                component_registry=mock_registry, # Pass mock registry
                memory_manager=memory_manager     # Pass real memory manager
                # Default model name for planner, but the actual call is mocked here
            )
        # Store the internal mock used by the planner for assertions later
        planner.model.generate_content = mock_llm_internal.generate_content # Ensure the assertion target is correct
        components['planner'] = planner
        components['mock_llm_generate_content'] = planner.model.generate_content # Make the mock accessible

        # 5. Mocked Execution Engine
        mock_engine = MagicMock(spec=ExecutionEngine)
        # Configure mock engine behavior (e.g., execute_action return value)
        components['mock_engine'] = mock_engine

        logger.info("E2E setup complete. Yielding components.")
        yield components

    finally:
        logger.info("Tearing down E2E test environment...")
        # Teardown: reset and remove the temporary database
        if 'memory_manager' in components and components['memory_manager'].client:
            try:
                components['memory_manager'].client.reset()
                logger.info(f"ChromaDB at {temp_db_path} reset successfully.")
            except Exception as e:
                logger.error(f"Error resetting ChromaDB at {temp_db_path}: {e}", exc_info=True)
        
        if os.path.exists(temp_db_path):
            try:
                shutil.rmtree(temp_db_path)
                logger.info(f"Temporary ChromaDB directory {temp_db_path} removed.")
            except Exception as e:
                logger.error(f"Error removing temporary ChromaDB directory {temp_db_path}: {e}", exc_info=True)

# --- Placeholder E2E Test ---

def test_kfm_memory_e2e_sequence(kfm_e2e_setup):
    """
    Placeholder for the end-to-end test scenario simulating multiple KFM rounds
    with memory logging and retrieval influencing decisions.
    """
    # Extract components from the fixture
    planner = kfm_e2e_setup['planner']
    memory_manager = kfm_e2e_setup['memory_manager']
    mock_registry = kfm_e2e_setup['mock_registry']
    mock_engine = kfm_e2e_setup['mock_engine']
    mock_llm_call = kfm_e2e_setup['mock_llm_generate_content'] # The mock to assert calls on

    logger.info("Starting E2E test sequence...")
    
    # --- Round 1 ---
    logger.info("--- Round 1 Start ---")
    # Define Round 1 context
    round1_task_req = {"min_accuracy": 0.7, "max_latency": 2.0}
    round1_comp_perf = {"comp_fast": {"accuracy": 0.65, "latency": 0.5}}
    
    # Act: Get KFM decision
    kfm_decision1 = planner.decide_kfm_action(
        task_name="round1_task",
        task_requirements=round1_task_req,
        all_components_performance=round1_comp_perf
    )
    logger.info(f"Round 1 KFM Decision: {kfm_decision1}")
    mock_llm_call.assert_called_once() # Check LLM was called
    prompt1 = mock_llm_call.call_args[0][0]
    assert "No relevant past experiences found" in prompt1 # Expect no memories yet
    
    # Simulate execution and log experience
    # Assuming the default mock LLM said 'Fuck' comp_fast
    # Simulate an outcome for this action
    simulated_outcome_metrics1 = ComponentMetrics(accuracy=0.72, latency=0.6) # Improved slightly
    experience1 = AgentExperienceLog(
         timestamp=datetime.now(timezone.utc),
         current_task_requirements=round1_task_req,
         previous_component_name="comp_fast", # Or determine based on kfm_decision1
         previous_component_metrics=ComponentMetrics(**round1_comp_perf["comp_fast"]),
         planner_llm_input=prompt1, # Store the actual prompt
         planner_llm_output=json.dumps(kfm_decision1),
         kfm_action_taken=kfm_decision1.get('action', 'No Action'),
         selected_component_name=kfm_decision1.get('component', 'comp_fast'),
         execution_outcome_metrics=simulated_outcome_metrics1,
         outcome_success=True,
         action_execution_error=None,
         reflection_llm_output="Reflection for Round 1: Action seems successful."
    )
    entry_id1 = memory_manager.add_memory_entry(experience1)
    assert entry_id1 is not None
    assert memory_manager.count_items() == 1
    logger.info(f"--- Round 1 End (Logged experience {entry_id1}) ---")

    # --- Round 2 ---
    logger.info("--- Round 2 Start ---")
    # Define Round 2 context (similar requirements, should retrieve Round 1 memory)
    round2_task_req = {"min_accuracy": 0.7, "max_latency": 2.1} # Slightly different
    round2_comp_perf = {"comp_fast": {"accuracy": 0.72, "latency": 0.6}} # Use the updated perf

    # Reset the mock call count for the next assertion
    mock_llm_call.reset_mock() 
    
    # Act: Get KFM decision for Round 2
    kfm_decision2 = planner.decide_kfm_action(
        task_name="round2_task",
        task_requirements=round2_task_req,
        all_components_performance=round2_comp_perf
    )
    logger.info(f"Round 2 KFM Decision: {kfm_decision2}")
    
    # Assert: LLM called and prompt includes Round 1 memory
    mock_llm_call.assert_called_once()
    prompt2 = mock_llm_call.call_args[0][0]
    logger.debug(f"Round 2 Prompt:\n{prompt2}")
    
    assert "Relevant Past Successful Experiences" in prompt2, "Round 2 prompt should include past experiences."
    assert "Reflection for Round 1" in prompt2, "Details from Round 1 experience missing in Round 2 prompt."
    assert "Action: No Action" in prompt2 # Based on the default mock response stored in experience1
    assert "Success: True" in prompt2
    
    # Simulate and log Round 2 (optional for this test, focus is on retrieval impact)
    logger.info("--- Round 2 End ---")

    # Add more rounds or more complex assertions as needed
    pass # Test structure complete 