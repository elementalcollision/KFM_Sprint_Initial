import pytest
import yaml
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from typing import Any

from src.core.discovery import (
    ModuleDiscoveryService,
    ModuleMetadata,
    ModuleDependency,
    YAMLParseError,
    MetadataValidationError,
    ModuleDiscoveryError
)

VALID_MODULE_CONTENT = {
    "module_name": "TestModule1",
    "version": "1.0.0",
    "entry_point": "test_module1.main.TestModule1Class",
    "description": "A test module.",
    "author": "Test Author",
    "dependencies": [
        {"name": "CoreDep", "version_specifier": ">=1.0"},
        {"name": "AnotherDep", "version_specifier": "==0.5"}
    ]
}

VALID_MODULE_MINIMAL_CONTENT = {
    "module_name": "MinimalModule",
    "version": "0.1.0",
    "entry_point": "minimal_module.entry"
}

MALFORMED_YAML_CONTENT = """
module_name: MalformedModule
version: 1.0.0
entry_point: malformed.entry
  description: This YAML is malformed due to indentation
"""

INVALID_METADATA_MISSING_NAME_CONTENT = {
    "version": "1.0.0",
    "entry_point": "invalid.module.entry"
}

INVALID_METADATA_WRONG_TYPE_CONTENT = {
    "module_name": "WrongTypeModule",
    "version": 123, # Should be string
    "entry_point": "wrong.type.module.entry"
}


@pytest.fixture
def discovery_service():
    """Returns a new instance of ModuleDiscoveryService for each test."""
    return ModuleDiscoveryService()

