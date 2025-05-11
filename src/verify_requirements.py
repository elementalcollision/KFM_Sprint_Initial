#!/usr/bin/env python3
"""
Script to run KFM Agent MVP requirements validation.
This script executes the validation checklist to verify all MVP-REQ-001 to MVP-REQ-012
are satisfied by the current implementation.
"""

import os
import sys
import logging
from src.core.validation import run_validation
from src.logger import setup_logger, setup_file_logger

# Setup logger for verification script
logger = setup_logger('VerifyRequirements')

def main():
    """Run the MVP requirements validation and report results."""
    logger.info("Starting MVP requirements verification")
    
    # Setup file logger to capture validation results
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'requirements_validation.log')
    
    # Setup file logging for this run
    file_handler = setup_file_logger(log_path)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    try:
        logger.info(f"Validation results will be logged to: {log_path}")
        
        # Run the validation
        print("\nRunning KFM Agent MVP Requirements Validation...")
        all_passed = run_validation()
        
        # Return exit code based on validation result
        if all_passed:
            logger.info("All requirements passed validation!")
            print(f"\nSuccess! All requirements validated. Full report saved to {log_path}")
            return 0
        else:
            logger.warning("Some requirements failed validation")
            print(f"\nWarning: Some requirements failed validation. See full report in {log_path}")
            return 1
            
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}", exc_info=True)
        print(f"\nError: Validation process failed: {str(e)}")
        print(f"See log for details: {log_path}")
        return 2
    finally:
        # Clean up file handler
        if file_handler in root_logger.handlers:
            root_logger.removeHandler(file_handler)
            file_handler.close()

if __name__ == "__main__":
    sys.exit(main()) 