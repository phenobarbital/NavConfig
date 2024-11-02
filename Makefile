venv:
	python3.11 -m venv .venv
	echo 'run `source .venv/bin/activate` to start develop NavConfig'

install:
	pip install -e .[uvloop,default]

develop:
	pip install -e .[uvloop,default]
	python -m pip install -Ur docs/requirements-dev.txt

dev:
	flit install --symlink

release: lint test clean
	flit publish

format:
	python -m black navconfig

lint:
	python -m pylint --rcfile .pylint navconfig/*.py
	python -m black --check navconfig

setup_test:
	pip install pytest
	pip install pytest-asyncio
	pip install pytest-xdist
	pip install pytest-assume

test:
	python -m coverage run -m navconfig.tests
	python -m coverage report
	python -m mypy navconfig/*.py

perf:
	python -m unittest -v navconfig.tests.perf

distclean:
	rm -rf .venv
