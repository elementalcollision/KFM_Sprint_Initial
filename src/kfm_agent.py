# src/kfm_agent.py
import sys
import os
import logging
import time
import hashlib
import asyncio # Added for async main

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from typing import Dict, Any, Callable, Tuple, Optional
from langgraph.graph import StateGraph, END # Import END for conditional edges
from src.state_types import KFMAgentState
from src.langgraph_nodes import monitor_state_node, kfm_decision_node, execute_action_node, reflect_node, should_fallback, fallback_node
from src.factory import create_kfm_agent # Use the factory to get components
from src.logger import setup_logger, setup_shared_file_logger, setup_centralized_logging, setup_component_logger, create_timestamped_log_file
from src.tracing import configure_tracing, reset_trace_history, visualize_trace_path, get_trace_history, create_trace_summary, save_trace_to_file
from src.debugging import debug_graph_execution, step_through_execution, diff_states, wrap_node_for_debug
from src.core.execution_engine import ExecutionEngine

# Imports for Reversibility and Lifecycle Control
from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage
from src.core.reversibility.snapshot_service import SnapshotService
from src.core.reversibility.reversal_manager import ReversalManager
from src.core.agent_lifecycle_controller import AgentLifecycleController

agent_logger = setup_logger('KFMAgent')
reflect_logger = setup_logger('ReflectNode') # Define reflect_logger here

# Add stub functions for testing
def create_performance_monitor(*args, **kwargs):
    """
    Create a performance monitor for the KFM agent.
    This is a stub function for testing.
    """
    agent_logger.warning("create_performance_monitor called - stub function for testing")
    return None

def create_components_manager(*args, **kwargs):
    """
    Create a components manager for the KFM agent.
    This is a stub function for testing.
    """
    agent_logger.warning("create_components_manager called - stub function for testing")
    return None

def create_kfm_agent_graph() -> Tuple[StateGraph, Dict[str, Any]]:
    """Create the KFM Agent LangGraph.
    
    Returns:
        Tuple[StateGraph, Dict[str, Any]]: The compiled graph application and core components
    """
    agent_logger.info("Creating KFM Agent graph...")
    # Create the KFM agent core components using the factory
    registry, monitor, planner_llm, engine, planner_original, snapshot_service = create_kfm_agent()
    agent_logger.info("Core components created (including KFMPlannerLlm, KFMPlanner, and SnapshotService).")
    
    # Create the graph builder
    builder = StateGraph(KFMAgentState)
    
    # Add nodes, binding components using lambdas
    agent_logger.info("Adding nodes...")
    builder.add_node("monitor", lambda state: monitor_state_node(state, monitor, snapshot_service))
    builder.add_node("decide", lambda state: kfm_decision_node(state, planner_llm, snapshot_service))
    builder.add_node("execute", lambda state: execute_action_node(state, engine, snapshot_service))
    builder.add_node("reflect", lambda state: reflect_node(state, snapshot_service))
    builder.add_node("fallback", lambda state: fallback_node(state, planner_original, snapshot_service))
    agent_logger.info("Nodes added (including fallback with original planner and snapshot_service).")
    
    # Set the entry point
    builder.set_entry_point("monitor")
    agent_logger.info("Entry point set to 'monitor'.")
    
    # Add standard edges
    agent_logger.info("Adding edges...")
    builder.add_edge("monitor", "decide")
    builder.add_edge("execute", "reflect")
    builder.add_edge("fallback", "reflect")
    agent_logger.info("Standard edges added. Adding conditional edges...")
    
    # Conditional edge after decision node based on confidence/errors
    builder.add_conditional_edges(
        "decide",
        should_fallback,
        {
            "fallback": "fallback",
            "execute": "execute"
        }
    )
    agent_logger.info("Conditional edge added from 'decide' to 'execute' or 'fallback'.")
    
    # Conditional edge after reflection: if done, end the graph, otherwise loop (for future extension)
    def should_continue(state: KFMAgentState) -> str:
        """Determines the next step after reflection."""
        agent_logger.info("⚠️ CONDITIONAL: Evaluating workflow continuation")
        
        # Log state information for debugging
        agent_logger.debug(f"State keys: {list(state.keys())}")
        agent_logger.debug(f"State.done: {state.get('done', False)}")
        agent_logger.debug(f"State.error: {state.get('error', None)}")
        
        if state.get('error'):
            error_msg = state.get('error')
            agent_logger.error(f"Workflow ending due to error: {error_msg}")
            reflect_logger.error(f"Workflow ending due to error: {error_msg}")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END
            
        if state.get("done", False):
            agent_logger.info("Workflow marked as done. Ending.")
            reflect_logger.info("Workflow marked as done. Ending.")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END
        else:
            # In future, could loop back to monitor or another node
            agent_logger.warning("Workflow not marked done, but MVP ends here anyway.")
            reflect_logger.warning("Workflow not marked done, but MVP ends here anyway.")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END # End for MVP even if not explicitly done
    
    builder.add_conditional_edges("reflect", should_continue)
    agent_logger.info("Conditional edge added from 'reflect'.")
    
    # Compile the graph with error handling
    agent_logger.info("Compiling graph...")
    kfm_app = None
    try:
        kfm_app = builder.compile()
        agent_logger.info("LangGraph application successfully compiled")
    except Exception as e:
        error_msg = f"Error compiling LangGraph application: {e}"
        agent_logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    
    # Return the graph and its components for potential external use
    components = {
        "registry": registry,
        "monitor": monitor,
        "planner_llm": planner_llm,
        "planner_original": planner_original,
        "engine": engine,
        "snapshot_service": snapshot_service
    }
    
    return kfm_app, components

