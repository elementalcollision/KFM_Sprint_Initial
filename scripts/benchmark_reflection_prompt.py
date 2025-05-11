#!/usr/bin/env python3
"""
Benchmark script for measuring reflection prompt performance:
- Token usage for different state sizes and complexity levels
- Prompt generation timing
- Response processing overhead (excluding actual API latency)

Run this script to generate performance metrics and ensure the prompt
remains within efficient limits.
"""

import sys
import os
import time
import json
import statistics
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import get_reflection_prompt, call_llm_for_reflection
from src.logger import setup_logger

# Setup logger
benchmark_logger = setup_logger('benchmark')

def count_tokens(text):
    """Estimate token count using a simple heuristic.
    
    This is a rough approximation. For production, use the
    actual tokenizer from your LLM provider.
    """
    # Simple approximation: ~4 chars per token for English text
    return len(text) // 4

def generate_test_state(complexity='simple'):
    """Generate a test state with the specified complexity.
    
    Args:
        complexity: 'simple', 'medium', or 'complex'
        
    Returns:
        A test state dictionary
    """
    if complexity == 'simple':
        return {
            'kfm_action': {
                'action': 'keep',
                'component': 'simple_component',
                'reason': 'Good enough performance'
            },
            'active_component': 'simple_component',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.9},
            'error': None
        }
    elif complexity == 'medium':
        return {
            'kfm_action': {
                'action': 'marry',
                'component': 'data_processor',
                'reason': 'Good performance metrics with potential for enhancement'
            },
            'active_component': 'data_processor',
            'result': {
                'analysis': 'Component performed well but could benefit from integration',
                'metrics': {
                    'throughput': 875,
                    'error_rate': 0.02
                }
            },
            'execution_performance': {
                'latency': 0.65,
                'accuracy': 0.92,
                'memory_usage': 180
            },
            'error': None
        }
    else:  # complex
        return {
            'kfm_action': {
                'action': 'marry',
                'component': 'data_processor_advanced',
                'reason': 'Excellent performance metrics with high accuracy and good integration potential with other components in the pipeline including the analyzer and transformer modules'
            },
            'active_component': 'data_processor_advanced',
            'result': {
                'analysis': 'Detailed analysis of the component performance over extended runtime',
                'metrics': {
                    'throughput': 1200,
                    'error_rate': 0.005,
                    'response_distribution': [0.05, 0.15, 0.25, 0.35, 0.20],
                    'peak_memory': 512,
                    'avg_cpu_usage': 65.3,
                    'p99_latency': 0.85
                },
                'recommendations': [
                    'Consider enhancing with feature X to improve throughput',
                    'Monitor memory usage under high load conditions',
                    'Add additional error handling for edge cases',
                    'Optimize the internal queue management',
                    'Consider parallelizing the workload for better performance'
                ],
                'detailed_logs': [
                    {'timestamp': '2023-07-01T10:00:00', 'event': 'processing started', 'details': '...'},
                    {'timestamp': '2023-07-01T10:00:01', 'event': 'batch processed', 'details': '...'},
                    {'timestamp': '2023-07-01T10:00:02', 'event': 'optimization applied', 'details': '...'},
                    {'timestamp': '2023-07-01T10:00:03', 'event': 'processing completed', 'details': '...'}
                ]
            },
            'execution_performance': {
                'latency': 0.72,
                'accuracy': 0.985,
                'memory_usage': 487,
                'cpu_usage': 72.5,
                'io_operations': 1250,
                'throughput_per_second': 450,
                'batch_size': 64,
                'optimization_level': 3,
                'parallel_threads': 8
            },
            'error': None
        }

def benchmark_token_usage():
    """Benchmark token usage for different state complexities."""
    results = {}
    
    for complexity in ['simple', 'medium', 'complex']:
        state = generate_test_state(complexity)
        prompt = get_reflection_prompt(state)
        token_count = count_tokens(prompt)
        results[complexity] = {
            'token_count': token_count,
            'char_count': len(prompt),
            'token_to_char_ratio': token_count / len(prompt) if len(prompt) > 0 else 0
        }
        
        benchmark_logger.info(f"{complexity.capitalize()} state prompt: {token_count} tokens (estimated)")
    
    return results

