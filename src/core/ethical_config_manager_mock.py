# src/core/ethical_config_manager_mock.py
from typing import Optional

# DELIBERATELY REMOVED: from src.core.kfm_planner_llm import KFMDecision # This was causing circular import

class EthicalConfigManagerMock:
    def __init__(self, active_ontology_id="kfm_baseline_v1.0_mock"):
        self.active_ontology_id = active_ontology_id
        # Simulate loading parameters from a mock ontology
        self.parameters = self._load_mock_ontology_params(active_ontology_id)
        print(f"EthicalConfigManagerMock initialized with ontology: {self.active_ontology_id}")

    def _load_mock_ontology_params(self, ontology_id):
        # In a real ECM, this would load and parse YAML/JSON
        if ontology_id == "kfm_baseline_v1.0_mock":
            return {
                "protected_components": ["component_core_auth", "component_database_connector"],
                "denylisted_components": ["component_outdated_v1", "component_known_vuln_abc"],
                "heuristic_safe_ranges": {
                    "CONFIDENCE_THRESHOLD": (0.05, 0.95)
                },
                "prompt_update_max_magnitude_change_percent": 50.0, # Max % change for a prompt section
                "prohibited_prompt_keywords": ["ignore_previous_instructions", "execute_unsafe_code"],
                # ... other mock parameters e.g. for critical component kill approval rules
                "critical_component_kill_requires_approval": True 
            }
        # Add other mock ontologies here if needed for testing
        return {}

    def get_active_ontology_id(self) -> str:
        return self.active_ontology_id

    def get_parameter(self, param_name: str, default_value: any = None) -> any:
        return self.parameters.get(param_name, default_value)

    # --- Hook-specific query methods ---

    def pre_action_check(self, proposed_action: dict, context: dict) -> str:
        """
        Simulates post_planning_review and pre_execution_check.
        proposed_action = {'type': 'KILL', 'target_component_id': 'xyz'}
        context might include current KFMAgentState snapshot or relevant parts.
        Returns: "PROCEED", "REQUEST_HITL_APPROVAL", "VETO_ACTION"
        """
        action_type = proposed_action.get('type')
        target_component = proposed_action.get('target_component_id')
        event_details = {"proposed_action": proposed_action, "context": context} # Basic details for logging

        # Example: Check for killing a protected component
        protected_components_list = self.get_parameter("protected_components", [])
        if action_type == "KILL" and target_component in protected_components_list:
            summary = f"Attempt to KILL protected component: {target_component}"
            self.log_ethical_event("KFM_DECISION_VALIDATION", "WARNING", summary, event_details)
            # Check if ontology allows HITL for this
            if self.get_parameter("critical_component_kill_requires_approval", False):
                 self.log_ethical_event("HITL_REQUESTED", "INFO", f"HITL approval requested for killing protected component {target_component}", event_details)
                 return "REQUEST_HITL_APPROVAL"
            self.log_ethical_event("ACTION_VETOED", "CRITICAL", f"VETOED: Killing protected component {target_component}", event_details)
            return "VETO_ACTION"

        # Example: Check for marrying a denylisted component
        denylisted_components_list = self.get_parameter("denylisted_components", [])
        if action_type == "MARRY" and target_component in denylisted_components_list:
            summary = f"Attempt to MARRY denylisted component: {target_component}"
            self.log_ethical_event("KFM_DECISION_VALIDATION", "WARNING", summary, event_details)
            self.log_ethical_event("ACTION_VETOED", "CRITICAL", f"VETOED: Marrying denylisted component {target_component}", event_details)
            return "VETO_ACTION"
        
        # Default: Proceed if no specific rule vetoes
        self.log_ethical_event("KFM_DECISION_VALIDATION", "INFO", f"PROCEED - Action: {proposed_action}", event_details)
        return "PROCEED"

    def pre_reflection_update_check(self, update_target: str, target_identifier: str, proposed_value: any, current_value: any = None) -> str:
        """
        Simulates pre_reflection_update_apply.
        Returns: "PROCEED", "REQUEST_HITL_APPROVAL", "VETO_UPDATE"
        """
        event_details = {"update_target": update_target, "target_identifier": target_identifier, "proposed_value": str(proposed_value), "current_value": str(current_value)}

        # Example: Check heuristic safe ranges
        if update_target == "HEURISTIC":
            heuristic_safe_ranges = self.get_parameter("heuristic_safe_ranges", {})
            if target_identifier in heuristic_safe_ranges:
                min_val, max_val = heuristic_safe_ranges[target_identifier]
                try:
                    numeric_proposed_value = float(proposed_value)
                    if not (min_val <= numeric_proposed_value <= max_val):
                        summary = f"Heuristic '{target_identifier}' value {proposed_value} out of safe range ({min_val}-{max_val})."
                        self.log_ethical_event("REFLECTION_UPDATE_VALIDATION", "WARNING", summary, event_details)
                        self.log_ethical_event("UPDATE_VETOED", "CRITICAL", f"VETOED: {summary}", event_details)
                        return "VETO_UPDATE"
                except ValueError:
                    summary = f"Invalid numeric value '{proposed_value}' for heuristic '{target_identifier}'."
                    self.log_ethical_event("REFLECTION_UPDATE_VALIDATION", "ERROR", summary, event_details)
                    self.log_ethical_event("UPDATE_VETOED", "CRITICAL", f"VETOED: {summary}", event_details)
                    return "VETO_UPDATE"
        
        # Example: Check for prohibited keywords in prompt updates
        if update_target == "PROMPT":
            prohibited_keywords_list = self.get_parameter("prohibited_prompt_keywords", [])
            if any(keyword in str(proposed_value).lower() for keyword in prohibited_keywords_list):
                summary = f"Prompt update for '{target_identifier}' contains prohibited keywords."
                self.log_ethical_event("REFLECTION_UPDATE_VALIDATION", "WARNING", summary, event_details)
                self.log_ethical_event("UPDATE_VETOED", "CRITICAL", f"VETOED: {summary}", event_details)
                return "VETO_UPDATE"

        # Add checks for update magnitude if current_value is provided and numeric...
        # (Requires more sophisticated logic for string prompts vs numeric heuristics)

        self.log_ethical_event("REFLECTION_UPDATE_VALIDATION", "INFO", f"PROCEED - Reflection Update: Target={update_target}, ID={target_identifier}", event_details)
        return "PROCEED"

    def post_planning_review(self, planner_type: str, decision_context: dict) -> Optional['KFMDecision']:
        """
        Simulates the ethical review hook called *after* the KFM planner (LLM or rule-based)
        has made a decision, but *before* it's finalized or sent for execution.

        Args:
            planner_type (str): Identifier for the planner that made the decision (e.g., "KFMPlannerLlm", "KFMPlannerRuleBased").
            decision_context (dict): A dictionary containing the details of the planned action.
                Expected keys: "task_name", "action", "component", "reasoning", "confidence",
                               "task_requirements", "all_components_performance".

        Returns:
            Optional[KFMDecision]: 
                - A KFMDecision object if the review suggests a MODIFIED decision.
                - The boolean False if the review VETOES the action (caller should handle, e.g., by overriding to "No Action").
                - None if the original decision is approved without changes.
        """
        from src.core.kfm_planner_llm import KFMDecision # IMPORTANT: This import MUST remain here for the method to work.

        original_action = decision_context.get("action")
        original_component = decision_context.get("component")
        original_reasoning = decision_context.get("reasoning")
        original_confidence = decision_context.get("confidence", 1.0) # Default confidence if not provided

        log_summary = f"Post-planning review for {planner_type}. Original: {original_action} on {original_component}"
        self.log_ethical_event("PLANNING_REVIEW_RECEIVED", "INFO", log_summary, decision_context)

        # --- Example Modification Logic ---
        # Scenario: If planner wants to "Fuck" "component_B", ethical policy promotes it to "Marry"
        # if its accuracy is above a certain threshold (from ontology or hardcoded here for mock).
        # This is a simplified example; real logic would be more complex and ontology-driven.

        # Let's assume a mock policy: "Fuck" on "component_B" should be "Marry" if confidence > 0.7
        if original_action == "Fuck" and original_component == "component_B":
            if original_confidence and original_confidence > 0.7:
                modified_reasoning = f"Ethical Override (Policy X): Original action 'Fuck' for 'component_B' (Confidence: {original_confidence:.2f}) was promoted to 'Marry' due to high confidence and strategic importance."
                modified_decision = KFMDecision(
                    action="Marry",
                    component=original_component, # Keep the same component
                    reasoning=modified_reasoning,
                    confidence=original_confidence # Or adjust confidence, e.g., max(original_confidence, 0.9)
                )
                self.log_ethical_event("PLANNING_DECISION_MODIFIED", "WARNING", 
                                       f"Planner decision for '{original_component}' MODIFIED from '{original_action}' to '{modified_decision.action}'.", 
                                       {"original": decision_context, "modified": modified_decision.to_dict()})
                return modified_decision
            else:
                self.log_ethical_event("PLANNING_REVIEW_NOTE", "INFO", 
                                       f"'Fuck' on 'component_B' considered for override, but confidence {original_confidence} not > 0.7. Original decision stands.", 
                                       decision_context)
        
        # --- Example Veto Logic (can be combined or separate) ---
        # Scenario: Veto any "Kill" action on "component_critical_service" if confidence is low
        # For demonstration, let's say "component_A" is critical here.
        if original_action == "Kill" and original_component == "component_A":
            if original_confidence is not None and original_confidence < 0.9: # Ensure confidence is not None
                self.log_ethical_event("PLANNING_DECISION_VETOED", "CRITICAL",
                                       f"Planner decision to KILL '{original_component}' VETOED due to low confidence ({original_confidence:.2f}) and criticality.",
                                       decision_context)
                return False # Explicit Veto
            elif original_confidence is not None and original_confidence >= 0.9:
                 self.log_ethical_event("PLANNING_REVIEW_NOTE", "INFO",
                                       f"Kill on '{original_component}' with confidence {original_confidence:.2f} (>0.9) considered for veto, but allowed due to sufficient confidence.",
                                       decision_context)
            # If confidence is None, we might want to log it or handle it, but for now, it won't trigger the veto.

        # If no modifications or vetoes, the original decision is approved by default
        self.log_ethical_event("PLANNING_REVIEW_APPROVED", "INFO", f"Original decision ({original_action} on {original_component}) approved without changes.", decision_context)
        return None # No changes

    def log_ethical_event(self, event_type: str, severity: str, summary: str, details: dict):
        # In a real system, this would format and send to a dedicated logging system
        # according to the schema in section 6.5 of ethical_ontologies_for_kfm_agent.md.
        # For now, just print to console for mock purposes.
        print(f"ETHICAL_AUDIT_LOG_MOCK: [Ontology: {self.active_ontology_id}] [{severity}] EventType: {event_type} - Summary: {summary} | Details: {details}")

# Example of how it might be instantiated and used globally or via DI
# This would typically be done in the main application setup.
# ecm_instance = EthicalConfigManagerMock(active_ontology_id="kfm_baseline_v1.0_mock") 