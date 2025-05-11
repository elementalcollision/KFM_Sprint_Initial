#!/usr/bin/env python3

"""
Simplified test for the call_llm_for_reflection function.
This script makes an actual API call but with a minimal state example.
"""

import logging
import os
import sys
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleReflectionTest")

def main():
    """Run a simplified test of call_llm_for_reflection with real API call."""
    logger.info("Starting simplified reflection function test...")
    
    # Verify .env file exists
    if not os.path.exists('.env'):
        logger.error("No .env file found. Please create one with GOOGLE_API_KEY.")
        return False
    
    # Check if API key is set
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set in environment or .env file.")
        return False
    
    # Import the function from module
    try:
        from src.langgraph_nodes import call_llm_for_reflection
        logger.info("Successfully imported call_llm_for_reflection function")
    except ImportError as e:
        logger.error(f"Failed to import call_llm_for_reflection: {str(e)}")
        return False
    
    # Create a minimal test state
    minimal_state = {
        'kfm_action': {
            'action': 'keep',
            'component': 'data_processor',
            'reason': 'Performance metrics within acceptable thresholds'
        },
        'active_component': 'data_processor',
        'result': {
            'processed_items': 145,
            'errors': 3
        },
        'execution_performance': {
            'latency': 1.2,
            'accuracy': 0.92
        }
    }
    
    logger.info("Calling call_llm_for_reflection with minimal state...")
    
    try:
        start_time = time.time()
        reflection = call_llm_for_reflection(minimal_state)
        elapsed_time = time.time() - start_time
        
        if not reflection:
            logger.error("No reflection was returned.")
            return False
        
        logger.info(f"API call completed successfully in {elapsed_time:.2f} seconds")
        logger.info(f"Reflection length: {len(reflection)} characters")
        
        # Print a snippet of the reflection
        print("\n\n=== REFLECTION SNIPPET ===")
        if len(reflection) > 300:
            print(f"{reflection[:300]}...\n[truncated]")
        else:
            print(reflection)
        print("=========================\n")
        
        # Simple validation checks
        validation_passes = True
        
        # Check for basic elements that should be in the reflection
        expected_elements = [
            "Reflection", "Decision", "component", "data_processor", 
            "Strengths", "Improvement", "Recommendation"
        ]
        
        for element in expected_elements:
            if element not in reflection:
                logger.warning(f"Reflection is missing expected element: {element}")
                validation_passes = False
        
        if "[LLM REFLECTION ERROR]" in reflection:
            logger.error("Reflection contains error indicator.")
            validation_passes = False
        
        if validation_passes:
            logger.info("✅ Basic reflection validation passed!")
            return True
        else:
            logger.error("❌ Reflection failed validation checks.")
            return False
            
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ TEST PASSED: The live call_llm_for_reflection function works!")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED. See error messages above.")
        sys.exit(1) 