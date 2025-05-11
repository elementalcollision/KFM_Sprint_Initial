import pytest
from unittest.mock import patch, MagicMock
import logging

# Assume these imports are correct based on project structure
# Adjust if necessary after checking file locations
from src.core.state import KFMAgentState 
from src.kfm_agent import create_kfm_agent_graph # Assuming graph creation function is here
from src.core.component_registry import ComponentRegistry
from src.core.state_monitor import StateMonitor
from src.core.kfm_planner import KFMPlanner
from src.core.execution_engine import ExecutionEngine
# Assuming mock reflection function can be imported or defined here if simple
# from src.langgraph_nodes import generate_mock_reflection 

# Mock function for reflection (can be imported if complex)
def generate_mock_reflection(state, **kwargs):
    action_type = state.current_activation_type
    component = state.active_component if state.active_component else 'unknown'
    kfm_comp = state.kfm_decision.get('component', 'unknown') if state.kfm_decision else 'unknown'
    return f"Mock reflection for {action_type} activation. KFM Action on: '{kfm_comp}'. Active: '{component}'."

@pytest.fixture(scope="module") # Scope to module might be more efficient
def kfm_graph_components():
    """Sets up the KFM agent graph with mockable components for integration testing."""
    # 1. Create Component Registry with test components
    registry = ComponentRegistry()
    
    # Mock component functions - return tuple (result_dict, accuracy)
    registry.register_component(
        key='comp_marry', 
        component_func=MagicMock(return_value=({'result': 'marry_result'}, 0.9)),
        is_default=True # Let's set a default
    )
    registry.register_component(
        key='comp_fuck_acc', 
        component_func=MagicMock(return_value=({'result': 'fuck_acc_result'}, 0.95))
    )
    registry.register_component(
        key='comp_fuck_lat', 
        component_func=MagicMock(return_value=({'result': 'fuck_lat_result'}, 0.7))
    )
    registry.register_component(
        key='comp_kill', 
        component_func=MagicMock(return_value=({'result': 'kill_result'}, 0.5))
    )

    # 2. Create State Monitor with mocked performance data
    monitor = MagicMock(spec=StateMonitor)
    
    mock_performance_data = {
        'comp_marry': {'accuracy': 0.9, 'latency': 0.8},
        'comp_fuck_acc': {'accuracy': 0.95, 'latency': 1.5},
        'comp_fuck_lat': {'accuracy': 0.7, 'latency': 0.5},
        'comp_kill': {'accuracy': 0.5, 'latency': 2.0}
    }
    monitor.get_performance_data.return_value = mock_performance_data

    # Mock task requirements - return specific reqs or default
    default_task_requirements = {
        'default': {'min_accuracy': 0.8, 'max_latency': 1.0},
        'strict': {'min_accuracy': 0.99, 'max_latency': 0.1}
    }
    monitor.get_task_requirements.side_effect = lambda task_name='default': default_task_requirements.get(task_name, default_task_requirements['default'])

    # 3. Create Planner and Engine
    # Note: ExecutionEngine uses the *real* registry here
    engine = ExecutionEngine(registry)
    # Note: KFMPlanner uses the *mocked* monitor
    planner = KFMPlanner(monitor, engine) 

    # 4. Create the LangGraph app using the *real* components
    # We pass the instantiated components to the graph creation function
    # Assuming create_kfm_agent_graph uses these instances
    app, core_components = create_kfm_agent_graph(
        registry=registry, 
        monitor=monitor, 
        planner=planner, 
        engine=engine
    )

    # 5. Mock LLM Reflection Call within the graph's execution context
    # Patch the function *where it's looked up* (i.e., in langgraph_nodes module)
    patcher = patch('src.langgraph_nodes.call_llm_for_reflection_v3', side_effect=generate_mock_reflection)
    
    # Start patching before yielding, stop after tests are done
    mock_llm_call = patcher.start()
    
    yield {
        "app": app,
        "registry": registry,
        "monitor": monitor,
        "planner": planner,
        "engine": engine,
        "mock_llm_call": mock_llm_call # Yield the mock object if needed
    }
    
    # Stop patching after the tests in the module have run
    patcher.stop()

# --- Test Cases Implementation --- 

