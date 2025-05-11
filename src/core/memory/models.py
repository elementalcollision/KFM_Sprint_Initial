from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import datetime
import uuid

# Define the structure for component metrics
class ComponentMetrics(BaseModel):
    accuracy: Optional[float] = None
    latency: Optional[float] = None
    # Add other relevant metrics if needed
    # cost: Optional[float] = None
    # token_count: Optional[int] = None

class AgentExperienceLog(BaseModel):
    """Represents a snapshot of the agent's state and actions for memory storage."""
    # Contextual Info
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)
    current_task_requirements: Dict[str, Any] # E.g., required accuracy, latency constraints
    previous_component_name: Optional[str] = None
    previous_component_metrics: Optional[ComponentMetrics] = None

    # Planner Decision
    planner_llm_input: str # The prompt/context given to the planner
    planner_llm_output: str # The raw output/decision from the planner
    kfm_action_taken: Literal["Kill", "Marry", "Fuck", "No Action"]

    # Action Execution & Outcome
    selected_component_name: Optional[str] = None # Component chosen by Kill/Marry/Fuck
    execution_outcome_metrics: Optional[ComponentMetrics] = None # Metrics *after* action execution
    action_execution_error: Optional[str] = None # If execution failed

    # Reflection (Optional)
    reflection_llm_output: Optional[str] = None

    # Overall Assessment
    outcome_success: bool # Was the overall goal achieved / state improved by this step?
    # This needs a clear definition based on metrics/requirements comparison

    # --- Fields primarily for Chroma interaction (can be generated dynamically) ---
    # We generate these before calling chroma add, they don't need to be part of the core log input
    # experience_summary_for_embedding: Optional[str] = None # Generated text for embedding
    # chroma_id: str = Field(default_factory=lambda: uuid.uuid4().hex) # Generated before storage

class AgentQueryContext(BaseModel):
    """Represents the context provided to query agent memory."""
    # Core context elements used to generate the query embedding text
    current_task_requirements: Dict[str, Any]
    current_component_name: Optional[str] = None
    current_component_metrics: Optional[ComponentMetrics] = None 
    # Optional: Explicit text override if natural language query is provided elsewhere
    explicit_query_text: Optional[str] = None 
    # Optional: Add other state elements if relevant for context generation
    # last_action: Optional[str] = None 
    # recent_errors: Optional[List[str]] = None 