# src/core/exceptions.py

class KFMVerifierError(Exception):
    """Base exception for all KFM Verifier application errors."""
    pass

class ConfigurationError(KFMVerifierError):
    """Raised for errors related to loading, validating, or accessing configuration."""
    pass

class LogParsingError(KFMVerifierError):
    """Raised for errors encountered during log file parsing or analysis."""
    pass

class RegistryAccessError(KFMVerifierError):
    """Raised for errors related to accessing or querying the component registry."""
    pass

class VerificationError(KFMVerifierError):
    """Raised for general errors during the verification logic itself (not a failed check outcome)."""
    pass

class ReportingError(KFMVerifierError):
    """Raised for errors encountered during report generation."""
    pass

class CIIntegrationError(KFMVerifierError):
    """Raised for errors specific to CI/CD integration components or processes."""
    pass

class ResilienceError(KFMVerifierError):
    """Raised for errors related to retry mechanisms or other resilience patterns."""
    pass

# It can be useful to also have more specific sub-exceptions if needed, for example:
# class NetworkTimeoutError(RegistryAccessError):
#     """Raised specifically for network timeouts when accessing registry."""
#     pass

# class InvalidLogFormatError(LogParsingError):
#     """Raised when a log file does not match the expected format for its parser."""
#     pass 