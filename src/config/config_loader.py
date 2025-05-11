import yaml
import os
from typing import Dict, Any, Optional
from pydantic import ValidationError
from src.config.models import VerificationConfig
from src.core.exceptions import ConfigurationError

# Environment variable prefix
ENV_VAR_PREFIX = "KFM_VERIFIER_"

def _convert_to_type(value: str, target_type: type) -> Any:
    """Helper to convert string env var to basic Python types."""
    if target_type == bool:
        return value.lower() in ('true', '1', 't', 'yes', 'y')
    if target_type == int:
        return int(value)
    if target_type == float:
        return float(value)
    # Add other types like list (e.g., comma-separated) if needed
    return value

def _get_env_var_overrides(prefix: str = ENV_VAR_PREFIX) -> Dict[str, Any]:
    """
    Collects configuration overrides from environment variables.
    Recognizes nested structures via double underscores, e.g., KFM_VERIFIER_GLOBAL_SETTINGS__LOG_LEVEL.
    """
    overrides: Dict[str, Any] = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Remove prefix and split by double underscore for nesting
            config_path = key[len(prefix):].lower().split('__')
            
            current_level = overrides
            for i, path_part in enumerate(config_path):
                if i == len(config_path) - 1:
                    # Attempt to guess basic types for env vars, Pydantic will do final validation
                    # This simple type conversion is limited; Pydantic handles complex types.
                    # For structured types like lists or nested dicts from env vars, a more
                    # sophisticated parsing strategy (e.g. JSON strings) might be needed if
                    # Pydantic can't infer correctly or if direct type hints aren't sufficient.
                    current_level[path_part] = value # Store as string, Pydantic will coerce/validate
                else:
                    current_level = current_level.setdefault(path_part, {})
    return overrides