def test_successful_fuck_action_workflow(kfm_graph_components, caplog):
    """Test the full graph flow when a 'Fuck' action is expected."""
    app = kfm_graph_components["app"]
    # registry = kfm_graph_components["registry"]
    # monitor = kfm_graph_components["monitor"]
    # engine = kfm_graph_components["engine"]
    
    # Initial state: Use 'default' requirements (acc>=0.8, lat<=1.0)
    # This should make comp_fuck_acc (0.95, 1.5) the best FUCK candidate
    # because comp_marry (0.9, 0.8) meets both (MARRY preferred).
    # Let's adjust requirements slightly to force FUCK:
    # Use requirements where only comp_fuck_acc meets accuracy, 
    # and comp_fuck_lat meets latency, and comp_marry fails latency.
    # Example: min_accuracy=0.9, max_latency=0.6
    # comp_marry (0.9, 0.8) -> FUCK (latency fail)
    # comp_fuck_acc (0.95, 1.5) -> FUCK (latency fail) - HIGHEST ACCURACY
    # comp_fuck_lat (0.7, 0.5) -> FUCK (accuracy fail)
    # comp_kill (0.5, 2.0) -> KILL
    
    initial_state_dict = {
        'task_name': "custom_req_for_fuck", # We'll mock the requirement lookup for this task name
        'input': {'query': 'test query for fuck action'},
        # Other state fields will be populated by the graph nodes
    }
    # Mock the requirements specifically for this task name within the test
    monitor = kfm_graph_components["monitor"]
    original_side_effect = monitor.get_task_requirements.side_effect
    def side_effect_func(task_name='default'):
        if task_name == "custom_req_for_fuck":
            return {'min_accuracy': 0.9, 'max_latency': 0.6}
        # Call original side effect for other task names if needed, 
        # though default is handled by lambda in fixture
        return original_side_effect(task_name)
    monitor.get_task_requirements.side_effect = side_effect_func
    
    initial_state = KFMAgentState(initial_state_dict)

    # Invoke the graph
    final_state = None
    with caplog.at_level(logging.INFO): # Capture INFO and higher
        # Assuming app.invoke returns the final state as a dictionary
        final_state_dict = app.invoke(initial_state.to_dict())
        # Convert back to KFMAgentState object if needed for easier attribute access
        final_state = KFMAgentState(final_state_dict) 

    # Reset side effect after test if necessary (though fixture scope might handle this)
    monitor.get_task_requirements.side_effect = original_side_effect

    assert final_state is not None
    
    # Assertions on Final State:
    # Decision node should have decided 'fuck' with 'comp_fuck_acc'
    assert final_state.kfm_decision is not None
    assert final_state.kfm_decision.get('action') == 'fuck'
    assert final_state.kfm_decision.get('component') == 'comp_fuck_acc'
    
    # Execute node should have set activation type and active component
    assert final_state.current_activation_type == 'fuck'
    assert final_state.active_component == 'comp_fuck_acc'
    
    # Results and performance should match the mock component
    assert final_state.results == {'result': 'fuck_acc_result'}
    # The mock component returns accuracy 0.95, latency is based on mock call time (negligible)
    # The performance dict in state reflects the mock *return value* accuracy, not monitor data
    assert final_state.execution_performance['accuracy'] == 0.95 
    assert 'latency' in final_state.execution_performance # Latency is measured

    # Assertions on Logs (`caplog`):
    # Decision Log (Planner - WARNING)
    assert "KFM Decision: FUCK component 'comp_fuck_acc'" in caplog.text
    assert "Reason: Compromise solution" in caplog.text
    assert "Score: (0.95, -1.5)" in caplog.text # Score based on monitor data
    
    # Activation Log (Engine - WARNING)
    assert "KFM Action FUCK: Temporarily set active component to 'comp_fuck_acc'" in caplog.text
    
    # Execution Log (Engine - INFO)
    assert "Using active component: comp_fuck_acc (activated via: fuck)" in caplog.text
    
    # Post-Execution Log (Node - INFO)
    assert "Task executed via FUCK: Component 'comp_fuck_acc'" in caplog.text
    assert '"accuracy": 0.95' in caplog.text # Performance from execution result
    
    # Reflection Log (Node - INFO)
    assert "Reflection context: Initiating reflection for KFM Action 'fuck' on component 'comp_fuck_acc'" in caplog.text
    assert "Activation method: 'fuck'" in caplog.text