def get_graph_creation_functions() -> Tuple[Callable, Callable]:
    """Returns the standard and debug graph creation functions."""
    return create_kfm_agent_graph, create_debug_kfm_agent_graph

def create_debug_kfm_agent_graph() -> Tuple[StateGraph, Dict[str, Any]]:
    """Create a debug version of the KFM Agent LangGraph with node wrapping.
    
    Returns:
        Tuple[StateGraph, Dict[str, Any]]: The compiled debug graph application and core components
    """
    agent_logger.info("Creating KFM Agent debug graph...")
    # Create the KFM agent core components using the factory
    registry, monitor, planner_llm, engine, planner_original, snapshot_service = create_kfm_agent()
    agent_logger.info("Core components created (including KFMPlannerLlm, KFMPlanner, and SnapshotService).")
    
    # Create the graph builder
    builder = StateGraph(KFMAgentState)
    
    # Add nodes with debug wrappers
    agent_logger.info("Adding debug-wrapped nodes...")
    
    # Wrap the node functions with debug wrappers
    wrapped_monitor_node = wrap_node_for_debug(
        lambda state: monitor_state_node(state, monitor, snapshot_service), 
        "monitor"
    )
    wrapped_decision_node = wrap_node_for_debug(
        lambda state: kfm_decision_node(state, planner_llm, snapshot_service), 
        "decide"
    )
    wrapped_execute_node = wrap_node_for_debug(
        lambda state: execute_action_node(state, engine, snapshot_service), 
        "execute"
    )
    wrapped_reflect_node = wrap_node_for_debug(
        lambda state: reflect_node(state, snapshot_service), 
        "reflect"
    )
    wrapped_fallback_node = wrap_node_for_debug(
        lambda state: fallback_node(state, planner_original, snapshot_service), 
        "fallback"
    )
    
    # Add the wrapped nodes to the builder
    builder.add_node("monitor", wrapped_monitor_node)
    builder.add_node("decide", wrapped_decision_node)
    builder.add_node("execute", wrapped_execute_node)
    builder.add_node("reflect", wrapped_reflect_node)
    builder.add_node("fallback", wrapped_fallback_node)
    
    agent_logger.info("Debug-wrapped nodes added (including fallback).")
    
    # Set the entry point
    builder.set_entry_point("monitor")
    agent_logger.info("Entry point set to 'monitor'.")
    
    # Add standard edges
    agent_logger.info("Adding edges...")
    builder.add_edge("monitor", "decide")
    builder.add_edge("decide", "execute")
    builder.add_edge("execute", "reflect")
    builder.add_edge("fallback", "reflect")
    agent_logger.info("Standard edges added. Adding conditional edges...")
    
    # Conditional edge after decision node based on confidence/errors
    builder.add_conditional_edges(
        "decide",
        should_fallback,
        {
            "fallback": "fallback",
            "execute": "execute"
        }
    )
    agent_logger.info("Conditional edge added from 'decide' to 'execute' or 'fallback'.")
    
    # Conditional edge after reflection: if done, end the graph, otherwise loop (for future extension)
    def should_continue(state: KFMAgentState) -> str:
        """Determines the next step after reflection."""
        agent_logger.info("⚠️ CONDITIONAL: Evaluating workflow continuation")
        
        # Log state information for debugging
        agent_logger.debug(f"State keys: {list(state.keys())}")
        agent_logger.debug(f"State.done: {state.get('done', False)}")
        agent_logger.debug(f"State.error: {state.get('error', None)}")
        
        if state.get('error'):
            error_msg = state.get('error')
            agent_logger.error(f"Workflow ending due to error: {error_msg}")
            reflect_logger.error(f"Workflow ending due to error: {error_msg}")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END
            
        if state.get("done", False):
            agent_logger.info("Workflow marked as done. Ending.")
            reflect_logger.info("Workflow marked as done. Ending.")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END
        else:
            reflect_logger.warning("Workflow not marked done, but ends here anyway.")
            agent_logger.warning("Workflow not marked done, but MVP ends here anyway.")
            agent_logger.info("⚠️ CONDITIONAL RESULT: END")
            return END
    
    builder.add_conditional_edges("reflect", should_continue)
    agent_logger.info("Conditional edge added from 'reflect'.")
    
    # Compile the graph with error handling
    agent_logger.info("Compiling debug graph...")
    kfm_app = None
    try:
        kfm_app = builder.compile()
        agent_logger.info("Debug LangGraph application successfully compiled")
    except Exception as e:
        error_msg = f"Error compiling debug LangGraph application: {e}"
        agent_logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    
    # Return the graph and its components
    components = {
        "registry": registry,
        "monitor": monitor,
        "planner_llm": planner_llm,
        "planner_original": planner_original,
        "engine": engine,
        "snapshot_service": snapshot_service
    }
    
    return kfm_app, components

