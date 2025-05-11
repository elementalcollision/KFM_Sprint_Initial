from typing import Type
import json

from pydantic import ValidationError
from langchain_core.output_parsers import PydanticOutputParser

from .reflection_schemas import ReflectionOutput, SCHEMA_VERSION # Assuming reflection_schemas.py is in the same directory (src/core)

def get_reflection_output_parser() -> PydanticOutputParser[ReflectionOutput]:
    """
    Returns a PydanticOutputParser configured for the ReflectionOutput schema.
    This parser can be used to get format instructions for the LLM and to parse its output.
    """
    return PydanticOutputParser(pydantic_object=ReflectionOutput)

def parse_llm_reflection_response(
    llm_response_str: str,
    reflection_run_id: str
) -> ReflectionOutput:
    """
    Parses the raw string output from an LLM, attempting to convert it into a ReflectionOutput object.

    Args:
        llm_response_str: The raw string response from the LLM.
        reflection_run_id: The unique ID for this reflection run.

    Returns:
        A ReflectionOutput object. If parsing is successful, it contains the parsed data.
        If parsing fails, the status field will indicate 'failure_parsing_input',
        and the message field will contain error details.
    """
    parser = get_reflection_output_parser()

    try:
        # PydanticOutputParser expects a string. If the LLM is not guaranteed
        # to return a string that directly maps to the Pydantic model (e.g., it might be wrapped),
        # this parse method handles it.
        # If the LLM is supposed to return JSON that directly maps to ReflectionOutput,
        # one might also consider ReflectionOutput.model_validate_json(llm_response_str)
        # after ensuring llm_response_str is valid JSON.
        # However, PydanticOutputParser is designed to work with LangChain's prompting.
        parsed_output = parser.parse(llm_response_str)
        
        # Ensure the parsed output is indeed a ReflectionOutput instance
        # and fill in potentially missing server-side fields if the LLM didn't provide them.
        # (Though PydanticOutputParser should construct the correct type)
        if isinstance(parsed_output, ReflectionOutput):
            # If LLM somehow omitted these, though schema has defaults/requirements
            if not parsed_output.reflection_run_id:
                 parsed_output.reflection_run_id = reflection_run_id
            if not parsed_output.schema_version:
                parsed_output.schema_version = SCHEMA_VERSION
            return parsed_output
        else:
            # This case should ideally not be hit if PydanticOutputParser works as expected
            return ReflectionOutput(
                reflection_run_id=reflection_run_id,
                status="failure_parsing_input",
                message=f"Parser returned an unexpected type: {type(parsed_output).__name__}. Expected ReflectionOutput.",
                schema_version=SCHEMA_VERSION,
                heuristic_updates=[],
                prompt_modifications=[]
            )

    except ValidationError as e:
        error_message = f"Pydantic validation error while parsing LLM reflection: {e.errors()}"
        return ReflectionOutput(
            reflection_run_id=reflection_run_id,
            status="failure_parsing_input",
            message=error_message,
            schema_version=SCHEMA_VERSION,
            heuristic_updates=[],
            prompt_modifications=[]
        )
    except json.JSONDecodeError as e:
        error_message = f"JSON decoding error while parsing LLM reflection: {e.msg}. Response was: {llm_response_str[:500]}..." # Show start of problematic string
        return ReflectionOutput(
            reflection_run_id=reflection_run_id,
            status="failure_parsing_input",
            message=error_message,
            schema_version=SCHEMA_VERSION,
            heuristic_updates=[],
            prompt_modifications=[]
        )
    except Exception as e:
        # Catch-all for other unexpected parsing errors
        error_message = f"Unexpected error during LLM reflection parsing: {str(e)}. Type: {type(e).__name__}."
        return ReflectionOutput(
            reflection_run_id=reflection_run_id,
            status="failure_parsing_input", # Or "failure_internal_error" if it seems more systemic
            message=error_message,
            schema_version=SCHEMA_VERSION,
            heuristic_updates=[],
            prompt_modifications=[]
        ) 