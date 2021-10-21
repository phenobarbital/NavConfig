venv:
	python3.9 -m venv .venv
	echo 'run `source .venv/bin/activate` to start develop asyncDB'

develop:
	pip install wheel==0.37.0
	pip install -e .
	python -m pip install -Ur docs/requirements.txt

dev:
	flit install --symlink

release: lint test clean
	flit publish

format:
	python -m black navconfig

lint:
	python -m pylint --rcfile .pylint navconfig/*.py
	python -m black --check navconfig

test:
	python -m coverage run -m navconfig.tests
	python -m coverage report
	python -m mypy navconfig/*.py

perf:
	python -m unittest -v navconfig.tests.perf

distclean:
	rm -rf .venv
