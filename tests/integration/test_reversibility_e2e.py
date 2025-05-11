import pytest
import pytest_asyncio
import asyncio
import os
import uuid
import logging
from typing import Dict, Any, Optional, Tuple, List, Callable

from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage
from src.core.reversibility.snapshot_service import SnapshotService, SnapshotManifest
from src.core.reversibility.reversal_manager import ReversalManager, ReversalResult
from src.core.agent_lifecycle_controller import AgentLifecycleController
from src.core.kfm_planner_llm import KFMPlannerLlm, KFMDecision
from src.core.execution_engine import ExecutionEngine, ExecutionResult
from src.core.state_monitor import StateMonitor
from src.core.component_registry import ComponentRegistry
from src.core.discovery import ModuleMetadata
from src.state_types import KFMAgentState, ActionType
from src.langgraph_nodes import monitor_state_node, kfm_decision_node, execute_action_node, reflect_node, fallback_node, should_fallback
from src.logger import setup_logger
from src.core.ethical_manager_instance import get_ecm_instance

from langgraph.graph import StateGraph, END

# --- Mocks & Test Utilities ---

class MockKFMPlannerLlm(KFMPlannerLlm):
    def __init__(self, component_registry: ComponentRegistry, decision_to_make: Optional[Dict[str, Any]] = None, model_name: str = "mock_planner_model_default"):
        # Call the KFMPlannerLlm's __init__ directly via super(),
        # providing the arguments it requires.
        # KFMPlannerLlm.__init__ will then handle its own Pydantic field initialization.
        super().__init__(
            component_registry=component_registry,
            model_name=model_name
            # Other arguments for KFMPlannerLlm.__init__ (memory_manager, prompt_manager, etc.)
            # will use their defaults as defined in KFMPlannerLlm.__init__ signature,
            # unless explicitly passed here.
        )
        
        # Set mock-specific attributes AFTER the parent is initialized
        self.decision_to_make = decision_to_make or {
            "action": "No Action", 
            "component": "default_component_A_from_mock", 
            "reasoning": "Default mock decision: No Action chosen by MockKFMPlannerLlm",
            "confidence": 1.0
        }
        self.logger = setup_logger(self.__class__.__name__) # Explicitly set logger for the mock

    async def decide_kfm_action(self, current_state: KFMAgentState) -> Dict:
        task_name = current_state.get("task_name", "Unknown Task")
        self.logger.info(f"MockKFMPlannerLlm: Deciding action for task '{task_name}' based on current_state. Returning pre-defined: {self.decision_to_make}")
        # Ensure it returns a dict compatible with KFMDecision().to_dict()
        # If KFMDecision is directly returned by real planner, mock should do so too then convert.
        # For simplicity, if decision_to_make is already a dict, return it.
        # If it's a KFMDecision object, call .to_dict()
        if isinstance(self.decision_to_make, KFMDecision):
            return self.decision_to_make.to_dict()
        return self.decision_to_make

class MockExecutionEngine:
    def __init__(self, action_results: Optional[Dict[Tuple[str, str], Any]] = None, action_errors: Optional[Dict[Tuple[str, str], Exception]] = None):
        self.action_results = action_results or {}
        self.action_errors = action_errors or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    async def execute(self, action_type: ActionType, target_component: Optional[str], params: Dict, agent_state: KFMAgentState) -> ExecutionResult:
        self.logger.info(f"MockExecutionEngine: Executing action '{action_type.value}' on component '{target_component}' with params {params}")
        
        action_key = (str(target_component), action_type.value) # Key by (component_name_str, action_value_str)

        if action_key in self.action_errors:
            error_to_raise = self.action_errors[action_key]
            self.logger.warning(f"MockExecutionEngine: Intentionally raising error for {action_key}: {type(error_to_raise).__name__}: {error_to_raise}")
            raise error_to_raise
        
        result = self.action_results.get(action_key, {"status": "mock_success", "detail": f"Mock result for {action_key}"})
        self.logger.info(f"MockExecutionEngine: Returning result for '{action_key}': {result}")
        return result

# --- Fixtures ---

@pytest.fixture
def temp_snapshot_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("kfm_e2e_snapshots")

