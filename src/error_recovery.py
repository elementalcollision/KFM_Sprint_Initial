"""
Specialized error recovery strategies for LLM API calls.

This module provides targeted recovery mechanisms for specific error types
to improve resilience during API interactions, including rate limiting,
network errors, and service unavailability.
"""

import time
import threading
import logging
import queue
import random
import httpx
from typing import Dict, Any, Optional, Callable, List, Tuple, Union, TypeVar
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

from src.exceptions import (
    LLMAPIError, 
    LLMNetworkError, 
    LLMTimeoutError, 
    LLMConnectionError,
    LLMClientError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
    LLMServerError,
    LLMServiceUnavailableError,
    LLMInternalError,
)

# Configure logging
logger = logging.getLogger(__name__)

# Type for function return value
T = TypeVar('T')

# Request priority levels
class RequestPriority(Enum):
    """Priority levels for queued requests."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class QueuedRequest:
    """A request in the priority queue."""
    priority: RequestPriority
    timestamp: float
    callback: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """Compare requests based on priority first, then timestamp."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value  # Higher value = higher priority
        return self.timestamp < other.timestamp  # Earlier timestamp = higher priority

class TokenBucketRateLimiter:
    """
    Implements the token bucket algorithm for rate limiting.
    
    The token bucket algorithm works by assigning tokens to a virtual bucket at a
    constant rate. Each request consumes one or more tokens. If there are enough
    tokens, the request is allowed; otherwise, it's delayed or rejected.
    
    This implementation supports:
    - Adaptive rate limiting based on observed rate limit responses
    - Burst tolerance for handling sudden request spikes
    - Automatic rate recovery when no rate limits are encountered
    """
    
    def __init__(
        self,
        rate: float = 10.0,  # Tokens per second
        max_tokens: int = 60,  # Maximum bucket capacity
        tokens_per_request: int = 1,  # Tokens consumed per request
        min_rate: float = 0.2,  # Minimum rate (tokens/sec) during severe rate limiting
        recovery_factor: float = 1.2,  # Rate increase factor on successful requests
        backoff_factor: float = 0.5,  # Rate decrease factor on rate limit errors
    ):
        """
        Initialize the token bucket rate limiter.
        
        Args:
            rate: Tokens added per second
            max_tokens: Maximum tokens the bucket can hold
            tokens_per_request: Number of tokens consumed per request
            min_rate: Minimum rate during severe rate limiting
            recovery_factor: Factor to increase rate by after successful period
            backoff_factor: Factor to decrease rate by after rate limit errors
        """
        self.rate = rate
        self.max_tokens = max_tokens
        self.tokens = max_tokens  # Start with a full bucket
        self.tokens_per_request = tokens_per_request
        self.min_rate = min_rate
        self.recovery_factor = recovery_factor
        self.backoff_factor = backoff_factor
        
        self.last_updated = time.time()
        self._lock = threading.RLock()
        
        # Track rate limit events
        self.rate_limit_count = 0
        self.last_rate_limit = 0
        self.successful_request_count = 0
        self.last_rate_recovery = 0
        
        logger.info(f"TokenBucketRateLimiter initialized with rate={rate}, max_tokens={max_tokens}")
    
    def add_tokens(self) -> None:
        """Add tokens to the bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_updated
        
        # Calculate tokens to add based on rate and elapsed time
        new_tokens = elapsed * self.rate
        
        # Update token count, capped at max_tokens
        with self._lock:
            self.tokens = min(self.tokens + new_tokens, self.max_tokens)
            self.last_updated = now
    
    def get_wait_time(self) -> float:
        """
        Calculate wait time needed before enough tokens are available.
        
        Returns:
            float: Time in seconds to wait (0 if no wait needed)
        """
        with self._lock:
            self.add_tokens()
            
            if self.tokens >= self.tokens_per_request:
                return 0
            
            # Calculate time needed for enough tokens
            missing_tokens = self.tokens_per_request - self.tokens
            wait_time = missing_tokens / self.rate
            
            return wait_time
    
    def consume(self, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Consume tokens for a request.
        
        Args:
            block: Whether to block until tokens are available
            timeout: Maximum time to wait for tokens (None = no limit)
            
        Returns:
            bool: True if tokens were consumed, False if timed out
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                self.add_tokens()
                
                if self.tokens >= self.tokens_per_request:
                    self.tokens -= self.tokens_per_request
                    return True
            
            # If not blocking, return False immediately
            if not block:
                return False
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
            
            # Wait for tokens to be added
            wait_time = self.get_wait_time()
            if wait_time > 0:
                # Add a small random jitter to prevent thundering herd
                jitter = random.uniform(0, 0.1)
                time.sleep(min(wait_time + jitter, 0.5))  # Cap at 0.5s per iteration
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens for a request without blocking.
        This is an alias for consume(block=False) for backwards compatibility.
        
        Args:
            timeout: Maximum time to wait for tokens (not used in non-blocking mode)
            
        Returns:
            bool: True if tokens were acquired, False otherwise
        """
        return self.consume(block=False)
    
    def record_rate_limit(self) -> None:
        """Record a rate limit error and adjust rates accordingly."""
        with self._lock:
            self.rate_limit_count += 1
            self.last_rate_limit = time.time()
            
            # Decrease the token rate
            new_rate = max(self.rate * self.backoff_factor, self.min_rate)
            
            if new_rate < self.rate:
                logger.warning(f"Rate limited: Reducing token rate from {self.rate:.2f} to {new_rate:.2f} tokens/sec")
                self.rate = new_rate
            
            # Reset successful request counter
            self.successful_request_count = 0
    
    def record_success(self) -> None:
        """Record a successful request and potentially increase rate."""
        with self._lock:
            self.successful_request_count += 1
            
            # Only try to recover rate after a sequence of successful requests
            recovery_threshold = 10
            
            # If we've had several successes since last rate limit and it's been a while
            # since we last adjusted the rate upward, gradually increase the rate
            now = time.time()
            if (self.successful_request_count >= recovery_threshold and 
                (now - self.last_rate_recovery) > 30):  # Wait at least 30 seconds between recoveries
                
                old_rate = self.rate
                self.rate = min(self.rate * self.recovery_factor, self.max_tokens)
                
                if self.rate > old_rate:
                    logger.info(f"Increasing token rate from {old_rate:.2f} to {self.rate:.2f} tokens/sec after {self.successful_request_count} successful requests")
                    self.last_rate_recovery = now
                    
                    # Reset counter after successful recovery
                    self.successful_request_count = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the rate limiter."""
        with self._lock:
            self.add_tokens()
            
            return {
                "current_rate": self.rate,
                "available_tokens": self.tokens,
                "max_tokens": self.max_tokens,
                "rate_limit_count": self.rate_limit_count,
                "successful_request_count": self.successful_request_count,
                "time_since_last_limit": time.time() - self.last_rate_limit if self.last_rate_limit else None
            }

class RequestQueueManager:
    """
    Manages a priority queue for requests during rate limiting or service degradation.
    
    This class provides:
    - Priority-based queueing for different types of requests
    - Graceful handling of excess requests during rate limiting
    - Integration with the TokenBucketRateLimiter for controlled request processing
    """
    
    def __init__(
        self,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        max_queue_size: int = 100,
        worker_threads: int = 1,
        default_priority: RequestPriority = RequestPriority.NORMAL
    ):
        """
        Initialize the request queue manager.
        
        Args:
            rate_limiter: TokenBucketRateLimiter for controlling request rate
            max_queue_size: Maximum number of requests in the queue
            worker_threads: Number of worker threads for processing requests
            default_priority: Default priority for requests without specified priority
        """
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self.default_priority = default_priority
        self.max_queue_size = max_queue_size
        
        # Use a priority queue for request processing
        self.request_queue = queue.PriorityQueue(maxsize=max_queue_size)
        
        # Keep track of active and queued requests
        self._active_count = 0
        self._queued_count = 0
        self._lock = threading.RLock()
        
        # Controls for workers
        self._stop_event = threading.Event()
        self._workers = []
        
        # Start worker threads
        for i in range(worker_threads):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"request-queue-worker-{i}",
                daemon=True
            )
            self._workers.append(worker)
            worker.start()
            
        logger.info(f"RequestQueueManager initialized with {worker_threads} workers and max queue size {max_queue_size}")
    
    def enqueue(
        self,
        callback: Callable,
        *args,
        priority: Optional[RequestPriority] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> bool:
        """
        Add a request to the queue.
        
        Args:
            callback: Function to call when processing the request
            *args: Arguments to pass to the callback
            priority: Priority level for this request
            timeout: Maximum time to wait for queue space (None = no limit)
            **kwargs: Keyword arguments to pass to the callback
            
        Returns:
            bool: True if queued successfully, False if timed out or queue full
        """
        if self._stop_event.is_set():
            logger.warning("RequestQueueManager is shutting down, rejecting new request")
            return False
        
        priority = priority or self.default_priority
        request = QueuedRequest(
            priority=priority,
            timestamp=time.time(),
            callback=callback,
            args=args,
            kwargs=kwargs
        )
        
        try:
            # Try to add to the queue with timeout
            if self.request_queue.put(request, block=True, timeout=timeout):
                with self._lock:
                    self._queued_count += 1
                logger.debug(f"Request enqueued with priority {priority.name}")
                return True
        except queue.Full:
            logger.warning(f"Request queue full, rejecting request with priority {priority.name}")
            return False
    
    def _worker_loop(self) -> None:
        """Worker thread function to process queued requests."""
        while not self._stop_event.is_set():
            try:
                # Get the next request from the queue
                request = self.request_queue.get(block=True, timeout=1.0)
                
                with self._lock:
                    self._queued_count -= 1
                    self._active_count += 1
                
                # Wait for a token from the rate limiter
                if not self.rate_limiter.consume(block=True):
                    logger.warning("Failed to acquire rate limit token, re-queueing request")
                    # Put the request back in the queue
                    self.request_queue.put(request)
                    with self._lock:
                        self._queued_count += 1
                        self._active_count -= 1
                    continue
                
                # Process the request
                try:
                    logger.debug(f"Processing request with priority {request.priority.name}")
                    request.callback(*request.args, **request.kwargs)
                    # Record successful request with rate limiter
                    self.rate_limiter.record_success()
                except Exception as e:
                    # Check if it's a rate limit error
                    if isinstance(e, LLMRateLimitError):
                        logger.warning(f"Rate limit error during request processing: {str(e)}")
                        self.rate_limiter.record_rate_limit()
                    else:
                        logger.exception(f"Error processing request: {str(e)}")
                finally:
                    with self._lock:
                        self._active_count -= 1
                    # Mark task as done
                    self.request_queue.task_done()
                    
            except queue.Empty:
                # No requests in the queue, just continue
                pass
            except Exception as e:
                logger.exception(f"Unexpected error in request queue worker: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the request queue."""
        with self._lock:
            return {
                "active_requests": self._active_count,
                "queued_requests": self._queued_count,
                "queue_capacity": self.max_queue_size,
                "rate_limiter_status": self.rate_limiter.get_status()
            }
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the request queue manager.
        
        Args:
            wait: Whether to wait for all queued requests to complete
        """
        logger.info("Shutting down RequestQueueManager")
        
        # Signal workers to stop
        self._stop_event.set()
        
        if wait:
            # Wait for all requests to complete
            logger.info("Waiting for queued requests to complete")
            self.request_queue.join()
            
        # Wait for worker threads to exit
        for worker in self._workers:
            worker.join(timeout=1.0)
            
        logger.info("RequestQueueManager shutdown complete")

class NetworkConnectionManager:
    """
    Manages HTTP connections with connection pooling, configurable timeouts, and network monitoring.
    
    This class provides:
    - Connection pooling to reduce connection overhead
    - Operation-specific timeout configuration
    - Network status monitoring to detect broader connectivity issues
    """
    
    # Operation types for specific timeout settings
    class OperationType(Enum):
        DEFAULT = "default"
        REFLECTION = "reflection"
        GENERATION = "generation"
        EMBEDDING = "embedding"
        HEALTH_CHECK = "health_check"
    
    def __init__(
        self,
        limits: Optional[httpx.Limits] = None,
        timeouts: Optional[Dict[str, Union[float, httpx.Timeout]]] = None,
        retries: int = 1,
        http2: bool = True
    ):
        """
        Initialize the network connection manager.
        
        Args:
            limits: Connection pool limits
            timeouts: Operation-specific timeout settings
            retries: Number of connection retries
            http2: Whether to enable HTTP/2
        """
        # Default connection pool settings
        self.limits = limits or httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0  # seconds
        )
        
        # Default timeout settings by operation type
        self.timeouts = {
            self.OperationType.DEFAULT.value: httpx.Timeout(
                connect=5.0,  # connection timeout
                read=20.0,    # read timeout
                write=10.0,   # write timeout
                pool=5.0      # pool timeout
            ),
            self.OperationType.REFLECTION.value: httpx.Timeout(
                connect=5.0,
                read=60.0,    # longer timeout for reflection
                write=10.0,
                pool=5.0
            ),
            self.OperationType.GENERATION.value: httpx.Timeout(
                connect=5.0,
                read=120.0,   # longer timeout for generation
                write=10.0,
                pool=5.0
            ),
            self.OperationType.EMBEDDING.value: httpx.Timeout(
                connect=5.0,
                read=30.0,
                write=10.0,
                pool=5.0
            ),
            self.OperationType.HEALTH_CHECK.value: httpx.Timeout(
                connect=2.0,
                read=5.0,
                write=2.0,
                pool=2.0
            )
        }
        
        # Override defaults with any provided timeouts
        if timeouts:
            for operation_type, timeout in timeouts.items():
                if isinstance(timeout, (int, float)):
                    # If a simple number is provided, use it as a global timeout
                    self.timeouts[operation_type] = httpx.Timeout(timeout)
                else:
                    # Otherwise use the provided Timeout object
                    self.timeouts[operation_type] = timeout
        
        # Connection parameters
        self.retries = retries
        self.http2 = http2
        
        # Network status metrics
        self._network_status = {
            "status": "healthy",
            "successful_connections": 0,
            "failed_connections": 0,
            "consecutive_failures": 0,
            "last_success_time": time.time(),
            "last_failure_time": 0,
            "failures_by_type": {},
            "response_times": deque(maxlen=100)  # Keep last 100 response times
        }
        self._network_lock = threading.RLock()
        
        # Create the HTTP client
        self._client = httpx.Client(
            limits=self.limits,
            timeout=self.get_timeout(self.OperationType.DEFAULT.value),
            http2=self.http2
        )
        
        # Track client instances
        self._async_clients = {}
        self._lock = threading.RLock()
        
        logger.info(f"NetworkConnectionManager initialized with {self.limits.max_connections} max connections, HTTP/2={'enabled' if http2 else 'disabled'}")
    
    def get_timeout(self, operation_type: str) -> httpx.Timeout:
        """
        Get the timeout for a specific operation type.
        
        Args:
            operation_type: Type of operation (default, reflection, generation, etc.)
            
        Returns:
            httpx.Timeout object for the operation
        """
        if operation_type in self.timeouts:
            return self.timeouts[operation_type]
        return self.timeouts[self.OperationType.DEFAULT.value]
    
    def record_successful_connection(self, response_time: float) -> None:
        """
        Record a successful connection and update network status.
        
        Args:
            response_time: Time taken for the request/response in seconds
        """
        with self._network_lock:
            self._network_status["successful_connections"] += 1
            self._network_status["consecutive_failures"] = 0
            self._network_status["last_success_time"] = time.time()
            self._network_status["response_times"].append(response_time)
            
            # If we were previously in a degraded state, restore to healthy
            if self._network_status["status"] != "healthy":
                logger.info("Network status restored to healthy after successful connection")
                self._network_status["status"] = "healthy"
    
    def record_failed_connection(self, error_type: str) -> None:
        """
        Record a failed connection and update network status.
        
        Args:
            error_type: Type of error encountered
        """
        with self._network_lock:
            self._network_status["failed_connections"] += 1
            self._network_status["consecutive_failures"] += 1
            self._network_status["last_failure_time"] = time.time()
            
            # Update failure counter by type
            if error_type in self._network_status["failures_by_type"]:
                self._network_status["failures_by_type"][error_type] += 1
            else:
                self._network_status["failures_by_type"][error_type] = 1
            
            # After several consecutive failures, mark network as degraded
            if (self._network_status["consecutive_failures"] >= 3 and 
                self._network_status["status"] == "healthy"):
                logger.warning(f"Network status degraded after {self._network_status['consecutive_failures']} consecutive failures")
                self._network_status["status"] = "degraded"
            
            # If many failures without recent success, mark as potentially down
            if (self._network_status["consecutive_failures"] >= 10 and
                time.time() - self._network_status["last_success_time"] > 300):  # 5 minutes
                logger.error("Network appears to be down - no successful connections in over 5 minutes")
                self._network_status["status"] = "down"
    
    def get_network_status(self) -> Dict[str, Any]:
        """
        Get the current network status.
        
        Returns:
            Dict with network status information
        """
        with self._network_lock:
            status = dict(self._network_status)
            
            # Calculate average response time
            if status["response_times"]:
                status["avg_response_time"] = sum(status["response_times"]) / len(status["response_times"])
            else:
                status["avg_response_time"] = None
                
            return status
    
    def get_client(self, operation_type: str = None) -> httpx.Client:
        """
        Get an HTTP client for the specified operation type.
        
        Args:
            operation_type: Type of operation (default, reflection, generation, etc.)
            
        Returns:
            httpx.Client instance with appropriate configuration
        """
        # Use the default client with appropriate timeout
        timeout = self.get_timeout(operation_type or self.OperationType.DEFAULT.value)
        
        with self._lock:
            # Configure the client with the appropriate timeout
            self._client.timeout = timeout
            return self._client
    
    async def get_async_client(self, operation_type: str = None) -> httpx.AsyncClient:
        """
        Get an async HTTP client for the specified operation type.
        
        Args:
            operation_type: Type of operation (default, reflection, generation, etc.)
            
        Returns:
            httpx.AsyncClient instance with appropriate configuration
        """
        operation_type = operation_type or self.OperationType.DEFAULT.value
        
        with self._lock:
            # Check if we already have a client for this operation type
            if operation_type in self._async_clients:
                return self._async_clients[operation_type]
            
            # Create a new client with appropriate settings
            timeout = self.get_timeout(operation_type)
            client = httpx.AsyncClient(
                limits=self.limits,
                timeout=timeout,
                http2=self.http2
            )
            
            # Store for future use
            self._async_clients[operation_type] = client
            return client
    
    def perform_health_check(self, url: str = "https://www.google.com") -> bool:
        """
        Perform a network health check.
        
        Args:
            url: URL to check connectivity to
            
        Returns:
            bool: True if health check succeeded, False otherwise
        """
        start_time = time.time()
        client = self.get_client(self.OperationType.HEALTH_CHECK.value)
        
        try:
            response = client.get(url)
            response.raise_for_status()
            
            # Record successful connection
            elapsed = time.time() - start_time
            self.record_successful_connection(elapsed)
            
            logger.debug(f"Health check to {url} succeeded in {elapsed:.2f}s")
            return True
            
        except httpx.RequestError as e:
            # Record failed connection
            self.record_failed_connection(type(e).__name__)
            
            logger.warning(f"Health check to {url} failed: {str(e)}")
            return False
    
    def close(self) -> None:
        """Close all HTTP clients and release resources."""
        with self._lock:
            # Close the synchronous client
            if self._client and not self._client.is_closed:
                self._client.close()
            
            # Close all async clients
            for operation_type, client in self._async_clients.items():
                if client and not client.is_closed:
                    client.aclose()
            
            # Clear the clients dictionary
            self._async_clients = {}
            
        logger.info("NetworkConnectionManager closed all HTTP clients")

class ServiceHealthMonitor:
    """
    Monitors the health of LLM API services and adapts behavior based on service status.
    
    This class provides:
    - Periodic health checks of API endpoints
    - Status tracking for multiple service providers
    - Proactive circuit breaking for degraded services
    - Automatic status updates based on request outcomes
    """
    
    # Service health states
    class ServiceStatus(Enum):
        HEALTHY = "healthy"          # Service is fully operational
        DEGRADED = "degraded"        # Service has issues but is usable
        RATE_LIMITED = "limited"     # Service is temporarily rate limiting requests
        UNAVAILABLE = "unavailable"  # Service is not available
        UNKNOWN = "unknown"          # Service status not yet determined
    
    def __init__(
        self,
        health_check_interval: float = 300.0,  # 5 minutes
        health_check_urls: Optional[Dict[str, str]] = None,
        circuit_break_threshold: int = 5,  # failures before breaking circuit
        circuit_recovery_time: float = 60.0,  # seconds
        enable_adaptive_routing: bool = True,
        connection_manager: Optional[NetworkConnectionManager] = None,
    ):
        """
        Initialize the service health monitor.
        
        Args:
            health_check_interval: Time between health checks in seconds
            health_check_urls: Dict mapping service names to health check URLs
            circuit_break_threshold: Number of failures before breaking circuit
            circuit_recovery_time: Time to wait before trying a broken service again
            enable_adaptive_routing: Whether to route requests to healthier services
            connection_manager: NetworkConnectionManager instance for HTTP requests
        """
        self.health_check_interval = health_check_interval
        self.health_check_urls = health_check_urls or {}
        self.circuit_break_threshold = circuit_break_threshold
        self.circuit_recovery_time = circuit_recovery_time
        self.enable_adaptive_routing = enable_adaptive_routing
        
        # Use provided connection manager or create a new one
        self.connection_manager = connection_manager or NetworkConnectionManager()
        
        # Track service health status
        self._service_status = {}
        self._service_metrics = {}
        self._lock = threading.RLock()
        
        # Initialize status for each service
        for service_name in self.health_check_urls.keys():
            self._initialize_service_status(service_name)
        
        # Background health check thread
        self._stop_event = threading.Event()
        self._health_check_thread = None
        
        # Start health check thread if we have URLs to check
        if self.health_check_urls:
            self._start_health_check_thread()
            
        logger.info(f"ServiceHealthMonitor initialized for {len(self.health_check_urls)} services, checking every {health_check_interval} seconds")
    
    def _initialize_service_status(self, service_name: str) -> None:
        """Initialize status tracking for a service."""
        with self._lock:
            self._service_status[service_name] = self.ServiceStatus.UNKNOWN
            self._service_metrics[service_name] = {
                "failure_count": 0,
                "success_count": 0,
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "last_success_time": 0,
                "last_failure_time": 0,
                "circuit_broken": False,
                "circuit_break_until": 0,
                "rate_limited_until": 0,
                "avg_response_time": None,
                "recent_response_times": deque(maxlen=10),
                "error_counts": {},
                "last_health_check": 0,
                "last_health_check_success": False,
            }
    
    def _start_health_check_thread(self) -> None:
        """Start the background health check thread."""
        if self._health_check_thread is not None and self._health_check_thread.is_alive():
            logger.warning("Health check thread already running, not starting a new one")
            return
            
        self._stop_event.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            name="service-health-monitor",
            daemon=True
        )
        self._health_check_thread.start()
        logger.debug("Started service health check thread")
    
    def _health_check_loop(self) -> None:
        """Background thread loop for performing health checks."""
        while not self._stop_event.is_set():
            try:
                # Perform health checks for all registered services
                for service_name, url in self.health_check_urls.items():
                    try:
                        self._check_service_health(service_name, url)
                    except Exception as e:
                        logger.exception(f"Error during health check for {service_name}: {str(e)}")
                
                # Sleep until next check interval
                # Use small intervals to check stop event more frequently
                for _ in range(int(self.health_check_interval / 5)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(5)
            except Exception as e:
                logger.exception(f"Unexpected error in health check loop: {str(e)}")
                # In case of unexpected error, sleep briefly to avoid tight loop
                time.sleep(10)
    
    def _check_service_health(self, service_name: str, url: str) -> None:
        """
        Perform a health check for a specific service.
        
        Args:
            service_name: Name of the service to check
            url: URL to check for health
        """
        # Skip if we don't have this service registered
        if service_name not in self._service_metrics:
            self._initialize_service_status(service_name)
        
        with self._lock:
            # Skip health check if circuit is broken and we're still in the recovery period
            if (self._service_metrics[service_name]["circuit_broken"] and
                time.time() < self._service_metrics[service_name]["circuit_break_until"]):
                logger.debug(f"Skipping health check for {service_name}: circuit broken")
                return
            
            # Skip health check if we're rate limited and the rate limit period hasn't expired
            if time.time() < self._service_metrics[service_name]["rate_limited_until"]:
                logger.debug(f"Skipping health check for {service_name}: rate limited")
                return
        
        # Record start time for response time calculation
        start_time = time.time()
        
        # Perform the health check using the connection manager
        success = self.connection_manager.perform_health_check(url)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        with self._lock:
            metrics = self._service_metrics[service_name]
            
            # Update last health check time
            metrics["last_health_check"] = start_time
            metrics["last_health_check_success"] = success
            
            if success:
                # Update success metrics
                metrics["success_count"] += 1
                metrics["consecutive_successes"] += 1
                metrics["consecutive_failures"] = 0
                metrics["last_success_time"] = start_time
                
                # Update response time tracking
                metrics["recent_response_times"].append(response_time)
                metrics["avg_response_time"] = sum(metrics["recent_response_times"]) / len(metrics["recent_response_times"])
                
                # Clear circuit breaker if it was broken
                if metrics["circuit_broken"]:
                    logger.info(f"Service {service_name} health check succeeded, resetting circuit breaker")
                    metrics["circuit_broken"] = False
                    metrics["circuit_break_until"] = 0
                
                # Update service status based on consecutive successes
                if metrics["consecutive_successes"] >= 2:
                    new_status = self.ServiceStatus.HEALTHY
                else:
                    # First success after failures - still consider degraded until consistent
                    new_status = self.ServiceStatus.DEGRADED
                    
                # Check if status is already rate limited, maintain that status if it's still active
                if (self._service_status[service_name] == self.ServiceStatus.RATE_LIMITED and
                    time.time() < metrics["rate_limited_until"]):
                    new_status = self.ServiceStatus.RATE_LIMITED
                
                # Only log if status changed
                if self._service_status[service_name] != new_status:
                    logger.info(f"Service {service_name} status changed from {self._service_status[service_name].value} to {new_status.value}")
                self._service_status[service_name] = new_status
                
            else:
                # Update failure metrics
                metrics["failure_count"] += 1
                metrics["consecutive_failures"] += 1
                metrics["consecutive_successes"] = 0
                metrics["last_failure_time"] = start_time
                
                # Trip the circuit breaker if we've hit the threshold
                if metrics["consecutive_failures"] >= self.circuit_break_threshold:
                    if not metrics["circuit_broken"]:
                        logger.warning(f"Service {service_name} health check failed {metrics['consecutive_failures']} consecutive times, breaking circuit")
                        metrics["circuit_broken"] = True
                    
                    # Set or extend the circuit break period
                    metrics["circuit_break_until"] = time.time() + self.circuit_recovery_time
                    
                # Update service status based on consecutive failures
                if metrics["consecutive_failures"] >= self.circuit_break_threshold:
                    new_status = self.ServiceStatus.UNAVAILABLE
                else:
                    new_status = self.ServiceStatus.DEGRADED
                
                # Only log if status changed
                if self._service_status[service_name] != new_status:
                    logger.warning(f"Service {service_name} status changed from {self._service_status[service_name].value} to {new_status.value}")
                self._service_status[service_name] = new_status
    
    def record_request_result(
        self, 
        service_name: str, 
        success: bool, 
        response_time: Optional[float] = None,
        error_type: Optional[str] = None,
        rate_limited_duration: Optional[float] = None
    ) -> None:
        """
        Record the result of an API request to update service status.
        
        Args:
            service_name: Name of the service the request was sent to
            success: Whether the request was successful
            response_time: Time taken for the request/response in seconds
            error_type: Type of error if the request failed
            rate_limited_duration: Duration of rate limit if rate limited
        """
        # Initialize service if we don't have it yet
        if service_name not in self._service_metrics:
            self._initialize_service_status(service_name)
        
        with self._lock:
            metrics = self._service_metrics[service_name]
            now = time.time()
            
            if success:
                # Update success metrics
                metrics["success_count"] += 1
                metrics["consecutive_successes"] += 1
                metrics["consecutive_failures"] = 0
                metrics["last_success_time"] = now
                
                # Update response time tracking if provided
                if response_time is not None:
                    metrics["recent_response_times"].append(response_time)
                    if metrics["recent_response_times"]:
                        metrics["avg_response_time"] = sum(metrics["recent_response_times"]) / len(metrics["recent_response_times"])
                
                # Determine new status based on consecutive successes
                if metrics["consecutive_successes"] >= 2:
                    new_status = self.ServiceStatus.HEALTHY
                else:
                    # First success after failures - still consider degraded until consistent
                    new_status = self.ServiceStatus.DEGRADED
                
                # Only update status if we're not rate limited or circuit broken
                if (self._service_status[service_name] != self.ServiceStatus.RATE_LIMITED and 
                    not (metrics["circuit_broken"] and now < metrics["circuit_break_until"])):
                    
                    # Only log if status changed
                    if self._service_status[service_name] != new_status:
                        logger.info(f"Service {service_name} status changed from {self._service_status[service_name].value} to {new_status.value}")
                    self._service_status[service_name] = new_status
                
            else:
                # Update failure metrics
                metrics["failure_count"] += 1
                metrics["consecutive_failures"] += 1
                metrics["consecutive_successes"] = 0
                metrics["last_failure_time"] = now
                
                # Track error type
                if error_type:
                    if error_type in metrics["error_counts"]:
                        metrics["error_counts"][error_type] += 1
                    else:
                        metrics["error_counts"][error_type] = 1
                
                # Handle rate limiting specially
                if error_type == "LLMRateLimitError" and rate_limited_duration is not None:
                    # Set rate limited status with expiration
                    metrics["rate_limited_until"] = now + rate_limited_duration
                    new_status = self.ServiceStatus.RATE_LIMITED
                    
                    logger.warning(f"Service {service_name} rate limited for {rate_limited_duration} seconds")
                    
                # Trip the circuit breaker if we've hit the threshold (except for rate limits)
                elif metrics["consecutive_failures"] >= self.circuit_break_threshold and error_type != "LLMRateLimitError":
                    if not metrics["circuit_broken"]:
                        logger.warning(f"Service {service_name} had {metrics['consecutive_failures']} consecutive failures, breaking circuit")
                        metrics["circuit_broken"] = True
                    
                    # Set or extend the circuit break period
                    metrics["circuit_break_until"] = now + self.circuit_recovery_time
                    new_status = self.ServiceStatus.UNAVAILABLE
                    
                # Use degraded status for non-circuit-breaking failures
                else:
                    new_status = self.ServiceStatus.DEGRADED
                
                # Update service status
                if self._service_status[service_name] != new_status:
                    logger.warning(f"Service {service_name} status changed from {self._service_status[service_name].value} to {new_status.value}")
                self._service_status[service_name] = new_status
    
    def is_service_available(self, service_name: str) -> bool:
        """
        Check if a service is currently available for requests.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            bool: True if service is available, False if unavailable or circuit broken
        """
        with self._lock:
            # Initialize service if we don't have it yet
            if service_name not in self._service_metrics:
                self._initialize_service_status(service_name)
                return True  # Assume available until proven otherwise
                
            metrics = self._service_metrics[service_name]
            
            # Check if circuit breaker is active
            if metrics["circuit_broken"] and time.time() < metrics["circuit_break_until"]:
                return False
                
            # Check if currently rate limited
            if time.time() < metrics["rate_limited_until"]:
                return False
                
            # Consider service available if not circuit broken or rate limited
            return self._service_status[service_name] not in [self.ServiceStatus.UNAVAILABLE]
    
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """
        Get the current status of a service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            ServiceStatus: Current status of the service
        """
        with self._lock:
            # Initialize service if we don't have it yet
            if service_name not in self._service_status:
                self._initialize_service_status(service_name)
                return self.ServiceStatus.UNKNOWN
                
            return self._service_status[service_name]
    
    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """
        Get detailed metrics for a service.
        
        Args:
            service_name: Name of the service to get metrics for
            
        Returns:
            Dict with service metrics
        """
        with self._lock:
            # Initialize service if we don't have it yet
            if service_name not in self._service_metrics:
                self._initialize_service_status(service_name)
                
            # Return a copy to avoid external modification
            return dict(self._service_metrics[service_name])
    
    def get_all_services_status(self) -> Dict[str, ServiceStatus]:
        """
        Get status for all monitored services.
        
        Returns:
            Dict mapping service names to their current status
        """
        with self._lock:
            # Return a copy to avoid external modification
            return {service: status for service, status in self._service_status.items()}
    
    def register_service(self, service_name: str, health_check_url: Optional[str] = None) -> None:
        """
        Register a new service with the health monitor.
        
        Args:
            service_name: Name of the service to register
            health_check_url: URL for health checks (can be None)
        """
        with self._lock:
            self._initialize_service_status(service_name)
            
            if health_check_url:
                self.health_check_urls[service_name] = health_check_url
                logger.info(f"Registered service {service_name} with health check URL {health_check_url}")
            else:
                logger.info(f"Registered service {service_name} without health check URL")
    
    def shutdown(self) -> None:
        """Stop background health check thread and close connections."""
        logger.info("Shutting down ServiceHealthMonitor")
        
        # Signal health check thread to stop
        self._stop_event.set()
        
        # Wait for health check thread to exit
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=1.0)
            
        # Close connection manager
        if self.connection_manager:
            self.connection_manager.close()
            
        logger.info("ServiceHealthMonitor shutdown complete")

class ErrorRecoveryStrategies:
    """
    Provides specialized recovery strategies for different types of LLM API errors.
    
    This class integrates the other components to provide a comprehensive error
    recovery system for LLM API interactions, handling:
    - Rate limit errors
    - Network errors
    - Service unavailability
    
    Each strategy is tailored to the specific error type and designed to maximize
    the chances of successful recovery while minimizing impact on the application.
    """
    
    def __init__(
        self,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        request_queue: Optional[RequestQueueManager] = None,
        connection_manager: Optional[NetworkConnectionManager] = None,
        service_monitor: Optional[ServiceHealthMonitor] = None,
        default_retry_attempts: int = 3,
        max_retry_delay: float = 60.0,  # seconds
        jitter_factor: float = 0.1,  # 10% jitter
        circuit_breaker_reset_timeout: float = 300.0,  # 5 minutes
    ):
        """
        Initialize the error recovery strategies.
        
        Args:
            rate_limiter: TokenBucketRateLimiter for rate limiting
            request_queue: RequestQueueManager for request queueing and prioritization
            connection_manager: NetworkConnectionManager for connection handling
            service_monitor: ServiceHealthMonitor for service health tracking
            default_retry_attempts: Default number of retry attempts
            max_retry_delay: Maximum delay between retries
            jitter_factor: Random jitter factor to add to retry delays
            circuit_breaker_reset_timeout: Time before resetting a circuit breaker
        """
        # Create components if not provided
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self.connection_manager = connection_manager or NetworkConnectionManager()
        self.service_monitor = service_monitor or ServiceHealthMonitor(
            connection_manager=self.connection_manager
        )
        self.request_queue = request_queue or RequestQueueManager(
            rate_limiter=self.rate_limiter
        )
        
        # Retry configuration
        self.default_retry_attempts = default_retry_attempts
        self.max_retry_delay = max_retry_delay
        self.jitter_factor = jitter_factor
        self.circuit_breaker_reset_timeout = circuit_breaker_reset_timeout
        
        # Track circuit breaker status for different error types
        self._circuit_breakers = {
            "rate_limit": {
                "tripped": False,
                "reset_time": 0,
                "failure_count": 0,
                "threshold": 5,
            },
            "network": {
                "tripped": False,
                "reset_time": 0,
                "failure_count": 0,
                "threshold": 3,
            },
            "service_unavailable": {
                "tripped": False,
                "reset_time": 0,
                "failure_count": 0,
                "threshold": 3,
            }
        }
        self._lock = threading.RLock()
        
        logger.info("ErrorRecoveryStrategies initialized with specialized strategies for rate limits, network errors, and service unavailability")
    
    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to a delay value."""
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor) * delay
        return max(0, delay + jitter)
    
    def _calculate_retry_delay(self, attempt: int, base_delay: float = 1.0, rate_limit_duration: Optional[float] = None) -> float:
        """
        Calculate delay before next retry attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (1-based)
            base_delay: Base delay in seconds for exponential calculation
            rate_limit_duration: Specific rate limit duration if known
            
        Returns:
            Delay in seconds before next retry
        """
        if rate_limit_duration is not None:
            # If we have an explicit rate limit duration, use that
            delay = rate_limit_duration
        else:
            # Otherwise, use exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), self.max_retry_delay)
        
        # Add jitter to prevent thundering herd
        return self._add_jitter(delay)
    
    def _should_retry(self, error_type: str, attempt: int, max_attempts: int) -> bool:
        """
        Determine if a retry should be attempted based on error type and attempt count.
        
        Args:
            error_type: Type of error that occurred
            attempt: Current attempt number
            max_attempts: Maximum number of attempts allowed
            
        Returns:
            bool: True if retry should be attempted, False otherwise
        """
        # Don't retry if max attempts reached
        if attempt >= max_attempts:
            return False
            
        with self._lock:
            # Check circuit breaker for relevant error type
            circuit_type = self._map_error_to_circuit(error_type)
            if circuit_type in self._circuit_breakers:
                circuit = self._circuit_breakers[circuit_type]
                
                # If circuit is tripped and not yet reset time, don't retry
                if circuit["tripped"] and time.time() < circuit["reset_time"]:
                    logger.warning(f"Circuit breaker for {circuit_type} errors is open, skipping retry")
                    return False
                    
                # If circuit was tripped but reset time has passed, reset it
                if circuit["tripped"] and time.time() >= circuit["reset_time"]:
                    logger.info(f"Resetting circuit breaker for {circuit_type} errors")
                    circuit["tripped"] = False
                    circuit["failure_count"] = 0
        
        return True
    
    def _map_error_to_circuit(self, error_type: str) -> str:
        """Map an error type to a circuit breaker category."""
        if error_type in ("LLMRateLimitError"):
            return "rate_limit"
        elif error_type in ("LLMNetworkError", "LLMConnectionError", "LLMTimeoutError"):
            return "network"
        elif error_type in ("LLMServiceUnavailableError", "LLMServerError"):
            return "service_unavailable"
        else:
            return "other"
    
    def _update_circuit_breaker(self, error_type: str, success: bool) -> None:
        """
        Update circuit breaker status based on request result.
        
        Args:
            error_type: Type of error that occurred (or None if success)
            success: Whether the request ultimately succeeded
        """
        if success:
            # On success, reduce failure count for all circuit breakers
            with self._lock:
                for circuit_type, circuit in self._circuit_breakers.items():
                    if circuit["failure_count"] > 0:
                        circuit["failure_count"] = max(0, circuit["failure_count"] - 1)
            return
            
        # On failure, update the appropriate circuit breaker
        circuit_type = self._map_error_to_circuit(error_type)
        if circuit_type not in self._circuit_breakers:
            return
            
        with self._lock:
            circuit = self._circuit_breakers[circuit_type]
            circuit["failure_count"] += 1
            
            # Trip circuit breaker if threshold reached
            if circuit["failure_count"] >= circuit["threshold"] and not circuit["tripped"]:
                circuit["tripped"] = True
                circuit["reset_time"] = time.time() + self.circuit_breaker_reset_timeout
                logger.warning(f"Circuit breaker tripped for {circuit_type} errors after {circuit['failure_count']} consecutive failures")
    
    def handle_rate_limit_error(
        self,
        service_name: str,
        error: LLMRateLimitError,
        retry_func: Callable,
        *args,
        retry_delay: Optional[float] = None,
        max_attempts: Optional[int] = None,
        priority: Optional[RequestPriority] = None,
        **kwargs
    ) -> T:
        """
        Handle a rate limit error with adaptive backoff and queuing.
        
        Args:
            service_name: Name of the service that rate limited the request
            error: The rate limit error that occurred
            retry_func: Function to retry
            *args: Arguments to pass to the retry function
            retry_delay: Initial delay before retry (None to use error's retry_after or calculate)
            max_attempts: Maximum number of retry attempts
            priority: Priority for the queued request
            **kwargs: Keyword arguments to pass to the retry function
            
        Returns:
            Result from the retry_func if successful
            
        Raises:
            LLMRateLimitError: If rate limit persists after max retries
        """
        max_attempts = max_attempts or self.default_retry_attempts
        attempt = 1
        
        # Extract retry duration from error if available
        rate_limit_duration = getattr(error, "retry_after", None)
        if isinstance(rate_limit_duration, str):
            try:
                # Try to parse ISO format date string to get seconds until then
                from dateutil.parser import parse
                rate_limit_time = parse(rate_limit_duration)
                rate_limit_duration = max(0, (rate_limit_time - datetime.now()).total_seconds())
            except:
                # If parsing fails, use default exponential backoff
                rate_limit_duration = None
        
        # Use provided retry_delay, error's retry_after, or calculate
        delay = retry_delay or rate_limit_duration or self._calculate_retry_delay(attempt, rate_limit_duration=rate_limit_duration)
        
        # Record rate limit in service monitor and rate limiter
        self.service_monitor.record_request_result(
            service_name=service_name,
            success=False,
            error_type="LLMRateLimitError",
            rate_limited_duration=delay
        )
        self.rate_limiter.record_rate_limit()
        
        logger.warning(f"Rate limit error for {service_name}, backing off for {delay:.2f} seconds before retry {attempt}/{max_attempts}")
        
        # Try the special rate limit recovery approach: queue with priority
        priority = priority or RequestPriority.NORMAL
        success = False
        
        while attempt <= max_attempts and not success:
            if attempt > 1:
                # Recalculate delay for subsequent attempts
                delay = self._calculate_retry_delay(attempt, rate_limit_duration=rate_limit_duration)
                logger.info(f"Rate limit retry {attempt}/{max_attempts} after {delay:.2f} seconds")
            
            # Wait for the backoff period
            time.sleep(delay)
            
            # Queue the retry with priority
            try:
                # Attempt to queue the request
                enqueued = self.request_queue.enqueue(
                    retry_func, *args, priority=priority, **kwargs
                )
                
                if not enqueued:
                    logger.warning(f"Failed to enqueue rate-limited request, attempt {attempt}/{max_attempts}")
                    # If queuing fails, increment attempt and try again with backoff
                    attempt += 1
                    continue
                
                # Wait for result
                result = retry_func(*args, **kwargs)
                success = True
                
                # Record successful request
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=True
                )
                self.rate_limiter.record_success()
                self._update_circuit_breaker("LLMRateLimitError", True)
                
                return result
                
            except LLMRateLimitError as e:
                logger.warning(f"Rate limit persists on retry {attempt}/{max_attempts}: {str(e)}")
                self.rate_limiter.record_rate_limit()
                self._update_circuit_breaker("LLMRateLimitError", False)
                
                # Update service monitor with new rate limit
                rate_limit_duration = getattr(e, "retry_after", None)
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=False,
                    error_type="LLMRateLimitError",
                    rate_limited_duration=rate_limit_duration or delay * 2
                )
                
                # Try again with backoff
                attempt += 1
                
            except Exception as other_e:
                # For other errors, update circuit breaker and re-raise
                self._update_circuit_breaker(type(other_e).__name__, False)
                raise
                
        # If we exit the loop without success, re-raise the last error
        if not success:
            raise LLMRateLimitError(f"Rate limit persisted after {max_attempts} retry attempts")
    
    def handle_network_error(
        self,
        service_name: str,
        error: Union[LLMNetworkError, LLMConnectionError, LLMTimeoutError],
        retry_func: Callable,
        *args,
        operation_type: Optional[str] = None,
        max_attempts: Optional[int] = None,
        **kwargs
    ) -> T:
        """
        Handle network errors with connection pooling and adaptive timeouts.
        
        Args:
            service_name: Name of the service that experienced the network error
            error: The network error that occurred
            retry_func: Function to retry
            *args: Arguments to pass to the retry function
            operation_type: Type of operation for timeout configuration
            max_attempts: Maximum number of retry attempts
            **kwargs: Keyword arguments to pass to the retry function
            
        Returns:
            Result from the retry_func if successful
            
        Raises:
            LLMNetworkError: If network issues persist after max retries
        """
        max_attempts = max_attempts or self.default_retry_attempts
        attempt = 1
        
        # Record failed connection
        self.connection_manager.record_failed_connection(type(error).__name__)
        
        # Record error in service monitor
        self.service_monitor.record_request_result(
            service_name=service_name,
            success=False,
            error_type=type(error).__name__
        )
        
        # Update circuit breaker
        self._update_circuit_breaker(type(error).__name__, False)
        
        # If the service is known to be unavailable, fail fast
        if not self.service_monitor.is_service_available(service_name):
            logger.warning(f"Service {service_name} is marked as unavailable, not attempting retries")
            raise error
        
        # Determine operation type for timeout settings
        if operation_type is None:
            # Try to infer operation type from the kwargs or use default
            if "model" in kwargs and kwargs.get("model", "").lower().find("embed") >= 0:
                operation_type = NetworkConnectionManager.OperationType.EMBEDDING.value
            elif any(k in kwargs for k in ["messages", "prompt"]):
                operation_type = NetworkConnectionManager.OperationType.GENERATION.value
            else:
                operation_type = NetworkConnectionManager.OperationType.DEFAULT.value
        
        logger.warning(f"Network error for {service_name} ({operation_type}): {str(error)}, will retry {max_attempts} times")
        
        success = False
        last_error = error
        
        while attempt <= max_attempts and not success:
            # Calculate delay with exponential backoff and jitter
            delay = self._calculate_retry_delay(attempt)
            
            logger.info(f"Network error retry {attempt}/{max_attempts} after {delay:.2f} seconds")
            
            # Wait for the backoff period
            time.sleep(delay)
            
            try:
                # Perform health check to verify connectivity
                if attempt > 1 and not self.connection_manager.perform_health_check():
                    logger.warning("Network health check failed, continuing with retry anyway")
                
                # Get appropriate client with timeout for this operation type
                # If the request function accepts a client parameter, provide it
                if "client" in kwargs:
                    kwargs["client"] = self.connection_manager.get_client(operation_type)
                
                start_time = time.time()
                result = retry_func(*args, **kwargs)
                response_time = time.time() - start_time
                
                # Record successful connection
                self.connection_manager.record_successful_connection(response_time)
                
                # Update service monitor
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=True,
                    response_time=response_time
                )
                
                # Update circuit breaker
                self._update_circuit_breaker(type(error).__name__, True)
                
                success = True
                return result
                
            except (LLMNetworkError, LLMConnectionError, LLMTimeoutError) as e:
                # Record continued network failure
                self.connection_manager.record_failed_connection(type(e).__name__)
                
                # Update service monitor
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=False,
                    error_type=type(e).__name__
                )
                
                # Update circuit breaker
                self._update_circuit_breaker(type(e).__name__, False)
                
                # Try again with backoff
                attempt += 1
                last_error = e
                
            except Exception as other_e:
                # For other errors, record failure but don't retry
                self._update_circuit_breaker(type(other_e).__name__, False)
                raise
        
        # If we exit the loop without success, re-raise the last error
        if not success:
            raise LLMNetworkError(f"Network error persisted after {max_attempts} retry attempts: {str(last_error)}")
    
    def handle_service_unavailable_error(
        self,
        service_name: str,
        error: Union[LLMServiceUnavailableError, LLMServerError],
        retry_func: Callable,
        *args,
        fallback_func: Optional[Callable] = None,
        max_attempts: Optional[int] = None,
        **kwargs
    ) -> T:
        """
        Handle service unavailable errors with circuit breaking and potential fallback.
        
        Args:
            service_name: Name of the service that is unavailable
            error: The service unavailable error that occurred
            retry_func: Function to retry
            *args: Arguments to pass to the retry function
            fallback_func: Alternative function to call if service remains unavailable
            max_attempts: Maximum number of retry attempts
            **kwargs: Keyword arguments to pass to the retry function
            
        Returns:
            Result from the retry_func or fallback_func if successful
            
        Raises:
            LLMServiceUnavailableError: If service unavailability persists after max retries and no fallback exists
        """
        max_attempts = max_attempts or self.default_retry_attempts
        attempt = 1
        
        # Record error in service monitor with service unavailable status
        self.service_monitor.record_request_result(
            service_name=service_name,
            success=False,
            error_type=type(error).__name__
        )
        
        # Update circuit breaker
        self._update_circuit_breaker(type(error).__name__, False)
        
        # If circuit breaker is already tripped for this type of error, try fallback immediately
        circuit_type = self._map_error_to_circuit(type(error).__name__)
        with self._lock:
            circuit = self._circuit_breakers.get(circuit_type)
            if circuit and circuit["tripped"] and time.time() < circuit["reset_time"]:
                if fallback_func:
                    logger.warning(f"Circuit breaker for {service_name} is open, using fallback immediately")
                    return fallback_func(*args, **kwargs)
        
        logger.warning(f"Service unavailable error for {service_name}: {str(error)}, will retry {max_attempts} times")
        
        success = False
        last_error = error
        
        while attempt <= max_attempts and not success:
            # Calculate delay with exponential backoff and jitter
            delay = self._calculate_retry_delay(attempt, base_delay=2.0)  # Longer base delay for server errors
            
            logger.info(f"Service unavailable retry {attempt}/{max_attempts} after {delay:.2f} seconds")
            
            # Wait for the backoff period
            time.sleep(delay)
            
            try:
                # Check if service is available before retry
                if not self.service_monitor.is_service_available(service_name):
                    logger.warning(f"Service {service_name} is still marked as unavailable")
                    
                    # If service is still unavailable and we have a fallback,
                    # use it instead of continuing to retry
                    if fallback_func and attempt >= max_attempts // 2:
                        logger.warning(f"Switching to fallback after {attempt} failed attempts")
                        return fallback_func(*args, **kwargs)
                
                start_time = time.time()
                result = retry_func(*args, **kwargs)
                response_time = time.time() - start_time
                
                # Record successful request
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=True,
                    response_time=response_time
                )
                
                # Update circuit breaker
                self._update_circuit_breaker(type(error).__name__, True)
                
                success = True
                return result
                
            except (LLMServiceUnavailableError, LLMServerError) as e:
                # Update service monitor
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=False,
                    error_type=type(e).__name__
                )
                
                # Update circuit breaker
                self._update_circuit_breaker(type(e).__name__, False)
                
                # Try again with backoff
                attempt += 1
                last_error = e
                
                # If we have a fallback and have tried at least half the max attempts,
                # switch to the fallback
                if fallback_func and attempt > max_attempts // 2:
                    logger.warning(f"Switching to fallback after {attempt} failed attempts")
                    return fallback_func(*args, **kwargs)
                
            except Exception as other_e:
                # For other errors, record failure but don't retry
                self._update_circuit_breaker(type(other_e).__name__, False)
                raise
        
        # If we exit the loop without success and have a fallback, use it
        if not success and fallback_func:
            logger.warning(f"Using fallback after exhausting {max_attempts} retry attempts")
            return fallback_func(*args, **kwargs)
            
        # Otherwise, re-raise the last error
        if not success:
            raise LLMServiceUnavailableError(f"Service unavailable error persisted after {max_attempts} retry attempts: {str(last_error)}")
    
    def handle_error(
        self,
        service_name: str,
        error: LLMAPIError,
        retry_func: Callable,
        *args,
        fallback_func: Optional[Callable] = None,
        operation_type: Optional[str] = None,
        max_attempts: Optional[int] = None,
        priority: Optional[RequestPriority] = None,
        **kwargs
    ) -> T:
        """
        Generic error handler that routes to the appropriate specialized handler.
        
        Args:
            service_name: Name of the service that experienced the error
            error: The error that occurred
            retry_func: Function to retry
            *args: Arguments to pass to the retry function
            fallback_func: Alternative function to call if service remains unavailable
            operation_type: Type of operation for timeout configuration
            max_attempts: Maximum number of retry attempts
            priority: Priority for the queued request
            **kwargs: Keyword arguments to pass to the retry function
            
        Returns:
            Result from the retry_func or fallback_func if successful
            
        Raises:
            The original error if recovery fails
        """
        # Route to the appropriate specialized handler based on error type
        if isinstance(error, LLMRateLimitError):
            return self.handle_rate_limit_error(
                service_name=service_name,
                error=error,
                retry_func=retry_func,
                *args,
                max_attempts=max_attempts,
                priority=priority,
                **kwargs
            )
            
        elif isinstance(error, (LLMNetworkError, LLMConnectionError, LLMTimeoutError)):
            return self.handle_network_error(
                service_name=service_name,
                error=error,
                retry_func=retry_func,
                *args,
                operation_type=operation_type,
                max_attempts=max_attempts,
                **kwargs
            )
            
        elif isinstance(error, (LLMServiceUnavailableError, LLMServerError)):
            return self.handle_service_unavailable_error(
                service_name=service_name,
                error=error,
                retry_func=retry_func,
                *args,
                fallback_func=fallback_func,
                max_attempts=max_attempts,
                **kwargs
            )
            
        # For other error types, just retry with backoff
        max_attempts = max_attempts or self.default_retry_attempts
        attempt = 1
        
        # Record error in service monitor
        self.service_monitor.record_request_result(
            service_name=service_name,
            success=False,
            error_type=type(error).__name__
        )
        
        logger.warning(f"API error for {service_name}: {str(error)}, will retry {max_attempts} times")
        
        success = False
        last_error = error
        
        while attempt <= max_attempts and not success:
            delay = self._calculate_retry_delay(attempt)
            
            logger.info(f"API error retry {attempt}/{max_attempts} after {delay:.2f} seconds")
            
            time.sleep(delay)
            
            try:
                result = retry_func(*args, **kwargs)
                
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=True
                )
                
                success = True
                return result
                
            except LLMAPIError as e:
                self.service_monitor.record_request_result(
                    service_name=service_name,
                    success=False,
                    error_type=type(e).__name__
                )
                
                attempt += 1
                last_error = e
                
            except Exception as other_e:
                raise
        
        # If we exit the loop without success and have a fallback, use it
        if not success and fallback_func:
            logger.warning(f"Using fallback after exhausting {max_attempts} retry attempts")
            return fallback_func(*args, **kwargs)
            
        # Otherwise, re-raise the last error
        if not success:
            raise last_error
    
    def shutdown(self) -> None:
        """Shutdown all components."""
        logger.info("Shutting down ErrorRecoveryStrategies")
        
        # Shutdown components in reverse order of dependency
        if self.request_queue:
            self.request_queue.shutdown()
            
        if self.service_monitor:
            self.service_monitor.shutdown()
            
        if self.connection_manager:
            self.connection_manager.close()
            
        logger.info("ErrorRecoveryStrategies shutdown complete") 