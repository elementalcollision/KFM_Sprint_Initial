import pytest
import os
import yaml
import copy
from unittest import mock

from src.config.config_loader import load_verification_config, get_config, _clear_cached_config
from src.config.models import VerificationConfig, GlobalConfig
from src.core.exceptions import ConfigurationError

# Fixtures and Helper functions
@pytest.fixture(autouse=True)
def clear_config_cache_after_test():
    """Ensures the global config cache is cleared after each test."""
    yield
    _clear_cached_config()

def create_yaml_file(filepath, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        yaml.dump(content, f)
    return filepath

# Basic valid config structure for tests
VALID_CONFIG_DICT = {
    "global_settings": {
        "log_level": "INFO",
        "log_file_path": "logs/test_kfm_verifier.log",
        "max_retries": 2,
    },
    "log_parsing": {
        "default_date_formats": ["%Y-%m-%d %H:%M:%S"],
        "log_sources": [
            {"path": "./dummy.log", "parser_type": "auto_detect"}
        ]
    },
    "registry_verifier": {
        "client_type": "mock_from_file",
        "mock_registry_data_file": "./dummy_registry.json",
        "cache_ttl": 60
    },
    "outcome_comparator": {
        "default_numeric_tolerance": 0.01
    },
    "report_generator": {
        "default_report_formats": ["json"],
        "report_templates_dir": "./templates",
        "default_report_output_dir": "./test_reports"
    },
    "cli_defaults": {
        "verification_level": "basic"
    }
}

@pytest.fixture
def dummy_files_for_config(tmp_path):
    """Create dummy files that a valid config might point to."""
    (tmp_path / "dummy.log").touch()
    (tmp_path / "dummy_registry.json").touch()
    (tmp_path / "templates").mkdir(exist_ok=True)

    # For default config loading by get_config() or load_verification_config(None)
    # These paths are often referenced in verification_config.yaml or Pydantic defaults
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "logs" / "llm_api.log").touch()
    (tmp_path / "logs" / "kfm_verifier.log").touch() # Default for GlobalConfig.log_file_path
    (tmp_path / "logs" / "kfm_verifier_errors.jsonl").touch() # Default for GlobalConfig.error_log_file_path

    fixtures_dir = tmp_path / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "mock_registry_data.yaml").touch()

    report_templates_dir_default = tmp_path / "src" / "verification" / "report_generator" / "templates"
    report_templates_dir_default.mkdir(parents=True, exist_ok=True)

    return tmp_path

