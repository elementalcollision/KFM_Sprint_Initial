import streamlit as st
import os
import sys

# Adjust Python path to find the src directory if running streamlit from project root
# This assumes the script is in src/transparency/ui/ and project root is three levels up.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from src.transparency.local_explanation_service import (
        LocalKfmExplanationService,
        DEFAULT_SEMANTIC_LOG_FILE as DEFAULT_LOCAL_LOG,
        DEFAULT_DECISION_EVENT_TAG
    )
    from src.transparency.global_analytics_service import (
        GlobalAnalyticsService,
        DEFAULT_LOG_PATTERN as DEFAULT_GLOBAL_LOG_PATTERN
    )
except ImportError as e:
    st.error(f"Error importing services: {e}. Please ensure PYTHONPATH is set correctly or run from project root.")
    st.stop() # Stop the app if services can't be imported

# --- Page Configuration (Optional, but good practice) ---
st.set_page_config(
    page_title="KFM Agent Transparency UI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Main Application Logic ---
def local_explanation_page():
    st.header("KFM Agent - Local Decision Explanation")
    st.write("Retrieve and view a formatted explanation for a specific KFM agent decision based on semantic logs.")

    # --- Inputs for Local Explanation ---
    with st.form(key="local_explanation_form"):
        st.subheader("Input Parameters")
        col1, col2 = st.columns(2)
        with col1:
            run_id = st.text_input("Run ID (Required)", help="The unique identifier for the agent run.")
            log_file_local = st.text_input(
                "Log File Path (Optional)", 
                placeholder=DEFAULT_LOCAL_LOG, 
                help=f"Path to the semantic log file. Defaults to '{DEFAULT_LOCAL_LOG}' if left empty."
            )
        with col2:
            decision_index = st.number_input(
                "Decision Index (0-based, Optional)", 
                min_value=0, 
                value=0, 
                step=1, 
                help="The index of the decision within the run (0 for the first, 1 for the second, etc.)."
            )
            event_tag_local = st.text_input(
                "Decision Event Tag (Optional)", 
                placeholder=DEFAULT_DECISION_EVENT_TAG,
                help=f"The log event tag that identifies KFM decisions. Defaults to '{DEFAULT_DECISION_EVENT_TAG}'."
            )
        
        submit_button_local = st.form_submit_button(label="Get Explanation")

    # --- Processing and Display for Local Explanation ---
    if submit_button_local:
        if not run_id:
            st.error("Run ID is required.")
        else:
            with st.spinner("Fetching explanation..."):
                try:
                    # Use provided log file or default if empty
                    effective_log_file_local = log_file_local if log_file_local else DEFAULT_LOCAL_LOG
                    effective_event_tag_local = event_tag_local if event_tag_local else DEFAULT_DECISION_EVENT_TAG
                    
                    explainer = LocalKfmExplanationService(log_file_path=effective_log_file_local)
                    context = explainer.get_kfm_decision_context(
                        run_id=run_id,
                        decision_event_tag=effective_event_tag_local,
                        decision_index=decision_index
                    )
                    if context:
                        explanation = explainer.format_decision_explanation(context)
                        st.subheader("Formatted Explanation")
                        st.markdown(f"```\n{explanation}\n```") # Using markdown with triple backticks for preformatted block
                        
                        # Optionally show raw context for debugging/power users
                        with st.expander("Show Raw Decision Context (JSON)"):
                            st.json(context)
                    else:
                        st.warning(
                            f"Could not find decision context for Run ID '{run_id}' (Index: {decision_index}, Tag: '{effective_event_tag_local}') "
                            f"in log file '{explainer.log_file_path}'."
                        )
                except FileNotFoundError:
                    st.error(f"Log file not found: '{effective_log_file_local}'. Please check the path.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.exception(e) # Shows stack trace

# --- Placeholder for Global Analytics Page (to be implemented next) ---
def global_analytics_page():
    st.header("KFM Agent - Global Analytics Report")
    st.write("Generate and view a global analytics report by processing multiple semantic log files.")
    st.info("Global Analytics Page: Under Construction.")

    # --- Inputs for Global Analytics ---
    with st.form(key="global_analytics_form"):
        st.subheader("Log Sources")
        log_files_str = st.text_input(
            "Log Files (Optional, comma-separated)", 
            help="Provide a comma-separated list of specific log file paths."
        )
        log_dir = st.text_input(
            "Log Directory (Optional)", 
            help="Provide a directory path. All files matching the pattern below in this directory will be processed."
        )
        log_pattern_global = st.text_input(
            "Log Pattern (if Log Directory is used)", 
            value=DEFAULT_GLOBAL_LOG_PATTERN, 
            help=f"The glob pattern to use when searching for logs in the Log Directory. Default: '{DEFAULT_GLOBAL_LOG_PATTERN}'."
        )
        
        submit_button_global = st.form_submit_button(label="Generate Global Report")
    
    # --- Processing and Display for Global Analytics ---
    if submit_button_global:
        if not log_files_str and not log_dir:
            st.error("Please provide at least one log source: either specific log files or a log directory.")
        else:
            with st.spinner("Generating global report..."):
                try:
                    log_files_list = [lf.strip() for lf in log_files_str.split(',') if lf.strip()] if log_files_str else None
                    
                    # Instantiate and process
                    analytics_service = GlobalAnalyticsService(
                        log_files=log_files_list,
                        log_dir=log_dir if log_dir else None, # Ensure None if empty string
                        log_pattern=log_pattern_global
                    )
                    analytics_service.process_logs() # This prints to console, which is fine for Streamlit script log
                    
                    # Display a summary of processing
                    st.write(f"Log sources found and attempted: {len(analytics_service.log_sources)}")
                    st.write(f"Total log entries processed across all files: {analytics_service.total_log_entries_processed}")

                    if analytics_service.total_log_entries_processed == 0 and not analytics_service.log_sources:
                        st.warning("No log files were specified or found. Report cannot be generated.")
                    elif analytics_service.total_log_entries_processed == 0 and analytics_service.log_sources:
                        st.warning("Log files were specified/found, but they contained no processable entries. Report might be empty or minimal.")

                    report_markdown = analytics_service.generate_report_text()
                    
                    st.subheader("Global Analytics Report")
                    st.markdown(report_markdown) # Render the Markdown report

                    # Optional: Display some key metrics as charts if there's data
                    metrics = analytics_service.get_aggregated_metrics()
                    if metrics.get("kfm_action_counts") and sum(metrics["kfm_action_counts"].values()) > 0:
                        with st.expander("Visual: KFM Action Distribution", expanded=False):
                            # Convert Counter to a format suitable for st.bar_chart (DataFrame or dict)
                            action_counts_df = {
                                "Action Type": list(metrics["kfm_action_counts"].keys()),
                                "Count": list(metrics["kfm_action_counts"].values())
                            }
                            st.bar_chart(action_counts_df, x="Action Type", y="Count")
                    
                    if metrics.get("task_requirement_satisfaction_distribution") and sum(metrics["task_requirement_satisfaction_distribution"].values()) > 0:
                        with st.expander("Visual: Task Satisfaction Distribution", expanded=False):
                            satisfaction_df = {
                                "Satisfaction Score": list(metrics["task_requirement_satisfaction_distribution"].keys()),
                                "Count": list(metrics["task_requirement_satisfaction_distribution"].values())
                            }
                            st.bar_chart(satisfaction_df, x="Satisfaction Score", y="Count")

                except Exception as e:
                    st.error(f"An error occurred while generating the global report: {e}")
                    st.exception(e)

# --- Sidebar for Navigation (Simple version using radio buttons) ---
st.sidebar.title("Navigation")
page_options = {
    "Local Decision Explanation": local_explanation_page,
    "Global Analytics Report": global_analytics_page
}
selected_page_name = st.sidebar.radio("Go to", list(page_options.keys()))

# --- Render the selected page ---
if selected_page_name:
    page_function = page_options[selected_page_name]
    page_function()

# --- To Run (from project root directory): ---
# streamlit run src/transparency/ui/kfm_explain_ui.py 