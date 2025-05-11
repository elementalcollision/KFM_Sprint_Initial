import time

def analyze_fast(input_data):
    """A fast but less accurate analysis component.
    
    Args:
        input_data (dict): The input data to analyze
        
    Returns:
        dict: Analysis results
    """
    # Simulate fast processing
    time.sleep(0.1)  # Simulate processing time
    
    return {
        'result': f"Fast analysis of {input_data.get('text', '')}[:10]...",
        'confidence': 0.7
    }

def analyze_accurate(input_data):
    """A more accurate but slower analysis component.
    
    Args:
        input_data (dict): The input data to analyze
        
    Returns:
        dict: Analysis results
    """
    # Simulate slower processing
    time.sleep(0.5)  # Simulate processing time
    
    return {
        'result': f"Detailed analysis of {input_data.get('text', '')}",
        'confidence': 0.95
    }

def analyze_balanced(input_data):
    """A balanced analysis component with moderate speed and accuracy.
    
    Args:
        input_data (dict): The input data to analyze
        
    Returns:
        dict: Analysis results
    """
    # Simulate moderate processing
    time.sleep(0.3)  # Simulate processing time
    
    return {
        'result': f"Balanced analysis of {input_data.get('text', '')}",
        'confidence': 0.85
    } 