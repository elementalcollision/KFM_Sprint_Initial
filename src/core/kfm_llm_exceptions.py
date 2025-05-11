from typing import Optional, Dict, Any

class KfmPlannerError(Exception):
    """Base exception class for KFMPlannerLlm related errors."""
    def __init__(self, message: str, error_type: str = "KfmPlannerError", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}

class KfmValidationError(KfmPlannerError):
    """Exception raised for KFM input validation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmValidationError", details=details)

class KfmJsonConversionError(KfmPlannerError):
    """Exception raised for errors during JSON conversion of inputs."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmJsonConversionError", details=details)

class KfmOutputParsingError(KfmPlannerError):
    """Exception raised when the LLM output cannot be parsed into the KFMDecision model."""
    def __init__(self, message: str, llm_output: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmOutputParsingError", details=details)
        self.llm_output = llm_output

class KfmInvocationError(KfmPlannerError):
    """Exception raised for errors during the invocation of the LLM chain (e.g., API errors after retries)."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmInvocationError", details=details)
        self.original_exception = original_exception

class KfmReasoningError(KfmPlannerError): # Though less likely to be raised directly, good for categorization
    """Exception for errors related to the LLM's reasoning process itself (e.g., if it explicitly states inability)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmReasoningError", details=details)

class KfmConfigurationError(KfmPlannerError):
    """Exception for errors related to KFMPlannerLlm configuration."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="KfmConfigurationError", details=details)

# Example of how you might use these in KFMPlannerLlm:
#
# try:
#     # some operation
#     if validation_fails:
#         raise KfmValidationError("Input validation failed for X.", details={"field": "X", "value": y})
# except KfmValidationError as e:
#     self.logger.error(e.message, extra={"props": {"event_type": "error", "error_type": e.error_type, "details": e.details}})
#     # handle error 