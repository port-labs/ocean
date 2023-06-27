SHELL := /bin/bash
ACTIVATE := . venv/bin/activate

venv:
	@if [ ! -d "./venv" ]; then \
		python3 -m venv "venv"; \
	fi

generate_config:
	@if [[ ! -e .env ]]; then \
		cp example.config.yaml config.yaml; \
	fi

install: venv generate_config
	$(ACTIVATE) && \
	pip install --upgrade pip && \
	pip install poetry && \
	poetry install --with dev --all-extras

install-release:
	pip install --upgrade pip && \
	pip install poetry && \
	poetry install --with dev --all-extras
	
mypy:
	$(ACTIVATE) && mypy ./port_ocean

run: mypy
	$(ACTIVATE) && poetry run main.py

test: mypy

clean:
	@find . -name '*.pyc' -exec rm -rf {} \;
	@find . -name '__pycache__' -exec rm -rf {} \;
	@find . -name 'Thumbs.db' -exec rm -rf {} \;
	@find . -name '*~' -exec rm -rf {} \;
	rm -rf .cache
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info
	rm -rf htmlcov
	rm -rf .tox/
	rm -rf docs/_build
	rm -rf venv/