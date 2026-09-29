"""Sample configuration files for bootstrapping NavConfig projects."""
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent


def get_sample_path(name: str) -> Path:
    """Return the absolute path to a sample file by name."""
    path = SAMPLES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Sample file not found: {name}")
    return path
