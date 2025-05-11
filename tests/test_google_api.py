#!/usr/bin/env python3

import os
import time
from dotenv import load_dotenv

def test_google_genai_api():
    """Test the Google Generative AI API key and make a sample call."""
    print("=== Testing Google Generative AI API ===")
    
    # Load API key from environment
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY not found in environment variables")
        print("Please set this variable in your .env file")
        return False
    
    # Validate API key format (basic check)
    if not api_key.startswith("AIza"):
        print("⚠️ WARNING: API key format may be incorrect. Google API keys typically start with 'AIza'")
    
    print(f"✓ API Key found in environment (not shown for security)")
    
    # Import the Google Generative AI library
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
        print("✓ Successfully imported google.generativeai")
    except ImportError:
        print("❌ ERROR: Google Generative AI SDK not installed")
        print("Run 'pip install google-generativeai' to install it")
        return False
    
    # Configure the API
    try:
        genai.configure(api_key=api_key)
        print("✓ API client configured successfully")
    except Exception as e:
        print(f"❌ ERROR configuring API client: {str(e)}")
        return False
    
    # Setup safety settings and generation config as in our implementation
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
    
    generation_config = GenerationConfig(
        temperature=0.3,
        top_p=0.95,
        top_k=40,
        max_output_tokens=2048
    )
    
    # Create the model
    try:
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print("✓ Successfully created GenerativeModel instance with gemini-2.0-flash")
    except Exception as e:
        print(f"❌ ERROR creating model: {str(e)}")
        return False
    
    # Make a test API call
    test_prompt = """# KFM Agent Reflection Analysis

## Context
You are analyzing a Knowledge Flow Management (KFM) decision made by an AI agent. The agent follows a "Keep-Marry-Kill" framework for managing AI components:
- KEEP: Continue using the component as is
- MARRY: Enhance or integrate the component with others
- KILL: Remove or replace the component

## Decision Details
- KFM Action: KEEP
- Component: 'data_processor'
- Reason Given: "Performance metrics within acceptable thresholds"
- Active Component Used: 'data_processor'
- Performance Metrics:
  - Latency: 1.2s
  - Accuracy: 0.92
- Execution Results: {'processed_items': 145, 'errors': 3}

## Reflection Questions
1. Was the KEEP decision appropriate given the performance metrics and context?
2. How effective was the execution of this decision using component 'data_processor'?
3. What were the specific strengths of this decision and execution?
4. What could be improved in future similar scenarios?
5. Are there any patterns or insights to be gained for future KFM decisions?

## Output Format Requirements
Structure your response using these exact Markdown headings:
```
# Reflection on Keep Decision for Component 'data_processor'

## Decision Analysis
[Your analysis of whether the decision was appropriate]

## Execution Assessment
[Your assessment of the execution effectiveness]
- Latency: 1.2s
- Accuracy: 0.92

## Strengths
- [Specific strength 1]
- [Specific strength 2]
- [Specific strength 3]

## Areas for Improvement
- [Specific improvement 1]
- [Specific improvement 2]

## Patterns and Insights
[Analysis of patterns and insights]

## Recommendation
[Concrete recommendation for future actions]
```

## Guidelines
- Be specific and objective in your analysis
- Base your assessment on the performance metrics and execution results
- Provide concrete, actionable recommendations
- Consider both short-term outcomes and long-term implications
- Keep your total response under 500 words
"""
    
    print("\nMaking test API call to generate reflection...")
    try:
        start_time = time.time()
        response = model.generate_content(test_prompt)
        elapsed_time = time.time() - start_time
        
        print(f"✓ API call successful (completed in {elapsed_time:.2f} seconds)")
        print("\n=== Response ===")
        print(response.text)
        print("===============")
        return True
    except Exception as e:
        print(f"❌ ERROR making API call: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_google_genai_api()
    if success:
        print("\n✅ All tests passed! The API key is working correctly with gemini-2.0-flash model.")
    else:
        print("\n❌ Tests failed. Please check the errors above.") 