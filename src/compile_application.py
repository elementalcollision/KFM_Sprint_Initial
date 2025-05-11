# src/compile_application.py
import argparse
import json
import os
import sys
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.compiler import KFMGraphCompiler, compile_kfm_graph
from src.kfm_agent import save_graph_visualization
from src.logger import setup_logger

app_logger = setup_logger('CompileApp')

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a JSON file.
    
    Args:
        config_path (str): Path to the config file
        
    Returns:
        Dict[str, Any]: Configuration parameters
    """
    app_logger.info(f"Loading config from {config_path}")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        app_logger.info(f"Config loaded successfully: {list(config.keys())}")
        return config
    except Exception as e:
        app_logger.error(f"Error loading config: {e}")
        return {}

def parse_args():
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Compile KFM LangGraph Application")
    parser.add_argument("--config", "-c", help="Path to config file")
    parser.add_argument("--debug", "-d", action="store_true", help="Compile in debug mode")
    parser.add_argument("--visualize", "-v", action="store_true", help="Generate visualization")
    parser.add_argument("--export", "-e", help="Export compiled graph to specified path")
    parser.add_argument("--output-dir", "-o", default="./compiled_graph", 
                        help="Directory to save outputs when not specifying explicit paths")
    return parser.parse_args()

def main():
    """Main function to run the compilation process."""
    args = parse_args()
    
    # Prepare output directory if needed
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)
    
    # Load config if specified
    config = {}
    if args.config:
        config = load_config(args.config)
    
    # Create compiler
    compiler = KFMGraphCompiler(config)
    
    # Compile the graph
    try:
        app_logger.info(f"Starting compilation (debug_mode={args.debug})")
        kfm_app, components = compiler.compile(debug_mode=args.debug)
        app_logger.info("Compilation successful")
        
        # Generate visualization if requested
        if args.visualize:
            if args.export:
                vis_path = args.export.replace('.json', '.png')
            else:
                vis_path = os.path.join(args.output_dir, "kfm_graph.png")
                
            app_logger.info(f"Generating visualization to {vis_path}")
            if save_graph_visualization(kfm_app, vis_path):
                app_logger.info(f"Visualization saved to {vis_path}")
            else:
                app_logger.warning("Failed to save visualization")
        
        # Export if requested
        if args.export:
            export_path = args.export
        else:
            export_path = os.path.join(args.output_dir, "compiled_graph.json")
            
        app_logger.info(f"Exporting compiled graph to {export_path}")
        if compiler.export_compiled_graph(kfm_app, export_path):
            app_logger.info(f"Graph exported to {export_path}")
        else:
            app_logger.warning("Failed to export graph")
        
        # Print graph statistics
        node_count = len(kfm_app.nodes)
        app_logger.info(f"Compilation statistics: {node_count} nodes")
        app_logger.info("Compilation process completed successfully")
        
        return 0
    except Exception as e:
        app_logger.error(f"Compilation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 