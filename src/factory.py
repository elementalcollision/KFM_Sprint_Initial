"""
Factory module for creating KFM agent components.

This module provides factory functions to create and configure
the components needed for the KFM agent system.
"""

import os
from dotenv import load_dotenv
from typing import Tuple
from src.core.component_registry import ComponentRegistry
from src.core.state_monitor import StateMonitor  
from src.core.kfm_planner_llm import KFMPlannerLlm
from src.core.kfm_planner import KFMPlanner
from src.core.execution_engine import ExecutionEngine
from src.logger import setup_logger
from langchain_openai import ChatOpenAI
from src.state_types import KFMAgentState
from src.core.component_registry import ComponentRegistry
from src.core.embedding_service import EmbeddingService
from src.core.memory.chroma_manager import ChromaMemoryManager
from src.config.config_loader import load_verification_config

# Import for Reversibility System
from src.core.reversibility.snapshot_service import SnapshotService
from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage
# from src.core.reversibility.state_adapter_registry import StateAdapterRegistry # If needed later

# Setup factory logger
factory_logger = setup_logger('Factory')

# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()

def create_sample_components():
    """Create sample components for the registry.
    
    Returns:
        Dictionary of component functions
    """
    def analyze_fast(input_data):
        """Fast but less accurate analysis component."""
        # Simple implementation for demonstration
        text = input_data.get('text', '')
        if not text:
            return {"error": "No text provided"}, 0.0
            
        # Very simple "analysis" for demo
        result = {
            "word_count": len(text.split()),
            "type": "fast_analysis",
            "summary": "Fast analysis complete"
        }
        
        # Fast component has lower accuracy but good latency
        accuracy = 0.7
        
        return result, accuracy
        
    def analyze_accurate(input_data):
        """Accurate but slower analysis component."""
        # Simple implementation for demonstration
        text = input_data.get('text', '')
        if not text:
            return {"error": "No text provided"}, 0.0
            
        # More detailed "analysis" for demo
        words = text.split()
        result = {
            "word_count": len(words),
            "char_count": len(text),
            "avg_word_length": sum(len(w) for w in words) / max(len(words), 1),
            "type": "detailed_analysis",
            "summary": "Detailed analysis complete"
        }
        
        # Accurate component has higher accuracy
        accuracy = 0.95
        
        return result, accuracy
        
    def analyze_balanced(input_data):
        """Balanced analysis component with medium accuracy and speed."""
        # Simple implementation for demonstration
        text = input_data.get('text', '')
        if not text:
            return {"error": "No text provided"}, 0.0
            
        # Balanced "analysis" for demo
        words = text.split()
        result = {
            "word_count": len(words),
            "type": "balanced_analysis",
            "summary": "Balanced analysis complete" 
        }
        
        # Balanced component has medium accuracy
        accuracy = 0.85
        
        return result, accuracy
    
    # Return dictionary of components
    return {
        "analyze_fast": analyze_fast,
        "analyze_accurate": analyze_accurate,
        "analyze_balanced": analyze_balanced
    }

def create_sample_performance_data():
    """Create sample performance data for components.
    
    Returns:
        Dictionary of performance data by component
    """
    return {
        "analyze_fast": {
            "latency": 0.5,  # in seconds
            "accuracy": 0.7  # scale 0-1
        },
        "analyze_accurate": {
            "latency": 2.0,  # in seconds
            "accuracy": 0.95  # scale 0-1
        },
        "analyze_balanced": {
            "latency": 1.0,  # in seconds
            "accuracy": 0.85  # scale 0-1
        }
    }

def create_sample_task_requirements():
    """Create sample task requirements for different task types.
    
    Returns:
        Dictionary of requirements by task
    """
    return {
        "default": {
            "max_latency": 1.5,  # in seconds
            "min_accuracy": 0.8   # scale 0-1
        },
        "high_accuracy_task": {
            "max_latency": 3.0,   # in seconds
            "min_accuracy": 0.9   # scale 0-1
        },
        "fast_response_task": {
            "max_latency": 0.8,   # in seconds
            "min_accuracy": 0.6   # scale 0-1
        },
        "trace_example": {
            "max_latency": 1.5,   # in seconds
            "min_accuracy": 0.8   # scale 0-1
        },
        "error_example": {
            "max_latency": 1.5,   # in seconds
            "min_accuracy": 0.8   # scale 0-1
        }
    }

