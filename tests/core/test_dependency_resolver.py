# tests/core/test_dependency_resolver.py
import pytest
from pathlib import Path
import time # For dummy mtime

# Make sure src is importable
# import sys
# sys.path.insert(0, Path(__file__).parent.parent.as_posix()) 

from src.core.discovery import ModuleMetadata, ModuleDependency
from src.core.dependency_resolver import (
    DependencyResolver,
    DependencyResolutionError,
    CircularDependencyError,
    MissingDependencyError
)

# --- Test Data / Fixtures ---

@pytest.fixture
def resolver():
    """Provides a fresh DependencyResolver instance."""
    return DependencyResolver()

# Helper to create dummy metadata easily
def create_meta(name, version, deps=None, path_suffix=""):
    if deps is None:
        deps = []
    # Ensure deps are ModuleDependency objects
    parsed_deps = []
    for d in deps:
        if isinstance(d, tuple) and len(d) == 2:
            parsed_deps.append(ModuleDependency(name=d[0], version_specifier=d[1]))
        elif isinstance(d, ModuleDependency):
            parsed_deps.append(d)
        else:
            raise ValueError("Invalid dependency format in test setup")
            
    return ModuleMetadata(
        module_name=name, version=version, entry_point=f"{name}.{version}.main",
        source_file_path=Path(f"/fake/{name}{path_suffix}.yaml"), 
        cached_at_mtime=time.time(),
        dependencies=parsed_deps
    )

# --- Test Cases ---

