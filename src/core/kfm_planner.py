import time
from src.core.state_monitor import StateMonitor
from src.core.execution_engine import ExecutionEngine
from src.logger import setup_logger

class KFMPlanner:
    """Dynamically selects KFM (Kill, Fuck, Marry) actions based on task requirements 
    and component performance data obtained from the StateMonitor. Aims to optimize
    component usage according to the KFM paradigm.
    See [KFM Paradigm Design](docs/design_notes/kfm_paradigm.md) for details.
    """
    def __init__(self, state_monitor: StateMonitor, execution_engine: ExecutionEngine):
        self.state_monitor = state_monitor
        self.execution_engine = execution_engine
        self.logger = setup_logger('KFMPlanner')
        self.logger.info("KFMPlanner initialized.")

    def decide_kfm_action(self, task_name: str) -> dict | None:
        """Decides the KFM action (marry, fuck, kill) based on task requirements and component performance.

        The decision follows this hierarchy:
        1. **Marry:** If a component meets all primary requirements (e.g., accuracy & latency).
           Selects the highest-scoring 'Marry' candidate.
        2. **Fuck:** If no 'Marry' candidate exists, but one or more components meet at least one
           primary requirement (e.g., accuracy OR latency). This represents temporary usage or
           repurposing of a sub-optimal component.
           Selects the highest-ranked 'Fuck' candidate (prioritizing accuracy, then latency).
        3. **Kill:** If no component is suitable for 'Marry' or 'Fuck'. Represents deactivation
           or removal (currently generic, component is None).

        Args:
            task_name: The name/ID of the task being considered.
            
        Returns:
            A dictionary representing the action ('action': ['marry'|'fuck'|'kill'], 'component': str|None)
            or None if requirements are missing or no action can be determined.
            Example: {'action': 'marry', 'component': 'analyze_accurate_fast'}
                     {'action': 'fuck', 'component': 'analyze_fast_but_imprecise'}
                     {'action': 'kill', 'component': None} 
        """
        self.logger.info(f"Deciding KFM action for task '{task_name}'")
        
        requirements = self.state_monitor.get_task_requirements(task_name)
        if not requirements:
            self.logger.error(f"Cannot decide action: No requirements found for task '{task_name}'.")
            return None

        min_accuracy = requirements.get('min_accuracy')
        max_latency = requirements.get('max_latency')

        if min_accuracy is None or max_latency is None:
            self.logger.error(f"Task '{task_name}' requirements are incomplete (missing min_accuracy or max_latency).")
            return None

        self.logger.debug(f"Task '{task_name}' Requirements: min_accuracy={min_accuracy:.2f}, max_latency={max_latency:.2f}s")

        # Assuming StateMonitor provides a way to get all components and their performance
        # This might be: self.state_monitor.get_all_component_performance() -> dict[str, dict]
        # Or: self.state_monitor.get_available_component_keys() -> list[str]
        # For now, let's placeholder with a hypothetical method call
        all_components_performance = self.state_monitor.get_performance_data() # Corrected method call
        if not all_components_performance:
            self.logger.warning("No component performance data available from StateMonitor.")
            return {'action': 'kill', 'component': None} # Or some other appropriate response

        marry_candidates = []
        fuck_candidates = []

        for component_key, perf_data in all_components_performance.items():
            latency = perf_data.get('latency', float('inf'))
            accuracy = perf_data.get('accuracy', 0.0)
            
            meets_accuracy = accuracy >= min_accuracy
            meets_latency = latency <= max_latency

            if meets_accuracy and meets_latency:
                # Score: (is_marry_candidate_flag, accuracy, -latency) - higher is better
                marry_candidates.append(((1, accuracy, -latency), component_key))
                self.logger.debug(f"Component '{component_key}' is a MARRY candidate (acc: {accuracy:.2f}, lat: {latency:.2f}s).")
            elif meets_accuracy or meets_latency:
                # Score: (accuracy, -latency) - higher is better
                # This component meets some but not all requirements, making it a 'Fuck' candidate.
                fuck_candidates.append(((accuracy, -latency), component_key))
                self.logger.debug(f"Component '{component_key}' is a FUCK candidate (acc: {accuracy:.2f}, lat: {latency:.2f}s).")
            else:
                self.logger.debug(f"Component '{component_key}' meets neither MARRY nor FUCK criteria (acc: {accuracy:.2f}, lat: {latency:.2f}s).")

        decision = None
        if marry_candidates:
            marry_candidates.sort(key=lambda x: x[0], reverse=True)
            chosen_component_key = marry_candidates[0][1]
            self.logger.info(f"Selected MARRY action with component '{chosen_component_key}'. Perf: {all_components_performance[chosen_component_key]['accuracy']:.2f} acc, {all_components_performance[chosen_component_key]['latency']:.2f}s lat")
            decision = {'action': 'marry', 'component': chosen_component_key}
        elif fuck_candidates:
            fuck_candidates.sort(key=lambda x: x[0], reverse=True)
            chosen_score, chosen_component_key = fuck_candidates[0]
            perf = all_components_performance[chosen_component_key]
            # Log the decision using WARNING level to highlight the temporary/compromise nature of 'Fuck' action.
            self.logger.warning(
                f"KFM Decision: FUCK component '{chosen_component_key}'. "
                f"Reason: Compromise solution (meets partial criteria). "
                f"Score: {chosen_score} (acc: {perf['accuracy']:.2f}, lat: {perf['latency']:.2f}s)"
            )
            decision = {'action': 'fuck', 'component': chosen_component_key}
        else:
            self.logger.warning(f"KFM Decision: KILL proposed. No suitable MARRY or FUCK component found for task '{task_name}'.")
            # Potentially identify a specific component to kill if needed, e.g., current active one if it's bad.
            # For now, generic kill.
            decision = {'action': 'kill', 'component': None} 
            
        self.logger.info(f"Final KFM Decision for task '{task_name}': {decision}")
        return decision
        
    def get_kfm_action(self, task_name: str, performance_data=None, requirements=None, current_state=None) -> dict | None:
        """Alias for decide_kfm_action for API compatibility.
        
        Args:
            task_name: The name/ID of the task being considered.
            performance_data: Optional performance data (ignored, uses state_monitor)
            requirements: Optional requirements (ignored, uses state_monitor)
            current_state: Optional current state (not used)
            
        Returns:
            A dictionary representing the action or None if no action needed.
        """
        self.logger.info(f"get_kfm_action called for '{task_name}' (forwarding to decide_kfm_action)")
        return self.decide_kfm_action(task_name)