def visualize_graph(kfm_app: StateGraph) -> Optional[bytes]:
    """Visualize the compiled graph structure if LangGraph supports it.
    
    Args:
        kfm_app (StateGraph): The compiled LangGraph application
        
    Returns:
        Optional[bytes]: PNG image data of the graph visualization if available, None otherwise
    """
    try:
        # LangGraph supports visualization via Mermaid
        return kfm_app.get_graph().draw_mermaid_png()
    except (AttributeError, ImportError, Exception) as e:
        agent_logger.warning(f"Unable to visualize graph structure: {e}")
        return None

def save_graph_visualization(kfm_app: StateGraph, output_path: str = "kfm_graph.png") -> bool:
    """Save the visualization of the KFM graph to a file.
    
    Args:
        kfm_app (StateGraph): The compiled LangGraph application
        output_path (str): Path where to save the visualization (default: kfm_graph.png)
        
    Returns:
        bool: True if the visualization was successfully saved, False otherwise
    """
    visualization_data = visualize_graph(kfm_app)
    if visualization_data:
        try:
            with open(output_path, "wb") as f:
                f.write(visualization_data)
            agent_logger.info(f"Graph visualization saved to {output_path}")
            return True
        except Exception as e:
            agent_logger.error(f"Failed to save graph visualization: {e}")
    return False

