import pytest
import time
from src.core.components import analyze_fast, analyze_accurate, analyze_balanced


@pytest.fixture
def sample_input():
    return {'text': 'Sample text for testing'}


def test_analyze_fast_output_structure(sample_input):
    result = analyze_fast(sample_input)
    assert 'result' in result
    assert 'confidence' in result
    assert isinstance(result['result'], str)
    assert isinstance(result['confidence'], float)
    assert result['confidence'] == 0.7


def test_analyze_accurate_output_structure(sample_input):
    result = analyze_accurate(sample_input)
    assert 'result' in result
    assert 'confidence' in result
    assert isinstance(result['result'], str)
    assert isinstance(result['confidence'], float)
    assert result['confidence'] == 0.95


def test_analyze_balanced_output_structure(sample_input):
    result = analyze_balanced(sample_input)
    assert 'result' in result
    assert 'confidence' in result
    assert isinstance(result['result'], str)
    assert isinstance(result['confidence'], float)
    assert result['confidence'] == 0.85


def test_analyze_fast_performance(sample_input):
    start_time = time.time()
    analyze_fast(sample_input)
    duration = time.time() - start_time
    # Expecting ~0.1s sleep + overhead
    assert 0.1 <= duration < 0.2, f"Expected ~0.1s, took {duration:.4f}s"


def test_analyze_accurate_performance(sample_input):
    start_time = time.time()
    analyze_accurate(sample_input)
    duration = time.time() - start_time
    # Expecting ~0.5s sleep + overhead
    assert 0.5 <= duration < 0.6, f"Expected ~0.5s, took {duration:.4f}s"


def test_analyze_balanced_performance(sample_input):
    start_time = time.time()
    analyze_balanced(sample_input)
    duration = time.time() - start_time
    # Expecting ~0.3s sleep + overhead
    assert 0.3 <= duration < 0.4, f"Expected ~0.3s, took {duration:.4f}s"


def test_empty_input_handling():
    empty_input = {}
    # Should not raise exceptions and should handle missing 'text' key gracefully
    result_fast = analyze_fast(empty_input)
    result_accurate = analyze_accurate(empty_input)
    result_balanced = analyze_balanced(empty_input)
    
    assert 'result' in result_fast
    assert 'confidence' in result_fast
    assert 'result' in result_accurate
    assert 'confidence' in result_accurate
    assert 'result' in result_balanced
    assert 'confidence' in result_balanced

def test_input_with_no_text_key():
    input_no_text = {'other_key': 'value'}
    # Should not raise exceptions and should handle missing 'text' key gracefully
    result_fast = analyze_fast(input_no_text)
    result_accurate = analyze_accurate(input_no_text)
    result_balanced = analyze_balanced(input_no_text)
    
    assert 'result' in result_fast
    assert 'confidence' in result_fast
    assert 'Fast analysis of ' in result_fast['result'] # Checks default value used
    assert 'result' in result_accurate
    assert 'confidence' in result_accurate
    assert 'Detailed analysis of ' in result_accurate['result']
    assert 'result' in result_balanced
    assert 'confidence' in result_balanced
    assert 'Balanced analysis of ' in result_balanced['result'] 