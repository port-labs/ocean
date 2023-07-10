SHELL := /bin/bash
ACTIVATE := . .venv/bin/activate

define run_lint
	exit_code=0; \
	cd $1; \
	mypy . --exclude '/venv/' || exit_code=$$?; \
	ruff . || exit_code=$$?; \
	black --exclude venv --check . || exit_code=$$?; \
	if [ $$exit_code  == 1 ]; then \
		echo -e "\033[0;31mOne or more lints failed with exit code $$exit_code\033[0m"; \
	else \
		echo -e "\033[0;32mAll lints executed successfully.\033[0m"; \
	fi; \
	exit $$exit_code
endef

define deactivate_virtualenv
    if [ -n "$$VIRTUAL_ENV" ]; then \
        unset VIRTUAL_ENV; \
        unset PYTHONHOME; \
        unset -f pydoc >/dev/null 2>&1; \
        OLD_PATH="$$PATH"; \
        PATH=$$(echo -n "$$PATH" | awk -v RS=: -v ORS=: '/\/virtualenv\/bin$$/ {next} {print}'); \
        export PATH; \
        hash -r; \
        echo "Deactivated the virtual environment."; \
    fi
endef

.SILENT: install lint run test clean

install:
	$(call deactivate_virtualenv) && \
	pip install poetry && \
	poetry install

install/dev:
	$(call deactivate_virtualenv) && \
	pip install poetry && \
	poetry install --with dev

lint:
	$(ACTIVATE) && \
	$(call run_lint,.)

run:
	$(ACTIVATE) && ocean sail

test: lint
	$(ACTIVATE) && poetry run pytest

clean:
	@find . -name '.venv' -type d -exec rm -rf {} \;
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
	rm -rf dist/