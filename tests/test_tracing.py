import pytest
import logging
from src.tracing import (
    trace_node, 
    configure_tracing, 
    reset_trace_history, 
    get_trace_history,
    visualize_trace_path
)
from src.core.state import KFMAgentState

# Mock node functions for testing
@trace_node
def mock_node1(state: KFMAgentState):
    """Mock node that adds a field to the state"""
    if isinstance(state, dict):
        # For TypedDict
        new_state = state.copy()
        new_state["mock_field"] = "added by mock_node1"
        return new_state
    else:
        # For KFMAgentState class
        state.results = {"mock_field": "added by mock_node1"}
        return state

@trace_node
def mock_node2(state: KFMAgentState):
    """Mock node that modifies an existing field"""
    if isinstance(state, dict):
        # For TypedDict
        new_state = state.copy()
        if "mock_field" in new_state:
            new_state["mock_field"] = "modified by mock_node2"
        return new_state
    else:
        # For KFMAgentState class
        if state.results:
            state.results = {"mock_field": "modified by mock_node2"}
        return state

@trace_node
def mock_error_node(state: KFMAgentState):
    """Mock node that raises an exception"""
    raise ValueError("Test error")

# Setup and teardown
@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset trace history before and after each test"""
    configure_tracing(log_level=logging.INFO)
    reset_trace_history()
    yield
    reset_trace_history()

# Tests
def test_trace_node_with_typeddict():
    """Test tracing with TypedDict state"""
    # Initial state as dictionary (TypedDict style)
    initial_state = {
        "task_name": "test_task",
        "input": {"text": "test input"}
    }
    
    # Run the nodes
    state1 = mock_node1(initial_state)
    state2 = mock_node2(state1)
    
    # Check trace history
    history = get_trace_history()
    assert len(history) == 2
    
    # Check first node trace
    assert history[0]["node"] == "mock_node1"
    assert history[0]["success"] is True
    assert "mock_field" in history[0]["changes"]
    assert history[0]["changes"]["mock_field"]["before"] is None
    assert history[0]["changes"]["mock_field"]["after"] == "added by mock_node1"
    
    # Check second node trace
    assert history[1]["node"] == "mock_node2"
    assert history[1]["success"] is True
    assert "mock_field" in history[1]["changes"]
    assert history[1]["changes"]["mock_field"]["before"] == "added by mock_node1"
    assert history[1]["changes"]["mock_field"]["after"] == "modified by mock_node2"

def test_trace_node_with_kfmagentstate_class():
    """Test tracing with KFMAgentState class"""
    # Initial state as KFMAgentState class
    initial_state = KFMAgentState({
        "task_name": "test_task",
        "input": {"text": "test input"}
    })
    
    # Run the nodes
    state1 = mock_node1(initial_state)
    state2 = mock_node2(state1)
    
    # Check trace history
    history = get_trace_history()
    assert len(history) == 2
    
    # Check that the results were properly traced
    # First node adds the results field
    assert "result" in history[0]["changes"]
    
    # Second node modifies the results field
    assert "result" in history[1]["changes"]
    assert history[1]["changes"]["result"]["after"]["mock_field"] == "modified by mock_node2"

def test_trace_error_handling():
    """Test tracing when a node raises an exception"""
    # Initial state
    initial_state = KFMAgentState({"task_name": "test_task"})
    
    # Run node that will raise an error
    with pytest.raises(ValueError):
        mock_error_node(initial_state)
    
    # Check trace history
    history = get_trace_history()
    assert len(history) == 1
    assert history[0]["node"] == "mock_error_node"
    assert history[0]["success"] is False
    assert "Test error" in history[0]["error"]
    assert "output_state" not in history[0]

def test_visualization():
    """Test the trace path visualization"""
    # Run a sequence of nodes
    initial_state = KFMAgentState({"task_name": "test_task"})
    try:
        state1 = mock_node1(initial_state)
        mock_error_node(state1)  # This will raise an error
    except ValueError:
        pass  # Expected error
    
    # Get the visualization
    viz = visualize_trace_path()
    
    # Check that visualization contains expected elements
    assert "Execution Path:" in viz
    assert "mock_node1" in viz
    assert "mock_error_node" in viz
    assert "Test error" in viz
    assert "✅" in viz  # Success indicator
    assert "❌" in viz  # Error indicator
    
    # Test with full state details
    full_viz = visualize_trace_path(show_all_states=True)
    assert "Input state:" in full_viz
    assert "Output state:" in full_viz 