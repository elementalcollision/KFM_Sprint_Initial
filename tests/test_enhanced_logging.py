import sys
import os
import unittest
import logging
import tempfile
from unittest.mock import patch, MagicMock, call

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.logger import setup_logger, setup_shared_file_logger
from src.kfm_agent import run_kfm_agent
from src.langgraph_nodes import call_llm_for_reflection


class TestEnhancedLogging(unittest.TestCase):
    """Test cases for the enhanced logging implementation."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for log files
        self.temp_dir = tempfile.TemporaryDirectory()
        # Override the logs directory for testing
        self.old_logs_dir = os.path.join(project_root, 'logs')
        self.test_logs_dir = self.temp_dir.name
        os.environ['LOGS_DIR'] = self.test_logs_dir
        
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
        if 'LOGS_DIR' in os.environ:
            del os.environ['LOGS_DIR']
    
    def test_setup_logger(self):
        """Test that setup_logger properly configures the logger."""
        with self.assertLogs(level='INFO') as log:
            logger = setup_logger('TestLogger', level=logging.INFO)
            logger.info("Test log message")
            
        self.assertEqual(len(log.records), 1)
        self.assertEqual(log.records[0].message, "Test log message")
        self.assertEqual(log.records[0].name, "TestLogger")
    
    @patch('src.kfm_agent.create_kfm_agent_graph')
    @patch('src.kfm_agent.print_execution_summary')
    def test_run_kfm_agent_logging(self, mock_print_summary, mock_create_graph):
        """Test that run_kfm_agent logs proper execution steps."""
        # Setup mock graph
        mock_app = MagicMock()
        mock_app.invoke.return_value = {
            'input': {'text': 'test'},
            'task_name': 'test_task',
            'done': True
        }
        mock_create_graph.return_value = (mock_app, {})
        
        # Setup temporary log file
        log_file = os.path.join(self.test_logs_dir, "test_log.log")
        
        # Run the function with logging
        with self.assertLogs(level='INFO') as log:
            run_kfm_agent({'text': 'test'}, task_name='test_task', log_file=log_file)
        
        # Verify logs show execution steps
        log_messages = [record.message for record in log.records]
        
        # Verify key log messages exist
        self.assertTrue(any('KFM AGENT RUN START' in msg for msg in log_messages))
        self.assertTrue(any('Graph invocation complete' in msg for msg in log_messages))
        self.assertTrue(any('KFM AGENT RUN COMPLETE' in msg for msg in log_messages))
        
        # Verify mock calls
        mock_app.invoke.assert_called_once()
        mock_print_summary.assert_called_once()
    
    def test_reflection_logging(self):
        """Test that call_llm_for_reflection logs entry and exit."""
        # Create test state
        test_state = {
            'kfm_action': {'action': 'test', 'component': 'test_comp'},
            'active_component': 'test_comp',
            'result': {'test': 'result'},
            'execution_performance': {'latency': 1.0, 'accuracy': 0.9}
        }
        
        # Run reflection with logging
        with self.assertLogs(level='INFO') as log:
            reflection = call_llm_for_reflection(test_state)
        
        # Verify logs show entry and exit
        log_messages = [record.message for record in log.records]
        
        # Check for entry/exit logs
        self.assertTrue(any('ENTER: call_llm_for_reflection' in msg for msg in log_messages))
        self.assertTrue(any('Making LLM call for reflection' in msg for msg in log_messages))
        self.assertTrue(any('EXIT: call_llm_for_reflection' in msg for msg in log_messages))
        
        # Check reflection contains expected content
        self.assertIn('test_comp', reflection)


if __name__ == '__main__':
    unittest.main() 