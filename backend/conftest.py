"""Top-level pytest config — makes `backend/` importable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
