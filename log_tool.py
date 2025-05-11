#!/usr/bin/env python3
"""
Runner script for KFM logging and visualization tools.

Usage:
  python log_tool.py [command] [options]

Commands:
  analyze   - Analyze log files and generate reports
  visualize - Visualize execution data
  monitor   - Monitor log files in real-time
  summary   - Generate a summary of execution logs

For more information, run:
  python log_tool.py --help
"""

import sys
from src.cli.log_tools import main

if __name__ == "__main__":
    sys.exit(main()) 