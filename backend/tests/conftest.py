"""Ensure `backend/` (the package root for `scoring` and `app`) is importable
regardless of the working directory pytest is invoked from."""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