def run_kfm_agent(
    input_data: Dict[str, Any], 
    task_name: str = "default", 
    trace_level: int = logging.INFO,
    debug_mode: bool = False,
    step_mode: bool = False,
    log_file: str = "kfm_app.log"
) -> Optional[Dict[str, Any]]:
    """Run the KFM Agent on the given input data.
    
    Args:
        input_data (Dict[str, Any]): Input data for the task
        task_name (str): Name of the task
        trace_level (int): Logging level for tracing (default: logging.INFO)
        debug_mode (bool): Whether to run in debug mode with full state tracing (default: False)
        step_mode (bool): Whether to run step-by-step execution (default: False)
        log_file (str): Name of the log file to use (default: kfm_app.log)
        
    Returns:
        Dict[str, Any]: Final state after execution, or None if graph creation fails
    """
    # Setup centralized logging
    log_manager = setup_centralized_logging()
    
    # Set up component-specific logging for this run
    run_logger = setup_component_logger(f"kfm_run.{task_name}")
    
    # Add a shared file logger for all components in this run
    setup_shared_file_logger(log_file)
    
    # Setup tracing
    configure_tracing(log_level=trace_level)
    reset_trace_history()
    
    # Start timing execution
    start_time = time.time()
    
    run_logger.info("="*50)
    run_logger.info(f"KFM AGENT RUN START - Task: '{task_name}'")
    run_logger.info(f"Debug Mode: {debug_mode}, Step Mode: {step_mode}")
    run_logger.info("="*50)
    
    run_logger.debug(f"Input data: {input_data}")
    
    try:
        # Create the appropriate version of the graph
        graph_start_time = time.time()
        if debug_mode:
            kfm_app, components = create_debug_kfm_agent_graph()
            run_logger.info(f"Created debug version of KFM agent graph in {time.time() - graph_start_time:.2f}s")
        else:
            kfm_app, components = create_kfm_agent_graph()
            run_logger.info(f"Created standard KFM agent graph in {time.time() - graph_start_time:.2f}s")
    except Exception as e:
        run_logger.exception(f"Failed to create KFM agent graph: {str(e)}", exc_info=True)
        return None
    
    # Create initial state
    initial_state = {
        "input": input_data,
        "task_name": task_name,
        # Initialize other optional fields potentially expected by nodes
        "performance_data": {},
        "task_requirements": {},
        "kfm_action": None,
        "active_component": None,
        "result": None,
        "execution_performance": None,
        "error": None,
        "done": False
    }
    run_logger.info(f"Invoking graph with initial state for task '{task_name}'.")
    run_logger.debug(f"Initial state: {initial_state}")
    
    # Run the graph
    final_state = None
    execution_start_time = time.time()
    
    try:
        # Use debug execution modes if requested
        if debug_mode and step_mode:
            run_logger.info("Running in step-by-step debug mode")
            final_state = step_through_execution(kfm_app, initial_state)
        elif debug_mode:
            run_logger.info("Running in debug mode")
            final_state = debug_graph_execution(kfm_app, initial_state)
        else:
            # Standard execution
            run_logger.info("Running in standard mode")
            final_state = kfm_app.invoke(initial_state)
            
        execution_time = time.time() - execution_start_time
        run_logger.info(f"Graph invocation complete. Execution time: {execution_time:.2f}s")
        run_logger.debug(f"Final state keys: {list(final_state.keys() if final_state else [])}")
        
        # Log success or error
        if final_state and not final_state.get('error'):
            run_logger.info("✅ Workflow completed successfully")
        elif final_state and final_state.get('error'):
            run_logger.error(f"❌ Workflow completed with errors: {final_state.get('error')}")
        
    except Exception as e:
        execution_time = time.time() - execution_start_time
        run_logger.exception(f"Error during graph invocation: {str(e)}", exc_info=True)
        run_logger.info(f"Failed execution time: {execution_time:.2f}s")
        
        # Try to return the state as it was when the error occurred if possible
        # This might depend on LangGraph's error handling
        if final_state is None:
             final_state = initial_state.copy()
        final_state["error"] = str(e)
    
    # Log total execution time
    total_time = time.time() - start_time
    run_logger.info("="*50)
    run_logger.info(f"KFM AGENT RUN COMPLETE - Total time: {total_time:.2f}s")
    if final_state and final_state.get('error'):
        run_logger.info(f"Execution status: FAILED - {final_state.get('error')}")
    else:
        run_logger.info("Execution status: SUCCESS")
    run_logger.info("="*50)
    
    return final_state

def print_state_trace(show_all_states: bool = False) -> None:
    """Print the complete state trace from the last execution.
    
    Args:
        show_all_states: Whether to show all state details
    """
    trace_viz = visualize_trace_path(show_all_states)
    print("\n" + trace_viz)

