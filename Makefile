ACTIVATE := . .venv/bin/activate

define run_checks
	exit_code=0; \
	cd $1; \
	poetry check || exit_code=$$?;\
	mypy . --exclude '/\.venv/' || exit_code=$$?; \
	ruff check . || exit_code=$$?; \
	black --check . || exit_code=$$?; \
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
		pip install poetry; \
	else \
    	echo "Poetry is already installed."; \
	fi
endef

define install_precommit
	command pre-commit install
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

.SILENT: install install/all test/all test/smoke clean/smoke lint lint/fix build run new test test/watch clean bump/integrations bump/single-integration execute/all


# Install dependencies
install:
	$(call deactivate_virtualenv) && \
	$(call install_poetry) && \
	poetry install --with dev --all-extras &&  \
	$(ACTIVATE) && \
	$(call install_precommit)

test/all: test
	$(ACTIVATE) && \
	for dir in $(wildcard $(CURDIR)/integrations/*); do \
		count=$$(find $$dir -type f -name '*.py' -not -path "*/venv/*" | wc -l); \
		if [ $$count -ne 0 ]; then \
			echo "Testing $$dir"; \
		  	cd $$dir; \
			$(MAKE) test || exit_code=$$?; \
			cd ../..; \
		fi; \
	done;


execute/all:
	# run script for all integrations (${SCRIPT_TO_RUN})
	for dir in $(wildcard $(CURDIR)/integrations/*); do \
		count=$$(find $$dir -type f -name '*.py' -not -path "*/venv/*" | wc -l); \
		if [ $$count -ne 0 ]; then \
			echo "Running '${SCRIPT_TO_RUN}' $$dir"; \
		  	cd $$dir; \
			${SCRIPT_TO_RUN} || exit_code=$$?; \
			cd ../..; \
		fi; \
	done;

install/all: install
	exit_code=0; \
	for dir in $(wildcard $(CURDIR)/integrations/*); do \
		count=$$(find $$dir -type f -name '*.py' -not -path "*/venv/*" | wc -l); \
		if [ $$count -ne 0 ]; then \
			echo "Installing $$dir"; \
		  	cd $$dir; \
			$(MAKE) install || exit_code=$$?; \
			cd ../..; \
		fi; \
    done; \
    if [ $$exit_code -ne 0 ]; then \
        exit 1; \
    fi

# Linting
lint:
	$(ACTIVATE) && \
	$(call run_checks,.)

lint/fix:
	$(ACTIVATE) && \
	black .
	ruff check --fix .

# Development commands
build:
	$(ACTIVATE) && poetry build

run: lint
	$(ACTIVATE) && poetry run ocean sail ./integrations/example

new:
	$(ACTIVATE) && poetry run ocean new ./integrations --public

test:
	$(ACTIVATE) && pytest -m 'not smoke'

test/smoke:
	$(ACTIVATE) && SMOKE_TEST_SUFFIX=$${SMOKE_TEST_SUFFIX:-default_value} pytest -m smoke

clean/smoke:
	$(ACTIVATE) && SMOKE_TEST_SUFFIX=$${SMOKE_TEST_SUFFIX:-default_value} python ./scripts/clean-smoke-test.py

test/watch:
	$(ACTIVATE) && \
		pytest \
			--color=yes \
			-f

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

# make bump/integrations VERSION=0.3.2
bump/integrations:
	./scripts/bump-all.sh $(VERSION)

# make bump/single-integration INTEGRATION=aws
bump/single-integration:
	./scripts/bump-single-integration.sh -i $(INTEGRATION)
