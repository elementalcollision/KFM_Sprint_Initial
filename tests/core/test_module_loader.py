# tests/core/test_module_loader.py
import pytest
import sys
import os
from pathlib import Path
from types import ModuleType

# Ensure src directory is in path for testing
# Adjust the path depth as necessary based on test execution context
TEST_DIR = Path(__file__).parent
SRC_DIR = TEST_DIR.parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# Create dummy fixture directories if they don't exist
FIXTURES_DIR = TEST_DIR.parent / "fixtures" / "loadable_modules"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
(FIXTURES_DIR / "__init__.py").touch(exist_ok=True)

# Create a dummy valid module
VALID_MODULE_PATH = FIXTURES_DIR / "valid_module.py"
VALID_MODULE_CONTENT = """
VALUE = 123
def main():
    return 'Hello from valid_module'
"""
VALID_MODULE_PATH.write_text(VALID_MODULE_CONTENT)

# Create a dummy module with an import error
IMPORT_ERROR_MODULE_PATH = FIXTURES_DIR / "import_error_module.py"
IMPORT_ERROR_MODULE_CONTENT = """
import non_existent_library
VALUE = 456
"""
IMPORT_ERROR_MODULE_PATH.write_text(IMPORT_ERROR_MODULE_CONTENT)

# Create a dummy module with syntax error
SYNTAX_ERROR_MODULE_PATH = FIXTURES_DIR / "syntax_error_module.py"
SYNTAX_ERROR_MODULE_CONTENT = """
VALUE = 789
def func(
""" # Missing closing parenthesis
SYNTAX_ERROR_MODULE_PATH.write_text(SYNTAX_ERROR_MODULE_CONTENT)

# Add fixtures directory to sys.path *for the test run* if needed for importlib
# Note: Modifying sys.path directly in tests can sometimes be fragile.
# Consider using pytest fixtures (`monkeypatch`) if issues arise.
LOADABLE_MODULES_PARENT = str(FIXTURES_DIR.parent)
if LOADABLE_MODULES_PARENT not in sys.path:
    sys.path.insert(0, LOADABLE_MODULES_PARENT)

# Now import the necessary classes from the module under test
from core.module_loader import ModuleLoader, ModuleLoadError
from core.discovery import ModuleMetadata # Assuming discovery provides this


# Helper to create metadata for tests
def create_loader_meta(name, version, entry_point):
    return ModuleMetadata(
        module_name=name,
        version=version,
        entry_point=entry_point,
        source_file_path=Path(f"/fake/{name}.yaml"), # Path doesn't matter for loading
        cached_at_mtime=0 # mtime doesn't matter for loading
    )

@pytest.fixture
def loader():
    """Provides a ModuleLoader instance."""
    return ModuleLoader()


class TestModuleLoader:

    def test_load_successful(self, loader: ModuleLoader):
        """Test loading a valid module."""
        meta = create_loader_meta("ValidModule", "1.0", "loadable_modules.valid_module")
        loaded_module = loader.load_module(meta)
        
        assert isinstance(loaded_module, ModuleType)
        assert hasattr(loaded_module, "VALUE")
        assert loaded_module.VALUE == 123
        assert hasattr(loaded_module, "main")
        assert loaded_module.main() == 'Hello from valid_module'

    def test_load_module_not_found(self, loader: ModuleLoader):
        """Test loading a module that doesn't exist."""
        meta = create_loader_meta("NotFound", "1.0", "loadable_modules.non_existent_module")
        with pytest.raises(ModuleLoadError) as excinfo:
            loader.load_module(meta)
        
        assert excinfo.value.module_name == "NotFound"
        assert excinfo.value.entry_point == "loadable_modules.non_existent_module"
        assert isinstance(excinfo.value.original_exception, ModuleNotFoundError)

    def test_load_module_import_error_inside(self, loader: ModuleLoader):
        """Test loading a module that raises ImportError internally."""
        meta = create_loader_meta("ImportErr", "1.0", "loadable_modules.import_error_module")
        with pytest.raises(ModuleLoadError) as excinfo:
            loader.load_module(meta)
        
        assert excinfo.value.module_name == "ImportErr"
        assert excinfo.value.entry_point == "loadable_modules.import_error_module"
        # The original exception raised by importlib when the module itself fails to import
        assert isinstance(excinfo.value.original_exception, ImportError) 
        assert "non_existent_library" in str(excinfo.value.original_exception)

    def test_load_module_syntax_error_inside(self, loader: ModuleLoader):
        """Test loading a module that has a SyntaxError."""
        # NOTE: SyntaxErrors during import are often caught earlier by Python's import mechanism
        # and might raise SyntaxError directly, or ModuleNotFoundError if the file cannot be parsed at all.
        # importlib.import_module behavior might vary slightly.
        meta = create_loader_meta("SyntaxErr", "1.0", "loadable_modules.syntax_error_module")
        with pytest.raises(ModuleLoadError) as excinfo:
            loader.load_module(meta)
        
        assert excinfo.value.module_name == "SyntaxErr"
        assert excinfo.value.entry_point == "loadable_modules.syntax_error_module"
        assert isinstance(excinfo.value.original_exception, SyntaxError)

    def test_load_module_no_entry_point(self, loader: ModuleLoader):
        """Test loading a module where metadata lacks an entry point."""
        meta = create_loader_meta("NoEntry", "1.0", None) # Entry point is None or empty
        with pytest.raises(ModuleLoadError) as excinfo:
            loader.load_module(meta)
        
        assert excinfo.value.module_name == "NoEntry"
        assert isinstance(excinfo.value.original_exception, ValueError)
        assert "Entry point not specified" in str(excinfo.value.original_exception) 