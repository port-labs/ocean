#!/bin/bash

set -e

exit_code=0
for dir in ./integrations/*; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f -name '*.py' -not -path "*/venv/*" | wc -l)
        if [ "$count" -ne 0 ]; then
            echo "Running tests in $dir"
            cd "$dir"
            if [ ! -z "${SCRIPT_TO_RUN}" ]; then
                eval "${SCRIPT_TO_RUN}"
            fi
            . .venv/bin/activate && PYTEST_ADDOPTS="--junitxml=${PWD}/junit/test-results-core-change/$(basename $dir).xml" pytest -n auto || exit_code=$?
            cd - > /dev/null
        fi
    fi
done
exit $exit_code
