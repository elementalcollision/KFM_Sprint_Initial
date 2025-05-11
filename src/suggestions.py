"""
Error Suggestions Engine for LangGraph workflow.

This module provides intelligent suggestions for resolving errors in LangGraph
applications, including pattern matching, heuristics, documentation linking,
and feedback collection.

It builds on the existing error context system to provide targeted, actionable
suggestions for resolving common errors and issues.
"""

import os
import re
import json
import logging
import traceback
import datetime
from typing import Dict, Any, List, Optional, Tuple, Union, Set, Callable
from collections import defaultdict, Counter
import difflib
from dataclasses import dataclass, field
from functools import lru_cache
import sys

from src.error_context import (
    EnhancedError,
    get_similar_errors,
    get_error_statistics,
    get_recent_errors,
    analyze_error_patterns,
    normalize_error_message
)

from src.logger import setup_logger

# Set up logger
suggestions_logger = setup_logger('suggestions')

# Directory for error knowledge base
KNOWLEDGE_BASE_DIR = "logs/error_knowledge_base"
FEEDBACK_DIR = "logs/error_feedback"
DOCUMENTATION_DIR = "docs/error_docs"

# Ensure directories exist
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(DOCUMENTATION_DIR, exist_ok=True)

# Load the knowledge base on module import
_knowledge_base = {}
_feedback_data = defaultdict(list)
_documentation_index = {}

@dataclass
class SuggestionEntry:
    """A suggestion for resolving an error."""
    suggestion: str
    confidence: float = 1.0
    example: Optional[str] = None
    documentation_link: Optional[str] = None
    feedback_score: float = 0.0
    feedback_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "example": self.example,
            "documentation_link": self.documentation_link,
            "feedback_score": self.feedback_score,
            "feedback_count": self.feedback_count,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SuggestionEntry':
        """Create from dictionary."""
        return cls(
            suggestion=data["suggestion"],
            confidence=data.get("confidence", 1.0),
            example=data.get("example"),
            documentation_link=data.get("documentation_link"),
            feedback_score=data.get("feedback_score", 0.0),
            feedback_count=data.get("feedback_count", 0),
            tags=data.get("tags", [])
        )

