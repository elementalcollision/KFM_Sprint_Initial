#!/usr/bin/env python3

"""
Test script for validating the call_llm_for_reflection function from langgraph_nodes.py.
This script creates a mock KFM agent state and passes it to the function to test the 
integration with the Google Generative AI API.
"""

import time
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReflectionTest")

# Create mock state
def create_mock_state() -> Dict[str, Any]:
    """Create a realistic mock KFM agent state for testing."""
    return {
        'kfm_action': {
            'action': 'keep',
            'component': 'data_processor',
            'reason': 'Performance metrics within acceptable thresholds'
        },
        'active_component': 'data_processor',
        'result': {
            'processed_items': 145,
            'errors': 3,
            'status': 'completed'
        },
        'execution_performance': {
            'latency': 1.2,
            'accuracy': 0.92,
            'memory_usage_mb': 245.6
        },
        'task_name': 'data_processing_task',
        'done': True
    }

def main():
    """Test the call_llm_for_reflection function with mock state."""
    logger.info("Starting reflection function test...")
    
    # Import the function from module
    try:
        from src.langgraph_nodes import call_llm_for_reflection
        logger.info("Successfully imported call_llm_for_reflection function")
    except ImportError as e:
        logger.error(f"Failed to import call_llm_for_reflection: {str(e)}")
        return False
    
    # Create mock state
    mock_state = create_mock_state()
    logger.info(f"Created mock state with KFM action: {mock_state['kfm_action']}")
    
    # Call the function
    logger.info("Calling call_llm_for_reflection function...")
    try:
        start_time = time.time()
        reflection = call_llm_for_reflection(mock_state)
        elapsed_time = time.time() - start_time
        
        logger.info(f"Call completed successfully in {elapsed_time:.2f} seconds")
        
        # Check the result
        if reflection and isinstance(reflection, str):
            if len(reflection) > 100:  # Check for substantial content
                logger.info("Reflection contains substantial content")
                logger.info(f"First 100 chars: {reflection[:100]}...")
                logger.info(f"Length: {len(reflection)} characters")
            else:
                logger.warning(f"Reflection seems short: {reflection}")
        else:
            logger.error(f"Unexpected reflection type or empty: {type(reflection)}")
            return False
        
        # Print the full reflection
        print("\n" + "="*50)
        print("REFLECTION RESULT:")
        print("="*50)
        print(reflection)
        print("="*50 + "\n")
        
        return True
    except Exception as e:
        logger.error(f"Error calling call_llm_for_reflection: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Test passed! The call_llm_for_reflection function works with the actual Google Generative AI API.")
    else:
        print("\n❌ Test failed. See error messages above.") 