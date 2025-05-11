"""
Unit tests for the RequestQueueManager class.

This module tests the functionality for queuing and processing
requests when rate limits or service availability issues occur.
"""

import unittest
import time
import json
import threading
from unittest.mock import patch, MagicMock, Mock

from src.error_recovery import RequestQueueManager


class TestRequestQueueManager(unittest.TestCase):
    """Test suite for the RequestQueueManager class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a queue manager with known parameters for testing
        self.queue_manager = RequestQueueManager(
            max_queue_size=10,
            processing_interval=0.1,  # Short interval for testing
            retry_limit=3
        )
        
        # Create a test request
        self.test_request = {
            "user_id": "test-user-123",
            "request_id": "test-request-456",
            "prompt": "Test prompt",
            "timestamp": time.time()
        }
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop the queue manager's processing thread
        self.queue_manager.stop()
    
    def test_initialization(self):
        """Test that the queue manager initializes with correct values."""
        self.assertEqual(self.queue_manager.max_queue_size, 10)
        self.assertEqual(self.queue_manager.processing_interval, 0.1)
        self.assertEqual(self.queue_manager.retry_limit, 3)
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_enqueue_request(self):
        """Test enqueueing a request."""
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Check that the request was added to the queue
        self.assertEqual(len(self.queue_manager.queue), 1)
        self.assertEqual(self.queue_manager.queue[0]["request"]["request_id"], "test-request-456")
        
        # Check that a request ID was returned
        self.assertEqual(request_id, "test-request-456")
    
    def test_enqueue_with_custom_id(self):
        """Test enqueueing a request with a custom ID."""
        # Enqueue a request with a specific ID
        custom_id = "custom-id-789"
        request = self.test_request.copy()
        request["request_id"] = custom_id
        
        request_id = self.queue_manager.enqueue(request)
        
        # Check that the request was added with the custom ID
        self.assertEqual(len(self.queue_manager.queue), 1)
        self.assertEqual(self.queue_manager.queue[0]["request"]["request_id"], custom_id)
        self.assertEqual(request_id, custom_id)
    
    def test_enqueue_full_queue(self):
        """Test enqueueing to a full queue."""
        # Fill the queue
        for i in range(self.queue_manager.max_queue_size):
            request = self.test_request.copy()
            request["request_id"] = f"request-{i}"
            self.queue_manager.enqueue(request)
        
        # Try to enqueue one more request
        request = self.test_request.copy()
        request["request_id"] = "overflow-request"
        
        with self.assertRaises(ValueError):
            self.queue_manager.enqueue(request)
        
        # Check that the queue size is still the maximum
        self.assertEqual(len(self.queue_manager.queue), self.queue_manager.max_queue_size)
    
    def test_dequeue_request(self):
        """Test dequeuing a request."""
        # Enqueue a request
        self.queue_manager.enqueue(self.test_request)
        
        # Dequeue the request
        request = self.queue_manager.dequeue()
        
        # Check that the request was returned
        self.assertEqual(request["request_id"], "test-request-456")
        
        # Check that the queue is now empty
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_dequeue_empty_queue(self):
        """Test dequeuing from an empty queue."""
        # Try to dequeue from an empty queue
        request = self.queue_manager.dequeue()
        
        # Should return None
        self.assertIsNone(request)
    
    def test_get_queue_status(self):
        """Test retrieving queue status."""
        # Enqueue a few requests
        for i in range(3):
            request = self.test_request.copy()
            request["request_id"] = f"request-{i}"
            self.queue_manager.enqueue(request)
        
        # Get queue status
        status = self.queue_manager.get_queue_status()
        
        # Check the status fields
        self.assertEqual(status["queue_size"], 3)
        self.assertEqual(status["queue_capacity"], self.queue_manager.max_queue_size)
        self.assertEqual(status["queue_utilization"], 3 / self.queue_manager.max_queue_size)
        self.assertEqual(len(status["queued_requests"]), 3)
    
    def test_clear_queue(self):
        """Test clearing the queue."""
        # Enqueue requests
        for i in range(5):
            request = self.test_request.copy()
            request["request_id"] = f"request-{i}"
            self.queue_manager.enqueue(request)
        
        # Clear the queue
        self.queue_manager.clear()
        
        # Check that the queue is empty
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_get_request_status(self):
        """Test retrieving the status of a specific request."""
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Get the status of the request
        status = self.queue_manager.get_request_status(request_id)
        
        # Check the status fields
        self.assertEqual(status["request_id"], request_id)
        self.assertEqual(status["status"], "queued")
        self.assertEqual(status["retry_count"], 0)
        self.assertIn("position", status)
        self.assertEqual(status["position"], 0)  # First in queue
    
    def test_get_nonexistent_request_status(self):
        """Test retrieving the status of a request that doesn't exist."""
        # Get the status of a nonexistent request
        status = self.queue_manager.get_request_status("nonexistent-id")
        
        # Should return None
        self.assertIsNone(status)
    
    def test_process_next_request(self):
        """Test processing the next request in the queue."""
        # Create a mock processor function
        processor = Mock(return_value="Processed result")
        
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Process the next request
        result = self.queue_manager.process_next_request(processor)
        
        # Check that the processor was called with the request
        processor.assert_called_once()
        first_arg = processor.call_args[0][0]
        self.assertEqual(first_arg["request_id"], "test-request-456")
        
        # Check that the result was returned
        self.assertEqual(result, "Processed result")
        
        # Check that the queue is now empty
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_process_next_request_with_error(self):
        """Test processing a request that results in an error."""
        # Create a mock processor function that raises an error
        processor = Mock(side_effect=Exception("Processing error"))
        
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Process the next request
        with self.assertRaises(Exception):
            self.queue_manager.process_next_request(processor)
        
        # Check that the processor was called with the request
        processor.assert_called_once()
        
        # Check that the request is still in the queue with increased retry count
        self.assertEqual(len(self.queue_manager.queue), 1)
        self.assertEqual(self.queue_manager.queue[0]["request"]["request_id"], request_id)
        self.assertEqual(self.queue_manager.queue[0]["retry_count"], 1)
    
    def test_retry_limit_exceeded(self):
        """Test that a request is removed after exceeding the retry limit."""
        # Create a mock processor function that always raises an error
        processor = Mock(side_effect=Exception("Processing error"))
        
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Process the request multiple times to exceed retry limit
        for _ in range(self.queue_manager.retry_limit):
            try:
                self.queue_manager.process_next_request(processor)
            except Exception:
                pass
        
        # After the retry limit is reached, the request should still be in the queue
        self.assertEqual(len(self.queue_manager.queue), 1)
        
        # Process one more time
        try:
            self.queue_manager.process_next_request(processor)
        except Exception:
            pass
        
        # Now the request should be removed from the queue
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_prioritization(self):
        """Test that requests are processed in priority order."""
        # Enqueue requests with different priorities
        low_priority = self.test_request.copy()
        low_priority["request_id"] = "low-priority"
        low_priority["priority"] = 0
        
        medium_priority = self.test_request.copy()
        medium_priority["request_id"] = "medium-priority"
        medium_priority["priority"] = 1
        
        high_priority = self.test_request.copy()
        high_priority["request_id"] = "high-priority"
        high_priority["priority"] = 2
        
        # Enqueue in reverse priority order
        self.queue_manager.enqueue(low_priority)
        self.queue_manager.enqueue(medium_priority)
        self.queue_manager.enqueue(high_priority)
        
        # Check that the queue is processed in priority order
        processor = Mock(return_value="Processed")
        
        # Process the first request
        self.queue_manager.process_next_request(processor)
        first_arg = processor.call_args[0][0]
        self.assertEqual(first_arg["request_id"], "high-priority")
        
        # Process the second request
        self.queue_manager.process_next_request(processor)
        second_arg = processor.call_args[0][0]
        self.assertEqual(second_arg["request_id"], "medium-priority")
        
        # Process the third request
        self.queue_manager.process_next_request(processor)
        third_arg = processor.call_args[0][0]
        self.assertEqual(third_arg["request_id"], "low-priority")
    
    def test_automatic_processing(self):
        """Test that the queue manager automatically processes requests."""
        # Create a mock processor function
        processor = Mock(return_value="Processed result")
        
        # Start automatic processing
        self.queue_manager.start_processing(processor)
        
        # Enqueue a request
        request_id = self.queue_manager.enqueue(self.test_request)
        
        # Wait for the request to be processed
        time.sleep(0.3)  # Wait longer than the processing interval
        
        # Check that the processor was called with the request
        processor.assert_called()
        call_arg = None
        for call in processor.call_args_list:
            if call[0][0]["request_id"] == request_id:
                call_arg = call[0][0]
                break
        
        self.assertIsNotNone(call_arg, "Request was not processed")
        self.assertEqual(call_arg["request_id"], request_id)
        
        # Check that the queue is now empty
        self.assertEqual(len(self.queue_manager.queue), 0)
    
    def test_remove_request(self):
        """Test removing a specific request from the queue."""
        # Enqueue multiple requests
        request_ids = []
        for i in range(3):
            request = self.test_request.copy()
            request["request_id"] = f"request-{i}"
            request_ids.append(self.queue_manager.enqueue(request))
        
        # Remove the middle request
        removed = self.queue_manager.remove_request(request_ids[1])
        
        # Check that the request was removed
        self.assertTrue(removed)
        self.assertEqual(len(self.queue_manager.queue), 2)
        current_ids = [item["request"]["request_id"] for item in self.queue_manager.queue]
        self.assertNotIn(request_ids[1], current_ids)
        self.assertIn(request_ids[0], current_ids)
        self.assertIn(request_ids[2], current_ids)
    
    def test_remove_nonexistent_request(self):
        """Test removing a request that doesn't exist in the queue."""
        # Try to remove a nonexistent request
        removed = self.queue_manager.remove_request("nonexistent-id")
        
        # Should return False
        self.assertFalse(removed)
    
    def test_concurrent_access(self):
        """Test that the queue manager handles concurrent access properly."""
        # Define a function to enqueue requests
        def enqueue_requests():
            for i in range(5):
                request = self.test_request.copy()
                request["request_id"] = f"thread-{threading.get_ident()}-{i}"
                try:
                    self.queue_manager.enqueue(request)
                except ValueError:
                    # Queue might be full, that's expected
                    pass
        
        # Create and start threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=enqueue_requests)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that the queue wasn't corrupted
        self.assertLessEqual(len(self.queue_manager.queue), self.queue_manager.max_queue_size)
    
    def test_queue_statistics(self):
        """Test retrieving queue statistics."""
        # Process some requests successfully and some with errors
        processor_success = Mock(return_value="Success")
        processor_error = Mock(side_effect=Exception("Error"))
        
        # Enqueue and process successful requests
        for i in range(3):
            request = self.test_request.copy()
            request["request_id"] = f"success-{i}"
            self.queue_manager.enqueue(request)
            self.queue_manager.process_next_request(processor_success)
        
        # Enqueue and process failed requests
        for i in range(2):
            request = self.test_request.copy()
            request["request_id"] = f"error-{i}"
            self.queue_manager.enqueue(request)
            try:
                self.queue_manager.process_next_request(processor_error)
            except Exception:
                pass
        
        # Get queue statistics
        stats = self.queue_manager.get_statistics()
        
        # Check the statistics
        self.assertEqual(stats["total_requests_processed"], 5)
        self.assertEqual(stats["successful_requests"], 3)
        self.assertEqual(stats["failed_requests"], 2)
        self.assertEqual(stats["current_queue_size"], 2)  # Failed requests are still in queue
    
    def test_batch_enqueue(self):
        """Test enqueueing multiple requests at once."""
        # Create a batch of requests
        batch = []
        for i in range(5):
            request = self.test_request.copy()
            request["request_id"] = f"batch-{i}"
            batch.append(request)
        
        # Enqueue the batch
        request_ids = self.queue_manager.enqueue_batch(batch)
        
        # Check that all requests were added to the queue
        self.assertEqual(len(self.queue_manager.queue), 5)
        
        # Check that all request IDs were returned
        self.assertEqual(len(request_ids), 5)
        for i, request_id in enumerate(request_ids):
            self.assertEqual(request_id, f"batch-{i}")


if __name__ == '__main__':
    unittest.main() 