#!/bin/bash

# cd integrations/fake-integration
# ls /usr/bin/python*
# rm -rf .venv
/usr/bin/python3 -m venv .venv
cd integrations/fake-integration
source .venv/bin/activate
make install/local-core
# python -m pip install poetry
# poetry install
# python -m pip install debugpy

# source .venv/bin/activate
# cd integrations/fake-integration
# file .venv/bin/python


# python -m debugpy --listen 0.0.0.0:5678 --wait-for-client /app/integrations/fake-integration/debug.py
make run
# python3 -m pip install memray
# python3 -m memray run -o output.bin /app/integrations/fake-integration/debug.py
