# Graph Execution Errors

This document describes common errors that can occur during graph execution and how to resolve them.

## Node Not Found

### Problem
This error occurs when the graph tries to execute a node that doesn't exist.

### Possible Causes
- Typo in node name
- Node not properly registered in the graph
- Attempting to use a node from a different graph

### Solutions
1. Check for typos in node names
2. Verify that the node is registered in the graph
3. Use `graph.get_nodes()` to list all available nodes

## Cycle Detected

### Problem
This error occurs when there is a circular dependency in the graph.

### Possible Causes
- Node A depends on Node B, which depends on Node A
- Complex dependency chain creating a loop

### Solutions
1. Review the graph structure to identify the cycle
2. Implement a condition to break the cycle
3. Restructure the graph to eliminate circular dependencies