def create_kfm_agent() -> Tuple[ComponentRegistry, StateMonitor, KFMPlannerLlm, ExecutionEngine, KFMPlanner, SnapshotService]:
    """Create all components needed for the KFM agent.
    
    Returns:
        Tuple of (ComponentRegistry, StateMonitor, KFMPlannerLlm, ExecutionEngine, KFMPlanner, SnapshotService)
    """
    factory_logger.info("Creating KFM agent components...")
    
    # Define project_root for paths relative to the project's root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # Load Configuration
    config = load_verification_config()
    if not config:
        # Handle error case where config loading fails
        factory_logger.error("Failed to load verification_config.yaml. Cannot create agent.")
        raise ValueError("Configuration loading failed.")
    factory_logger.info("Loaded verification configuration.")

    # Create sample components for the registry
    components = create_sample_components()
    factory_logger.info(f"Created sample components: {list(components.keys())}")
    
    # Create the registry and add components
    registry = ComponentRegistry()
    for name, func in components.items():
        registry.register_component(name, func)
    registry.set_default_component("analyze_balanced")
    factory_logger.info(f"Component registry created with {len(components)} components")
    
    # Create performance data and requirements for the monitor
    performance_data = create_sample_performance_data()
    task_requirements = create_sample_task_requirements()
    
    # Create the state monitor
    monitor = StateMonitor(performance_data, task_requirements)
    factory_logger.info("State monitor created")
    
    # Create the execution engine
    engine = ExecutionEngine(registry)
    factory_logger.info("Execution engine created")
    
    # --- Initialize Memory System ---
    try:
        embedding_service = EmbeddingService(model_name=config.memory.embedding_model_name)
        factory_logger.info("Embedding service initialized.")
        memory_manager = ChromaMemoryManager(
            embedding_service=embedding_service,
            db_path=config.memory.vector_db_path,
            collection_name=config.memory.collection_name
        )
        factory_logger.info("Chroma memory manager initialized.")
    except Exception as e:
        factory_logger.error(f"Failed to initialize memory system: {e}", exc_info=True)
        raise # Stop agent creation if memory system fails
    # -------------------------------

    # --- Instantiate the LLM and the LLM Planner ---
    try:
        # Ensure API key is loaded (needed for LLM, not memory itself)
        # if not os.getenv("GOOGLE_API_KEY"): # Check relevant key for Gemini
        #     factory_logger.warning("GOOGLE_API_KEY environment variable not set for KFMPlannerLlm.")
        
        # Instantiate the KFM LLM planner - Updated Instantiation
        planner_llm = KFMPlannerLlm(
            component_registry=registry, # Pass registry
            memory_manager=memory_manager, # Pass memory manager
            model_name=config.global_settings.llm_model_name if hasattr(config.global_settings, 'llm_model_name') else KFMPlannerLlm.DEFAULT_MODEL_NAME # Get model from config if exists
            # google_api_key=os.getenv("GOOGLE_API_KEY") # Pass key if needed by constructor
        )
        factory_logger.info("KFM LLM planner (KFMPlannerLlm) created.")
        
    except ImportError:
        factory_logger.error("Failed to import LLM components. Check installations (e.g., google-generativeai).")
        raise
    except ValueError as ve:
        factory_logger.error(f"Configuration error for LLM: {ve}")
        raise
    except Exception as e:
        factory_logger.error(f"Failed to instantiate LLM or KFMPlannerLlm: {e}")
        raise # Re-raise after logging
    # ------------------------------------------------
    
    # --- Instantiate the Original Rule-Based Planner ---
    # The original planner needs performance data and task requirements
    planner_original = KFMPlanner(performance_data, task_requirements)
    factory_logger.info("Original KFM planner (KFMPlanner) created.")
    # ----------------------------------------------------
    
    # --- Initialize Reversibility System ---
    factory_logger.info("Initializing Reversibility System...")
    try:
        snapshot_base_path = os.path.join(project_root, "kfm_snapshots")
        if not os.path.exists(snapshot_base_path):
            os.makedirs(snapshot_base_path)
            factory_logger.info(f"Created snapshot directory: {snapshot_base_path}")

        file_snapshot_storage = FileSnapshotStorage(base_path=snapshot_base_path)
        factory_logger.info(f"FileSnapshotStorage initialized with base_path: {snapshot_base_path}")
        
        # adapter_registry can be None initially if no adapters are defined yet
        # adapter_registry = StateAdapterRegistry() 
        # factory_logger.info("StateAdapterRegistry initialized.")

        snapshot_service = SnapshotService(storage_backend=file_snapshot_storage, adapter_registry=None)
        factory_logger.info("SnapshotService initialized.")
    except Exception as e:
        factory_logger.error(f"Failed to initialize Reversibility System: {e}", exc_info=True)
        raise # Stop agent creation if reversibility system fails
    # ---------------------------------------
    
    # Return all components, including both planners and the snapshot_service
    return registry, monitor, planner_llm, engine, planner_original, snapshot_service 