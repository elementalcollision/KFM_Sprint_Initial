import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from src.core.agent_lifecycle_controller import AgentLifecycleController
from src.state_types import KFMAgentState
# We'll need to mock the graph creation functions from kfm_agent
# If they are complex to mock, we might need to adjust the controller's __init__ for testing

@pytest.fixture
def mock_create_graph_fn():
    """Provides a mock for the create_graph_fn."""
    mock_fn = MagicMock()
    mock_app = MagicMock() # This is the LangGraph application mock
    # mock_app.invoke needs to be a simple MagicMock if it's called via run_in_executor
    # as run_in_executor handles the async wrapping part.
    mock_app.invoke = MagicMock() 
    mock_components = {}
    mock_fn.return_value = (mock_app, mock_components)
    return mock_fn

@pytest.fixture
def mock_create_debug_graph_fn():
    """Provides a mock for the create_debug_graph_fn."""
    mock_fn = MagicMock()
    mock_app = MagicMock()
    mock_app.invoke = MagicMock()
    mock_components = {}
    mock_fn.return_value = (mock_app, mock_components)
    return mock_fn

@pytest.fixture
def agent_lifecycle_controller_instance(mock_create_graph_fn, mock_create_debug_graph_fn):
    """Provides an AgentLifecycleController instance with mocked graph creation functions."""
    return AgentLifecycleController(
        create_graph_fn=mock_create_graph_fn,
        create_debug_graph_fn=mock_create_debug_graph_fn,
        debug_graph=False
    )

@pytest.fixture
def agent_lifecycle_controller_debug_instance(mock_create_graph_fn, mock_create_debug_graph_fn):
    """Provides an AgentLifecycleController instance for debug graph testing."""
    return AgentLifecycleController(
        create_graph_fn=mock_create_graph_fn,
        create_debug_graph_fn=mock_create_debug_graph_fn,
        debug_graph=True
    )

@pytest.mark.asyncio
async def test_initialize_graph_standard(agent_lifecycle_controller_instance, mock_create_graph_fn, mock_create_debug_graph_fn):
    """Test that the standard graph is initialized correctly."""
    assert agent_lifecycle_controller_instance.kfm_app is not None
    assert agent_lifecycle_controller_instance.agent_components is not None
    mock_create_graph_fn.assert_called_once()
    mock_create_debug_graph_fn.assert_not_called()

@pytest.mark.asyncio
async def test_initialize_graph_debug(agent_lifecycle_controller_debug_instance, mock_create_graph_fn, mock_create_debug_graph_fn):
    """Test that the debug graph is initialized correctly when debug_graph=True."""
    assert agent_lifecycle_controller_debug_instance.kfm_app is not None
    assert agent_lifecycle_controller_debug_instance.agent_components is not None
    mock_create_debug_graph_fn.assert_called_once()
    mock_create_graph_fn.assert_not_called()

@pytest.mark.asyncio
async def test_stop_current_run_active_task(agent_lifecycle_controller_instance):
    """Test stopping an active run."""
    # Create a real asyncio.Task wrapping an AsyncMock coroutine
    # This ensures it behaves like a real task when cancelled and awaited.
    dummy_coro_for_task = AsyncMock() 
    mock_task = asyncio.create_task(dummy_coro_for_task())
    
    # Mock the done() method if needed for specific initial state checks, 
    # but for cancellation, the task's actual done state will change.
    # For this test, we mainly care that cancel() is called and no error occurs during stop_current_run.

    agent_lifecycle_controller_instance.current_execution_task = mock_task

    await agent_lifecycle_controller_instance.stop_current_run()

    assert mock_task.cancelled()  # Check if the task was actually cancelled
    assert agent_lifecycle_controller_instance.current_execution_task is None
    # dummy_coro_for_task.assert_not_called() # The coro itself might not be called if cancelled early enough

