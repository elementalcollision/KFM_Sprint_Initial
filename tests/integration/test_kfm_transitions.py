import pytest
from unittest.mock import MagicMock, patch
import copy

from src.core.state import KFMAgentState
from src.graph import create_kfm_agent_graph
from src.core.component_registry import ComponentRegistry
from src.core.state_monitor import StateMonitor
from src.core.execution_engine import ExecutionEngine
from src.core.kfm_planner import KFMPlanner
# Assuming langgraph_nodes might be needed for patching if LLM call wasn't fully mocked in create_graph
# from src import langgraph_nodes 

# Mock component function (can be shared)
def mock_component_func(input_data):
    # Returns result, accuracy
    # Accuracy might be read from metadata in a real scenario, here we hardcode for simplicity
    # based on component name conventions in the test
    if 'marry' in input_data.get('component_id', ''):
        return {"output": f"processed by {input_data.get('component_id')}"}, 0.95
    elif 'fuck_acc' in input_data.get('component_id', ''):
         return {"output": f"processed by {input_data.get('component_id')}"}, 0.85 # Meets accuracy, not latency
    elif 'fuck_lat' in input_data.get('component_id', ''):
         return {"output": f"processed by {input_data.get('component_id')}"}, 0.75 # Meets latency, not accuracy
    elif 'kill' in input_data.get('component_id', ''):
         return {"output": f"processed by {input_data.get('component_id')}"}, 0.5 # Meets neither
    else:
        return {"output": f"processed by {input_data.get('component_id')}"}, 0.7 # Default

@pytest.fixture
def kfm_graph_components_mutable(request):
    """Fixture providing KFM components with a mutable mock StateMonitor."""
    registry = ComponentRegistry()
    # Register components with representative names for test cases
    registry.register("comp_marry", lambda data: mock_component_func({'component_id': 'comp_marry', **data}))
    registry.register("comp_fuck_acc", lambda data: mock_component_func({'component_id': 'comp_fuck_acc', **data})) # High Accuracy, Slow
    registry.register("comp_fuck_lat", lambda data: mock_component_func({'component_id': 'comp_fuck_lat', **data})) # Low Accuracy, Fast
    registry.register("comp_kill", lambda data: mock_component_func({'component_id': 'comp_kill', **data})) # Low Accuracy, Slow

    # Create a mock StateMonitor that can be modified by tests
    mock_monitor = MagicMock(spec=StateMonitor)
    
    # Default initial performance data - can be overridden in tests
    mock_monitor.performance_data = {
        "comp_marry": {"accuracy": 0.95, "latency": 0.5}, # Good on both
        "comp_fuck_acc": {"accuracy": 0.85, "latency": 1.5}, # Good accuracy, bad latency
        "comp_fuck_lat": {"accuracy": 0.75, "latency": 0.4}, # Bad accuracy, good latency
        "comp_kill": {"accuracy": 0.60, "latency": 2.0}, # Bad on both
    }
    # Default initial task requirements - can be overridden
    mock_monitor.task_requirements = {
         'min_accuracy': 0.80, 
         'max_latency': 1.0
    }
    
    # Set up the mock methods
    mock_monitor.get_performance_data.side_effect = lambda: copy.deepcopy(mock_monitor.performance_data)
    mock_monitor.get_task_requirements.side_effect = lambda task_name: copy.deepcopy(mock_monitor.task_requirements)
    mock_monitor.validate_state.return_value = {'valid': True} # Assume state is valid

    # Create real Planner and Engine instances with the registry and mock monitor
    planner = KFMPlanner(mock_monitor, MagicMock()) # Mock engine for planner init, not used in decision
    engine = ExecutionEngine(registry)
    
    # --- Mocking LLM Call --- 
    # Patch the LLM call within the graph nodes to return a simple mock reflection
    # This prevents actual API calls during testing.
    def simple_mock_reflection(state, **kwargs): 
        act_type = state.current_activation_type
        comp = state.active_component
        return f"Mock reflection: Action='{act_type}', Component='{comp}'"

    # Patch the specific function used for LLM calls in langgraph_nodes
    # Adjust the path if your LLM call function is different
    llm_patcher = patch('src.langgraph_nodes.call_llm_for_reflection_v3', side_effect=simple_mock_reflection)
    mock_llm_call = llm_patcher.start()
    # --- End Mocking LLM Call ---
    
    # Create the graph using the real components and the mock monitor/LLM
    app = create_kfm_agent_graph(registry=registry, monitor=mock_monitor, planner=planner, engine=engine)

    yield {
        "app": app,
        "registry": registry,
        "mock_monitor": mock_monitor,
        "planner": planner,
        "engine": engine
    }

    # Cleanup patcher
    llm_patcher.stop()

