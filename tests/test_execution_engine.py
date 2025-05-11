import pytest
import time
import logging # For caplog
from src.core.execution_engine import ExecutionEngine
from src.core.component_registry import ComponentRegistry
from src.core.components import analyze_fast, analyze_accurate, analyze_balanced
from src.core.state import KFMAgentState # Import for typing and mocking state
from unittest.mock import MagicMock # Using MagicMock

# --- Fixtures ---

@pytest.fixture
def registry():
    """Provides a ComponentRegistry instance."""
    return ComponentRegistry()

@pytest.fixture
def populated_registry(registry):
    """Provides a registry with dummy components registered."""
    # Use real components for execute_task tests
    registry.register_component('fast', analyze_fast)
    registry.register_component('accurate', analyze_accurate)
    registry.register_component('balanced', analyze_balanced, is_default=True) # Set a default
    return registry

@pytest.fixture
def engine(populated_registry):
    """Provides an ExecutionEngine instance initialized with the populated registry."""
    # Engine will pick up the default 'balanced' from the populated_registry
    return ExecutionEngine(populated_registry)

# Remove populated_engine fixture as we use engine directly now
# @pytest.fixture
# def populated_engine(populated_registry):
#     """Provides an engine linked to the populated registry."""
#     return ExecutionEngine(populated_registry)

# --- Test apply_kfm_action (Refactored) ---

def test_apply_action_marry_success(engine, populated_registry, mocker, caplog):
    """Test successfully applying a MARRY action."""
    mock_set_default = mocker.patch.object(populated_registry, 'set_default_component')
    action = {'action': 'marry', 'component': 'accurate'}
    
    with caplog.at_level(logging.INFO):
        result = engine.apply_kfm_action(action)
        
    assert result is True
    mock_set_default.assert_called_once_with('accurate')
    assert engine.get_active_component_key() == 'accurate' # Engine updates its internal key
    assert "Successfully applied 'marry' action." in caplog.text
    assert "Set active component to 'accurate'" in caplog.text

def test_apply_action_fuck_success(engine, populated_registry, mocker, caplog):
    """Test successfully applying a FUCK action."""
    mock_set_default = mocker.patch.object(populated_registry, 'set_default_component')
    action = {'action': 'fuck', 'component': 'fast'}
    initial_active = engine.get_active_component_key()

    with caplog.at_level(logging.WARNING):
        result = engine.apply_kfm_action(action)
        
    assert result is True
    mock_set_default.assert_called_once_with('fast')
    assert engine.get_active_component_key() == 'fast'
    assert "KFM Action FUCK: Temporarily set active component to 'fast'" in caplog.text
    assert f"Previous: '{initial_active}'" in caplog.text

def test_apply_action_kill_recognized(engine, populated_registry, mocker, caplog):
    """Test that KILL action is recognized but doesn't change active component by default."""
    mock_set_default = mocker.patch.object(populated_registry, 'set_default_component')
    initial_active = engine.get_active_component_key()
    action_named = {'action': 'kill', 'component': 'fast'}
    action_generic = {'action': 'kill', 'component': None}

    with caplog.at_level(logging.INFO):
        result_named = engine.apply_kfm_action(action_named)
        result_generic = engine.apply_kfm_action(action_generic)
        
    assert result_named is True
    assert result_generic is True
    mock_set_default.assert_not_called() # Kill doesn't change default/active component
    assert engine.get_active_component_key() == initial_active # Active key remains unchanged
    assert "'kill' action received for component 'fast'" in caplog.text
    assert "Generic 'kill' action received" in caplog.text

def test_apply_action_fail_missing_component_name(engine, mocker, caplog):
    """Test apply action fails if component name is missing for marry/fuck."""
    mock_set_default = mocker.patch.object(engine._registry, 'set_default_component')
    initial_active = engine.get_active_component_key()

    for action_type in ['marry', 'fuck']:
        caplog.clear()
        action = {'action': action_type, 'component': None}
        with caplog.at_level(logging.ERROR):
            result = engine.apply_kfm_action(action)
        assert result is False
        mock_set_default.assert_not_called()
        assert engine.get_active_component_key() == initial_active # Unchanged
        assert f"Cannot apply '{action_type}' action: Component name is missing" in caplog.text

