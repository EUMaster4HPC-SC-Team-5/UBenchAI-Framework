#!/usr/bin/env python3
"""
Workload Generator v2 - Multi-service benchmark client with multinode support

Supports:
- Ollama: LLM inference server
- Qdrant: Vector database
- vLLM: OpenAI-compatible LLM inference server
- Multinode execution via SLURM
"""

import time
import json
import random
import statistics
import os
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
    node_id: Optional[int] = None  # NEW: Node identifier
    hostname: Optional[str] = None  # NEW: Hostname

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
            "node_id": self.node_id,
            "hostname": self.hostname,
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
    def __init__(
        self,
        endpoint: str,
        collection_name: str = "benchmark_collection",
        vector_size: int = 1536,
        timeout: int = 30,
    ):
        super().__init__(endpoint, timeout)
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._collection_created = False
        
        self.cached_vectors = [
            np.random.randn(self.vector_size).tolist() for _ in range(1000) 
        ]

    def test_connection(self) -> Tuple[bool, str]:
        try:
            url = f"{self.endpoint}/collections"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self._create_collection()
                return True, "Connection OK"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    def _create_collection(self) -> bool:
        if self._collection_created: return True
        try:
            if requests.get(f"{self.endpoint}/collections/{self.collection_name}").status_code == 200:
                self._collection_created = True
                return True
            
            payload = {
                "vectors": {"size": self.vector_size, "distance": "Cosine"},
                "optimizers_config": {"default_segment_number": 2} 
            }
            resp = requests.put(f"{self.endpoint}/collections/{self.collection_name}", json=payload)
            if resp.status_code in [200, 201]:
                self._collection_created = True
                return True
        except Exception:
            pass
        return False

    def send_request(self, operation: str = "insert", **kwargs) -> Tuple[bool, float, Optional[str]]:
        start_time = time.time()
        try:
            if operation == "insert":
                return self._insert_vectors(start_time, **kwargs)
            else:
                return self._search_vectors(start_time, **kwargs)
        except Exception as e:
            return False, time.time() - start_time, str(e)

    def _insert_vectors(self, start_time: float, batch_size: int = 100, **kwargs):
        real_batch_size = 100
        url = f"{self.endpoint}/collections/{self.collection_name}/points"
        
        batch_vectors = self.cached_vectors[:real_batch_size]
        points = []
        base_id = random.randint(1, 1000000000)
        
        for i, vec in enumerate(batch_vectors):
            points.append({
                "id": base_id + i, 
                "vector": vec
            })

        response = requests.put(f"{url}?wait=false", json={"points": points}, timeout=self.timeout)
        latency = time.time() - start_time
        return response.status_code in [200, 201], latency, None

    def _search_vectors(self, start_time: float, top_k: int = 10, **kwargs):
        url = f"{self.endpoint}/collections/{self.collection_name}/points/search"
        query_vector = random.choice(self.cached_vectors)
        
        payload = {"vector": query_vector, "limit": top_k}
        response = requests.post(url, json=payload, timeout=self.timeout)
        latency = time.time() - start_time
        return response.status_code == 200, latency, None


# ============================================================================
# vLLM Client
# ============================================================================