@pytest.mark.asyncio
async def test_stop_current_run_no_active_task(agent_lifecycle_controller_instance):
    """Test stopping when no run is active."""
    agent_lifecycle_controller_instance.current_execution_task = None
    await agent_lifecycle_controller_instance.stop_current_run()
    assert agent_lifecycle_controller_instance.current_execution_task is None

@pytest.mark.asyncio
async def test_prepare_for_new_run_with_state(agent_lifecycle_controller_instance):
    """Test preparing for a new run with a specific state."""
    initial_state = KFMAgentState(task_name="test_task", current_snapshot_id="snap1")
    agent_lifecycle_controller_instance.current_execution_task = None 
    await agent_lifecycle_controller_instance.prepare_for_new_run_with_state(initial_state)
    assert agent_lifecycle_controller_instance.next_initial_state == initial_state

@pytest.mark.asyncio
async def test_prepare_for_new_run_stops_active_task(agent_lifecycle_controller_instance):
    """Test that preparing for a new run stops any currently active task."""
    dummy_coro_for_task = AsyncMock()
    mock_task = asyncio.create_task(dummy_coro_for_task())

    agent_lifecycle_controller_instance.current_execution_task = mock_task
    initial_state = KFMAgentState(task_name="new_task")

    await agent_lifecycle_controller_instance.prepare_for_new_run_with_state(initial_state)

    assert mock_task.cancelled()
    assert agent_lifecycle_controller_instance.current_execution_task is None
    assert agent_lifecycle_controller_instance.next_initial_state == initial_state

@pytest.mark.asyncio
async def test_start_new_run_success(agent_lifecycle_controller_instance, mock_create_graph_fn):
    """Test starting a new run successfully."""
    initial_state_dict = {"task_name": "run_task"}
    mock_kfm_app = mock_create_graph_fn.return_value[0]
    expected_final_state = {"result": "success"}
    mock_kfm_app.invoke.return_value = expected_final_state

    agent_lifecycle_controller_instance.current_execution_task = None
    agent_lifecycle_controller_instance.next_initial_state = None

    final_state = await agent_lifecycle_controller_instance.start_new_run(initial_state_dict)
    
    # The task should be cleared by the finally block in _execute_run_internal
    assert agent_lifecycle_controller_instance.current_execution_task is None 
    assert final_state == expected_final_state
    mock_kfm_app.invoke.assert_called_once_with(initial_state_dict)

@pytest.mark.asyncio
async def test_start_new_run_with_prepared_state(agent_lifecycle_controller_instance, mock_create_graph_fn):
    """Test starting a run uses the prepared state."""
    prepared_state = KFMAgentState(task_name="prepared_task")
    agent_lifecycle_controller_instance.next_initial_state = prepared_state
    mock_kfm_app = mock_create_graph_fn.return_value[0]
    mock_kfm_app.invoke.return_value = {"status": "done"}

    agent_lifecycle_controller_instance.current_execution_task = None

    await agent_lifecycle_controller_instance.start_new_run() 

    expected_invoke_arg = prepared_state.model_dump() if hasattr(prepared_state, 'model_dump') else dict(prepared_state)
    mock_kfm_app.invoke.assert_called_once_with(expected_invoke_arg) # Removed config from assertion
    assert agent_lifecycle_controller_instance.next_initial_state is None
    assert agent_lifecycle_controller_instance.current_execution_task is None

@pytest.mark.asyncio
async def test_start_new_run_no_initial_state(agent_lifecycle_controller_instance):
    """Test starting a run fails if no initial state is provided or prepared."""
    agent_lifecycle_controller_instance.current_execution_task = None
    agent_lifecycle_controller_instance.next_initial_state = None
    # Updated expected error message to match controller
    with pytest.raises(ValueError, match="Initial state for the agent run is missing."):
        await agent_lifecycle_controller_instance.start_new_run()

