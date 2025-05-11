import os
from dotenv import load_dotenv

# Load environment variables from the .env file located in the project root
# dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # More robust path finding
# load_dotenv(dotenv_path=dotenv_path)
load_dotenv() # Simpler, assumes script is run from project root or .env is findable

# Retrieve the API key from the environment
api_key = os.getenv('GOOGLE_API_KEY')

# Check if the key was loaded and print status
# A basic check: key exists and is longer than 10 characters (typical for API keys)
key_loaded = api_key is not None and len(api_key) > 10 
print(f"GOOGLE_API_KEY loaded successfully: {key_loaded}")

if key_loaded:
     # Avoid printing the actual key; show only confirmation or masked version
     print(f"API Key starts with: {api_key[:4]}...")
else:
     print("API Key not found or is empty in .env file.") 