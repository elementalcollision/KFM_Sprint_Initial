import pytest
import logging # Needed for caplog checks
from src.core.kfm_planner import KFMPlanner
from src.core.state_monitor import StateMonitor
from unittest.mock import MagicMock # Using unittest.mock for simplicity here

@pytest.fixture
def state_monitor():
    # Using MagicMock for more flexible mocking of methods
    monitor = MagicMock(spec=StateMonitor)
    
    # Define default return values for mocked methods
    default_performance_data = {}
    default_task_requirements = {
        'default': {'min_accuracy': 0.8, 'max_latency': 1.0},
        'speed_critical': {'min_accuracy': 0.6, 'max_latency': 0.5},
        'accuracy_critical': {'min_accuracy': 0.95, 'max_latency': 2.0},
        'zero_acc': {'min_accuracy': 0.0, 'max_latency': 1.0}
    }
    
    # Configure the mock methods
    monitor.get_performance_data.return_value = default_performance_data
    # Use a side_effect to return specific reqs or default
    monitor.get_task_requirements.side_effect = lambda task_name='default': default_task_requirements.get(task_name, default_task_requirements['default'])

    # Store these on the mock object if needed for direct manipulation in tests
    monitor.mock_performance_data = default_performance_data
    monitor.mock_task_requirements = default_task_requirements 
    
    return monitor

@pytest.fixture
def planner(state_monitor):
    """Provides a KFMPlanner instance initialized with the mocked state_monitor."""
    # Mock ExecutionEngine as it's not needed for decide_kfm_action tests
    mock_execution_engine = MagicMock()
    # Pass the mocked monitor to the planner
    return KFMPlanner(state_monitor, mock_execution_engine)

# Helper function to set performance data in tests
def set_performance(monitor, data):
    monitor.get_performance_data.return_value = data
    monitor.mock_performance_data = data # Update mock attribute too if accessed directly

# --- Marry Tests --- 

def test_marry_single_candidate(planner, state_monitor):
    """Test MARRY action when one component meets both criteria."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 0.5} # Marry
    })
    action = planner.decide_kfm_action(task_name='default') # Pass task_name
    assert action == {'action': 'marry', 'component': 'comp_a'}

def test_marry_best_of_multiple(planner, state_monitor):
    """Test MARRY action selects the best candidate (highest accuracy, then lowest latency)."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.85, 'latency': 0.8}, # Marry
        'comp_b': {'accuracy': 0.95, 'latency': 0.7}, # Marry (Better Acc)
        'comp_c': {'accuracy': 0.95, 'latency': 0.6}, # Marry (Same Acc, Better Lat) -> Best
        'comp_d': {'accuracy': 0.7, 'latency': 0.6}  # Fuck (Low Accuracy)
    })
    action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'marry', 'component': 'comp_c'}

def test_marry_tie_breaker_latency(planner, state_monitor):
    """Test MARRY tie-breaker favors lower latency when accuracy is equal."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 0.8}, # Marry (Slower)
        'comp_b': {'accuracy': 0.9, 'latency': 0.6}  # Marry (Faster)
    })
    action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'marry', 'component': 'comp_b'}

# --- Fuck Tests --- 

def test_fuck_accuracy_only(planner, state_monitor, caplog):
    """Test FUCK action when only accuracy is met."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 1.5} # Fuck (Too slow)
    })
    with caplog.at_level(logging.WARNING):
        action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'fuck', 'component': 'comp_a'}
    assert "KFM Decision: FUCK component 'comp_a'" in caplog.text
    assert "Reason: Compromise solution" in caplog.text
    assert "Score: (0.9, -1.5)" in caplog.text # Check score format

def test_fuck_latency_only(planner, state_monitor, caplog):
    """Test FUCK action when only latency is met."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.7, 'latency': 0.5} # Fuck (Inaccurate)
    })
    with caplog.at_level(logging.WARNING):
        action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'fuck', 'component': 'comp_a'}
    assert "KFM Decision: FUCK component 'comp_a'" in caplog.text
    assert "Score: (0.7, -0.5)" in caplog.text

def test_fuck_best_of_multiple(planner, state_monitor, caplog):
    """Test FUCK action selects the best candidate (highest accuracy, then lowest latency)."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.6, 'latency': 1.5}, # Kill (Neither)
        'comp_b': {'accuracy': 0.7, 'latency': 0.5}, # Fuck (Latency only)
        'comp_c': {'accuracy': 0.9, 'latency': 1.2}, # Fuck (Accuracy only - Highest Acc) -> Wins
        'comp_d': {'accuracy': 0.85, 'latency': 1.1} # Fuck (Accuracy only)
    })
    with caplog.at_level(logging.WARNING):
        action = planner.decide_kfm_action(task_name='default')
    # Score is (acc, -lat), reverse=True
    # comp_c: (0.9, -1.2) -> Wins
    # comp_d: (0.85, -1.1)
    # comp_b: (0.7, -0.5)
    assert action == {'action': 'fuck', 'component': 'comp_c'}
    assert "KFM Decision: FUCK component 'comp_c'" in caplog.text
    assert "Score: (0.9, -1.2)" in caplog.text

