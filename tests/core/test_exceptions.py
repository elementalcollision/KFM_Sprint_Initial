import pytest
from src.core.exceptions import (
    KFMVerifierError,
    ConfigurationError,
    LogParsingError,
    RegistryAccessError,
    VerificationError,
    ReportingError,
    ResilienceError
)

class TestCustomExceptions:
    def test_kfm_verifier_error_inheritance(self):
        assert issubclass(KFMVerifierError, Exception)

    def test_kfm_verifier_error_instantiation(self):
        try:
            raise KFMVerifierError("Base KFM Verifier error.")
        except KFMVerifierError as e:
            assert str(e) == "Base KFM Verifier error."
            assert isinstance(e, Exception)

    @pytest.mark.parametrize("exception_class, message", [
        (ConfigurationError, "A config error occurred."),
        (LogParsingError, "A log parsing error occurred."),
        (RegistryAccessError, "A registry access error occurred."),
        (VerificationError, "A verification process error occurred."),
        (ReportingError, "A reporting error occurred."),
        (ResilienceError, "A resilience-related error occurred.")
    ])
    def test_specific_exception_inheritance_and_instantiation(self, exception_class, message):
        assert issubclass(exception_class, KFMVerifierError)
        try:
            raise exception_class(message)
        except KFMVerifierError as e: # Catching via base KFMVerifierError
            assert str(e) == message
            assert isinstance(e, exception_class)
            assert isinstance(e, KFMVerifierError)
            assert isinstance(e, Exception)
        except Exception as e_general: # Fallback, should not happen if logic is correct
            pytest.fail(f"Exception {exception_class.__name__} was not caught by KFMVerifierError or itself. Caught by general Exception: {e_general}")

    def test_configuration_error_specific_catch(self):
        message = "Specific configuration issue."
        try:
            raise ConfigurationError(message)
        except ConfigurationError as e:
            assert str(e) == message
        except KFMVerifierError:
            pytest.fail("ConfigurationError was caught by KFMVerifierError instead of its specific type.")

    # Add similar specific catch tests for other exceptions if needed for clarity or specific handling logic in future.
    # For now, the parametrized test covers the primary inheritance and message propagation well. 