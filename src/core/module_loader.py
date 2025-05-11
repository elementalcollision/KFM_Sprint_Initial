# src/core/module_loader.py
import importlib
import logging
from typing import Any

try:
    # Assuming ModuleMetadata is defined here or importable
    from .discovery import ModuleMetadata
except ImportError:
    from discovery import ModuleMetadata # Fallback for tests

logger = logging.getLogger(__name__)

class ModuleLoadError(Exception):
    """Custom exception for errors encountered during module loading."""
    def __init__(self, module_name: str, version: str, entry_point: str, original_exception: Exception):
        self.module_name = module_name
        self.version = version
        self.entry_point = entry_point
        self.original_exception = original_exception
        message = f"""Failed to load module '{module_name}' version '{version}' using entry point '{entry_point}'. Reason: {original_exception}"""
        super().__init__(message)


class ModuleLoader:
    """Handles the dynamic loading of resolved modules."""

    def __init__(self):
        # Potentially add ComponentRegistry or other dependencies later if needed
        pass

    def load_module(self, module_metadata: ModuleMetadata) -> Any:
        """
        Loads a module based on its metadata.

        Args:
            module_metadata: The metadata of the module to load.

        Returns:
            The loaded module object.

        Raises:
            ModuleLoadError: If the module cannot be loaded due to import errors
                             or errors during the module\'s initialization.
        """
        module_name = module_metadata.module_name
        version = module_metadata.version
        entry_point = module_metadata.entry_point # Assuming format like \'my_package.my_module\'

        if not entry_point:
            # Or raise error? Depends on requirements. For now, log and skip.
            logger.error(f"Module {module_name} v{version} has no entry point defined. Cannot load.")
            # Decide on behavior: return None? Raise specific error?
            # Let's raise for now, as loading is impossible without an entry point.
            raise ModuleLoadError(module_name, version, "", ValueError("Entry point not specified in metadata"))

        logger.info(f"Attempting to load module \'{module_name}\' v{version} from entry point \'{entry_point}\'...")
        try:
            # Use importlib.import_module to load the specified module path
            loaded_module = importlib.import_module(entry_point)
            logger.info(f"Successfully loaded module \'{module_name}\' v{version} from \'{entry_point}\'.")
            return loaded_module
        except ImportError as e:
            logger.error(f"ImportError loading {module_name} v{version} ({entry_point}): {e}")
            raise ModuleLoadError(module_name, version, entry_point, e) from e
        except Exception as e:
            # Catch other potential errors during module execution/import (e.g., SyntaxError, NameError in module)
            logger.error(f"Exception during import/loading of {module_name} v{version} ({entry_point}): {e}")
            raise ModuleLoadError(module_name, version, entry_point, e) from e 