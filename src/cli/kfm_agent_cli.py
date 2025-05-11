import argparse
import sys
import os

# Assuming the script is run from the root of the project or PYTHONPATH is set up
# to find the 'src' directory.
try:
    from src.transparency.local_explanation_service import LocalKfmExplanationService, DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG
    from src.transparency.global_analytics_service import GlobalAnalyticsService, DEFAULT_LOG_PATTERN as DEFAULT_GLOBAL_LOG_PATTERN
    from src.core.logging_setup import setup_logging # For consistent logging if needed
    # Define PROJECT_ROOT based on the assumption that this script is in src/cli
    # and the project root is two levels up.
    PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))
except ImportError:
    # This block allows the script to be run directly from the 'src/cli' directory
    # or if 'src' is not in PYTHONPATH, by temporarily adding the project root.
    # This is primarily for local development convenience.
    PACKAGE_PARENT = '..'
    SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
    # The path to append is the project root
    PROJECT_ROOT_FOR_SYSPATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT, PACKAGE_PARENT))
    sys.path.append(PROJECT_ROOT_FOR_SYSPATH)
    PROJECT_ROOT = PROJECT_ROOT_FOR_SYSPATH # Define PROJECT_ROOT here as well for consistency
    try:
        from src.transparency.local_explanation_service import LocalKfmExplanationService, DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG
        from src.transparency.global_analytics_service import GlobalAnalyticsService, DEFAULT_LOG_PATTERN as DEFAULT_GLOBAL_LOG_PATTERN
        from src.core.logging_setup import setup_logging
    except ImportError as e:
        print(f"Critical Import Error: Could not import necessary modules. Make sure you are running from the project root or have PYTHONPATH configured. {e}")
        sys.exit(1)

# Setup a basic logger for the CLI tool itself if needed
# cli_logger = setup_logging('KfmAgentCli', level='INFO', console=True, file=False)

def handle_explain_decision(args):
    """Handles the 'explain-decision' command."""
    explainer = LocalKfmExplanationService(log_file_path=args.log_file)
    
    context = explainer.get_kfm_decision_context(
        run_id=args.run_id,
        decision_event_tag=args.event_tag,
        decision_index=args.decision_index
    )
    
    if context:
        explanation = explainer.format_decision_explanation(context)
        print("\n" + explanation)
    else:
        print(f"Could not find decision context for run_id='{args.run_id}', index={args.decision_index}, tag='{args.event_tag}' in log file '{explainer.log_file_path}'.")

def handle_generate_global_report(args):
    """Handles the 'generate-global-report' command."""
    print("Generating Global Analytics Report...")
    log_files_list = args.log_files.split(',') if args.log_files else None
    
    service = GlobalAnalyticsService(
        log_files=log_files_list,
        log_dir=args.log_dir,
        log_pattern=args.log_pattern
    )
    service.process_logs()
    report_content = service.generate_report_text()

    if args.output_file:
        try:
            with open(args.output_file, 'w') as f:
                f.write(report_content)
            print(f"Global report saved to: {args.output_file}")
        except IOError as e:
            print(f"Error writing report to file '{args.output_file}': {e}", file=sys.stderr)
            # Optionally print to console as fallback
            print("\n--- Global Report ---")
            print(report_content)
    else:
        print("\n--- Global Report ---")
        print(report_content)

