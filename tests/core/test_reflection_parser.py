import pytest
import json
from pydantic import ValidationError

# Add project root to path if tests are run from a different directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.reflection_parser import parse_llm_reflection_response
from src.core.reflection_schemas import ReflectionOutput, SCHEMA_VERSION

# --- Test Data --- 

VALID_REFLECTION_JSON_STR = json.dumps({
    "schema_version": SCHEMA_VERSION,
    "reflection_run_id": "run_abc",
    "status": "success_no_updates",
    "message": "System performing optimally.",
    "confidence_score": None,
    "heuristic_updates": [],
    "prompt_modifications": []
})

VALID_REFLECTION_JSON_WITH_UPDATES_STR = json.dumps({
    "schema_version": SCHEMA_VERSION,
    "reflection_run_id": "run_def",
    "status": "success_updates_proposed",
    "message": "Suggest increasing confidence threshold.",
    "confidence_score": 0.9,
    "heuristic_updates": [
        {
            "heuristic_id": "fallback_rules",
            "parameter_adjustments": [
                {"parameter_name": "confidence_threshold", "new_value": 0.75, "reasoning": "Increase threshold"}
            ],
            "change_description": "Increase confidence threshold"
        }
    ],
    "prompt_modifications": []
})

INVALID_JSON_STR = "{\"reflection_run_id\": \"run_ghi\", \"status\": \"failure_parsing_input\""
# Missing closing brace

VALID_JSON_INVALID_SCHEMA_STR = json.dumps({
    "run_identifier": "run_jkl", # Wrong key name
    "outcome": "success_no_updates", # Wrong key name
    "notes": "All good."
})

VALID_JSON_MISSING_REQUIRED_FIELD_STR = json.dumps({
    # Missing reflection_run_id, status, message
    "schema_version": SCHEMA_VERSION,
    "confidence_score": None,
    "heuristic_updates": [],
    "prompt_modifications": []
})

NON_JSON_STRING = "This is just plain text, not JSON."

# --- Test Cases --- 

def test_parse_valid_reflection_no_updates():
    """Test parsing a valid reflection output string with no updates."""
    run_id = "run_abc"
    result = parse_llm_reflection_response(VALID_REFLECTION_JSON_STR, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "success_no_updates"
    assert result.reflection_run_id == run_id
    assert result.message == "System performing optimally."
    assert result.confidence_score is None
    assert not result.heuristic_updates
    assert not result.prompt_modifications
    assert result.schema_version == SCHEMA_VERSION

def test_parse_valid_reflection_with_updates():
    """Test parsing a valid reflection output string with updates."""
    run_id = "run_def"
    result = parse_llm_reflection_response(VALID_REFLECTION_JSON_WITH_UPDATES_STR, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "success_updates_proposed"
    assert result.reflection_run_id == run_id
    assert result.message == "Suggest increasing confidence threshold."
    assert result.confidence_score == 0.9
    assert len(result.heuristic_updates) == 1
    assert result.heuristic_updates[0].heuristic_id == "fallback_rules"
    assert len(result.heuristic_updates[0].parameter_adjustments) == 1
    assert result.heuristic_updates[0].parameter_adjustments[0].parameter_name == "confidence_threshold"
    assert result.heuristic_updates[0].parameter_adjustments[0].new_value == 0.75
    assert not result.prompt_modifications
    assert result.schema_version == SCHEMA_VERSION

def test_parse_invalid_json():
    """Test parsing an invalid JSON string."""
    run_id = "run_ghi"
    result = parse_llm_reflection_response(INVALID_JSON_STR, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "failure_parsing_input"
    assert result.reflection_run_id == run_id
    # Check for substring indicating parsing failure
    assert "error during LLM reflection parsing" in result.message or "OutputParserException" in result.message 
    assert result.confidence_score is None
    assert not result.heuristic_updates
    assert not result.prompt_modifications

def test_parse_valid_json_invalid_schema():
    """Test parsing valid JSON that does not match the ReflectionOutput schema."""
    run_id = "run_jkl"
    # This should raise ValidationError inside the parser function
    result = parse_llm_reflection_response(VALID_JSON_INVALID_SCHEMA_STR, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "failure_parsing_input"
    assert result.reflection_run_id == run_id
    # Check for substring indicating parsing/validation failure
    assert "error during LLM reflection parsing" in result.message or "OutputParserException" in result.message
    # Check for specific missing fields mentioned in the error (less reliable)
    # assert "reflection_run_id" in result.message
    assert "status" in result.message
    assert "message" in result.message 
    assert result.confidence_score is None
    assert not result.heuristic_updates
    assert not result.prompt_modifications

def test_parse_valid_json_missing_required():
    """Test parsing valid JSON that matches schema but is missing required fields."""
    run_id = "run_mno" 
    # This should also raise ValidationError inside the parser function
    result = parse_llm_reflection_response(VALID_JSON_MISSING_REQUIRED_FIELD_STR, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "failure_parsing_input"
    # The run_id in the result should be the one passed to the function, not from the (missing) parsed data
    assert result.reflection_run_id == run_id 
    # Check for substring indicating parsing/validation failure
    assert "error during LLM reflection parsing" in result.message or "OutputParserException" in result.message
    # Check that the error message mentions the missing fields (less reliable)
    # assert "reflection_run_id" in result.message # Pydantic should complain about missing required fields
    assert "status" in result.message
    assert "message" in result.message
    assert result.confidence_score is None
    assert not result.heuristic_updates
    assert not result.prompt_modifications

def test_parse_non_json_string():
    """Test parsing a string that is not JSON at all."""
    run_id = "run_pqr"
    # LangChain's Pydantic parser might raise JSONDecodeError or a custom error
    result = parse_llm_reflection_response(NON_JSON_STRING, run_id)
    
    assert isinstance(result, ReflectionOutput)
    assert result.status == "failure_parsing_input"
    assert result.reflection_run_id == run_id
    # The error message might vary depending on how PydanticOutputParser handles non-JSON
    # Check for substring indicating parsing failure
    assert "error during LLM reflection parsing" in result.message or "Invalid json output" in result.message or "OutputParserException" in result.message
    assert result.confidence_score is None
    assert not result.heuristic_updates
    assert not result.prompt_modifications 