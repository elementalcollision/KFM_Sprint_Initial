# src/compiler.py
import logging
import os
from typing import Dict, Any, Tuple, Optional, List, Union
from langgraph.graph import StateGraph
from src.state_types import KFMAgentState
from src.kfm_agent import create_kfm_agent_graph, create_debug_kfm_agent_graph
from src.logger import setup_logger
import traceback
import json
import datetime

# Try to import visualization module
try:
    from src.visualization import visualize_timeline, create_execution_report
except ImportError:
    # Create placeholder functions if visualization module is not available
    def visualize_timeline(*args, **kwargs): return None
    def create_execution_report(*args, **kwargs): return None

compiler_logger = setup_logger('KFMCompiler')

class KFMGraphCompiler:
    """Handles compilation and validation of the KFM LangGraph application."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the compiler with optional configuration.
        
        Args:
            config (Optional[Dict[str, Any]]): Configuration parameters
        """
        self.config = config or {}
        self.enable_enhanced_logging = self.config.get('enable_enhanced_logging', True)
        self.log_level = self.config.get('log_level', 'INFO')
        self.log_directory = self.config.get('log_directory', 'logs/compiler')
        
        # Create log directory if it doesn't exist
        if self.enable_enhanced_logging:
            os.makedirs(self.log_directory, exist_ok=True)
            
        compiler_logger.info("KFM Graph Compiler initialized")
        
        if self.enable_enhanced_logging:
            compiler_logger.info(f"Enhanced logging enabled at level {self.log_level}")
            compiler_logger.info(f"Logs will be stored in {self.log_directory}")
    
    def compile(self, debug_mode: bool = False) -> Tuple[StateGraph, Dict[str, Any]]:
        """Compile the KFM Agent LangGraph with the specified options.
        
        Args:
            debug_mode (bool): Whether to compile in debug mode with instrumented nodes
            
        Returns:
            Tuple[StateGraph, Dict[str, Any]]: The compiled graph and components
        """
        # Start tracking compilation metrics
        start_time = datetime.datetime.now()
        compilation_id = f"compile_{start_time.strftime('%Y%m%d%H%M%S')}"
        
        compiler_logger.info(f"Compiling KFM Graph (debug_mode={debug_mode}, id={compilation_id})")
        
        # Enhanced logging for compilation configuration
        if self.enable_enhanced_logging:
            config_log = {
                "compilation_id": compilation_id,
                "timestamp": start_time.isoformat(),
                "debug_mode": debug_mode,
                "compiler_config": self.config
            }
            self._log_compilation_event("compilation_start", config_log)
        
        # Select the appropriate graph creation function based on debug mode
        if debug_mode:
            compiler_logger.info("Using debug graph creation")
            graph_creator = create_debug_kfm_agent_graph
        else:
            compiler_logger.info("Using standard graph creation")
            graph_creator = create_kfm_agent_graph
        
        # Apply any additional configuration
        threading_model = self.config.get('threading_model', 'sequential')
        compiler_logger.info(f"Using threading model: {threading_model}")
        
        # Compile with error handling
        try:
            # Track compilation steps
            step_times = {}
            
            # Step 1: Create the graph
            step_start = datetime.datetime.now()
            kfm_app, components = graph_creator()
            step_times["graph_creation"] = (datetime.datetime.now() - step_start).total_seconds()
            
            compiler_logger.info("Graph compiled successfully")
            
            # Step 2: Validate the graph structure
            step_start = datetime.datetime.now()
            validation_result = self.validate_graph_structure(kfm_app)
            step_times["validation"] = (datetime.datetime.now() - step_start).total_seconds()
            
            if not validation_result['valid']:
                compiler_logger.warning(f"Graph validation issues: {validation_result['issues']}")
            
            # Enhanced logging for successful compilation
            if self.enable_enhanced_logging:
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                completion_log = {
                    "compilation_id": compilation_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration": duration,
                    "success": True,
                    "step_times": step_times,
                    "validation_result": validation_result
                }
                self._log_compilation_event("compilation_complete", completion_log)
                
                # Create a visualization of the graph structure if available
                try:
                    # This would be implemented in the visualization module
                    # visualization_path = visualize_graph_structure(kfm_app, 
                    #     os.path.join(self.log_directory, f"graph_{compilation_id}.png"))
                    pass
                except Exception as viz_error:
                    compiler_logger.warning(f"Error creating graph visualization: {viz_error}")
            
            return kfm_app, components
        except Exception as e:
            error_msg = f"Error during graph compilation: {str(e)}"
            compiler_logger.error(error_msg)
            
            # Enhanced logging for failed compilation
            if self.enable_enhanced_logging:
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                error_log = {
                    "compilation_id": compilation_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration": duration,
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                self._log_compilation_event("compilation_error", error_log)
            
            raise RuntimeError(error_msg) from e

    def _log_compilation_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log a compilation event to a file.
        
        Args:
            event_type: Type of event (start, complete, error)
            event_data: Data to log
        """
        try:
            log_file = os.path.join(self.log_directory, f"{event_type}.jsonl")
            
            # Convert event data to JSON and append to log file
            with open(log_file, 'a') as f:
                f.write(json.dumps(event_data) + '\n')
                
        except Exception as e:
            compiler_logger.error(f"Error logging compilation event: {e}")

    def validate_graph_structure(self, graph: StateGraph) -> Dict[str, Any]:
        """Validate the compiled graph structure.
        
        Args:
            graph (StateGraph): The compiled graph to validate
            
        Returns:
            Dict[str, Any]: Validation results with 'valid' flag and any 'issues'
        """
        compiler_logger.info("Validating graph structure")
        issues = []
        
        try:
            # Check for required nodes
            required_nodes = ["monitor", "decide", "execute", "reflect"]
            graph_nodes = list(graph.nodes.keys())  # Access nodes using the StateGraph API
            
            for node in required_nodes:
                if node not in graph_nodes:
                    issues.append(f"Required node '{node}' missing from graph")
            
            # Check for entry point
            if not hasattr(graph, 'entry_point') or not graph.entry_point:
                issues.append("No entry point defined in graph")
            
            # Check for proper edge connections
            edges = self._get_graph_edges(graph)
            expected_edges = [
                ("monitor", "decide"),
                ("decide", "execute"),
                ("execute", "reflect")
            ]
            
            for source, target in expected_edges:
                if not self._has_edge(edges, source, target):
                    issues.append(f"Expected edge '{source}' -> '{target}' not found")
            
            # Validate conditional edges
            if not self._has_conditional_edge(graph, "reflect"):
                issues.append("Required conditional edge from 'reflect' node not found")
            
            valid = len(issues) == 0
            return {"valid": valid, "issues": issues}
        except Exception as e:
            compiler_logger.error(f"Error during graph validation: {str(e)}")
            return {"valid": False, "issues": [f"Validation error: {str(e)}"]}
    
    def _get_graph_edges(self, graph: StateGraph) -> List[Tuple[str, str]]:
        """Extract edges from the graph.
        
        Args:
            graph (StateGraph): The compiled graph
            
        Returns:
            List[Tuple[str, str]]: List of (source, target) edges
        """
        # This is a helper method to extract edges in a format suitable for validation
        try:
            # The actual implementation depends on LangGraph API
            # This is a best guess based on common graph APIs
            edges = []
            for source_node in graph.nodes:
                for target_node in graph.get_next_nodes(source_node):
                    edges.append((source_node, target_node))
            return edges
        except Exception as e:
            compiler_logger.warning(f"Could not extract edges: {e}")
            return []
    
    def _has_edge(self, edges: List[Tuple[str, str]], source: str, target: str) -> bool:
        """Check if a specific edge exists in the edge list.
        
        Args:
            edges (List[Tuple[str, str]]): List of edges
            source (str): Source node
            target (str): Target node
            
        Returns:
            bool: True if the edge exists
        """
        return (source, target) in edges
    
    def _has_conditional_edge(self, graph: StateGraph, node_name: str) -> bool:
        """Check if a node has conditional edges.
        
        Args:
            graph (StateGraph): The compiled graph
            node_name (str): Node to check for conditional edges
            
        Returns:
            bool: True if the node has conditional edges
        """
        try:
            # This implementation depends on the LangGraph API
            # This is a best guess based on common graph APIs
            return hasattr(graph, 'conditional_edges') and node_name in graph.conditional_edges
        except Exception as e:
            compiler_logger.warning(f"Could not check conditional edges: {e}")
            return False
    
    def export_compiled_graph(self, graph: StateGraph, output_path: str) -> bool:
        """Export the compiled graph for deployment.
        
        Args:
            graph (StateGraph): The compiled graph
            output_path (str): Path to save the exported graph
            
        Returns:
            bool: True if successful, False otherwise
        """
        compiler_logger.info(f"Exporting compiled graph to {output_path}")
        try:
            # Create the directory if it doesn't exist
            dir_path = os.path.dirname(output_path)
            if dir_path:  # Only create if there's a directory component
                os.makedirs(dir_path, exist_ok=True)
            
            # Export the graph configuration using LangGraph's serialization
            # The actual implementation depends on LangGraph's serialization support
            try:
                # Try to use LangGraph's serialization if available
                if hasattr(graph, 'serialize'):
                    serialized_graph = graph.serialize()
                    with open(output_path, 'wb') as f:
                        f.write(serialized_graph)
                else:
                    # Fallback - create a JSON representation of the graph structure
                    graph_structure = {
                        "nodes": list(graph.nodes.keys()),
                        "entry_point": getattr(graph, 'entry_point', None),
                        "export_date": str(os.path.basename(__file__))
                    }
                    with open(output_path, 'w') as f:
                        json.dump(graph_structure, f, indent=2)
                    
                compiler_logger.info("Graph exported successfully")
                return True
            except Exception as serialize_error:
                compiler_logger.error(f"Error serializing graph: {serialize_error}")
                return False
                
        except Exception as e:
            compiler_logger.error(f"Error exporting graph: {str(e)}")
            return False

# Convenient function to create and compile in one step
def compile_kfm_graph(config: Optional[Dict[str, Any]] = None, 
                     debug_mode: bool = False) -> Tuple[StateGraph, Dict[str, Any]]:
    """Create and compile a KFM graph in one step.
    
    Args:
        config (Optional[Dict[str, Any]]): Configuration parameters
        debug_mode (bool): Whether to compile in debug mode
        
    Returns:
        Tuple[StateGraph, Dict[str, Any]]: The compiled graph and components
    """
    compiler = KFMGraphCompiler(config)
    return compiler.compile(debug_mode=debug_mode)

def run_with_enhanced_logging(graph: StateGraph, initial_state: KFMAgentState, 
                              config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run the graph with enhanced logging and performance tracking.
    
    Args:
        graph: The compiled LangGraph application
        initial_state: Initial state for the graph
        config: Optional configuration parameters
        
    Returns:
        Dict containing the final state and execution metrics
    """
    from src.tracing import set_trace_enabled, get_trace_history, create_execution_summary
    
    config = config or {}
    run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    compiler_logger.info(f"Starting enhanced logging run {run_id}")
    
    # Create log directory
    log_dir = config.get('log_directory', 'logs/runs')
    run_log_dir = os.path.join(log_dir, run_id)
    os.makedirs(run_log_dir, exist_ok=True)
    
    # Enable tracing
    set_trace_enabled(True)
    
    # Run the graph
    start_time = datetime.datetime.now()
    try:
        result = graph.invoke(initial_state)
        success = True
        error = None
    except Exception as e:
        result = None
        success = False
        error = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        compiler_logger.error(f"Error running graph: {e}")
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Get trace history
    trace_history = get_trace_history()
    
    # Create summary
    execution_summary = create_execution_summary()
    
    # Save results
    run_data = {
        "run_id": run_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration": duration,
        "success": success,
        "error": error,
        "execution_summary": execution_summary
    }
    
    # Save the run data
    try:
        with open(os.path.join(run_log_dir, "run_data.json"), 'w') as f:
            json.dump(run_data, f, indent=2, default=str)
    except Exception as e:
        compiler_logger.error(f"Error saving run data: {e}")
    
    # Create visualizations if the visualization module is available
    try:
        # Create a timeline visualization
        timeline_path = visualize_timeline(
            trace_history,
            output_path=os.path.join(run_log_dir, "timeline.png")
        )
        
        # Create an execution report
        report_path = create_execution_report(
            trace_history,
            output_path=os.path.join(run_log_dir, "report.html")
        )
        
        if timeline_path:
            compiler_logger.info(f"Timeline visualization saved to {timeline_path}")
        if report_path:
            compiler_logger.info(f"Execution report saved to {report_path}")
    except Exception as e:
        compiler_logger.error(f"Error creating visualizations: {e}")
    
    return {
        "result": result,
        "success": success,
        "duration": duration,
        "run_id": run_id,
        "log_directory": run_log_dir,
        "execution_summary": execution_summary
    } 