@pytest_asyncio.fixture
async def snapshot_service(temp_snapshot_dir) -> SnapshotService:
    storage = FileSnapshotStorage(base_storage_path=str(temp_snapshot_dir))
    service = SnapshotService(snapshot_storage=storage)
    return service

@pytest.fixture
def component_registry() -> ComponentRegistry:
    """Provides a ComponentRegistry instance."""
    # This could be a real ComponentRegistry, as its methods are simple
    # and we might want it to discover mock components if our tests get more complex.
    # For now, it can be empty or have minimal setup.
    registry = ComponentRegistry()
    # Manually add some dummy metadata if needed for planner or other nodes
    # Example: 
    # registry.register_component_metadata(
    #     "dummy_component", 
    #     ModuleMetadata(module_name="dummy_component", version="1.0", description="...", entry_point="...", supports_reversibility=False)
    # )
    return registry

@pytest.fixture
def mock_kfm_planner(component_registry: ComponentRegistry, snapshot_service: SnapshotService) -> MockKFMPlannerLlm:
    # Default decision can be overridden in tests
    return MockKFMPlannerLlm(component_registry)

@pytest.fixture
def mock_execution_engine() -> MockExecutionEngine:
    return MockExecutionEngine()

# Fixture for creating a graph with mocked components
@pytest.fixture
def create_mocked_agent_graph_fns_factories(
    component_registry: ComponentRegistry, 
    mock_kfm_planner: MockKFMPlannerLlm, 
    mock_execution_engine: MockExecutionEngine, 
    snapshot_service: SnapshotService 
) -> Tuple[Callable[[], Callable], Callable[[], Callable]]:
    
    # Define the actual config creator function
    # It will be called by AgentLifecycleController with its instances of these services.
    async def actual_config_creator_fn(
        ss_param: SnapshotService, 
        cr_param: ComponentRegistry, 
        ee_param: MockExecutionEngine, # Should match type used in ALC context
        planner_param: MockKFMPlannerLlm # Should match type used in ALC context
    ):
        return {
            "component_registry": cr_param,
            "planner_llm": planner_param,
            "engine": ee_param,
            "snapshot_service": ss_param
            # Add any other items that nodes might expect from graph_config
        }

    # Define the actual graph creator function
    # It will take the graph_config produced by actual_config_creator_fn
    async def actual_graph_creator_fn(graph_config_dict: Dict[str, Any]):
        # Extract services from graph_config_dict for node wrappers
        # This ensures nodes use the instances provided through graph_config_dict
        
        # Node wrappers
        async def wrapped_monitor_node(state: KFMAgentState, config: Optional[Dict] = None) -> KFMAgentState:
            # Ensure graph_config_dict is correctly populated by actual_config_creator_fn
            sm_instance = StateMonitor(
                component_registry=graph_config_dict['component_registry'], 
                performance_data=state.get('all_components_details', {}),
                # Provide a default task requirement to avoid KeyError in StateMonitor
                task_requirements={"default": {"min_similarity": 0.0, "max_risk": 1.0}} 
            )
            # DEBUG print
            # print(f"DEBUG: wrapped_monitor_node received state with original_correlation_id: {state.get('original_correlation_id')}, run_id: {state.get('run_id')}")
            return await monitor_state_node(state, state_monitor=sm_instance, snapshot_service=graph_config_dict['snapshot_service'])

        async def wrapped_decision_node(state: KFMAgentState, config: Optional[Dict] = None) -> KFMAgentState:
            return await kfm_decision_node(state, kfm_planner=graph_config_dict['planner_llm'], snapshot_service=graph_config_dict['snapshot_service'])
        
        async def wrapped_execution_node(state: KFMAgentState, config: Optional[Dict] = None) -> KFMAgentState:
            return await execute_action_node(state, execution_engine=graph_config_dict['engine'], snapshot_service=graph_config_dict['snapshot_service'])

        async def wrapped_reflect_node(state: KFMAgentState, config: Optional[Dict] = None) -> KFMAgentState:
            return await reflect_node(state, snapshot_service=graph_config_dict['snapshot_service'])

        async def wrapped_fallback_node(state: KFMAgentState, config: Optional[Dict] = None) -> KFMAgentState:
            return await fallback_node(state, kfm_planner_original=graph_config_dict['planner_llm'], snapshot_service=graph_config_dict['snapshot_service'])

        builder = StateGraph(KFMAgentState)
        builder.add_node("monitor", wrapped_monitor_node)
        builder.add_node("decide", wrapped_decision_node)
        builder.add_node("execute", wrapped_execution_node)
        builder.add_node("reflect", wrapped_reflect_node)
        builder.add_node("fallback", wrapped_fallback_node)

        builder.set_entry_point("monitor")
        builder.add_edge("monitor", "decide")
        
        builder.add_edge("execute", "reflect")
        builder.add_edge("fallback", "reflect") # Edge from fallback node to reflect node

        builder.add_conditional_edges( # This is the correct conditional edge for 'decide'
            "decide",
            should_fallback, 
            {"fallback": "fallback", "execute": "execute"} 
        )
        
        builder.add_conditional_edges("reflect", lambda state: END if state.get("done") or state.get("error") else "monitor")

        checkpointer = None
        if hasattr(graph_config_dict['snapshot_service'], 'checkpointer') and graph_config_dict['snapshot_service'].checkpointer:
            checkpointer = graph_config_dict['snapshot_service'].checkpointer
        app = builder.compile(checkpointer=checkpointer)
        
        return app # Only the app is returned by the graph creator

    # Return factories
    return lambda: actual_graph_creator_fn, lambda: actual_config_creator_fn


