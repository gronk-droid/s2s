#!/usr/bin/env python3
"""
Backwards compatibility wrapper for s2s

This file provides backwards compatibility for scripts that import or run s2s.py directly.
The main code has moved to src/s2s/
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from s2s.cli import main

if __name__ == "__main__":
    main()
