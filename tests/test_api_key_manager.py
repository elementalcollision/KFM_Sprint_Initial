"""Unit tests for the API Key Manager module."""

import os
import re
import unittest
from unittest.mock import patch, MagicMock
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_key_manager import (
    APIKeyManager, 
    APIKeyNotFoundError,
    APIKeyInvalidError,
    APIKeyDefinition
)


class TestAPIKeyManager(unittest.TestCase):
    """Test cases for the API Key Manager module."""
    
    def setUp(self):
        """Set up the test environment."""
        # Clear any cached keys before each test
        APIKeyManager.clear_cache()
        # Reset the env_loaded flag
        APIKeyManager._env_loaded = False
        
        # Save original environment variables
        self.original_env = dict(os.environ)
        
        # Clear environment variables for API keys to ensure clean test environment
        for key_def in APIKeyManager._key_definitions.values():
            if key_def.env_var in os.environ:
                del os.environ[key_def.env_var]
    
    def tearDown(self):
        """Clean up after each test."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.api_key_manager.load_dotenv')
    def test_ensure_env_loaded(self, mock_load_dotenv):
        """Test that _ensure_env_loaded calls load_dotenv."""
        APIKeyManager._ensure_env_loaded()
        mock_load_dotenv.assert_called_once()
        
        # Second call should not reload
        APIKeyManager._ensure_env_loaded()
        mock_load_dotenv.assert_called_once()  # Still only called once
    
    @patch('src.api_key_manager.find_dotenv')
    @patch('src.api_key_manager.load_dotenv')
    def test_env_loaded_with_path(self, mock_load_dotenv, mock_find_dotenv):
        """Test that _ensure_env_loaded finds and uses the .env file path."""
        mock_find_dotenv.return_value = "/path/to/.env"
        
        APIKeyManager._ensure_env_loaded()
        
        mock_find_dotenv.assert_called_once_with(usecwd=True)
        mock_load_dotenv.assert_called_once_with("/path/to/.env")
    
    @patch('src.api_key_manager.find_dotenv')
    @patch('src.api_key_manager.load_dotenv')
    def test_env_loaded_no_file(self, mock_load_dotenv, mock_find_dotenv):
        """Test that _ensure_env_loaded handles no .env file gracefully."""
        mock_find_dotenv.return_value = ""  # No .env file found
        
        APIKeyManager._ensure_env_loaded()
        
        mock_find_dotenv.assert_called_once_with(usecwd=True)
        mock_load_dotenv.assert_not_called()
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_get_api_key_success(self, mock_validate, mock_environ_get):
        """Test successful API key retrieval."""
        # Mock a valid Google API key
        mock_environ_get.return_value = "AIzaTestKey123456789012345678901234567890"
        mock_validate.return_value = True
        
        key = APIKeyManager.get_api_key("google")
        self.assertEqual(key, "AIzaTestKey123456789012345678901234567890")
    
    @patch('os.environ.get')
    def test_get_api_key_missing(self, mock_environ_get):
        """Test missing API key handling."""
        # Mock a missing API key
        mock_environ_get.return_value = None
        
        with self.assertRaises(APIKeyNotFoundError):
            APIKeyManager.get_api_key("google")
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_get_api_key_invalid(self, mock_validate, mock_environ_get):
        """Test invalid API key format handling."""
        # Mock an invalid API key
        mock_environ_get.return_value = "InvalidKey"
        mock_validate.return_value = False
        
        with self.assertRaises(APIKeyInvalidError):
            APIKeyManager.get_api_key("google")
    
    @patch('os.environ.get')
    def test_get_api_key_no_validate(self, mock_environ_get):
        """Test that validation can be skipped."""
        # Mock an invalid API key
        mock_environ_get.return_value = "InvalidKey"
        
        key = APIKeyManager.get_api_key("google", validate=False)
        self.assertEqual(key, "InvalidKey")
    
    @patch('os.environ.get')
    def test_get_api_key_no_raise(self, mock_environ_get):
        """Test that error raising can be disabled."""
        # Mock a missing API key
        mock_environ_get.return_value = None
        
        key = APIKeyManager.get_api_key("google", raise_error=False)
        self.assertEqual(key, "")
    
    def test_get_api_key_unsupported_provider(self):
        """Test handling of unsupported provider."""
        with self.assertRaises(ValueError):
            APIKeyManager.get_api_key("unsupported_provider")
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_key_caching(self, mock_validate, mock_environ_get):
        """Test that API keys are cached."""
        # First call loads from environment
        mock_environ_get.return_value = "AIzaTestKey123456789012345678901234567890"
        mock_validate.return_value = True
        
        key1 = APIKeyManager.get_api_key("google")
        
        # Change the mock return value
        mock_environ_get.return_value = "AIzaNewKey12345678901234567890123456789012"
        
        # Second call should use cached value
        key2 = APIKeyManager.get_api_key("google")
        
        self.assertEqual(key1, key2)
        self.assertEqual(key2, "AIzaTestKey123456789012345678901234567890")
        
        # Clear cache and get the new value
        APIKeyManager.clear_cache()
        key3 = APIKeyManager.get_api_key("google")
        
        self.assertEqual(key3, "AIzaNewKey12345678901234567890123456789012")
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_use_api_key_context_manager(self, mock_validate, mock_environ_get):
        """Test the use_api_key context manager."""
        # Mock a valid API key
        mock_environ_get.return_value = "AIzaTestKey123456789012345678901234567890"
        mock_validate.return_value = True
        
        with APIKeyManager.use_api_key("google") as key:
            self.assertEqual(key, "AIzaTestKey123456789012345678901234567890")
    
    @patch('os.environ.get')
    def test_use_api_key_context_manager_error(self, mock_environ_get):
        """Test the use_api_key context manager with error."""
        # Mock a missing API key
        mock_environ_get.return_value = None
        
        with self.assertRaises(APIKeyNotFoundError):
            with APIKeyManager.use_api_key("google") as key:
                pass  # Should not reach here
    
    def test_mask_key(self):
        """Test the mask_key function."""
        # Regular key - we'll count the exact number of stars instead of hardcoding
        key = "AIzaTestKey123456789012345678901234567890"
        masked = APIKeyManager.mask_key(key)
        
        # Check the key starts and ends with the expected characters
        self.assertTrue(masked.startswith("AIza"))
        self.assertTrue(masked.endswith("7890"))
        
        # Check that the middle is all stars
        middle = masked[4:-4]
        self.assertEqual(len(middle), len(key) - 8)
        self.assertEqual(middle, "*" * (len(key) - 8))
        
        # Short key
        masked = APIKeyManager.mask_key("short")
        self.assertEqual(masked, "********")
        
        # Empty key
        masked = APIKeyManager.mask_key("")
        self.assertEqual(masked, "********")
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_get_key_info(self, mock_validate, mock_environ_get):
        """Test the get_key_info function."""
        # Mock a valid API key
        mock_environ_get.return_value = "AIzaTestKey123456789012345678901234567890"
        mock_validate.return_value = True
        
        info = APIKeyManager.get_key_info("google")
        
        self.assertEqual(info["provider"], "google")
        self.assertEqual(info["env_var"], "GOOGLE_API_KEY")
        self.assertTrue(info["exists"])
    
    def test_get_key_info_unsupported(self):
        """Test get_key_info with unsupported provider."""
        info = APIKeyManager.get_key_info("unsupported_provider")
        
        self.assertEqual(info["provider"], "unsupported_provider")
        self.assertFalse(info["exists"])
        self.assertEqual(info["error"], "Unsupported provider")
    
    def test_list_providers(self):
        """Test the list_providers function."""
        providers = APIKeyManager.list_providers()
        
        self.assertIn("google", providers)
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)
    
    @patch('os.environ.get')
    @patch('src.api_key_manager.APIKeyManager._validate_key_format')
    def test_list_keys_status(self, mock_validate, mock_environ_get):
        """Test the list_keys_status function."""
        # Mock behavior based on provider and validation
        def side_effect_env(arg, default=None):
            if arg == "GOOGLE_API_KEY":
                return "AIzaTestKey123456789012345678901234567890"
            elif arg == "OPENAI_API_KEY":
                return "sk-TestOpenAI12345678901234567890123456789012345678901234"
            return None
        
        def side_effect_validate(key, definition):
            return key is not None  # Valid if not None
        
        mock_environ_get.side_effect = side_effect_env
        mock_validate.side_effect = side_effect_validate
        
        status = APIKeyManager.list_keys_status()
        
        self.assertIn("google", status)
        self.assertIn("openai", status)
        
        self.assertTrue(status["google"]["exists"])
        self.assertTrue(status["openai"]["exists"])
        self.assertFalse(status["anthropic"]["exists"])
    
    @patch('src.api_key_manager.APIKeyManager.get_api_key')
    def test_configure_provider_google(self, mock_get_api_key):
        """Test the configure_provider function for Google."""
        mock_get_api_key.return_value = "AIzaTestKey123456789012345678901234567890"
        
        # Create a mock for google.generativeai
        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()
        
        # Use sys.modules to mock the import
        with patch.dict('sys.modules', {'google.generativeai': mock_genai}):
            result = APIKeyManager.configure_provider("google")
            
            # Check that configure was called with the right key
            mock_genai.configure.assert_called_once_with(api_key="AIzaTestKey123456789012345678901234567890")
    
    @patch('src.api_key_manager.APIKeyManager.get_api_key')
    def test_configure_provider_openai(self, mock_get_api_key):
        """Test the configure_provider function for OpenAI."""
        mock_get_api_key.return_value = "sk-TestOpenAI12345678901234567890123456789012345678901234"
        
        # Create a mock for openai
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        
        # Use sys.modules to mock the import
        with patch.dict('sys.modules', {'openai': mock_openai}):
            result = APIKeyManager.configure_provider("openai")
            
            # Check that OpenAI client was created with the right key
            mock_openai.OpenAI.assert_called_once_with(api_key="sk-TestOpenAI12345678901234567890123456789012345678901234")
            self.assertEqual(result, mock_client)
    
    @patch('src.api_key_manager.APIKeyManager.get_api_key')
    def test_configure_provider_anthropic(self, mock_get_api_key):
        """Test the configure_provider function for Anthropic."""
        mock_get_api_key.return_value = "sk-ant-api03-TestAnthropicKey12345678901234567890123456789012345678901234567890"
        
        # Create a mock for anthropic
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        
        # Use sys.modules to mock the import
        with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
            result = APIKeyManager.configure_provider("anthropic")
            
            # Check that Anthropic client was created with the right key
            mock_anthropic.Anthropic.assert_called_once_with(api_key="sk-ant-api03-TestAnthropicKey12345678901234567890123456789012345678901234567890")
            self.assertEqual(result, mock_client)
    
    @patch('src.api_key_manager.APIKeyManager.get_api_key')
    def test_configure_provider_unsupported(self, mock_get_api_key):
        """Test the configure_provider function for an unsupported provider."""
        mock_get_api_key.return_value = "TestKey"
        
        result = APIKeyManager.configure_provider("unsupported_provider")
        
        self.assertEqual(result, "TestKey")
    
    @patch('src.api_key_manager.APIKeyManager.get_api_key')
    def test_configure_provider_import_error(self, mock_get_api_key):
        """Test the configure_provider function with ImportError."""
        mock_get_api_key.return_value = "AIzaTestKey123456789012345678901234567890"
        
        # Use a context manager to mock the import
        with patch('builtins.__import__', side_effect=ImportError("No module named 'google.generativeai'")):
            with self.assertRaises(ImportError):
                APIKeyManager.configure_provider("google")


if __name__ == '__main__':
    unittest.main() 