# Reflection Prompt Template

This document provides detailed documentation for the reflection prompt template used in the KFM (Knowledge Flow Management) system's LLM integration. This template is a critical component of the reflection mechanism, designed to elicit high-quality, structured reflections from Large Language Models (LLMs).

## Overview

The reflection prompt template is designed to:
1. Provide the LLM with sufficient context about KFM decisions
2. Structure the reflection request in a consistent format
3. Guide the LLM to produce structured, actionable responses
4. Ensure responses follow a standardized format for easier parsing

## Prompt Structure

The prompt template consists of five main sections:

### 1. KFM Agent Reflection Analysis (Header)

This is the main title of the prompt that sets the context for the LLM.

### 2. Context Section

```markdown
## Context
You are analyzing a Knowledge Flow Management (KFM) decision made by an AI agent. The agent follows a "Keep-Marry-Kill" framework for managing AI components:
- KEEP: Continue using the component as is
- MARRY: Enhance or integrate the component with others
- KILL: Remove or replace the component
```

This section explains the KFM framework to the LLM, ensuring it understands the specific domain terminology and decision types.

### 3. Decision Details Section

```markdown
## Decision Details
- KFM Action: {action_type.upper()}
- Component: '{component}'
- Reason Given: "{reason}"
- Active Component Used: '{active_component}'
- Performance Metrics:
  - Latency: {latency}
  - Accuracy: {accuracy}
- Execution Results: {result}
```

This section provides the specific details about the decision being reflected upon, including:
- The KFM action type (keep, marry, kill)
- The component involved
- The reason for the decision
- The component actually used in execution
- Performance metrics
- Execution results

All placeholders are dynamically populated from the current state.

### 4. Reflection Questions Section

```markdown
## Reflection Questions
1. Was the {action_type.upper()} decision appropriate given the performance metrics and context?
2. How effective was the execution of this decision using component '{active_component}'?
3. What were the specific strengths of this decision and execution?
4. What could be improved in future similar scenarios?
5. Are there any patterns or insights to be gained for future KFM decisions?
```

This section guides the LLM with specific questions to address in its reflection, ensuring comprehensive analysis.

### 5. Output Format Requirements Section

```markdown
## Output Format Requirements
Structure your response using these exact Markdown headings:
```
# Reflection on {action_type.title()} Decision for Component '{component}'

## Decision Analysis
[Your analysis of whether the decision was appropriate]

## Execution Assessment
[Your assessment of the execution effectiveness]
- Latency: {latency}
- Accuracy: {accuracy}

## Strengths
- [Specific strength 1]
- [Specific strength 2]
- [Specific strength 3]

## Areas for Improvement
- [Specific improvement 1]
- [Specific improvement 2]

## Patterns and Insights
[Analysis of patterns and insights]

## Recommendation
[Concrete recommendation for future actions]
```

This section provides a clear template for the LLM to structure its response, making it easier to parse and process the reflection programmatically.

### 6. Guidelines Section

```markdown
## Guidelines
- Be specific and objective in your analysis
- Base your assessment on the performance metrics and execution results
- Provide concrete, actionable recommendations
- Consider both short-term outcomes and long-term implications
- Keep your total response under 500 words
```

This section provides general guidance to the LLM about the style, approach, and constraints for the reflection.

## Implementation

The prompt template is implemented in the `get_reflection_prompt` function in `src/langgraph_nodes.py`:

```python
def get_reflection_prompt(state: KFMAgentState) -> str:
    """Generate a detailed reflection prompt based on the current state.
    
    Args:
        state (KFMAgentState): Current state containing KFM decision and execution data
        
    Returns:
        str: Formatted reflection prompt with clear structure and detailed instructions
    """
    # Implementation details...
```

This function is responsible for:
1. Extracting relevant information from the state
2. Formatting the prompt with the state information
3. Returning the complete formatted prompt as a string

## Customization Guide

When modifying the prompt template, developers should follow these guidelines:

### Handling New Action Types

If new KFM action types are added beyond keep, marry, and kill:
1. Update the Context section to include explanations of the new action types
2. Ensure the parsing logic in `extract_reflection_insights` and `analyze_reflection` functions understands the new action types

### Adding New Context Information

To add additional context information to the prompt:
1. Extract the new information from the state in the `get_reflection_prompt` function
2. Add the information to the Decision Details section with clear labeling
3. Update the corresponding tests to verify the new information is included

### Modifying Output Format

If changes to the output format are required:
1. Update the Output Format Requirements section with the new structure
2. Modify the `extract_reflection_insights` function to correctly parse the new format
3. Update relevant tests to verify both the new prompt format and correct parsing

### Token Optimization

To optimize token usage:
1. Consider removing any non-essential sections or instructions
2. Prioritize information that impacts decision quality
3. Monitor token usage after changes to ensure efficient operation

## Testing

The reflection prompt template is tested in multiple files:

1. `tests/test_reflection_prompt.py` - Verifies prompt structure and content
2. `tests/test_live_reflection.py` - Tests actual LLM interaction with the prompt

When modifying the prompt, ensure all tests continue to pass and add new tests for any new features or edge cases.

## Integration with LLM

The prompt template is used by the `call_llm_for_reflection` function, which:
1. Gets the formatted prompt using `get_reflection_prompt`
2. Calls the LLM (currently using Google Generative AI)
3. Returns the LLM's response for further processing

When integrating with different LLM providers, the prompt format should remain consistent, but you may need to adjust:
1. The prompt introduction to match the LLM's preferred interaction style
2. The output format requirements based on the LLM's capabilities
3. The token optimization strategy based on the LLM's pricing model

## Response Parsing

After receiving a response from the LLM, two main functions process it:

1. `extract_reflection_insights` - Extracts structured data from the reflection text
2. `analyze_reflection` - Determines if the decision was appropriate and effective

These functions rely on the specified output format, so any changes to the prompt's output requirements must be reflected in these parsing functions as well. 