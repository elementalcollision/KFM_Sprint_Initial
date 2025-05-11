import pytest
from pydantic import ValidationError

# Add project root to path if tests are run from a different directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.reflection_schemas import (
    ReflectionOutput,
    PromptModification,
    HeuristicUpdate,
    PromptModificationSegment,
    HeuristicParameterAdjustment
)

# --- Tests for PromptModification --- 

def test_prompt_modification_valid_full_template():
    """Test valid PromptModification with only new_full_template."""
    mod = PromptModification(
        prompt_id="test_prompt",
        new_full_template="This is a new template.",
        change_description="Full update."
    )
    assert mod.prompt_id == "test_prompt"
    assert mod.new_full_template == "This is a new template."
    assert mod.segment_modifications is None

def test_prompt_modification_valid_segments():
    """Test valid PromptModification with only segment_modifications."""
    segments = [PromptModificationSegment(segment_id="s1", new_content="c1", modification_action="replace")]
    mod = PromptModification(
        prompt_id="test_prompt",
        segment_modifications=segments,
        change_description="Segment update."
    )
    assert mod.prompt_id == "test_prompt"
    assert mod.new_full_template is None
    assert mod.segment_modifications == segments

def test_prompt_modification_invalid_both_template_and_segments():
    """Test invalid PromptModification specifying both template and segments."""
    with pytest.raises(ValidationError, match="Cannot specify both new_full_template and segment_modifications"):
        PromptModification(
            prompt_id="test_prompt",
            new_full_template="This is a new template.",
            segment_modifications=[PromptModificationSegment(segment_id="s1", new_content="c1")],
            change_description="Invalid update."
        )

def test_prompt_modification_invalid_neither_template_nor_segments():
    """Test invalid PromptModification specifying neither template nor segments."""
    with pytest.raises(ValidationError, match="Must specify either new_full_template or at least one segment_modification"):
        PromptModification(
            prompt_id="test_prompt",
            # Neither new_full_template nor segment_modifications provided
            change_description="Invalid update - missing action."
        )

# --- Tests for ReflectionOutput --- 

@pytest.fixture
def base_reflection_data():
    """Provides base data for ReflectionOutput tests."""
    return {
        "reflection_run_id": "run_123",
        "status": "success_updates_proposed",
        "message": "Updates proposed based on analysis.",
        "confidence_score": 0.85,
        "heuristic_updates": [
            HeuristicUpdate(
                heuristic_id="h1",
                parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="p1", new_value=10)],
                change_description="Adjust p1"
            )
        ],
        "prompt_modifications": []
    }

def test_reflection_output_valid_updates_proposed(base_reflection_data):
    """Test valid ReflectionOutput with updates proposed."""
    output = ReflectionOutput(**base_reflection_data)
    assert output.status == "success_updates_proposed"
    assert output.confidence_score == 0.85
    assert len(output.heuristic_updates) == 1
    assert not output.prompt_modifications

def test_reflection_output_valid_prompt_mod_only(base_reflection_data):
    """Test valid ReflectionOutput with only prompt updates proposed."""
    data = base_reflection_data.copy()
    data["heuristic_updates"] = []
    data["prompt_modifications"] = [
        PromptModification(prompt_id="p1", new_full_template="new", change_description="change p1")
    ]
    output = ReflectionOutput(**data)
    assert output.status == "success_updates_proposed"
    assert output.confidence_score == 0.85
    assert not output.heuristic_updates
    assert len(output.prompt_modifications) == 1

def test_reflection_output_valid_no_updates(base_reflection_data):
    """Test valid ReflectionOutput with status success_no_updates."""
    data = base_reflection_data.copy()
    data["status"] = "success_no_updates"
    data["message"] = "No updates needed."
    data["confidence_score"] = None
    data["heuristic_updates"] = []
    data["prompt_modifications"] = []
    output = ReflectionOutput(**data)
    assert output.status == "success_no_updates"
    assert output.confidence_score is None
    assert not output.heuristic_updates
    assert not output.prompt_modifications

def test_reflection_output_valid_failure(base_reflection_data):
    """Test valid ReflectionOutput with a failure status."""
    data = base_reflection_data.copy()
    data["status"] = "failure_parsing_input"
    data["message"] = "Error parsing LLM response."
    data["confidence_score"] = None
    data["heuristic_updates"] = []
    data["prompt_modifications"] = []
    output = ReflectionOutput(**data)
    assert output.status == "failure_parsing_input"
    assert output.confidence_score is None
    assert not output.heuristic_updates
    assert not output.prompt_modifications

def test_reflection_output_invalid_updates_proposed_missing_updates(base_reflection_data):
    """Test invalid status='success_updates_proposed' with no actual updates."""
    data = base_reflection_data.copy()
    data["heuristic_updates"] = []
    data["prompt_modifications"] = []
    with pytest.raises(ValidationError, match="either heuristic_updates or prompt_modifications must be non-empty"):
        ReflectionOutput(**data)

def test_reflection_output_invalid_updates_proposed_missing_confidence(base_reflection_data):
    """Test invalid status='success_updates_proposed' with missing confidence score."""
    data = base_reflection_data.copy()
    data["confidence_score"] = None
    with pytest.raises(ValidationError, match="confidence_score must be provided"):
        ReflectionOutput(**data)

def test_reflection_output_invalid_no_updates_with_heuristic_updates(base_reflection_data):
    """Test invalid status='success_no_updates' but heuristic updates provided."""
    data = base_reflection_data.copy()
    data["status"] = "success_no_updates"
    data["confidence_score"] = None
    # heuristic_updates IS provided, which is wrong for this status
    data["prompt_modifications"] = []
    with pytest.raises(ValidationError, match="heuristic_updates should be empty"):
        ReflectionOutput(**data)

def test_reflection_output_invalid_failure_with_prompt_updates(base_reflection_data):
    """Test invalid failure status but prompt updates provided."""
    data = base_reflection_data.copy()
    data["status"] = "failure_internal_error"
    data["message"] = "Internal server error."
    data["confidence_score"] = None
    data["heuristic_updates"] = []
    # prompt_modifications IS provided, which is wrong for this status
    data["prompt_modifications"] = [
        PromptModification(prompt_id="p1", new_full_template="new", change_description="change p1")
    ]
    with pytest.raises(ValidationError, match="prompt_modifications should be empty"):
        ReflectionOutput(**data)

def test_reflection_output_invalid_failure_with_confidence(base_reflection_data):
    """Test invalid failure status but confidence score provided."""
    data = base_reflection_data.copy()
    data["status"] = "failure_update_generation"
    data["message"] = "Could not generate updates."
    # confidence_score IS provided, which is wrong for this status
    data["heuristic_updates"] = []
    data["prompt_modifications"] = []
    with pytest.raises(ValidationError, match="confidence_score should not be provided"):
        ReflectionOutput(**data) 