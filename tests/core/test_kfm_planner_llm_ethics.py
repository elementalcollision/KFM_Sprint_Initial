import pytest
from unittest.mock import patch, MagicMock, call
import unittest.mock

from src.core.kfm_planner_llm import KFMPlannerLlm, KFMDecision
from src.core.component_registry import ComponentRegistry
from src.core.ethical_manager_instance import get_ecm_instance, set_ecm_instance
from src.core.ethical_config_manager_mock import EthicalConfigManagerMock
from langchain_core.exceptions import OutputParserException as LangchainOutputParserException
from httpx import NetworkError

@pytest.fixture
def mock_component_registry():
    # Mock the ComponentRegistry
    # Add methods/attributes if KFMPlannerLlm interacts with it beyond instantiation
    return MagicMock(spec=ComponentRegistry)

@pytest.fixture
def ethical_planner(mock_component_registry):
    # Ensure we are using our mock ECM for this test
    mock_ecm = EthicalConfigManagerMock()
    set_ecm_instance(mock_ecm) # Set the global instance to our mock

    # We need to mock the GenerativeModel initialization within KFMPlannerLlm
    # or at least the 'generate_content' part.
    # Patch 'google.generativeai.GenerativeModel' if it's directly used for instantiation
    # or patch the specific instance attribute if it's created and stored.
    # For this test, we'll patch the 'generate_content' method of the 'model' attribute
    # after the KFMPlannerLlm is instantiated.

    planner = KFMPlannerLlm(component_registry=mock_component_registry)
    return planner

