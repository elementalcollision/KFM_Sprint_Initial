import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, NamedTuple
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ModuleDependency:
    name: str
    version_specifier: str

@dataclass(frozen=True)
class ModuleMetadata:
    module_name: str
    version: str
    entry_point: str
    source_file_path: Path
    cached_at_mtime: float
    description: Optional[str] = None
    author: Optional[str] = None
    dependencies: List[ModuleDependency] = field(default_factory=list)
    supports_reversibility: bool = False

class ModuleDiscoveryError(Exception):
    """Base exception for module discovery issues."""
    pass

class YAMLParseError(ModuleDiscoveryError):
    """Raised when a module YAML file cannot be parsed."""
    pass

class MetadataValidationError(ModuleDiscoveryError):
    """Raised when module metadata validation fails."""
    pass

class ModuleDiscoveryService:
    """
    Discovers modules defined by YAML configuration files within specified directories.
    Parses, validates, and caches the metadata from these files.
    """
    def __init__(self):
        self._cache: Dict[str, ModuleMetadata] = {} # In-memory cache

    def _scan_for_module_files(self, directories: List[str], file_pattern: str = "*.module.yaml") -> List[Path]:
        """Scans directories for module definition files."""
        module_files: List[Path] = []
        for directory_str in directories:
            dir_path = Path(directory_str)
            if not dir_path.is_dir():
                print(f"Warning: Directory not found or not a directory: {directory_str}")
                continue
            module_files.extend(list(dir_path.rglob(file_pattern)))
        return module_files

    def _parse_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Parses a single YAML file into a dictionary."""
        try:
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
                if content is None: # Handles completely empty file
                    return {} 
                if not isinstance(content, dict): # Ensure top level is a map
                    raise YAMLParseError(f"YAML content in {file_path} is not a dictionary (map). Expected a map, got {type(content)}.")
                return content
        except yaml.YAMLError as e:
            raise YAMLParseError(f"Error parsing YAML file {file_path}: {e}") from e
        except IOError as e:
            raise ModuleDiscoveryError(f"Error reading file {file_path}: {e}") from e

    def _validate_and_create_metadata(self, data: Dict[str, Any], file_path: Path) -> ModuleMetadata:
        """Validates the raw data and creates a ModuleMetadata object."""
        required_fields = ["module_name", "version", "entry_point"]
        for field_name in required_fields:
            if field_name not in data:
                raise MetadataValidationError(f"Missing required field '{field_name}' in {file_path}")
            if not isinstance(data[field_name], str) or not data[field_name].strip():
                raise MetadataValidationError(f"Field '{field_name}' must be a non-empty string in {file_path}")

        # Further type checks for optional fields if present
        if "description" in data and data["description"] is not None and not isinstance(data["description"], str):
            raise MetadataValidationError(f"Optional field 'description' must be a string if present in {file_path}")
        if "author" in data and data["author"] is not None and not isinstance(data["author"], str):
            raise MetadataValidationError(f"Optional field 'author' must be a string if present in {file_path}")

        dependencies_data = data.get("dependencies")
        parsed_dependencies: List[ModuleDependency] = []
        if dependencies_data is not None:
            if not isinstance(dependencies_data, list):
                raise MetadataValidationError(f"Field 'dependencies' must be a list in {file_path}")
            for i, dep_data in enumerate(dependencies_data):
                if not isinstance(dep_data, dict):
                    raise MetadataValidationError(f"Each dependency (index {i}) must be a dictionary in {file_path}")
                
                dep_name = dep_data.get("name")
                dep_version = dep_data.get("version_specifier")
                
                if not dep_name or not isinstance(dep_name, str) or not dep_name.strip():
                    raise MetadataValidationError(f"Dependency (index {i}) 'name' is missing, not a string, or empty in {file_path}")
                if not dep_version or not isinstance(dep_version, str) or not dep_version.strip():
                    raise MetadataValidationError(f"Dependency (index {i}) 'version_specifier' for '{dep_name}' is missing, not a string, or empty in {file_path}")
                parsed_dependencies.append(ModuleDependency(name=dep_name, version_specifier=dep_version))
        
        # Handle supports_reversibility field
        supports_reversibility_val = data.get("supports_reversibility", False) # Default to False if not present
        if not isinstance(supports_reversibility_val, bool):
            raise MetadataValidationError(f"Optional field 'supports_reversibility' must be a boolean if present in {file_path}")

        try:
            current_mtime = file_path.stat().st_mtime
            return ModuleMetadata(
                module_name=data["module_name"].strip(),
                version=data["version"].strip(),
                entry_point=data["entry_point"].strip(),
                description=data.get("description", "").strip() or None,
                author=data.get("author", "").strip() or None,
                dependencies=parsed_dependencies,
                source_file_path=file_path.resolve(),
                cached_at_mtime=current_mtime,
                supports_reversibility=supports_reversibility_val
            )
        except TypeError as e: 
            raise MetadataValidationError(f"Error creating ModuleMetadata from data in {file_path}: {e}")


    def discover_modules(self, directories: List[str], use_cache: bool = True) -> Dict[str, ModuleMetadata]:
        """
        Discovers all modules in the given directories.
        Uses cache by default. If use_cache is False, it will refresh the cache.
        """
        if not use_cache:
            self.clear_cache()

        discovered_modules_this_run: Dict[str, ModuleMetadata] = {}
        module_files = self._scan_for_module_files(directories)

        for file_path in module_files:
            module_name_for_cache_check: Optional[str] = None
            cached_entry_found_by_path = False
            
            try:
                current_file_mtime = file_path.stat().st_mtime

                if use_cache:
                    for mn_in_cache, meta_in_cache in list(self._cache.items()): 
                        if meta_in_cache.source_file_path.resolve() == file_path.resolve():
                            module_name_for_cache_check = mn_in_cache
                            if not meta_in_cache.source_file_path.exists():
                                print(f"Info: Cached source file {meta_in_cache.source_file_path} for module {mn_in_cache} no longer exists. Removing from cache.")
                                del self._cache[mn_in_cache]
                                break

                            cached_object_mtime = meta_in_cache.cached_at_mtime 
                            if current_file_mtime <= cached_object_mtime:
                                discovered_modules_this_run[module_name_for_cache_check] = meta_in_cache
                                cached_entry_found_by_path = True
                            else:
                                print(f"Info: Cache invalidated for {module_name_for_cache_check} (file: {file_path}) due to file modification (current_mtime: {current_file_mtime}, cached_mtime: {cached_object_mtime}).")
                                del self._cache[module_name_for_cache_check]
                            break 
                
                if cached_entry_found_by_path:
                    continue

                raw_data = self._parse_yaml_file(file_path)
                if not raw_data:
                    # This case should be handled by _parse_yaml_file returning {} for empty file
                    # and then the module_name check below will fail.
                    # Adding an explicit check here if _parse_yaml_file can return None/empty for other reasons.
                    print(f"Warning: No data parsed from {file_path} or file is empty. Skipping.")
                    continue

                module_name = raw_data.get("module_name")
                if not isinstance(module_name, str) or not module_name.strip():
                    print(f"Warning: 'module_name' missing, not a string, or empty in {file_path}. Skipping.")
                    continue
                module_name = module_name.strip()
                
                metadata = self._validate_and_create_metadata(raw_data, file_path)
                
                # If an old module with the same name but different file path existed, this will overwrite it.
                # This is generally fine. If a module moves and keeps its name, it's effectively a "new" discovery at the new path.
                self._cache[module_name] = metadata 
                discovered_modules_this_run[module_name] = metadata

            except ModuleDiscoveryError as e:
                print(f"Error discovering module from file {file_path}: {e}")
            except FileNotFoundError:
                print(f"Warning: File {file_path} not found during processing (e.g., deleted after scan). Skipping.")
            except Exception as e:
                print(f"Unexpected error processing file {file_path}: {e}")
        
        return discovered_modules_this_run


    def clear_cache(self):
        """Clears the in-memory module cache."""
        self._cache.clear()
        print("Info: Module discovery cache cleared.") 