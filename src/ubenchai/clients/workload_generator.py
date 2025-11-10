#!/usr/bin/env python3
"""
Workload Generator v2 - Multi-service benchmark client

Supports:
- Ollama: LLM inference server
- Qdrant: Vector database  
- vLLM: OpenAI-compatible LLM inference server
"""

import time
import json
import random
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import requests
import numpy as np
from loguru import logger


# ============================================================================
# Results and Metrics
# ============================================================================


@dataclass
class WorkloadResult:
    """Results from a benchmark run"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    custom_metrics: Dict = field(default_factory=dict)

    def add_success(self, latency: float):
        """Record successful request"""
        self.successful_requests += 1
        self.total_requests += 1
        self.latencies.append(latency)

    def add_failure(self, error: str):
        """Record failed request"""
        self.failed_requests += 1
        self.total_requests += 1
        self.errors.append(error)

    def get_metrics(self) -> Dict:
        """Calculate and return metrics"""
        duration = (
            (self.end_time - self.start_time).total_seconds()
            if self.end_time and self.start_time
            else 0
        )

        metrics = {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0
            ),
            "duration_seconds": duration,
            "throughput_rps": (
                self.successful_requests / duration if duration > 0 else 0
            ),
        }

        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            metrics.update(
                {
                    "latency_min": min(self.latencies),
                    "latency_max": max(self.latencies),
                    "latency_mean": statistics.mean(self.latencies),
                    "latency_median": statistics.median(self.latencies),
                    "latency_p50": sorted_latencies[int(len(sorted_latencies) * 0.50)],
                    "latency_p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
                    "latency_p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
                }
            )

        # Add custom metrics
        metrics.update(self.custom_metrics)

        return metrics


# ============================================================================
# Service Clients (Abstract Base)
# ============================================================================


class ServiceClient(ABC):
    """Abstract base class for service-specific clients"""

    def __init__(self, endpoint: str, timeout: int = 30):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        logger.info(f"{self.__class__.__name__} initialized: {self.endpoint}")

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to service"""
        pass

    @abstractmethod
    def send_request(self, **kwargs) -> Tuple[bool, float, Optional[str]]:
        """Send a single request"""
        pass


# ============================================================================
# Ollama Client
# ============================================================================


