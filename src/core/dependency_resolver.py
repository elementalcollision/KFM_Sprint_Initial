# src/core/dependency_resolver.py
from typing import Dict, List, Optional, Tuple, Any
import networkx as nx
from packaging.version import parse as parse_version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier

# Assuming ModuleMetadata and ModuleDependency are correctly importable
# Adjust the path if necessary based on project structure
try:
    from .discovery import ModuleMetadata, ModuleDependency
except ImportError:
    # Fallback for potential execution context issues (e.g., running tests directly)
    # This might need adjustment based on the actual project structure and test setup.
    from discovery import ModuleMetadata, ModuleDependency


# --- Custom Exceptions ---

class DependencyResolutionError(Exception):
    """Base class for dependency resolution errors."""
    def __init__(self, message: str):
        super().__init__(message)

class CircularDependencyError(DependencyResolutionError):
    """Raised when a circular dependency is detected."""
    def __init__(self, cycle: List[Tuple[str, str]]):
        self.cycle = cycle
        # Format the cycle for the error message
        if cycle:
            cycle_str = " -> ".join([f"{name}({ver})" for name, ver in cycle])
            # Add the start node again if it's a path representation
            if cycle[0] != cycle[-1]: 
                cycle_str += f" -> {cycle[0][0]}({cycle[0][1]})"
        else:
            cycle_str = "(Cycle details unavailable)"
        super().__init__(f"Circular dependency detected: {cycle_str}")

class MissingDependencyError(DependencyResolutionError):
    """Raised when a required dependency cannot be found or no compatible version exists."""
    def __init__(self, requiring_module: Tuple[str, str], missing_dep_name: str, specifier: str):
        self.requiring_module = requiring_module
        self.missing_dep_name = missing_dep_name
        self.specifier = specifier
        req_name, req_ver = requiring_module
        super().__init__(f"Module {req_name}({req_ver}) requires {missing_dep_name} (version {specifier}), but no compatible version was found.")

class VersionConflictError(DependencyResolutionError):
    """Specific error if a module exists but no versions match the specifier."""
    # Currently covered by MissingDependencyError logic, but could be raised specifically
    # in _find_best_compatible_version if available_versions is not empty but result is None.
    pass

# --- Resolver Class ---

