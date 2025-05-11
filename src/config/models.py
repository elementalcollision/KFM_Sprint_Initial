import os
from pydantic import BaseModel, FilePath, DirectoryPath, field_validator, model_validator, HttpUrl
from typing import List, Optional, Union, Literal, Dict, Any
from typing_extensions import Self

class GlobalConfig(BaseModel):
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    log_file_path: Optional[str] = "logs/kfm_verifier.log"  # Default log file path
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Default log format
    error_log_file_path: Optional[str] = "logs/kfm_verifier_errors.jsonl"  # Default error log file path (JSON Lines)
    error_log_format: str = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "funcName": "%(funcName)s", "lineno": %(lineno)d, "message": "%(message)s", "exception": "%(exc_info)s"}' # Default structured JSON error format
    max_retries: int = 3
    retry_delay: float = 5.0  # seconds, changed to float

class LogSourceConfig(BaseModel):
    path: Union[FilePath, DirectoryPath]
    parser_type: str # Later, this could be Literal['json_line', 'regex_line', 'auto_detect']
    # regex_patterns_file: Optional[FilePath] = None # Example if we add this

class LogParsingConfig(BaseModel):
    default_date_formats: List[str] = ["%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%dT%H:%M:%S.%fZ"]
    log_sources: List[LogSourceConfig] = []

class RegistryAccessDetails(BaseModel): # Placeholder for actual details
    endpoint: Optional[HttpUrl] = None
    # ... other potential fields like api_key_env_var: Optional[str] = None

class RegistryVerifierConfig(BaseModel):
    client_type: Literal['live', 'mock_from_file', 'in_memory'] = 'live'
    registry_access_details: Optional[RegistryAccessDetails] = None
    mock_registry_data_file: Optional[FilePath] = None
    cache_ttl: int = 300  # seconds

    @model_validator(mode='after')
    def check_mock_file_if_mock_type(self) -> Self:
        # 'self' here is the model instance after initial field validation
        if self.client_type == 'mock_from_file' and not self.mock_registry_data_file:
            raise ValueError("mock_registry_data_file must be provided if client_type is 'mock_from_file'")
        return self

class OutcomeComparatorConfig(BaseModel):
    default_numeric_tolerance: float = 0.001
    default_missing_path_behavior: Literal['fail', 'warn', 'pass'] = 'warn'

class ReportGeneratorConfig(BaseModel):
    default_report_formats: List[Literal['json', 'html', 'pdf']] = ['json', 'html']
    report_templates_dir: DirectoryPath = 'src/verification/report_generator/templates'
    default_report_output_dir: str = "verification_reports" # Not a Path type, as it's created at runtime

class CliDefaultConfig(BaseModel):
    verification_level: Literal['basic', 'standard', 'detailed'] = 'standard'
    # other CLI options can have defaults here if needed

class MemoryConfig(BaseModel):
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_db_path: str = "./kfm_chroma_db"  # Default path for Chroma persistent storage
    collection_name: str = "agent_experiences" # Default collection name
    # Potentially other memory-related settings later, e.g.:
    # default_top_k_retrieval: int = 5

class VerificationConfig(BaseModel):
    global_settings: GlobalConfig = GlobalConfig()
    log_parsing: LogParsingConfig = LogParsingConfig()
    registry_verifier: RegistryVerifierConfig = RegistryVerifierConfig()
    outcome_comparator: OutcomeComparatorConfig = OutcomeComparatorConfig()
    report_generator: ReportGeneratorConfig = ReportGeneratorConfig()
    cli_defaults: CliDefaultConfig = CliDefaultConfig()
    memory: MemoryConfig = MemoryConfig()
    verification_criteria: Optional[List[Dict[str, Any]]] = None

    # Example for loading from a dict (e.g., from YAML)
    # This is more for the loader, but shows how it might interact
    # @classmethod
    # def from_dict(cls, data: Dict[str, Any]) -> 'VerificationConfig':
    #     return cls(**data)

if __name__ == '__main__':
    # Example usage and validation
    sample_config_data = {
        "global_settings": {"log_level": "DEBUG"},
        "log_parsing": {
            "log_sources": [
                {"path": "logs/dummy.log", "parser_type": "auto_detect"}
            ]
        },
        "registry_verifier": {
            "client_type": "mock_from_file",
            # "mock_registry_data_file": "path/to/mock.json" # Missing, should raise error if not for the __main__ check
        }
    }
    
    # Test with a valid mock_registry_data_file for the mock client type
    sample_config_data_valid_mock = {
        "global_settings": {"log_level": "DEBUG"},
        "log_parsing": {
            "log_sources": [
                # Assuming a dummy file exists or pydantic won't complain in this example context
                # For real usage, FilePath checks existence. For this __main__ example, we might bypass.
                 {"path": ".", "parser_type": "auto_detect"} # Using current dir as a dummy existing path
            ]
        },
        "registry_verifier": {
            "client_type": "mock_from_file",
            "mock_registry_data_file": "README.md" # Using an existing file as dummy
        },
        "report_generator": {
            # Assuming templates dir exists or pydantic will complain for DirectoryPath
            # For this __main__ example, we might bypass or point to an existing one.
            "report_templates_dir": "." # Using current dir as a dummy existing path
        }
    }

    try:
        print("--- Testing basic structure (potentially missing mock_registry_data_file for 'mock_from_file') ---")
        # config_test_1 = VerificationConfig(**sample_config_data) # This would fail if files don't exist
        # print(config_test_1.model_dump_json(indent=2))
        print("\\n--- Testing with valid mock_registry_data_file ---")
        # To make FilePath and DirectoryPath work in this __main__ without actual files/dirs at expected locations,
        # we'd need to create them or use a more elaborate setup.
        # For now, we'll assume the paths like "." or "README.md" satisfy Pydantic's basic checks
        # if they exist at the root when running this script directly.
        
        # Create dummy files/dirs for Pydantic validation if they don't exist
        if not os.path.exists("logs"): os.makedirs("logs")
        if not os.path.exists("logs/dummy.log"): open("logs/dummy.log", "w").close()
        if not os.path.exists("src/verification/report_generator/templates"):
             os.makedirs("src/verification/report_generator/templates")

        sample_config_data_for_main = {
            "global_settings": {"log_level": "DEBUG"},
            "log_parsing": {
                "log_sources": [
                    {"path": "logs/dummy.log", "parser_type": "auto_detect"}
                ]
            },
            "registry_verifier": {
                "client_type": "mock_from_file",
                "mock_registry_data_file": "README.md" 
            },
            "report_generator": {
                 "report_templates_dir": "src/verification/report_generator/templates"
            }
        }
        config_test_valid = VerificationConfig(**sample_config_data_for_main)
        print(config_test_valid.model_dump_json(indent=2))

    except Exception as e:
        print(f"Error during Pydantic model validation: {e}")

    # Example of how the validator works:
    print("\\n--- Testing RegistryVerifierConfig validator ---")
    try:
        RegistryVerifierConfig(client_type='mock_from_file') # Missing mock_registry_data_file
    except ValueError as e:
        print(f"Caught expected error: {e}")

    try:
        RegistryVerifierConfig(client_type='mock_from_file', mock_registry_data_file='README.md') # Valid
        print("Successfully created RegistryVerifierConfig with mock_from_file and mock_registry_data_file.")
    except ValueError as e:
        print(f"Caught unexpected error: {e}") 