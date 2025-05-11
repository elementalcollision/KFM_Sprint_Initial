import pytest
from src.core.state_monitor import StateMonitor

def test_get_performance_data():
    monitor = StateMonitor()
    # Test getting all performance data
    all_data = monitor.get_performance_data()
    assert 'analyze_fast' in all_data
    assert 'analyze_accurate' in all_data
    assert len(all_data) == 2
    
    # Test getting specific component data
    fast_data = monitor.get_performance_data('analyze_fast')
    assert fast_data['latency'] == 0.5
    assert fast_data['accuracy'] == 0.7
    
    accurate_data = monitor.get_performance_data('analyze_accurate')
    assert accurate_data['latency'] == 2.0
    assert accurate_data['accuracy'] == 0.95

def test_get_performance_data_unknown():
    monitor = StateMonitor()
    unknown_data = monitor.get_performance_data('unknown_component')
    assert unknown_data == {}

def test_get_task_requirements():
    monitor = StateMonitor()
    # Test getting default requirements
    default_req = monitor.get_task_requirements()
    assert default_req['max_latency'] == 1.0
    assert default_req['min_accuracy'] == 0.8
    
    # Test getting requirements for default task explicitly
    default_explicit_req = monitor.get_task_requirements('default')
    assert default_explicit_req == default_req

def test_get_task_requirements_unknown():
    monitor = StateMonitor()
    # Test getting requirements for unknown task (should return default)
    unknown_req = monitor.get_task_requirements('unknown_task')
    default_req = monitor.get_task_requirements('default')
    assert unknown_req == default_req 