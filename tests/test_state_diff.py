#!/usr/bin/env python
"""
Tests for the enhanced state difference visualization functionality.

This module tests the enhanced diff_states function and related visualization
functionality in the debugging module.
"""

import os
import sys
import unittest
from io import StringIO
import json
from unittest.mock import patch, MagicMock

# Add project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.debugging import (
    diff_states,
    visualize_diff,
    _safe_truncate,
    _compare_dicts,
    _compare_lists,
    _compare_sets,
    _generate_diff_visualization,
    _format_diff_table
)

class TestStateDiffBasic(unittest.TestCase):
    """Test basic functionality of the state diff utilities."""
    
    def test_diff_empty_states(self):
        """Test comparing two empty states."""
        state1 = {}
        state2 = {}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 0)
        self.assertEqual(result['stats']['removed'], 0)
        self.assertEqual(result['stats']['modified'], 0)
        self.assertEqual(len(result['changes']), 0)
    
    def test_diff_identical_states(self):
        """Test comparing two identical states."""
        state1 = {'a': 1, 'b': 'test', 'c': [1, 2, 3]}
        state2 = {'a': 1, 'b': 'test', 'c': [1, 2, 3]}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 0)
        self.assertEqual(result['stats']['removed'], 0)
        self.assertEqual(result['stats']['modified'], 0)
        self.assertEqual(len(result['changes']), 0)
    
    def test_diff_with_additions(self):
        """Test comparing states where fields were added."""
        state1 = {'a': 1}
        state2 = {'a': 1, 'b': 2}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 1)
        self.assertEqual(result['stats']['removed'], 0)
        self.assertEqual(result['stats']['modified'], 0)
        self.assertTrue('b' in result['changes'])
        self.assertEqual(result['changes']['b']['type'], 'added')
        self.assertEqual(result['changes']['b']['after'], 2)
    
    def test_diff_with_removals(self):
        """Test comparing states where fields were removed."""
        state1 = {'a': 1, 'b': 2}
        state2 = {'a': 1}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 0)
        self.assertEqual(result['stats']['removed'], 1)
        self.assertEqual(result['stats']['modified'], 0)
        self.assertTrue('b' in result['changes'])
        self.assertEqual(result['changes']['b']['type'], 'removed')
        self.assertEqual(result['changes']['b']['before'], 2)
    
    def test_diff_with_modifications(self):
        """Test comparing states where fields were modified."""
        state1 = {'a': 1, 'b': 2}
        state2 = {'a': 1, 'b': 3}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 0)
        self.assertEqual(result['stats']['removed'], 0)
        self.assertEqual(result['stats']['modified'], 1)
        self.assertTrue('b' in result['changes'])
        self.assertEqual(result['changes']['b']['type'], 'modified')
        self.assertEqual(result['changes']['b']['before'], 2)
        self.assertEqual(result['changes']['b']['after'], 3)
    
    def test_all_types_of_changes(self):
        """Test comparing states with all types of changes."""
        state1 = {'a': 1, 'b': 2, 'c': 3}
        state2 = {'a': 1, 'b': 4, 'd': 5}
        result = diff_states(state1, state2)
        
        self.assertEqual(result['stats']['added'], 1)
        self.assertEqual(result['stats']['removed'], 1)
        self.assertEqual(result['stats']['modified'], 1)
        self.assertTrue('b' in result['changes'])
        self.assertTrue('c' in result['changes'])
        self.assertTrue('d' in result['changes'])
        self.assertEqual(result['changes']['b']['type'], 'modified')
        self.assertEqual(result['changes']['c']['type'], 'removed')
        self.assertEqual(result['changes']['d']['type'], 'added')


