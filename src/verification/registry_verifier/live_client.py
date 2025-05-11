"""
Live Component Registry Client

This module provides a concrete implementation of the ComponentRegistryClient that
interfaces with the actual ComponentRegistry instances in the application.
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import inspect
import json
from .client import ComponentRegistryClient

class LiveComponentRegistryClient(ComponentRegistryClient):
    """
    A client implementation that directly interfaces with a ComponentRegistry instance
    to extract and verify its state.
    """
    
    def __init__(self, component_registry, config: Optional[Dict[str, Any]] = None):
        """
        Initialize with an actual ComponentRegistry instance.
        
        Args:
            component_registry: An instance of ComponentRegistry
            config: Additional configuration options
        """
        super().__init__(config)
        self.registry = component_registry
        self.fetch_timestamp = datetime.now()
        
    def get_component_state(self, component_id: str, at_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the state of a specific component from the registry.
        
        Args:
            component_id: The ID/key of the component to check
            at_time: Not supported for live registry - will use current state
            
        Returns:
            A dictionary representing the component's state, or None if not found
        """
        if at_time:
            # Live client doesn't support historical states - log a warning
            self._log_warning("Historical state retrieval not supported. Using current state.")
        
        # Get all component functions from the registry
        components = self.registry.list_components()
        
        if component_id not in components:
            return None
            
        component_func = components.get(component_id)
        
        # Extract metadata about the component function
        return self._extract_component_metadata(component_id, component_func)
    
    def get_all_components_state(self, at_time: Optional[datetime] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Retrieves the state of all components from the registry.
        
        Args:
            at_time: Not supported for live registry - will use current state
            
        Returns:
            A dictionary mapping component IDs to their states
        """
        if at_time:
            # Live client doesn't support historical states - log a warning
            self._log_warning("Historical state retrieval not supported. Using current state.")
        
        # Get all component functions from the registry
        components = self.registry.list_components()
        
        # Create the state dictionary
        states = {}
        
        for component_id, component_func in components.items():
            states[component_id] = self._extract_component_metadata(component_id, component_func)
        
        # Add the registry-level state information
        default_key = self.registry.get_default_component_key()
        if default_key:
            for component_id in states:
                if component_id == default_key:
                    states[component_id]["is_default"] = True
                else:
                    states[component_id]["is_default"] = False
        
        return states
    
    def get_registry_snapshot(self, snapshot_identifier: Any = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a snapshot of the entire registry state.
        
        Args:
            snapshot_identifier: Not used for live registry - will use current state
            
        Returns:
            A dictionary with the registry's state
        """
        # Get all component states
        component_states = self.get_all_components_state()
        
        # Add registry-level metadata
        registry_snapshot = {
            "components": component_states,
            "default_component_key": self.registry.get_default_component_key(),
            "component_count": len(component_states),
            "snapshot_time": datetime.now().isoformat(),
        }
        
        return registry_snapshot

    def _extract_component_metadata(self, component_id: str, component_func: Callable) -> Dict[str, Any]:
        """
        Extract metadata and state information from a component function.
        
        Args:
            component_id: The ID/key of the component
            component_func: The actual component function
            
        Returns:
            A dictionary with the component's metadata
        """
        # Basic metadata
        metadata = {
            "component_id": component_id,
            "is_default": (component_id == self.registry.get_default_component_key()),
            "callable": callable(component_func),
            "function_name": component_func.__name__,
            "module": component_func.__module__,
        }
        
        # Add function signature information
        try:
            sig = inspect.signature(component_func)
            metadata["signature"] = {
                "parameters": [param for param in sig.parameters],
                "parameter_count": len(sig.parameters),
                "return_annotation": str(sig.return_annotation)
            }
        except (ValueError, TypeError):
            # Some callables don't support signature inspection
            metadata["signature"] = {"error": "Could not inspect signature"}
        
        # Add function docstring if available
        if component_func.__doc__:
            metadata["doc"] = component_func.__doc__.strip()
        
        # Add function attributes that might be set on component functions
        # (like accuracy_level, latency_profile, etc.)
        for attr_name in dir(component_func):
            if not attr_name.startswith("__") and not callable(getattr(component_func, attr_name)):
                try:
                    attr_value = getattr(component_func, attr_name)
                    # Only include serializable attributes
                    json.dumps({"test": attr_value})  # Will raise error if not serializable
                    metadata[f"attr_{attr_name}"] = attr_value
                except (TypeError, OverflowError, ValueError):
                    # Skip non-serializable attributes
                    pass
        
        return metadata
    
    def _log_warning(self, message: str) -> None:
        """Log a warning message."""
        # Use the registry's logger if available, otherwise just print
        if hasattr(self.registry, 'logger'):
            self.registry.logger.warning(message)
        else:
            print(f"WARNING: {message}") 