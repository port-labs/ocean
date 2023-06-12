SHELL := /bin/bash
ACTIVATE := . venv/bin/activate

venv:
	@if [ ! -d "./venv" ]; then \
		python3 -m venv "venv"; \
	fi

install: venv
	$(ACTIVATE) && \
	pip install --upgrade pip && \
	pip install poetry && \
	poetry install --with dev --all-extras

build:
	$(ACTIVATE) && poetry build

run:
	$(ACTIVATE) && ocean sail ./integrations/example

generate_dot_env:
	@if [[ ! -e .env ]]; then \
		cp .env.example .env; \
	fi

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
	rm -rf dist/