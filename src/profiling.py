"""
Performance profiling utilities for LangGraph workflow.

This module provides functions and classes for measuring the performance
of graph execution, identifying bottlenecks, tracking memory usage,
and generating performance reports.
"""

import time
import gc
import sys
import statistics
import json
import os
import datetime
import logging
from typing import Dict, Any, List, Optional, Set, Union, Tuple, Callable
from functools import wraps
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from src.logger import setup_logger
from src.core.state import KFMAgentState

# Setup logger for the profiling module
profile_logger = setup_logger('src.profiling')

class PerformanceProfiler:
    """
    Central class for performance profiling of graph execution.
    
    This class handles:
    - Timing node execution
    - Tracking node execution frequencies
    - Identifying performance bottlenecks
    - Monitoring memory usage
    - Generating performance reports
    """
    
    def __init__(self, 
                 enabled: bool = True,
                 detailed_timing: bool = True,
                 memory_tracking: bool = True,
                 bottleneck_detection: bool = True,
                 bottleneck_threshold: float = 0.1,
                 report_dir: str = "logs/performance"):
        """
        Initialize the performance profiler.
        
        Args:
            enabled: Whether profiling is enabled
            detailed_timing: Whether to collect detailed timing statistics
            memory_tracking: Whether to track memory usage
            bottleneck_detection: Whether to identify bottlenecks
            bottleneck_threshold: Threshold for bottleneck detection (proportion of total time)
            report_dir: Directory for storing performance reports
        """
        self.enabled = enabled
        self.detailed_timing = detailed_timing
        self.memory_tracking = memory_tracking
        self.bottleneck_detection = bottleneck_detection
        self.bottleneck_threshold = bottleneck_threshold
        self.report_dir = report_dir
        
        # Ensure report directory exists
        os.makedirs(report_dir, exist_ok=True)
        
        # Execution statistics storage
        self.node_timing: Dict[str, List[float]] = defaultdict(list)
        self.node_calls: Dict[str, int] = defaultdict(int)
        self.node_memory: Dict[str, List[int]] = defaultdict(list)
        self.execution_timeline: List[Dict[str, Any]] = []
        
        # Current run information
        self.current_run_id: Optional[str] = None
        self.run_start_time: Optional[float] = None
        self.run_end_time: Optional[float] = None
        self.total_nodes_executed: int = 0
        
        # Historical runs for comparison
        self.historical_runs: Dict[str, Dict[str, Any]] = {}
        
        profile_logger.info("Performance profiler initialized")
    
    def start_run(self, run_id: Optional[str] = None) -> str:
        """
        Start a new profiling run.
        
        Args:
            run_id: Optional identifier for this run
            
        Returns:
            The run ID (generated if not provided)
        """
        if not self.enabled:
            return "disabled"
            
        # Generate a timestamp-based ID if not provided
        if run_id is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"run_{timestamp}"
        
        self.current_run_id = run_id
        self.run_start_time = time.perf_counter()
        self.total_nodes_executed = 0
        
        # Clear execution timeline for this run
        self.execution_timeline = []
        
        profile_logger.info(f"Started profiling run: {run_id}")
        return run_id
    
    def end_run(self) -> Dict[str, Any]:
        """
        End the current profiling run and generate summary.
        
        Returns:
            Summary statistics for the run
        """
        if not self.enabled or self.current_run_id is None:
            return {}
            
        self.run_end_time = time.perf_counter()
        
        # Calculate overall run statistics
        run_time = self.run_end_time - self.run_start_time
        
        # Create run summary
        summary = {
            "run_id": self.current_run_id,
            "start_time": self.run_start_time,
            "end_time": self.run_end_time,
            "total_time": run_time,
            "nodes_executed": self.total_nodes_executed,
            "node_statistics": self._generate_node_statistics()
        }
        
        # Identify bottlenecks if enabled
        if self.bottleneck_detection:
            summary["bottlenecks"] = self._identify_bottlenecks(run_time)
        
        # Store in historical runs
        self.historical_runs[self.current_run_id] = summary
        
        profile_logger.info(f"Ended profiling run: {self.current_run_id}. "
                           f"Total time: {run_time:.4f}s, Nodes executed: {self.total_nodes_executed}")
        
        # Clear current run data
        self.current_run_id = None
        
        return summary
    
    def record_node_execution(self, 
                             node_name: str, 
                             execution_time: float, 
                             input_state: Dict[str, Any],
                             output_state: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a single node execution.
        
        Args:
            node_name: Name of the executed node
            execution_time: Time taken for execution in seconds
            input_state: Input state to the node
            output_state: Output state from the node (if available)
        """
        if not self.enabled or self.current_run_id is None:
            return
            
        # Update timing statistics
        self.node_timing[node_name].append(execution_time)
        self.node_calls[node_name] += 1
        self.total_nodes_executed += 1
        
        # Create execution event
        event = {
            "timestamp": time.perf_counter(),
            "node_name": node_name,
            "execution_time": execution_time,
            "run_id": self.current_run_id
        }
        
        # Memory tracking if enabled
        if self.memory_tracking and output_state is not None:
            # Estimate memory usage of state
            memory_usage = self._estimate_state_size(output_state)
            self.node_memory[node_name].append(memory_usage)
            event["memory_usage"] = memory_usage
        
        # Add to timeline
        self.execution_timeline.append(event)
        
        profile_logger.debug(f"Recorded node execution: {node_name}, Time: {execution_time:.4f}s")
    
    def profile_node(self, func: Callable) -> Callable:
        """
        Decorator for profiling node execution.
        
        Args:
            func: Node function to profile
            
        Returns:
            Profiled function
        """
        @wraps(func)
        def wrapper(state: Union[Dict[str, Any], KFMAgentState], *args, **kwargs):
            if not self.enabled:
                return func(state, *args, **kwargs)
                
            # Start timing
            start_time = time.perf_counter()
            
            # Convert state to dict if it's not already
            if not isinstance(state, dict):
                input_state_dict = state.to_dict()
            else:
                input_state_dict = state.copy()
            
            # Run the function
            result = func(state, *args, **kwargs)
            
            # End timing
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            
            # Convert result to dict if needed
            if result is not None:
                if not isinstance(result, dict):
                    result_dict = result.to_dict()
                else:
                    result_dict = result.copy()
            else:
                result_dict = None
            
            # Record the execution
            self.record_node_execution(
                node_name=func.__name__,
                execution_time=execution_time,
                input_state=input_state_dict,
                output_state=result_dict
            )
            
            return result
        
        return wrapper
    
    def get_node_statistics(self, node_name: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific node.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Dictionary of node execution statistics
        """
        if node_name not in self.node_timing:
            return {
                "node_name": node_name,
                "calls": 0,
                "total_time": 0,
                "statistics": {}
            }
            
        times = self.node_timing[node_name]
        
        stats = {
            "node_name": node_name,
            "calls": self.node_calls[node_name],
            "total_time": sum(times),
            "statistics": {
                "min": min(times),
                "max": max(times),
                "mean": statistics.mean(times),
                "median": statistics.median(times)
            }
        }
        
        # Add percentiles if we have enough data
        if len(times) >= 5:
            stats["statistics"]["percentiles"] = {
                "p90": np.percentile(times, 90),
                "p95": np.percentile(times, 95),
                "p99": np.percentile(times, 99)
            }
        
        # Add memory stats if available
        if node_name in self.node_memory:
            memory_data = self.node_memory[node_name]
            stats["memory"] = {
                "min": min(memory_data),
                "max": max(memory_data),
                "mean": statistics.mean(memory_data),
                "current": memory_data[-1] if memory_data else 0
            }
        
        return stats
    
    def generate_report(self, 
                       run_id: Optional[str] = None, 
                       include_graphs: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.
        
        Args:
            run_id: ID of the run to report on (latest by default)
            include_graphs: Whether to generate and save visualizations
            
        Returns:
            Performance report data
        """
        # Use latest run if none specified
        if run_id is None:
            if self.current_run_id is not None:
                run_id = self.current_run_id
            elif self.historical_runs:
                run_id = list(self.historical_runs.keys())[-1]
            else:
                return {"error": "No runs available"}
        
        # Get run data
        if run_id in self.historical_runs:
            run_data = self.historical_runs[run_id]
        else:
            return {"error": f"Run {run_id} not found"}
        
        # Create detailed report
        report = {
            "run_id": run_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "run_summary": run_data,
            "node_details": {
                node: self.get_node_statistics(node)
                for node in self.node_timing.keys()
            }
        }
        
        # Generate graphs if requested
        if include_graphs:
            graph_paths = self._generate_visualization(run_id)
            report["visualizations"] = graph_paths
        
        # Save the report
        report_path = os.path.join(self.report_dir, f"report_{run_id}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        profile_logger.info(f"Generated performance report for run {run_id}: {report_path}")
        
        return report
    
    def compare_runs(self, 
                    run_ids: List[str], 
                    include_graphs: bool = True) -> Dict[str, Any]:
        """
        Compare multiple profiling runs.
        
        Args:
            run_ids: List of run IDs to compare
            include_graphs: Whether to generate comparison visualizations
            
        Returns:
            Comparison report
        """
        if not all(run_id in self.historical_runs for run_id in run_ids):
            missing = [run_id for run_id in run_ids if run_id not in self.historical_runs]
            return {"error": f"Runs not found: {missing}"}
        
        # Extract data for comparison
        comparison = {
            "run_ids": run_ids,
            "timestamp": datetime.datetime.now().isoformat(),
            "total_times": {
                run_id: self.historical_runs[run_id]["total_time"]
                for run_id in run_ids
            },
            "nodes_executed": {
                run_id: self.historical_runs[run_id]["nodes_executed"]
                for run_id in run_ids
            },
            "node_comparisons": {}
        }
        
        # Compare node statistics
        all_nodes = set()
        for run_id in run_ids:
            all_nodes.update(self.historical_runs[run_id]["node_statistics"].keys())
        
        for node in all_nodes:
            comparison["node_comparisons"][node] = {
                run_id: self.historical_runs[run_id]["node_statistics"].get(node, {})
                for run_id in run_ids
            }
        
        # Generate comparison visualizations
        if include_graphs:
            graph_paths = self._generate_comparison_visualization(run_ids)
            comparison["visualizations"] = graph_paths
        
        # Save the comparison report
        comparison_id = "_vs_".join(run_ids)
        report_path = os.path.join(self.report_dir, f"comparison_{comparison_id}.json")
        with open(report_path, 'w') as f:
            json.dump(comparison, f, indent=2)
        
        profile_logger.info(f"Generated comparison report: {report_path}")
        
        return comparison
    
    def clear_data(self, keep_historical: bool = False) -> None:
        """
        Clear profiling data.
        
        Args:
            keep_historical: Whether to keep historical run data
        """
        self.node_timing = defaultdict(list)
        self.node_calls = defaultdict(int)
        self.node_memory = defaultdict(list)
        self.execution_timeline = []
        self.total_nodes_executed = 0
        
        if not keep_historical:
            self.historical_runs = {}
        
        profile_logger.info("Cleared profiling data")
    
    def _estimate_state_size(self, state: Dict[str, Any]) -> int:
        """
        Estimate the memory size of a state object.
        
        Args:
            state: The state dictionary to measure
            
        Returns:
            Estimated size in bytes
        """
        # Direct measurement using sys.getsizeof
        # This is an approximation as it doesn't fully account for all nested objects
        try:
            return sys.getsizeof(state)
        except:
            return 0
    
    def _generate_node_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate statistics for all profiled nodes.
        
        Returns:
            Dictionary of node statistics
        """
        return {
            node: {
                "calls": self.node_calls[node],
                "total_time": sum(self.node_timing[node]),
                "mean_time": statistics.mean(self.node_timing[node]) if self.node_timing[node] else 0,
                "max_time": max(self.node_timing[node]) if self.node_timing[node] else 0,
                "memory": {
                    "mean": statistics.mean(self.node_memory[node]) if node in self.node_memory and self.node_memory[node] else 0,
                    "max": max(self.node_memory[node]) if node in self.node_memory and self.node_memory[node] else 0
                } if self.memory_tracking else {}
            }
            for node in self.node_timing.keys()
        }
    
    def _identify_bottlenecks(self, total_run_time: float) -> List[Dict[str, Any]]:
        """
        Identify performance bottlenecks.
        
        Args:
            total_run_time: Total execution time of the run
            
        Returns:
            List of identified bottlenecks with details
        """
        bottlenecks = []
        
        for node, times in self.node_timing.items():
            node_total_time = sum(times)
            time_proportion = node_total_time / total_run_time if total_run_time > 0 else 0
            
            # Check if this node exceeds the bottleneck threshold
            if time_proportion >= self.bottleneck_threshold:
                bottleneck = {
                    "node_name": node,
                    "total_time": node_total_time,
                    "proportion": time_proportion,
                    "calls": self.node_calls[node],
                    "avg_time": statistics.mean(times),
                    "severity": "high" if time_proportion >= 0.3 else "medium"
                }
                
                # Add memory information if available
                if node in self.node_memory:
                    bottleneck["memory"] = {
                        "avg": statistics.mean(self.node_memory[node]),
                        "max": max(self.node_memory[node])
                    }
                
                bottlenecks.append(bottleneck)
        
        # Sort bottlenecks by proportion of time
        bottlenecks.sort(key=lambda x: x["proportion"], reverse=True)
        
        return bottlenecks
    
    def _generate_visualization(self, run_id: str) -> Dict[str, str]:
        """
        Generate performance visualization graphs.
        
        Args:
            run_id: ID of the run to visualize
            
        Returns:
            Dictionary of graph file paths
        """
        graph_paths = {}
        
        # Extract relevant data
        if run_id not in self.historical_runs:
            return {"error": f"Run {run_id} not found"}
            
        run_data = self.historical_runs[run_id]
        node_stats = run_data["node_statistics"]
        
        # Create graph directory
        graph_dir = os.path.join(self.report_dir, f"graphs_{run_id}")
        os.makedirs(graph_dir, exist_ok=True)
        
        # 1. Node execution time bar chart
        plt.figure(figsize=(12, 8))
        nodes = list(node_stats.keys())
        times = [node_stats[node]["total_time"] for node in nodes]
        
        plt.bar(nodes, times)
        plt.xlabel('Node')
        plt.ylabel('Total Execution Time (s)')
        plt.title(f'Node Execution Times - Run {run_id}')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        time_chart_path = os.path.join(graph_dir, "node_times.png")
        plt.savefig(time_chart_path)
        plt.close()
        graph_paths["node_times"] = time_chart_path
        
        # 2. Node call frequency pie chart
        plt.figure(figsize=(10, 10))
        calls = [node_stats[node]["calls"] for node in nodes]
        
        plt.pie(calls, labels=nodes, autopct='%1.1f%%')
        plt.title(f'Node Call Distribution - Run {run_id}')
        plt.tight_layout()
        
        calls_chart_path = os.path.join(graph_dir, "node_calls.png")
        plt.savefig(calls_chart_path)
        plt.close()
        graph_paths["node_calls"] = calls_chart_path
        
        # 3. Memory usage chart (if available)
        if self.memory_tracking:
            memory_nodes = [node for node in nodes if node_stats[node].get("memory", {}).get("mean", 0) > 0]
            
            if memory_nodes:
                plt.figure(figsize=(12, 8))
                memory_values = [node_stats[node]["memory"]["mean"] for node in memory_nodes]
                
                plt.bar(memory_nodes, memory_values)
                plt.xlabel('Node')
                plt.ylabel('Average Memory Usage (bytes)')
                plt.title(f'Node Memory Usage - Run {run_id}')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                memory_chart_path = os.path.join(graph_dir, "memory_usage.png")
                plt.savefig(memory_chart_path)
                plt.close()
                graph_paths["memory_usage"] = memory_chart_path
        
        return graph_paths
    
    def _generate_comparison_visualization(self, run_ids: List[str]) -> Dict[str, str]:
        """
        Generate comparison visualizations for multiple runs.
        
        Args:
            run_ids: List of run IDs to compare
            
        Returns:
            Dictionary of graph file paths
        """
        if not all(run_id in self.historical_runs for run_id in run_ids):
            return {"error": "Some runs not found"}
            
        graph_paths = {}
        
        # Create graph directory
        comparison_id = "_vs_".join(run_ids)
        graph_dir = os.path.join(self.report_dir, f"comparison_{comparison_id}")
        os.makedirs(graph_dir, exist_ok=True)
        
        # 1. Total execution time comparison
        plt.figure(figsize=(10, 6))
        times = [self.historical_runs[run_id]["total_time"] for run_id in run_ids]
        
        plt.bar(run_ids, times)
        plt.xlabel('Run ID')
        plt.ylabel('Total Execution Time (s)')
        plt.title('Total Execution Time Comparison')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        total_time_path = os.path.join(graph_dir, "total_time_comparison.png")
        plt.savefig(total_time_path)
        plt.close()
        graph_paths["total_time"] = total_time_path
        
        # 2. Node-by-node comparison (for common nodes)
        # Find common nodes across all runs
        common_nodes = set()
        for run_id in run_ids:
            if common_nodes:
                common_nodes &= set(self.historical_runs[run_id]["node_statistics"].keys())
            else:
                common_nodes = set(self.historical_runs[run_id]["node_statistics"].keys())
        
        if common_nodes:
            plt.figure(figsize=(12, 8))
            
            x = np.arange(len(common_nodes))
            width = 0.8 / len(run_ids)
            
            for i, run_id in enumerate(run_ids):
                node_times = [self.historical_runs[run_id]["node_statistics"][node]["mean_time"] 
                             for node in common_nodes]
                plt.bar(x + i*width, node_times, width, label=run_id)
            
            plt.xlabel('Node')
            plt.ylabel('Average Execution Time (s)')
            plt.title('Node Performance Comparison')
            plt.xticks(x + width * (len(run_ids) - 1) / 2, list(common_nodes), rotation=45, ha='right')
            plt.legend()
            plt.tight_layout()
            
            node_comparison_path = os.path.join(graph_dir, "node_comparison.png")
            plt.savefig(node_comparison_path)
            plt.close()
            graph_paths["node_comparison"] = node_comparison_path
        
        return graph_paths

# Global profiler instance
_profiler = None

def get_profiler() -> PerformanceProfiler:
    """
    Get the global profiler instance.
    
    Returns:
        The global PerformanceProfiler instance
    """
    global _profiler
    
    if _profiler is None:
        _profiler = PerformanceProfiler()
        
    return _profiler

def profile_node(func: Callable) -> Callable:
    """
    Decorator for profiling node execution.
    
    Args:
        func: Node function to profile
        
    Returns:
        Profiled function
    """
    return get_profiler().profile_node(func)

def start_profiling_run(run_id: Optional[str] = None) -> str:
    """
    Start a new profiling run.
    
    Args:
        run_id: Optional identifier for this run
        
    Returns:
        The run ID
    """
    return get_profiler().start_run(run_id)

def end_profiling_run() -> Dict[str, Any]:
    """
    End the current profiling run and generate summary.
    
    Returns:
        Summary statistics for the run
    """
    return get_profiler().end_run()

def generate_performance_report(run_id: Optional[str] = None, 
                               include_graphs: bool = True) -> Dict[str, Any]:
    """
    Generate a comprehensive performance report.
    
    Args:
        run_id: ID of the run to report on (latest by default)
        include_graphs: Whether to generate and save visualizations
        
    Returns:
        Performance report data
    """
    return get_profiler().generate_report(run_id, include_graphs)

def compare_profiling_runs(run_ids: List[str], 
                          include_graphs: bool = True) -> Dict[str, Any]:
    """
    Compare multiple profiling runs.
    
    Args:
        run_ids: List of run IDs to compare
        include_graphs: Whether to generate comparison visualizations
        
    Returns:
        Comparison report
    """
    return get_profiler().compare_runs(run_ids, include_graphs)

def configure_profiler(enabled: bool = True,
                      detailed_timing: bool = True,
                      memory_tracking: bool = True,
                      bottleneck_detection: bool = True,
                      bottleneck_threshold: float = 0.1,
                      report_dir: str = "logs/performance") -> None:
    """
    Configure the global profiler.
    
    Args:
        enabled: Whether profiling is enabled
        detailed_timing: Whether to collect detailed timing statistics
        memory_tracking: Whether to track memory usage
        bottleneck_detection: Whether to identify bottlenecks
        bottleneck_threshold: Threshold for bottleneck detection (proportion of total time)
        report_dir: Directory for storing performance reports
    """
    global _profiler
    
    _profiler = PerformanceProfiler(
        enabled=enabled,
        detailed_timing=detailed_timing,
        memory_tracking=memory_tracking,
        bottleneck_detection=bottleneck_detection,
        bottleneck_threshold=bottleneck_threshold,
        report_dir=report_dir
    )
    
    profile_logger.info("Global profiler configured")

def clear_profiling_data(keep_historical: bool = False) -> None:
    """
    Clear profiling data.
    
    Args:
        keep_historical: Whether to keep historical run data
    """
    get_profiler().clear_data(keep_historical) 