def test_fuck_tie_breaker_latency(planner, state_monitor, caplog):
    """Test FUCK tie-breaker favors lower latency when accuracy is equal."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 1.8}, # Fuck (Acc OK, Slow)
        'comp_b': {'accuracy': 0.9, 'latency': 1.2}, # Fuck (Acc OK, Faster) -> Wins
        'comp_c': {'accuracy': 0.7, 'latency': 0.5}  # Fuck (Lat OK, Less Acc)
    })
    with caplog.at_level(logging.WARNING):
        action = planner.decide_kfm_action(task_name='default')
    # Comp B score: (0.9, -1.2)
    # Comp A score: (0.9, -1.8)
    assert action == {'action': 'fuck', 'component': 'comp_b'}
    assert "KFM Decision: FUCK component 'comp_b'" in caplog.text
    assert "Score: (0.9, -1.2)" in caplog.text

def test_marry_preferred_over_fuck(planner, state_monitor):
    """Test that MARRY is chosen even if FUCK candidates exist."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 1.5}, # Fuck (Too slow)
        'comp_b': {'accuracy': 0.85, 'latency': 0.8} # Marry
    })
    action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'marry', 'component': 'comp_b'}

# --- Kill (No Suitable Action) Tests --- 

def test_kill_no_components(planner, state_monitor):
    """Test KILL action when no components are available."""
    set_performance(state_monitor, {})
    action = planner.decide_kfm_action(task_name='default')
    # Implementation returns {'action': 'kill', 'component': None}
    assert action == {'action': 'kill', 'component': None}

def test_kill_all_fail(planner, state_monitor, caplog):
    """Test KILL action when all components fail both requirements."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.7, 'latency': 1.5}, # Kill
        'comp_b': {'accuracy': 0.6, 'latency': 2.0}  # Kill
    })
    with caplog.at_level(logging.WARNING):
        action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'kill', 'component': None}
    assert "KFM Decision: KILL proposed" in caplog.text

# --- Custom Requirements Tests ---

def test_custom_req_speed_critical(planner, state_monitor):
    """Test decisions with speed-critical requirements."""
    # Req: acc >= 0.6, lat <= 0.5
    set_performance(state_monitor, {
        'comp_fast': {'accuracy': 0.7, 'latency': 0.4}, # Marry
        'comp_slow': {'accuracy': 0.9, 'latency': 0.8}  # Fuck (Too slow)
    })
    action = planner.decide_kfm_action(task_name='speed_critical')
    assert action == {'action': 'marry', 'component': 'comp_fast'}

def test_custom_req_accuracy_critical(planner, state_monitor):
    """Test decisions with accuracy-critical requirements."""
    # Req: acc >= 0.95, lat <= 2.0
    set_performance(state_monitor, {
        'comp_accurate': {'accuracy': 0.96, 'latency': 1.8}, # Marry
        'comp_fast_inaccurate': {'accuracy': 0.8, 'latency': 0.5} # Fuck (Too inaccurate)
    })
    action = planner.decide_kfm_action(task_name='accuracy_critical')
    assert action == {'action': 'marry', 'component': 'comp_accurate'}

# --- Edge Cases ---

def test_missing_metrics(planner, state_monitor):
    """Test handling of components with missing performance metrics."""
    set_performance(state_monitor, {
        'comp_a': {'latency': 0.5}, # Missing accuracy (defaults to 0 -> Kill)
        'comp_b': {'accuracy': 0.9}, # Missing latency (defaults to inf -> Fuck)
        'comp_c': {'accuracy': 0.99, 'latency': 0.1} # Marry
    })
    action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'marry', 'component': 'comp_c'}

def test_zero_latency(planner, state_monitor):
    """Test handling of component with zero latency."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.9, 'latency': 0.0} # Marry
    })
    action = planner.decide_kfm_action(task_name='default')
    assert action == {'action': 'marry', 'component': 'comp_a'}

def test_zero_min_accuracy_req(planner, state_monitor):
    """Test behavior when min_accuracy requirement is zero."""
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.1, 'latency': 0.5} # Marry (accuracy >= 0.0 met)
    })
    action = planner.decide_kfm_action(task_name='zero_acc')
    assert action == {'action': 'marry', 'component': 'comp_a'}

# Test for incomplete requirements provided by state monitor
def test_incomplete_requirements(planner, state_monitor, caplog):
    """Test that planner handles missing requirements keys gracefully."""
    state_monitor.get_task_requirements.return_value = {'min_accuracy': 0.9} # Missing max_latency
    set_performance(state_monitor, {
        'comp_a': {'accuracy': 0.95, 'latency': 0.5}
    })
    with caplog.at_level(logging.ERROR):
        action = planner.decide_kfm_action(task_name='incomplete_req_task')
    assert action is None
    assert "requirements are incomplete" in caplog.text 