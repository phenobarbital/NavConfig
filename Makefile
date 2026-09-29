# Navconfig Makefile
# This Makefile provides a set of commands to manage the Navconfig project.

.PHONY: venv install develop setup dev dev-install editable release format lint test clean distclean lock sync

# Python version to use
PYTHON_VERSION := 3.11

# Auto-detect available tools
HAS_UV := $(shell command -v uv 2> /dev/null)
HAS_PIP := $(shell command -v pip 2> /dev/null)

# Install uv for faster workflows
install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo "uv installed! You may need to restart your shell or run 'source ~/.bashrc'"
	@echo "Then re-run make commands to use faster uv workflows"

# Create virtual environment
venv:
	uv venv --python $(PYTHON_VERSION) .venv
	@echo 'run `source .venv/bin/activate` to start develop with Navconfig.'

# Install production dependencies using lock file
install:
	uv sync --frozen --no-dev
	@echo "Production dependencies installed. Use 'make develop' for development setup."

# Install with all extras
install-all:
	uv sync --extra all
	@echo "All dependencies installed. Use 'make develop' for development setup."

# Generate lock files (uv only)
lock:
ifdef HAS_UV
	uv lock
else
	@echo "Lock files require uv. Install with: pip install uv"
endif

# Install all dependencies including dev dependencies
develop:
	uv sync --frozen --extra all --extra dev

# Alternative: install without lock file (faster for development)
develop-fast:
	uv pip install -e .[all,dev]

# Install in development/editable mode (what you're looking for!)
dev-install: build-inplace
	@echo "Installing NavConfig in development mode..."
	uv pip install -e .
	@echo "✅ NavConfig installed in editable mode. Changes to source will be reflected immediately."

# Alias for dev-install
editable: dev-install

# Complete development setup: dependencies + Cython + editable install
dev-setup: develop build-inplace dev-install
	@echo "🎉 Complete development environment ready!"
	@echo "   - All dependencies installed"
	@echo "   - Cython extensions compiled"
	@echo "   - Package installed in editable mode"

# Setup development environment from requirements file (if you still have one)
setup:
	uv pip install -r requirements/requirements-dev.txt

# Install in development mode using flit (if you want to keep flit)
dev:
	uv pip install flit
	flit install --symlink

# Build and publish release
release: lint test clean
	uv build
	uv publish

# Alternative release using flit
release-flit: lint test clean
	flit publish

# Format code
format:
	uv run black navconfig

# Lint code
lint:
	uv run pylint --rcfile .pylint navconfig/*.py
	uv run black --check navconfig

# Run tests with coverage
test:
	uv run coverage run -m navconfig.tests
	uv run coverage report
	uv run mypy navconfig/*.py

# Alternative test command using pytest directly
test-pytest:
	uv run pytest

# Add new dependency and update lock file
add:
	@if [ -z "$(pkg)" ]; then echo "Usage: make add pkg=package-name"; exit 1; fi
	uv add $(pkg)

# Add development dependency
add-dev:
	@if [ -z "$(pkg)" ]; then echo "Usage: make add-dev pkg=package-name"; exit 1; fi
	uv add --dev $(pkg)

# Remove dependency
remove:
	@if [ -z "$(pkg)" ]; then echo "Usage: make remove pkg=package-name"; exit 1; fi
	uv remove $(pkg)

# Compile Cython extensions using setup.py
build-cython:
	@echo "Compiling Cython extensions..."
	python setup.py build_ext

# Build Cython extensions in place (for development)
build-inplace:
	@echo "Installing build dependencies..."
	@uv pip install setuptools==74.0.0 Cython==3.0.11 wheel==0.44.0
	@echo "Building Cython extensions in place..."
	python setup.py build_ext --inplace

# Full build using uv
build: clean
	@echo "Building package with uv..."
	uv build

# Update all dependencies
update:
	uv lock --upgrade

# Show project info
info:
	uv tree

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.so" -delete
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."

# Remove virtual environment
distclean:
	rm -rf .venv
	rm -rf uv.lock

# Version management
bump-patch:
	@python -c "import re; \
	content = open('navconfig/version.py').read(); \
	version = re.search(r'__version__ = \"(.+)\"', content).group(1); \
	parts = version.split('.'); \
	parts[2] = str(int(parts[2]) + 1); \
	new_version = '.'.join(parts); \
	new_content = re.sub(r'__version__ = \".+\"', f'__version__ = \"{new_version}\"', content); \
	open('navconfig/version.py', 'w').write(new_content); \
	print(f'Version bumped to {new_version}')"

bump-minor:
	@python -c "import re; \
	content = open('navconfig/version.py').read(); \
	version = re.search(r'__version__ = \"(.+)\"', content).group(1); \
	parts = version.split('.'); \
	parts[1] = str(int(parts[1]) + 1); \
	parts[2] = '0'; \
	new_version = '.'.join(parts); \
	new_content = re.sub(r'__version__ = \".+\"', f'__version__ = \"{new_version}\"', content); \
	open('navconfig/version.py', 'w').write(new_content); \
	print(f'Version bumped to {new_version}')"

bump-major:
	@python -c "import re; \
	content = open('navconfig/version.py').read(); \
	version = re.search(r'__version__ = \"(.+)\"', content).group(1); \
	parts = version.split('.'); \
	parts[0] = str(int(parts[0]) + 1); \
	parts[1] = '0'; \
	parts[2] = '0'; \
	new_version = '.'.join(parts); \
	new_content = re.sub(r'__version__ = \".+\"', f'__version__ = \"{new_version}\"', content); \
	open('navconfig/version.py', 'w').write(new_content); \
	print(f'Version bumped to {new_version}')"

# Create wheel
wheel:
	uv run python setup.py bdist_wheel

# Test the development installation
test-dev:
	@echo "Testing development installation..."
	@python -c "import navconfig; print(f'✅ NavConfig {navconfig.__version__} imported successfully')"
	@python -c "from navconfig import config; print(f'✅ Config object created: {config.site_root}')"
	@echo "✅ Development installation is working correctly!"

help:
	@echo "Available targets:"
	@echo "  venv         - Create virtual environment"
	@echo "  install      - Install production dependencies"
	@echo "  develop      - Install development dependencies"
	@echo "  dev-install  - Install package in development/editable mode"
	@echo "  editable     - Alias for dev-install"
	@echo "  dev-setup    - Complete development setup (deps + build + install)"
	@echo "  build        - Build package"
	@echo "  build-inplace - Build Cython extensions in place"
	@echo "  release      - Build and publish package"
	@echo "  test         - Run tests"
	@echo "  test-dev     - Test development installation"
	@echo "  format       - Format code"
	@echo "  lint         - Lint code"
	@echo "  clean        - Clean build artifacts"
	@echo "  install-uv   - Install uv"
	@echo "  add pkg=name - Add dependency"
	@echo "  remove pkg=name - Remove dependency"
	@echo "  bump-patch   - Bump patch version"
	@echo "  bump-minor   - Bump minor version"
	@echo "  bump-major   - Bump major version"
	@echo ""
	@echo "Quick development workflow:"
	@echo "  make venv && source .venv/bin/activate"
	@echo "  make dev-setup  # Complete setup"
	@echo "  make test-dev   # Verify installation"
