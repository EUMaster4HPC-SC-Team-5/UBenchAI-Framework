#!/usr/bin/env python3
"""
Workload Generator - Generates benchmark requests against AI services
"""

import time
import json
import statistics
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import requests
from loguru import logger


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
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        metrics = {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "duration_seconds": duration,
            "throughput_rps": self.successful_requests / duration if duration > 0 else 0,
        }
        
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            metrics.update({
                "latency_min": min(self.latencies),
                "latency_max": max(self.latencies),
                "latency_mean": statistics.mean(self.latencies),
                "latency_median": statistics.median(self.latencies),
                "latency_p50": sorted_latencies[int(len(sorted_latencies) * 0.50)],
                "latency_p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
                "latency_p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
            })
        
        return metrics


class WorkloadGenerator:
    """
    Generates benchmark workloads against AI services
    """
    
    def __init__(
        self,
        target_endpoint: str,
        model_name: str = "tinyllama",
        timeout: int = 30
    ):
        """
        Initialize workload generator
        
        Args:
            target_endpoint: Base URL of the service (e.g., http://mel2067:11434)
            model_name: Name of the model to use
            timeout: Request timeout in seconds
        """
        self.target_endpoint = target_endpoint.rstrip('/')
        self.model_name = model_name
        self.timeout = timeout
        
        logger.info(f"WorkloadGenerator initialized: {self.target_endpoint}")
    
    def generate_prompt(self, prompt_length: int = 50) -> str:
        """Generate a synthetic prompt"""
        prompts = [
            "What is artificial intelligence?",
            "Explain machine learning in simple terms.",
            "What are the benefits of cloud computing?",
            "Describe the concept of neural networks.",
            "What is the difference between AI and ML?",
        ]
        
        # Cycle through prompts
        base_prompt = prompts[prompt_length % len(prompts)]
        
        # Pad to requested length if needed
        if len(base_prompt) < prompt_length:
            base_prompt += " " * (prompt_length - len(base_prompt))
        
        return base_prompt[:prompt_length]
    
    def send_request(self, prompt: str) -> tuple[bool, float, Optional[str]]:
        """
        Send a single inference request to Ollama
        
        Returns:
            Tuple of (success, latency_seconds, error_message)
        """
        url = f"{self.target_endpoint}/api/generate"
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,  # Non-streaming for easier benchmarking
            "options": {
                "temperature": 0.7,
                "num_predict": 100  # Limit response length for faster benchmarks
            }
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            latency = time.time() - start_time
            
            if response.status_code == 200:
                # Verify we got a valid response
                data = response.json()
                if "response" in data:
                    return True, latency, None
                else:
                    return False, latency, "Invalid response format"
            else:
                return False, latency, f"HTTP {response.status_code}: {response.text[:100]}"
        
        except requests.exceptions.Timeout:
            latency = time.time() - start_time
            return False, latency, "Timeout"
        
        except requests.exceptions.ConnectionError as e:
            latency = time.time() - start_time
            return False, latency, f"Connection error: {str(e)[:100]}"
        
        except requests.exceptions.RequestException as e:
            latency = time.time() - start_time
            return False, latency, f"Request error: {str(e)[:100]}"
        
        except Exception as e:
            latency = time.time() - start_time
            return False, latency, f"Unexpected error: {str(e)[:100]}"
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to the target endpoint
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Try to get list of models (simpler endpoint)
            url = f"{self.target_endpoint}/api/tags"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                
                if self.model_name in models:
                    return True, f"Connection OK. Model '{self.model_name}' is available."
                else:
                    return False, f"Model '{self.model_name}' not found. Available: {models}"
            else:
                return False, f"Server returned HTTP {response.status_code}"
        
        except Exception as e:
            return False, f"Connection failed: {e}"
    
    def run_closed_loop(
        self,
        duration_seconds: int,
        concurrent_users: int,
        think_time_ms: int = 0,
        prompt_length: int = 50
    ) -> WorkloadResult:
        """
        Run closed-loop workload pattern
        
        In closed-loop, each user waits for response before sending next request
        
        Args:
            duration_seconds: How long to run the test
            concurrent_users: Number of concurrent users
            think_time_ms: Think time between requests (milliseconds)
            prompt_length: Length of generated prompts
        """
        logger.info(f"Starting closed-loop workload: {concurrent_users} users, {duration_seconds}s")
        
        result = WorkloadResult()
        result.start_time = datetime.now()
        
        end_time = time.time() + duration_seconds
        
        def user_loop():
            """Simulates a single user's request loop"""
            while time.time() < end_time:
                prompt = self.generate_prompt(prompt_length)
                success, latency, error = self.send_request(prompt)
                
                if success:
                    result.add_success(latency)
                else:
                    result.add_failure(error or "Unknown error")
                
                # Think time (simulates user reading response)
                if think_time_ms > 0:
                    time.sleep(think_time_ms / 1000.0)
        
        # Execute concurrent users
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_loop) for _ in range(concurrent_users)]
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"User loop error: {e}")
        
        result.end_time = datetime.now()
        
        logger.info(f"Closed-loop workload completed: {result.total_requests} requests")
        return result
    
    def run_open_loop(
        self,
        duration_seconds: int,
        requests_per_second: int,
        prompt_length: int = 50
    ) -> WorkloadResult:
        """
        Run open-loop workload pattern
        
        In open-loop, requests are sent at a fixed rate regardless of responses
        
        Args:
            duration_seconds: How long to run the test
            requests_per_second: Target request rate
            prompt_length: Length of generated prompts
        """
        logger.info(f"Starting open-loop workload: {requests_per_second} RPS, {duration_seconds}s")
        
        result = WorkloadResult()
        result.start_time = datetime.now()
        
        interval = 1.0 / requests_per_second
        end_time = time.time() + duration_seconds
        
        def send_async_request():
            """Send a single async request"""
            prompt = self.generate_prompt(prompt_length)
            success, latency, error = self.send_request(prompt)
            
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


