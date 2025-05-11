from typing import Dict, Any, Optional, List, Literal
import copy

class KFMAgentState:
    """
    KFMAgentState object structure for data flow between nodes in the LangGraph implementation.
    
    This class provides a structured and type-safe way to manage state data within the KFM Agent,
    including performance metrics, KFM decisions, execution results, and error tracking.
    
    Attributes:
        performance (Dict[str, Dict[str, float]]): Dictionary to store performance metrics for components
        kfm_decision (Optional[Dict[str, str]]): Dictionary to store KFM decision (e.g., {'action': 'kill', 'component': 'analyze_fast'})
        results (Dict[str, Any]): Dictionary to store execution results from component actions
        error (Optional[str]): Field to track error states (None when no errors)
        input (Dict[str, Any]): The input data to process
        task_name (str): Name of the current task
        task_requirements (Dict[str, float]): Requirements for the current task
        active_component (Optional[str]): Name of the active component
        current_activation_type (Optional[Literal['marry', 'fuck', 'kill']]): 
            Indicates how the current `active_component` was set by the last KFM action.
            - 'marry': Component chosen for long-term use.
            - 'fuck': Component chosen for temporary usage (repurposing).
            - 'kill': Indicates the last action aimed to deactivate/remove a component.
            - None: Initial state or state after non-KFM component changes.
        execution_performance (Optional[Dict[str, float]]): Performance of the execution
        done (bool): Whether the workflow is complete
    """
    
    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialize a new KFMAgentState instance.
        
        Args:
            initial_data: Optional dictionary with initial values for state properties
        """
        # Initialize default values
        self.input: Dict[str, Any] = {}
        self.task_name: str = "default"
        self.performance: Dict[str, Dict[str, float]] = {}  # Component performance metrics
        self.task_requirements: Dict[str, float] = {}  # Requirements for the current task
        self.kfm_decision: Optional[Dict[str, str]] = None  # The KFM action to apply
        self.active_component: Optional[str] = None  # Name of the active component
        self.current_activation_type: Optional[Literal['marry', 'fuck', 'kill']] = None # How the component was activated
        self.results: Dict[str, Any] = {}  # Result from executing the task
        self.execution_performance: Optional[Dict[str, float]] = None  # Performance of the execution
        self.error: Optional[str] = None  # Error message if something went wrong
        self.done: bool = False  # Whether the workflow is complete
        
        # Update with initial data if provided
        if initial_data:
            self.update(initial_data)
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update multiple state properties from a dictionary.
        
        Args:
            data: Dictionary with key-value pairs to update
        """
        # Mapping from TypedDict keys to class attributes
        key_mapping = {
            'input': 'input',
            'task_name': 'task_name',
            'performance_data': 'performance',  # Map from TypedDict name to our class attribute name
            'task_requirements': 'task_requirements',
            'kfm_action': 'kfm_decision',  # Map from TypedDict name to our class attribute name
            'active_component': 'active_component',
            'current_activation_type': 'current_activation_type', # Added
            'result': 'results',  # Map from TypedDict name to our class attribute name
            'execution_performance': 'execution_performance',
            'error': 'error',
            'done': 'done'
        }
        
        for key, value in data.items():
            if key in key_mapping:
                attr_name = key_mapping[key]
                setattr(self, attr_name, copy.deepcopy(value))
            else:
                # Skip unknown keys
                pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state object to dictionary compatible with TypedDict.
        
        Returns:
            Dictionary representation of the state
        """
        # Mapping from class attributes to TypedDict keys
        attr_mapping = {
            'input': 'input',
            'task_name': 'task_name',
            'performance': 'performance_data',  # Map from our class attribute name to TypedDict name
            'task_requirements': 'task_requirements',
            'kfm_decision': 'kfm_action',  # Map from our class attribute name to TypedDict name
            'active_component': 'active_component',
            'current_activation_type': 'current_activation_type', # Added
            'results': 'result',  # Map from our class attribute name to TypedDict name
            'execution_performance': 'execution_performance',
            'error': 'error',
            'done': 'done'
        }
        
        result = {}
        for attr_name, dict_key in attr_mapping.items():
            value = getattr(self, attr_name)
            if value is not None:  # Only include non-None values
                result[dict_key] = copy.deepcopy(value)
        
        return result
    
    def has_error(self) -> bool:
        """
        Check if the state contains an error.
        
        Returns:
            True if an error is present, False otherwise
        """
        return self.error is not None
    
    def set_performance(self, component_name: str, metrics: Dict[str, float]) -> None:
        """
        Set performance metrics for a specific component.
        
        Args:
            component_name: Name of the component
            metrics: Dictionary of performance metrics (e.g., {'latency': 0.5, 'accuracy': 0.9})
        """
        self.performance[component_name] = copy.deepcopy(metrics)
    
    def get_performance(self, component_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for a specific component or all components.
        
        Args:
            component_name: Optional name of the component to get metrics for
            
        Returns:
            Dictionary of performance metrics or all performance data
        """
        if component_name:
            return copy.deepcopy(self.performance.get(component_name, {}))
        return copy.deepcopy(self.performance)
    
    def set_kfm_decision(self, action: str, component: str) -> None:
        """
        Set a KFM decision.
        
        Args:
            action: KFM action (e.g., 'kill', 'marry')
            component: Target component name
        """
        self.kfm_decision = {'action': action, 'component': component}
    
    def clear_kfm_decision(self) -> None:
        """Clear the current KFM decision."""
        self.kfm_decision = None
    
    def set_result(self, result_data: Dict[str, Any]) -> None:
        """
        Set the execution result.
        
        Args:
            result_data: Result data dictionary
        """
        self.results = copy.deepcopy(result_data)
    
    def set_error(self, error_message: str) -> None:
        """
        Set an error state.
        
        Args:
            error_message: Error message
        """
        self.error = error_message
    
    def clear_error(self) -> None:
        """Clear the current error state."""
        self.error = None
    
    def set_done(self, done: bool = True) -> None:
        """
        Mark the workflow as done or not done.
        
        Args:
            done: Whether the workflow is complete (default True)
        """
        self.done = done
    
    def __str__(self) -> str:
        """
        Get a string representation of the state.
        
        Returns:
            String representation
        """
        components = []
        for key, value in self.to_dict().items():
            if isinstance(value, dict) and len(value) > 3:
                # Summarize large dictionaries
                components.append(f"{key}: {{{len(value)} items}}")
            else:
                components.append(f"{key}: {value}")
        
        return f"KFMAgentState({', '.join(components)})" 