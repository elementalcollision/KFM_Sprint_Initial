#!/usr/bin/env python
"""
State Difference Visualization Demo

This script demonstrates the enhanced state difference visualization capabilities,
including nested structure comparison, different output formats, and color-coded diffs.
"""

import os
import sys
import json
from pprint import pprint

# Add project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.debugging import (
    diff_states,
    visualize_diff,
    configure_debug_level
)

# Configure the debug level to show all messages
configure_debug_level('DEBUG')

def print_separator(title):
    """Print a separator with a title."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def demo_basic_comparison():
    """Demonstrate basic state comparison."""
    print_separator("BASIC STATE COMPARISON")
    
    # Create two simple states with various types of changes
    state1 = {
        'name': 'John',
        'age': 30,
        'active': True,
        'tags': ['user', 'customer'],
        'removed_field': 'This will be removed'
    }
    
    state2 = {
        'name': 'John',  # Unchanged
        'age': 31,       # Modified
        'active': False, # Modified
        'tags': ['user', 'premium'],  # Modified
        'new_field': 'This is new'    # Added
    }
    
    print("State 1 (Before):")
    pprint(state1)
    print("\nState 2 (After):")
    pprint(state2)
    
    # Compare states in basic mode
    print("\nDiff Results (Basic Mode):")
    diff_result = diff_states(state1, state2, mode='basic')
    
    # Print the statistical summary
    print(f"\nSummary: {diff_result['summary']}")
    
    # Print changes in JSON format
    print("\nDetailed Changes:")
    print(json.dumps(diff_result['changes'], indent=2))

def demo_nested_comparison():
    """Demonstrate comparison of nested structures."""
    print_separator("NESTED STRUCTURE COMPARISON")
    
    # Create states with nested structures
    state1 = {
        'user': {
            'id': 123,
            'name': 'John Doe',
            'contact': {
                'email': 'john.doe@example.com',
                'phone': '555-1234'
            },
            'preferences': {
                'theme': 'dark',
                'notifications': {
                    'email': True,
                    'push': False
                }
            },
            'history': [
                {'date': '2023-01-01', 'action': 'login'},
                {'date': '2023-01-02', 'action': 'purchase'}
            ]
        },
        'app_settings': {
            'version': '1.0.0',
            'debug': False
        }
    }
    
    state2 = {
        'user': {
            'id': 123,
            'name': 'John Doe',
            'contact': {
                'email': 'john.new@example.com',  # Changed
                'phone': '555-1234'
            },
            'preferences': {
                'theme': 'light',  # Changed
                'notifications': {
                    'email': True,
                    'push': True,  # Changed
                    'sms': True    # Added
                }
            },
            'history': [
                {'date': '2023-01-01', 'action': 'login'},
                {'date': '2023-01-02', 'action': 'purchase'},
                {'date': '2023-01-03', 'action': 'logout'}  # Added
            ]
        },
        'app_settings': {
            'version': '1.1.0',  # Changed
            'debug': True       # Changed
        }
    }
    
    print("Comparing states with nested structures...")
    
    # Compare states in detailed mode
    diff_result = diff_states(state1, state2, mode='detailed')
    
    # Print the statistical summary
    print(f"\nSummary: {diff_result['summary']}")
    
    # Print standard visualization
    print("\nVisualization (Standard Format):")
    print(diff_result['visualization'])

def demo_visualization_formats():
    """Demonstrate different visualization formats."""
    print_separator("VISUALIZATION FORMATS")
    
    # Create two states with changes
    state1 = {
        'user': {
            'name': 'Alice',
            'roles': ['user', 'editor'],
            'settings': {
                'theme': 'dark',
                'language': 'en'
            }
        }
    }
    
    state2 = {
        'user': {
            'name': 'Alice',
            'roles': ['user', 'editor', 'admin'],
            'settings': {
                'theme': 'light',
                'language': 'en',
                'notifications': True
            }
        }
    }
    
    # Get diff result in comprehensive mode
    diff_result = diff_states(state1, state2, mode='comprehensive')
    
    # Show standard visualization (default)
    print("Standard Format:")
    print(visualize_diff(diff_result, format_type='standard'))
    
    # Show table visualization
    print("\nTable Format:")
    print(visualize_diff(diff_result, format_type='table'))
    
    # Show JSON visualization
    print("\nJSON Format:")
    formatted_json = visualize_diff(diff_result, format_type='json')
    # Print first 500 characters to avoid overwhelming output
    print(formatted_json[:500] + "..." if len(formatted_json) > 500 else formatted_json)

def demo_large_state_truncation():
    """Demonstrate truncation of large states."""
    print_separator("LARGE STATE TRUNCATION")
    
    # Create states with large data structures
    state1 = {
        'users': [f'user{i}' for i in range(100)],
        'products': {f'product{i}': i for i in range(50)},
        'settings': {
            'debug': False,
            'logging': {
                'level': 'info',
                'file': 'app.log',
                'rotation': {
                    'max_size': '10MB',
                    'backup_count': 5
                }
            }
        }
    }
    
    state2 = {
        'users': [f'user{i}' for i in range(120)],  # 20 more users
        'products': {f'product{i}': i for i in range(40)},  # 10 fewer products
        'settings': {
            'debug': True,
            'logging': {
                'level': 'debug',
                'file': 'debug.log',
                'rotation': {
                    'max_size': '20MB',
                    'backup_count': 10
                }
            }
        }
    }
    
    print("Comparing large states with truncation...")
    
    # Compare states with truncation
    diff_result = diff_states(state1, state2, mode='detailed')
    
    # Print the statistical summary
    print(f"\nSummary: {diff_result['summary']}")
    
    # Print visualization (will show truncated values)
    print("\nVisualization (with truncation):")
    print(diff_result['visualization'])

def demo_complex_state_changes():
    """Demonstrate handling complex state changes."""
    print_separator("COMPLEX STATE CHANGES")
    
    # Initial state for a knowledge flow management agent
    initial_state = {
        'conversation_history': [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'What is the capital of France?'}
        ],
        'current_node': 'query_understanding',
        'query': 'What is the capital of France?',
        'parsed_query': {
            'intent': None,
            'entities': [],
            'keywords': []
        },
        'knowledge_sources': [],
        'retrieved_documents': [],
        'reasoning_steps': [],
        'response_draft': '',
        'metadata': {
            'session_id': 'sess_123456',
            'timestamp': '2023-06-15T10:30:00Z',
            'user_id': 'user_789'
        }
    }
    
    # Updated state after processing
    updated_state = {
        'conversation_history': [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'What is the capital of France?'},
            {'role': 'assistant', 'content': 'The capital of France is Paris.'}
        ],
        'current_node': 'response_generation',
        'query': 'What is the capital of France?',
        'parsed_query': {
            'intent': 'factual_query',
            'entities': ['France'],
            'keywords': ['capital', 'France'],
            'category': 'geography'
        },
        'knowledge_sources': ['geography_kb', 'world_facts'],
        'retrieved_documents': [
            {
                'source': 'geography_kb',
                'content': 'Paris is the capital and most populous city of France.',
                'relevance': 0.95
            },
            {
                'source': 'world_facts',
                'content': 'France is a country in Western Europe with its capital in Paris.',
                'relevance': 0.85
            }
        ],
        'reasoning_steps': [
            'Query is about the capital of France',
            'Identifying France as a country entity',
            'Searching for capital information in geography knowledge base',
            'Multiple sources confirm Paris is the capital'
        ],
        'response_draft': 'The capital of France is Paris.',
        'confidence': 0.98,
        'metadata': {
            'session_id': 'sess_123456',
            'timestamp': '2023-06-15T10:30:05Z',
            'user_id': 'user_789',
            'processing_time': '500ms'
        }
    }
    
    print("Comparing complex KFM agent states...")
    
    # Compare states in comprehensive mode
    diff_result = diff_states(initial_state, updated_state, mode='comprehensive')
    
    # Print the statistical summary
    print(f"\nSummary: {diff_result['summary']}")
    
    # Print visualization
    print("\nState Changes (Table Format):")
    print(visualize_diff(diff_result, format_type='table'))

def main():
    """Run all demos."""
    print("STATE DIFFERENCE VISUALIZATION DEMO")
    print("===================================")
    print("This demo shows the enhanced state difference visualization features.")
    
    demo_basic_comparison()
    demo_nested_comparison()
    demo_visualization_formats()
    demo_large_state_truncation()
    demo_complex_state_changes()
    
    print_separator("DEMO COMPLETE")
    print("The enhanced state difference visualization system provides:")
    print("1. Detailed comparison of nested structures")
    print("2. Multiple visualization formats (standard, table, JSON)")
    print("3. Intelligent truncation for large objects")
    print("4. Color-coded and symbol-based output")
    print("5. Summary statistics and path-based change tracking")

if __name__ == "__main__":
    main() 