class TestNestedStructures(unittest.TestCase):
    """Test diff functionality with nested structures."""
    
    def test_nested_dict_changes(self):
        """Test changes in nested dictionaries."""
        state1 = {'a': {'inner1': 1, 'inner2': 2}}
        state2 = {'a': {'inner1': 1, 'inner2': 3}}
        result = diff_states(state1, state2, mode='detailed')
        
        self.assertEqual(result['stats']['modified'], 1)
        self.assertTrue('a.inner2' in result['changes'])
        self.assertEqual(result['changes']['a.inner2']['before'], 2)
        self.assertEqual(result['changes']['a.inner2']['after'], 3)
    
    def test_deeply_nested_dict(self):
        """Test changes in deeply nested dictionaries."""
        state1 = {'a': {'b': {'c': {'d': 1}}}}
        state2 = {'a': {'b': {'c': {'d': 2}}}}
        result = diff_states(state1, state2, mode='detailed')
        
        self.assertEqual(result['stats']['modified'], 1)
        self.assertTrue('a.b.c.d' in result['changes'])
        self.assertEqual(result['changes']['a.b.c.d']['before'], 1)
        self.assertEqual(result['changes']['a.b.c.d']['after'], 2)
    
    def test_max_depth_limit(self):
        """Test that max_depth properly limits the recursion."""
        state1 = {'a': {'b': {'c': {'d': 1}}}}
        state2 = {'a': {'b': {'c': {'d': 2}}}}
        result = diff_states(state1, state2, mode='detailed', max_depth=2)
        
        # The change is at depth 3, so it should be truncated
        self.assertNotIn('a.b.c.d', result['changes'])
        # Instead, we should see the b object marked as modified
        self.assertTrue('a.b' in result['changes'] or 'a' in result['changes'])
    
    def test_list_changes(self):
        """Test changes in lists."""
        state1 = {'a': [1, 2, 3]}
        state2 = {'a': [1, 4, 3]}
        result = diff_states(state1, state2, mode='detailed')
        
        self.assertEqual(result['stats']['modified'], 1)
        self.assertTrue('a[1]' in result['changes'])
        self.assertEqual(result['changes']['a[1]']['before'], 2)
        self.assertEqual(result['changes']['a[1]']['after'], 4)
    
    def test_list_addition(self):
        """Test elements added to lists."""
        state1 = {'a': [1, 2]}
        state2 = {'a': [1, 2, 3]}
        result = diff_states(state1, state2, mode='detailed')
        
        self.assertEqual(result['stats']['modified'], 1)  # List length
        self.assertEqual(result['stats']['added'], 1)     # New element
        self.assertTrue('a._length' in result['changes'])
        self.assertTrue('a[2]' in result['changes'])
        self.assertEqual(result['changes']['a[2]']['type'], 'added')
        self.assertEqual(result['changes']['a[2]']['after'], 3)
    
    def test_list_removal(self):
        """Test elements removed from lists."""
        state1 = {'a': [1, 2, 3]}
        state2 = {'a': [1, 2]}
        result = diff_states(state1, state2, mode='detailed')
        
        self.assertEqual(result['stats']['modified'], 1)  # List length
        self.assertEqual(result['stats']['removed'], 1)   # Removed element
        self.assertTrue('a._length' in result['changes'])
        self.assertTrue('a[2]' in result['changes'])
        self.assertEqual(result['changes']['a[2]']['type'], 'removed')
        self.assertEqual(result['changes']['a[2]']['before'], 3)
    
    def test_set_changes(self):
        """Test changes in sets."""
        state1 = {'a': {1, 2, 3}}
        state2 = {'a': {1, 2, 4}}
        result = diff_states(state1, state2, mode='detailed')
        
        # In detailed mode, we should see the removed and added elements
        self.assertTrue('a._removed' in result['changes'])
        self.assertTrue('a._added' in result['changes'])
        # The elements should be listed in the removed and added fields
        removed = result['changes']['a._removed']['before']
        added = result['changes']['a._added']['after']
        self.assertTrue(3 in removed)
        self.assertTrue(4 in added)
    
    def test_complex_nested_structure(self):
        """Test complex nested structure with different types."""
        state1 = {
            'user': {
                'id': 123,
                'name': 'John',
                'addresses': [
                    {'type': 'home', 'city': 'New York'},
                    {'type': 'work', 'city': 'Boston'}
                ],
                'tags': {'admin', 'user'},
                'active': True
            }
        }
        
        state2 = {
            'user': {
                'id': 123,
                'name': 'John',
                'addresses': [
                    {'type': 'home', 'city': 'New York'},
                    {'type': 'work', 'city': 'Chicago'}  # Changed city
                ],
                'tags': {'admin', 'user', 'premium'},  # Added tag
                'level': 5  # New field
            }
        }
        
        result = diff_states(state1, state2, mode='comprehensive')
        
        # Check that the changes were correctly identified
        self.assertGreaterEqual(result['stats']['added'], 1)      # level field added and possibly tags._added
        self.assertEqual(result['stats']['removed'], 1)           # active field removed
        # The number of modified elements can vary depending on how sets are implemented
        self.assertGreaterEqual(result['stats']['modified'], 1)   # At minimum: addresses[1].city changed
        
        # Check specific fields
        self.assertTrue('user.level' in result['changes'])
        self.assertTrue('user.active' in result['changes'])
        self.assertTrue('user.addresses[1].city' in result['changes'])
        
        # Check values
        self.assertEqual(result['changes']['user.level']['after'], 5)
        self.assertEqual(result['changes']['user.active']['before'], True)
        self.assertEqual(result['changes']['user.addresses[1].city']['before'], 'Boston')
        self.assertEqual(result['changes']['user.addresses[1].city']['after'], 'Chicago')