class OllamaClient(ServiceClient):
    """Client for Ollama LLM inference server"""

    def __init__(self, endpoint: str, model_name: str = "tinyllama", timeout: int = 30):
        super().__init__(endpoint, timeout)
        self.model_name = model_name

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Ollama"""
        try:
            url = f"{self.endpoint}/api/tags"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]

                if self.model_name in models:
                    return True, f"Connection OK. Model '{self.model_name}' available."
                else:
                    return (
                        False,
                        f"Model '{self.model_name}' not found. Available: {models}",
                    )
            else:
                return False, f"Server returned HTTP {response.status_code}"

        except Exception as e:
            return False, f"Connection failed: {e}"

    def send_request(self, prompt: str, **kwargs) -> Tuple[bool, float, Optional[str]]:
        """Send inference request to Ollama"""
        url = f"{self.endpoint}/api/generate"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 100),
            },
        }

        start_time = time.time()

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )

            latency = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    return True, latency, None
                else:
                    return False, latency, "Invalid response format"
            else:
                return (
                    False,
                    latency,
                    f"HTTP {response.status_code}: {response.text[:100]}",
                )

        except Exception as e:
            latency = time.time() - start_time
            return False, latency, f"Request error: {str(e)[:100]}"

    def generate_prompt(self, length: int = 50) -> str:
        """Generate synthetic prompt"""
        prompts = [
            "What is artificial intelligence?",
            "Explain machine learning in simple terms.",
            "What are the benefits of cloud computing?",
            "Describe the concept of neural networks.",
            "What is the difference between AI and ML?",
        ]
        base_prompt = prompts[length % len(prompts)]
        if len(base_prompt) < length:
            base_prompt += " " * (length - len(base_prompt))
        return base_prompt[:length]


# ============================================================================
# Qdrant Client
# ============================================================================


class QdrantClient(ServiceClient):
    """Client for Qdrant vector database"""

    def __init__(
        self,
        endpoint: str,
        collection_name: str = "benchmark_collection",
        vector_size: int = 384,
        timeout: int = 30,
    ):
        super().__init__(endpoint, timeout)
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._collection_created = False

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Qdrant"""
        try:
            url = f"{self.endpoint}/collections"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                # Try to create collection for benchmarking
                self._create_collection()
                return True, "Connection OK. Collection created for benchmarking."
            else:
                return False, f"Server returned HTTP {response.status_code}"

        except Exception as e:
            return False, f"Connection failed: {e}"

    def _create_collection(self) -> bool:
        """Create benchmark collection if it doesn't exist"""
        if self._collection_created:
            return True

        try:
            # Check if collection exists
            url = f"{self.endpoint}/collections/{self.collection_name}"
            response = requests.get(url, timeout=5)

            if response.status_code == 404:
                # Create collection
                create_url = f"{self.endpoint}/collections/{self.collection_name}"
                payload = {
                    "vectors": {"size": self.vector_size, "distance": "Cosine"}
                }
                response = requests.put(create_url, json=payload, timeout=10)

                if response.status_code in [200, 201]:
                    logger.info(
                        f"Created collection: {self.collection_name} (size={self.vector_size})"
                    )
                    self._collection_created = True
                    return True

            elif response.status_code == 200:
                logger.info(f"Collection already exists: {self.collection_name}")
                self._collection_created = True
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def send_request(
        self, operation: str = "insert", **kwargs
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Send request to Qdrant

        Operations:
        - insert: Insert random vectors
        - search: Search for similar vectors
        - delete: Delete points
        """
        start_time = time.time()

        try:
            if operation == "insert":
                return self._insert_vectors(start_time, **kwargs)
            elif operation == "search":
                return self._search_vectors(start_time, **kwargs)
            elif operation == "delete":
                return self._delete_vectors(start_time, **kwargs)
            else:
                return False, 0, f"Unknown operation: {operation}"

        except Exception as e:
            latency = time.time() - start_time
            return False, latency, f"Request error: {str(e)[:100]}"

    def _insert_vectors(
        self, start_time: float, batch_size: int = 10, **kwargs
    ) -> Tuple[bool, float, Optional[str]]:
        """Insert random vectors"""
        url = f"{self.endpoint}/collections/{self.collection_name}/points"

        # Generate random vectors
        points = []
        for i in range(batch_size):
            point_id = random.randint(1, 1000000)
            vector = np.random.randn(self.vector_size).tolist()
            points.append(
                {"id": point_id, "vector": vector, "payload": {"index": i}}
            )

        payload = {"points": points}

        response = requests.put(url, json=payload, timeout=self.timeout)
        latency = time.time() - start_time

        if response.status_code in [200, 201]:
            return True, latency, None
        else:
            return False, latency, f"HTTP {response.status_code}"

    def _search_vectors(
        self, start_time: float, top_k: int = 10, **kwargs
    ) -> Tuple[bool, float, Optional[str]]:
        """Search for similar vectors"""
        url = f"{self.endpoint}/collections/{self.collection_name}/points/search"

        # Generate random query vector
        query_vector = np.random.randn(self.vector_size).tolist()

        payload = {"vector": query_vector, "limit": top_k}

        response = requests.post(url, json=payload, timeout=self.timeout)
        latency = time.time() - start_time

        if response.status_code == 200:
            return True, latency, None
        else:
            return False, latency, f"HTTP {response.status_code}"

    def _delete_vectors(
        self, start_time: float, **kwargs
    ) -> Tuple[bool, float, Optional[str]]:
        """Delete random points"""
        url = f"{self.endpoint}/collections/{self.collection_name}/points/delete"

        # Delete random points
        point_ids = [random.randint(1, 1000000) for _ in range(10)]
        payload = {"points": point_ids}

        response = requests.post(url, json=payload, timeout=self.timeout)
        latency = time.time() - start_time

        if response.status_code == 200:
            return True, latency, None
        else:
            return False, latency, f"HTTP {response.status_code}"


# ============================================================================
# vLLM Client
# ============================================================================


class VLLMClient(ServiceClient):
    """Client for vLLM OpenAI-compatible inference server"""

    def __init__(self, endpoint: str, model_name: str = "facebook/opt-125m", timeout: int = 30):
        super().__init__(endpoint, timeout)
        self.model_name = model_name

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to vLLM"""
        try:
            # Try to list models
            url = f"{self.endpoint}/v1/models"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                models = [m.get("id") for m in data.get("data", [])]

                if self.model_name in models:
                    return True, f"Connection OK. Model '{self.model_name}' available."
                else:
                    return (
                        True,
                        f"Connected but model '{self.model_name}' not in list: {models}",
                    )
            else:
                return False, f"Server returned HTTP {response.status_code}"

        except Exception as e:
            return False, f"Connection failed: {e}"

    def send_request(self, prompt: str, **kwargs) -> Tuple[bool, float, Optional[str]]:
        """Send completion request to vLLM"""
        url = f"{self.endpoint}/v1/completions"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 20),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
        }

        start_time = time.time()

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )

            latency = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return True, latency, None
                else:
                    return False, latency, "Invalid response format"
            else:
                return (
                    False,
                    latency,
                    f"HTTP {response.status_code}: {response.text[:100]}",
                )

        except Exception as e:
            latency = time.time() - start_time
            return False, latency, f"Request error: {str(e)[:100]}"

    def generate_prompt(self, length: int = 50) -> str:
        """Generate synthetic prompt"""
        prompts = [
            "The future of AI is",
            "Machine learning will",
            "Deep learning allows us to",
            "Natural language processing can",
            "Computer vision helps",
        ]
        base_prompt = prompts[length % len(prompts)]
        if len(base_prompt) < length:
            base_prompt += " " * (length - len(base_prompt))
        return base_prompt[:length]


