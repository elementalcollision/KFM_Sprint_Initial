"""
API Key Manager Module

This module provides a centralized system for securely loading, validating, and managing 
API keys from environment variables or .env files. It ensures no credentials are hardcoded
and implements proper validation and error handling for missing or invalid credentials.

Usage:
    from src.api_key_manager import APIKeyManager
    
    # Get Google API key
    try:
        google_key = APIKeyManager.get_api_key("google")
        # Use the key...
    except KeyError as e:
        # Handle missing key
        print(f"Error: {str(e)}")
    
    # Or use the context manager to configure an API client
    with APIKeyManager.use_api_key("google") as api_key:
        # Configure client with api_key
        client.configure(api_key=api_key)
"""

import os
import re
import time
import logging
from typing import Dict, Optional, Any, List, Pattern, Union, Iterator
from functools import lru_cache
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta

# Import dotenv for loading .env files
from dotenv import load_dotenv, find_dotenv

# Configure logging
logger = logging.getLogger("api_key_manager")

class APIKeyError(Exception):
    """Base exception for all API key related errors."""
    pass

class APIKeyNotFoundError(APIKeyError, KeyError):
    """Exception raised when an API key is not found."""
    pass

class APIKeyInvalidError(APIKeyError, ValueError):
    """Exception raised when an API key fails validation."""
    pass

@dataclass
class APIKeyDefinition:
    """Definition of an API key configuration."""
    # Name of the provider (e.g., "google", "openai")
    provider: str
    # Environment variable name (e.g., "GOOGLE_API_KEY")
    env_var: str
    # Regular expression pattern for validation, if applicable
    validation_pattern: Optional[Pattern] = None
    # Description of the key for documentation
    description: str = ""
    # Whether the key is required for the application
    required: bool = False
    # Expected prefix for the key, if any
    expected_prefix: Optional[str] = None
    # Key security classification (e.g., "high", "medium", "low")
    security_level: str = "high"
    # Additional information or notes about the key
    notes: str = ""

