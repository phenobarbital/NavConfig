import pytest
import os
import logging
from logging.config import dictConfig
import asyncio
from pathlib import Path
import pytest_asyncio
from navconfig.logging import logging_config


# Modern pytest-asyncio configuration
pytestmark = pytest.mark.asyncio(scope="session")


# Your existing tests (unchanged)
async def test_config():
    from navconfig import config, SITE_ROOT, BASE_DIR, DEBUG
    current_path = Path(__file__).resolve().parent.parent
    assert current_path == SITE_ROOT
    debug = bool(os.getenv('DEBUG', False))
    assert debug == DEBUG


async def test_conf():
    from navconfig import config
    from navconfig.conf import LOCAL_DEVELOPMENT
    from settings.settings import LOCAL_DEVELOPMENT as LP
    assert LP == LOCAL_DEVELOPMENT
    dictConfig(logging_config)
    log = logging.getLogger()
    log.debug('HELLO WORLD')


async def test_environment():
    from navconfig import config
    config.configure(env='dev', override=True)
    cnf = config.get('CONFIG_FILE')
    assert cnf == 'etc/navigator.ini'


async def test_settings():
    from navconfig import config
    from settings.settings import SEND_NOTIFICATIONS
    assert SEND_NOTIFICATIONS is True


async def test_local_settings():
    from navconfig import config
    from navconfig.conf import CONFIG_TEST
    from settings.settings import CONFIG_TEST as CT
    ct = config.get('CONFIG_TEST', fallback='NAVCONFIG')
    assert ct == CT
    assert CONFIG_TEST == CT


# New tests for environment switching and info
async def test_get_env_info():
    """Test get_env_info() returns proper structure and data."""
    from navconfig import config

    env_info = config.get_env_info()

    # Test required fields exist
    required_fields = [
        'current_env', 'loader_type', 'available_envs',
        'cached_envs', 'site_root', 'total_variables'
    ]

    for field in required_fields:
        assert field in env_info, f"Missing required field: {field}"

    # Test field types
    assert isinstance(env_info['current_env'], (str, type(None)))
    assert isinstance(env_info['loader_type'], (str, type(None)))
    assert isinstance(env_info['available_envs'], list)
    assert isinstance(env_info['cached_envs'], list)
    assert isinstance(env_info['site_root'], str)
    assert isinstance(env_info['total_variables'], int)

    # Test values make sense
    assert env_info['total_variables'] >= 0
    assert Path(env_info['site_root']).exists()

    print(f"Environment info validated: {env_info['loader_type']} loader, "
          f"{env_info['total_variables']} variables")


async def test_vault_status_info():
    """Test vault status information in get_env_info()."""
    from navconfig import config

    env_info = config.get_env_info()

    # If vault status is present, validate its structure
    if 'vault_status' in env_info:
        vault_status = env_info['vault_status']

        # Required vault status fields
        required_vault_fields = ['enabled', 'connected', 'config', 'secrets_loaded', 'environment']

        for field in required_vault_fields:
            assert field in vault_status, f"Missing vault status field: {field}"

        # Test field types
        assert isinstance(vault_status['enabled'], bool)
        assert isinstance(vault_status['connected'], bool)
        assert isinstance(vault_status['config'], dict)
        assert isinstance(vault_status['secrets_loaded'], int)
        assert isinstance(vault_status['environment'], str)

        # Test config structure
        if vault_status['enabled']:
            vault_config = vault_status['config']
            expected_config_fields = ['url', 'mount_point', 'version']

            for field in expected_config_fields:
                assert field in vault_config, f"Missing vault config field: {field}"

        print(f"Vault status: enabled={vault_status['enabled']}, "
              f"connected={vault_status['connected']}, "
              f"secrets_loaded={vault_status['secrets_loaded']}")
    else:
        print("No vault status found (file-only loader)")


async def test_current_environment():
    """Test getting current environment."""
    from navconfig import config

    current_env = config.get_current_env()
    assert isinstance(current_env, (str, type(None)))

    # Should match ENV environment variable or default
    expected_env = os.getenv('ENV', 'dev')  # Assuming 'dev' is your default

    # Current env should be set to something
    assert current_env is not None
    print(f"Current environment: {current_env}")


async def test_list_available_environments():
    """Test listing available environments."""
    from navconfig import config

    available_envs = config.list_available_envs()

    # Should return a list
    assert isinstance(available_envs, list)

    # Should contain at least the current environment
    current_env = config.get_current_env()
    if current_env:
        assert current_env in available_envs, f"Current env '{current_env}' not in available envs"

    # All entries should be strings
    for env in available_envs:
        assert isinstance(env, str), f"Environment name should be string, got {type(env)}"
        assert env.strip() == env, "Environment names should be stripped of whitespace"

    print(f"Available environments: {available_envs}")


async def test_environment_switching():
    """Test switching between environments."""
    from navconfig import config

    # Get original environment
    original_env = config.get_current_env()
    available_envs = config.list_available_envs()

    # Find a different environment to switch to
    target_env = None
    for env in available_envs:
        if env != original_env:
            target_env = env
            break

    if target_env is None:
        pytest.skip("No alternative environment available for switching test")

    # Test switching
    success = config.set_env(target_env)
    assert success is True, f"Failed to switch to environment: {target_env}"

    # Verify environment switched
    assert config.get_current_env() == target_env

    # Switch back to original
    success = config.set_env(original_env)
    assert success is True, f"Failed to switch back to original environment: {original_env}"

    # Verify we're back to original
    assert config.get_current_env() == original_env

    print(f"Environment switching test: {original_env} -> {target_env} -> {original_env}")


