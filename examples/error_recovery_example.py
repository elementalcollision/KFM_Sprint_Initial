"""
Example usage of error recovery strategies with LLM API calls.

This example demonstrates how to use the specialized recovery strategies
for handling rate limits, network errors, and service unavailability.
"""

import os
import time
import logging
import httpx
from typing import List, Dict, Any, Optional

from src.error_recovery import (
    TokenBucketRateLimiter,
    RequestQueueManager,
    NetworkConnectionManager,
    ServiceHealthMonitor,
    ErrorRecoveryStrategies,
    RequestPriority
)

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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LLMClient:
    """Simple LLM API client with error handling."""
    
    def __init__(
        self, 
        api_key: str,
        service_name: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        recovery_strategies: Optional[ErrorRecoveryStrategies] = None
    ):
        """
        Initialize the LLM client.
        
        Args:
            api_key: API key for the LLM service
            service_name: Name of the LLM service
            base_url: Base URL for API requests
            timeout: Default timeout for requests
            recovery_strategies: Error recovery strategies to use
        """
        self.api_key = api_key
        self.service_name = service_name
        self.base_url = base_url
        self.timeout = timeout
        
        # Create or use provided error recovery strategies
        if recovery_strategies:
            self.recovery = recovery_strategies
        else:
            # Create components
            rate_limiter = TokenBucketRateLimiter(
                rate=20.0,  # 20 tokens per second
                max_tokens=60,  # Maximum token bucket size
                tokens_per_request=1  # Each request consumes 1 token
            )
            
            connection_manager = NetworkConnectionManager(
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                http2=True
            )
            
            service_monitor = ServiceHealthMonitor(
                health_check_interval=300.0,  # 5 minutes
                health_check_urls={
                    service_name: f"{base_url}/models"  # Simple health check endpoint
                },
                connection_manager=connection_manager
            )
            
            request_queue = RequestQueueManager(
                rate_limiter=rate_limiter,
                max_queue_size=100,
                worker_threads=2
            )
            
            self.recovery = ErrorRecoveryStrategies(
                rate_limiter=rate_limiter,
                request_queue=request_queue,
                connection_manager=connection_manager,
                service_monitor=service_monitor
            )
        
        # Register the service
        self.recovery.service_monitor.register_service(
            self.service_name, 
            health_check_url=f"{self.base_url}/models"
        )
        
        # Create HTTP client
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            limits=self.recovery.connection_manager.limits,
            http2=self.recovery.connection_manager.http2
        )
        
        logger.info(f"LLM client initialized for {service_name}")
    
    def _handle_api_error(self, error: Exception, retry_func, *args, **kwargs) -> Any:
        """
        Handle API errors by dispatching to appropriate recovery strategy.
        
        Args:
            error: The error that occurred
            retry_func: Function to retry
            *args: Arguments to pass to the retry function
            **kwargs: Keyword arguments to pass to the retry function
            
        Returns:
            Result from successful retry
            
        Raises:
            LLMAPIError: If recovery fails
        """
        try:
            if isinstance(error, LLMRateLimitError):
                logger.info(f"Handling rate limit error for {self.service_name}")
                return self.recovery.handle_rate_limit_error(
                    service_name=self.service_name,
                    error=error,
                    retry_func=retry_func,
                    *args,
                    **kwargs
                )
                
            elif isinstance(error, (LLMNetworkError, LLMConnectionError, LLMTimeoutError)):
                logger.info(f"Handling network error for {self.service_name}")
                return self.recovery.handle_network_error(
                    service_name=self.service_name,
                    error=error,
                    retry_func=retry_func,
                    *args,
                    **kwargs
                )
                
            elif isinstance(error, (LLMServiceUnavailableError, LLMServerError)):
                logger.info(f"Handling service unavailable error for {self.service_name}")
                # If we have a fallback model, use it as a fallback function
                fallback_func = self.generate_fallback if hasattr(self, 'generate_fallback') else None
                
                return self.recovery.handle_service_unavailable_error(
                    service_name=self.service_name,
                    error=error,
                    retry_func=retry_func,
                    fallback_func=fallback_func,
                    *args,
                    **kwargs
                )
                
            else:
                # For other errors, use general recovery approach
                logger.info(f"Handling general API error for {self.service_name}")
                return self.recovery.handle_error(
                    service_name=self.service_name,
                    error=error if isinstance(error, LLMAPIError) else LLMAPIError(str(error)),
                    retry_func=retry_func,
                    *args,
                    **kwargs
                )
                
        except Exception as recovery_error:
            logger.error(f"Error recovery failed: {str(recovery_error)}")
            raise
    
    def _make_api_request(self, method: str, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make an API request with error handling.
        
        Args:
            method: HTTP method to use
            endpoint: API endpoint to call
            json_data: JSON data to send
            
        Returns:
            Response JSON
            
        Raises:
            LLMAPIError: If the request fails
        """
        # Get client from connection manager with appropriate timeouts
        operation_type = NetworkConnectionManager.OperationType.GENERATION.value
        if endpoint.endswith("/embeddings"):
            operation_type = NetworkConnectionManager.OperationType.EMBEDDING.value
        
        # Function to make the actual request
        def make_request():
            try:
                start_time = time.time()
                
                # Make request
                response = self.client.request(
                    method,
                    endpoint,
                    json=json_data,
                    timeout=self.recovery.connection_manager.get_timeout(operation_type)
                )
                
                # Record response time
                response_time = time.time() - start_time
                
                # Check for errors
                response.raise_for_status()
                
                # Record successful request
                self.recovery.service_monitor.record_request_result(
                    service_name=self.service_name,
                    success=True,
                    response_time=response_time
                )
                
                return response.json()
                
            except httpx.HTTPStatusError as e:
                # Map HTTP errors to appropriate LLM API errors
                status_code = e.response.status_code
                error_message = str(e)
                
                try:
                    error_data = e.response.json()
                    if "error" in error_data and "message" in error_data["error"]:
                        error_message = error_data["error"]["message"]
                except:
                    pass
                
                if status_code == 401:
                    raise LLMAuthenticationError(f"Authentication error: {error_message}")
                elif status_code == 429:
                    # Get retry-after header if available
                    retry_after = e.response.headers.get("retry-after")
                    error = LLMRateLimitError(f"Rate limit exceeded: {error_message}")
                    error.retry_after = retry_after
                    raise error
                elif status_code == 400:
                    raise LLMInvalidRequestError(f"Invalid request: {error_message}")
                elif status_code >= 500:
                    if status_code == 503:
                        raise LLMServiceUnavailableError(f"Service unavailable: {error_message}")
                    else:
                        raise LLMServerError(f"Server error: {error_message}")
                else:
                    raise LLMAPIError(f"API error: {error_message}")
                    
            except httpx.RequestError as e:
                # Map request errors to appropriate LLM network errors
                if isinstance(e, httpx.TimeoutException):
                    raise LLMTimeoutError(f"Request timed out: {str(e)}")
                elif isinstance(e, httpx.ConnectError):
                    raise LLMConnectionError(f"Connection error: {str(e)}")
                else:
                    raise LLMNetworkError(f"Network error: {str(e)}")
                    
            except Exception as e:
                # Catch-all for other errors
                raise LLMAPIError(f"Unexpected error: {str(e)}")
        
        try:
            # Attempt to make the request
            return make_request()
        except Exception as e:
            # Handle the error with recovery strategies
            return self._handle_api_error(e, make_request)
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with error recovery.
        
        Args:
            messages: List of message objects
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Response from the LLM API
        """
        logger.info(f"Generating with model {model}")
        
        endpoint = "/chat/completions"
        
        json_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        return self._make_api_request("POST", endpoint, json_data)
    
    def create_embedding(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create embeddings with error recovery.
        
        Args:
            texts: List of texts to embed
            model: Model to use
            **kwargs: Additional parameters
            
        Returns:
            Response from the LLM API
        """
        logger.info(f"Creating embeddings with model {model}")
        
        endpoint = "/embeddings"
        
        json_data = {
            "model": model,
            "input": texts,
            **kwargs
        }
        
        return self._make_api_request("POST", endpoint, json_data)
    
    def close(self):
        """Close the client and shutdown recovery strategies."""
        logger.info("Closing LLM client")
        self.client.close()
        self.recovery.shutdown()

def run_example():
    """Run a simple example using the LLM client with error recovery."""
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("Please set OPENAI_API_KEY environment variable")
        return
    
    # Create client
    client = LLMClient(api_key=api_key, service_name="openai")
    
    try:
        # Generate text
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me about error recovery strategies in distributed systems."}
        ]
        
        response = client.generate(messages=messages, model="gpt-4")
        logger.info("Generation successful")
        
        # Print response
        print("\nResponse from LLM:")
        if "choices" in response and len(response["choices"]) > 0:
            print(response["choices"][0]["message"]["content"])
        else:
            print(response)
            
        # Create embeddings
        texts = ["Error recovery strategies", "Distributed systems", "Fault tolerance"]
        embedding_response = client.create_embedding(texts=texts)
        logger.info("Embedding creation successful")
        
        # Print embedding dimensions
        if "data" in embedding_response and len(embedding_response["data"]) > 0:
            print(f"\nEmbedding dimensions: {len(embedding_response['data'][0]['embedding'])}")
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")
    finally:
        # Clean up
        client.close()

if __name__ == "__main__":
    run_example() 