def test_apply_action_fail_component_not_found(engine, mocker, caplog):
    """Test apply action fails if component is not in the registry."""
    mock_set_default = mocker.patch.object(engine._registry, 'set_default_component')
    initial_active = engine.get_active_component_key()
    
    for action_type in ['marry', 'fuck']:
        caplog.clear()
        action = {'action': action_type, 'component': 'nonexistent'}
        with caplog.at_level(logging.ERROR):
            result = engine.apply_kfm_action(action)
        assert result is False
        mock_set_default.assert_not_called()
        assert engine.get_active_component_key() == initial_active # Unchanged
        assert f"Cannot apply '{action_type}' action: Component 'nonexistent' not found" in caplog.text

def test_apply_action_fail_invalid_format(engine, mocker, caplog):
    """Test apply action fails with invalid action format."""
    mock_set_default = mocker.patch.object(engine._registry, 'set_default_component')
    initial_active = engine.get_active_component_key()
    invalid_actions = [
        {'component': 'fast'}, # Missing action key
        'string', 
        None, 
        {}
    ]
    for action in invalid_actions:
        caplog.clear()
        with caplog.at_level(logging.ERROR):
            result = engine.apply_kfm_action(action)
        assert result is False
        mock_set_default.assert_not_called()
        assert engine.get_active_component_key() == initial_active # Unchanged
        assert "Invalid action format received" in caplog.text

# --- Test execute_task (Refactored & Added) ---

@pytest.fixture
def sample_input():
    return {'text': 'test execution'}

def test_execute_task_success(engine, sample_input):
    """Test successful task execution with default component."""
    # Engine initialized with 'balanced' as active (set as default in fixture)
    result, performance = engine.execute_task(sample_input)
    
    assert isinstance(result, dict)
    assert 'result' in result
    assert 'confidence' in result
    assert result['result'] == "Balanced analysis of test execution"
    assert result['confidence'] == 0.85
    
    assert isinstance(performance, dict)
    assert 'latency' in performance
    assert 'accuracy' in performance
    assert 0.9 < performance['latency'] < 1.1 # analyze_balanced sleeps for 1s
    assert performance['accuracy'] == 0.85

def test_execute_task_logs_activation_type(engine, sample_input, caplog):
    """Test that execute_task logs the activation type from agent_state."""
    # Mock the component function to avoid actual execution time/output variation
    mock_component_func = MagicMock(return_value=({}, 0.9))
    engine._registry.register_component('mock_comp', mock_component_func)
    engine.apply_kfm_action({'action': 'marry', 'component': 'mock_comp'}) # Set active

    # Test case 1: Fuck activation
    state_fuck = MagicMock(spec=KFMAgentState)
    state_fuck.current_activation_type = 'fuck'
    caplog.clear()
    with caplog.at_level(logging.INFO):
        engine.execute_task(sample_input, agent_state=state_fuck)
    assert "Using active component: mock_comp (activated via: fuck)" in caplog.text

    # Test case 2: Marry activation
    state_marry = MagicMock(spec=KFMAgentState)
    state_marry.current_activation_type = 'marry'
    caplog.clear()
    with caplog.at_level(logging.INFO):
        engine.execute_task(sample_input, agent_state=state_marry)
    assert "Using active component: mock_comp (activated via: marry)" in caplog.text

    # Test case 3: No activation type in state
    state_none = MagicMock(spec=KFMAgentState)
    state_none.current_activation_type = None
    caplog.clear()
    with caplog.at_level(logging.INFO):
        engine.execute_task(sample_input, agent_state=state_none)
    # Should default to unknown or just not include the activation part
    assert "(activated via: " not in caplog.text 
    assert "(activation type: unknown)" in caplog.text

    # Test case 4: No state passed
    caplog.clear()
    with caplog.at_level(logging.INFO):
        engine.execute_task(sample_input, agent_state=None)
    assert "(activated via: " not in caplog.text
    assert "(activation type: unknown)" in caplog.text

