import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, call

# Assuming src.api.main.app is the FastAPI application instance
from src.api.main import app 
# Import defaults for verification
from src.transparency.local_explanation_service import DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_global_explanation_service():
    """Mocks the global local_explanation_service_instance in src.api.main"""
    mock_service = MagicMock()
    with patch('src.api.main.local_explanation_service_instance', mock_service):
        yield mock_service

@pytest.fixture
def mock_local_explanation_service_class():
    """Mocks the LocalKfmExplanationService class itself for testing custom log file instantiation."""
    with patch('src.api.main.LocalKfmExplanationService') as mock_class:
        # Configure the mock class to return a MagicMock instance when called
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance 
        yield mock_class, mock_instance # Yield both class and the instance it would return

class TestExplainDecisionAPI:

    def test_explain_decision_success_default_log(self, client, mock_global_explanation_service):
        run_id = "api_run_001"
        decision_index = 0
        expected_explanation_str = "API explanation for run_001"
        mock_context = {"run_id": run_id, "decision_index_found": decision_index, "action": "Keep"}

        mock_global_explanation_service.get_kfm_decision_context.return_value = mock_context
        mock_global_explanation_service.format_decision_explanation.return_value = expected_explanation_str
        mock_global_explanation_service.log_file_path = DEFAULT_SEMANTIC_LOG_FILE # Set for response check

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}&decision_index={decision_index}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["decision_index_found"] == decision_index
        assert data["formatted_explanation"] == expected_explanation_str
        assert data["log_file_used"] == DEFAULT_SEMANTIC_LOG_FILE
        assert data["event_tag_used"] == DEFAULT_DECISION_EVENT_TAG
        
        mock_global_explanation_service.get_kfm_decision_context.assert_called_once_with(
            run_id=run_id,
            decision_event_tag=DEFAULT_DECISION_EVENT_TAG,
            decision_index=decision_index
        )
        mock_global_explanation_service.format_decision_explanation.assert_called_once_with(mock_context)

    def test_explain_decision_context_not_found(self, client, mock_global_explanation_service):
        run_id = "api_run_002"
        mock_global_explanation_service.get_kfm_decision_context.return_value = None
        mock_global_explanation_service.log_file_path = DEFAULT_SEMANTIC_LOG_FILE

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert run_id in data["detail"]
        assert DEFAULT_SEMANTIC_LOG_FILE in data["detail"]

    def test_explain_decision_service_unavailable(self, client):
        # Patch the global instance to be None to simulate service unavailability
        with patch('src.api.main.local_explanation_service_instance', None):
            response = client.get("/agent/v1/explain-decision?run_id=any_run")
            assert response.status_code == 503
            assert "Local Explanation Service is not available" in response.json()["detail"]

    def test_explain_decision_internal_error_get_context(self, client, mock_global_explanation_service):
        run_id = "api_run_003"
        mock_global_explanation_service.get_kfm_decision_context.side_effect = Exception("DB error")

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}")
        assert response.status_code == 500
        assert "Error retrieving decision context: DB error" in response.json()["detail"]

    def test_explain_decision_internal_error_format_context(self, client, mock_global_explanation_service):
        run_id = "api_run_004"
        mock_context = {"run_id": run_id, "decision_index_found": 0, "action": "Kill"}
        mock_global_explanation_service.get_kfm_decision_context.return_value = mock_context
        mock_global_explanation_service.format_decision_explanation.side_effect = Exception("Formatting boom")

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}")
        assert response.status_code == 500
        assert "Error formatting decision explanation: Formatting boom" in response.json()["detail"]

    def test_explain_decision_success_custom_log_file(self, client, mock_local_explanation_service_class):
        run_id = "api_run_005"
        custom_log = "my/custom/semantic.log"
        expected_explanation_str = "Explanation from custom log"
        mock_context = {"run_id": run_id, "decision_index_found": 0, "action": "Marry"}

        # mock_local_explanation_service_class yields (MockClass, mock_instance_returned_by_class)
        mock_class, mock_instance = mock_local_explanation_service_class
        
        mock_instance.get_kfm_decision_context.return_value = mock_context
        mock_instance.format_decision_explanation.return_value = expected_explanation_str
        # The mock instance needs its log_file_path set as the real one would upon instantiation
        mock_instance.log_file_path = custom_log 

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}&log_file={custom_log}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["formatted_explanation"] == expected_explanation_str
        assert data["log_file_used"] == custom_log

        # Assert the class was called to create an instance with the custom log file
        mock_class.assert_called_once_with(log_file_path=custom_log)
        
        # Assert methods were called on the instance returned by the mocked class
        mock_instance.get_kfm_decision_context.assert_called_once_with(
            run_id=run_id,
            decision_event_tag=DEFAULT_DECISION_EVENT_TAG,
            decision_index=0
        )
        mock_instance.format_decision_explanation.assert_called_once_with(mock_context)

    def test_explain_decision_instantiation_error_custom_log(self, client, mock_local_explanation_service_class):
        run_id = "api_run_006"
        custom_log = "bad/path.log"

        mock_class, _ = mock_local_explanation_service_class
        mock_class.side_effect = Exception("Cannot create service") # Simulate error during LocalKfmExplanationService(log_file_path=custom_log)

        response = client.get(f"/agent/v1/explain-decision?run_id={run_id}&log_file={custom_log}")
        assert response.status_code == 500
        assert "Error initializing explanation service with custom log file" in response.json()["detail"]
        assert "Cannot create service" in response.json()["detail"] 