def main():
    """Main entry point for CLI execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark workload generator")
    parser.add_argument("--endpoint", required=True, help="Target endpoint URL")
    parser.add_argument("--model", default="tinyllama", help="Model name")
    parser.add_argument("--pattern", choices=["closed-loop", "open-loop"], required=True)
    parser.add_argument("--duration", type=int, required=True, help="Duration in seconds")
    parser.add_argument("--concurrent-users", type=int, default=1)
    parser.add_argument("--requests-per-second", type=int)
    parser.add_argument("--think-time", type=int, default=0, help="Think time in ms")
    parser.add_argument("--prompt-length", type=int, default=50)
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = WorkloadGenerator(
        target_endpoint=args.endpoint,
        model_name=args.model
    )
    
    # Test connection first
    print("Testing connection to target endpoint...")
    success, message = generator.test_connection()
    print(f"{'✓' if success else '✗'} {message}")
    
    if not success:
        print("\nError: Cannot connect to target endpoint")
        return 1
    
    print("\n" + "=" * 60)
    print("STARTING BENCHMARK")
    print("=" * 60)
    
    # Run workload
    if args.pattern == "closed-loop":
        result = generator.run_closed_loop(
            duration_seconds=args.duration,
            concurrent_users=args.concurrent_users,
            think_time_ms=args.think_time,
            prompt_length=args.prompt_length
        )
    else:  # open-loop
        if not args.requests_per_second:
            print("Error: --requests-per-second required for open-loop pattern")
            return 1
        
        result = generator.run_open_loop(
            duration_seconds=args.duration,
            requests_per_second=args.requests_per_second,
            prompt_length=args.prompt_length
        )
    
    # Get metrics
    metrics = result.get_metrics()
    
    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total Requests:      {metrics['total_requests']}")
    print(f"Successful:          {metrics['successful_requests']}")
    print(f"Failed:              {metrics['failed_requests']}")
    print(f"Success Rate:        {metrics['success_rate']:.2%}")
    print(f"Duration:            {metrics['duration_seconds']:.2f}s")
    print(f"Throughput:          {metrics['throughput_rps']:.2f} req/s")
    
    if 'latency_mean' in metrics:
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
            "errors": result.errors[:10]  # First 10 errors
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to: {args.output}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())