# ============================================================================
# Workload Generator (Main Class)
# ============================================================================


class WorkloadGenerator:
    """
    Multi-service workload generator for benchmarking
    """

    def __init__(
        self,
        target_endpoint: str,
        service_type: str = "ollama",
        timeout: int = 30,
        **service_kwargs,
    ):
        """
        Initialize workload generator

        Args:
            target_endpoint: Base URL of the service
            service_type: Type of service (ollama, qdrant, vllm)
            timeout: Request timeout in seconds
            **service_kwargs: Service-specific configuration
        """
        self.target_endpoint = target_endpoint
        self.service_type = service_type.lower()
        self.timeout = timeout

        # Initialize appropriate client
        if self.service_type == "ollama":
            self.client = OllamaClient(
                endpoint=target_endpoint,
                model_name=service_kwargs.get("model_name", "tinyllama"),
                timeout=timeout,
            )
        elif self.service_type == "qdrant":
            self.client = QdrantClient(
                endpoint=target_endpoint,
                collection_name=service_kwargs.get(
                    "collection_name", "benchmark_collection"
                ),
                vector_size=service_kwargs.get("vector_size", 384),
                timeout=timeout,
            )
        elif self.service_type == "vllm":
            self.client = VLLMClient(
                endpoint=target_endpoint,
                model_name=service_kwargs.get("model_name", "facebook/opt-125m"),
                timeout=timeout,
            )
        else:
            raise ValueError(
                f"Unsupported service type: {service_type}. Choose: ollama, qdrant, vllm"
            )

        logger.info(f"WorkloadGenerator initialized for {service_type}")

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to target service"""
        return self.client.test_connection()

    def run_closed_loop(
        self,
        duration_seconds: int,
        concurrent_users: int,
        think_time_ms: int = 0,
        **request_kwargs,
    ) -> WorkloadResult:
        """
        Run closed-loop workload pattern

        Args:
            duration_seconds: How long to run the test
            concurrent_users: Number of concurrent users
            think_time_ms: Think time between requests (milliseconds)
            **request_kwargs: Service-specific request parameters
        """
        logger.info(
            f"Starting closed-loop workload: {concurrent_users} users, {duration_seconds}s, service={self.service_type}"
        )

        result = WorkloadResult()
        result.start_time = datetime.now()

        end_time = time.time() + duration_seconds

        def user_loop():
            """Simulates a single user's request loop"""
            while time.time() < end_time:
                success, latency, error = self._send_service_request(**request_kwargs)

                if success:
                    result.add_success(latency)
                else:
                    result.add_failure(error or "Unknown error")

                # Think time
                if think_time_ms > 0:
                    time.sleep(think_time_ms / 1000.0)

        # Execute concurrent users
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_loop) for _ in range(concurrent_users)]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"User loop error: {e}")

        result.end_time = datetime.now()

        logger.info(f"Closed-loop workload completed: {result.total_requests} requests")
        return result

    def run_open_loop(
        self, duration_seconds: int, requests_per_second: int, **request_kwargs
    ) -> WorkloadResult:
        """
        Run open-loop workload pattern

        Args:
            duration_seconds: How long to run the test
            requests_per_second: Target request rate
            **request_kwargs: Service-specific request parameters
        """
        logger.info(
            f"Starting open-loop workload: {requests_per_second} RPS, {duration_seconds}s, service={self.service_type}"
        )

        result = WorkloadResult()
        result.start_time = datetime.now()

        interval = 1.0 / requests_per_second
        end_time = time.time() + duration_seconds

        def send_async_request():
            """Send a single async request"""
            success, latency, error = self._send_service_request(**request_kwargs)

            if success:
                result.add_success(latency)
            else:
                result.add_failure(error or "Unknown error")

        # Send requests at fixed rate
        with ThreadPoolExecutor(max_workers=requests_per_second * 2) as executor:
            while time.time() < end_time:
                executor.submit(send_async_request)
                time.sleep(interval)

        result.end_time = datetime.now()

        logger.info(f"Open-loop workload completed: {result.total_requests} requests")
        return result

    def _send_service_request(self, **kwargs) -> Tuple[bool, float, Optional[str]]:
        """Send request based on service type"""
        if self.service_type == "ollama":
            prompt = kwargs.get("prompt") or self.client.generate_prompt(
                kwargs.get("prompt_length", 50)
            )
            return self.client.send_request(prompt=prompt, **kwargs)

        elif self.service_type == "qdrant":
            operation = kwargs.pop("operation", "search")
            return self.client.send_request(operation=operation, **kwargs)

        elif self.service_type == "vllm":
            prompt = kwargs.get("prompt") or self.client.generate_prompt(
                kwargs.get("prompt_length", 50)
            )
            return self.client.send_request(prompt=prompt, **kwargs)

        return False, 0, "Invalid service type"


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    """Main entry point for CLI execution"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-service benchmark workload generator"
    )
    parser.add_argument("--endpoint", required=True, help="Target endpoint URL")
    parser.add_argument(
        "--service-type",
        choices=["ollama", "qdrant", "vllm"],
        required=True,
        help="Service type",
    )
    parser.add_argument("--model", default="tinyllama", help="Model name (for LLM services)")
    parser.add_argument(
        "--pattern", choices=["closed-loop", "open-loop"], required=True
    )
    parser.add_argument(
        "--duration", type=int, required=True, help="Duration in seconds"
    )
    parser.add_argument("--concurrent-users", type=int, default=1)
    parser.add_argument("--requests-per-second", type=int)
    parser.add_argument("--think-time", type=int, default=0, help="Think time in ms")
    parser.add_argument("--prompt-length", type=int, default=50)
    parser.add_argument(
        "--operation",
        choices=["insert", "search", "delete"],
        default="search",
        help="Qdrant operation type",
    )
    parser.add_argument("--output", help="Output file for results (JSON)")

    args = parser.parse_args()

    # Initialize generator
    service_kwargs = {}
    if args.service_type in ["ollama", "vllm"]:
        service_kwargs["model_name"] = args.model
    elif args.service_type == "qdrant":
        service_kwargs["collection_name"] = "benchmark_collection"
        service_kwargs["vector_size"] = 384

    generator = WorkloadGenerator(
        target_endpoint=args.endpoint,
        service_type=args.service_type,
        **service_kwargs,
    )

    # Test connection
    print("Testing connection to target endpoint...")
    success, message = generator.test_connection()
    print(f"{'✓' if success else '✗'} {message}")

    if not success:
        print("\nError: Cannot connect to target endpoint")
        return 1

    print("\n" + "=" * 60)
    print("STARTING BENCHMARK")
    print("=" * 60)

    # Prepare request kwargs
    request_kwargs = {"prompt_length": args.prompt_length}
    if args.service_type == "qdrant":
        request_kwargs["operation"] = args.operation

    # Run workload
    if args.pattern == "closed-loop":
        result = generator.run_closed_loop(
            duration_seconds=args.duration,
            concurrent_users=args.concurrent_users,
            think_time_ms=args.think_time,
            **request_kwargs,
        )
    else:  # open-loop
        if not args.requests_per_second:
            print("Error: --requests-per-second required for open-loop pattern")
            return 1

        result = generator.run_open_loop(
            duration_seconds=args.duration,
            requests_per_second=args.requests_per_second,
            **request_kwargs,
        )

    # Get metrics
    metrics = result.get_metrics()

    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Service Type:        {args.service_type}")
    print(f"Total Requests:      {metrics['total_requests']}")
    print(f"Successful:          {metrics['successful_requests']}")
    print(f"Failed:              {metrics['failed_requests']}")
    print(f"Success Rate:        {metrics['success_rate']:.2%}")
    print(f"Duration:            {metrics['duration_seconds']:.2f}s")
    print(f"Throughput:          {metrics['throughput_rps']:.2f} req/s")

    if "latency_mean" in metrics:
        print(f"\nLatency Statistics (seconds):")
        print(f"  Min:     {metrics['latency_min']:.3f}")
        print(f"  Mean:    {metrics['latency_mean']:.3f}")
        print(f"  Median:  {metrics['latency_median']:.3f}")
        print(f"  P95:     {metrics['latency_p95']:.3f}")
        print(f"  P99:     {metrics['latency_p99']:.3f}")
        print(f"  Max:     {metrics['latency_max']:.3f}")

    print("=" * 60)

    # Save to file if requested
    if args.output:
        output_data = {
            "config": vars(args),
            "metrics": metrics,
            "errors": result.errors[:10],  # First 10 errors
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\nResults saved to: {args.output}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())