async def test_environment_switching_idempotent():
    """Test that switching to the same environment is idempotent."""
    from navconfig import config

    current_env = config.get_current_env()

    # Switch to same environment should succeed
    success = config.set_env(current_env)
    assert success is True

    # Should still be in same environment
    assert config.get_current_env() == current_env


async def test_cross_environment_query():
    """Test querying variables from different environments without switching."""
    from navconfig import config

    current_env = config.get_current_env()
    available_envs = config.list_available_envs()

    # Test querying current environment (should work like normal get())
    test_key = 'CONFIG_FILE'  # A key that should exist
    current_value = config.get(test_key)
    cross_env_value = config.get_with_env(test_key, current_env)

    if current_value is not None:
        assert current_value == cross_env_value, "Cross-env query should match current env"

    # Test querying different environment (if available)
    for env in available_envs:
        if env != current_env:
            # This might return None if the key doesn't exist in that env, which is fine
            cross_value = config.get_with_env(test_key, env)
            # Just verify it doesn't crash and returns something reasonable
            assert cross_value is None or isinstance(cross_value, str)
            break

    print(f"Cross-environment query test completed for key: {test_key}")


# async def test_environment_caching():
#     """Test environment caching functionality."""
#     from navconfig import config

#     # Clear cache first
#     config.clear_env_cache()

#     env_info_before = config.get_env_info()
#     cached_envs_before = len(env_info_before['cached_envs'])

#     available_envs = config.list_available_envs()
#     current_env = config.get_current_env()

#     # Find alternative environment
#     target_env = None
#     for env in available_envs:
#         if env != current_env:
#             target_env = env
#             break

#     if target_env is None:
#         pytest.skip("No alternative environment available for caching test")

#     # Switch to different environment (should cache it)
#     config.set_env(target_env)

#     env_info_after = config.get_env_info()
#     cached_envs_after = len(env_info_after['cached_envs'])

#     # Should have more cached environments now
#     assert cached_envs_after >= cached_envs_before
#     assert target_env in env_info_after['cached_envs']

#     # Clear cache and verify
#     config.clear_env_cache(target_env)
#     env_info_cleared = config.get_env_info()

#     # The specific environment should be cleared from cache
#     if target_env in env_info_cleared['cached_envs']:
#         # It might still be there if it's the current environment
#         pass

#     print(f"Caching test: {cached_envs_before} -> {cached_envs_after} cached environments")

#     # Switch back to original
#     config.set_env(current_env)


async def test_loaded_files_info():
    """Test loaded files information in get_env_info()."""
    from navconfig import config

    env_info = config.get_env_info()

    # Check if loaded files info is present
    if 'loaded_files' in env_info:
        loaded_files = env_info['loaded_files']
        file_count = env_info.get('file_count', 0)

        assert isinstance(loaded_files, list)
        assert isinstance(file_count, int)
        assert len(loaded_files) == file_count

        # All loaded files should exist
        for file_path in loaded_files:
            assert isinstance(file_path, str)
            file_path_obj = Path(file_path)
            assert file_path_obj.exists(), f"Loaded file should exist: {file_path}"

        print(f"Loaded files: {file_count} files")
        for file_path in loaded_files:
            print(f"  - {file_path}")
    else:
        print("No loaded files information available")


async def test_configuration_values_exist():
    """Test that some expected configuration values exist."""
    from navconfig import config

    # Test some values that should typically exist
    test_cases = [
        ('DEBUG', bool),
        ('CONFIG_FILE', str),
        ('APP_NAME', str),
    ]

    for key, expected_type in test_cases:
        value = config.get(key) if expected_type is not bool else config.getboolean(key)
        if value is not None:
            assert isinstance(value, expected_type), f"{key} should be {expected_type}, got {type(value)}"
            print(f"Configuration test: {key} = {value} ({type(value).__name__})")
        else:
            print(f"Configuration test: {key} = None (not set)")


async def test_environment_reload():
    """Test reloading current environment."""
    from navconfig import config

    current_env = config.get_current_env()

    # Get current variable count
    env_info_before = config.get_env_info()
    vars_before = env_info_before['total_variables']

    # Reload environment
    config.reload_current_env()

    # Should still be in same environment
    assert config.get_current_env() == current_env

    # Check that reload worked (variables should be loaded again)
    env_info_after = config.get_env_info()
    vars_after = env_info_after['total_variables']

    # Variable count should be similar (unless environment changed externally)
    assert vars_after > 0, "Should have variables after reload"

    print(f"Environment reload test: {vars_before} -> {vars_after} variables")


# Fixture for cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_environment():
    """Ensure we end up in a clean state after tests."""
    from navconfig import config

    # Store original environment
    original_env = os.getenv('ENV', 'dev')

    yield  # Run the test

    # Cleanup: ensure we're back in the expected environment
    try:
        if config.get_current_env() != original_env:
            config.set_env(original_env)
    except Exception as e:
        # If cleanup fails, just log it
        print(f"Cleanup warning: {e}")


# Test to validate the overall test setup
async def test_pytest_setup():
    """Validate that the test environment is properly set up."""
    from navconfig import config

    # Basic sanity checks
    assert config is not None
    assert hasattr(config, 'get')
    assert hasattr(config, 'get_env_info')
    assert hasattr(config, 'get_current_env')
    assert hasattr(config, 'list_available_envs')
    assert hasattr(config, 'set_env')

    print("Pytest setup validation completed")


if __name__ == "__main__":
    # If run directly, execute a simple test
    import asyncio

    async def run_simple_test():
        await test_get_env_info()
        print("Simple test completed successfully")

    asyncio.run(run_simple_test())
