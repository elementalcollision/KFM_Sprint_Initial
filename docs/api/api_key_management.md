# API Key Management

This document describes how to use the API Key Management system in the codebase, which provides secure handling of API keys for various providers.

## Overview

The API Key Management system centralizes all API key handling in the codebase, ensuring:

- No credentials are hardcoded anywhere in the code
- Consistent validation of API keys
- Proper error handling for missing or invalid keys
- Clear instructions for setting up environment variables
- Safe logging without exposing sensitive key values

## Setting Up API Keys

### Step 1: Create a `.env` File

Copy the `.env.example` file to a new file named `.env`:

```bash
cp .env.example .env
```

### Step 2: Add Your API Keys

Edit the `.env` file to add your actual API keys:

```
GOOGLE_API_KEY=AIza...your-actual-key-here...
OPENAI_API_KEY=sk-...your-actual-key-here...
```

**Important**: Never commit your `.env` file to version control! The `.gitignore` file already includes this pattern, but be cautious.

## Using the API Key Manager

The API Key Manager is implemented in `src/api_key_manager.py` and provides a centralized way to manage API keys.

### Basic Key Retrieval

```python
from src.api_key_manager import APIKeyManager, APIKeyNotFoundError, APIKeyInvalidError

# Get a specific API key
try:
    google_key = APIKeyManager.get_api_key("google")
    # Use the key...
except APIKeyNotFoundError:
    # Handle missing key
    print("Google API key not found in environment variables or .env file")
except APIKeyInvalidError:
    # Handle invalid key format
    print("Google API key has an invalid format")
```

### Context Manager

For safer key handling, use the context manager:

```python
from src.api_key_manager import APIKeyManager

# Use the context manager
with APIKeyManager.use_api_key("google") as api_key:
    # Use the key within this block
    # The key will be validated and properly handled
    client.configure(api_key=api_key)
```

### Automatic Client Configuration

The API Key Manager can automatically configure common API clients:

```python
from src.api_key_manager import APIKeyManager

# For Google Generative AI
genai = APIKeyManager.configure_provider("google")
# The genai client is now configured with the API key

# For OpenAI
openai_client = APIKeyManager.configure_provider("openai")
# The OpenAI client is now configured with the API key
```

### Getting Key Information

You can get information about available keys and their status:

```python
from src.api_key_manager import APIKeyManager

# List all supported providers
providers = APIKeyManager.list_providers()
print(f"Supported providers: {providers}")

# Get info about a specific key
key_info = APIKeyManager.get_key_info("google")
print(f"Google API key exists: {key_info['exists']}")

# Get status of all keys
status = APIKeyManager.list_keys_status()
for provider, info in status.items():
    print(f"{provider}: {'✅ Available' if info['exists'] else '❌ Missing'}")
```

## Supported Providers

The API Key Manager supports the following providers:

| Provider ID | Environment Variable | Description |
|-------------|----------------------|-------------|
| `google` | `GOOGLE_API_KEY` | Google Generative AI (Gemini) |
| `openai` | `OPENAI_API_KEY` | OpenAI API |
| `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Claude API |
| `azure_openai` | `AZURE_OPENAI_API_KEY` | Azure OpenAI services |
| `mistral` | `MISTRAL_API_KEY` | Mistral AI |
| `perplexity` | `PERPLEXITY_API_KEY` | Perplexity API |
| `xai` | `XAI_API_KEY` | xAI API |
| `openrouter` | `OPENROUTER_API_KEY` | OpenRouter API |

## Security Considerations

- API keys are treated as highly sensitive information
- Keys are never exposed in logs (only masked versions may be shown)
- Keys are cached in memory to reduce the number of environment lookups
- The system attempts to validate key formats when possible
- Clear error messages are provided for missing or invalid keys
- No default or fallback keys are provided; genuine keys are required

## Extending for New Providers

To add support for a new API key provider, update the `_key_definitions` dictionary in the `APIKeyManager` class in `src/api_key_manager.py`:

```python
# Example of adding a new provider
"new_provider": APIKeyDefinition(
    provider="new_provider",
    env_var="NEW_PROVIDER_API_KEY",
    validation_pattern=re.compile(r"^expected-pattern$"),
    expected_prefix="prefix-",
    description="Description of the new provider",
    required=False
)
```

After adding a new provider, update the `.env.example` file to include the new environment variable with documentation.

## Best Practices

1. Always use the API Key Manager instead of directly accessing environment variables
2. Handle key-related exceptions appropriately in your code
3. Use context managers when possible for safer key handling
4. Don't store API keys in configuration files or code
5. Periodically rotate your API keys for enhanced security
6. Set appropriate permissions for your `.env` file (e.g., `chmod 600 .env`)
7. Consider using a secret management service for production deployments 