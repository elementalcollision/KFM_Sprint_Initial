from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class VerificationCheckResult(BaseModel):
    """Represents the result of a single verification check."""
    check_name: str
    passed: bool
    component_id: Optional[str] = None # ID of the component being checked, if applicable
    attribute_checked: Optional[str] = None # Specific attribute checked, if applicable
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    message: Optional[str] = None # General message, or details of failure/discrepancy
    discrepancies: Optional[List[str]] = None # Detailed list of discrepancies if complex comparison

class OverallVerificationResult(BaseModel):
    """Represents the overall result of a set of verification checks."""
    overall_passed: bool
    checks: List[VerificationCheckResult]
    summary: Optional[str] = None
    error_count: int = 0
    warning_count: int = 0 # If warnings are also tracked 