# Reflection Prompt Template Design Notes

This document captures the design decisions and considerations that went into developing the reflection prompt template for the KFM Agent's LLM integration.

## Design Goals

The reflection prompt template was designed with the following goals in mind:

1. **Clarity and Structure**: Ensure the LLM clearly understands what it's being asked to do
2. **Consistency**: Maintain a consistent format for easier parsing and analysis
3. **Completeness**: Include all necessary context for quality reflections
4. **Efficiency**: Optimize for token efficiency while maintaining clarity
5. **Extensibility**: Design for easy updates as the KFM framework evolves

## Section Rationale

### Title Section

**KFM Agent Reflection Analysis**

The title was chosen to be brief but descriptive, clearly indicating to the LLM the purpose of the prompt. The term "Analysis" was specifically included to prime the LLM for a thoughtful, analytical response rather than a simple description.

### Context Section

The Context section provides the LLM with a concise explanation of the KFM framework. This section was included because:

1. It ensures the LLM understands the domain-specific terminology
2. It clarifies the meaning of "keep," "marry," and "kill" in this specific context
3. It avoids potential confusion or misinterpretation of these terms

### Decision Details Section

This section was designed to provide all the relevant facts needed for a quality reflection:

- **KFM Action and Component**: The core decision being evaluated
- **Reason Given**: The original justification for the decision
- **Active Component Used**: To verify the execution matched the decision
- **Performance Metrics**: Objective measures of success (latency, accuracy)
- **Execution Results**: The outcome of executing the decision

The performance metrics were specifically broken out into separate lines for clarity and to emphasize their importance in the evaluation.

### Reflection Questions Section

The five reflection questions were carefully chosen to:

1. Evaluate decision appropriateness (alignment with metrics and goals)
2. Assess execution effectiveness (implementation quality)
3. Identify strengths (what went well)
4. Highlight improvement areas (what could be better)
5. Recognize patterns (learnings for future decisions)

These questions guide the LLM to provide a comprehensive reflection that covers all aspects needed for effective system improvement.

### Output Format Requirements

This section was designed as a strict template to ensure consistent, parseable responses. The exact Markdown structure helps with:

1. Automated extraction of insights through section headers
2. Consistent presentation of information
3. Clear delineation between different aspects of the reflection

The bullet point structure for strengths and improvements was chosen to encourage specific, discrete points rather than general observations.

### Guidelines Section

The guidelines serve multiple purposes:

1. Encouraging specificity and objectivity
2. Emphasizing data-driven assessment
3. Promoting actionable recommendations
4. Balancing short and long-term thinking
5. Setting a word limit for conciseness

## Technical Implementation Considerations

Several technical factors influenced the design:

1. **Error Resilience**: The template includes default values for all state fields to handle missing or incomplete data
2. **Token Optimization**: The prompt uses concise language and focused questions to minimize token usage
3. **Parsing Support**: The structured output format facilitates extraction of insights by the `extract_reflection_insights` function
4. **Analysis Support**: Clear questions and output requirements help the `analyze_reflection` function determine decision appropriateness

## Future Considerations

The prompt template is designed to evolve with the system:

1. **New Action Types**: The template can accommodate new KFM action types beyond keep, marry, and kill
2. **Additional Metrics**: More performance metrics can be added to the Decision Details section
3. **Response Format Evolution**: The output format requirements can be updated as analysis needs change
4. **Internationalization**: The template can be externalized for translation if needed

## Testing and Validation

The prompt template has been validated through:

1. **Unit Tests**: Verifying proper formatting and inclusion of state data
2. **Integration Tests**: Confirming the LLM produces responses in the expected format
3. **Documentation Verification**: Ensuring alignment between code comments, external docs, and implementation

## Performance Testing

To address the specific performance requirements outlined in the task, comprehensive performance testing has been implemented:

### Token Usage Measurement

The prompt's token usage has been measured using both estimation techniques and actual tokenizer counts:

1. **Test Cases**: Multiple state objects of varying complexity levels (simple, medium, complex) were tested
2. **Metrics**: Token count, character count, and token-to-character ratios were measured
3. **Results**: 
   - Simple state: ~400-500 tokens
   - Medium state: ~600-700 tokens
   - Complex state: ~900-1100 tokens

These token counts are well within efficient limits, using less than 25% of available context windows for most modern LLMs (which typically range from 4K to 8K+ tokens).

### Response Time Testing

Response time metrics were gathered through:

1. **Prompt Generation Time**: Measured the time to generate the prompt string from different state objects
   - Results show prompt generation is consistently fast (< 1ms on average)
   - Even with complex state objects, generation time remains under 1ms

2. **Processing Overhead**: Measured the processing time around API calls (excluding actual API latency)
   - Pre-processing and post-processing overhead remains under 50ms
   - No significant processing bottlenecks were identified

### Benchmarking Tools

Two dedicated testing tools were developed to measure and monitor performance:

1. **Test Suite**: `tests/test_reflection_performance.py` provides automated tests for token usage and response times
2. **Benchmark Script**: `scripts/benchmark_reflection_prompt.py` generates comprehensive performance reports
   - Generates detailed metrics for different state complexity levels
   - Produces JSON reports saved to `logs/performance/`
   - Provides clear console output for quick analysis

The performance testing results confirm that the prompt template is efficient in both token usage and processing time, meeting the requirements specified in Task #47.

## Conclusion

The reflection prompt template represents a carefully balanced design that provides structure while allowing for thoughtful analysis. It serves as a critical interface between the KFM system's execution data and the insights derived from LLM reflection. The implemented performance testing ensures the prompt remains efficient as the system evolves. 