import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import create_kfm_agent_graph, visualize_graph, save_graph_visualization


class TestKFMAppCompilation(unittest.TestCase):
    """Test cases for the LangGraph application compilation."""
    
    @patch('src.kfm_agent.create_kfm_agent')
    @patch('src.factory.create_kfm_agent')
    def test_create_kfm_agent_graph_success(self, mock_factory, mock_agent_create):
        """Test that the LangGraph application compiles successfully."""
        # Mock the factory and components
        mock_registry = MagicMock()
        mock_monitor = MagicMock()
        mock_planner = MagicMock()
        mock_engine = MagicMock()
        
        mock_agent_create.return_value = (mock_registry, mock_monitor, mock_planner, mock_engine)
        mock_factory.return_value = (mock_registry, mock_monitor, mock_planner, mock_engine)
        
        # Call the function
        kfm_app, components = create_kfm_agent_graph()
        
        # Assertions
        self.assertIsNotNone(kfm_app, "The compiled kfm_app should not be None")
        self.assertEqual(components['registry'], mock_registry)
        self.assertEqual(components['monitor'], mock_monitor)
        self.assertEqual(components['planner'], mock_planner)
        self.assertEqual(components['engine'], mock_engine)
    
    @patch('src.kfm_agent.create_kfm_agent')
    @patch('src.factory.create_kfm_agent')
    def test_graph_visualization(self, mock_factory, mock_agent_create):
        """Test the graph visualization functionality."""
        # Mock the factory and components
        mock_registry = MagicMock()
        mock_monitor = MagicMock()
        mock_planner = MagicMock()
        mock_engine = MagicMock()
        
        mock_agent_create.return_value = (mock_registry, mock_monitor, mock_planner, mock_engine)
        mock_factory.return_value = (mock_registry, mock_monitor, mock_planner, mock_engine)
        
        # Create a mock StateGraph for testing visualization
        kfm_app, _ = create_kfm_agent_graph()
        
        # Mock the visualization methods
        mock_graph = MagicMock()
        kfm_app.get_graph = MagicMock(return_value=mock_graph)
        mock_graph.draw_mermaid_png = MagicMock(return_value=b'fake_png_data')
        
        # Test visualize_graph
        result = visualize_graph(kfm_app)
        self.assertEqual(result, b'fake_png_data')
        
        # Test save_graph_visualization with a mock file
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            success = save_graph_visualization(kfm_app, "test_graph.png")
            self.assertTrue(success)
            mock_file.assert_called_once_with("test_graph.png", "wb")
            mock_file().write.assert_called_once_with(b'fake_png_data')
    
    @patch('src.kfm_agent.create_kfm_agent')
    @patch('src.kfm_agent.StateGraph.compile')
    def test_create_kfm_agent_graph_error(self, mock_compile, mock_create_kfm_agent):
        """Test that errors during compilation are properly handled."""
        # Setup mocks
        mock_create_kfm_agent.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
        mock_compile.side_effect = Exception("Compilation failed")
        
        # Check that the error is propagated properly
        with self.assertRaises(RuntimeError) as context:
            create_kfm_agent_graph()
        
        self.assertIn("Error compiling LangGraph application", str(context.exception))


if __name__ == '__main__':
    unittest.main() 