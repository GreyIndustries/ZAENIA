from pathlib import Path
import os

# Base directory for the entire project
BASE_DIR = Path(__file__).resolve().parent.parent

def get_path(*parts):
    """Builds a cross-platform file path safely."""
    return os.path.join(BASE_DIR, *parts)
