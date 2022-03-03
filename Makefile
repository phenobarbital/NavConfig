venv:
	python3.9 -m venv .venv
	echo 'run `source .venv/bin/activate` to start develop asyncDB'

develop:
	pip install wheel==0.37.0
	pip install -e .
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
	pip install pytest>=6.0.0
	pip install pytest-asyncio==0.18.0
	pip install pytest-xdist==2.1.0
	pip install pytest-assume==2.4.2

test:
	python -m coverage run -m navconfig.tests
	python -m coverage report
	python -m mypy navconfig/*.py

perf:
	python -m unittest -v navconfig.tests.perf

distclean:
	rm -rf .venv
