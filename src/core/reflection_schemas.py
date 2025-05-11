from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, conlist, confloat, model_validator

# Schema Version
SCHEMA_VERSION = "1.0.0"


class HeuristicParameterAdjustment(BaseModel):
    parameter_name: str = Field(..., description="The name of the heuristic parameter to adjust.")
    new_value: Any = Field(..., description="The new value for the parameter.")
    reasoning: Optional[str] = Field(None, description="Reasoning for this specific parameter adjustment.")


class HeuristicUpdate(BaseModel):
    heuristic_id: str = Field(..., description="Identifier for the heuristic to be updated.")
    new_definition_code: Optional[str] = Field(
        None,
        description="The new Python code snippet for the heuristic's logic. Required if update is definition-related."
    )
    parameter_adjustments: Optional[List[HeuristicParameterAdjustment]] = Field(
        None,
        description="A list of specific parameter adjustments for the heuristic."
    )
    is_active: Optional[bool] = Field(
        None,
        description="New activation status for the heuristic (True for active, False for inactive)."
    )
    change_description: str = Field(
        ...,
        description="Human-readable description of what this heuristic update entails and why it's proposed."
    )


class PromptModificationSegment(BaseModel):
    segment_id: str = Field(..., description="Identifier for the specific segment or section of the prompt to be modified.")
    new_content: str = Field(..., description="The new content for this prompt segment.")
    modification_action: Literal["replace", "append", "prepend", "delete"] = Field(
        "replace",
        description="Action to take on the segment (e.g., replace its content, append to it, etc.)."
    )


class PromptModification(BaseModel):
    prompt_id: str = Field(
        ...,
        description="Identifier for the prompt to be modified (e.g., 'kfm_planner_main_prompt', 'reflection_prompt_template')."
    )
    new_full_template: Optional[str] = Field(
        None,
        description="The complete new template content for the prompt. Use this for wholesale changes."
    )
    segment_modifications: Optional[List[PromptModificationSegment]] = Field(
        None,
        description="A list of modifications to specific, predefined segments within the prompt."
    )
    change_description: str = Field(
        ...,
        description="Human-readable description of what this prompt modification entails and why it's proposed."
    )

    @model_validator(mode='after')
    def check_exclusive_modifications(cls, values: 'PromptModification') -> 'PromptModification':
        new_full_template = values.new_full_template
        segment_modifications = values.segment_modifications

        if new_full_template is not None and segment_modifications is not None:
            raise ValueError("Cannot specify both new_full_template and segment_modifications. Choose one.")
        if new_full_template is None and segment_modifications is None:
            raise ValueError("Must specify either new_full_template or at least one segment_modification.")
        return values


class ReflectionOutput(BaseModel):
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="Version of this reflection output schema.",
        frozen=True
    )
    reflection_run_id: str = Field(..., description="Unique identifier for this specific reflection run.")
    status: Literal[
        "success_updates_proposed",
        "success_no_updates",
        "failure_parsing_input",
        "failure_update_generation",
        "failure_internal_error"
    ] = Field(
        ...,
        description="Status of the reflection process."
    )
    message: str = Field(
        ...,
        description="A message providing reasoning for proposed updates, an explanation if no updates are proposed, or an error message if the status indicates a failure."
    )
    confidence_score: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None,
        description="Confidence score (0.0 to 1.0) in the proposed updates. Relevant if status is 'success_updates_proposed'."
    )
    heuristic_updates: List[HeuristicUpdate] = Field( # Changed to non-optional with default_factory
        default_factory=list,
        description="List of proposed updates to heuristics. Empty if no heuristic updates are proposed."
    )
    prompt_modifications: List[PromptModification] = Field( # Changed to non-optional with default_factory
        default_factory=list,
        description="List of proposed modifications to prompts. Empty if no prompt modifications are proposed."
    )

    @model_validator(mode='after')
    def check_updates_logic(cls, values: 'ReflectionOutput') -> 'ReflectionOutput':
        status = values.status
        heuristic_updates = values.heuristic_updates
        prompt_modifications = values.prompt_modifications
        confidence_score = values.confidence_score

        if status == "success_updates_proposed":
            if not heuristic_updates and not prompt_modifications:
                raise ValueError("If status is 'success_updates_proposed', either heuristic_updates or prompt_modifications must be non-empty.")
            if confidence_score is None:
                raise ValueError("If status is 'success_updates_proposed', confidence_score must be provided.")
        elif status in ["success_no_updates", "failure_parsing_input", "failure_update_generation", "failure_internal_error"]:
            if heuristic_updates: # Check if list is not empty
                raise ValueError(f"If status is '{status}', heuristic_updates should be empty.")
            if prompt_modifications: # Check if list is not empty
                raise ValueError(f"If status is '{status}', prompt_modifications should be empty.")
            if confidence_score is not None:
                raise ValueError(f"If status is '{status}', confidence_score should not be provided.")
        return values 