@pytest.fixture
def temp_plugin_dir():
    """Creates a temporary directory for plugin YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def create_module_file(dir_path: Path, filename: str, content: Any):
    file_path = dir_path / filename
    with open(file_path, 'w') as f:
        if isinstance(content, str): # For malformed YAML
            f.write(content)
        else:
            yaml.dump(content, f)
    return file_path

class TestModuleDiscoveryService:

    def test_discover_single_valid_module(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        module_file = create_module_file(temp_plugin_dir, "valid1.module.yaml", VALID_MODULE_CONTENT)
        
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        
        assert len(discovered) == 1
        assert "TestModule1" in discovered
        metadata = discovered["TestModule1"]
        
        assert metadata.module_name == "TestModule1"
        assert metadata.version == "1.0.0"
        assert metadata.entry_point == "test_module1.main.TestModule1Class"
        assert metadata.description == "A test module."
        assert metadata.author == "Test Author"
        assert metadata.source_file_path == module_file.resolve()
        assert len(metadata.dependencies) == 2
        assert ModuleDependency(name="CoreDep", version_specifier=">=1.0") in metadata.dependencies
        assert ModuleDependency(name="AnotherDep", version_specifier="==0.5") in metadata.dependencies

    def test_discover_minimal_valid_module(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        module_file = create_module_file(temp_plugin_dir, "minimal.module.yaml", VALID_MODULE_MINIMAL_CONTENT)
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        
        assert len(discovered) == 1
        assert "MinimalModule" in discovered
        metadata = discovered["MinimalModule"]
        
        assert metadata.module_name == "MinimalModule"
        assert metadata.version == "0.1.0"
        assert metadata.entry_point == "minimal_module.entry"
        assert metadata.description is None
        assert metadata.author is None
        assert metadata.source_file_path == module_file.resolve()
        assert len(metadata.dependencies) == 0

    def test_discover_no_modules_in_empty_directory(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0

    def test_discover_no_module_yaml_files(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        (temp_plugin_dir / "some_other_file.txt").write_text("hello")
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0

    def test_handle_non_existent_directory(self, discovery_service: ModuleDiscoveryService, capsys):
        non_existent_dir = str(Path(tempfile.gettempdir()) / "non_existent_plugin_dir_12345")
        discovered = discovery_service.discover_modules([non_existent_dir])
        assert len(discovered) == 0
        captured = capsys.readouterr()
        assert f"Warning: Directory not found or not a directory: {non_existent_dir}" in captured.out


    def test_yaml_parse_error_malformed_yaml(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        create_module_file(temp_plugin_dir, "malformed.module.yaml", MALFORMED_YAML_CONTENT)
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0 # Should not add malformed modules
        captured = capsys.readouterr()
        assert "Error discovering module from file" in captured.out
        assert "Error parsing YAML file" in captured.out 


    def test_metadata_validation_error_missing_required_field(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        module_file_path = create_module_file(temp_plugin_dir, "missing_name.module.yaml", INVALID_METADATA_MISSING_NAME_CONTENT)
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0
        captured = capsys.readouterr()
        assert f"Warning: 'module_name' missing, not a string, or empty in {module_file_path}. Skipping." in captured.out

    def test_metadata_validation_error_incorrect_type(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        create_module_file(temp_plugin_dir, "wrong_type.module.yaml", INVALID_METADATA_WRONG_TYPE_CONTENT)
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0
        captured = capsys.readouterr()
        assert "Error discovering module from file" in captured.out
        assert "Field 'version' must be a non-empty string" in captured.out

    def test_empty_yaml_file_is_skipped(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        module_file_path = temp_plugin_dir / "empty.module.yaml"
        module_file_path.write_text("") # Create an empty file
        
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0
        captured = capsys.readouterr()
        assert f"Warning: No data parsed from {module_file_path} or file is empty. Skipping." in captured.out
        assert f"Error parsing YAML file {module_file_path}" not in captured.out

    def test_yaml_file_not_a_map_is_handled(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        module_file_path = temp_plugin_dir / "list_top.module.yaml"
        yaml.dump(["item1", "item2"], module_file_path.open('w'))

        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 0
        captured = capsys.readouterr()
        assert f"Error discovering module from file {module_file_path}" in captured.out
        assert f"YAML content in {module_file_path} is not a dictionary (map)" in captured.out 

    def test_cache_populated_and_used(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        module_file_path = create_module_file(temp_plugin_dir, "cache_test.module.yaml", VALID_MODULE_CONTENT)

        # First discovery, should parse and cache
        discovered1 = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert "TestModule1" in discovered1
        assert discovery_service._cache["TestModule1"].source_file_path == module_file_path.resolve()

        # To prove cache is used, we can "corrupt" the file. If cache is used, old data remains.
        # If not, it would try to parse corrupted data or fail if file is removed.
        # For simplicity, let's check by patching _parse_yaml_file to see if it's called again.
        with patch.object(discovery_service, '_parse_yaml_file', wraps=discovery_service._parse_yaml_file) as mock_parse:
            discovered2 = discovery_service.discover_modules([str(temp_plugin_dir)], use_cache=True)
            assert "TestModule1" in discovered2
            assert discovered1["TestModule1"] == discovered2["TestModule1"] # Ensure same metadata
            mock_parse.assert_not_called() # Should not be called if mtime hasn't changed and using cache

    def test_cache_not_used_when_use_cache_is_false(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        create_module_file(temp_plugin_dir, "cache_test_false.module.yaml", VALID_MODULE_CONTENT)
        
        # Populate cache
        discovery_service.discover_modules([str(temp_plugin_dir)], use_cache=True)
        assert "TestModule1" in discovery_service._cache

        with patch.object(discovery_service, '_parse_yaml_file', wraps=discovery_service._parse_yaml_file) as mock_parse:
            discovery_service.discover_modules([str(temp_plugin_dir)], use_cache=False)
            # _parse_yaml_file should be called because use_cache is False
            mock_parse.assert_called() 
        
        # Cache should still contain the item as it was re-parsed and re-cached
        assert "TestModule1" in discovery_service._cache


    def test_clear_cache_empties_internal_cache(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        create_module_file(temp_plugin_dir, "cache_clear.module.yaml", VALID_MODULE_CONTENT)
        discovery_service.discover_modules([str(temp_plugin_dir)])
        assert "TestModule1" in discovery_service._cache
        
        discovery_service.clear_cache()
        assert len(discovery_service._cache) == 0

    def test_cache_invalidation_on_file_modification_time_change(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        module_file = create_module_file(temp_plugin_dir, "mod_time.module.yaml", VALID_MODULE_CONTENT)
        
        # Initial discovery
        discovery_service.discover_modules([str(temp_plugin_dir)])
        assert "TestModule1" in discovery_service._cache
        original_metadata = discovery_service._cache["TestModule1"]

        # Simulate time passing and file modification
        time.sleep(0.01) # Ensure discernible mtime change
        updated_content = {**VALID_MODULE_CONTENT, "version": "1.0.1"}
        create_module_file(temp_plugin_dir, "mod_time.module.yaml", updated_content) # Overwrite
        
        # Force Path.stat().st_mtime to return a newer time for the specific file
        # This is a bit tricky as the service itself calls stat.
        # The mtime check in discover_modules should handle this if the file's mtime actually changes.
        # The create_module_file will update the mtime.

        with patch.object(discovery_service, '_parse_yaml_file', wraps=discovery_service._parse_yaml_file) as mock_parse:
            discovered_again = discovery_service.discover_modules([str(temp_plugin_dir)], use_cache=True)
            # _parse_yaml_file should be called due to mtime change
            mock_parse.assert_called_once() 
        
        assert "TestModule1" in discovered_again
        new_metadata = discovered_again["TestModule1"]
        assert new_metadata.version == "1.0.1" # Check if it re-parsed the new version
        assert new_metadata != original_metadata

    def test_discover_multiple_valid_modules_in_one_directory(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        create_module_file(temp_plugin_dir, "multi1.module.yaml", VALID_MODULE_CONTENT)
        content2 = {**VALID_MODULE_MINIMAL_CONTENT, "module_name": "MultiModule2"}
        create_module_file(temp_plugin_dir, "multi2.module.yaml", content2)
        
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        assert len(discovered) == 2
        assert "TestModule1" in discovered
        assert "MultiModule2" in discovered
        assert discovered["TestModule1"].module_name == "TestModule1"
        assert discovered["MultiModule2"].module_name == "MultiModule2"

    def test_discover_modules_from_multiple_directories(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path):
        dir1 = temp_plugin_dir / "plugins1"
        dir2 = temp_plugin_dir / "plugins2"
        dir1.mkdir()
        dir2.mkdir()

        create_module_file(dir1, "pluginA.module.yaml", {"module_name": "PluginA", "version": "1.0", "entry_point": "a.main"})
        create_module_file(dir2, "pluginB.module.yaml", {"module_name": "PluginB", "version": "1.0", "entry_point": "b.main"})
        
        discovered = discovery_service.discover_modules([str(dir1), str(dir2)])
        assert len(discovered) == 2
        assert "PluginA" in discovered
        assert "PluginB" in discovered

    def test_discover_mixed_valid_and_invalid_modules(self, discovery_service: ModuleDiscoveryService, temp_plugin_dir: Path, capsys):
        valid_file_path = create_module_file(temp_plugin_dir, "valid_mix.module.yaml", VALID_MODULE_CONTENT)
        invalid_file_path = create_module_file(temp_plugin_dir, "invalid_mix.module.yaml", INVALID_METADATA_MISSING_NAME_CONTENT)
        content_minimal = {**VALID_MODULE_MINIMAL_CONTENT, "module_name": "MinimalMix"}
        minimal_file_path = create_module_file(temp_plugin_dir, "minimal_mix.module.yaml", content_minimal)
        
        discovered = discovery_service.discover_modules([str(temp_plugin_dir)])
        
        assert len(discovered) == 2 
        assert "TestModule1" in discovered
        assert "MinimalMix" in discovered
        assert "InvalidModule" not in discovered
        
        captured = capsys.readouterr()
        # Check for the specific warning for the invalid file with missing module_name
        assert f"Warning: 'module_name' missing, not a string, or empty in {invalid_file_path}. Skipping." in captured.out
        # Ensure that this specific invalid file did not also cause a MetadataValidationError type of message to be printed by the generic error handler
        assert f"Error discovering module from file {invalid_file_path}: Missing required field 'module_name'" not in captured.out
        # The following was removed as it's covered by the more specific warning above, and an "Error discovering..." shouldn't occur if it skips.
        # assert "Error discovering module from file" in captured.out # For the invalid one (REMOVED)
        assert f"Missing required field 'module_name' in {invalid_file_path}" not in captured.out 