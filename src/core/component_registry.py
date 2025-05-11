import threading
from typing import Callable, Dict, List, Optional, Tuple, Any
from packaging.version import parse as parse_version
from src.logger import setup_logger
from .discovery import ModuleMetadata

class ComponentRegistry:
    """Registry for managing KFM analysis components and dynamically loaded modules.

    Note: ComponentRegistry manages the currently active default component
    but does not track whether that component was activated via 'Marry' or 'Fuck'.
    That contextual information is managed by KFMAgentState.
    """

    def __init__(self):
        """Initialize the ComponentRegistry."""
        self._modules: Dict[str, Dict[str, ModuleMetadata]] = {}
        self._default_module_key: Optional[Tuple[str, str]] = None
        self._lock = threading.RLock()
        self._event_listeners: Dict[str, List[Callable]] = {
            "registered": [],
            "deregistered": []
        }
        # No need for separate active component tracking - moved to ExecutionEngine
        self.logger = setup_logger('ComponentRegistry')
        self.logger.info("ComponentRegistry initialized with dynamic module support.")
    
    # This method will be replaced/removed in favor of register_module
    # def register_component(self, key: str, component_func: Callable, is_default: bool = False):
    #     ...

    def _notify(self, event_type: str, module_data: Any, version_info: Optional[str] = None):
        """Internal helper to notify listeners of an event."""
        # For thread safety on listeners list, either lock or iterate over a copy.
        listeners_for_event = list(self._event_listeners.get(event_type, []))
        
        for callback in listeners_for_event:
            try:
                if event_type == "registered":
                    # Assuming module_data is ModuleMetadata for "registered"
                    callback(module_data) 
                elif event_type == "deregistered":
                    # Assuming module_data is module_name for "deregistered"
                    callback(module_data, version_info) # version_info is the specific version or None for all
            except Exception as e:
                self.logger.error(f"Error executing event listener {callback.__name__} for event {event_type}: {e}", exc_info=True)

    def register_module(self, module_meta: ModuleMetadata, is_default: bool = False):
        """
        Registers a module based on its metadata. Handles versioning.

        Args:
            module_meta (ModuleMetadata): The metadata object for the module to register.
            is_default (bool): Whether this specific module version should become the default.
        """
        if not isinstance(module_meta, ModuleMetadata):
            raise TypeError("module_meta must be an instance of ModuleMetadata")

        with self._lock:
            module_name = module_meta.module_name
            version = module_meta.version

            if module_name not in self._modules:
                self._modules[module_name] = {}
            
            if version in self._modules[module_name]:
                self.logger.warning(
                    f"Module '{module_name}' version '{version}' already registered. Overwriting."
                )
            
            self._modules[module_name][version] = module_meta
            self.logger.info(f"Module '{module_name}' version '{version}' registered.")
            
            self._notify("registered", module_meta) # Pass ModuleMetadata object

            if is_default or self._default_module_key is None:
                try:
                    self.set_default_module(module_name, version) # To be implemented/refactored
                except ValueError as e: 
                    self.logger.error(f"Error setting default module during registration of {module_name} v{version}: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to module lifecycle events.
        Supported event_types: "registered", "deregistered".

        Args:
            event_type (str): The type of event to subscribe to.
            callback (Callable): The function to call when the event occurs.
                                 For "registered", callback(module_meta: ModuleMetadata).
                                 For "deregistered", callback(module_name: str, version: Optional[str]).
        """
        if event_type not in self._event_listeners:
            self.logger.warning(f"Attempted to subscribe to unknown event type: {event_type}. Supported: {list(self._event_listeners.keys())}")
            return
        
        with self._lock: 
            if callback not in self._event_listeners[event_type]:
                self._event_listeners[event_type].append(callback)
                # Safely get listener name
                listener_name = getattr(callback, '__name__', repr(callback))
                self.logger.info(f"Listener {listener_name} subscribed to event '{event_type}'.")
            else:
                # Safely get listener name here too
                listener_name = getattr(callback, '__name__', repr(callback))
                self.logger.info(f"Listener {listener_name} already subscribed to event '{event_type}'.")

    def deregister_module(self, module_name: str, version: Optional[str] = None) -> bool:
        """
        Deregisters a module or a specific version of a module.

        Args:
            module_name (str): The name of the module to deregister.
            version (Optional[str]): The specific version to deregister. 
                                     If None, all versions of the module are deregistered.

        Returns:
            bool: True if any module/version was successfully deregistered, False otherwise.
        """
        if not isinstance(module_name, str) or not module_name.strip():
            self.logger.error("deregister_module: module_name must be a non-empty string.")
            return False

        with self._lock:
            if module_name not in self._modules:
                self.logger.warning(f"Module '{module_name}' not found for deregistration.")
                return False

            deregistered_something = False

            if version is not None:
                # Deregister a specific version
                if version in self._modules[module_name]:
                    # module_meta_to_remove = self._modules[module_name].pop(version) # Keep for notification if needed
                    del self._modules[module_name][version]
                    self.logger.info(f"Module '{module_name}' version '{version}' deregistered.")
                    self._notify("deregistered", module_name, version_info=version) 
                    deregistered_something = True
                    
                    if self._default_module_key == (module_name, version):
                        self._default_module_key = None
                        self.logger.info(f"Default module '{module_name}' version '{version}' was deregistered. Default cleared.")
                    
                    if not self._modules[module_name]: # Check if the inner dict is empty
                        del self._modules[module_name]
                        self.logger.info(f"All versions of module '{module_name}' removed after deregistering version '{version}'.")
                else:
                    self.logger.warning(f"Version '{version}' of module '{module_name}' not found for deregistration.")
            else:
                # Deregister all versions of the module
                if module_name in self._modules: # This check is somewhat redundant due to the one at the start of the lock
                    # Notify with module_name, implying all its versions are being removed
                    self._notify("deregistered", module_name, version_info=None) 
                    
                    del self._modules[module_name]
                    self.logger.info(f"All versions of module '{module_name}' deregistered.")
                    deregistered_something = True

                    if self._default_module_key and self._default_module_key[0] == module_name:
                        self._default_module_key = None
                        self.logger.info(f"Default module '{module_name}' (all versions) was deregistered. Default cleared.")
            
            return deregistered_something

    def list_modules(self) -> Dict[str, Dict[str, ModuleMetadata]]:
        """List all registered modules with their versions.

        Returns:
            Dict[str, Dict[str, ModuleMetadata]]: Dictionary of module names to a dict of their versions and metadata.
        """
        with self._lock:
            # Return a deep copy to prevent external modification of cached ModuleMetadata objects
            # For now, a shallow copy of the outer dicts and direct refs to immutable ModuleMetadata
            return {name: vers.copy() for name, vers in self._modules.items()}

    def get_module_names(self) -> List[str]:
        """Get the names (keys) of all registered module groups (module_name).
        
        Returns:
            List[str]: A list of module names.
        """
        with self._lock:
            return list(self._modules.keys())

    def get_module_versions(self, module_name: str) -> Optional[Dict[str, ModuleMetadata]]:
        """Get all registered versions for a specific module name.

        Args:
            module_name (str): The name of the module.

        Returns:
            Optional[Dict[str, ModuleMetadata]]: A dictionary of version strings to ModuleMetadata, or None if module not found.
        """
        with self._lock:
            if module_name in self._modules:
                return self._modules[module_name].copy() # Return a copy of the versions dict
            self.logger.warning(f"Module family '{module_name}' not found.")
            return None

    def get_module(self, module_name: str, version: str) -> Optional[ModuleMetadata]:
        """Get a specific version of a module by its name and version string.

        Args:
            module_name (str): The name of the module.
            version (str): The specific version string of the module.

        Returns:
            Optional[ModuleMetadata]: The ModuleMetadata for the specific version, or None if not found.
        """
        with self._lock:
            if module_name in self._modules and version in self._modules[module_name]:
                return self._modules[module_name][version]
            self.logger.warning(f"Module '{module_name}' version '{version}' not found.")
            return None

    def get_latest_module_version(self, module_name: str) -> Optional[ModuleMetadata]:
        """Gets the latest registered version of a module based on semantic versioning.

        Args:
            module_name (str): The name of the module.

        Returns:
            Optional[ModuleMetadata]: The ModuleMetadata for the latest version, or None if no versions are registered or versions are unparseable.
        """
        with self._lock:
            if module_name not in self._modules or not self._modules[module_name]:
                self.logger.warning(f"No versions found for module '{module_name}'.")
                return None
            
            versions_dict = self._modules[module_name]
            latest_version_obj = None
            latest_version_str = None

            for v_str in versions_dict.keys():
                try:
                    current_v_obj = parse_version(v_str)
                    if latest_version_obj is None or current_v_obj > latest_version_obj:
                        latest_version_obj = current_v_obj
                        latest_version_str = v_str
                except Exception as e: # Handles InvalidVersion from packaging.version.parse
                    self.logger.warning(f"Could not parse version '{v_str}' for module '{module_name}'. Skipping for latest check. Error: {e}")
            
            if latest_version_str:
                return versions_dict[latest_version_str]
            else:
                self.logger.warning(f"Could not determine latest version for module '{module_name}' (possibly all versions unparseable).")
                return None
        
    def get_default_module_key(self) -> Optional[Tuple[str, str]]:
        """Get the key (name, version) of the default module.
        
        Returns:
            Optional[Tuple[str, str]]: The (name, version) of the default module, or None if no default set.
        """
        # No lock needed for reading a single atomic variable if writes are locked, but use for consistency or if it becomes complex.
        # Python attribute access is generally atomic.
        # For simplicity and future-proofing if this becomes more complex: with self._lock:
        return self._default_module_key

    def get_default_module(self) -> Optional[ModuleMetadata]:
        """Gets the ModuleMetadata for the default module.

        Returns:
            Optional[ModuleMetadata]: The metadata of the default module, or None if no default is set or it cannot be found.
        """
        default_key = self.get_default_module_key() # Uses its own lock if necessary
        if default_key:
            module_name, version = default_key
            # Use get_module which is already locked
            return self.get_module(module_name, version)
        return None

    def set_default_module(self, module_name: str, version: str):
        """Set the default module by its name and version.

        Args:
            module_name (str): The name of the module to set as default.
            version (str): The version of the module to set as default.

        Raises:
            ValueError: If the module name or version is not registered.
        """
        with self._lock:
            if module_name not in self._modules or version not in self._modules[module_name]:
                raise ValueError(f"Module '{module_name}' version '{version}' not found in registry. Cannot set as default.")
            self._default_module_key = (module_name, version)
            self.logger.info(f"Module '{module_name}' version '{version}' set as default.")

    # --- New method to get richer component details ---
    def get_all_component_details(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns detailed information for all registered module versions, including reversibility support."""
        details_map: Dict[str, List[Dict[str, Any]]] = {}
        with self._lock:
            for module_name, versions_dict in self._modules.items():
                version_details_list = []
                for version_str, module_meta in versions_dict.items():
                    details = {
                        "module_name": module_meta.module_name,
                        "version": module_meta.version,
                        "description": module_meta.description,
                        "entry_point": module_meta.entry_point,
                        "supports_reversibility": module_meta.supports_reversibility,
                        "author": module_meta.author,
                        "source_file_path": str(module_meta.source_file_path), # Convert Path to str
                        "dependencies": [
                            {"name": dep.name, "version_specifier": dep.version_specifier}
                            for dep in module_meta.dependencies
                        ],
                        # Placeholder for performance data - to be integrated later
                        "performance_metrics": self.get_component_performance(module_name, version_str) or {}
                    }
                    version_details_list.append(details)
                if version_details_list: # Only add if there are versions
                    details_map[module_name] = version_details_list
        return details_map

    # --- Methods related to performance (may need adjustment for ModuleMetadata) ---
    def get_component_performance(self, module_name: str, version: str) -> Optional[Dict[str, float]]:
        # Implementation of get_component_performance method
        # This is a placeholder and should be replaced with the actual implementation
        return None

    # --- Old methods removed below --- #
    # The following methods were part of the original ComponentRegistry focused on Callables
    # and have been superseded by the module-centric methods above. They are removed for clarity.

    # def list_components(self) -> Dict[str, Callable]: (Removed)

    # def get_component_names(self) -> List[str]: (Removed)

    # def get_component(self, key: str) -> Optional[Callable]: (Removed)

    # def set_default_component(self, key: str): (Removed - old signature)