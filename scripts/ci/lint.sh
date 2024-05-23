#!/bin/bash

set -ex

if [ $# -gt 0 ]; then
	PYLINT_DISABLE_COMMANDS="$1"
fi

find . -name _symbol -prune -o -type f -name "*.sh" -print0 | xargs -0 shellcheck
find . -name _symbol -prune -o -type f -name "*.py" -print0 | PYTHONPATH=. xargs -0 python3 -m isort \
	--line-length 140 \
	--indent "	" \
	--multi-line 3 \
	--check-only
find . -name _symbol -prune -o -type f -name "*.py" -print0 | PYTHONPATH=. xargs -0 python3 -m pycodestyle \
	--config="$(git rev-parse --show-toplevel)/linters/python/.pycodestyle"
find . -name _symbol -prune -o -type f -name "*.py" -print0 | PYTHONPATH=. xargs -0 python3 -m pylint \
	--rcfile "$(git rev-parse --show-toplevel)/linters/python/.pylintrc" \
	--disable "${PYLINT_DISABLE_COMMANDS}"