class TestDependencyResolver:

    def test_resolve_no_modules(self, resolver: DependencyResolver):
        assert resolver.resolve({}) == []

    def test_resolve_single_module_no_deps(self, resolver: DependencyResolver):
        meta_a = create_meta("A", "1.0")
        available = {"A": {"1.0": meta_a}}
        resolved = resolver.resolve(available)
        assert resolved == [meta_a]

    def test_resolve_multiple_modules_no_deps(self, resolver: DependencyResolver):
        meta_a = create_meta("A", "1.0")
        meta_b = create_meta("B", "2.0")
        available = {"A": {"1.0": meta_a}, "B": {"2.0": meta_b}}
        resolved = resolver.resolve(available)
        # Order doesn't matter if no dependencies
        assert len(resolved) == 2
        assert meta_a in resolved
        assert meta_b in resolved

    def test_resolve_linear_dependency(self, resolver: DependencyResolver):
        # A -> B -> C
        meta_c = create_meta("C", "1.0")
        meta_b = create_meta("B", "1.0", deps=[("C", "==1.0")])
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b},
            "C": {"1.0": meta_c}
        }
        resolved = resolver.resolve(available)
        assert resolved == [meta_c, meta_b, meta_a]

    def test_resolve_diamond_dependency(self, resolver: DependencyResolver):
        #   A
        #  / \
        # B   C
        #  \ / 
        #   D
        meta_d = create_meta("D", "1.0")
        meta_b = create_meta("B", "1.0", deps=[("D", "==1.0")])
        meta_c = create_meta("C", "1.0", deps=[("D", "==1.0")])
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0"), ("C", "==1.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b},
            "C": {"1.0": meta_c},
            "D": {"1.0": meta_d}
        }
        resolved = resolver.resolve(available)
        # Valid orders: D, B, C, A or D, C, B, A
        assert len(resolved) == 4
        assert resolved[0] == meta_d
        assert resolved[-1] == meta_a
        assert meta_b in resolved[1:3]
        assert meta_c in resolved[1:3]
        
    def test_resolve_selects_latest_compatible_version(self, resolver: DependencyResolver):
        # A -> B (>=1.0)
        meta_b1 = create_meta("B", "1.0")
        meta_b2 = create_meta("B", "1.1")
        meta_b09 = create_meta("B", "0.9")
        meta_a = create_meta("A", "1.0", deps=[("B", ">=1.0,<2.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b1, "1.1": meta_b2, "0.9": meta_b09}
        }
        resolved = resolver.resolve(available)
        # Should select B v1.1
        assert len(resolved) == 2
        assert resolved[0].module_name == "B"
        assert resolved[0].version == "1.1"
        assert resolved[1].module_name == "A"
        assert resolved[1].version == "1.0"

    def test_resolve_selects_exact_version(self, resolver: DependencyResolver):
        # A -> B (==1.0)
        meta_b1 = create_meta("B", "1.0")
        meta_b2 = create_meta("B", "1.1")
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b1, "1.1": meta_b2}
        }
        resolved = resolver.resolve(available)
        # Should select B v1.0
        assert len(resolved) == 2
        assert resolved[0].module_name == "B"
        assert resolved[0].version == "1.0"
        assert resolved[1].module_name == "A"
        assert resolved[1].version == "1.0"

    def test_resolve_missing_dependency_module(self, resolver: DependencyResolver):
        # A -> B, but B is not available
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0")])
        available = {"A": {"1.0": meta_a}}
        
        with pytest.raises(MissingDependencyError) as excinfo:
            resolver.resolve(available)
        assert excinfo.value.requiring_module == ("A", "1.0")
        assert excinfo.value.missing_dep_name == "B"
        assert excinfo.value.specifier == "==1.0"
        assert "requires B (version ==1.0), but no compatible version was found" in str(excinfo.value)

    def test_resolve_missing_dependency_version(self, resolver: DependencyResolver):
        # A -> B (==2.0), but only B v1.0 is available
        meta_b1 = create_meta("B", "1.0")
        meta_a = create_meta("A", "1.0", deps=[("B", "==2.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b1}
        }
        
        with pytest.raises(MissingDependencyError) as excinfo:
            resolver.resolve(available)
        assert excinfo.value.requiring_module == ("A", "1.0")
        assert excinfo.value.missing_dep_name == "B"
        assert excinfo.value.specifier == "==2.0"
        assert "requires B (version ==2.0), but no compatible version was found" in str(excinfo.value)

    def test_resolve_invalid_version_specifier(self, resolver: DependencyResolver):
        # A -> B (invalid spec)
        meta_b = create_meta("B", "1.0")
        meta_a = create_meta("A", "1.0", deps=[("B", "invalid-spec!!!")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b}
        }
        
        with pytest.raises(DependencyResolutionError) as excinfo:
            resolver.resolve(available)
        assert "invalid version specifier" in str(excinfo.value)
        assert "'invalid-spec!!!'" in str(excinfo.value)

    def test_resolve_circular_dependency_direct(self, resolver: DependencyResolver):
        # A -> B, B -> A
        meta_b = create_meta("B", "1.0", deps=[("A", "==1.0")])
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b}
        }
        
        with pytest.raises(CircularDependencyError) as excinfo:
            resolver.resolve(available)
        # Cycle can be A->B->A or B->A->B
        assert ("A(1.0) -> B(1.0) -> A(1.0)" in str(excinfo.value) or 
                "B(1.0) -> A(1.0) -> B(1.0)" in str(excinfo.value))

    def test_resolve_circular_dependency_indirect(self, resolver: DependencyResolver):
        # A -> B -> C -> A
        meta_c = create_meta("C", "1.0", deps=[("A", "==1.0")])
        meta_b = create_meta("B", "1.0", deps=[("C", "==1.0")])
        meta_a = create_meta("A", "1.0", deps=[("B", "==1.0")])
        available = {
            "A": {"1.0": meta_a},
            "B": {"1.0": meta_b},
            "C": {"1.0": meta_c}
        }
        
        with pytest.raises(CircularDependencyError) as excinfo:
            resolver.resolve(available)
        
        # Check that the cycle involves the expected module names
        # The .cycle attribute in the exception is a list of (name, version) tuples
        # representing the cycle path, with the start node repeated at the end.
        cycle_node_tuples = excinfo.value.cycle
        assert len(cycle_node_tuples) > 1 # Should be at least start -> end (e.g. A->A for direct self-loop of 1 node)
                                          # For A->B->C->A, it's 4 elements.
        
        # Extract unique module names from the cycle path (excluding the repeated end node for simplicity of set)
        unique_node_names_in_cycle = set(t[0] for t in cycle_node_tuples[:-1])
        assert unique_node_names_in_cycle == {"A", "B", "C"}
        # Ensure the cycle consists of 3 unique nodes before repetition
        assert len(unique_node_names_in_cycle) == 3

    def test_resolve_complex_graph_multiple_versions(self, resolver: DependencyResolver):
        # App -> Framework(>=2.0), UI(==1.5)
        # Framework -> Core(==1.0)
        # UI -> Core(>=0.9,<2.0), Utils(==1.0)
        # Utils -> Core(==1.0)
        
        meta_core_v1 = create_meta("Core", "1.0")
        meta_core_v09 = create_meta("Core", "0.9")
        meta_utils_v1 = create_meta("Utils", "1.0", deps=[("Core", "==1.0")])
        meta_framework_v2 = create_meta("Framework", "2.0", deps=[("Core", "==1.0")])
        meta_framework_v2_1 = create_meta("Framework", "2.1", deps=[("Core", "==1.0")])
        meta_ui_v15 = create_meta("UI", "1.5", deps=[("Core", ">=0.9,<2.0"), ("Utils", "==1.0")])
        meta_app = create_meta("App", "1.0", deps=[("Framework", ">=2.0"), ("UI", "==1.5")])

        available = {
            "App": {"1.0": meta_app},
            "Framework": {"2.0": meta_framework_v2, "2.1": meta_framework_v2_1},
            "UI": {"1.5": meta_ui_v15},
            "Utils": {"1.0": meta_utils_v1},
            "Core": {"0.9": meta_core_v09, "1.0": meta_core_v1}
        }
        
        resolved = resolver.resolve(available)
        
        # Expected: Core(1.0), Utils(1.0), Framework(2.1), UI(1.5), App(1.0)
        # Core v1.0 is needed by Utils and Framework v2.1, and compatible with UI v1.5
        # Utils v1.0 is needed by UI v1.5
        # Framework v2.1 is latest compatible for App
        # UI v1.5 is exact match for App
        
        assert len(resolved) == 5
        resolved_names_versions = [(m.module_name, m.version) for m in resolved]
        
        # Check content
        expected_set = {
            ("Core", "1.0"), 
            ("Utils", "1.0"), 
            ("Framework", "2.1"), 
            ("UI", "1.5"), 
            ("App", "1.0")
        }
        assert set(resolved_names_versions) == expected_set
        
        # Check core ordering constraints imposed by dependencies
        # (index method will raise ValueError if item not found, covered by set check)
        core_index = resolved_names_versions.index(("Core", "1.0"))
        utils_index = resolved_names_versions.index(("Utils", "1.0"))
        framework_index = resolved_names_versions.index(("Framework", "2.1"))
        ui_index = resolved_names_versions.index(("UI", "1.5"))
        app_index = resolved_names_versions.index(("App", "1.0"))
        
        assert core_index < utils_index      # Utils depends on Core
        assert core_index < framework_index  # Framework depends on Core
        # UI depends on Core and Utils, so Core < UI and Utils < UI
        assert core_index < ui_index      
        assert utils_index < ui_index       
        # App depends on Framework and UI, so Framework < App and UI < App
        assert framework_index < app_index  
        assert ui_index < app_index 