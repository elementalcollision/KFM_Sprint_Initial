"""
Help System for KFM Debugging Tools

This module provides a help system with contextual help, searchable documentation, and tooltips
for the KFM debugging tools.
"""

import os
import json
import re
import importlib.resources
from typing import Dict, List, Optional, Union, Callable, Any


class HelpSystem:
    """
    Main help system class that provides access to documentation and contextual help
    for the KFM debugging tools.
    """

    def __init__(self, docs_path: Optional[str] = None):
        """
        Initialize the help system.

        Args:
            docs_path: Optional path to the documentation directory. If not provided,
                       the system will attempt to find the docs directory relative to
                       the package.
        """
        # Initialize documentation path
        self.docs_path = docs_path or self._find_docs_path()
        
        # Initialize help database
        self.help_database = self._load_help_database()
        
        # Initialize search index
        self.search_index = self._build_search_index()
        
        # Initialize tooltips
        self.tooltips = self._load_tooltips()

    def _find_docs_path(self) -> str:
        """Find the documentation directory path."""
        # Try to locate docs relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check potential locations
        potential_paths = [
            os.path.join(current_dir, '..', 'docs'),  # One level up
            os.path.join(current_dir, '..', '..', 'docs'),  # Two levels up
            os.path.join(current_dir, 'docs')  # Same directory
        ]
        
        for path in potential_paths:
            if os.path.isdir(path):
                return os.path.abspath(path)
        
        # Fallback to a default path if docs aren't found
        return os.path.join(current_dir, '..', 'docs')

    def _load_help_database(self) -> Dict[str, Any]:
        """
        Load and parse the help database from documentation files.
        
        Returns:
            A dictionary containing the help content organized by topic.
        """
        help_db = {
            "user_guides": {},
            "examples": {},
            "troubleshooting": {},
            "api": {},
            "error_docs": {}
        }
        
        # Load user guides
        user_guides_path = os.path.join(self.docs_path, 'user_guides')
        if os.path.isdir(user_guides_path):
            for filename in os.listdir(user_guides_path):
                if filename.endswith('.md'):
                    topic = filename[:-3]  # Remove .md extension
                    file_path = os.path.join(user_guides_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        help_db["user_guides"][topic] = self._parse_markdown(content)
        
        # Load examples
        examples_path = os.path.join(self.docs_path, 'examples')
        if os.path.isdir(examples_path):
            for filename in os.listdir(examples_path):
                if filename.endswith('.md'):
                    topic = filename[:-3]
                    file_path = os.path.join(examples_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        help_db["examples"][topic] = self._parse_markdown(content)
        
        # Load troubleshooting guides
        troubleshooting_path = os.path.join(self.docs_path, 'troubleshooting')
        if os.path.isdir(troubleshooting_path):
            for filename in os.listdir(troubleshooting_path):
                if filename.endswith('.md'):
                    topic = filename[:-3]
                    file_path = os.path.join(troubleshooting_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        help_db["troubleshooting"][topic] = self._parse_markdown(content)
        
        # Load API documentation
        api_path = os.path.join(self.docs_path, 'api')
        if os.path.isdir(api_path):
            for filename in os.listdir(api_path):
                if filename.endswith('.md'):
                    topic = filename[:-3]
                    file_path = os.path.join(api_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        help_db["api"][topic] = self._parse_markdown(content)
        
        # Load error docs
        error_docs_path = os.path.join(self.docs_path, 'error_docs')
        if os.path.isdir(error_docs_path):
            error_index_path = os.path.join(error_docs_path, 'index.json')
            if os.path.exists(error_index_path):
                with open(error_index_path, 'r', encoding='utf-8') as f:
                    error_index = json.load(f)
                    help_db["error_docs"]["index"] = error_index
            
            errors_path = os.path.join(error_docs_path, 'errors')
            if os.path.isdir(errors_path):
                for filename in os.listdir(errors_path):
                    if filename.endswith('.md'):
                        error_type = filename[:-3]
                        file_path = os.path.join(errors_path, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            help_db["error_docs"][error_type] = self._parse_markdown(content)
        
        return help_db

    def _parse_markdown(self, content: str) -> Dict[str, Any]:
        """
        Parse a markdown document into a structured format.
        
        Args:
            content: The markdown content to parse.
            
        Returns:
            A dictionary containing the parsed content.
        """
        # Extract title (first h1)
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled"
        
        # Extract sections (h2 headers)
        sections = {}
        section_pattern = r'^## (.+?)\n(.*?)(?=^## |\Z)'
        for match in re.finditer(section_pattern, content, re.MULTILINE | re.DOTALL):
            section_title = match.group(1).strip()
            section_content = match.group(2).strip()
            sections[section_title] = section_content
        
        # Extract code examples
        code_examples = []
        code_pattern = r'```(?:python)?\n(.*?)```'
        for match in re.finditer(code_pattern, content, re.DOTALL):
            code_examples.append(match.group(1).strip())
        
        return {
            "title": title,
            "sections": sections,
            "code_examples": code_examples,
            "full_content": content
        }

    def _build_search_index(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build a search index from the help database.
        
        Returns:
            A dictionary mapping search terms to relevant help entries.
        """
        search_index = {}
        
        # Process each category
        for category, topics in self.help_database.items():
            if category == "error_docs" and "index" in topics:
                # Skip the error index
                continue
                
            for topic_id, content in topics.items():
                # Skip non-dictionary content
                if not isinstance(content, dict):
                    continue
                    
                # Get title and content text
                title = content.get("title", "")
                full_content = content.get("full_content", "")
                
                # Extract keywords (lowercase words at least 3 chars long)
                words = re.findall(r'\b[a-zA-Z]{3,}\b', full_content.lower())
                
                # Add to search index
                for word in set(words):
                    if word not in search_index:
                        search_index[word] = []
                    
                    # Check if this topic is already indexed for this word
                    if not any(item["category"] == category and item["topic"] == topic_id 
                              for item in search_index[word]):
                        search_index[word].append({
                            "category": category,
                            "topic": topic_id,
                            "title": title,
                            "relevance": 1  # Base relevance score
                        })
        
        return search_index

    def _load_tooltips(self) -> Dict[str, str]:
        """
        Load tooltips for UI elements.
        
        Returns:
            A dictionary mapping tooltip IDs to tooltip text.
        """
        tooltips_file = os.path.join(self.docs_path, 'tooltips.json')
        
        if os.path.exists(tooltips_file):
            with open(tooltips_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Default tooltips if file not found
        return {
            "debugger_run": "Run the graph with debugging enabled",
            "enable_logging": "Enable enhanced logging",
            "enable_breakpoints": "Enable breakpoints to pause execution",
            "enable_profiling": "Enable performance profiling",
            "show_state_diff": "Show differences between states",
            "visualize_graph": "Visualize the graph structure",
            "show_execution_path": "Show the execution path through the graph"
        }

    def get_help(self, topic: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get help for a specific topic.
        
        Args:
            topic: The topic to get help for.
            category: Optional category to narrow the search.
            
        Returns:
            A dictionary containing the help content, or None if not found.
        """
        if category:
            if category in self.help_database and topic in self.help_database[category]:
                return self.help_database[category][topic]
            return None
        
        # Search across all categories if no category specified
        for cat, topics in self.help_database.items():
            if topic in topics:
                return topics[topic]
        
        return None

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for help topics matching the query.
        
        Args:
            query: The search query.
            max_results: Maximum number of results to return.
            
        Returns:
            A list of matching help entries, sorted by relevance.
        """
        results = []
        query_words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        
        # Track relevance scores for each result
        relevance_scores = {}
        
        # Process each query word
        for word in query_words:
            if word in self.search_index:
                for item in self.search_index[word]:
                    key = f"{item['category']}:{item['topic']}"
                    
                    # Initialize or update relevance score
                    if key not in relevance_scores:
                        relevance_scores[key] = {
                            "category": item["category"],
                            "topic": item["topic"],
                            "title": item["title"],
                            "score": 0
                        }
                    
                    # Increase score for this match
                    relevance_scores[key]["score"] += item["relevance"]
        
        # Convert to list and sort by relevance
        results = list(relevance_scores.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top results
        return results[:max_results]

    def get_contextual_help(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get contextual help based on the current context.
        
        Args:
            context: A dictionary containing context information.
            
        Returns:
            A dictionary containing relevant help content.
        """
        help_results = {
            "primary_topic": None,
            "related_topics": [],
            "suggested_actions": []
        }
        
        # Extract context features
        current_node = context.get("current_node")
        error_type = context.get("error_type")
        action = context.get("action")
        feature = context.get("feature")
        
        # Handle error context
        if error_type:
            error_help = self.get_help(error_type, "error_docs")
            if error_help:
                help_results["primary_topic"] = {
                    "category": "error_docs",
                    "topic": error_type,
                    "content": error_help
                }
                help_results["suggested_actions"].append({
                    "action": "view_error_docs",
                    "description": f"View documentation for {error_type} errors"
                })
        
        # Handle feature context
        elif feature:
            feature_help = self.get_help(feature, "user_guides")
            if feature_help:
                help_results["primary_topic"] = {
                    "category": "user_guides",
                    "topic": feature,
                    "content": feature_help
                }
                
                # Add related examples
                related_examples = self.search(feature, max_results=3)
                for example in related_examples:
                    if example["category"] == "examples":
                        help_results["related_topics"].append({
                            "category": "examples",
                            "topic": example["topic"],
                            "title": example["title"]
                        })
        
        # Handle action context
        elif action:
            # Search for action-related help
            action_results = self.search(action, max_results=5)
            if action_results:
                primary = action_results[0]
                help_content = self.get_help(primary["topic"], primary["category"])
                help_results["primary_topic"] = {
                    "category": primary["category"],
                    "topic": primary["topic"],
                    "content": help_content
                }
                
                # Add other results as related topics
                for result in action_results[1:]:
                    help_results["related_topics"].append({
                        "category": result["category"],
                        "topic": result["topic"],
                        "title": result["title"]
                    })
        
        # Default to general help if no specific context
        if not help_results["primary_topic"]:
            getting_started = self.get_help("getting_started", "user_guides")
            if getting_started:
                help_results["primary_topic"] = {
                    "category": "user_guides",
                    "topic": "getting_started",
                    "content": getting_started
                }
        
        # Always add some suggested actions
        help_results["suggested_actions"].extend([
            {
                "action": "search_docs",
                "description": "Search documentation"
            },
            {
                "action": "view_examples",
                "description": "Browse examples"
            }
        ])
        
        return help_results

    def get_tooltip(self, tooltip_id: str) -> Optional[str]:
        """
        Get a tooltip by ID.
        
        Args:
            tooltip_id: The ID of the tooltip to retrieve.
            
        Returns:
            The tooltip text, or None if not found.
        """
        return self.tooltips.get(tooltip_id)

    def get_error_help(self, error_type: str) -> Optional[Dict[str, Any]]:
        """
        Get help for a specific error type.
        
        Args:
            error_type: The type of error to get help for.
            
        Returns:
            A dictionary containing the error help content, or None if not found.
        """
        return self.get_help(error_type, "error_docs")


class HelpRenderer:
    """
    Helper class for rendering help content in different formats.
    """
    
    @staticmethod
    def render_text(help_content: Dict[str, Any]) -> str:
        """
        Render help content as plain text.
        
        Args:
            help_content: The help content to render.
            
        Returns:
            The rendered text.
        """
        if not help_content:
            return "No help content available."
        
        title = help_content.get("title", "Untitled")
        sections = help_content.get("sections", {})
        
        # Build the text output
        output = [f"{title}\n{'=' * len(title)}\n"]
        
        # Add sections
        for section_title, section_content in sections.items():
            output.append(f"\n{section_title}\n{'-' * len(section_title)}\n")
            output.append(section_content)
        
        return "\n".join(output)

    @staticmethod
    def render_markdown(help_content: Dict[str, Any]) -> str:
        """
        Render help content as markdown.
        
        Args:
            help_content: The help content to render.
            
        Returns:
            The rendered markdown.
        """
        if not help_content:
            return "No help content available."
        
        # Just return the full content if available
        if "full_content" in help_content:
            return help_content["full_content"]
        
        # Otherwise, rebuild from parts
        title = help_content.get("title", "Untitled")
        sections = help_content.get("sections", {})
        
        # Build the markdown output
        output = [f"# {title}\n"]
        
        # Add sections
        for section_title, section_content in sections.items():
            output.append(f"\n## {section_title}\n")
            output.append(section_content)
        
        return "\n".join(output)

    @staticmethod
    def render_html(help_content: Dict[str, Any]) -> str:
        """
        Render help content as HTML.
        
        Args:
            help_content: The help content to render.
            
        Returns:
            The rendered HTML.
        """
        if not help_content:
            return "<p>No help content available.</p>"
        
        # Convert markdown to HTML
        try:
            import markdown
            md = markdown.Markdown(extensions=['tables', 'fenced_code', 'codehilite'])
            return md.convert(HelpRenderer.render_markdown(help_content))
        except ImportError:
            # Fallback to basic HTML if markdown package is not available
            title = help_content.get("title", "Untitled")
            sections = help_content.get("sections", {})
            
            # Build the HTML output
            output = [f"<h1>{title}</h1>"]
            
            # Add sections
            for section_title, section_content in sections.items():
                output.append(f"<h2>{section_title}</h2>")
                # Very basic markdown-to-HTML conversion
                paragraphs = section_content.split("\n\n")
                for p in paragraphs:
                    output.append(f"<p>{p}</p>")
            
            return "\n".join(output)


class HelpCommand:
    """
    Command-line interface for the help system.
    """
    
    def __init__(self, help_system: HelpSystem):
        """
        Initialize the help command.
        
        Args:
            help_system: The help system to use.
        """
        self.help_system = help_system
    
    def execute(self, args: List[str]) -> str:
        """
        Execute the help command with the given arguments.
        
        Args:
            args: Command-line arguments.
            
        Returns:
            The command output.
        """
        if not args:
            return self._show_help_overview()
        
        command = args[0].lower()
        
        if command == "search" and len(args) > 1:
            # Help search <query>
            query = " ".join(args[1:])
            return self._search_help(query)
        
        elif command == "topic" and len(args) > 1:
            # Help topic <topic> [category]
            topic = args[1]
            category = args[2] if len(args) > 2 else None
            return self._show_topic(topic, category)
        
        elif command == "error" and len(args) > 1:
            # Help error <error_type>
            error_type = args[1]
            return self._show_error_help(error_type)
        
        elif command == "tooltip" and len(args) > 1:
            # Help tooltip <tooltip_id>
            tooltip_id = args[1]
            return self._show_tooltip(tooltip_id)
        
        elif command == "list":
            # Help list [category]
            category = args[1] if len(args) > 1 else None
            return self._list_topics(category)
        
        else:
            # Treat as a topic
            topic = args[0]
            return self._show_topic(topic)
    
    def _show_help_overview(self) -> str:
        """Show an overview of available help commands."""
        return """
Help System Commands:

  help search <query>         Search for help topics
  help topic <topic> [category]  Show help for a specific topic
  help error <error_type>     Show help for a specific error
  help tooltip <tooltip_id>   Show a tooltip
  help list [category]        List available topics
  
Categories:
  user_guides                 User guides for features
  examples                    Example code and tutorials
  troubleshooting             Troubleshooting guides
  api                         API documentation
        """
    
    def _search_help(self, query: str) -> str:
        """Search for help topics."""
        results = self.help_system.search(query)
        
        if not results:
            return f"No results found for '{query}'."
        
        output = [f"Search results for '{query}':\n"]
        
        for i, result in enumerate(results, 1):
            category = result["category"]
            topic = result["topic"]
            title = result["title"]
            output.append(f"{i}. {category}/{topic}: {title}")
        
        output.append("\nUse 'help topic <topic> <category>' to view a topic.")
        return "\n".join(output)
    
    def _show_topic(self, topic: str, category: Optional[str] = None) -> str:
        """Show help for a specific topic."""
        help_content = self.help_system.get_help(topic, category)
        
        if not help_content:
            if category:
                return f"Topic '{topic}' not found in category '{category}'."
            else:
                return f"Topic '{topic}' not found."
        
        return HelpRenderer.render_text(help_content)
    
    def _show_error_help(self, error_type: str) -> str:
        """Show help for a specific error."""
        error_help = self.help_system.get_error_help(error_type)
        
        if not error_help:
            return f"No help found for error type '{error_type}'."
        
        return HelpRenderer.render_text(error_help)
    
    def _show_tooltip(self, tooltip_id: str) -> str:
        """Show a tooltip."""
        tooltip = self.help_system.get_tooltip(tooltip_id)
        
        if not tooltip:
            return f"Tooltip '{tooltip_id}' not found."
        
        return f"Tooltip '{tooltip_id}': {tooltip}"
    
    def _list_topics(self, category: Optional[str] = None) -> str:
        """List available topics."""
        if category:
            if category not in self.help_system.help_database:
                return f"Category '{category}' not found."
            
            topics = self.help_system.help_database[category]
            output = [f"Topics in category '{category}':\n"]
            
            for topic_id, content in topics.items():
                # Skip non-dictionary content
                if not isinstance(content, dict):
                    continue
                    
                title = content.get("title", topic_id)
                output.append(f"- {topic_id}: {title}")
            
            return "\n".join(output)
        
        # List categories
        output = ["Available categories:\n"]
        
        for category, topics in self.help_system.help_database.items():
            topic_count = sum(1 for t in topics.values() if isinstance(t, dict))
            output.append(f"- {category}: {topic_count} topics")
        
        output.append("\nUse 'help list <category>' to list topics in a category.")
        return "\n".join(output)


# Initialize the help system
help_system = HelpSystem()

# Function to get help
def get_help(topic: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get help for a specific topic.
    
    Args:
        topic: The topic to get help for.
        category: Optional category to narrow the search.
        
    Returns:
        A dictionary containing the help content, or None if not found.
    """
    return help_system.get_help(topic, category)

# Function to search help
def search_help(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search for help topics matching the query.
    
    Args:
        query: The search query.
        max_results: Maximum number of results to return.
        
    Returns:
        A list of matching help entries, sorted by relevance.
    """
    return help_system.search(query, max_results)

# Function to get contextual help
def get_contextual_help(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get contextual help based on the current context.
    
    Args:
        context: A dictionary containing context information.
        
    Returns:
        A dictionary containing relevant help content.
    """
    return help_system.get_contextual_help(context)

# Function to get a tooltip
def get_tooltip(tooltip_id: str) -> Optional[str]:
    """
    Get a tooltip by ID.
    
    Args:
        tooltip_id: The ID of the tooltip to retrieve.
        
    Returns:
        The tooltip text, or None if not found.
    """
    return help_system.get_tooltip(tooltip_id)

# Function to get error help
def get_error_help(error_type: str) -> Optional[Dict[str, Any]]:
    """
    Get help for a specific error type.
    
    Args:
        error_type: The type of error to get help for.
        
    Returns:
        A dictionary containing the error help content, or None if not found.
    """
    return help_system.get_error_help(error_type)

# Function to render help content
def render_help(help_content: Dict[str, Any], format: str = "text") -> str:
    """
    Render help content in the specified format.
    
    Args:
        help_content: The help content to render.
        format: The format to render in ('text', 'markdown', or 'html').
        
    Returns:
        The rendered help content.
    """
    if format == "markdown":
        return HelpRenderer.render_markdown(help_content)
    elif format == "html":
        return HelpRenderer.render_html(help_content)
    else:
        return HelpRenderer.render_text(help_content)

# Command-line help handler
def handle_help_command(args: List[str]) -> str:
    """
    Handle a help command.
    
    Args:
        args: Command-line arguments.
        
    Returns:
        The command output.
    """
    help_command = HelpCommand(help_system)
    return help_command.execute(args)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        result = handle_help_command(sys.argv[1:])
        print(result)
    else:
        print(handle_help_command([])) 