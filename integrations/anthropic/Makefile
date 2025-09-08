MAKEFLAGS := --silent

define get_build_context
$(shell python ../../scripts/get_integration_relative_dir.py --integration-name anthropic)
endef

build:
	docker build --platform="linux/amd64" -t anthropic-integration:latest . -f $(call get_build_context)/Dockerfile --build-arg BUILD_CONTEXT=$(call get_build_context)

run-local: build
	docker run --platform="linux/amd64" -i -t --rm --name anthropic-integration anthropic-integration:latest

# install integration locally using pip
install:
	pip install --editable .

lint:
	ruff check . --fix

format:
	black .

type:
	mypy .

test:
	pytest

run-tests: lint format type test

new:
	towncrier create --content "new change"