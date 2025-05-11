import asyncio
import traceback # For error logging
import time # Added to resolve potential linter issue with time.time()
from typing import Any, Optional, Dict, Tuple, Callable, Coroutine
import logging
import uuid
import json
from datetime import datetime

from src.state_types import KFMAgentState
from src.logger import setup_logger
from src.core.reversibility.snapshot_service import SnapshotService
from src.core.component_registry import ComponentRegistry
from src.core.execution_engine import ExecutionEngine
from src.core.kfm_planner_llm import KFMPlannerLlm

lifecycle_logger = logging.getLogger(__name__)
# Ensure logs propagate to allow capture by testing frameworks like pytest's caplog,
# or for centralized logging setups.
lifecycle_logger.propagate = True 

class AgentLifecycleController:
    """
    Manages the lifecycle of the KFM agent's LangGraph application,
    including starting, stopping, and restarting with specific states.
    """
    def __init__(self, 
                 snapshot_service: SnapshotService,
                 component_registry: ComponentRegistry,
                 execution_engine: ExecutionEngine,
                 kfm_planner_instance: KFMPlannerLlm, # KFMPlannerLlm or a compatible mock
                 graph_creation_fn_factory: Callable[[], Callable[..., Coroutine[Any, Any, Any]]], # Factory returning the async graph_creation_fn
                 graph_config_fn_factory: Callable[[], Callable[..., Coroutine[Any, Any, Any]]],   # Factory returning the async graph_config_fn
                 debug_graph: bool = False):
        self.logger = setup_logger(self.__class__.__name__)
        self.snapshot_service = snapshot_service
        self.component_registry = component_registry
        self.execution_engine = execution_engine
        self.kfm_planner_instance = kfm_planner_instance
        
        if not callable(graph_creation_fn_factory) or not callable(graph_config_fn_factory):
            raise ValueError("graph_creation_fn_factory and graph_config_fn_factory must be callable factories.")

        self._graph_creation_fn_factory = graph_creation_fn_factory
        self._graph_config_fn_factory = graph_config_fn_factory
        
        self.initial_debug_graph_flag = debug_graph # Retained for potential future use, though not directly used by current _ensure_graph_initialized
        self.current_execution_task: Optional[asyncio.Task] = None
        self.next_initial_state: Optional[KFMAgentState] = None
        self.current_run_config: Optional[Dict] = None
        self.current_run_id: Optional[str] = None
        self._stop_event = asyncio.Event() # Used to signal stop to the running task
        self.current_task = None
        self.kfm_app: Optional[Any] = None
        self.agent_components: Optional[Dict[str, Any]] = None

    def _get_graph_creation_functions(self) -> Tuple[Optional[Callable], Optional[Callable]]:
        """Calls the stored factories to get the actual graph and config creation functions."""
        graph_fn = self._graph_creation_fn_factory() if self._graph_creation_fn_factory else None
        config_fn = self._graph_config_fn_factory() if self._graph_config_fn_factory else None
        if graph_fn is None or config_fn is None:
            self.logger.error("Graph or config creation function factory did not produce a function.")
            return None, None
        return graph_fn, config_fn

    async def _ensure_graph_initialized(self):
        """Ensures the graph is initialized. Called by methods that need the graph."""
        if self.kfm_app is None:
            graph_creation_fn, config_creation_fn = self._get_graph_creation_functions()
            if graph_creation_fn is None or config_creation_fn is None:
                raise RuntimeError("Graph creation functions not set during AgentLifecycleController initialization.")
            
            graph_config = await config_creation_fn(self.snapshot_service, self.component_registry, self.execution_engine, self.kfm_planner_instance)
            self.kfm_app = await graph_creation_fn(graph_config)
            if self.kfm_app is None:
                raise RuntimeError("KFM Agent graph (kfm_app) could not be initialized by the lifecycle controller.")

    async def stop_current_run(self, run_id_to_stop: Optional[str] = None) -> bool:
        lifecycle_logger.info("Attempting to stop current agent execution task...")
        if self.current_execution_task and not self.current_execution_task.done():
            self.current_execution_task.cancel()
            try:
                await self.current_execution_task
                lifecycle_logger.info("Current execution task was awaited after cancellation signal (may have completed or raised CancelledError).")
            except asyncio.CancelledError:
                lifecycle_logger.info("Current execution task was cancelled as expected.")
            except Exception as e:
                lifecycle_logger.error(f"Error encountered while awaiting cancelled task: {e}", exc_info=True)
            finally:
                self.current_execution_task = None
        else:
            lifecycle_logger.info("No active execution task to stop, or task already done.")
        return True

    async def prepare_for_new_run_with_state(self, initial_state: KFMAgentState):
        lifecycle_logger.info(f"Preparing for new run with provided initial state.")
        # Stop any ongoing run before preparing a new one.
        if self.current_execution_task and not self.current_execution_task.done():
            lifecycle_logger.warning("An existing task is active. Stopping it before preparing for a new run.")
            await self.stop_current_run()
        
        self.next_initial_state = initial_state
        lifecycle_logger.info(f"Next initial state has been set. Agent is ready to be started with this state.")
        # Optional: Re-initialize graph if strict separation between runs is needed
        # self._initialize_graph() 

    async def start_new_run(
        self, 
        initial_state: KFMAgentState # Changed from initial_input, and made non-optional for clarity here
    ) -> Optional[KFMAgentState]:
        """Starts a new agent run with the given initial state."""
        await self._ensure_graph_initialized()

        if self.current_task and not self.current_task.done():
            self.logger.warning("Attempting to start a new run while a previous run may still be active. This is not recommended.")
            # Optionally, cancel the previous task here if that's the desired behavior
            # self.stop_current_run(reason="Starting a new run")

        run_id = initial_state.get("run_id")
        if not run_id:
            run_id = str(uuid.uuid4())
            initial_state["run_id"] = run_id # Ensure run_id is in the state to be passed
            self.logger.info(f"Generated new run_id for new run: {run_id}")
        
        # Ensure original_correlation_id is also present if not already
        if not initial_state.get("original_correlation_id"):
            initial_state["original_correlation_id"] = initial_state.get("run_id") # Default to run_id if not present
            self.logger.info(f"original_correlation_id set to run_id: {initial_state['original_correlation_id']}")

        # Set the current run configuration for LangGraph
        self.current_run_config = {"configurable": {"thread_id": run_id}}
        self.current_run_id = run_id # Also store the run_id directly if needed elsewhere

        self.logger.info(f"Starting new agent run. Run ID: {run_id}, Thread ID for LangGraph: {self.current_run_config['configurable']['thread_id']}")
        self.logger.debug(f"Initial state for new run ({run_id}): {json.dumps(initial_state, indent=2, default=str)}")

        # prepare_for_new_run_with_state now primarily sets self.next_initial_state and handles stopping previous runs.
        # The initial_state for the *current* run is passed directly to _execute_run_internal.
        await self.prepare_for_new_run_with_state(run_id=run_id, restored_state=initial_state) 

        final_state_from_graph = await self._execute_run_internal(initial_graph_state=initial_state)
        
        if final_state_from_graph is None:
            self.logger.error(f"Agent run (ID: {run_id}) _execute_run_internal returned None. This should not happen.")
            # Construct a basic error KFMAgentState
            current_time_iso = datetime.utcnow().isoformat() + "Z"
            error_payload = {
                "type": "InternalError",
                "message": "Agent execution failed to return a state.",
                "category": "FATAL",
                "severity": 5,
                "timestamp": current_time_iso,
                "recoverable": False,
                "details": {"run_id": run_id, "reason": "_execute_run_internal returned None"}
            }
            final_state_from_graph = KFMAgentState(
                error=json.dumps(error_payload),
                done=True,
                original_correlation_id=initial_state.get("original_correlation_id"),
                run_id=run_id
            )

        self.logger.info(f"Agent run (ID: {run_id}) completed. Final state error: {final_state_from_graph.get('error')}, Done: {final_state_from_graph.get('done')}")
        self.current_task = None # Clear task after completion or error
        return final_state_from_graph

    async def prepare_for_new_run_with_state(self, run_id: str, restored_state: Optional[KFMAgentState] = None):
        # lifecycle_logger.info(f"Preparing for new run with provided initial state.") # logger is self.logger now
        self.logger.info(f"Preparing for new run. Run ID: {run_id}")
        
        # Stop any ongoing run before preparing a new one.
        if self.current_execution_task and not self.current_execution_task.done():
            self.logger.warning("An existing task is active. Stopping it before preparing for a new run.")
            await self.stop_current_run()
        
        self.next_initial_state = restored_state
        self.logger.info(f"Next initial state has been set. Agent is ready to be started with this state.")
        # Optional: Re-initialize graph if strict separation between runs is needed
        # self._initialize_graph() 

    async def _execute_run_internal(self, initial_graph_state: KFMAgentState) -> Optional[KFMAgentState]:
        """Internal method to execute the agent run, designed to be awaited as a task."""
        if self.kfm_app is None or self.current_run_config is None:
            self.logger.error("Agent or run configuration not initialized before _execute_run_internal.")
            # Return a KFMAgentState with an error
            current_time_iso = datetime.utcnow().isoformat() + "Z"
            error_payload = {
                "type": "InternalError",
                "message": "Agent/run config not initialized.",
                "category": "FATAL",
                "severity": 5,
                "timestamp": current_time_iso,
                "recoverable": False,
                "details": {"run_id": self.current_run_id if hasattr(self, 'current_run_id') else 'unknown'}
            }
            return KFMAgentState(
                error=json.dumps(error_payload),
                done=True
            )

        try:
            # Ensure LangSmith tracing context if run_id is available in config
            trace_config = {}
            if self.current_run_config and self.current_run_config.get("configurable", {}).get("thread_id"):
                trace_config = {"metadata": {"langgraph_run_id": self.current_run_config["configurable"]["thread_id"]}}
            
            async for event in self.kfm_app.astream_events(initial_graph_state, config=self.current_run_config, version="v1"):
                kind = event["event"]
                if kind == "on_chain_end": # or on_chat_model_end, on_llm_end, etc.
                    # This is where you'd typically get the final state or output
                    # For StateGraph, the final state is usually in event["data"]["output"]
                    # However, astream_events does not easily give the *final accumulated state* in one go.
                    # It's better to use ainvoke for the final state if that's the primary need.
                    pass # Intermediate event processing if needed

            # After iterating through events, get the final state explicitly
            # This ensures we have the complete accumulated state.
            final_graph_output = await self.kfm_app.ainvoke(initial_graph_state, config=self.current_run_config)
            
            if not isinstance(final_graph_output, dict):
                self.logger.error(f"Graph execution returned unexpected type: {type(final_graph_output)}. Expected dict (KFMAgentState).")
                current_time_iso = datetime.utcnow().isoformat() + "Z"
                error_payload = {
                    "type": "GraphError",
                    "message": "Graph returned non-dictionary state.",
                    "category": "FATAL",
                    "severity": 5,
                    "timestamp": current_time_iso,
                    "recoverable": False,
                    "details": {"run_id": self.current_run_id, "return_type": str(type(final_graph_output))}
                }
                return KFMAgentState(error=json.dumps(error_payload), done=True)

            # Ensure it's a KFMAgentState structure, especially if 'error' is present. 'done' should always be there.
            final_state = KFMAgentState(**final_graph_output)
            if 'done' not in final_state:
                final_state['done'] = True # Default to done if not specified by graph, especially on error or unexpected end

            return final_state
            
        except Exception as e:
            tb_str = traceback.format_exc()
            self.logger.error(f"Exception during agent execution (_execute_run_internal): {e}\n{tb_str}")
            current_time_iso = datetime.utcnow().isoformat() + "Z"
            error_payload = {
                "type": "AgentExecutionError",
                "message": str(e),
                "category": "FATAL",
                "severity": 5,
                "timestamp": current_time_iso,
                "recoverable": False,
                "details": {"run_id": self.current_run_id, "traceback": tb_str}
            }
            return KFMAgentState(error=json.dumps(error_payload), done=True)