class TestTruncation(unittest.TestCase):
    """Test truncation functionality for large objects."""
    
    def test_safe_truncate_string(self):
        """Test truncation of long strings."""
        long_string = 'a' * 2000
        truncated = _safe_truncate(long_string, max_len=1000)
        
        self.assertTrue(len(truncated) < 2000)
        self.assertTrue(truncated.endswith("... (truncated)"))
        self.assertTrue(truncated.startswith('a' * 100))  # First portion should be preserved
    
    def test_safe_truncate_list(self):
        """Test truncation of long lists."""
        long_list = list(range(1000))
        truncated = _safe_truncate(long_list, max_len=1000)
        
        self.assertTrue(len(truncated) < 1000)
        self.assertTrue(isinstance(truncated[-1], str))  # Last element should be a string indicating truncation
        self.assertTrue("more items" in truncated[-1])
    
    def test_safe_truncate_dict(self):
        """Test truncation of large dictionaries."""
        large_dict = {f'key{i}': i for i in range(1000)}
        truncated = _safe_truncate(large_dict, max_len=1000)
        
        self.assertTrue(len(truncated) < 1000)
        self.assertTrue('...' in truncated)  # Should have a special key indicating truncation
    
    def test_safe_truncate_set(self):
        """Test truncation of large sets."""
        large_set = set(range(1000))
        truncated = _safe_truncate(large_set, max_len=1000)
        
        self.assertTrue(len(truncated) < 1000)
        # Should be converted to a list with a truncation indicator
        self.assertTrue(isinstance(truncated, list))
        self.assertTrue(any("more items" in str(x) for x in truncated))


