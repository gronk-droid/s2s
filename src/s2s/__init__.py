"""
s2s (script2storyboard) - Convert video scripts to animation storyboards

A command-line tool for interactively converting video scripts into
animation storyboards with a beautiful terminal interface.
"""

__version__ = "0.1.0"

from .cli import main

__all__ = ["main"]