# Example usage block
def main():
    agent_logger.info("--- Running KFM Agent Example --- ")
    
    # Set debug flag from command-line argument if present
    debug_mode = '--debug' in sys.argv
    step_mode = '--step' in sys.argv
    
    # Set logging levels based on arguments
    log_level = logging.DEBUG if '--verbose' in sys.argv else logging.INFO
    
    # Configure centralized logging
    setup_centralized_logging()
    
    # Create a timestamped log file for this run
    log_file = create_timestamped_log_file("kfm_app")
    log_filename = os.path.basename(log_file)
    
    agent_logger.info(f"Logs will be written to session directory: {os.path.dirname(log_file)}")
    agent_logger.info(f"Main log file: {log_filename}")
    
    # Demonstrate creating and visualizing the graph
    try:
        agent_logger.info("Creating KFM Agent graph")
        kfm_app, components = create_kfm_agent_graph()
        
        # Save graph visualization to file
        visualization_file = f"kfm_graph_{time.strftime('%Y%m%d_%H%M%S')}.png"
        agent_logger.info(f"Generating graph visualization to {visualization_file}")
        
        visualization_saved = save_graph_visualization(kfm_app, visualization_file)
        if visualization_saved:
            print(f"Graph visualization saved to {visualization_file}")
            agent_logger.info(f"Graph visualization saved to {visualization_file}")
    except Exception as e:
        error_msg = f"Error creating or visualizing graph: {e}"
        print(error_msg)
        agent_logger.error(error_msg, exc_info=True)
        return
    
    # Run the agent with sample data
    test_message = "This is a sample text to analyze"
    agent_logger.info(f"Running agent with test message: {test_message}")
    
    input_data = {"text": test_message}
    final_result = run_kfm_agent(
        input_data, 
        debug_mode=debug_mode,
        step_mode=step_mode,
        trace_level=log_level,
        log_file=log_filename
    )
    
    if final_result:
        agent_logger.info("Agent execution completed successfully")
    else:
        agent_logger.error("Agent execution failed to return a result")

