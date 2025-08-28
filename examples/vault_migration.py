#!/usr/bin/env python3
"""
Migrate .env file to HashiCorp Vault

This script migrates environment variables from a .env file to HashiCorp Vault
using the KV secrets engine v2 format.

Usage:
    python vault_migration.py --vault_url https://127.0.0.1:8200 --vault_token hvs.xxx --vault_mountpoint navapi --env dev [.env file]
"""

import os
import sys
import json
import requests
import urllib3
import argparse
from pathlib import Path
from typing import Dict, Optional
import re

# Disable SSL warnings for development (remove in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def parse_env_file(file_path: Path) -> Dict[str, str]:
    """
    Parse .env file manually to handle various formats.
    """
    env_vars = {}

    if not file_path.exists():
        raise FileNotFoundError(f"Environment file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Match KEY=VALUE pattern
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
            if not match:
                print(f"Warning: Skipping invalid line {line_num}: {line}")
                continue

            key, value = match.groups()

            # Handle quoted values
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]  # Remove quotes
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]  # Remove quotes

            # Handle escaped characters in double quotes
            if '"' in value:
                value = value.replace('\\"', '"')

            env_vars[key] = value

    return env_vars


def parse_arguments():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Migrate .env file to HashiCorp Vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic migration
  python vault_migration.py --vault_url https://127.0.0.1:8200 --vault_token hvs.xxx --vault_mountpoint navapi --env dev

  # Specify custom .env file
  python vault_migration.py --vault_url https://127.0.0.1:8200 --vault_token hvs.xxx --vault_mountpoint navapi --env prod .env.production

  # Migration with insecure SSL (for development)
  python vault_migration.py --vault_url https://127.0.0.1:8200 --vault_token hvs.xxx --vault_mountpoint navapi --env dev --insecure
        """
    )

    parser.add_argument(
        "--vault_url",
        required=True,
        help="Vault server URL (e.g., https://127.0.0.1:8200)"
    )

    parser.add_argument(
        "--vault_token",
        required=True,
        help="Vault root token or token with write permissions"
    )

    parser.add_argument(
        "--vault_mountpoint",
        required=True,
        help="Vault KV mount point name (e.g., navapi)"
    )

    parser.add_argument(
        "--env",
        required=True,
        help="Environment name (e.g., dev, prod, staging)"
    )

    parser.add_argument(
        "env_file",
        nargs="?",
        default=".env",
        help="Path to .env file (default: .env)"
    )

    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip SSL certificate verification (for development only)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually writing to Vault"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    return parser.parse_args()


def test_vault_connection(vault_url: str, token: str, verify_ssl: bool = True, verbose: bool = False) -> bool:
    """
    Test connection to Vault server.
    """
    try:
        headers = {"X-Vault-Token": token}
        response = requests.get(
            f"{vault_url}/v1/sys/health",
            headers=headers,
            timeout=10,
            verify=verify_ssl
        )

        if response.status_code == 200:
            health = response.json()
            server_version = health.get('version', 'unknown')
            if verbose:
                print(f"Vault connection successful. Server version: {server_version}")
                print(f"Vault status: {'sealed' if health.get('sealed') else 'unsealed'}")
                print(f"Cluster name: {health.get('cluster_name', 'unknown')}")
            else:
                print(f"Vault connection successful (version: {server_version})")
            return True
        else:
            print(f"Vault health check failed: {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to Vault: {e}")
        return False


def check_mount_point(vault_url: str, token: str, mount_point: str, verify_ssl: bool = True, verbose: bool = False) -> bool:
    """
    Check if mount point exists and is KV v2.
    """
    try:
        headers = {"X-Vault-Token": token}
        response = requests.get(
            f"{vault_url}/v1/sys/mounts",
            headers=headers,
            timeout=10,
            verify=verify_ssl
        )

        if response.status_code != 200:
            print(f"Failed to list mounts: {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False

        mounts = response.json()
        mount_path = f"{mount_point}/"

        if mount_path in mounts.get('data', {}):
            mount_info = mounts['data'][mount_path]
            mount_type = mount_info.get('type')
            version = mount_info.get('options', {}).get('version', '1')

            if mount_type == 'kv' and version == '2':
                print(f"Mount point '{mount_point}' exists and is KV v2")
                return True
            else:
                print(f"Mount point '{mount_point}' exists but is not KV v2 (type: {mount_type}, version: {version})")
                return False
        else:
            print(f"Mount point '{mount_point}' does not exist")
            print(f"Creating KV v2 mount point '{mount_point}'...")
            return create_mount_point(vault_url, token, mount_point, verify_ssl, verbose)

    except requests.exceptions.RequestException as e:
        print(f"Failed to check mount point: {e}")
        return False


def create_mount_point(vault_url: str, token: str, mount_point: str, verify_ssl: bool = True, verbose: bool = False) -> bool:
    """
    Create KV v2 mount point.
    """
    try:
        headers = {
            "X-Vault-Token": token,
            "Content-Type": "application/json"
        }

        data = {
            "type": "kv",
            "options": {
                "version": "2"
            },
            "description": f"KV v2 secrets engine for {mount_point}"
        }

        response = requests.post(
            f"{vault_url}/v1/sys/mounts/{mount_point}",
            headers=headers,
            json=data,
            timeout=10,
            verify=verify_ssl
        )

        if response.status_code == 204:
            print(f"Successfully created KV v2 mount point: {mount_point}")
            return True
        else:
            print(f"Failed to create mount point: {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Failed to create mount point: {e}")
        return False


def write_secrets_to_vault(vault_url: str, token: str, mount_point: str,
                          env_name: str, secrets: Dict[str, str],
                          verify_ssl: bool = True, verbose: bool = False) -> bool:
    """
    Write secrets to Vault using KV v2 format.
    """
    if not secrets:
        print("No secrets to write")
        return True

    headers = {
        "X-Vault-Token": token,
        "Content-Type": "application/json"
    }

    # KV v2 requires data to be wrapped in a "data" object
    payload = {
        "data": secrets
    }

    try:
        # KV v2 path format: /v1/{mount}/data/{path}
        url = f"{vault_url}/v1/{mount_point}/data/{env_name}"

        if verbose:
            print(f"Writing to URL: {url}")

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
            verify=verify_ssl
        )

        if response.status_code in (200, 204):
            print(f"Successfully wrote {len(secrets)} secrets to {mount_point}/{env_name}")
            return True
        else:
            print(f"Failed to write secrets: {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Failed to write secrets to Vault: {e}")
        return False


def verify_secrets(vault_url: str, token: str, mount_point: str,
                  env_name: str, original_secrets: Dict[str, str],
                  verify_ssl: bool = True, verbose: bool = False) -> bool:
    """
    Verify that secrets were written correctly to Vault.
    """
    headers = {"X-Vault-Token": token}

    try:
        # KV v2 read path format: /v1/{mount}/data/{path}
        url = f"{vault_url}/v1/{mount_point}/data/{env_name}"

        if verbose:
            print(f"Verifying from URL: {url}")

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            verify=verify_ssl
        )

        if response.status_code != 200:
            print(f"Failed to read back secrets: {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False

        data = response.json()
        vault_secrets = data.get('data', {}).get('data', {})

        # Compare secrets
        missing_keys = set(original_secrets.keys()) - set(vault_secrets.keys())
        extra_keys = set(vault_secrets.keys()) - set(original_secrets.keys())

        mismatched_values = []
        for key in original_secrets:
            if key in vault_secrets and original_secrets[key] != vault_secrets[key]:
                mismatched_values.append(key)

        if missing_keys:
            print(f"Missing keys in Vault: {missing_keys}")
            return False

        if extra_keys:
            print(f"Extra keys in Vault: {extra_keys}")

        if mismatched_values:
            print(f"Mismatched values for keys: {mismatched_values}")
            return False

        print(f"Verification successful: All {len(original_secrets)} secrets match")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Failed to verify secrets: {e}")
        return False


def main():
    """
    Main migration function using argparse.
    """
    args = parse_arguments()

    print("=== .env to HashiCorp Vault Migration Tool ===\n")

    # Clean up vault URL (remove trailing slash)
    vault_url = args.vault_url.rstrip('/')
    env_path = Path(args.env_file)
    verify_ssl = not args.insecure

    if args.verbose:
        print(f"Configuration:")
        print(f"  Vault URL: {vault_url}")
        print(f"  Mount point: {args.vault_mountpoint}")
        print(f"  Environment: {args.env}")
        print(f"  .env file: {env_path}")
        print(f"  SSL verification: {verify_ssl}")
        print(f"  Dry run: {args.dry_run}")
        print()

    try:
        # Parse .env file
        if args.verbose:
            print(f"Parsing {env_path}...")
        else:
            print(f"Parsing {env_path}...")

        env_vars = parse_env_file(env_path)
        print(f"Found {len(env_vars)} environment variables")

        if not env_vars:
            print("No environment variables found in the file")
            return 1

        # Show preview of variables (without values for security)
        if args.verbose:
            print("\nEnvironment variables found:")
            for key in sorted(env_vars.keys()):
                value_preview = env_vars[key][:20] + "..." if len(env_vars[key]) > 20 else env_vars[key]
                print(f"  {key} = {value_preview}")
        else:
            print(f"Variables: {', '.join(sorted(env_vars.keys()))}")

        if args.dry_run:
            print(f"\nDRY RUN - Would migrate to:")
            print(f"  Vault: {vault_url}")
            print(f"  Path: {args.vault_mountpoint}/{args.env}")
            print(f"  Variables: {len(env_vars)}")
            return 0

        # Test Vault connection
        print(f"\nTesting connection to {vault_url}...")
        if not test_vault_connection(vault_url, args.vault_token, verify_ssl, args.verbose):
            return 1

        # Check/create mount point
        print(f"\nChecking mount point '{args.vault_mountpoint}'...")
        if not check_mount_point(vault_url, args.vault_token, args.vault_mountpoint, verify_ssl, args.verbose):
            return 1

        # Final confirmation (unless --force is used)
        if not args.force:
            print(f"\nReady to migrate:")
            print(f"  Source: {env_path}")
            print(f"  Destination: {args.vault_mountpoint}/{args.env}")
            print(f"  Variables: {len(env_vars)}")
            print(f"  Vault URL: {vault_url}")

            confirm = input("\nProceed with migration? (y/N): ").strip().lower()
            if confirm not in ('y', 'yes'):
                print("Migration cancelled")
                return 0

        # Write secrets to Vault
        print(f"\nWriting secrets to Vault...")
        if not write_secrets_to_vault(
            vault_url, args.vault_token, args.vault_mountpoint,
            args.env, env_vars, verify_ssl, args.verbose
        ):
            return 1

        # Verify secrets
        print("\nVerifying written secrets...")
        if verify_secrets(
            vault_url, args.vault_token, args.vault_mountpoint,
            args.env, env_vars, verify_ssl, args.verbose
        ):
            print("\nMigration completed successfully!")
            print(f"\nTo use with NavConfig, set these environment variables:")
            print(f"  export VAULT_ENABLED=true")
            print(f"  export VAULT_URL={vault_url}")
            print(f"  export VAULT_TOKEN=your-token")  # Don't expose the actual token
            print(f"  export VAULT_MOUNT_POINT={args.vault_mountpoint}")
            print(f"  export VAULT_VERSION=2")
            print(f"  export ENV={args.env}")

            if args.verbose:
                print(f"\nOr create a .env.vault file:")
                print(f"VAULT_ENABLED=true")
                print(f"VAULT_URL={vault_url}")
                print(f"VAULT_TOKEN=your-token")
                print(f"VAULT_MOUNT_POINT={args.vault_mountpoint}")
                print(f"VAULT_VERSION=2")
                print(f"ENV={args.env}")

            return 0
        else:
            print("\nMigration completed but verification failed")
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