def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges update dict into base dict."""
    merged = base.copy()
    for key, value in updates.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged

_loaded_config: Optional[VerificationConfig] = None

def load_verification_config(config_filepath: Optional[str] = None, force_reload: bool = False) -> VerificationConfig:
    """
    Loads the verification configuration from a YAML file, applies environment
    variable overrides, validates it, and caches the result.

    Args:
        config_filepath: Optional path to the YAML configuration file.
                         If None, tries to load from a default path or uses pure defaults/env vars.
        force_reload: If True, reloads the configuration even if already loaded.

    Returns:
        The validated VerificationConfig object.

    Raises:
        ConfigurationError: If the config file is not found, unparsable, or invalid.
    """
    global _loaded_config
    if _loaded_config is not None and not force_reload:
        return _loaded_config

    base_config_data: Dict[str, Any] = {}
    default_config_paths = [
        './verification_config.yaml',
        'verification_config.yaml',
        'config/verification_config.yaml'
    ]
    actual_config_path_used = None

    if config_filepath:
        if not os.path.exists(config_filepath):
            raise ConfigurationError(f"Specified configuration file not found: {config_filepath}")
        actual_config_path_used = config_filepath
        try:
            with open(config_filepath, 'r') as f:
                base_config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML configuration file '{config_filepath}': {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Unexpected error loading configuration file '{config_filepath}': {e}") from e
    else:
        for path in default_config_paths:
            if os.path.exists(path):
                actual_config_path_used = path
                print(f"Loading configuration from default path: {path}")
                try:
                    with open(path, 'r') as f:
                        base_config_data = yaml.safe_load(f) or {}
                    break
                except yaml.YAMLError as e:
                    raise ConfigurationError(f"Error parsing YAML configuration file '{path}': {e}") from e
                except Exception as e:
                    raise ConfigurationError(f"Unexpected error loading configuration file '{path}': {e}") from e
        else:
            print("No configuration file provided or found at default locations. Using Pydantic defaults and environment variables.")

    env_overrides = _get_env_var_overrides()
    final_config_data = _deep_merge_dicts(base_config_data, env_overrides)
    
    try:
        config = VerificationConfig(**final_config_data)
        _loaded_config = config
        return _loaded_config
    except ValidationError as e:
        err_msg = f"Configuration validation error(s) (loaded from {actual_config_path_used if actual_config_path_used else 'defaults/env'}):\n{e}"
        raise ConfigurationError(err_msg) from e
    except Exception as e: # Catch any other unexpected Pydantic or model instantiation errors
        raise ConfigurationError(f"Unexpected error during final configuration model instantiation: {e}") from e

def get_config() -> VerificationConfig:
    """
    Returns the loaded VerificationConfig instance.
    Loads it if it hasn't been loaded yet (e.g., from a default path).
    """
    if _loaded_config is None:
        # Attempt to load from default paths or use pure defaults if no file found
        return load_verification_config()
    return _loaded_config

def _clear_cached_config(): # Simpler: clear the single global cache
    """Clears the cached configuration. Primarily for testing."""
    global _loaded_config
    _loaded_config = None

# --- Example Usage and Testing --- #
if __name__ == '__main__':
    # Create dummy files and directories for testing
    if not os.path.exists("src/config"): os.makedirs("src/config")
    if not os.path.exists("config"): os.makedirs("config")
    if not os.path.exists("logs"): os.makedirs("logs")
    if not os.path.exists("logs/dummy.log"): open("logs/dummy.log", "w").close()
    if not os.path.exists("src/verification/report_generator/templates"): 
        os.makedirs("src/verification/report_generator/templates")

    # 1. Test with a sample config file
    sample_yaml_content = """
    global_settings:
      log_level: DEBUG
      max_retries: 5
    log_parsing:
      log_sources:
        - path: logs/dummy.log
          parser_type: test_parser
    registry_verifier:
      client_type: mock_from_file
      mock_registry_data_file: README.md # Assuming README.md exists at root
    report_generator:
        report_templates_dir: src/verification/report_generator/templates
    """
    sample_config_path = "./temp_test_config.yaml"
    with open(sample_config_path, 'w') as f:
        f.write(sample_yaml_content)

    print("--- Testing loading from file ---")
    try:
        cfg_from_file = load_verification_config(sample_config_path, force_reload=True)
        print("Loaded from file:", cfg_from_file.global_settings.log_level)
        assert cfg_from_file.global_settings.log_level == "DEBUG"
        assert cfg_from_file.log_parsing.log_sources[0].path.name == "dummy.log" # Pydantic FilePath
    except Exception as e:
        print(f"Error in file loading test: {e}")

    # 2. Test with environment variable overrides
    print("\\n--- Testing environment variable overrides ---")
    os.environ[f"{ENV_VAR_PREFIX}GLOBAL_SETTINGS__LOG_LEVEL"] = "WARNING"
    os.environ[f"{ENV_VAR_PREFIX}GLOBAL_SETTINGS__MAX_RETRIES"] = "10" # This should be int
    os.environ[f"{ENV_VAR_PREFIX}LOG_PARSING__LOG_SOURCES__0__PATH"] = "logs/override.log"
    # Pydantic will handle type conversion for simple types like int for max_retries if it can.

    try:
        # Create override.log for FilePath validation if it doesn't exist
        if not os.path.exists("logs/override.log"): open("logs/override.log", "w").close()

        cfg_with_env = load_verification_config(sample_config_path, force_reload=True)
        print("With env overrides:")
        print("  Log Level:", cfg_with_env.global_settings.log_level)
        print("  Max Retries:", cfg_with_env.global_settings.max_retries)
        print("  Log Source 0 Path:", cfg_with_env.log_parsing.log_sources[0].path)
        
        assert cfg_with_env.global_settings.log_level == "WARNING"
        assert cfg_with_env.global_settings.max_retries == 10 # Pydantic converted '10' string to int
        assert cfg_with_env.log_parsing.log_sources[0].path.name == "override.log"

    except Exception as e:
        print(f"Error in env override test: {e}")
    finally:
        # Clean up environment variables
        del os.environ[f"{ENV_VAR_PREFIX}GLOBAL_SETTINGS__LOG_LEVEL"]
        del os.environ[f"{ENV_VAR_PREFIX}GLOBAL_SETTINGS__MAX_RETRIES"]
        del os.environ[f"{ENV_VAR_PREFIX}LOG_PARSING__LOG_SOURCES__0__PATH"]
        if os.path.exists("logs/override.log"): os.remove("logs/override.log")

    # 3. Test loading with no file (using defaults and any remaining env vars)
    print("\\n--- Testing loading with no file (defaults) ---")
    if os.path.exists(sample_config_path): os.remove(sample_config_path)
    # Ensure default_config_paths don't exist for this test
    if os.path.exists('./verification_config.yaml'): os.rename('./verification_config.yaml', './verification_config.yaml.bak')
    if os.path.exists('verification_config.yaml'): os.rename('verification_config.yaml', 'verification_config.yaml.bak')
    if os.path.exists('config/verification_config.yaml'): os.rename('config/verification_config.yaml', 'config/verification_config.yaml.bak')
    
    try:
        cfg_default = load_verification_config(force_reload=True)
        print("Default log level:", cfg_default.global_settings.log_level) # Should be INFO (Pydantic default)
        assert cfg_default.global_settings.log_level == "INFO"
    except Exception as e:
        print(f"Error in no-file loading test: {e}")
    finally:
        # Restore backed up config files if they exist
        if os.path.exists('./verification_config.yaml.bak'): os.rename('./verification_config.yaml.bak', './verification_config.yaml')
        if os.path.exists('verification_config.yaml.bak'): os.rename('verification_config.yaml.bak', 'verification_config.yaml')
        if os.path.exists('config/verification_config.yaml.bak'): os.rename('config/verification_config.yaml.bak', 'config/verification_config.yaml')

    # 4. Test get_config()
    print("\\n--- Testing get_config() ---")
    try:
        # Assumes cfg_default was loaded successfully in the previous step
        retrieved_cfg = get_config()
        print("Retrieved log level via get_config():", retrieved_cfg.global_settings.log_level)
        assert retrieved_cfg is _loaded_config # Check if it returns the cached instance
        assert retrieved_cfg.global_settings.log_level == "INFO"
    except Exception as e:
        print(f"Error in get_config() test: {e}")

    # Clean up dummy file
    if os.path.exists(sample_config_path): os.remove(sample_config_path)
    print("\\nExample usage finished.") 