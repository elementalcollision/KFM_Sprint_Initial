import pytest
import threading
import time
import logging
import io
from pathlib import Path
from unittest.mock import MagicMock, call

# Make sure src is importable (this might be needed depending on test runner setup)
# import sys
# sys.path.insert(0, Path(__file__).parent.parent.as_posix()) 

from src.core.component_registry import ComponentRegistry
from src.core.discovery import ModuleMetadata, ModuleDependency

# --- Test Data / Fixtures ---

@pytest.fixture
def registry():
    """Provides a fresh ComponentRegistry instance for each test."""
    return ComponentRegistry()

# Sample ModuleMetadata instances for testing
# Note: We use dummy Path objects; they don't need to exist for registry logic testing.
# We use time.time() for mtime initially, can be overridden in tests if needed.
DUMMY_PATH_1 = Path("/fake/path/module1.module.yaml")
DUMMY_PATH_2 = Path("/fake/path/module1_new.module.yaml")
DUMMY_PATH_3 = Path("/fake/path/module2.module.yaml")

META_MOD1_V1 = ModuleMetadata(
    module_name="Module1", version="1.0.0", entry_point="mod1.v1.main",
    source_file_path=DUMMY_PATH_1, cached_at_mtime=time.time(), 
    description="Mod1 V1 Desc", author="Auth1", dependencies=[ModuleDependency("Core", ">=1.0")]
)
META_MOD1_V2 = ModuleMetadata(
    module_name="Module1", version="1.2.0", entry_point="mod1.v2.main",
    source_file_path=DUMMY_PATH_2, cached_at_mtime=time.time() + 1, 
    description="Mod1 V2 Desc"
)
META_MOD1_V0_9 = ModuleMetadata(
    module_name="Module1", version="0.9.0", entry_point="mod1.v09.main",
    source_file_path=DUMMY_PATH_1, cached_at_mtime=time.time() -1
)
META_MOD2_V1 = ModuleMetadata(
    module_name="Module2", version="1.0.0", entry_point="mod2.v1.main",
    source_file_path=DUMMY_PATH_3, cached_at_mtime=time.time()
)
META_MOD_INVALID_VER = ModuleMetadata(
    module_name="InvalidVer", version="NotAVersion", entry_point="invalid.ver.main",
    source_file_path=DUMMY_PATH_1, cached_at_mtime=time.time()
)


# --- Test Class ---

