import pytest
import asyncio
from unittest.mock import MagicMock, patch, call
from typing import Dict, Any, Optional, cast

from src.state_types import KFMAgentState, ActionType
from src.core.execution_engine import ExecutionResult
# Import the node function to test
from src.langgraph_nodes import execute_action_node, log_semantic_state_details # Ensure log_semantic_state_details is imported for patching

# Minimal KFMAgentState for testing
def create_test_state(
    kfm_action: Optional[Dict[str, Any]] = None,
    current_task_requirements: Optional[Dict[str, Any]] = None,
    execution_performance: Optional[Dict[str, Any]] = None # This will be set by mocked ExecutionEngine
) -> KFMAgentState:
    state = {
        "run_id": "test_run_satisfaction",
        "original_correlation_id": "test_corr_satisfaction",
        "input": {"data": "sample"},
        "task_name": "Test Task for Satisfaction",
        "kfm_action": kfm_action if kfm_action else {"action": ActionType.KEEP.value, "component": "TestComponent", "params": {}},
        "active_component": None,
        "result": None,
        "error": None,
        "done": False,
        "last_snapshot_ids": {},
        "current_task_requirements": current_task_requirements,
        "execution_performance": execution_performance # Initial state, will be overwritten by engine mock
    }
    return cast(KFMAgentState, state) # Need to import cast from typing for this to be valid

@pytest.mark.asyncio
class TestExecuteActionNodeSatisfaction:

    @pytest.fixture
    def mock_execution_engine(self):
        engine = MagicMock()
        # Default successful execution result
        engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={"summary": "OK"}, performance={}))
        return engine

    @pytest.fixture
    def mock_snapshot_service(self):
        service = MagicMock()
        service.take_snapshot = AsyncMock(return_value="snap_123") # Needs to be AsyncMock for await
        return service
    
    # Need to import AsyncMock from unittest.mock for Python 3.8+
    # For older versions, a synchronous MagicMock might work if the internal awaits are simple enough,
    # but AsyncMock is preferred.
    # Let's assume Python 3.8+ for now, or adjust if linter complains.
    # If AsyncMock is not found, it is part of unittest.mock from Python 3.8
    try:
        from unittest.mock import AsyncMock
    except ImportError:
        # Fallback for older Python versions if needed, though it might require more complex mocking
        class AsyncMock(MagicMock):
            async def __call__(self, *args, **kwargs):
                return super(AsyncMock, self).__call__(*args, **kwargs)

    @patch('src.langgraph_nodes.log_semantic_state_details') # Patch the imported function
    async def test_satisfaction_all_reqs_met(
        self, mock_log_semantic, mock_execution_engine, mock_snapshot_service
    ):
        task_reqs = {"metric1": 100, "metric2": True}
        exec_perf = {"metric1": 100, "metric2": True, "extra_metric": "abc"}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        # Check the call to log_semantic_state_details for success exit
        # We expect two calls normally (entry, exit_success)
        # The one we care about for calculated_metrics is the exit_success one
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success": # event_tag
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics is not None
                assert calculated_metrics["task_requirement_satisfaction"] == "MetAll (2/2)"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics, "log_semantic_state_details not called with exit_success or metrics"

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_some_reqs_met_some_unmet(
        self, mock_log_semantic, mock_execution_engine, mock_snapshot_service
    ):
        task_reqs = {"metric1": 100, "metric2": True, "metric3": "abc"}
        exec_perf = {"metric1": 100, "metric2": False, "metric3": "abc"}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "MetSome (2/3) [Details: Unmet:1]"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_some_reqs_met_some_perf_missing(
        self, mock_log_semantic, mock_execution_engine, mock_snapshot_service
    ):
        task_reqs = {"metric1": 100, "metric2": True, "metric3": "abc"}
        exec_perf = {"metric1": 100, "metric3": "abc"} # metric2 performance is missing
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "MetSome (2/3) [Details: PerfMissing:1]"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_no_reqs_met_all_unmet(
        self, mock_log_semantic, mock_execution_engine, mock_snapshot_service
    ):
        task_reqs = {"metric1": 100, "metric2": True}
        exec_perf = {"metric1": 99, "metric2": False}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "MetNone (0/2) [Details: Unmet:2]"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_no_reqs_met_all_perf_missing(
        self, mock_log_semantic, mock_execution_engine, mock_snapshot_service
    ):
        task_reqs = {"metric1": 100, "metric2": True}
        exec_perf = {"other_metric": "xyz"} # Performance for metric1, metric2 missing
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "MetNone (0/2) [Details: PerfMissing:2]"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_empty_task_reqs(self, mock_log_semantic, mock_execution_engine, mock_snapshot_service):
        task_reqs = {}
        exec_perf = {"metric1": 100}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "PerfDataAvailable_NoTrackedReqs"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_empty_exec_perf(self, mock_log_semantic, mock_execution_engine, mock_snapshot_service):
        task_reqs = {"metric1": 100}
        exec_perf = {}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "ReqsDefined (1)_NoPerfData"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_no_reqs_no_perf(self, mock_log_semantic, mock_execution_engine, mock_snapshot_service):
        task_reqs = None # Or {} and exec_perf=None
        exec_perf = None
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "NoReqsOrPerfData"
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_task_reqs_not_dict(self, mock_log_semantic, mock_execution_engine, mock_snapshot_service):
        task_reqs = "not_a_dict"
        exec_perf = {"metric1": 100}
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success":
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "PerfDataAvailable_NoReqsDefined" # Because task_reqs is not a dict
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

    @patch('src.langgraph_nodes.log_semantic_state_details')
    async def test_satisfaction_exec_perf_not_dict(self, mock_log_semantic, mock_execution_engine, mock_snapshot_service):
        task_reqs = {"metric1": 100}
        exec_perf = "not_a_dict" # This will be set by the mocked engine
        mock_execution_engine.execute = AsyncMock(return_value=ExecutionResult(status="success", result={}, performance=exec_perf))
        
        initial_state = create_test_state(current_task_requirements=task_reqs)
        await execute_action_node(initial_state, mock_execution_engine, mock_snapshot_service)
        
        found_call_with_metrics = False
        for log_call in mock_log_semantic.call_args_list:
            args, kwargs = log_call
            if args[1] == "execute_action_node_exit_success": # event_tag
                calculated_metrics = kwargs.get("calculated_metrics")
                assert calculated_metrics["task_requirement_satisfaction"] == "ReqsDefined (1)_NoPerfData" # Because exec_perf is not a dict
                found_call_with_metrics = True
                break
        assert found_call_with_metrics

# Need to add `from typing import cast` at the top of the file for create_test_state
# Need to ensure AsyncMock is correctly available (e.g. from unittest.mock if Python 3.8+) 