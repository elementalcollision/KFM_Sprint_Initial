import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.compiler import KFMGraphCompiler, compile_kfm_graph


class TestKFMCompiler(unittest.TestCase):
    """Test cases for the KFM Graph Compiler."""
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_compile_standard_mode(self, mock_create_graph):
        """Test compilation in standard mode."""
        # Setup mock
        mock_graph = MagicMock()
        mock_graph.nodes = {"monitor": MagicMock(), "decide": MagicMock(), 
                          "execute": MagicMock(), "reflect": MagicMock()}
        mock_components = {"registry": MagicMock(), "monitor": MagicMock()}
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Configure the graph structure for validation
        mock_graph.get_next_nodes = MagicMock(return_value=[])
        
        # Create compiler and compile
        compiler = KFMGraphCompiler({"threading_model": "sequential"})
        graph, components = compiler.compile(debug_mode=False)
        
        # Assertions
        self.assertEqual(graph, mock_graph)
        self.assertEqual(components, mock_components)
        mock_create_graph.assert_called_once()
    
    @patch('src.compiler.create_debug_kfm_agent_graph')
    def test_compile_debug_mode(self, mock_create_debug_graph):
        """Test compilation in debug mode."""
        # Setup mock
        mock_graph = MagicMock()
        mock_graph.nodes = {"monitor": MagicMock(), "decide": MagicMock(), 
                          "execute": MagicMock(), "reflect": MagicMock()}
        mock_components = {"registry": MagicMock(), "monitor": MagicMock()}
        mock_create_debug_graph.return_value = (mock_graph, mock_components)
        
        # Configure the graph structure for validation
        mock_graph.get_next_nodes = MagicMock(return_value=[])
        
        # Create compiler and compile
        compiler = KFMGraphCompiler()
        graph, components = compiler.compile(debug_mode=True)
        
        # Assertions
        self.assertEqual(graph, mock_graph)
        self.assertEqual(components, mock_components)
        mock_create_debug_graph.assert_called_once()
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_compile_with_error(self, mock_create_graph):
        """Test error handling during compilation."""
        # Setup mock to throw exception
        mock_create_graph.side_effect = Exception("Compilation error")
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Test exception handling
        with self.assertRaises(RuntimeError) as context:
            compiler.compile()
        
        self.assertIn("Error during graph compilation", str(context.exception))
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_validate_graph_structure_success(self, mock_create_graph):
        """Test graph structure validation when all required elements are present."""
        # Setup mock with valid structure
        mock_graph = MagicMock()
        mock_graph.nodes = {
            "monitor": MagicMock(), 
            "decide": MagicMock(), 
            "execute": MagicMock(), 
            "reflect": MagicMock()
        }
        mock_graph.entry_point = "monitor"
        mock_components = MagicMock()
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Configure graph edge validation
        mock_graph.get_next_nodes = MagicMock()
        mock_graph.get_next_nodes.side_effect = lambda node: {
            "monitor": ["decide"],
            "decide": ["execute"],
            "execute": ["reflect"],
            "reflect": []
        }.get(node, [])
        
        # Add conditional edges property
        mock_graph.conditional_edges = ["reflect"]
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Perform validation directly
        result = compiler.validate_graph_structure(mock_graph)
        
        # Assertions
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['issues']), 0)
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_validate_graph_structure_missing_nodes(self, mock_create_graph):
        """Test validation when nodes are missing."""
        # Setup mock with missing nodes
        mock_graph = MagicMock()
        mock_graph.nodes = {
            "monitor": MagicMock(), 
            "decide": MagicMock(), 
            "execute": MagicMock()
            # Missing "reflect" node
        }
        mock_graph.entry_point = "monitor"
        mock_components = MagicMock()
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Configure graph edge validation
        mock_graph.get_next_nodes = MagicMock()
        mock_graph.get_next_nodes.side_effect = lambda node: {
            "monitor": ["decide"],
            "decide": ["execute"],
            "execute": []
        }.get(node, [])
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Perform validation directly
        result = compiler.validate_graph_structure(mock_graph)
        
        # Assertions
        self.assertFalse(result['valid'])
        self.assertTrue(any("missing" in issue for issue in result['issues']))
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_validate_graph_structure_missing_edges(self, mock_create_graph):
        """Test validation when edges are missing."""
        # Setup mock with missing edges
        mock_graph = MagicMock()
        mock_graph.nodes = {
            "monitor": MagicMock(), 
            "decide": MagicMock(), 
            "execute": MagicMock(),
            "reflect": MagicMock()
        }
        mock_graph.entry_point = "monitor"
        mock_components = MagicMock()
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Configure graph edge validation with missing edge
        mock_graph.get_next_nodes = MagicMock()
        mock_graph.get_next_nodes.side_effect = lambda node: {
            "monitor": ["decide"],
            "decide": [], # Missing edge to "execute"
            "execute": ["reflect"],
            "reflect": []
        }.get(node, [])
        
        # Add conditional edges property
        mock_graph.conditional_edges = ["reflect"]
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Perform validation directly
        result = compiler.validate_graph_structure(mock_graph)
        
        # Assertions
        self.assertFalse(result['valid'])
        self.assertTrue(any("edge" in issue for issue in result['issues']))
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_export_compiled_graph_success(self, mock_create_graph):
        """Test successful export of the compiled graph."""
        # Setup mock
        mock_graph = MagicMock()
        mock_graph.nodes = {"monitor": MagicMock(), "decide": MagicMock()}
        mock_graph.entry_point = "monitor"
        mock_components = MagicMock()
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Mock serialization method
        mock_graph.serialize = MagicMock(return_value=b'serialized_data')
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Mock file operations
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            # Try to export
            result = compiler.export_compiled_graph(mock_graph, "test_output.bin")
            
            # Assertions
            self.assertTrue(result)
            mock_file.assert_called_once_with("test_output.bin", "wb")
            mock_file().write.assert_called_once_with(b'serialized_data')
    
    @patch('src.compiler.create_kfm_agent_graph')
    def test_export_compiled_graph_fallback(self, mock_create_graph):
        """Test fallback export method when serialization is not available."""
        # Setup mock without serialize method
        mock_graph = MagicMock()
        mock_graph.nodes = {"monitor": MagicMock(), "decide": MagicMock()}
        mock_graph.entry_point = "monitor"
        # Remove serialization capability
        del mock_graph.serialize
        
        mock_components = MagicMock()
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Create compiler
        compiler = KFMGraphCompiler()
        
        # Mock file operations and json dump
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:
            # Try to export
            result = compiler.export_compiled_graph(mock_graph, "test_output.json")
            
            # Assertions
            self.assertTrue(result)
            mock_file.assert_called_once_with("test_output.json", "w")
            mock_json_dump.assert_called_once()
    
    def test_convenience_function(self):
        """Test the convenience function for compilation."""
        with patch('src.compiler.KFMGraphCompiler.compile') as mock_compile:
            # Setup mock
            mock_graph = MagicMock()
            mock_components = MagicMock()
            mock_compile.return_value = (mock_graph, mock_components)
            
            # Call the convenience function
            config = {"threading_model": "parallel"}
            graph, components = compile_kfm_graph(config, debug_mode=True)
            
            # Assertions
            self.assertEqual(graph, mock_graph)
            self.assertEqual(components, mock_components)
            mock_compile.assert_called_once_with(debug_mode=True)


if __name__ == '__main__':
    unittest.main() 