@pytest_asyncio.fixture
async def agent_lifecycle_controller(
    snapshot_service: SnapshotService,
    component_registry: ComponentRegistry,
    mock_execution_engine: MockExecutionEngine, # Pass the actual engine instance
    mock_kfm_planner: MockKFMPlannerLlm,         # Pass the actual planner instance
    create_mocked_agent_graph_fns_factories: Tuple[Callable[[], Callable], Callable[[], Callable]] # Use the new fixture
) -> AgentLifecycleController:
    graph_creation_fn_factory, graph_config_fn_factory = create_mocked_agent_graph_fns_factories
    
    controller = AgentLifecycleController(
        snapshot_service=snapshot_service,
        component_registry=component_registry,
        execution_engine=mock_execution_engine, # Pass to ALC
        kfm_planner_instance=mock_kfm_planner, # Pass to ALC
        graph_creation_fn_factory=graph_creation_fn_factory,
        graph_config_fn_factory=graph_config_fn_factory,
        debug_graph=False 
    )
    return controller

@pytest_asyncio.fixture
async def reversal_manager(snapshot_service, agent_lifecycle_controller) -> ReversalManager:
    # Pass the already initialized AgentLifecycleController
    manager = ReversalManager(
        snapshot_service=snapshot_service, 
        lifecycle_controller=agent_lifecycle_controller # Corrected: kfm_agent_instance to lifecycle_controller
    )
    return manager


# --- Test Cases ---

@pytest.mark.asyncio
async def test_dummy_placeholder():
    """ Placeholder test to ensure the file is picked up by pytest. """
    assert True

