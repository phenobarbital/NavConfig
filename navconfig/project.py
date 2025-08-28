import sys
import os
import logging
from pathlib import Path, PurePath

class ProjectDetectionError(Exception):
    """Raised when project root cannot be properly detected."""
    pass

def get_environment() -> str:
    """Returns the environment selected."""
    return os.getenv("ENV", "")


def get_env_type() -> str:
    # environment type can be a file (.env) an encrypted file (crypt)
    return os.getenv("ENV_TYPE", "vault")


def is_virtualenv() -> bool:
    """Check if we're running inside a virtual environment."""
    return (
        os.getenv(
            "PYENV_VIRTUAL_ENV"
        ) or os.getenv(
            "VIRTUAL_ENV"
        ) or hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )
    )

def is_notebook() -> bool:
    """Check if we're running in a Jupyter notebook."""
    try:
        from IPython import get_ipython  # pylint: disable=import-outside-toplevel  # noqa
        return 'IPKernelApp' in get_ipython().config
    except (ImportError, AttributeError):
        return False

def find_project_root(
    base_file: str,
    markers=("etc/config.ini", ".env", "pyproject.toml", "setup.py", ".git")
) -> PurePath:
    """
    Find project root by looking for common project markers.

    Args:
        base_file: Starting file path for search
        markers: Tuple of file/directory names that indicate project root

    Returns:
        Path to project root

    Raises:
        ProjectDetectionError: If no project root can be found
    """
    current_dir = Path(base_file).resolve().parent
    # Check current directory first
    for marker in markers:
        if (current_dir / marker).exists():
            return current_dir

    # Then check parent directories
    for parent in current_dir.parents:
        for marker in markers:
            if (parent / marker).exists():
                return parent

    checked_dirs = [
        str(current_dir)
    ] + [str(p) for p in current_dir.parents[:5]]
    raise ProjectDetectionError(
        f"Could not find project root. Searched for markers {markers} in:\n"
        f"  {chr(10).join(checked_dirs)}\n"
        f"Please ensure you're running from within a project directory or set SITE_ROOT explicitly."  # noqa
    )

def validate_project_environment() -> tuple[str, list[str]]:
    """
    Validate the current environment setup and provide diagnostic information.

    Returns:
        Tuple of (status, warnings) where status is 'ok', 'warning', or 'error'
        and warnings is a list of diagnostic messages.
    """
    warnings = []
    status = 'ok'

    # Check virtual environment
    if not is_virtualenv():
        warnings.append(
            "No virtual environment detected. "
            "Consider using a virtual environment "
            "for better dependency isolation."
        )
        status = 'warning'

    # Check working directory
    cwd = Path.cwd()
    if cwd.name in ('site-packages', 'dist-packages'):
        warnings.append(
            f"Current working directory appears to be a Python package directory: {cwd}. "  # noqa
            f"This might indicate you're not running from your project root."
        )
        status = 'error'

    return status, warnings

def project_root(base_file: str) -> tuple[PurePath, PurePath]:
    """
    Determine project root and base directory with improved error handling.

    Args:
        base_file: File path to start search from (usually __file__)

    Returns:
        Tuple of (site_root, base_dir)

    Raises:
        ProjectDetectionError: If project structure cannot be determined
    """
    # First, validate the environment and log any warnings
    env_status, warnings = validate_project_environment()

    # Log warnings
    for warning in warnings:
        logging.warning(f"NavConfig: {warning}")

    site_root = os.getenv("SITE_ROOT", None)
    base_dir = os.getenv("BASE_DIR", None)

    if site_root is not None:
        site_root = Path(site_root).resolve()
        if not site_root.exists():
            raise ProjectDetectionError(
                f"SITE_ROOT points to non-existent directory: {site_root}"
            )
    elif is_virtualenv():
        site_root = Path(sys.prefix).resolve().parent
    else:
        try:
            site_root = find_project_root(base_file)
        except ProjectDetectionError as e:
            cwd = Path.cwd()
            base_file_path = Path(base_file).resolve()

            error_msg = (
                f"NavConfig could not determine project root:\n\n"
                f"Current working directory: {cwd}\n"
                f"NavConfig location: {base_file_path.parent}\n"
                f"Virtual environment: {'Yes' if is_virtualenv() else 'No'}\n\n"  # noqa
                f"To fix this issue, you can:\n"
                f"1. Set SITE_ROOT environment variable: export SITE_ROOT=/path/to/your/project\n"  # noqa
                f"2. Run from your project directory (containing pyproject.toml, setup.py, or .git)\n"  # noqa
                f"3. Activate a virtual environment in your project directory\n"  # noqa
                f"4. Create an 'etc' directory with config.ini in your project root\n\n"  # noqa
                f"Original error: {e}"
            )
            raise ProjectDetectionError(error_msg) from e

    base_dir = site_root if base_dir is None else Path(base_dir).resolve()

    return site_root, base_dir
