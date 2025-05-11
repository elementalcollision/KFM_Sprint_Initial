# tests/core/test_module_orchestrator.py
import pytest
import logging
from pathlib import Path
from unittest.mock import MagicMock, call
import sys

# Ensure src directory is in path for testing
TEST_DIR = Path(__file__).parent
SRC_DIR = TEST_DIR.parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# Import necessary components
from core.discovery import ModuleDiscoveryService, ModuleMetadata, ModuleDependency
from core.dependency_resolver import DependencyResolver, DependencyResolutionError, MissingDependencyError, CircularDependencyError
from core.module_loader import ModuleLoader, ModuleLoadError
from core.module_orchestrator import ModuleOrchestrator

# Helper to create metadata for tests
def create_orch_meta(name, version, deps=None, entry_point=None):
    if deps is None: deps = []
    # Assume deps are already ModuleDependency objects if provided, or tuples
    parsed_deps = [(d if isinstance(d, tuple) else (d.name, d.version_specifier)) for d in deps]
    # Simplified creation focusing on what orchestrator might use
    return ModuleMetadata(
        module_name=name,
        version=version,
        entry_point=entry_point if entry_point else f"dummy.module.{name}.v{version}",
        source_file_path=Path(f"/fake/{name}.yaml"), 
        cached_at_mtime=0, # Not relevant for orchestration logic
        dependencies=[ModuleDependency(name=d[0], version_specifier=d[1]) for d in parsed_deps]
    )

@pytest.fixture
def mock_discovery_service():
    return MagicMock(spec=ModuleDiscoveryService)

@pytest.fixture
def mock_resolver():
    return MagicMock(spec=DependencyResolver)

@pytest.fixture
def mock_loader():
    return MagicMock(spec=ModuleLoader)

@pytest.fixture
def orchestrator(mock_discovery_service, mock_resolver, mock_loader):
    """Provides a ModuleOrchestrator instance with mocked dependencies."""
    return ModuleOrchestrator(mock_discovery_service, mock_resolver, mock_loader)


class TestModuleOrchestrator:

    def test_successful_workflow(self, orchestrator, mock_discovery_service, mock_resolver, mock_loader):
        """Test the happy path: discover, resolve, load successfully."""
        discovery_path = Path("/modules")
        meta_b = create_orch_meta("B", "1.0")
        meta_a = create_orch_meta("A", "1.0", deps=[("B", "==1.0")])
        
        mock_discovery_service.discover_modules.return_value = [meta_a, meta_b] 
        mock_resolver.resolve.return_value = [meta_b, meta_a] # Correct load order
        mock_loader.load_module.side_effect = ["loaded_module_b", "loaded_module_a"] # Dummy loaded objects
        
        result = orchestrator.load_discovered_modules(discovery_path)
        
        mock_discovery_service.discover_modules.assert_called_once_with(discovery_path)
        # Verify resolve was called with the correctly structured dict
        expected_resolver_arg = {"A": {"1.0": meta_a}, "B": {"1.0": meta_b}}
        mock_resolver.resolve.assert_called_once_with(expected_resolver_arg)
        # Verify loader was called in the correct order
        assert mock_loader.load_module.call_count == 2
        mock_loader.load_module.assert_has_calls([
            call(meta_b),
            call(meta_a)
        ])
        
        # Verify result contains the loaded modules keyed correctly
        assert result == {
            ("B", "1.0"): "loaded_module_b",
            ("A", "1.0"): "loaded_module_a"
        }

    def test_no_modules_found(self, orchestrator, mock_discovery_service):
        """Test when discovery service finds no modules."""
        discovery_path = Path("/modules")
        mock_discovery_service.discover_modules.return_value = []
        
        result = orchestrator.load_discovered_modules(discovery_path)
        
        mock_discovery_service.discover_modules.assert_called_once_with(discovery_path)
        assert result == {}

    def test_discovery_error(self, orchestrator, mock_discovery_service, caplog):
        """Test when discovery service raises an exception."""
        discovery_path = Path("/modules")
        mock_discovery_service.discover_modules.side_effect = OSError("Disk read error")
        caplog.set_level(logging.ERROR)

        result = orchestrator.load_discovered_modules(discovery_path)
        
        mock_discovery_service.discover_modules.assert_called_once_with(discovery_path)
        assert result == {}
        assert "Error during module discovery" in caplog.text
        assert "Disk read error" in caplog.text

    def test_resolution_error(self, orchestrator, mock_discovery_service, mock_resolver, caplog):
        """Test when resolver raises a DependencyResolutionError."""
        discovery_path = Path("/modules")
        meta_b = create_orch_meta("B", "1.0", deps=[("A", "==1.0")]) # Cycle A->B, B->A
        meta_a = create_orch_meta("A", "1.0", deps=[("B", "==1.0")])
        
        mock_discovery_service.discover_modules.return_value = [meta_a, meta_b]
        error_instance = CircularDependencyError([('A', '1.0'), ('B', '1.0'), ('A', '1.0')])
        mock_resolver.resolve.side_effect = error_instance
        caplog.set_level(logging.ERROR)

        result = orchestrator.load_discovered_modules(discovery_path)
        
        expected_resolver_arg = {"A": {"1.0": meta_a}, "B": {"1.0": meta_b}}
        mock_resolver.resolve.assert_called_once_with(expected_resolver_arg)
        assert result == {}
        assert "Failed to resolve module dependencies" in caplog.text
        assert "Circular dependency detected" in caplog.text 

    def test_loading_error_continues(self, orchestrator, mock_discovery_service, mock_resolver, mock_loader, caplog):
        """Test that loading continues for other modules if one fails."""
        discovery_path = Path("/modules")
        meta_b = create_orch_meta("B", "1.0") # Fails to load
        meta_a = create_orch_meta("A", "1.0") # Loads successfully
        
        mock_discovery_service.discover_modules.return_value = [meta_a, meta_b]
        mock_resolver.resolve.return_value = [meta_b, meta_a] # Load B first, then A
        
        error_instance = ModuleLoadError("B", "1.0", "entry.b", ImportError("Cannot import B"))
        mock_loader.load_module.side_effect = [error_instance, "loaded_module_a"]
        caplog.set_level(logging.ERROR)

        result = orchestrator.load_discovered_modules(discovery_path)
        
        # Verify loader was called for both
        assert mock_loader.load_module.call_count == 2
        mock_loader.load_module.assert_has_calls([
            call(meta_b), # Failed call
            call(meta_a)  # Successful call
        ])
        
        # Verify error logged
        assert "Failed to load module B v1.0" in caplog.text
        assert "Cannot import B" in caplog.text
        
        # Verify result contains only the successfully loaded module
        assert result == {
            ("A", "1.0"): "loaded_module_a"
        } 