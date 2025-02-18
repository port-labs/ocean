ACTIVATE := . .venv/bin/activate

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
	poetry install --with dev && \
	$(ACTIVATE) && pip install pytest pytest-xdist

install/local-core: install
	# NOTE: This is a temporary change that shouldn't be committed
	$(ACTIVATE) && pip install -e ../../

install/prod:
	poetry install --without dev --no-root --no-interaction --no-ansi --no-cache
	$(call install_poetry) && \

lint:
	$(ACTIVATE) && \
	poetry check && \
	mypy . --exclude '/\.venv/' && \
	ruff check . && \
	black --check . && \
	yamllint .

lint/fix:
	$(ACTIVATE) && \
	black .
	ruff check --fix .

run:
	$(ACTIVATE) && ocean sail

test:
	$(ACTIVATE) && pytest -n auto || exit $$?

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