@pytest.mark.asyncio
async def test_manual_reversal_of_fuck_action(
    agent_lifecycle_controller: AgentLifecycleController,
    reversal_manager: ReversalManager,
    mock_kfm_planner: MockKFMPlannerLlm, # To control the decision
    snapshot_service: SnapshotService, # To inspect snapshots if needed
    temp_snapshot_dir: str # For path inspection if needed
):
    """ 
    Tests manual reversal of a 'Fuck' action. 
    1. Agent runs, decides 'Fuck' action, pre-Fuck snapshot is taken.
    2. Action (mocked) 'completes'.
    3. ReversalManager reverts to the pre-Fuck snapshot.
    4. Agent state is checked post-reversal.
    """
    original_correlation_id = f"e2e_manual_reversal_corr_{uuid.uuid4()}"
    task_name = "e2e_manual_reversal_task"
    target_component_id = "component_for_fuck"

    # Configure mock planner to decide 'Fuck'
    mock_kfm_planner.decision_to_make = {
        "action": "Fuck",
        "component": target_component_id,
        "reasoning": "E2E Test: Intentionally choosing Fuck action",
        "confidence": 0.99
    }

    initial_agent_state_dict = {
        "input": {"data": "some_initial_input_for_manual_reversal"},
        "task_name": task_name,
        "original_correlation_id": original_correlation_id,
        "run_id": original_correlation_id, # For simplicity in this test, run_id = original_correlation_id
        "current_task_requirements": {"min_accuracy": 0.1, "max_latency": 1000},
        "activation_type": "planner_decision_e2e", # Added for reflect_node
        "all_components_details": { # Provide some details for the monitor node and planner
            target_component_id: [
                {
                    "module_name": target_component_id,
                    "version": "1.0",
                    "description": "A test component for Fuck action",
                    "entry_point": "main.py",
                    "supports_reversibility": True,
                    "performance_metrics": {"accuracy": 0.5, "latency": 500} # Meets neither for Marry, eligible for Fuck
                }
            ]
        },
        # ... other necessary initial state fields ...
        "kfm_action": None,
        "done": False,
        "error": None
    }

    # --- 1. Run Agent to perform the 'Fuck' action ---
    # The graph is set up with the mocked planner and engine
    # The execute_action_node will call snapshot_service for pre_execution_snapshot
    # The kfm_decision_node will call snapshot_service for decision_post_planner_pre_fuck
    run_result_dict = await agent_lifecycle_controller.start_new_run(initial_state=initial_agent_state_dict)

    assert run_result_dict is not None, "Agent run did not produce a result"
    # print(f"Run result from initial run: {run_result_dict}")
    # Depending on graph structure, it might run to END or wait. Assume it ends or is cancellable.
    # For this test, we are interested in the snapshots created, specifically the pre-Fuck one.

    # --- 2. Identify the pre-Fuck action snapshot ---
    # This relies on the kfm_decision_node correctly taking a snapshot with
    # metadata: trigger_event="decision_post_planner_pre_fuck" or is_fuck_action_pre_snapshot=True
    # and original_correlation_id matching.
    pre_fuck_snapshot_id = await reversal_manager.identify_pre_fuck_action_snapshot_id(original_correlation_id)
    assert pre_fuck_snapshot_id is not None, f"Could not identify a pre-Fuck action snapshot for correlation_id {original_correlation_id}"
    
    # --- 3. Perform Manual Reversal ---
    reversal_outcome = await reversal_manager.revert_to_snapshot(pre_fuck_snapshot_id)
    assert reversal_outcome.success, f"Reversal to snapshot {pre_fuck_snapshot_id} failed: {reversal_outcome.message}"
    assert reversal_outcome.snapshot_id_used == pre_fuck_snapshot_id

    # --- 4. Validate Agent State Post-Reversal ---
    # The agent_lifecycle_controller should have restarted the graph with the restored state.
    # The restored state should be from *before* the 'Fuck' action was committed to state for execution.
    # The `kfm_decision_node` takes the pre-Fuck snapshot *after* the Fuck decision is made but *before* `execute_action_node`.
    # So, the restored state will have the 'Fuck' action in `kfm_action` field from the planner.
    
    # The lifecycle_controller.current_agent_state_dict might reflect the state *after* the new run (post-reversal) has completed a cycle.
    # To check the *exact* restored state that the new run started with, we'd ideally look at the input to the first node of the new run.
    # For now, let's load the snapshot data directly to verify what was restored.
    
    restored_agent_state_data = await snapshot_service.load_snapshot_agent_state_data(pre_fuck_snapshot_id)
    assert restored_agent_state_data is not None, f"Could not load data for snapshot {pre_fuck_snapshot_id}"

    # Verify key aspects of the restored state
    # This state is from kfm_decision_node, *after* planner decided "Fuck", *before* execution
    assert restored_agent_state_data.get("task_name") == task_name
    assert restored_agent_state_data.get("original_correlation_id") == original_correlation_id
    
    restored_kfm_action = restored_agent_state_data.get("kfm_action")
    assert restored_kfm_action is not None, "Restored state is missing 'kfm_action'"
    assert restored_kfm_action.get("action") == "Fuck", "Restored state's kfm_action should be 'Fuck' as it was snapshotted post-decision"
    assert restored_kfm_action.get("component") == target_component_id

    # The agent lifecycle controller starts a *new run* with this restored state.
    # We need to see what the first node (monitor) of this *new run* receives.
    # The AgentLifecycleController's `start_new_run` returns the final state of that new run.
    # Let's inspect the final state of the run that happened *after* reversal.
    # This state might have progressed if the graph invoked by revert_to_snapshot runs and then ends.
    
    # To keep it simple, assume the graph invoked by revert_to_snapshot runs and then ends.
    # The `reversal_outcome` itself is from `reversal_manager.revert_to_snapshot`, which calls `lifecycle_controller.start_new_run()`.
    # The result of that `start_new_run` is not directly in `reversal_outcome` other than success/message.
    # Need a way to get the state from the ALC *after* the reverted run.

    # Perhaps the simplest for now is to check that ALC is no longer running its *original* task_instance
    # and is ready for a new task, or has completed the reverted one.
    # This depends on AgentLifecycleController's state management. 
    # For now, the checks on `restored_agent_state_data` are the most direct validation of the restored content.

    # Optional: If the agent runs again from the restored state, what would it do?
    # If it re-enters `kfm_decision_node` with the same state (including the "Fuck" action in kfm_action),
    # it might try to execute it again. The `kfm_decision_node` should ideally be robust to this,
    # or the state loaded should be from *before* the decision was made if we want re-planning.
    # The current snapshot logic (is_fuck_action_pre_snapshot) is *after* planner decided "Fuck".
    # This is suitable for auto-reversal on EXECUTION failure of Fuck.
    # For a manual "undo Fuck", one might want a snapshot from *before* the Fuck decision.
    # This test validates the current "pre-execution of Fuck" snapshot reversal.

    # TODO: Add assertions about the *new* run started by the lifecycle_controller if possible.
    # For instance, if the agent is run again with the restored state, it should not immediately re-execute "Fuck"
    # if the intent of reversal is to re-evaluate. This depends on graph logic for handling pre-set kfm_action.
    # Our current graph re-evaluates from monitor. If kfm_action is already set, decide node might pass it through.
    # kfm_decision_node's current logic: "if state.get('error') is not None: ... return updated_state"
    # "if state.get('done', False): ... return updated_state" -> it proceeds to planner call. Good.