class TestComponentRegistryRefactored:

    def test_register_single_module(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        modules = registry.list_modules()
        assert "Module1" in modules
        assert "1.0.0" in modules["Module1"]
        assert modules["Module1"]["1.0.0"] == META_MOD1_V1

    def test_register_multiple_versions(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        registry.register_module(META_MOD1_V0_9)
        
        versions = registry.get_module_versions("Module1")
        assert versions is not None
        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "1.2.0" in versions
        assert "0.9.0" in versions
        assert versions["1.2.0"] == META_MOD1_V2

    def test_register_overwrite_warning(self, registry: ComponentRegistry):
        # Setup custom handler for this test
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING) 
        # Optional: Add a formatter if needed
        # test_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s')) 

        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        # Ensure the logger level itself is low enough
        registry.logger.setLevel(logging.WARNING) 

        try:
            registry.register_module(META_MOD1_V1)
            # Register same name/version again
            registry.register_module(META_MOD1_V1)
            
            log_output = log_stream.getvalue()
            assert "Module 'Module1' version '1.0.0' already registered. Overwriting." in log_output
        finally:
            # Clean up: remove handler and reset level
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level) # Reset to original level

    def test_register_invalid_type(self, registry: ComponentRegistry):
        with pytest.raises(TypeError, match="module_meta must be an instance of ModuleMetadata"):
            registry.register_module("not_metadata") # type: ignore

    def test_deregister_specific_version(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        assert registry.deregister_module("Module1", "1.0.0") is True
        
        versions = registry.get_module_versions("Module1")
        assert versions is not None
        assert "1.0.0" not in versions
        assert "1.2.0" in versions
        assert len(versions) == 1

    def test_deregister_last_version_removes_module_entry(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        assert registry.deregister_module("Module1", "1.0.0") is True
        assert "Module1" not in registry.list_modules() # Top level key should be gone

    def test_deregister_all_versions(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        assert registry.deregister_module("Module1") is True # Version is None
        
        assert "Module1" not in registry.list_modules()
        assert registry.get_module_versions("Module1") is None

    def test_deregister_nonexistent_version(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING)
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.WARNING)
        
        try:
            registry.register_module(META_MOD1_V1)
            assert registry.deregister_module("Module1", "9.9.9") is False
            log_output = log_stream.getvalue()
            assert "Version '9.9.9' of module 'Module1' not found for deregistration." in log_output
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)

    def test_deregister_nonexistent_module(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING)
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.WARNING)
        
        try:
            assert registry.deregister_module("NonExistentModule") is False
            log_output = log_stream.getvalue()
            assert "Module 'NonExistentModule' not found for deregistration." in log_output
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)
    
    def test_deregister_clears_default_specific_version(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1, is_default=True)
        registry.register_module(META_MOD1_V2)
        assert registry.get_default_module_key() == ("Module1", "1.0.0")
        
        registry.deregister_module("Module1", "1.0.0")
        assert registry.get_default_module_key() is None

    def test_deregister_clears_default_all_versions(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2, is_default=True)
        assert registry.get_default_module_key() == ("Module1", "1.2.0")

        registry.deregister_module("Module1") # Deregister all
        assert registry.get_default_module_key() is None

    def test_list_modules(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD2_V1)
        modules = registry.list_modules()
        assert len(modules) == 2
        assert "Module1" in modules
        assert "Module2" in modules
        assert "1.0.0" in modules["Module1"]

    def test_get_module_names(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD2_V1)
        names = registry.get_module_names()
        assert sorted(names) == ["Module1", "Module2"]

    def test_get_module_specific_version(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        mod_v1 = registry.get_module("Module1", "1.0.0")
        mod_v2 = registry.get_module("Module1", "1.2.0")
        
        assert mod_v1 == META_MOD1_V1
        assert mod_v2 == META_MOD1_V2

    def test_get_module_not_found(self, registry: ComponentRegistry):
        assert registry.get_module("Module1", "1.0.0") is None
        registry.register_module(META_MOD1_V1)
        assert registry.get_module("Module1", "9.9.9") is None
        assert registry.get_module("NonExistent", "1.0.0") is None

    def test_get_latest_module_version_simple(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V0_9)
        registry.register_module(META_MOD1_V2)
        
        latest = registry.get_latest_module_version("Module1")
        assert latest == META_MOD1_V2

    def test_get_latest_module_version_complex_versions(self, registry: ComponentRegistry):
        # Test with pre-releases, build metadata etc.
        m1 = ModuleMetadata("Complex", "1.0.0-alpha", "e", DUMMY_PATH_1, time.time())
        m2 = ModuleMetadata("Complex", "1.0.0", "e", DUMMY_PATH_1, time.time())
        m3 = ModuleMetadata("Complex", "1.1.0-rc.1", "e", DUMMY_PATH_1, time.time())
        m4 = ModuleMetadata("Complex", "1.0.1", "e", DUMMY_PATH_1, time.time())
        m5 = ModuleMetadata("Complex", "1.1.0", "e", DUMMY_PATH_1, time.time())
        
        registry.register_module(m1)
        registry.register_module(m2)
        registry.register_module(m3)
        registry.register_module(m4)
        registry.register_module(m5)
        
        latest = registry.get_latest_module_version("Complex")
        assert latest == m5 # 1.1.0 should be latest stable

    def test_get_latest_module_no_versions(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING)
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.WARNING)

        try:
            assert registry.get_latest_module_version("Module1") is None
            log_output = log_stream.getvalue()
            assert "No versions found for module 'Module1'." in log_output
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)

    def test_get_latest_module_unparseable_version(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING)
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.WARNING)

        try:
            registry.register_module(META_MOD_INVALID_VER)
            registry.register_module(META_MOD1_V1) 
            
            latest = registry.get_latest_module_version("InvalidVer")
            assert latest is None
            
            log_output = log_stream.getvalue()
            # Check both relevant warnings are present
            assert "Could not parse version 'NotAVersion'" in log_output
            assert "Could not determine latest version for module 'InvalidVer'" in log_output
            
            # Reset stream to check logs for the next call if needed, or just check accumulated logs
            # Check that the second module still works (log stream might contain previous logs too)
            latest_mod1 = registry.get_latest_module_version("Module1")
            assert latest_mod1 == META_MOD1_V1 
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)

    def test_set_default_module(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        registry.set_default_module("Module1", "1.2.0")
        assert registry.get_default_module_key() == ("Module1", "1.2.0")
        
        default_mod = registry.get_default_module()
        assert default_mod == META_MOD1_V2

    def test_set_default_automatically_on_first_register(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1) # First one registered becomes default
        assert registry.get_default_module_key() == ("Module1", "1.0.0")
        
        registry.register_module(META_MOD2_V1) # Does not change default
        assert registry.get_default_module_key() == ("Module1", "1.0.0")

    def test_set_default_using_is_default_flag(self, registry: ComponentRegistry):
        registry.register_module(META_MOD1_V1) 
        registry.register_module(META_MOD1_V2, is_default=True) # Set V2 as default explicitly
        assert registry.get_default_module_key() == ("Module1", "1.2.0")

    def test_set_default_nonexistent(self, registry: ComponentRegistry):
        with pytest.raises(ValueError, match="Module 'Module1' version '1.0.0' not found"):
            registry.set_default_module("Module1", "1.0.0")
        
        registry.register_module(META_MOD1_V1)
        with pytest.raises(ValueError, match="Module 'Module1' version '9.9.9' not found"):
            registry.set_default_module("Module1", "9.9.9")

    def test_get_default_when_none_set(self, registry: ComponentRegistry):
        assert registry.get_default_module_key() is None
        assert registry.get_default_module() is None

    # --- Event Tests ---

    def test_subscribe_and_notify_registered(self, registry: ComponentRegistry):
        mock_listener = MagicMock()
        registry.subscribe("registered", mock_listener)
        
        registry.register_module(META_MOD1_V1)
        mock_listener.assert_called_once_with(META_MOD1_V1)
        
        mock_listener.reset_mock()
        registry.register_module(META_MOD2_V1)
        mock_listener.assert_called_once_with(META_MOD2_V1)

    def test_subscribe_and_notify_deregistered_specific(self, registry: ComponentRegistry):
        mock_listener = MagicMock()
        registry.subscribe("deregistered", mock_listener)
        
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        registry.deregister_module("Module1", "1.0.0")
        # Expects callback(module_name: str, version: Optional[str])
        mock_listener.assert_called_once_with("Module1", "1.0.0")

    def test_subscribe_and_notify_deregistered_all(self, registry: ComponentRegistry):
        mock_listener = MagicMock()
        registry.subscribe("deregistered", mock_listener)
        
        registry.register_module(META_MOD1_V1)
        registry.register_module(META_MOD1_V2)
        
        registry.deregister_module("Module1") # Deregister all versions
        # Expects callback(module_name: str, version: Optional[str]=None)
        mock_listener.assert_called_once_with("Module1", None)

    def test_subscribe_unknown_event(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.WARNING)
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.WARNING)
        
        try:
            mock_listener = MagicMock()
            mock_listener.__name__ = "mock_listener"
            registry.subscribe("unknown_event", mock_listener)
            log_output = log_stream.getvalue()
            assert "Attempted to subscribe to unknown event type: unknown_event" in log_output
            mock_listener.assert_not_called()
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)

    def test_subscribe_same_listener_multiple_times(self, registry: ComponentRegistry):
        log_stream = io.StringIO()
        test_handler = logging.StreamHandler(log_stream)
        test_handler.setLevel(logging.INFO) # Set level to INFO for this test
        original_level = registry.logger.level
        registry.logger.addHandler(test_handler)
        registry.logger.setLevel(logging.INFO) # Ensure logger processes INFO

        try:
            mock_listener = MagicMock()
            mock_listener.__name__ = "mock_listener" 
            registry.subscribe("registered", mock_listener)
            registry.subscribe("registered", mock_listener) 
            
            log_output = log_stream.getvalue()
            assert "Listener mock_listener already subscribed to event 'registered'" in log_output
            
            # Verify registration still only calls listener once
            registry.register_module(META_MOD1_V1)
            mock_listener.assert_called_once_with(META_MOD1_V1) 
        finally:
            registry.logger.removeHandler(test_handler)
            registry.logger.setLevel(original_level)
        
    # --- Thread Safety (Basic Example) ---
    
    # Note: Truly verifying thread safety often requires more complex integration/stress tests.
    # This is a basic check for obvious race conditions.
    def test_thread_safety_concurrent_register(self, registry: ComponentRegistry):
        num_threads = 10
        num_versions_per_thread = 5
        threads = []
        errors = []

        def worker(thread_id):
            try:
                for i in range(num_versions_per_thread):
                    version = f"1.{thread_id}.{i}"
                    meta = ModuleMetadata(
                        module_name=f"ThreadMod", version=version, entry_point="x",
                        source_file_path=Path(f"/fake/{thread_id}_{i}"), cached_at_mtime=time.time()
                    )
                    registry.register_module(meta)
                    # Small sleep to increase chance of interleaving
                    time.sleep(0.001) 
            except Exception as e:
                errors.append(e)

        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert not errors, f"Errors occurred during concurrent registration: {errors}"
        
        final_versions = registry.get_module_versions("ThreadMod")
        assert final_versions is not None
        # Check if the final count matches the expected number of unique versions
        assert len(final_versions) == num_threads * num_versions_per_thread 