class VLLMClient(ServiceClient):
    """Client for vLLM OpenAI-compatible inference server"""

    def __init__(
        self, endpoint: str, model_name: str = "facebook/opt-125m", timeout: int = 30
    ):
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
    Multi-service workload generator for benchmarking with multinode support
    """

    def __init__(
        self,
        target_endpoint: str,
        service_type: str = "ollama",
        timeout: int = 30,
        node_id: Optional[int] = None,
        **service_kwargs,
    ):
        """
        Initialize workload generator

        Args:
            target_endpoint: Base URL of the service
            service_type: Type of service (ollama, qdrant, vllm)
            timeout: Request timeout in seconds
            node_id: Node identifier (for multinode execution)
            **service_kwargs: Service-specific configuration
        """
        self.target_endpoint = target_endpoint
        self.service_type = service_type.lower()
        self.timeout = timeout
        
        # NEW: Get node information from SLURM environment or parameter
        self.node_id = node_id if node_id is not None else int(os.getenv("SLURM_PROCID", "0"))
        self.hostname = os.getenv("HOSTNAME", "unknown")
        
        logger.info(f"WorkloadGenerator: node_id={self.node_id}, hostname={self.hostname}")

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
            f"[Node {self.node_id}] Starting closed-loop workload: "
            f"{concurrent_users} users, {duration_seconds}s, service={self.service_type}"
        )

        result = WorkloadResult()
        result.start_time = datetime.now()
        result.node_id = self.node_id
        result.hostname = self.hostname

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

        logger.info(
            f"[Node {self.node_id}] Closed-loop workload completed: "
            f"{result.total_requests} requests"
        )
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
            f"[Node {self.node_id}] Starting open-loop workload: "
            f"{requests_per_second} RPS, {duration_seconds}s, service={self.service_type}"
        )

        result = WorkloadResult()
        result.start_time = datetime.now()
        result.node_id = self.node_id
        result.hostname = self.hostname

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

        logger.info(
            f"[Node {self.node_id}] Open-loop workload completed: "
            f"{result.total_requests} requests"
        )
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
        description="Multi-service benchmark workload generator with multinode support"
    )
    parser.add_argument("--endpoint", required=True, help="Target endpoint URL")
    parser.add_argument(
        "--service-type",
        choices=["ollama", "qdrant", "vllm"],
        required=True,
        help="Service type",
    )
    parser.add_argument(
        "--model", default="tinyllama", help="Model name (for LLM services)"
    )
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
    parser.add_argument(
        "--node-id",
        type=int,
        help="Node ID (automatically set from SLURM_PROCID if not provided)",
    )

    args = parser.parse_args()

    # ========================================================================
    # SEED RANDOMICO PER OGNI NODO
    # ========================================================================
    # Determina il Node ID (da argomento o variabile d'ambiente)
    current_node_id = (
        args.node_id if args.node_id is not None 
        else int(os.getenv("SLURM_PROCID", "0"))
    )
    
    # IMPORTANTE: Varia il seed in base al nodo!
    # Altrimenti tutti i nodi generano gli stessi numeri casuali.
    seed_value = int(time.time()) + current_node_id
    logger.info(
        f"[Node {current_node_id}] Initializing random seed: {seed_value}"
    )
    random.seed(seed_value)
    np.random.seed(seed_value)
    # ========================================================================

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
        node_id=args.node_id,
        **service_kwargs,
    )

    # Test connection
    print(f"[Node {generator.node_id}] Testing connection to target endpoint...")
    success, message = generator.test_connection()
    print(f"[Node {generator.node_id}] {'✓' if success else '✗'} {message}")

    if not success:
        print(f"\n[Node {generator.node_id}] Error: Cannot connect to target endpoint")
        return 1

    print(f"\n[Node {generator.node_id}] " + "=" * 60)
    print(f"[Node {generator.node_id}] STARTING BENCHMARK")
    print(f"[Node {generator.node_id}] " + "=" * 60)

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
            print(
                f"[Node {generator.node_id}] Error: --requests-per-second required for open-loop pattern"
            )
            return 1

        result = generator.run_open_loop(
            duration_seconds=args.duration,
            requests_per_second=args.requests_per_second,
            **request_kwargs,
        )

    # Get metrics
    metrics = result.get_metrics()

    # Print results
    print(f"\n[Node {generator.node_id}] " + "=" * 60)
    print(f"[Node {generator.node_id}] BENCHMARK RESULTS")
    print(f"[Node {generator.node_id}] " + "=" * 60)
    print(f"[Node {generator.node_id}] Node ID:             {metrics['node_id']}")
    print(f"[Node {generator.node_id}] Hostname:            {metrics['hostname']}")
    print(f"[Node {generator.node_id}] Service Type:        {args.service_type}")
    print(f"[Node {generator.node_id}] Total Requests:      {metrics['total_requests']}")
    print(f"[Node {generator.node_id}] Successful:          {metrics['successful_requests']}")
    print(f"[Node {generator.node_id}] Failed:              {metrics['failed_requests']}")
    print(f"[Node {generator.node_id}] Success Rate:        {metrics['success_rate']:.2%}")
    print(f"[Node {generator.node_id}] Duration:            {metrics['duration_seconds']:.2f}s")
    print(f"[Node {generator.node_id}] Throughput:          {metrics['throughput_rps']:.2f} req/s")

    if "latency_mean" in metrics:
        print(f"\n[Node {generator.node_id}] Latency Statistics (seconds):")
        print(f"[Node {generator.node_id}]   Min:     {metrics['latency_min']:.3f}")
        print(f"[Node {generator.node_id}]   Mean:    {metrics['latency_mean']:.3f}")
        print(f"[Node {generator.node_id}]   Median:  {metrics['latency_median']:.3f}")
        print(f"[Node {generator.node_id}]   P95:     {metrics['latency_p95']:.3f}")
        print(f"[Node {generator.node_id}]   P99:     {metrics['latency_p99']:.3f}")
        print(f"[Node {generator.node_id}]   Max:     {metrics['latency_max']:.3f}")

    print(f"[Node {generator.node_id}] " + "=" * 60)

    # Save to file if requested
    if args.output:
        output_data = {
            "config": vars(args),
            "metrics": metrics,
            "errors": result.errors[:10],  # First 10 errors
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\n[Node {generator.node_id}] Results saved to: {args.output}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())