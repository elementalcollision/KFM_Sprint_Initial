import pytest
from src.core.state import KFMAgentState

def test_state_initialization_empty():
    """Test that state initializes correctly with default values when no initial data is provided."""
    state = KFMAgentState()
    
    # Check default values
    assert state.input == {}
    assert state.task_name == "default"
    assert state.performance == {}
    assert state.task_requirements == {}
    assert state.kfm_decision is None
    assert state.active_component is None
    assert state.results == {}
    assert state.execution_performance is None
    assert state.error is None
    assert state.done is False

def test_state_initialization_with_data():
    """Test that state initializes correctly with provided initial data."""
    initial_data = {
        'input': {'text': 'test input'},
        'task_name': 'test_task',
        'performance_data': {
            'component1': {'latency': 0.5, 'accuracy': 0.9}
        },
        'task_requirements': {'min_accuracy': 0.8},
        'kfm_action': {'action': 'kill', 'component': 'component2'},
        'active_component': 'component1',
        'result': {'output': 'test result'},
        'execution_performance': {'latency': 0.3},
        'error': None,
        'done': True
    }
    
    state = KFMAgentState(initial_data)
    
    # Check values were properly set
    assert state.input == {'text': 'test input'}
    assert state.task_name == 'test_task'
    assert state.performance == {'component1': {'latency': 0.5, 'accuracy': 0.9}}
    assert state.task_requirements == {'min_accuracy': 0.8}
    assert state.kfm_decision == {'action': 'kill', 'component': 'component2'}
    assert state.active_component == 'component1'
    assert state.results == {'output': 'test result'}
    assert state.execution_performance == {'latency': 0.3}
    assert state.error is None
    assert state.done is True

def test_update_method():
    """Test the update method for modifying state properties."""
    state = KFMAgentState()
    
    # Update with new data
    update_data = {
        'task_name': 'updated_task',
        'performance_data': {'component1': {'latency': 1.0}},
        'done': True
    }
    
    state.update(update_data)
    
    # Check that specified values were updated
    assert state.task_name == 'updated_task'
    assert state.performance == {'component1': {'latency': 1.0}}
    assert state.done is True
    
    # Check that other values remain default
    assert state.input == {}
    assert state.kfm_decision is None

def test_to_dict_method():
    """Test the to_dict method for converting state to TypedDict format."""
    state = KFMAgentState()
    
    # Set some values
    state.task_name = 'test_task'
    state.set_kfm_decision('marry', 'component1')
    state.set_result({'output': 'test output'})
    
    # Convert to dictionary
    state_dict = state.to_dict()
    
    # Check dictionary keys and values
    assert state_dict['task_name'] == 'test_task'
    assert state_dict['kfm_action'] == {'action': 'marry', 'component': 'component1'}
    assert state_dict['result'] == {'output': 'test output'}
    
    # Check key mapping
    assert 'kfm_decision' not in state_dict  # Our internal attribute name
    assert 'kfm_action' in state_dict       # TypedDict key name

def test_set_performance_and_get_performance():
    """Test setting and getting performance metrics."""
    state = KFMAgentState()
    
    # Set performance for a component
    metrics = {'latency': 0.5, 'accuracy': 0.95}
    state.set_performance('component1', metrics)
    
    # Get performance for specific component
    comp_metrics = state.get_performance('component1')
    assert comp_metrics == metrics
    
    # Get all performance data
    all_metrics = state.get_performance()
    assert 'component1' in all_metrics
    assert all_metrics['component1'] == metrics
    
    # Test getting metrics for unknown component
    unknown_metrics = state.get_performance('unknown')
    assert unknown_metrics == {}

def test_set_kfm_decision_and_clear():
    """Test setting and clearing KFM decision."""
    state = KFMAgentState()
    
    # Set decision
    state.set_kfm_decision('kill', 'component1')
    assert state.kfm_decision == {'action': 'kill', 'component': 'component1'}
    
    # Clear decision
    state.clear_kfm_decision()
    assert state.kfm_decision is None

def test_set_result():
    """Test setting result data."""
    state = KFMAgentState()
    
    # Set result
    result_data = {'output': 'test output', 'confidence': 0.8}
    state.set_result(result_data)
    assert state.results == result_data
    
    # Result object should be a copy, not a reference
    result_data['confidence'] = 0.9
    assert state.results['confidence'] == 0.8  # Should still be original value

def test_error_handling():
    """Test error setting, checking, and clearing."""
    state = KFMAgentState()
    
    # Initially no error
    assert state.has_error() is False
    assert state.error is None
    
    # Set error
    state.set_error("Test error message")
    assert state.has_error() is True
    assert state.error == "Test error message"
    
    # Clear error
    state.clear_error()
    assert state.has_error() is False
    assert state.error is None

def test_set_done():
    """Test setting the done flag."""
    state = KFMAgentState()
    
    # Initially not done
    assert state.done is False
    
    # Set done
    state.set_done()
    assert state.done is True
    
    # Set not done
    state.set_done(False)
    assert state.done is False

def test_update_with_unknown_keys():
    """Test that update method gracefully handles unknown keys."""
    state = KFMAgentState()
    
    # Update with unknown keys
    update_data = {
        'task_name': 'test_task',
        'unknown_key': 'some value'
    }
    
    state.update(update_data)
    
    # Known keys should be updated
    assert state.task_name == 'test_task'
    
    # Unknown keys should be ignored (no AttributeError)
    with pytest.raises(AttributeError):
        getattr(state, 'unknown_key')

def test_string_representation():
    """Test the string representation of the state."""
    state = KFMAgentState()
    state.task_name = 'test_task'
    state.set_kfm_decision('marry', 'component1')
    
    # Get string representation
    state_str = str(state)
    
    # Should contain key information
    assert 'KFMAgentState' in state_str
    assert 'task_name: test_task' in state_str
    assert "kfm_action: {'action': 'marry', 'component': 'component1'}" in state_str

def test_deep_copy_of_mutable_values():
    """Test that mutable values are deep copied during updates."""
    initial_data = {
        'performance_data': {
            'component1': {'latency': 0.5}
        }
    }
    
    state = KFMAgentState(initial_data)
    
    # Modify the original data
    initial_data['performance_data']['component1']['latency'] = 1.0
    
    # State should have the original value (deep copy)
    assert state.performance['component1']['latency'] == 0.5 