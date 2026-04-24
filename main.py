#!/usr/bin/env python3
"""
Entry point for the notification template API server.

This file is executed by the test runner as: python main.py
It starts the standalone templates server on port 6185.
"""
import os
import sys

# Ensure our repo directory is on the path
_repo_dir = os.path.dirname(os.path.abspath(__file__))
if _repo_dir not in sys.path:
    sys.path.insert(0, _repo_dir)

# Run the standalone templates server
import templates_server
templates_server.main()
