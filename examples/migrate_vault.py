import sys
from pathlib import Path
from navconfig import config


def process_config_file(file_path):
    # Check if the file exists
    if not Path(file_path).is_file():
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r') as file:
        for line in file:
            # Strip whitespace from the beginning and end of the line
            line = line.strip()

            # Skip blank lines and lines that start with '['
            if not line or line.startswith('['):
                continue

            # Split the line into key and value at the first '='
            parts = line.split('=', 1)
            if len(parts) == 2:
                key, value = parts
                key = key.strip()
                value = value.strip()
                vault = config.source('vault')
                if vault:
                    try:
                        vault.set(key, value)
                        print(f"Saved Key: {key}, Value: {value}")
                    except Exception as e:
                        print(
                            f"Error saving Key: {key}={value} on Vault: {e}"
                        )

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_config_file>")
        sys.exit(1)

    config_file_path = sys.argv[1]
    process_config_file(config_file_path)