def test_execute_task_fail_no_active_component(registry, sample_input, caplog):
    """Test execute_task failure when no component is active."""
    # Create engine with empty registry initially
    empty_registry = ComponentRegistry()
    engine_no_comp = ExecutionEngine(empty_registry)
    with caplog.at_level(logging.ERROR):
        result, performance = engine_no_comp.execute_task(sample_input)
    
    assert 'error' in result
    assert result['error'] == "No active component"
    assert performance == {'latency': 0, 'accuracy': 0.0}
    assert "Cannot execute task: No active component set." in caplog.text

def test_execute_task_fail_component_not_found(engine, sample_input, caplog):
    """Test execute_task failure when active component key doesn't exist (e.g., removed)."""
    engine._active_component_key = "deleted_component" # Force invalid active key
    with caplog.at_level(logging.ERROR):
        result, performance = engine.execute_task(sample_input)

    assert 'error' in result
    assert result['error'] == "Component 'deleted_component' not found"
    assert performance == {'latency': 0, 'accuracy': 0.0}
    assert "Active component 'deleted_component' not found" in caplog.text

def test_execute_task_fail_component_raises_error(engine, populated_registry, sample_input, caplog):
    """Test execute_task when the component function itself raises an exception."""
    def error_component(data):
        raise ValueError("Component calculation failed!")
        
    populated_registry.register_component('error_comp', error_component)
    engine.apply_kfm_action({'action': 'marry', 'component': 'error_comp'}) # Activate error comp
    
    with caplog.at_level(logging.ERROR):
        result, performance = engine.execute_task(sample_input)
    
    assert 'error' in result
    assert result['error'] == "Component calculation failed!"
    assert 'latency' in performance 
    assert performance['accuracy'] == 0.0
    assert "Error during task execution with component 'error_comp'" in caplog.text

# Remove old/invalid tests if they conflict or are redundant
# def test_execute_task_component_invalid_output(...)
# def test_execute_task_missing_confidence(...)

# def test_execute_task_no_active_component(populated_engine, sample_input):
#     # Ensure no active component is set (default state)
#     result, performance = populated_engine.execute_task(sample_input)
#     
#     assert result is None
#     assert 'error' in performance
#     assert performance['error'] == 'no_active_component'
#     assert performance['latency'] == 0
#     assert performance['accuracy'] == 0

# def test_execute_task_component_error(populated_engine, populated_registry, sample_input):
#     # Define a component that raises an error
#     def error_component(data):
#         raise ValueError("Component failed!")
#         
#     populated_registry.register_component('error', error_component)
#     populated_registry.set_active('error')
#     
#     result, performance = populated_engine.execute_task(sample_input)
#     
#     assert result is None
#     assert 'error' in performance
#     assert performance['error'] == "Component failed!"
#     assert 'latency' in performance # Should still measure time until failure
#     assert performance['accuracy'] == 0

# def test_execute_task_component_invalid_output(populated_engine, populated_registry, sample_input):
#     # Define a component that returns wrong type
#     def non_dict_component(data):
#         return "just a string"
#         
#     populated_registry.register_component('non_dict', non_dict_component)
#     populated_registry.set_active('non_dict')
#     
#     result, performance = populated_engine.execute_task(sample_input)
#     
#     assert result is None
#     assert 'error' in performance
#     assert performance['error'] == 'invalid_component_output'
#     assert 'latency' in performance
#     assert performance['accuracy'] == 0

# def test_execute_task_missing_confidence(populated_engine, populated_registry, sample_input):
#     # Define a component that returns dict without confidence
#     def no_confidence_component(data):
#         return {'result': 'some result'}
#         
#     populated_registry.register_component('no_conf', no_confidence_component)
#     populated_registry.set_active('no_conf')
#     
#     result, performance = populated_engine.execute_task(sample_input)
#     
#     assert result == {'result': 'some result'} # Result should still be returned
#     assert 'latency' in performance
#     assert performance['accuracy'] == 0.0 # Accuracy defaults to 0.0 