import sys
from pathlib import Path


def ensure_settings_priority(settings_dir: Path) -> bool:
    """
    Ensure that the settings directory is at the beginning of sys.path.

    Args:
        settings_dir (Path): Path to the project's settings directory
    """
    # Check if the settings directory exists
    if not settings_dir.exists():
        return False

    settings_path = str(settings_dir)

    # Remove project settings path from sys.path if it's already there
    if settings_path in sys.path:
        sys.path.remove(settings_path)

    # Add project settings Path
    sys.path.append(settings_path)

    # Also check for conflicts and silently adjust sys.path:
    has_conflict, _conflict_path = check_settings_conflicts(settings_dir)
    if has_conflict:
        # Silently adjust sys.path to prioritize the project's settings.
        # Insert at position 0 so the project settings take precedence.
        if settings_path in sys.path:
            sys.path.remove(settings_path)
        sys.path.insert(0, settings_path)

    return True

def check_settings_conflicts(settings_dir: Path) -> tuple:
    """Check for conflicts with other settings modules in sys.path.

    Args:
        settings_dir (Path): Path to the project's settings directory.

    Returns:
        tuple: (has_conflict, conflicting_path)
    """
    # Check if there are other settings modules in sys.path that might conflict
    settings_dir = settings_dir.resolve()  # Resolve to absolute path

    for path in sys.path:
        path_obj = Path(path).resolve()  # Resolve to absolute path

        # Skip if this is the project's settings directory we just added
        if path_obj == settings_dir:
            continue

        # Check for a settings package in this path
        if path_obj.name == "settings" and path_obj.is_dir() and (path_obj / "__init__.py").exists():
            return True, str(path_obj)

        # Check for settings package as a subdirectory
        settings_subdir = path_obj / "settings"
        if settings_subdir.exists() and settings_subdir != settings_dir and settings_subdir.is_dir() and (settings_subdir / "__init__.py").exists():
            return True, str(settings_subdir)

        # Check for settings.py file directly in the path
        settings_file = path_obj / "settings.py"
        if settings_file.exists() and settings_file.parent != settings_dir:
            return True, str(settings_file)

    return False, None
