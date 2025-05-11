# src/core/module_orchestrator.py
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Any

# Assuming components are importable from siblings
try:
    from .discovery import ModuleDiscoveryService, ModuleMetadata
    from .dependency_resolver import DependencyResolver, DependencyResolutionError
    from .module_loader import ModuleLoader, ModuleLoadError
except ImportError:
    # Fallback for potential execution context issues (e.g., running tests directly)
    from discovery import ModuleDiscoveryService, ModuleMetadata
    from dependency_resolver import DependencyResolver, DependencyResolutionError
    from module_loader import ModuleLoader, ModuleLoadError

logger = logging.getLogger(__name__)

class ModuleOrchestrator:
    """Coordinates the discovery, resolution, and loading of dynamic modules."""

    def __init__(
        self,
        discovery_service: ModuleDiscoveryService,
        resolver: DependencyResolver,
        loader: ModuleLoader
    ):
        self._discovery_service = discovery_service
        self._resolver = resolver
        self._loader = loader

    def load_discovered_modules(self, discovery_root_path: Path) -> Dict[Tuple[str, str], Any]:
        """
        Discovers, resolves, and loads modules found within the discovery path.

        Args:
            discovery_root_path: The root directory to search for module metadata files.

        Returns:
            A dictionary mapping (module_name, version) tuple to the loaded module object
            for all successfully loaded modules.
            Returns an empty dictionary if no modules are found or loaded successfully.
        """
        loaded_modules: Dict[Tuple[str, str], Any] = {}

        # 1. Discover Modules
        logger.info(f"Starting module discovery in: {discovery_root_path}")
        try:
            discovered_meta_list: List[ModuleMetadata] = self._discovery_service.discover_modules(discovery_root_path)
            if not discovered_meta_list:
                logger.info("No module metadata files found.")
                return {}
            logger.info(f"Discovered {len(discovered_meta_list)} module metadata entries.")
        except Exception as e:
            logger.exception(f"Error during module discovery in {discovery_root_path}: {e}")
            return {} # Halt on discovery error

        # 2. Organize Metadata for Resolver
        available_modules_for_resolver: Dict[str, Dict[str, ModuleMetadata]] = {}
        for meta in discovered_meta_list:
            if meta.module_name not in available_modules_for_resolver:
                available_modules_for_resolver[meta.module_name] = {}
            available_modules_for_resolver[meta.module_name][meta.version] = meta
        
        # 3. Resolve Dependencies
        logger.info("Resolving module dependencies...")
        try:
            resolved_load_order: List[ModuleMetadata] = self._resolver.resolve(available_modules_for_resolver)
            logger.info(f"Dependency resolution successful. Load order determined for {len(resolved_load_order)} modules.")
        except DependencyResolutionError as e:
            logger.error(f"Failed to resolve module dependencies: {e}")
            # Depending on requirements, we might want to load modules that *could* be resolved
            # before the error occurred, but for now, halt on resolution errors.
            return {} 
        except Exception as e:
            logger.exception(f"An unexpected error occurred during dependency resolution: {e}")
            return {} # Halt on unexpected error

        # 4. Load Modules in Order
        logger.info("Loading modules in resolved order...")
        modules_loaded_count = 0
        for meta_to_load in resolved_load_order:
            module_id = (meta_to_load.module_name, meta_to_load.version)
            try:
                loaded_module_obj = self._loader.load_module(meta_to_load)
                loaded_modules[module_id] = loaded_module_obj
                modules_loaded_count += 1
                # Optionally: Notify registry or perform other actions with loaded_module_obj
            except ModuleLoadError as e:
                logger.error(f"Failed to load module {module_id[0]} v{module_id[1]}: {e}")
                # Decide whether to continue loading others or halt.
                # Let's continue loading other modules for robustness.
                continue 
            except Exception as e:
                logger.exception(f"An unexpected error occurred loading module {module_id[0]} v{module_id[1]}: {e}")
                continue # Also continue on unexpected errors?

        logger.info(f"Module loading complete. Successfully loaded {modules_loaded_count} out of {len(resolved_load_order)} resolved modules.")
        return loaded_modules 