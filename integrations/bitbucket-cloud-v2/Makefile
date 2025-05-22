ACTIVATE := . .venv/bin/activate

define run_checks
	exit_code=0; \
	cd $1; \
	echo "Running poetry check"; \
	poetry check || exit_code=$$?;\
	echo "Running mypy"; \
	mypy . --exclude '/\.venv/' || exit_code=$$?; \
	echo "Running ruff"; \
	ruff check . || exit_code=$$?; \
	echo "Running black"; \
	black --check . || exit_code=$$?; \
	echo "Running yamllint"; \
	yamllint . || exit_code=$$?; \
	if [ $$exit_code -eq 1 ]; then \
		echo "\033[0;31mOne or more checks failed with exit code $$exit_code\033[0m"; \
	else \
		echo "\033[0;32mAll checks executed successfully.\033[0m"; \
	fi; \
	exit $$exit_code
endef

define install_poetry
	if ! command -v poetry &> /dev/null; then \
    	pip install --upgrade pip; \
		pip install 'poetry>=1.0.0,<2.0.0'; \
	else \
    	echo "Poetry is already installed."; \
	fi
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

.SILENT: install install/prod install/local-core lint lint/fix run test clean seed

install:
	$(call deactivate_virtualenv) && \
	$(call install_poetry) && \
	poetry install --with dev --no-root

install/local-core: install
	# NOTE: This is a temporary change that shouldn't be committed
	$(ACTIVATE) && pip install -e ../../

install/prod:
	poetry install --without dev --no-root --no-interaction --no-ansi --no-cache
	$(call install_poetry) && \

lint:
	$(ACTIVATE) && \
	$(call run_checks,.)

lint/fix:
	$(ACTIVATE) && \
	black .
	ruff check --fix .

run:
	$(ACTIVATE) && ocean sail

test:
	$(ACTIVATE) && poetry run pytest -n auto

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

seed:
	@if [ -f "tests/seed_data.py" ]; then \
		$(ACTIVATE) && python tests/seed_data.py; \
	else \
		echo "No seeding script found. Create tests/seed_data.py for this integration if needed."; \
		exit 0; \
	fi
