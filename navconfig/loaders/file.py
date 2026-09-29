import logging
from pathlib import PurePath
from .abstract import BaseLoader


def sort_key(path):
    name = path.name
    return "0" if name == ".env" else name


class fileLoader(BaseLoader):
    """fileLoader.

    Use to read configuration settings from .env Files.

    Loads one or multiple .env files from a directory to separate variables.
    Files are loaded in the order they are found, with later files overriding earlier ones.


    """  # noqa: E501

    # Define the order in which files should be loaded
    DEFAULT_ENV_FILES = [
        ".env",            # Base configuration
        ".env.resources",  # Resource configurations
        ".env.databases",  # Database credentials
        ".env.api",        # API keys and endpoints
        ".env.secrets",    # Sensitive data
        ".env.local"       # Local overrides (loaded last)
    ]

    def __init__(
        self,
        env_path: PurePath,
        override: bool = False,
        create: bool = True,
        file_patterns: list[str] = None,
        auto: bool = False,
        **kwargs
    ) -> None:
        super().__init__(env_path, override, create=create, **kwargs)
        # Allow custom file patterns or use defaults
        if auto:
            if env_files := list(self.env_path.glob(".env*")):
                env_files.sort(key=sort_key)
                self.file_patterns = [file.name for file in env_files]
            else:
                self.file_patterns = self.DEFAULT_ENV_FILES
        else:
            self.file_patterns = file_patterns or self.DEFAULT_ENV_FILES

        # Track which files were actually loaded
        self.loaded_files = []

    def load_environment(self):
        """Load multiple .env files in the specified order."""
        loaded_count = 0
        for file_pattern in self.file_patterns:
            file_path = self.env_path.joinpath(file_pattern)
            if file_path.exists() and file_path.is_file():
                try:
                    if file_path.stat().st_size == 0:
                        logging.warning(f"Empty environment file: {file_path}")
                        continue
                    self.load_from_file(file_path)
                    self.loaded_files.append(file_path)
                    loaded_count += 1
                except Exception as e:
                    logging.warning(
                        f"Error loading env file {file_path}: {e}"
                    )
        if loaded_count == 0:
            raise FileNotFoundError(
                f"No environment files found in {self.env_path}. "
                f"Looking for: {', '.join(self.file_patterns)}"
            )

    def save_environment(self):
        raise NotImplementedError

    def get_loaded_files(self):
        """Return list of successfully loaded files."""
        return self.loaded_files
