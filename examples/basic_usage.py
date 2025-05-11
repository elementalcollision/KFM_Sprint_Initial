import sys
import os

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.factory import create_kfm_agent

def main():
    # Create the KFM agent components
    registry, monitor, planner, engine = create_kfm_agent()
    
    # Example task input
    input_data = {'text': 'This is a sample text to analyze'}
    
    # Get task requirements
    task_name = 'default'
    requirements = monitor.get_task_requirements(task_name)
    print(f"Task requirements: {requirements}")
    
    # Make KFM decision
    action = planner.decide_kfm_action(task_name)
    print(f"KFM decision: {action}")
    
    # Apply the action
    if action:
        engine.apply_kfm_action(action)
    
    # Execute the task
    result, performance = engine.execute_task(input_data)
    print(f"Result: {result}")
    print(f"Performance: {performance}")

if __name__ == '__main__':
    main() 