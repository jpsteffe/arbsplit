#!/bin/sh
# Run from anywhere. Requires the packages in tests/requirements.txt.
set -eu
cd "$(dirname "$0")/.."
PYTHONPATH=src python -m unittest discover -s tests -v