@pytest.mark.asyncio
async def test_automatic_reversal_on_fuck_action_failure(
    agent_lifecycle_controller: AgentLifecycleController,
    mock_kfm_planner: MockKFMPlannerLlm,
    mock_execution_engine: MockExecutionEngine, # To simulate action failure
    snapshot_service: SnapshotService # To inspect snapshots
):
    """
    Tests automatic reversal when a 'Fuck' action fails during execution.
    1. Agent decides 'Fuck' action, pre-Fuck snapshot is taken by kfm_decision_node.
    2. Pre-execution snapshot is taken by execute_action_node.
    3. Mocked ExecutionEngine raises an error for the 'Fuck' action.
    4. Execute_action_node should catch this, load the pre-execution snapshot, and return a new state indicating auto-reversal.
    5. Verify the final agent state and that a post-auto-reversal snapshot was taken.
    """
    original_correlation_id = f"e2e_auto_reversal_corr_{uuid.uuid4()}"
    task_name = "e2e_auto_reversal_task"
    target_component_id = "component_for_failed_fuck"
    simulated_error_message = "Simulated critical failure during Fuck action!"

    # 1. Configure mock planner to decide 'Fuck'
    mock_kfm_planner.decision_to_make = {
        "action": "Fuck",
        "component": target_component_id,
        "reasoning": "E2E Test: Intentionally choosing Fuck for auto-reversal test",
        "confidence": 0.98
    }

    # 2. Configure mock execution engine to fail this specific 'Fuck' action
    mock_execution_engine.action_errors[(target_component_id, "Fuck")] = RuntimeError(simulated_error_message)

    initial_agent_state_dict = {
        "input": {"data": "some_initial_input_for_auto_reversal"},
        "task_name": task_name,
        "original_correlation_id": original_correlation_id,
        "run_id": original_correlation_id,
        "current_task_requirements": {"min_accuracy": 0.2, "max_latency": 800},
        "activation_type": "planner_decision_e2e", # Added for reflect_node
        "all_components_details": { # Provide some details for the monitor node and planner
            target_component_id: [
                {
                    "module_name": target_component_id,
                    "version": "1.0",
                    "description": "A test component for failed Fuck action",
                    "entry_point": "main.py",
                    "supports_reversibility": True,
                    "performance_metrics": {"accuracy": 0.4, "latency": 600} 
                }
            ]
        },
        "kfm_action": None,
        "done": False,
        "error": None
    }

    # --- 3. Run Agent ---
    # The execute_action_node is expected to handle the error and perform auto-reversal.
    final_run_state = await agent_lifecycle_controller.start_new_run(initial_state=initial_agent_state_dict)

    assert final_run_state is not None, "Agent run (with expected failure and auto-reversal) did not produce a final state"

    # --- 4. Validate Agent State Post-Auto-Reversal ---
    assert final_run_state.get("done") is True, "Agent should be marked as done after auto-reversal."
    
    error_message_in_state = final_run_state.get("error")
    assert error_message_in_state is not None, "Error message should be set in state after auto-reversal."
    assert isinstance(error_message_in_state, dict), "Error in state should be a dictionary"
    assert "State auto-reverted to pre-action snapshot" in error_message_in_state.get("message", ""), \
        f"Auto-reversal message not found in error details. Error: {error_message_in_state}"

    auto_reverted_snapshot_id = final_run_state.get("auto_reverted_from_snapshot")
    assert auto_reverted_snapshot_id is not None, "'auto_reverted_from_snapshot' ID should be set."
    
    # Check that the reverted snapshot (which was the pre-execution one) exists
    reverted_manifest = await snapshot_service.storage.get_snapshot_manifest(auto_reverted_snapshot_id)
    assert reverted_manifest is not None, f"The auto-reverted snapshot {auto_reverted_snapshot_id} manifest could not be found."
    assert reverted_manifest.metadata.get("trigger_event") == "pre_execution"
    assert reverted_manifest.metadata.get("component_id") == target_component_id
    assert reverted_manifest.metadata.get("action_name") == "Fuck"
    assert reverted_manifest.metadata.get("original_correlation_id") == original_correlation_id

    reverted_kfm_action = final_run_state.get("kfm_action")
    assert reverted_kfm_action is not None, "kfm_action should be set in state after auto-reversal."
    assert reverted_kfm_action.get("action") == "No Action", "kfm_action should be 'No Action' after auto-reversal."
    assert target_component_id in reverted_kfm_action.get("reasoning", ""), "Reasoning should mention the original target component."

    execution_result_in_state = final_run_state.get("execution_result")
    assert execution_result_in_state is not None, "execution_result should be set."
    assert execution_result_in_state.get("status") == "auto_reverted"
    assert simulated_error_message in execution_result_in_state.get("message", "")

    # --- 5. Verify that a "post_auto_reversal" snapshot was taken ---
    # We need to find this snapshot. Its ID is not directly in the state.
    # We can list manifests and look for the trigger_event.
    all_manifest_ids = await snapshot_service.storage.list_snapshot_manifests(limit=100)
    post_auto_reversal_snapshot_found = False
    for manifest_id in all_manifest_ids:
        manifest = await snapshot_service.storage.get_snapshot_manifest(manifest_id)
        if manifest and manifest.metadata.get("trigger_event") == "post_auto_reversal":
            assert manifest.metadata.get("original_action_name") == "Fuck"
            assert manifest.metadata.get("original_component_id") == target_component_id
            assert manifest.metadata.get("reverted_to_snapshot_id") == auto_reverted_snapshot_id
            assert manifest.metadata.get("original_correlation_id") == original_correlation_id
            post_auto_reversal_snapshot_found = True
            break
    assert post_auto_reversal_snapshot_found, "A 'post_auto_reversal' snapshot was not found."

# More tests will be added here for Scenario 1 and Scenario 2.
# For example:
# async def test_manual_reversal_of_fuck_action( ... fixtures ... ):
# ...

# async def test_automatic_reversal_on_fuck_action_failure( ... fixtures ... ):
# ... 