def handle_ui(args):
    """Handles the 'ui' command to launch the Streamlit application."""
    script_path = os.path.join(PROJECT_ROOT, "src", "transparency", "ui", "kfm_explain_ui.py")
    # Check if the script exists
    if not os.path.exists(script_path):
        print(f"Error: Streamlit UI script not found at {script_path}", file=sys.stderr)
        print("Please ensure the KFM Explain UI is correctly placed.", file=sys.stderr)
        sys.exit(1)

    print(f"Launching KFM Transparency UI from: {script_path}")
    print("You can typically stop the Streamlit server with Ctrl+C in the terminal where it runs.")
    
    try:
        import subprocess
        # Note: `streamlit run ...` is a blocking call.
        # The Python script will wait here until Streamlit is closed.
        process = subprocess.Popen(["streamlit", "run", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate() # Wait for it to finish, capture output
        
        if stdout:
            print("Streamlit UI stdout:", stdout.decode())
        if stderr:
            print("Streamlit UI stderr:", stderr.decode(), file=sys.stderr)
        
        if process.returncode != 0:
            print(f"Streamlit UI exited with error code {process.returncode}.", file=sys.stderr)
        else:
            print("Streamlit UI closed.")
            
    except FileNotFoundError:
        print("Error: 'streamlit' command not found. Is Streamlit installed and in your PATH?", file=sys.stderr)
        print("Try: pip install streamlit", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred while trying to launch Streamlit: {e}", file=sys.stderr)

def main(raw_args=None):
    """Main entry point for the KFM Agent CLI."""
    parser = argparse.ArgumentParser(description="KFM Agent CLI - Tools for interacting with and inspecting the KFM Agent.")
    subparsers = parser.add_subparsers(title="Commands", dest="command", help="Available commands", required=True)

    # --- explain-decision command ---
    explain_parser = subparsers.add_parser("explain-decision", help="Get an explanation for a specific KFM agent decision from logs.")
    explain_parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="The run_id of the agent execution to inspect."
    )
    explain_parser.add_argument(
        "--decision-index",
        type=int,
        default=0,
        help=f"The 0-based index of the decision to explain if multiple decisions occurred in the run (default: 0)."
    )
    explain_parser.add_argument(
        "--log-file",
        type=str,
        default=DEFAULT_SEMANTIC_LOG_FILE,
        help=f"Path to the semantic log file (default: {DEFAULT_SEMANTIC_LOG_FILE})."
    )
    explain_parser.add_argument(
        "--event-tag",
        type=str,
        default=DEFAULT_DECISION_EVENT_TAG,
        help=f"The log event tag identifying KFM decisions. Default: {DEFAULT_DECISION_EVENT_TAG}"
    )
    explain_parser.set_defaults(func=handle_explain_decision)

    # --- Subparser for generate-global-report ---
    report_parser = subparsers.add_parser(
        "generate-global-report", 
        help="Generates a global analytics report from KFM semantic logs.",
        description="Aggregates data from one or more semantic log files (semantic_state_details.log or similar) to produce a summary report on KFM agent behavior, decision patterns, and performance metrics."
    )
    report_parser.add_argument(
        "--log-files",
        type=str,
        help="Comma-separated list of specific log file paths to process."
    )
    report_parser.add_argument(
        "--log-dir",
        type=str,
        help="Directory containing log files to process (all files matching --log-pattern will be used)."
    )
    report_parser.add_argument(
        "--log-pattern",
        type=str,
        default=DEFAULT_GLOBAL_LOG_PATTERN,
        help=f"Glob pattern to match log files in --log-dir. Default: {DEFAULT_GLOBAL_LOG_PATTERN}"
    )
    report_parser.add_argument(
        "--output-file",
        type=str,
        help="(Optional) Path to save the generated Markdown report. Prints to console if not specified."
    )
    report_parser.set_defaults(func=handle_generate_global_report)

    # --- Subparser for ui ---
    ui_parser = subparsers.add_parser(
        "ui",
        help="Launches the KFM Transparency Streamlit Web UI.",
        description="Starts a local Streamlit web server to provide an interactive interface for local decision explanations and global analytics reports."
    )
    ui_parser.set_defaults(func=handle_ui)

    if not raw_args and len(sys.argv) == 1: # No command provided
        parser.print_help(sys.stderr)
        sys.exit(1)
    if not raw_args: # Normal execution
        args = parser.parse_args()
    else: # For testing or programmatic call
        args = parser.parse_args(raw_args)

    if hasattr(args, 'func'):
        args.func(args)
    else:
        # This case should ideally not be reached if subparsers are 'required'
        # and a default func is set for each. But as a fallback:
        parser.print_help(sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 