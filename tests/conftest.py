"""Pytest configuration — add scripts/ to sys.path so tests can import them."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