@pytest.mark.asyncio
async def test_start_new_run_app_not_initialized(mock_create_graph_fn, mock_create_debug_graph_fn):
    """Test starting a run fails if kfm_app is not initialized."""
    # Instantiate with a working graph fn first
    controller = AgentLifecycleController(
        create_graph_fn=mock_create_graph_fn,
        create_debug_graph_fn=mock_create_debug_graph_fn,
        debug_graph=False
    )
    # Manually set kfm_app to None to simulate failed initialization for this specific test part
    controller.kfm_app = None 

    # Updated regex match to be exact and use raw string
    with pytest.raises(RuntimeError, match=r"KFM agent graph \(kfm_app\) is not available."):
        await controller.start_new_run({"task_name": "some_task"})

@pytest.mark.asyncio
async def test_start_new_run_already_running(agent_lifecycle_controller_instance):
    """Test starting a new run fails if one is already in progress."""
    mock_task = AsyncMock(spec=asyncio.Task)
    mock_task.done.return_value = False
    agent_lifecycle_controller_instance.current_execution_task = mock_task
    # Updated expected error message to match controller
    with pytest.raises(RuntimeError, match="An agent execution is already in progress. Stop it before starting a new one."):
        await agent_lifecycle_controller_instance.start_new_run({"task_name": "another_task"})

@pytest.mark.asyncio
async def test_start_new_run_invoke_raises_exception(agent_lifecycle_controller_instance, mock_create_graph_fn):
    """Test that if kfm_app.invoke raises an exception, an error dict is returned."""
    initial_state_dict = {"task_name": "error_task"}
    mock_kfm_app = mock_create_graph_fn.return_value[0]
    test_exception = ValueError("Invoke failed!")
    mock_kfm_app.invoke.side_effect = test_exception

    agent_lifecycle_controller_instance.current_execution_task = None
    agent_lifecycle_controller_instance.next_initial_state = None

    result = await agent_lifecycle_controller_instance.start_new_run(initial_state_dict)
    
    assert result is not None
    # Updated expected status to match controller's returned dict
    assert result.get("status") == "execution_failed" 
    assert result.get("error_type") == "ValueError"
    assert result.get("error") == "Invoke failed!"
    assert agent_lifecycle_controller_instance.current_execution_task is None

@pytest.mark.asyncio
async def test_start_new_run_task_cancelled_externally(agent_lifecycle_controller_instance, mock_create_graph_fn, caplog):
    """Test behavior if the execution task is cancelled externally during invoke."""
    
    target_logger_name = "src.core.agent_lifecycle_controller"
    target_logger = logging.getLogger(target_logger_name)

    # Set caplog to capture INFO from root, and ensure our target logger is also at INFO.
    caplog.set_level(logging.INFO) # This sets root logger level and caplog handler level
    target_logger.setLevel(logging.INFO) # Ensure our specific logger also emits INFO

    initial_state_dict = {"task_name": "cancel_task"}
    mock_kfm_app = mock_create_graph_fn.return_value[0]
    # Simulate that the invoke call itself raises CancelledError, 
    # as if it was cancelled while running in the executor.
    mock_kfm_app.invoke.side_effect = asyncio.CancelledError("Task was cancelled by executor")

    agent_lifecycle_controller_instance.current_execution_task = None
    agent_lifecycle_controller_instance.next_initial_state = None

    # The CancelledError raised by invoke (in executor) is caught by _execute_run_internal,
    # which re-raises it. Then start_new_run catches it and returns a dict.
    result = await agent_lifecycle_controller_instance.start_new_run(initial_state_dict)
    
    expected_result = {"status": "cancelled", "message": "Agent run was cancelled externally."}
    assert result == expected_result
    
    # Give event loop a moment to process logs from other tasks
    await asyncio.sleep(0.01) 

    # Check for logs from both _execute_run_internal and start_new_run
    assert "Agent execution task (_execute_run_internal) was cancelled." in caplog.text
    assert "Awaiting current_execution_task in start_new_run was cancelled." in caplog.text
    assert agent_lifecycle_controller_instance.current_execution_task is None 