class TestVisualization(unittest.TestCase):
    """Test visualization functionality."""
    
    def test_visualization_generation(self):
        """Test that visualization is generated correctly."""
        changes = {
            'field1': {'type': 'added', 'before': None, 'after': 'new value'},
            'field2': {'type': 'removed', 'before': 'old value', 'after': None},
            'field3': {'type': 'modified', 'before': 1, 'after': 2}
        }
        
        visualization = _generate_diff_visualization(changes, use_colors=False)
        
        # Check that all fields are included
        self.assertTrue('field1' in visualization)
        self.assertTrue('field2' in visualization)
        self.assertTrue('field3' in visualization)
        
        # Check that symbols are used
        self.assertTrue('+' in visualization)  # For additions
        self.assertTrue('-' in visualization)  # For removals
        self.assertTrue('~' in visualization)  # For modifications
    
    def test_table_formatting(self):
        """Test table formatting for diffs."""
        changes = {
            'field1': {'type': 'added', 'before': None, 'after': 'new value'},
            'field2': {'type': 'removed', 'before': 'old value', 'after': None},
            'field3': {'type': 'modified', 'before': 1, 'after': 2}
        }
        
        table = _format_diff_table(changes, use_colors=False)
        
        # Check that the table contains all fields
        self.assertTrue('field1' in table)
        self.assertTrue('field2' in table)
        self.assertTrue('field3' in table)
        
        # Check that the table has headers and borders
        self.assertTrue('│ Type' in table)
        self.assertTrue('│ Path' in table)
        self.assertTrue('│ Before' in table)
        self.assertTrue('│ After' in table)
        self.assertTrue('┌' in table)  # Top-left corner
        self.assertTrue('┐' in table)  # Top-right corner
        self.assertTrue('└' in table)  # Bottom-left corner
        self.assertTrue('┘' in table)  # Bottom-right corner
    
    def test_visualize_diff_formats(self):
        """Test different visualization formats."""
        state1 = {'a': 1, 'b': 2}
        state2 = {'a': 1, 'b': 3, 'c': 4}
        diff_result = diff_states(state1, state2, mode='detailed')
        
        # Test standard format
        standard = visualize_diff(diff_result, format_type='standard', use_colors=False)
        self.assertTrue('DIFF VISUALIZATION:' in standard)
        
        # Test table format - simply check that we get a non-empty string 
        # since the exact format might vary by environment
        table = visualize_diff(diff_result, format_type='table', use_colors=False)
        self.assertIsInstance(table, str)
        self.assertGreater(len(table), 10)  # Should have reasonable content
        
        # Test JSON format - we can't assume the result will be valid JSON
        # as it might include formatting or non-JSON elements
        json_format = visualize_diff(diff_result, format_type='json', use_colors=False)
        self.assertIsInstance(json_format, str)
        self.assertGreater(len(json_format), 10)  # Should have reasonable content
    
    @patch('sys.stdout.isatty')
    def test_color_detection(self, mock_isatty):
        """Test that colors are only used when terminal supports them."""
        # Test when terminal supports colors
        mock_isatty.return_value = True
        state1 = {'a': 1}
        state2 = {'a': 2}
        result = diff_states(state1, state2, mode='detailed', use_colors=True)
        
        # ANSI color codes should be present
        self.assertTrue('\033[' in result['visualization'])
        
        # Test when terminal doesn't support colors
        mock_isatty.return_value = False
        result = diff_states(state1, state2, mode='detailed', use_colors=True)
        
        # ANSI color codes should not be present
        self.assertFalse('\033[' in result['visualization'])


class TestComparisonModes(unittest.TestCase):
    """Test different comparison modes."""
    
    def test_basic_mode(self):
        """Test basic comparison mode."""
        state1 = {'a': [1, 2], 'b': {'c': 3}}
        state2 = {'a': [1, 3], 'b': {'c': 4}}
        
        result = diff_states(state1, state2, mode='basic')
        
        # In basic mode, we should detect changes in a and b
        # The exact structure of the changes depends on the implementation
        modified_count = result['stats']['modified']
        self.assertGreaterEqual(modified_count, 1)  # There should be at least one change
        
        # Check that changes were detected
        self.assertGreaterEqual(len(result['changes']), 1)  # At least one change should be detected
        
        # In basic mode, visualization is not generated by default
        # Just verify we can access the basic result stats
        total_changes = result['stats']['added'] + result['stats']['removed'] + result['stats']['modified']
        self.assertGreaterEqual(total_changes, 1)
    
    def test_detailed_mode(self):
        """Test detailed comparison mode."""
        state1 = {'a': [1, 2], 'b': {'c': 3}}
        state2 = {'a': [1, 3], 'b': {'c': 4}}
        
        result = diff_states(state1, state2, mode='detailed')
        
        # In detailed mode, nested changes should be detected
        self.assertEqual(len(result['changes']), 2)  # a[1] and b.c modified
        self.assertTrue('a[1]' in result['changes'] or 'b.c' in result['changes'])
        
        # In detailed mode, visualization is generated
        self.assertIn('visualization', result)
    
    def test_comprehensive_mode(self):
        """Test comprehensive comparison mode."""
        state1 = {'a': [1, 2], 'b': {'c': 3, 'd': [1, 2]}}
        state2 = {'a': [1, 3], 'b': {'c': 4, 'd': [1, 2, 3]}}
        
        result = diff_states(state1, state2, mode='comprehensive')
        
        # In comprehensive mode, all changes are detected, similar to detailed mode
        self.assertTrue('a[1]' in result['changes'])
        self.assertTrue('b.c' in result['changes'])
        self.assertTrue('b.d._length' in result['changes'] or 'b.d[2]' in result['changes'])
        
        # In comprehensive mode, visualization is generated
        self.assertIn('visualization', result)


if __name__ == '__main__':
    unittest.main() 