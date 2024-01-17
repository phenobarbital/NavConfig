from .abstract import BaseLoader


class fileLoader(BaseLoader):
    """fileLoader.

    Use to read configuration settings from .env Files.
    """

    def load_environment(self):
        file_path = self.env_path.joinpath(self.env_file)
        if file_path.exists():
            if file_path.stat().st_size == 0:
                raise FileExistsError(f"Empty Environment File: {file_path}")
            # load dotenv from file:
            self.load_from_file(file_path)
        else:
            raise FileNotFoundError(f"Environment file not found: {file_path}")

    def save_environment(self):
        raise NotImplementedError