class DependencyResolver:
    """
    Resolves dependencies between modules and determines a valid loading order.
    """

    def __init__(self):
        """Initialize the resolver."""
        pass

    def _find_best_compatible_version(
        self,
        dep_name: str,
        specifier_set: SpecifierSet,
        available_versions: Dict[str, ModuleMetadata]
    ) -> Optional[str]:
        """
        Finds the highest version string that satisfies the specifier set.
        Args:
            dep_name: Name of the dependency.
            specifier_set: The packaging.specifiers.SpecifierSet required.
            available_versions: Dictionary of available versions {version_str: meta} for the dep_name.
        Returns:
            The best compatible version string, or None if none found.
        """
        candidate_strings = []
        for version_str in available_versions.keys():
            try:
                # Check if the version string is contained within the specifier set.
                if specifier_set.contains(version_str):
                    candidate_strings.append(version_str)
            except InvalidVersion:
                 # Ignore versions that cannot be parsed according to PEP 440
                 pass 
        
        if not candidate_strings:
            return None

        parsed_candidates: List[Tuple[Any, str]] = [] # Store (Version_obj, original_str)
        for s_version in candidate_strings:
            try:
                # Ensure we are creating Version objects for comparison
                parsed_v = parse_version(s_version)
                parsed_candidates.append((parsed_v, s_version))
            except InvalidVersion:
                # This case should ideally not be reached if specifier_set.contains worked
                # as .contains itself often involves parsing or handling unparseable versions.
                # However, good to be defensive.
                continue # Skip unparseable versions at this stage too
        
        if not parsed_candidates:
            # This could happen if all candidate_strings were somehow unparseable here
            # despite passing the initial .contains() check (unlikely but possible).
            return None

        # Sort by Version object (primary key), then by original string (secondary, for stability if versions parse identically)
        # Default sort for tuples will achieve this if Version objects are correctly comparable.
        # Version objects are rich comparable, so this works as expected.
        parsed_candidates.sort() # Sorts in ascending order

        # The last element after sorting will have the highest version
        # Return its original string representation
        return parsed_candidates[-1][1]


    def _build_dependency_graph(
        self,
        available_modules: Dict[str, Dict[str, ModuleMetadata]]
    ) -> nx.DiGraph:
        """
        Builds a directed graph containing only the selected versions of modules
        and their resolved dependencies.
        Nodes are (module_name, version_string), storing ModuleMetadata.
        Edges go from the selected dependee version to the depender version.
        """
        final_resolved_graph = nx.DiGraph()
        
        # Flatten all available modules for easy lookup by (name, version) tuple
        all_available_meta: Dict[Tuple[str,str], ModuleMetadata] = {}
        for name, versions_dict in available_modules.items():
            for version_str, meta in versions_dict.items():
                all_available_meta[(name, version_str)] = meta

        # Process each initially available module version as a potential start of a chain
        for initial_node_id, initial_meta in all_available_meta.items():
            
            # Queue for BFS-like traversal for the current initial_node_id's chain
            # Stores (node_to_process_id, meta_of_node_to_process)
            queue: List[Tuple[Tuple[str, str], ModuleMetadata]] = []
            
            # Add the initial module to the graph if not already present
            if not final_resolved_graph.has_node(initial_node_id):
                final_resolved_graph.add_node(initial_node_id, meta=initial_meta)
            
            # Start traversal from this initial module to resolve its specific dependencies
            queue.append((initial_node_id, initial_meta))
            # visited_in_current_traversal prevents cycles within a single starting point's resolution
            # and redundant processing if multiple paths lead to the same dependency.
            visited_in_current_traversal = {initial_node_id}

            head = 0
            while head < len(queue):
                depender_node_id, depender_meta = queue[head]
                head += 1

                for dep_info in depender_meta.dependencies:
                    dep_name = dep_info.name
                    dep_specifier_str = dep_info.version_specifier
                    
                    try:
                        specifier_set = SpecifierSet(dep_specifier_str)
                    except InvalidSpecifier:
                        raise DependencyResolutionError(
                            f"Module {depender_node_id[0]}({depender_node_id[1]}) has an invalid version specifier "
                            f"'{dep_specifier_str}' for dependency '{dep_name}'."
                        )

                    versions_for_this_dep = available_modules.get(dep_name)
                    if not versions_for_this_dep:
                        raise MissingDependencyError(depender_node_id, dep_name, dep_specifier_str)

                    selected_dep_version_str = self._find_best_compatible_version(
                        dep_name, specifier_set, versions_for_this_dep
                    )

                    if selected_dep_version_str is None:
                        raise MissingDependencyError(depender_node_id, dep_name, dep_specifier_str)

                    dependee_node_id = (dep_name, selected_dep_version_str)
                    selected_dependee_meta = all_available_meta.get(dependee_node_id)

                    if selected_dependee_meta is None:
                        raise DependencyResolutionError(
                            f"Internal error: Metadata for selected dependency {dependee_node_id} "
                            f"not found in the initial module set."
                        )
                    
                    if not final_resolved_graph.has_node(dependee_node_id):
                        final_resolved_graph.add_node(dependee_node_id, meta=selected_dependee_meta)
                    
                    final_resolved_graph.add_edge(dependee_node_id, depender_node_id)

                    if dependee_node_id not in visited_in_current_traversal:
                        visited_in_current_traversal.add(dependee_node_id)
                        queue.append((dependee_node_id, selected_dependee_meta))
                        
        return final_resolved_graph


    def resolve(
        self,
        available_modules: Dict[str, Dict[str, ModuleMetadata]]
    ) -> List[ModuleMetadata]:
        """
        Resolves dependencies and returns a list of modules in a valid loading order.
        """
        if not available_modules:
            return []

        try:
            graph = self._build_dependency_graph(available_modules)

            if not nx.is_directed_acyclic_graph(graph):
                # Find a cycle to report it
                try:
                    # Note: find_cycle requires edge orientation handling in some nx versions
                    cycle_edges = nx.find_cycle(graph, orientation='original') 
                    # Format cycle for better error message
                    # Cycle edges are (u, v) where u depends on v.
                    # We want to show the path: A -> B -> C -> A
                    # If cycle_edges = [(A, B), (B, C), (C, A)]
                    cycle_nodes = [edge[0] for edge in cycle_edges] 
                    # Add the start node again to explicitly show the loop
                    if cycle_nodes:
                        cycle_nodes.append(cycle_nodes[0])
                    raise CircularDependencyError(cycle_nodes)
                except nx.NetworkXNoCycle:
                     # This path indicates graph is not a DAG but no simple cycle was found?
                     # Or find_cycle failed unexpectedly.
                     raise DependencyResolutionError("Dependency graph is not acyclic, but failed to locate a specific cycle.")
            
            # Perform topological sort (generator)
            sorted_nodes_generator = nx.topological_sort(graph)

            # Filter to ensure only one version per module name ends up in the list,
            # respecting the topological order (first encounter wins).
            resolved_order_meta: List[ModuleMetadata] = []
            included_module_names: set[str] = set()
            
            for node_id in sorted_nodes_generator:
                name, version = node_id # Extract module name
                if name not in included_module_names:
                    meta = graph.nodes[node_id].get('meta')
                    if meta:
                        resolved_order_meta.append(meta)
                        included_module_names.add(name)
                    else:
                        # This should ideally not happen if graph construction is correct
                        raise DependencyResolutionError(f"Internal error: Metadata missing for node {node_id} in dependency graph.")

            return resolved_order_meta

        # Allow specific custom errors from _build_dependency_graph to propagate
        except (MissingDependencyError, CircularDependencyError, DependencyResolutionError):
            raise 
        except Exception as e:
            # Catch any other unexpected errors during resolution
            raise DependencyResolutionError(f"An unexpected error occurred during dependency resolution: {e}") from e 