async def main_async(): # Renamed and made async
    agent_logger.info("--- Running KFM Agent Async --- ")
    
    debug_mode = '--debug' in sys.argv
    # step_mode = '--step' in sys.argv # Note: step_mode not directly used by AgentLifecycleController yet
    # log_level = logging.DEBUG if '--verbose' in sys.argv else logging.INFO
    
    # Reversal arguments parsing
    revert_snapshot_id = None
    revert_last_fuck_corr_id = None
    skip_normal_run = False

    for i, arg in enumerate(sys.argv):
        if arg == '--revert-snapshot' and i + 1 < len(sys.argv):
            revert_snapshot_id = sys.argv[i+1]
            skip_normal_run = True
            agent_logger.info(f"Reversal requested for snapshot ID: {revert_snapshot_id}")
            break
        elif arg == '--revert-last-fuck' and i + 1 < len(sys.argv):
            revert_last_fuck_corr_id = sys.argv[i+1]
            skip_normal_run = True
            agent_logger.info(f"Reversal requested for last 'Fuck' action associated with correlation ID: {revert_last_fuck_corr_id}")
            break

    setup_centralized_logging()
    log_file_path = create_timestamped_log_file("kfm_app_async")
    log_filename = os.path.basename(log_file_path)
    
    agent_logger.info(f"Logs will be written to session directory: {os.path.dirname(log_file_path)}")
    agent_logger.info(f"Main log file: {log_filename}")

    # Initialize Reversibility Components and LifecycleController
    try:
        snapshot_dir = "./kfm_snapshots_main_example"
        os.makedirs(snapshot_dir, exist_ok=True) 
        storage_backend = FileSnapshotStorage(base_storage_path=snapshot_dir)
        snapshot_service = SnapshotService(storage_backend=storage_backend)
        
        # Pass the local graph creation functions to the controller
        lifecycle_controller = AgentLifecycleController(
            create_graph_fn=create_kfm_agent_graph, 
            create_debug_graph_fn=create_debug_kfm_agent_graph,
            debug_graph=debug_mode
        )
        reversal_manager = ReversalManager(snapshot_service=snapshot_service, kfm_agent_instance=lifecycle_controller)
        agent_logger.info("Reversibility components and LifecycleController initialized.")
    except Exception as e:
        agent_logger.critical(f"Failed to initialize core services: {e}", exc_info=True)
        return

    # Conditional execution: Reversal or Normal Run
    if skip_normal_run:
        agent_logger.info("--- Performing Reversal Action --- ")
        if revert_snapshot_id:
            agent_logger.info(f"Attempting to revert agent to snapshot ID: {revert_snapshot_id}")
            try:
                reversal_result = await reversal_manager.revert_to_snapshot(revert_snapshot_id)
                if reversal_result.get("success"):
                    agent_logger.info(f"Reversal to snapshot {revert_snapshot_id} successful: {reversal_result.get('message')}")
                else:
                    agent_logger.error(f"Reversal to snapshot {revert_snapshot_id} failed: {reversal_result.get('error')}")
            except Exception as e:
                agent_logger.error(f"Exception during revert_to_snapshot call: {e}", exc_info=True)
        
        elif revert_last_fuck_corr_id:
            agent_logger.info(f"Attempting to revert last 'Fuck' action for correlation ID: {revert_last_fuck_corr_id}")
            try:
                # This method needs to be implemented in ReversalManager
                reversal_result = await reversal_manager.revert_last_fuck_action(revert_last_fuck_corr_id)
                if reversal_result.get("success"):
                    agent_logger.info(f"Reversal of last 'Fuck' action for {revert_last_fuck_corr_id} successful: {reversal_result.get('message')}")
                else:
                    agent_logger.error(f"Reversal of last 'Fuck' action for {revert_last_fuck_corr_id} failed: {reversal_result.get('error')}")
            except Exception as e:
                agent_logger.error(f"Exception during revert_last_fuck_action call: {e}", exc_info=True)
        else:
            agent_logger.warning("Reversal requested but no specific action/ID provided.")
    else:
        # Initial run (Normal execution path)
        agent_logger.info("--- Performing Normal Agent Run --- ")
        test_message = "This is a sample text for the KFM agent to analyze."
        initial_input_data = {"text": test_message}
        initial_agent_state_dict = {
            "input": initial_input_data,
            "task_name": "async_sample_task",
            "performance_data": {},
            "task_requirements": {},
            "kfm_action": None,
            "active_component": None,
            "result": None,
            "execution_performance": None,
            "error": None,
            "done": False
        }
        # KFMAgentState can be instantiated from this dict if needed,
        # but AgentLifecycleController._execute_run_internal expects a dict or Pydantic model.
        
        agent_logger.info(f"Starting initial agent run with input: '{test_message}'")
        try:
            run_result = await lifecycle_controller.start_new_run(initial_state=initial_agent_state_dict) # type: ignore
            if run_result and not run_result.get("error") and run_result.get("status") != "cancelled":
                agent_logger.info(f"Initial agent run completed. Status: {run_result.get('status', 'successful')}")
                agent_logger.debug(f"Initial run final state: {run_result}")
            else:
                agent_logger.error(f"Initial agent run failed or returned an error/cancelled. Result: {run_result}")
        except Exception as e:
            agent_logger.error(f"Exception during initial agent run: {e}", exc_info=True)
            return # Stop if initial run fails critically

    # --- Simulate Reversal --- 
    agent_logger.info("--- Attempting Reversal Simulation --- ")
    
    all_snapshot_ids = []
    try:
        # Ensure storage_backend is awaited if its methods are async (FileSnapshotStorage methods are generally sync)
        # For FileSnapshotStorage, list_snapshot_manifest_ids is synchronous.
        # If it were async, it would be: all_snapshot_ids = await storage_backend.list_snapshot_manifest_ids()
        all_snapshot_ids = storage_backend.list_snapshot_manifest_ids() 
    except Exception as e:
        agent_logger.error(f"Error listing snapshot IDs from storage backend: {e}", exc_info=True)

    snapshot_id_to_revert = None
    if all_snapshot_ids:
        snapshot_id_to_revert = all_snapshot_ids[0] # Revert to the first one found
        agent_logger.info(f"Found {len(all_snapshot_ids)} snapshots. Will attempt to revert to the first one: {snapshot_id_to_revert}")
    else:
        agent_logger.warning("No snapshots found from the initial run. Cannot demonstrate reversal.")

    if snapshot_id_to_revert:
        agent_logger.info(f"Attempting to revert agent to snapshot ID: {snapshot_id_to_revert}")
        try:
            reversal_result = await reversal_manager.revert_to_snapshot(snapshot_id_to_revert)
            
            if reversal_result.get("success"):
                agent_logger.info(f"Reversal successful: {reversal_result.get('message')}")
                # To confirm, one might start another small run or check some state.
                agent_logger.info("Agent should have been restarted with the restored state.")
            else:
                agent_logger.error(f"Reversal failed: {reversal_result.get('error')}")
        except Exception as e:
            agent_logger.error(f"Exception during reversal attempt: {e}", exc_info=True)
    else:
        agent_logger.info("Skipping reversal demonstration as no suitable snapshot ID was identified.")

    agent_logger.info("--- KFM Agent Async Finished --- ")


if __name__ == "__main__":
    # main() # Original main can be kept for other testing if needed.
    asyncio.run(main_async()) 