def test_marry_preferred_over_fuck(kfm_graph_components, caplog):
    """Test the graph flow ensures Marry is chosen when both Marry and Fuck candidates exist."""
    app = kfm_graph_components["app"]
    monitor = kfm_graph_components["monitor"]

    # Initial state: Use 'default' requirements (acc>=0.8, lat<=1.0)
    # Based on fixture setup:
    # comp_marry (0.9, 0.8) -> Marry
    # comp_fuck_acc (0.95, 1.5) -> Fuck
    # comp_fuck_lat (0.7, 0.5) -> Fuck
    # Planner should choose comp_marry
    initial_state_dict = {
        'task_name': "default", 
        'input': {'query': 'test query for marry preference'},
    }
    initial_state = KFMAgentState(initial_state_dict)

    # Invoke the graph
    final_state = None
    with caplog.at_level(logging.INFO):
        final_state_dict = app.invoke(initial_state.to_dict())
        final_state = KFMAgentState(final_state_dict)

    assert final_state is not None
    
    # Assertions on Final State:
    # Decision should be 'marry' with 'comp_marry'
    assert final_state.kfm_decision is not None
    assert final_state.kfm_decision.get('action') == 'marry'
    assert final_state.kfm_decision.get('component') == 'comp_marry'
    
    # Activation type and active component should reflect Marry
    assert final_state.current_activation_type == 'marry'
    assert final_state.active_component == 'comp_marry'
    
    # Results and performance should match the mock marry component
    assert final_state.results == {'result': 'marry_result'}
    assert final_state.execution_performance['accuracy'] == 0.9
    assert 'latency' in final_state.execution_performance

    # Assertions on Logs (`caplog`):
    # Verify Marry-related logs are present
    assert "KFM Decision: MARRY component 'comp_marry'" in caplog.text # Assuming KFMPlanner logs MARRY at INFO
    assert "Successfully applied 'marry' action." in caplog.text # From ExecutionEngine
    assert "Using active component: comp_marry (activated via: marry)" in caplog.text
    
    # Verify FUCK-specific logs are NOT present
    assert "KFM Decision: FUCK component" not in caplog.text
    assert "KFM Action FUCK: Temporarily set active component" not in caplog.text
    assert "Task executed via FUCK:" not in caplog.text
    assert "Reflection context: Initiating reflection for KFM Action 'fuck'" not in caplog.text

def test_kill_when_no_suitable_candidate(kfm_graph_components, caplog):
    """Test the graph flow results in a Kill action when no component meets minimum criteria."""
    app = kfm_graph_components["app"]
    monitor = kfm_graph_components["monitor"]

    # Initial state: Use 'strict' requirements (acc>=0.99, lat<=0.1)
    # None of the components in the fixture meet these criteria.
    initial_state_dict = {
        'task_name': "strict", 
        'input': {'query': 'test query for kill action'},
    }
    initial_state = KFMAgentState(initial_state_dict)

    # Invoke the graph
    final_state = None
    with caplog.at_level(logging.INFO):
        final_state_dict = app.invoke(initial_state.to_dict())
        final_state = KFMAgentState(final_state_dict)

    assert final_state is not None
    
    # Assertions on Final State:
    # Decision should be 'kill'
    assert final_state.kfm_decision is not None
    assert final_state.kfm_decision.get('action') == 'kill'
    assert final_state.kfm_decision.get('component') is None # Generic kill
    
    # Activation type should be set to 'kill' by execute_action_node
    assert final_state.current_activation_type == 'kill'
    
    # Active component *might* remain what it was before the kill decision,
    # as the default kill action doesn't necessarily deactivate in the engine.
    # Let's check it's not None, assuming a default was set initially.
    assert final_state.active_component is not None 
    
    # Results should likely be empty or indicate no task was run, 
    # as the 'kill' action precedes execution attempt in the standard flow.
    # Check if the graph definition skips execution on 'kill'. 
    # For now, let's assume no execution result/performance is populated.
    assert not final_state.results 
    assert final_state.execution_performance is None

    # Assertions on Logs (`caplog`):
    # Verify Kill-related logs are present
    assert "KFM Decision: KILL proposed" in caplog.text # From Planner (WARNING)
    assert "Applying KFM action: Type='kill'" in caplog.text # From Execute Node (INFO)
    assert "Generic 'kill' action received" in caplog.text # From Engine (INFO)
    
    # Verify Marry/Fuck specific logs are NOT present
    assert "KFM Decision: FUCK" not in caplog.text
    assert "KFM Action FUCK:" not in caplog.text
    assert "KFM Decision: MARRY" not in caplog.text
    assert "Successfully applied 'marry' action" not in caplog.text
    assert "Task executed via FUCK" not in caplog.text
    # Verify reflection context reflects the kill action
    assert "Reflection context: Initiating reflection for KFM Action 'kill'" in caplog.text