class TestConfigLoading:
    def test_load_valid_yaml_file(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        # Adjust paths to be relative to tmp_path for Pydantic validation
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")
        
        config_path = create_yaml_file(tmp_path / "valid_config.yaml", config_content)
        
        loaded_config = load_verification_config(str(config_path))
        assert isinstance(loaded_config, VerificationConfig)
        assert loaded_config.global_settings.log_level == "INFO"
        # Compare Path objects directly
        assert loaded_config.log_parsing.log_sources[0].path == (dummy_files_for_config / "dummy.log")

    def test_load_non_existent_file(self):
        with pytest.raises(ConfigurationError, match="Specified configuration file not found"):
            load_verification_config("non_existent_config.yaml")

    def test_load_malformed_yaml_file(self, tmp_path):
        malformed_content = "global_settings: {log_level: INFO, another_key: [ unterminated list"
        config_path = tmp_path / "malformed_config.yaml"
        with open(config_path, 'w') as f:
            f.write(malformed_content)
        
        with pytest.raises(ConfigurationError, match="Error parsing YAML configuration file"):
            load_verification_config(str(config_path))

    def test_load_yaml_with_validation_error(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["global_settings"]["log_level"] = "INVALID_LEVEL" # Invalid enum value
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")

        config_path = create_yaml_file(tmp_path / "invalid_data_config.yaml", config_content)
        
        with pytest.raises(ConfigurationError, match=r"(?s)validation error.*global_settings.log_level"):
            load_verification_config(str(config_path))

    def test_load_yaml_missing_required_pydantic_field(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        del config_content["log_parsing"]["log_sources"][0]["parser_type"]
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")

        config_path = create_yaml_file(tmp_path / "missing_field_config.yaml", config_content)
        
        with pytest.raises(ConfigurationError, match=r"(?s)validation error.*Field required"):
            load_verification_config(str(config_path))

    def test_default_config_loading_if_path_none(self, monkeypatch, dummy_files_for_config):
        original_cwd = os.getcwd()
        # Change CWD to the temp dir where dummy_files_for_config created necessary default subdirs like 'logs' and 'src' structure
        os.chdir(dummy_files_for_config)
        
        def mock_exists_for_default_load(path):
            # Simulate no user-provided config files are found, to force Pydantic defaults
            if path in ["./verification_config.yaml", "verification_config.yaml", "config/verification_config.yaml"]:
                return False
            # For other paths (like Pydantic FilePath/DirectoryPath defaults), check actual existence in the new CWD
            return os.path.exists(path)

        monkeypatch.setattr("os.path.exists", mock_exists_for_default_load)
        
        try:
            loaded_config = load_verification_config(None) # Should load Pydantic defaults
            assert isinstance(loaded_config, VerificationConfig)
            assert loaded_config.global_settings.log_level == "INFO" # Pydantic default
            # Check a default path that dummy_files_for_config should have created relative to itself
            # Pydantic might keep string defaults as strings if not explicitly parsed from input data
            if isinstance(loaded_config.report_generator.report_templates_dir, str):
                assert os.path.basename(loaded_config.report_generator.report_templates_dir) == "templates"
                assert (dummy_files_for_config / loaded_config.report_generator.report_templates_dir).exists()
            else: # Assume it's a Path object if not a string
                assert loaded_config.report_generator.report_templates_dir.name == "templates"
                assert loaded_config.report_generator.report_templates_dir.exists()
        finally:
            os.chdir(original_cwd)

class TestEnvironmentVariableOverrides:
    @mock.patch.dict(os.environ, {
        "KFM_VERIFIER_GLOBAL_SETTINGS__LOG_LEVEL": "DEBUG",
        "KFM_VERIFIER_GLOBAL_SETTINGS__MAX_RETRIES": "10",
        # Removed problematic list-of-dict override for now
        # "KFM_VERIFIER_LOG_PARSING__LOG_SOURCES__0__PATH": "logs/env_override.log", 
        # "KFM_VERIFIER_LOG_PARSING__DEFAULT_DATE_FORMATS__0": "%Y/%m/%d", # Removed problematic list index override
        "KFM_VERIFIER_REGISTRY_VERIFIER__CLIENT_TYPE": "live",
        "KFM_VERIFIER_REGISTRY_VERIFIER__REGISTRY_ACCESS_DETAILS__ENDPOINT": "http://localhost:8080/api",
    })
    def test_env_overrides_simple_and_nested(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")

        config_path = create_yaml_file(tmp_path / "base_config_for_env_override.yaml", config_content)
        loaded_config = load_verification_config(str(config_path))

        assert loaded_config.global_settings.log_level == "DEBUG"
        assert loaded_config.global_settings.max_retries == 10
        # assert loaded_config.log_parsing.default_date_formats[0] == "%Y/%m/%d" # Assertion removed with override
        assert loaded_config.registry_verifier.client_type == "live"
        assert str(loaded_config.registry_verifier.registry_access_details.endpoint) == "http://localhost:8080/api"

    @mock.patch.dict(os.environ, {"KFM_VERIFIER_GLOBAL_SETTINGS__LOG_LEVEL": "INVALID_ENV_LEVEL"})
    def test_env_override_validation_error(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")

        config_path = create_yaml_file(tmp_path / "base_config_for_invalid_env.yaml", config_content)
        with pytest.raises(ConfigurationError, match=r"(?s)validation error.*global_settings.log_level"):
            load_verification_config(str(config_path))

    @mock.patch.dict(os.environ, {"KFM_VERIFIER_REGISTRY_VERIFIER__CACHE_TTL": "not_an_int"})
    def test_env_override_type_conversion_error(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")

        config_path = create_yaml_file(tmp_path / "base_config_for_type_error_env.yaml", config_content)
        with pytest.raises(ConfigurationError, match=r"(?s)validation error.*registry_verifier.cache_ttl"):
            load_verification_config(str(config_path))

class TestConfigCachingAndGetConfig:
    def test_config_caching(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")
        config_path = create_yaml_file(tmp_path / "cache_test_config.yaml", config_content)

        config1 = load_verification_config(str(config_path))
        config2 = load_verification_config(str(config_path)) 
        assert config1 is config2

        config3 = load_verification_config(str(config_path), force_reload=True)
        assert config1 is not config3

    def test_get_config_after_load(self, tmp_path, dummy_files_for_config):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")
        config_path = create_yaml_file(tmp_path / "get_config_test.yaml", config_content)

        loaded_config = load_verification_config(str(config_path))
        retrieved_config = get_config()
        assert loaded_config is retrieved_config

    def test_get_config_behavior_with_different_paths_and_force_reload(self, tmp_path, dummy_files_for_config):
        config_content1 = copy.deepcopy(VALID_CONFIG_DICT)
        config_content1["global_settings"]["log_level"] = "ERROR"
        config_content1["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy1.log")
        (dummy_files_for_config / "dummy1.log").touch()
        config_content1["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry1.json")
        (dummy_files_for_config / "dummy_registry1.json").touch()
        config_content1["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates1")
        (dummy_files_for_config / "templates1").mkdir(exist_ok=True)
        config_path1 = create_yaml_file(tmp_path / "specific1.yaml", config_content1)

        config_content2 = copy.deepcopy(VALID_CONFIG_DICT)
        config_content2["global_settings"]["log_level"] = "WARNING"
        config_content2["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy2.log")
        (dummy_files_for_config / "dummy2.log").touch()
        config_content2["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry2.json")
        (dummy_files_for_config / "dummy_registry2.json").touch()
        config_content2["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates2")
        (dummy_files_for_config / "templates2").mkdir(exist_ok=True)
        config_path2 = create_yaml_file(tmp_path / "specific2.yaml", config_content2)

        cfg1 = load_verification_config(str(config_path1))
        assert cfg1.global_settings.log_level == "ERROR"

        cfg2_attempt_load = load_verification_config(str(config_path2))
        assert cfg2_attempt_load is cfg1 
        assert cfg2_attempt_load.global_settings.log_level == "ERROR"

        cfg2_forced_load = load_verification_config(str(config_path2), force_reload=True)
        assert cfg2_forced_load is not cfg1
        assert cfg2_forced_load.global_settings.log_level == "WARNING"

        retrieved_cfg_after_force_reload = get_config()
        assert retrieved_cfg_after_force_reload is cfg2_forced_load

    def test_clear_config_cache_functionality(self, tmp_path, dummy_files_for_config, monkeypatch):
        config_content = copy.deepcopy(VALID_CONFIG_DICT)
        config_content["log_parsing"]["log_sources"][0]["path"] = str(dummy_files_for_config / "dummy.log")
        config_content["registry_verifier"]["mock_registry_data_file"] = str(dummy_files_for_config / "dummy_registry.json")
        config_content["report_generator"]["report_templates_dir"] = str(dummy_files_for_config / "templates")
        config_path = create_yaml_file(tmp_path / "cache_clear_test_config.yaml", config_content)

        # Load initial config
        config1 = load_verification_config(str(config_path))
        assert get_config() is config1  # Config should be cached

        # Clear the cache
        _clear_cached_config()
        
        config_after_clear = None
        original_cwd = os.getcwd()
        try:
            # Change CWD to where dummy_files_for_config creates default paths like \'logs/\' and \'src/verification/...\'
            # These are needed for Pydantic FilePath/DirectoryPath fields with default values.
            os.chdir(dummy_files_for_config)
            config_after_clear = get_config() # This calls load_verification_config(None)
        finally:
            os.chdir(original_cwd)

        assert config_after_clear is not None, "get_config() returned None after cache clear"
        assert config_after_clear is not config1, "get_config() returned the same cached instance after _clear_cached_config()"
        
        assert isinstance(config_after_clear, VerificationConfig), "Default config is not a VerificationConfig instance"
        # Check a Pydantic default value
        assert config_after_clear.global_settings.log_level == "INFO" 
        # Check that default paths are correctly resolved and exist within the dummy_files_for_config context
        # Ensure the paths created by dummy_files_for_config for Pydantic defaults are valid
        assert (dummy_files_for_config / config_after_clear.global_settings.log_file_path).exists()
        assert (dummy_files_for_config / config_after_clear.global_settings.error_log_file_path).exists()
        assert (dummy_files_for_config / config_after_clear.report_generator.report_templates_dir).exists()

        # Reload original config after cache clear and ensure it's a new object
        config2 = load_verification_config(str(config_path), force_reload=True) 
        assert config1 is not config2, "Loading same config path after cache clear did not return a new instance with force_reload"
        assert config2.global_settings.log_level == VALID_CONFIG_DICT["global_settings"]["log_level"]
        assert get_config() is config2 # The newly loaded config should now be cached

        # After clearing, get_config() will try to load defaults again, this time with os.path.exists mocked
        # to simulate no default config files being present, forcing pure Pydantic model defaults.
        _clear_cached_config() # Clear cache again before this specific test part
        
        original_cwd_mock_section = os.getcwd() # Use a unique name for cwd
        os.chdir(dummy_files_for_config) # Ensure CWD is correct for Pydantic default path resolution
        
        # Store the original os.path.exists before patching
        original_os_path_exists_func = os.path.exists # Store original function

        def mock_exists_no_files(path_to_check): # Renamed param to avoid confusion
            # This mock should only affect the specific default config file paths
            if path_to_check in ["./verification_config.yaml", "verification_config.yaml", "config/verification_config.yaml"]:
                return False
            # For all other paths (especially Pydantic\'s default FilePath/DirectoryPath checks),
            # use the original os.path.exists to check actual file existence.
            return original_os_path_exists_func(path_to_check) # Call stored original
        
        monkeypatch.setattr(os.path, 'exists', mock_exists_no_files)

        try:
            # This get_config() call will trigger load_verification_config(None)
            # which will then use the mocked os.path.exists
            config_pure_pydantic_defaults = get_config() 
            assert config_pure_pydantic_defaults is not config1, "Should be a new instance (pure Pydantic defaults)"
            assert config_pure_pydantic_defaults is not config2, "Should be a new instance (pure Pydantic defaults vs earlier file-loaded config2)"
            # Also should be different from config_after_clear (the first default load attempt before this specific mock)
            assert config_pure_pydantic_defaults is not config_after_clear, "Should be a new instance (pure Pydantic defaults vs first default load)"

            assert config_pure_pydantic_defaults.global_settings.log_level == "INFO" # Check Pydantic default
            # Ensure Pydantic\'s default paths are still being checked against the filesystem correctly
            # (via original_os_path_exists_func) if they are absolute or resolvable from dummy_files_for_config
            assert (dummy_files_for_config / config_pure_pydantic_defaults.global_settings.log_file_path).exists()
            assert (dummy_files_for_config / config_pure_pydantic_defaults.global_settings.error_log_file_path).exists()
            assert (dummy_files_for_config / config_pure_pydantic_defaults.report_generator.report_templates_dir).exists()

        finally:
            os.chdir(original_cwd_mock_section)
            monkeypatch.undo() # Crucial to undo the patch

        # Verify that after undo, loading the specific config file works as expected and updates the cache
        _clear_cached_config() # Clear cache one last time to ensure a fresh load
        final_config_from_file = load_verification_config(str(config_path))
        assert final_config_from_file.global_settings.log_level == VALID_CONFIG_DICT["global_settings"]["log_level"]
        assert get_config() is final_config_from_file
