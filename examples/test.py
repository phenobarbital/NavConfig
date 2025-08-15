#!/usr/bin/env python
"""Test script to verify NavConfig installation."""

def test_basic_import():
    try:
        import navconfig
        print(f"✅ NavConfig imported successfully (version: {navconfig.__version__})")
        return True
    except ImportError as e:
        print(f"❌ Failed to import NavConfig: {e}")
        return False

def test_config_object():
    try:
        from navconfig import config
        print(f"✅ Config object created successfully")
        print(f"   Site root: {config.site_root}")
        print(f"   Debug mode: {config.debug}")
        return True
    except Exception as e:
        print(f"❌ Failed to create config object: {e}")
        return False

def test_cython_extensions():
    """Test that Cython extensions are compiled and working."""
    tests = [
        ("navconfig.utils.functions", "strtobool"),
        ("navconfig.utils.types", "Singleton"),
        ("navconfig.exceptions", "KardexError"),
        ("navconfig.utils.json", "json_encoder"),
    ]

    for module_name, attr_name in tests:
        try:
            module = __import__(module_name, fromlist=[attr_name])
            getattr(module, attr_name)
            print(f"✅ Cython extension {module_name} working")
        except ImportError as e:
            print(f"❌ Failed to import {module_name}: {e}")
            return False
        except AttributeError as e:
            print(f"❌ Missing attribute {attr_name} in {module_name}: {e}")
            return False

    return True

if __name__ == "__main__":
    print("🧪 Testing NavConfig installation...")

    success = all([
        test_basic_import(),
        test_config_object(),
        test_cython_extensions(),
    ])

    if success:
        print("\n🎉 All tests passed! NavConfig is working correctly.")
        exit(0)
    else:
        print("\n💥 Some tests failed. Check the errors above.")
        exit(1)