def benchmark_generation_time(iterations=100):
    """Benchmark prompt generation time."""
    generation_times = {'simple': [], 'medium': [], 'complex': []}
    
    for complexity in ['simple', 'medium', 'complex']:
        state = generate_test_state(complexity)
        
        for _ in range(iterations):
            start_time = time.time()
            get_reflection_prompt(state)
            generation_time = time.time() - start_time
            generation_times[complexity].append(generation_time)
        
        avg_time = statistics.mean(generation_times[complexity])
        median_time = statistics.median(generation_times[complexity])
        min_time = min(generation_times[complexity])
        max_time = max(generation_times[complexity])
        
        benchmark_logger.info(f"{complexity.capitalize()} state generation time: "
                             f"avg={avg_time:.6f}s, median={median_time:.6f}s, "
                             f"min={min_time:.6f}s, max={max_time:.6f}s")
    
    return generation_times

def benchmark_api_processing_overhead():
    """Benchmark the processing overhead for API calls (excluding actual API latency)."""
    processing_times = {'simple': None, 'medium': None, 'complex': None}
    
    with patch('src.langgraph_nodes.genai') as mock_genai:
        # Configure the mock to return immediately
        mock_response = MagicMock()
        mock_response.text = "# Mock Reflection Response"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Set up environment variables
        os.environ["GOOGLE_API_KEY"] = "fake_api_key"
        
        for complexity in ['simple', 'medium', 'complex']:
            state = generate_test_state(complexity)
            
            # Measure processing time
            start_time = time.time()
            call_llm_for_reflection(state)
            processing_time = time.time() - start_time
            
            processing_times[complexity] = processing_time
            benchmark_logger.info(f"{complexity.capitalize()} state API processing overhead: {processing_time:.6f}s")
    
    return processing_times

def generate_report(token_results, generation_times, api_overhead):
    """Generate a comprehensive benchmark report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "token_usage": token_results,
        "generation_time": {
            k: {
                "average": statistics.mean(v),
                "median": statistics.median(v),
                "min": min(v),
                "max": max(v),
                "samples": len(v)
            } for k, v in generation_times.items()
        },
        "api_processing_overhead": api_overhead
    }
    
    # Save report to file
    report_dir = os.path.join(project_root, "logs", "performance")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"reflection_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    benchmark_logger.info(f"Benchmark report saved to {report_file}")
    
    # Print summary to console
    print("\n" + "="*80)
    print("REFLECTION PROMPT PERFORMANCE BENCHMARK SUMMARY")
    print("="*80)
    
    print("\nTOKEN USAGE:")
    for complexity, data in token_results.items():
        print(f"  {complexity.capitalize()}: {data['token_count']} tokens ({data['char_count']} characters)")
    
    print("\nPROMPT GENERATION TIME:")
    for complexity, stats in report["generation_time"].items():
        print(f"  {complexity.capitalize()}: avg={stats['average']:.6f}s, median={stats['median']:.6f}s")
    
    print("\nAPI PROCESSING OVERHEAD (excluding actual API latency):")
    for complexity, time_val in api_overhead.items():
        print(f"  {complexity.capitalize()}: {time_val:.6f}s")
    
    print("\nDetailed report saved to:", report_file)
    print("="*80 + "\n")
    
    return report_file

def main():
    """Run all benchmarks and generate report."""
    print("Running reflection prompt performance benchmarks...")
    
    # Run benchmarks
    token_results = benchmark_token_usage()
    generation_times = benchmark_generation_time()
    api_overhead = benchmark_api_processing_overhead()
    
    # Generate and save report
    report_file = generate_report(token_results, generation_times, api_overhead)
    
    print(f"Benchmark completed. Report saved to {report_file}")

if __name__ == "__main__":
    main() 