def test_fuck_to_marry_transition(kfm_graph_components_mutable, caplog):
    """Test transition: Fuck action in cycle 1, Marry action in cycle 2."""
    app = kfm_graph_components_mutable["app"]
    mock_monitor = kfm_graph_components_mutable["mock_monitor"]

    # Cycle 1: Requirements trigger 'Fuck' for comp_fuck_acc (Acc=0.85 >= 0.80, Lat=1.5 > 1.0)
    mock_monitor.task_requirements = {'min_accuracy': 0.80, 'max_latency': 1.0}
    initial_state_cycle1 = KFMAgentState({
        'task_name': 'task_cycle_1',
        'task_requirements': mock_monitor.task_requirements,
        'performance_data': mock_monitor.get_performance_data(),
        'input': {"data": "cycle1"}
    })
    state_after_cycle1 = app.invoke(initial_state_cycle1.to_dict()) # Use dict for invoke
    state_after_cycle1_obj = KFMAgentState(state_after_cycle1) # Convert back for easier assertion
    
    assert state_after_cycle1_obj.current_activation_type == 'fuck'
    assert state_after_cycle1_obj.active_component == 'comp_fuck_acc'
    assert "KFM Decision: FUCK component 'comp_fuck_acc'" in caplog.text
    caplog.clear() # Clear logs for next cycle check

    # Cycle 2: Simulate performance improvement for comp_fuck_acc or new requirements
    # Option A: comp_fuck_acc improves latency
    mock_monitor.performance_data['comp_fuck_acc']['latency'] = 0.9 
    # Requirements remain the same
    input_state_cycle2 = state_after_cycle1 # Pass the state dict from previous cycle
    input_state_cycle2['input'] = {"data": "cycle2"} # Update input if needed
    input_state_cycle2['kfm_action'] = None # Clear previous decision
    input_state_cycle2['result'] = None # Clear previous result
    input_state_cycle2['execution_performance'] = None
    
    state_after_cycle2 = app.invoke(input_state_cycle2)
    state_after_cycle2_obj = KFMAgentState(state_after_cycle2)

    assert state_after_cycle2_obj.current_activation_type == 'marry'
    assert state_after_cycle2_obj.active_component == 'comp_fuck_acc' # Now married
    assert "Selected MARRY action with component 'comp_fuck_acc'" in caplog.text