@dataclass
class ErrorPattern:
    """A pattern for matching errors."""
    pattern: str
    regex: bool = False
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    suggestions: List[SuggestionEntry] = field(default_factory=list)
    
    def matches(self, error_message: str) -> bool:
        """Check if the pattern matches the error message."""
        if self.regex:
            return bool(re.search(self.pattern, error_message))
        else:
            return self.pattern.lower() in error_message.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern,
            "regex": self.regex,
            "category": self.category,
            "tags": self.tags,
            "suggestions": [s.to_dict() for s in self.suggestions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorPattern':
        """Create from dictionary."""
        return cls(
            pattern=data["pattern"],
            regex=data.get("regex", False),
            category=data.get("category"),
            tags=data.get("tags", []),
            suggestions=[SuggestionEntry.from_dict(s) for s in data.get("suggestions", [])]
        )

@dataclass
class DocumentationReference:
    """A reference to documentation for an error."""
    title: str
    path: str
    url: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    error_patterns: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "path": self.path,
            "url": self.url,
            "description": self.description,
            "tags": self.tags,
            "error_patterns": self.error_patterns
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentationReference':
        """Create from dictionary."""
        return cls(
            title=data["title"],
            path=data["path"],
            url=data.get("url"),
            description=data.get("description"),
            tags=data.get("tags", []),
            error_patterns=data.get("error_patterns", [])
        )

class SuggestionsEngine:
    """
    Engine for generating error suggestions.
    
    This class provides methods for generating suggestions for resolving
    errors, based on patterns, heuristics, and feedback.
    """
    
    def __init__(self):
        """Initialize the suggestions engine."""
        self.knowledge_base = {}
        self.documentation_index = {}
        self.feedback_data = defaultdict(list)
        self.load_knowledge_base()
        self.load_documentation_index()
        self.load_feedback_data()
    
    def load_knowledge_base(self) -> None:
        """Load the error knowledge base from disk."""
        kb_path = os.path.join(KNOWLEDGE_BASE_DIR, "knowledge_base.json")
        if os.path.exists(kb_path):
            try:
                with open(kb_path, 'r') as f:
                    data = json.load(f)
                    self.knowledge_base = {
                        k: [ErrorPattern.from_dict(p) for p in patterns]
                        for k, patterns in data.items()
                    }
                suggestions_logger.info(f"Loaded knowledge base with {sum(len(v) for v in self.knowledge_base.values())} patterns")
            except Exception as e:
                suggestions_logger.error(f"Failed to load knowledge base: {e}")
                # Initialize with default patterns
                self._initialize_default_knowledge_base()
        else:
            suggestions_logger.warning(f"Knowledge base not found at {kb_path}, initializing defaults")
            self._initialize_default_knowledge_base()
    
    def _initialize_default_knowledge_base(self) -> None:
        """Initialize the knowledge base with default patterns."""
        # Create default knowledge base
        self.knowledge_base = self._create_default_knowledge_base()
        self.save_knowledge_base()
    
    def _create_default_knowledge_base(self) -> Dict[str, List[ErrorPattern]]:
        """Create the default knowledge base with common patterns."""
        knowledge_base = defaultdict(list)
        
        # Add common error patterns for each category
        # GRAPH_EXECUTION errors
        knowledge_base["GRAPH_EXECUTION"] = [
            ErrorPattern(
                pattern="node .* not found",
                regex=True,
                category="GRAPH_EXECUTION",
                tags=["node", "missing"],
                suggestions=[
                    SuggestionEntry(
                        suggestion="Verify that the node name is correct and exists in the graph definition",
                        confidence=0.9,
                        example="Check if 'process_data' is correctly defined in your graph"
                    ),
                    SuggestionEntry(
                        suggestion="Check for typos in node names when calling the graph",
                        confidence=0.8
                    )
                ]
            ),
            ErrorPattern(
                pattern="cycle detected",
                category="GRAPH_EXECUTION",
                tags=["cycle", "graph-structure"],
                suggestions=[
                    SuggestionEntry(
                        suggestion="Review graph structure for circular dependencies between nodes",
                        confidence=0.9,
                        example="Nodes A -> B -> C -> A creates a cycle"
                    ),
                    SuggestionEntry(
                        suggestion="Implement a condition to break the cycle",
                        confidence=0.7
                    )
                ]
            )
        ]
        
        # STATE_VALIDATION errors
        knowledge_base["STATE_VALIDATION"] = [
            ErrorPattern(
                pattern="required field .* missing",
                regex=True,
                category="STATE_VALIDATION",
                tags=["missing-field"],
                suggestions=[
                    SuggestionEntry(
                        suggestion="Check if the required field is being properly initialized",
                        confidence=0.9
                    ),
                    SuggestionEntry(
                        suggestion="Add validation to ensure required fields are present before passing to next node",
                        confidence=0.8,
                        example="if 'user_data' not in state: state['user_data'] = {}"
                    )
                ]
            ),
            ErrorPattern(
                pattern="type mismatch",
                category="STATE_VALIDATION",
                tags=["type-error"],
                suggestions=[
                    SuggestionEntry(
                        suggestion="Verify the type of the value before operations",
                        confidence=0.9,
                        example="if not isinstance(data, dict): data = {}"
                    ),
                    SuggestionEntry(
                        suggestion="Add type conversion where appropriate",
                        confidence=0.8,
                        example="amount = float(amount) if isinstance(amount, str) else amount"
                    )
                ]
            )
        ]
        
        # Add more categories and patterns...
        
        return knowledge_base
    
    def save_knowledge_base(self) -> None:
        """Save the knowledge base to disk."""
        kb_path = os.path.join(KNOWLEDGE_BASE_DIR, "knowledge_base.json")
        try:
            with open(kb_path, 'w') as f:
                json.dump({
                    k: [p.to_dict() for p in patterns]
                    for k, patterns in self.knowledge_base.items()
                }, f, indent=2)
            suggestions_logger.info(f"Saved knowledge base to {kb_path}")
        except Exception as e:
            suggestions_logger.error(f"Failed to save knowledge base: {e}")
    
    def load_documentation_index(self) -> None:
        """Load the documentation index from disk."""
        index_path = os.path.join(DOCUMENTATION_DIR, "index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                    self.documentation_index = {
                        k: DocumentationReference.from_dict(v)
                        for k, v in data.items()
                    }
                suggestions_logger.info(f"Loaded documentation index with {len(self.documentation_index)} entries")
            except Exception as e:
                suggestions_logger.error(f"Failed to load documentation index: {e}")
                self._initialize_default_documentation()
        else:
            suggestions_logger.warning(f"Documentation index not found at {index_path}, initializing defaults")
            self._initialize_default_documentation()
    
    def _initialize_default_documentation(self) -> None:
        """Initialize default documentation references."""
        # Create documentation directory and index
        os.makedirs(os.path.join(DOCUMENTATION_DIR, "errors"), exist_ok=True)
        
        # Create sample documentation files
        self._create_sample_documentation()
        
        # Create index of documentation
        self._create_documentation_index()
        
        # Save the index
        self.save_documentation_index()
    
    def _create_sample_documentation(self) -> None:
        """Create sample documentation files."""
        # Create documentation for common errors
        docs = [
            {
                "title": "Graph Execution Errors",
                "filename": "graph_execution_errors.md",
                "content": """# Graph Execution Errors

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
"""
            },
            {
                "title": "State Validation Errors",
                "filename": "state_validation_errors.md",
                "content": """# State Validation Errors

This document describes common errors related to state validation and how to resolve them.

## Missing Required Field

### Problem
This error occurs when a required field is missing from the state.

### Possible Causes
- Field not initialized properly
- Field removed by a previous node
- Typo in field name

### Solutions
1. Add validation to ensure required fields are present
2. Initialize fields with default values
3. Use defensive programming to check for fields before accessing

## Type Mismatch

### Problem
This error occurs when a field in the state has an unexpected type.

### Possible Causes
- Field initialized with wrong type
- Type conversion not performed
- API returning unexpected data type

### Solutions
1. Add type checking before operations
2. Convert types when necessary
3. Add validation for API responses
"""
            }
        ]
        
        # Write documentation files
        for doc in docs:
            doc_path = os.path.join(DOCUMENTATION_DIR, "errors", doc["filename"])
            with open(doc_path, 'w') as f:
                f.write(doc["content"])
            
            # Add to documentation index
            doc_id = doc["filename"].replace(".md", "")
            self.documentation_index[doc_id] = DocumentationReference(
                title=doc["title"],
                path=f"errors/{doc['filename']}",
                description=doc["title"],
                tags=[doc_id.replace("_", "-")]
            )
    
    def _create_documentation_index(self) -> None:
        """Create index of documentation files."""
        # Scan documentation directory for files
        for root, _, files in os.walk(os.path.join(DOCUMENTATION_DIR, "errors")):
            for filename in files:
                if filename.endswith(".md") and filename.replace(".md", "") not in self.documentation_index:
                    rel_path = os.path.join(os.path.relpath(root, DOCUMENTATION_DIR), filename)
                    doc_id = filename.replace(".md", "")
                    
                    # Read first line as title
                    with open(os.path.join(root, filename), 'r') as f:
                        first_line = f.readline().strip()
                        title = first_line.replace("# ", "") if first_line.startswith("# ") else doc_id.replace("_", " ").title()
                    
                    # Add to index
                    self.documentation_index[doc_id] = DocumentationReference(
                        title=title,
                        path=rel_path,
                        tags=[doc_id.replace("_", "-")]
                    )
    
    def save_documentation_index(self) -> None:
        """Save the documentation index to disk."""
        index_path = os.path.join(DOCUMENTATION_DIR, "index.json")
        try:
            with open(index_path, 'w') as f:
                json.dump({
                    k: v.to_dict()
                    for k, v in self.documentation_index.items()
                }, f, indent=2)
            suggestions_logger.info(f"Saved documentation index to {index_path}")
        except Exception as e:
            suggestions_logger.error(f"Failed to save documentation index: {e}")
    
    def load_feedback_data(self) -> None:
        """Load feedback data from disk."""
        feedback_path = os.path.join(FEEDBACK_DIR, "feedback.json")
        if os.path.exists(feedback_path):
            try:
                with open(feedback_path, 'r') as f:
                    self.feedback_data = defaultdict(list, json.load(f))
                suggestions_logger.info(f"Loaded feedback data with {sum(len(v) for v in self.feedback_data.values())} entries")
            except Exception as e:
                suggestions_logger.error(f"Failed to load feedback data: {e}")
        else:
            suggestions_logger.info(f"No feedback data found at {feedback_path}")
    
    def save_feedback_data(self) -> None:
        """Save feedback data to disk."""
        feedback_path = os.path.join(FEEDBACK_DIR, "feedback.json")
        try:
            with open(feedback_path, 'w') as f:
                json.dump(dict(self.feedback_data), f, indent=2)
            suggestions_logger.info(f"Saved feedback data to {feedback_path}")
        except Exception as e:
            suggestions_logger.error(f"Failed to save feedback data: {e}")
    
    def get_suggestions_for_error(self, error: Union[EnhancedError, str]) -> Dict[str, Any]:
        """
        Get suggestions for resolving an error.
        
        Args:
            error: The error to get suggestions for
            
        Returns:
            Dictionary with suggestions
        """
        # Get error details
        if isinstance(error, str):
            # Try to find the error in registry
            from src.error_context import _error_registry
            for uid, err in _error_registry.items():
                if uid == error or err.error_code == error:
                    error = err
                    break
            
            # If still a string, return generic suggestions
            if isinstance(error, str):
                return {
                    "error": f"Error not found: {error}",
                    "suggestions": self._get_generic_suggestions(),
                    "documentation": []
                }
        
        # Get basic suggestions
        basic_suggestions = self._get_basic_suggestions(error)
        
        # Enhance with advanced suggestions
        advanced_suggestions = self._get_advanced_suggestions(error)
        
        # Get documentation references
        documentation = self._get_documentation_for_error(error)
        
        # Combine and rank suggestions
        all_suggestions = basic_suggestions.get("suggestions", []) + [s.suggestion for s in advanced_suggestions]
        ranked_suggestions = self._rank_suggestions(all_suggestions, error)
        
        # Return combined results
        result = {
            "error_code": basic_suggestions.get("error_code", "unknown"),
            "category": basic_suggestions.get("category", "UNKNOWN"),
            "message": basic_suggestions.get("message", str(error)),
            "suggestions": ranked_suggestions,
            "documentation": documentation,
            "similar_errors_count": basic_suggestions.get("similar_errors_count", 0)
        }
        
        return result
    
    def _get_basic_suggestions(self, error: EnhancedError) -> Dict[str, Any]:
        """
        Get basic suggestions from the error context system.
        
        Args:
            error: The error to get suggestions for
            
        Returns:
            Dictionary with suggestions
        """
        # Create basic suggestion structure
        suggestions = []
        
        # Add category-based suggestions if we know the category
        if hasattr(error, 'category'):
            category = error.category
            category_suggestions = {
                "GRAPH_EXECUTION": [
                    "Check for proper node connectivity in the graph",
                    "Verify that state is properly flowing between nodes"
                ],
                "STATE_VALIDATION": [
                    "Check the expected schema of the state",
                    "Verify that required fields are present"
                ],
                "API_INTEGRATION": [
                    "Verify API credentials and permissions",
                    "Check network connectivity"
                ]
            }
            
            if category in category_suggestions:
                suggestions.extend(category_suggestions[category])
        
        # Add error type-specific suggestions
        if hasattr(error, 'original_error') and error.original_error:
            error_type = type(error.original_error).__name__
            if error_type == "KeyError":
                suggestions.append("Check if the required key exists in the dictionary")
            elif error_type == "TypeError":
                suggestions.append("Verify that objects are of the expected types")
        
        # Get similar errors if available
        similar_errors = []
        try:
            from src.error_context import get_similar_errors
            similar_errors = get_similar_errors(error.error_code)
        except (ImportError, AttributeError):
            pass
        
        # Create response
        basic_result = {
            "error_code": getattr(error, 'error_code', "unknown"),
            "category": getattr(error, 'category', "UNKNOWN"),
            "message": getattr(error, 'message', str(error)),
            "suggestions": suggestions,
            "similar_errors_count": len(similar_errors)
        }
        
        return basic_result
    
    def _get_advanced_suggestions(self, error: EnhancedError) -> List[SuggestionEntry]:
        """
        Get advanced suggestions based on patterns and heuristics.
        
        Args:
            error: The error to get suggestions for
            
        Returns:
            List of suggestion entries
        """
        suggestions = []
        
        # Get category-specific patterns
        category_patterns = self.knowledge_base.get(error.category, [])
        
        # Get general patterns
        general_patterns = self.knowledge_base.get("GENERAL", [])
        
        # Combine patterns
        all_patterns = category_patterns + general_patterns
        
        # Check for matching patterns
        message = error.message
        for pattern in all_patterns:
            if pattern.matches(message):
                suggestions.extend(pattern.suggestions)
        
        # Apply heuristics based on error context
        context_suggestions = self._apply_error_heuristics(error)
        suggestions.extend(context_suggestions)
        
        return suggestions
    
    def _apply_error_heuristics(self, error: EnhancedError) -> List[SuggestionEntry]:
        """
        Apply heuristics to generate context-specific suggestions.
        
        Args:
            error: The error to analyze
            
        Returns:
            List of suggestion entries
        """
        suggestions = []
        
        # Check if we have state information
        if hasattr(error, 'state') and error.state:
            # Check for missing keys in state
            if isinstance(error.original_error, KeyError):
                missing_key = str(error.original_error).strip("'")
                similar_keys = []
                
                # Find similar keys
                if error.state:
                    all_keys = list(error.state.keys())
                    similar_keys = difflib.get_close_matches(missing_key, all_keys, n=3, cutoff=0.6)
                
                if similar_keys:
                    suggestions.append(SuggestionEntry(
                        suggestion=f"The key '{missing_key}' is missing. Did you mean one of these: {', '.join(similar_keys)}?",
                        confidence=0.9,
                        tags=["key-error", "similar-keys"]
                    ))
            
            # Check for state inconsistencies
            if hasattr(error, 'context') and error.context and 'trace_entry' in error.context:
                node_name = error.context['trace_entry'].get('node')
                if node_name:
                    suggestions.append(SuggestionEntry(
                        suggestion=f"Check the state passed to the '{node_name}' node for inconsistencies",
                        confidence=0.7,
                        tags=["state-validation", "node-specific"]
                    ))
        
        # Add suggestions based on error type
        if error.original_error:
            error_type = type(error.original_error).__name__
            if error_type in ["JSONDecodeError", "SyntaxError"]:
                suggestions.append(SuggestionEntry(
                    suggestion="Check if the JSON/text is properly formatted",
                    confidence=0.9,
                    tags=["format-error", "json"]
                ))
            elif error_type in ["ConnectionError", "TimeoutError"]:
                suggestions.append(SuggestionEntry(
                    suggestion="Check network connectivity and API endpoint availability",
                    confidence=0.9,
                    tags=["network", "api"]
                ))
                suggestions.append(SuggestionEntry(
                    suggestion="Implement retry logic with exponential backoff",
                    confidence=0.8,
                    example="from src.recovery import RecoveryPolicy, RecoveryMode\npolicy = RecoveryPolicy(mode=RecoveryMode.RETRY, max_retries=3, backoff_factor=1.5)",
                    tags=["network", "retry"]
                ))
        
        return suggestions
    
    def _rank_suggestions(self, suggestions: List[str], error: EnhancedError) -> List[str]:
        """
        Rank suggestions by relevance.
        
        Args:
            suggestions: List of suggestions
            error: The error to rank for
            
        Returns:
            Ranked list of suggestions
        """
        # Remove duplicates while preserving order
        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
        
        # TODO: Implement more sophisticated ranking based on feedback and relevance
        
        return unique_suggestions
    
    def _get_generic_suggestions(self) -> List[str]:
        """
        Get generic suggestions that apply to many errors.
        
        Returns:
            List of generic suggestions
        """
        return [
            "Check logs for additional context about the error",
            "Review recent changes that might have introduced the issue",
            "Ensure all required dependencies are installed and up-to-date",
            "Verify that API endpoints are accessible and returning expected formats",
            "Check if similar errors have occurred in the past and how they were resolved"
        ]
    
    def _get_documentation_for_error(self, error: EnhancedError) -> List[Dict[str, Any]]:
        """
        Get documentation references for an error.
        
        Args:
            error: The error to get documentation for
            
        Returns:
            List of documentation references
        """
        docs = []
        
        # Check category-specific documentation
        category_docs = [
            doc for doc_id, doc in self.documentation_index.items()
            if error.category.lower() in doc_id.lower() or 
               any(error.category.lower() in tag.lower() for tag in doc.tags)
        ]
        
        # Check for specific error pattern matches
        error_message = error.message.lower()
        pattern_docs = [
            doc for doc_id, doc in self.documentation_index.items()
            if any(pattern.lower() in error_message for pattern in doc.error_patterns)
        ]
        
        # Combine and deduplicate
        all_docs = category_docs + pattern_docs
        seen_ids = set()
        for doc in all_docs:
            doc_id = doc.title
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                docs.append({
                    "title": doc.title,
                    "path": doc.path,
                    "url": doc.url,
                    "description": doc.description
                })
        
        return docs
    
    def add_feedback(self, error_code: str, suggestion: str, helpful: bool) -> None:
        """
        Add user feedback for a suggestion.
        
        Args:
            error_code: The error code the suggestion was for
            suggestion: The suggestion text
            helpful: Whether the suggestion was helpful
        """
        # Add feedback
        self.feedback_data[error_code].append({
            "suggestion": suggestion,
            "helpful": helpful,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Save feedback data
        self.save_feedback_data()
        
        # TODO: Use feedback to update suggestion rankings

# Create global instance
_suggestions_engine = None

def get_suggestions_engine() -> SuggestionsEngine:
    """
    Get the global suggestions engine instance.
    
    Returns:
        The suggestions engine
    """
    global _suggestions_engine
    if _suggestions_engine is None:
        _suggestions_engine = SuggestionsEngine()
    
    return _suggestions_engine

def get_suggestions(error: Union[EnhancedError, str]) -> Dict[str, Any]:
    """
    Get suggestions for resolving an error.
    
    Args:
        error: The error to get suggestions for
        
    Returns:
        Dictionary with suggestions
    """
    engine = get_suggestions_engine()
    return engine.get_suggestions_for_error(error)

def submit_feedback(error_code: str, suggestion: str, helpful: bool) -> None:
    """
    Submit feedback on a suggestion.
    
    Args:
        error_code: The error code the suggestion was for
        suggestion: The suggestion text
        helpful: Whether the suggestion was helpful
    """
    engine = get_suggestions_engine()
    engine.add_feedback(error_code, suggestion, helpful)

def get_documentation_for_error(error: Union[EnhancedError, str]) -> List[Dict[str, Any]]:
    """
    Get documentation references for an error.
    
    Args:
        error: The error to get documentation for
        
    Returns:
        List of documentation references
    """
    if isinstance(error, str):
        # Try to find the error in registry
        from src.error_context import _error_registry
        for uid, err in _error_registry.items():
            if uid == error or err.error_code == error:
                error = err
                break
        
        # If still a string, return empty list
        if isinstance(error, str):
            return []
    
    engine = get_suggestions_engine()
    return engine._get_documentation_for_error(error) 