def test_fuck_component_execution_failure(kfm_graph_components, caplog):
    """Test the graph flow handles errors when a component chosen via 'Fuck' fails."""
    app = kfm_graph_components["app"]
    monitor = kfm_graph_components["monitor"]
    registry = kfm_graph_components["registry"]
    
    # Modify the component that should be chosen via Fuck ('comp_fuck_acc')
    # to raise an exception during execution.
    mock_comp_fuck_acc = registry.get_component('comp_fuck_acc')
    error_message = "Component execution failed spectacularly!"
    mock_comp_fuck_acc.side_effect = ValueError(error_message)

    # Use the same requirements as test_successful_fuck_action_workflow to trigger Fuck
    initial_state_dict = {
        'task_name': "custom_req_for_fuck", 
        'input': {'query': 'test query for fuck failure'},
    }
    # Mock the requirements specifically for this task name within the test
    original_side_effect = monitor.get_task_requirements.side_effect
    def side_effect_func(task_name='default'):
        if task_name == "custom_req_for_fuck":
            return {'min_accuracy': 0.9, 'max_latency': 0.6}
        return original_side_effect(task_name)
    monitor.get_task_requirements.side_effect = side_effect_func
    
    initial_state = KFMAgentState(initial_state_dict)

    # Invoke the graph
    final_state = None
    with caplog.at_level(logging.INFO):
        final_state_dict = app.invoke(initial_state.to_dict())
        final_state = KFMAgentState(final_state_dict)

    # Reset side effect and mock behavior after test
    monitor.get_task_requirements.side_effect = original_side_effect
    mock_comp_fuck_acc.side_effect = None # Reset side effect

    assert final_state is not None
    
    # Assertions on Final State:
    # Decision and activation should still be 'fuck' for 'comp_fuck_acc'
    assert final_state.kfm_decision is not None
    assert final_state.kfm_decision.get('action') == 'fuck'
    assert final_state.kfm_decision.get('component') == 'comp_fuck_acc'
    assert final_state.current_activation_type == 'fuck'
    assert final_state.active_component == 'comp_fuck_acc'
    
    # State should contain an error from the execution phase
    assert final_state.error is not None
    # Error stored in state might be a formatted dict or just the string
    # Check if the original error message is present in the state error info
    assert error_message in str(final_state.error) 
    # Depending on graph structure, done might be True
    # assert final_state.done is True
    
    # Results should contain the error reported by ExecutionEngine
    assert final_state.results is not None
    assert final_state.results.get('error') == error_message
    
    # Performance might still have latency recorded until the error
    assert final_state.execution_performance is not None
    assert 'latency' in final_state.execution_performance
    assert final_state.execution_performance.get('accuracy') == 0.0 # Accuracy defaults to 0 on error

    # Assertions on Logs (`caplog`):
    # Verify initial Fuck decision/activation logs are present
    assert "KFM Decision: FUCK component 'comp_fuck_acc'" in caplog.text
    assert "KFM Action FUCK: Temporarily set active component to 'comp_fuck_acc'" in caplog.text
    assert "Using active component: comp_fuck_acc (activated via: fuck)" in caplog.text
    
    # Verify error log from ExecutionEngine during execute_task
    assert f"Error during task execution with component 'comp_fuck_acc': {error_message}" in caplog.text
    
    # Verify error log from execute_action_node (wrapping the engine error)
    assert "Task execution resulted in an error:" in caplog.text
    assert "ComponentExecutionError" in caplog.text
    
    # Reflection should still occur, potentially reflecting on the error
    assert "Reflection context: Initiating reflection for KFM Action 'fuck'" in caplog.text

# Remove placeholder test
# def test_placeholder():
#     """ Placeholder test to ensure file runs. """
#     assert True

# TODO: Implement Test Case 4: Edge Case - Component Failure During 'Fuck' Execution 