from typing import Optional
from pydantic import BaseModel, validator

class ReversalRequest(BaseModel):
    snapshot_id: Optional[str] = None
    revert_last_fuck: Optional[bool] = False
    original_correlation_id: Optional[str] = None # Needed if revert_last_fuck is true

    @validator('revert_last_fuck')
    def check_correlation_id_if_reverting_last_fuck(cls, v, values):
        if v and not values.get('original_correlation_id'):
            raise ValueError('original_correlation_id must be provided if revert_last_fuck is true')
        if not v and not values.get('snapshot_id'):
            # This case should be handled by the mutually_exclusive_fields validator,
            # but we can add an explicit check too.
            pass # Let other validators handle if both are None
        return v

    @validator('snapshot_id', always=True)
    def mutually_exclusive_fields(cls, v, values):
        if v and values.get('revert_last_fuck'):
            raise ValueError('snapshot_id and revert_last_fuck are mutually exclusive.')
        if not v and not values.get('revert_last_fuck'):
            raise ValueError('Either snapshot_id or revert_last_fuck (with original_correlation_id) must be provided.')
        return v


class ReversalResponse(BaseModel):
    status: str # e.g., "success", "error", "accepted"
    snapshot_id: Optional[str] = None
    message: Optional[str] = None

class ReversalInitiatedResponse(BaseModel):
    status: str = "initiated"
    message: str
    reversal_id: Optional[str] = None # ID for tracking async reversal if implemented

class DecisionExplanationResponse(BaseModel):
    run_id: str
    decision_index_found: int
    formatted_explanation: str
    log_file_used: str
    event_tag_used: str
    # We could also include the raw context if desired
    # raw_context: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    detail: str 