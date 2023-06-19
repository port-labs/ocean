SHELL := /bin/bash
ACTIVATE := . venv/bin/activate

define run_lint
	mypy $1 || exit_code=$$?; \
	ruff $1 || exit_code=$$?; \
	black --check $1 || exit_code=$$?; \
	\
	if [ -n "$$exit_code " ]; then \
		echo -e "\033[0;31mOne or more lints failed with exit code $$exit_code\033[0m"; \
	fi; \
	if [ -n "$$exit_code " ] && [ "$2" = 1 ]; then \
		exit 1; \
	fi; \

	echo "All lints executed successfully."
endef

venv:
	@if [ ! -d "./venv" ]; then \
		python3 -m venv "venv"; \
	fi

# Install dependencies
install: venv
	$(ACTIVATE) && \
	pip install --upgrade pip && \
	pip install poetry && \
	poetry install --with dev

install/all: venv
	$(ACTIVATE) && \
	pip install --upgrade pip && \
	pip install poetry && \
	poetry install --with dev --all-extras


# Linting
lint/framework:
	$(ACTIVATE) && \
	exist_on_first_fail=1; \
	$(call run_lint,./port_ocean,$$exist_on_first_fail)

lint/integrations:
	$(ACTIVATE) && \
	exist_on_first_fail=0; \
	for dir in $(wildcard $(CURDIR)/integrations/*); do \
        echo "Linting $$dir"; \
        $(call run_lint,$$dir,$$exist_on_first_fail) || failed_dirs+=" $$dir"; \
    done;

lint/all: lint/framework lint/integrations


# Development commands
build: 
	$(ACTIVATE) && poetry build

run: lint/framework
	$(ACTIVATE) && poetry run ocean sail ./integrations/example

new:
	$(ACTIVATE) && poetry run ocean new ./integrations

test: lint/framework
	$(ACTIVATE) && pytest

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