def test_fuck_to_different_fuck_transition(kfm_graph_components_mutable, caplog):
    """Test transition: Fuck CompA in cycle 1, Fuck CompB (better Fuck) in cycle 2."""
    app = kfm_graph_components_mutable["app"]
    mock_monitor = kfm_graph_components_mutable["mock_monitor"]

    # Cycle 1: Requirements trigger 'Fuck' for comp_fuck_lat (Acc=0.75 < 0.80, Lat=0.4 <= 0.5)
    mock_monitor.task_requirements = {'min_accuracy': 0.80, 'max_latency': 0.5}
    # Ensure comp_fuck_acc is worse latency-wise if it meets accuracy
    mock_monitor.performance_data['comp_fuck_acc'] = {'accuracy': 0.85, 'latency': 0.6}
    initial_state_cycle1 = KFMAgentState({
        'task_name': 'task_cycle_1_f2f',
        'task_requirements': mock_monitor.task_requirements,
        'performance_data': mock_monitor.get_performance_data(),
        'input': {"data": "cycle1"}
    })
    state_after_cycle1 = app.invoke(initial_state_cycle1.to_dict())
    state_after_cycle1_obj = KFMAgentState(state_after_cycle1)
    
    assert state_after_cycle1_obj.current_activation_type == 'fuck'
    assert state_after_cycle1_obj.active_component == 'comp_fuck_lat' # Chosen based on latency
    assert "KFM Decision: FUCK component 'comp_fuck_lat'" in caplog.text 
    caplog.clear()

    # Cycle 2: comp_fuck_acc improves latency slightly, becoming the better Fuck candidate
    # (comp_fuck_acc: Acc=0.85 -> Score(0.85, -0.55) vs comp_fuck_lat: Acc=0.75 -> Score(0.75, -0.4))
    mock_monitor.performance_data['comp_fuck_acc']['latency'] = 0.55 
    input_state_cycle2 = state_after_cycle1
    input_state_cycle2['input'] = {"data": "cycle2"} 
    input_state_cycle2['kfm_action'] = None 
    input_state_cycle2['result'] = None
    input_state_cycle2['execution_performance'] = None
    
    state_after_cycle2 = app.invoke(input_state_cycle2)
    state_after_cycle2_obj = KFMAgentState(state_after_cycle2)

    assert state_after_cycle2_obj.current_activation_type == 'fuck'
    assert state_after_cycle2_obj.active_component == 'comp_fuck_acc' # Now the better Fuck choice
    assert "KFM Decision: FUCK component 'comp_fuck_acc'" in caplog.text

def test_fuck_to_kill_transition(kfm_graph_components_mutable, caplog):
    """Test transition: Fuck action in cycle 1, Kill action in cycle 2 due to degradation."""
    app = kfm_graph_components_mutable["app"]
    mock_monitor = kfm_graph_components_mutable["mock_monitor"]

    # Cycle 1: Trigger 'Fuck' for comp_fuck_lat
    mock_monitor.task_requirements = {'min_accuracy': 0.80, 'max_latency': 0.5}
    mock_monitor.performance_data = {
        "comp_fuck_lat": {"accuracy": 0.75, "latency": 0.4}, # Only meets latency
        "comp_kill": {"accuracy": 0.60, "latency": 2.0}, # Meets neither
    }
    initial_state_cycle1 = KFMAgentState({
        'task_name': 'task_cycle_1_f2k',
        'task_requirements': mock_monitor.task_requirements,
        'performance_data': mock_monitor.get_performance_data(),
        'input': {"data": "cycle1"}
    })
    state_after_cycle1 = app.invoke(initial_state_cycle1.to_dict())
    state_after_cycle1_obj = KFMAgentState(state_after_cycle1)
    
    assert state_after_cycle1_obj.current_activation_type == 'fuck'
    assert state_after_cycle1_obj.active_component == 'comp_fuck_lat'
    assert "KFM Decision: FUCK component 'comp_fuck_lat'" in caplog.text
    caplog.clear()

    # Cycle 2: comp_fuck_lat degrades, no other suitable components exist
    mock_monitor.performance_data['comp_fuck_lat']['latency'] = 2.0 # Now meets neither requirement
    input_state_cycle2 = state_after_cycle1
    input_state_cycle2['input'] = {"data": "cycle2"} 
    input_state_cycle2['kfm_action'] = None 
    input_state_cycle2['result'] = None
    input_state_cycle2['execution_performance'] = None

    state_after_cycle2 = app.invoke(input_state_cycle2)
    state_after_cycle2_obj = KFMAgentState(state_after_cycle2)

    assert state_after_cycle2_obj.kfm_decision['action'] == 'kill' # Planner proposes kill
    assert state_after_cycle2_obj.current_activation_type == 'kill' # Action applied
    # Active component might become None or stay as the last one depending on Engine's kill logic
    # For now, we primarily check the decision and activation type
    assert "KFM Decision: KILL proposed." in caplog.text 