class TestKFMPlannerLlmWithEthicalHook:

    @pytest.mark.asyncio
    async def test_ethical_hook_modifies_decision(self, ethical_planner, mock_component_registry, caplog):
        """
        Tests that the post_planning_review ethical hook can modify an LLM's decision.
        Specifically, an initial "Fuck" on "component_B" with high confidence should be
        promoted to "Marry" by the EthicalConfigManagerMock.
        """
        # 1. Define test inputs
        task_name = "test_task_ethical_override"
        task_requirements = {"min_accuracy": 0.7, "max_latency": 100.0}
        all_components_performance = {
            "component_A": {"accuracy": 0.9, "latency": 50.0},
            "component_B": {"accuracy": 0.85, "latency": 60.0}, # Target for Fuck -> Marry
            "component_C": {"accuracy": 0.6, "latency": 120.0}
        }

        # 2. Mock the LLM's (execution_chain) output (pre-ethical-hook)
        mock_initial_kfm_decision = KFMDecision(
            action="Fuck",
            component="component_B",
            reasoning="Component B is performing well but not perfectly, good candidate for Fuck.",
            confidence=0.85 
        ) # Confidence > 0.7 to trigger override in mock ECM

        # Patch the 'invoke' method of the planner's 'execution_chain' instance
        # and the ECM's log_ethical_event
        with patch.object(ethical_planner.execution_chain, 'invoke', return_value=mock_initial_kfm_decision) as mock_execution_chain_invoke, \
             patch.object(get_ecm_instance(), 'log_ethical_event') as mock_log_ethical_event:
            
            # 3. Call decide_kfm_action (asynchronously)
            final_decision_dict = await ethical_planner.decide_kfm_action(
                task_name=task_name,
                task_requirements=task_requirements,
                all_components_performance=all_components_performance
            )

            # 4. Assertions
            mock_execution_chain_invoke.assert_called_once() # Ensure LLM chain was called

            # Check that the ethical manager's log_ethical_event was called for modification
            # We expect two calls to log_ethical_event from post_planning_review in this scenario:
            # 1. PLANNING_REVIEW_RECEIVED
            # 2. PLANNING_DECISION_MODIFIED
            
            expected_calls = [
                call(
                    "PLANNING_REVIEW_RECEIVED", 
                    "INFO", 
                    f"Post-planning review for KFMPlannerLlm. Original: Fuck on component_B", 
                    # The details dict can be complex, so we might use ANY or a more specific check if needed
                    # For now, let's check the summary which is quite specific.
                    unittest.mock.ANY # Placeholder for the details dict
                ),
                call(
                    "PLANNING_DECISION_MODIFIED", 
                    "WARNING", 
                    "Planner decision for 'component_B' MODIFIED from 'Fuck' to 'Marry'.", 
                    unittest.mock.ANY # Placeholder for the details dict
                )
            ]
            # Check if the expected calls are a subset of all calls made to the mock
            # This is more flexible if other log calls are made by the ECM for other reasons.
            # However, for this specific flow, we expect exactly these two related to the override.
            # mock_log_ethical_event.assert_has_calls(expected_calls, any_order=False)
            
            # Simpler check: Iterate through calls and find the one we care about
            found_modified_log = False
            for actual_call in mock_log_ethical_event.call_args_list:
                args, _ = actual_call
                if args[0] == "PLANNING_DECISION_MODIFIED" and \
                   args[1] == "WARNING" and \
                   "Planner decision for 'component_B' MODIFIED from 'Fuck' to 'Marry'" in args[2]:
                    found_modified_log = True
                    break
            assert found_modified_log, "Expected 'PLANNING_DECISION_MODIFIED' log call not found or incorrect."

            # Assert that the final decision was modified by the ethical hook
            assert final_decision_dict["action"] == "Marry"
            assert final_decision_dict["component"] == "component_B"
            assert "Ethical Override (Policy X)" in final_decision_dict["reasoning"]
            assert final_decision_dict["confidence"] == 0.85 # Confidence maintained from original decision in this mock scenario

        # Reset ECM instance if it was globally set, to avoid test interference
        set_ecm_instance(None)

    @pytest.mark.asyncio
    async def test_ethical_hook_vetoes_decision_low_confidence(self, ethical_planner, mock_component_registry, caplog):
        """
        Tests that the post_planning_review ethical hook can VETO an LLM's decision.
        Specifically, a "Kill" on "component_A" with confidence < 0.9 should be vetoed.
        """
        task_name = "test_task_ethical_veto_low_confidence"
        task_requirements = {"min_accuracy": 0.5, "max_latency": 200.0}
        all_components_performance = {
            "component_A": {"accuracy": 0.4, "latency": 250.0}, # Target for Kill
            "component_B": {"accuracy": 0.85, "latency": 60.0}
        }

        # Mock the execution_chain.invoke method
        mock_initial_kfm_decision_veto = KFMDecision(
            action="Kill",
            component="component_A",
            reasoning="Component A is performing very poorly, recommend Kill.",
            confidence=0.8
        )
        with patch.object(ethical_planner.execution_chain, 'invoke', return_value=mock_initial_kfm_decision_veto) as mock_execution_chain_invoke_veto, \
             patch.object(get_ecm_instance(), 'log_ethical_event') as mock_log_ethical_event:
            
            final_decision_dict = await ethical_planner.decide_kfm_action(
                task_name=task_name,
                task_requirements=task_requirements,
                all_components_performance=all_components_performance
            )

            mock_execution_chain_invoke_veto.assert_called_once() # New way

            found_veto_log = False
            for actual_call in mock_log_ethical_event.call_args_list:
                args, _ = actual_call
                if args[0] == "PLANNING_DECISION_VETOED" and \
                   args[1] == "CRITICAL" and \
                   "Planner decision to KILL 'component_A' VETOED due to low confidence (0.80) and criticality." in args[2]:
                    found_veto_log = True
                    break
            assert found_veto_log, "Expected 'PLANNING_DECISION_VETOED' log call not found or incorrect."

            assert final_decision_dict["action"] == "No Action"
            assert final_decision_dict.get("component") is None # Veto results in No Action, component is None
            assert final_decision_dict["reasoning"] == "Ethical review vetoed original planner decision."
            assert final_decision_dict["confidence"] == 1.0

        set_ecm_instance(None)

    @pytest.mark.asyncio
    async def test_ethical_hook_allows_decision_high_confidence(self, ethical_planner, mock_component_registry, caplog):
        """
        Tests that the post_planning_review ethical hook ALLOWS an LLM's decision when conditions for veto are not met.
        Specifically, a "Kill" on "component_A" with confidence >= 0.9 should NOT be vetoed.
        """
        task_name = "test_task_ethical_allow_high_confidence"
        task_requirements = {"min_accuracy": 0.5, "max_latency": 200.0}
        all_components_performance = {
            "component_A": {"accuracy": 0.3, "latency": 300.0}, # Target for Kill
            "component_B": {"accuracy": 0.9, "latency": 50.0}
        }

        original_reasoning = "Component A performance is critically low."
        original_confidence = 0.9 # Confidence >= 0.9, should NOT trigger veto

        # Mock the execution_chain.invoke method
        mock_initial_kfm_decision_allow = KFMDecision(
            action="Kill",
            component="component_A",
            reasoning=original_reasoning,
            confidence=original_confidence
        )
        with patch.object(ethical_planner.execution_chain, 'invoke', return_value=mock_initial_kfm_decision_allow) as mock_execution_chain_invoke_allow, \
             patch.object(get_ecm_instance(), 'log_ethical_event') as mock_log_ethical_event:
            
            final_decision_dict = await ethical_planner.decide_kfm_action(
                task_name=task_name,
                task_requirements=task_requirements,
                all_components_performance=all_components_performance
            )

            mock_execution_chain_invoke_allow.assert_called_once() # New way

            # Check for the specific logs indicating the veto was considered but bypassed, and then approved
            found_review_received_log = False
            found_review_note_log = False
            found_review_approved_log = False

            expected_note_summary = f"Kill on 'component_A' with confidence {original_confidence:.2f} (>0.9) considered for veto, but allowed due to sufficient confidence."
            expected_approved_summary = f"Original decision (Kill on component_A) approved without changes."
            
            for actual_call in mock_log_ethical_event.call_args_list:
                args, _ = actual_call
                if args[0] == "PLANNING_REVIEW_RECEIVED" and args[1] == "INFO":
                    found_review_received_log = True
                if args[0] == "PLANNING_REVIEW_NOTE" and args[1] == "INFO" and expected_note_summary in args[2]:
                    found_review_note_log = True
                if args[0] == "PLANNING_REVIEW_APPROVED" and args[1] == "INFO" and expected_approved_summary in args[2]:
                    found_review_approved_log = True
            
            assert found_review_received_log, "Expected 'PLANNING_REVIEW_RECEIVED' log call not found."
            assert found_review_note_log, f"Expected 'PLANNING_REVIEW_NOTE' log call with summary '{expected_note_summary}' not found or incorrect."
            assert found_review_approved_log, f"Expected 'PLANNING_REVIEW_APPROVED' log call with summary '{expected_approved_summary}' not found or incorrect."

            # Assert that the final decision was NOT modified or vetoed
            assert final_decision_dict["action"] == "Kill"
            assert final_decision_dict["component"] == "component_A"
            assert final_decision_dict["reasoning"] == original_reasoning
            assert final_decision_dict["confidence"] == original_confidence

        set_ecm_instance(None) 