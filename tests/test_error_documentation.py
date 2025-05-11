"""
Unit tests to verify error handling documentation across the codebase.

This module checks that all error handling components have proper
docstrings, examples, and explanations of error scenarios.
"""

import unittest
import inspect
import os
import re
from unittest.mock import patch

# Components to check for documentation
from src.exceptions import LLMAPIError
from src.error_classifier import ErrorClassifier
from src.retry_strategy import ExponentialBackoffStrategy
from src.error_recovery import CircuitBreaker, TokenBucketRateLimiter
from src.langgraph_nodes import call_llm_for_reflection_v3, generate_error_reflection


class TestErrorDocumentation(unittest.TestCase):
    """Test the documentation for error handling components."""
    
    def test_exception_docstrings(self):
        """Test that all exception classes have proper docstrings."""
        # Get all exception classes from exceptions module
        from src import exceptions
        exception_classes = [
            obj for name, obj in inspect.getmembers(exceptions)
            if inspect.isclass(obj) and issubclass(obj, Exception) and obj != Exception
        ]
        
        for exc_class in exception_classes:
            # Check that the class has a docstring
            self.assertIsNotNone(exc_class.__doc__, 
                                f"Exception class {exc_class.__name__} missing docstring")
            
            # Check docstring content
            self.assertGreater(len(exc_class.__doc__.strip()), 10, 
                              f"Exception class {exc_class.__name__} has too short docstring")
            
            # Check for key methods docstrings
            for method_name, method in inspect.getmembers(exc_class, predicate=inspect.isfunction):
                if method_name.startswith('_') and method_name not in ['__init__', '__str__']:
                    continue  # Skip private methods except for __init__ and __str__
                
                self.assertIsNotNone(method.__doc__,
                                   f"Method {exc_class.__name__}.{method_name} missing docstring")
    
    def test_error_classifier_docstrings(self):
        """Test that error classifier components have proper docstrings."""
        from src import error_classifier
        
        # Check module docstring
        self.assertIsNotNone(error_classifier.__doc__, "error_classifier module missing docstring")
        
        # Check classes and functions in the module
        for name, obj in inspect.getmembers(error_classifier):
            if inspect.isclass(obj) or inspect.isfunction(obj):
                if name.startswith('_'):
                    continue  # Skip private members
                
                self.assertIsNotNone(obj.__doc__, 
                                   f"Missing docstring for {name} in error_classifier")
                
                # Check that class methods have docstrings
                if inspect.isclass(obj):
                    for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                        if method_name.startswith('_') and method_name not in ['__init__']:
                            continue  # Skip private methods
                        
                        self.assertIsNotNone(method.__doc__,
                                           f"Method {name}.{method_name} missing docstring")
    
    def test_retry_strategy_docstrings(self):
        """Test that retry strategy components have proper docstrings."""
        from src import retry_strategy
        
        # Check module docstring
        self.assertIsNotNone(retry_strategy.__doc__, "retry_strategy module missing docstring")
        
        # Check functions and classes in the module
        for name, obj in inspect.getmembers(retry_strategy):
            if inspect.isclass(obj) or inspect.isfunction(obj):
                if name.startswith('_'):
                    continue  # Skip private members
                
                self.assertIsNotNone(obj.__doc__, 
                                   f"Missing docstring for {name} in retry_strategy")
    
    def test_error_recovery_docstrings(self):
        """Test that error recovery components have proper docstrings."""
        from src import error_recovery
        
        # Check module docstring
        self.assertIsNotNone(error_recovery.__doc__, "error_recovery module missing docstring")
        
        # Check classes in the module
        for name, obj in inspect.getmembers(error_recovery):
            if inspect.isclass(obj):
                if name.startswith('_'):
                    continue  # Skip private members
                
                self.assertIsNotNone(obj.__doc__, 
                                   f"Missing docstring for {name} in error_recovery")
                
                # Check that class methods have docstrings
                for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if method_name.startswith('_') and method_name not in ['__init__']:
                        continue  # Skip private methods
                    
                    self.assertIsNotNone(method.__doc__,
                                       f"Method {name}.{method_name} missing docstring")
    
    def test_langgraph_nodes_error_handling_docstrings(self):
        """Test that error-related functions in langgraph_nodes have proper docstrings."""
        from src import langgraph_nodes
        
        # List of error-related functions to check
        error_functions = [
            'call_llm_for_reflection_v3',
            'generate_error_reflection',
            'format_error_info'
        ]
        
        for func_name in error_functions:
            if hasattr(langgraph_nodes, func_name):
                func = getattr(langgraph_nodes, func_name)
                self.assertIsNotNone(func.__doc__, 
                                   f"Missing docstring for {func_name} in langgraph_nodes")
                
                # Check docstring content
                self.assertGreater(len(func.__doc__.strip()), 20, 
                                 f"Function {func_name} has too short docstring")
                
                # Check for error handling documentation
                self.assertTrue(
                    any(term in func.__doc__.lower() for term in ['error', 'exception', 'raise']),
                    f"Function {func_name} docstring doesn't mention error handling"
                )
    
    def test_examples_in_docstrings(self):
        """Test that docstrings include usage examples for error handling."""
        modules_to_check = [
            'src.error_recovery',
            'src.retry_strategy',
            'src.error_classifier'
        ]
        
        for module_name in modules_to_check:
            module = __import__(module_name, fromlist=[''])
            
            # Check classes in the module
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and not name.startswith('_'):
                    docstring = obj.__doc__ or ""
                    
                    # Check for "Example:" or "Examples:" in docstring
                    self.assertTrue(
                        re.search(r'Example[s]?:', docstring, re.IGNORECASE),
                        f"Class {module_name}.{name} docstring should include usage examples"
                    )
                    
                    # Check for code blocks in docstring (using indentation as a proxy)
                    indented_blocks = re.findall(r'\n\s{4,}[^\s].*(?:\n\s{4,}.*)*', docstring)
                    self.assertTrue(
                        indented_blocks,
                        f"Class {module_name}.{name} docstring should include code examples (indented blocks)"
                    )
    
    def test_error_recovery_documentation_consistency(self):
        """Test consistency of documentation across error recovery components."""
        # Get all error recovery classes
        from src import error_recovery
        recovery_classes = [
            obj for name, obj in inspect.getmembers(error_recovery)
            if inspect.isclass(obj) and not name.startswith('_')
        ]
        
        # Check for common terminology
        common_terms = ['error', 'recovery', 'strategy', 'handle', 'retry']
        
        for cls in recovery_classes:
            docstring = cls.__doc__ or ""
            
            # Check that the docstring mentions some common terms
            term_found = False
            for term in common_terms:
                if term in docstring.lower():
                    term_found = True
                    break
            
            self.assertTrue(term_found, 
                          f"Class {cls.__name__} docstring should use common error handling terminology")
            
            # Check for consistent formatting (triple quotes)
            if cls.__doc__:
                self.assertTrue(cls.__doc__.startswith('"""') or cls.__doc__.startswith("'''"),
                              f"Class {cls.__name__} should use triple quotes for docstrings")
    
    def test_markdown_documentation_exists(self):
        """Test that markdown documentation exists for error handling."""
        # Check for a dedicated error handling markdown file
        possible_paths = [
            'docs/error_handling.md',
            'docs/errors.md',
            'docs/exceptions.md',
            'README.md'
        ]
        
        file_found = False
        error_handling_content = False
        
        for path in possible_paths:
            if os.path.exists(path):
                file_found = True
                
                # Check file content for error handling documentation
                with open(path, 'r') as f:
                    content = f.read()
                    if re.search(r'error handling|exception|retry strategy', content, re.IGNORECASE):
                        error_handling_content = True
                        break
        
        self.assertTrue(file_found, "Should have documentation file (README.md or specific error docs)")
        self.assertTrue(error_handling_content, "Documentation should include information about error handling")
    
    def test_error_codes_documentation(self):
        """Test that error codes are documented."""
        # Check for enum or constants that define error codes/types
        from src import error_classifier
        
        # Look for ErrorCategory enum or similar
        error_categories_found = False
        for name, obj in inspect.getmembers(error_classifier):
            if name == 'ErrorCategory' or name.endswith('ErrorType') or name.endswith('ErrorCode'):
                error_categories_found = True
                
                # Check that each category has a docstring
                if inspect.isclass(obj):
                    for attr_name, attr_value in inspect.getmembers(obj):
                        if not attr_name.startswith('_') and not inspect.ismethod(attr_value):
                            # This is likely an enum value
                            # We can't check docstring directly, but we can check the class docstring
                            self.assertIn(attr_name, obj.__doc__, 
                                        f"Error category {attr_name} should be documented in {name} docstring")
        
        self.assertTrue(error_categories_found, "Should have documented error categories/codes")
    
    def test_error_handling_flow_documentation(self):
        """Test that the error handling flow is documented."""
        # Look for documentation on handling specific errors
        from src import langgraph_nodes
        
        # Check docstring of call_llm_for_reflection_v3
        if hasattr(langgraph_nodes, 'call_llm_for_reflection_v3'):
            func = getattr(langgraph_nodes, 'call_llm_for_reflection_v3')
            docstring = func.__doc__ or ""
            
            # Look for "Raises:" section in docstring
            self.assertIn("Raises:", docstring, 
                         "call_llm_for_reflection_v3 docstring should document raised exceptions")
            
            # Check for mentions of specific exception types
            from src import exceptions
            exception_classes = [
                obj.__name__ for name, obj in inspect.getmembers(exceptions)
                if inspect.isclass(obj) and issubclass(obj, Exception) and obj != Exception
            ]
            
            exceptions_documented = False
            for exc_name in exception_classes:
                if exc_name in docstring:
                    exceptions_documented = True
                    break
            
            self.assertTrue(exceptions_documented, 
                          "call_llm_for_reflection_v3 docstring should mention specific exception types")


if __name__ == '__main__':
    unittest.main() 