class APIKeyManager:
    """
    Manager for API keys that handles loading, validation, and secure access.
    
    This class provides a centralized way to manage API keys from environment
    variables and .env files, with proper validation and error handling.
    """
    
    # Dictionary mapping provider names to their key definitions
    _key_definitions: Dict[str, APIKeyDefinition] = {
        "google": APIKeyDefinition(
            provider="google",
            env_var="GOOGLE_API_KEY",
            validation_pattern=re.compile(r"^AIza[0-9A-Za-z_-]{35}$"),
            expected_prefix="AIza",
            description="Google API Key for Generative AI services",
            required=False,
            notes="Used for accessing Google's Gemini models."
        ),
        "openai": APIKeyDefinition(
            provider="openai",
            env_var="OPENAI_API_KEY",
            validation_pattern=re.compile(r"^sk-[0-9A-Za-z]{48}$"),
            expected_prefix="sk-",
            description="OpenAI API Key",
            required=False,
            notes="Used for accessing OpenAI models."
        ),
        "anthropic": APIKeyDefinition(
            provider="anthropic",
            env_var="ANTHROPIC_API_KEY",
            validation_pattern=re.compile(r"^sk-ant-api03-[0-9A-Za-z-]{68}$"),
            expected_prefix="sk-ant-api03-",
            description="Anthropic API Key",
            required=False,
            notes="Used for accessing Anthropic Claude models."
        ),
        "azure_openai": APIKeyDefinition(
            provider="azure_openai",
            env_var="AZURE_OPENAI_API_KEY",
            description="Azure OpenAI API Key",
            required=False,
            notes="Requires AZURE_OPENAI_ENDPOINT to be set as well."
        ),
        "mistral": APIKeyDefinition(
            provider="mistral",
            env_var="MISTRAL_API_KEY",
            description="Mistral AI API Key",
            required=False
        ),
        "perplexity": APIKeyDefinition(
            provider="perplexity",
            env_var="PERPLEXITY_API_KEY",
            expected_prefix="pplx-",
            description="Perplexity API Key",
            required=False
        ),
        "xai": APIKeyDefinition(
            provider="xai",
            env_var="XAI_API_KEY",
            description="xAI API Key",
            required=False
        ),
        "openrouter": APIKeyDefinition(
            provider="openrouter",
            env_var="OPENROUTER_API_KEY",
            description="OpenRouter API Key",
            required=False
        ),
    }
    
    # Cache of loaded API keys to avoid frequent environment checks
    _key_cache: Dict[str, str] = {}
    
    # Timestamps when keys were last loaded
    _key_last_loaded: Dict[str, datetime] = {}
    
    # Flag to indicate if .env has been loaded
    _env_loaded: bool = False
    
    @classmethod
    def _ensure_env_loaded(cls) -> None:
        """Ensure that environment variables from .env are loaded."""
        if not cls._env_loaded:
            # Try to find and load .env file from the current or parent directories
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path)
                logger.debug(f"Loaded environment variables from {dotenv_path}")
            else:
                logger.debug("No .env file found, using existing environment variables")
            
            cls._env_loaded = True
    
    @classmethod
    def _get_env_var(cls, env_var: str) -> Optional[str]:
        """
        Get an environment variable value.
        
        Args:
            env_var: Name of the environment variable
            
        Returns:
            The value of the environment variable, or None if not set
        """
        cls._ensure_env_loaded()
        return os.environ.get(env_var)
    
    @classmethod
    def _validate_key_format(cls, key: str, definition: APIKeyDefinition) -> bool:
        """
        Validate that a key matches the expected format.
        
        Args:
            key: The API key to validate
            definition: The key definition with validation rules
            
        Returns:
            True if the key is valid, False otherwise
        """
        # Basic checks
        if not key or not isinstance(key, str):
            return False
        
        # Check expected prefix if defined
        if definition.expected_prefix and not key.startswith(definition.expected_prefix):
            logger.warning(
                f"API key for {definition.provider} does not start with expected prefix "
                f"'{definition.expected_prefix}'"
            )
            return False
            
        # Use regex pattern if available
        if definition.validation_pattern and not definition.validation_pattern.match(key):
            return False
            
        return True
    
    @classmethod
    def get_api_key(cls, provider: str, validate: bool = True, raise_error: bool = True) -> str:
        """
        Get an API key for the specified provider.
        
        Args:
            provider: The name of the provider (e.g., "google", "openai")
            validate: Whether to validate the key format
            raise_error: Whether to raise an exception if the key is not found or invalid
            
        Returns:
            The API key as a string
            
        Raises:
            APIKeyNotFoundError: If the key is not found and raise_error is True
            APIKeyInvalidError: If the key is invalid and raise_error is True
        """
        # Check if provider is supported
        if provider not in cls._key_definitions:
            supported = ", ".join(cls._key_definitions.keys())
            error_msg = f"Unsupported provider '{provider}'. Supported providers: {supported}"
            logger.error(error_msg)
            if raise_error:
                raise ValueError(error_msg)
            return ""
        
        # Get the key definition
        definition = cls._key_definitions[provider]
        
        # Check if key is in cache and still valid
        if provider in cls._key_cache:
            logger.debug(f"Using cached API key for {provider}")
            key = cls._key_cache[provider]
            return key
            
        # Key not in cache, load from environment
        key = cls._get_env_var(definition.env_var)
        
        # Check if key exists
        if not key:
            error_msg = (
                f"API key for {provider} not found. Please set the {definition.env_var} "
                f"environment variable or add it to your .env file."
            )
            logger.error(error_msg)
            if raise_error:
                raise APIKeyNotFoundError(error_msg)
            return ""
        
        # Validate key format if requested
        if validate and not cls._validate_key_format(key, definition):
            error_msg = (
                f"API key for {provider} failed validation. Please check that the "
                f"{definition.env_var} environment variable contains a valid API key."
            )
            logger.error(error_msg)
            if raise_error:
                raise APIKeyInvalidError(error_msg)
            return ""
        
        # Add key to cache
        cls._key_cache[provider] = key
        cls._key_last_loaded[provider] = datetime.now()
        
        # Log success without revealing the key
        masked_key = cls.mask_key(key)
        logger.debug(f"Successfully loaded API key for {provider}: {masked_key}")
        
        return key
    
    @classmethod
    @contextmanager
    def use_api_key(cls, provider: str, validate: bool = True) -> Iterator[str]:
        """
        Context manager for using an API key.
        
        Args:
            provider: The name of the provider (e.g., "google", "openai")
            validate: Whether to validate the key format
            
        Yields:
            The API key as a string
            
        Raises:
            APIKeyNotFoundError: If the key is not found
            APIKeyInvalidError: If the key is invalid
        """
        try:
            key = cls.get_api_key(provider, validate=validate)
            yield key
        except APIKeyError as e:
            logger.error(f"Error using API key for {provider}: {str(e)}")
            raise
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the API key cache."""
        cls._key_cache.clear()
        cls._key_last_loaded.clear()
        logger.debug("API key cache cleared")
    
    @classmethod
    def reload_env(cls) -> None:
        """Force reload of environment variables from .env file."""
        cls._env_loaded = False
        cls.clear_cache()
        cls._ensure_env_loaded()
        logger.debug("Environment variables reloaded")
    
    @staticmethod
    def mask_key(key: str, show_chars: int = 4, mask_char: str = "*") -> str:
        """
        Mask an API key for safe logging.
        
        Args:
            key: The API key to mask
            show_chars: Number of characters to show at the beginning and end
            mask_char: Character to use for masking
            
        Returns:
            A masked version of the key (e.g., "AIza****abcd")
        """
        if not key or len(key) <= show_chars * 2:
            return f"{mask_char * 8}"
        
        masked_len = len(key) - (show_chars * 2)
        return f"{key[:show_chars]}{mask_char * masked_len}{key[-show_chars:]}"
    
    @classmethod
    def get_key_info(cls, provider: str) -> Dict[str, Any]:
        """
        Get information about an API key.
        
        Args:
            provider: The name of the provider
            
        Returns:
            A dictionary with information about the key
        """
        if provider not in cls._key_definitions:
            return {
                "provider": provider,
                "exists": False,
                "error": "Unsupported provider"
            }
        
        definition = cls._key_definitions[provider]
        key_exists = provider in cls._key_cache or cls._get_env_var(definition.env_var) is not None
        
        return {
            "provider": provider,
            "env_var": definition.env_var,
            "description": definition.description,
            "required": definition.required,
            "exists": key_exists,
            "last_loaded": cls._key_last_loaded.get(provider),
            "notes": definition.notes
        }
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """
        Get a list of all supported providers.
        
        Returns:
            A list of provider names
        """
        return list(cls._key_definitions.keys())
    
    @classmethod
    def list_keys_status(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the status of all API keys.
        
        Returns:
            A dictionary mapping provider names to key information
        """
        return {
            provider: cls.get_key_info(provider)
            for provider in cls.list_providers()
        }
    
    @classmethod
    def configure_provider(cls, provider: str, **client_kwargs) -> Any:
        """
        Configure a provider's client with the appropriate API key.
        
        This is a convenience method for common providers.
        
        Args:
            provider: The name of the provider
            **client_kwargs: Additional keyword arguments for the client
            
        Returns:
            The configured client, if applicable
            
        Raises:
            ImportError: If the required module is not installed
            APIKeyNotFoundError: If the key is not found
            APIKeyInvalidError: If the key is invalid
        """
        # Get the API key
        api_key = cls.get_api_key(provider)
        
        # Configure the appropriate client based on the provider
        if provider == "google":
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key, **client_kwargs)
                logger.info("Google Generative AI client configured successfully")
                return genai
            except ImportError:
                raise ImportError(
                    "Google Generative AI SDK not installed. "
                    "Run 'pip install google-generativeai'"
                )
        
        elif provider == "openai":
            try:
                import openai
                client = openai.OpenAI(api_key=api_key, **client_kwargs)
                logger.info("OpenAI client configured successfully")
                return client
            except ImportError:
                raise ImportError(
                    "OpenAI SDK not installed. Run 'pip install openai'"
                )
        
        elif provider == "anthropic":
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key, **client_kwargs)
                logger.info("Anthropic client configured successfully")
                return client
            except ImportError:
                raise ImportError(
                    "Anthropic SDK not installed. Run 'pip install anthropic'"
                )
                
        else:
            logger.warning(f"No automatic configuration available for {provider}")
            return api_key 