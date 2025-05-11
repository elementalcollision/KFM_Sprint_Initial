from src.logger import setup_logger
from typing import Dict, Any, Optional
from src.core.component_registry import ComponentRegistry

class StateMonitor:
    """Monitors component performance and task requirements."""
    
    def __init__(self, component_registry: ComponentRegistry, performance_data: Optional[Dict[str, Any]] = None, task_requirements: Optional[Dict[str, Any]] = None):
        """Initialize the StateMonitor.
        
        Args:
            component_registry: The ComponentRegistry instance.
            performance_data: Optional dictionary of performance metrics by component
            task_requirements: Optional dictionary of requirements by task
        """
        self.logger = setup_logger('StateMonitor')
        self.component_registry = component_registry
        
        # Initialize with provided data or defaults
        self._performance_data = performance_data or {
            'analyze_fast': {
                'latency': 0.5,  # seconds
                'accuracy': 0.7   # 0.0-1.0 scale
            },
            'analyze_accurate': {
                'latency': 2.0,   # seconds
                'accuracy': 0.95  # 0.0-1.0 scale
            },
            'analyze_balanced': {
                'latency': 1.0,   # seconds
                'accuracy': 0.85  # 0.0-1.0 scale
            }
        }
        
        self._task_requirements = task_requirements or {
            'default': {
                'max_latency': 1.5,  # seconds
                'min_accuracy': 0.8   # 0.0-1.0 scale
            }
        }
        
        self.logger.info(f"StateMonitor initialized with {len(self._performance_data)} components and {len(self._task_requirements)} task types")
    
    def get_performance_data(self, component_name=None):
        """Get performance data for a specific component or all components.
        
        Args:
            component_name: Optional name of the component to get data for
            
        Returns:
            Dictionary of performance metrics for the component or all components
        """
        if component_name:
            result = self._performance_data.get(component_name, {})
            self.logger.debug(f"Retrieved performance data for component '{component_name}': {result}")
            return result
            
        self.logger.debug(f"Retrieved performance data for all components: {list(self._performance_data.keys())}")
        return self._performance_data
    
    def get_task_requirements(self, task_name='default'):
        """Get requirements for a specific task.
        
        Args:
            task_name: Name of the task to get requirements for
            
        Returns:
            Dictionary of requirements for the task
        """
        result = self._task_requirements.get(task_name, self._task_requirements['default'])
        self.logger.debug(f"Retrieved requirements for task '{task_name}': {result}")
        return result
        
    def update_performance_data(self, component_name: str, metrics: Dict[str, float]) -> None:
        """Update performance metrics for a component.
        
        Args:
            component_name: Name of the component to update
            metrics: Dictionary of metrics to update
        """
        if component_name not in self._performance_data:
            self._performance_data[component_name] = {}
            
        # Update only the provided metrics
        for key, value in metrics.items():
            self._performance_data[component_name][key] = value
            
        self.logger.info(f"Updated performance data for component '{component_name}': {metrics}")
        
    def add_task_requirements(self, task_name: str, requirements: Dict[str, float]) -> None:
        """Add or update requirements for a task.
        
        Args:
            task_name: Name of the task
            requirements: Dictionary of requirements
        """
        self._task_requirements[task_name] = requirements
        self.logger.info(f"Added requirements for task '{task_name}': {requirements}")
        
    def validate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the current state against requirements.
        
        Args:
            state: Current state of the system with metrics
            
        Returns:
            Dictionary containing validation results
        """
        self.logger.info(f"Validating state against requirements")
        
        # Default validation result
        validation_result = {
            "valid": True,
            "component_metrics": {},
            "flags": {
                "performance_issue": False,
                "accuracy_issue": False
            },
            "recommendations": []
        }
        
        # Get active component
        active_component = state.get("active_component", "analyze_balanced")
        task_name = state.get("task_name", "default")
        task_requirements = self.get_task_requirements(task_name)
        
        # Add component metrics to result
        for component, metrics in self._performance_data.items():
            validation_result["component_metrics"][component] = metrics
            
            # Flag issues with currently active component
            if component == active_component:
                # Check latency
                if metrics.get("latency", 0) > task_requirements.get("max_latency", 1.5):
                    validation_result["flags"]["performance_issue"] = True
                    validation_result["recommendations"].append(f"Component {component} exceeds latency requirements")
                
                # Check accuracy
                if metrics.get("accuracy", 0) < task_requirements.get("min_accuracy", 0.8):
                    validation_result["flags"]["accuracy_issue"] = True
                    validation_result["recommendations"].append(f"Component {component} falls below accuracy requirements")
        
        # Set overall validity
        if validation_result["flags"]["performance_issue"] or validation_result["flags"]["accuracy_issue"]:
            validation_result["valid"] = False
            
        self.logger.debug(f"State validation result: {validation_result}")
        return validation_result 