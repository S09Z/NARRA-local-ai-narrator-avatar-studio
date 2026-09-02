# NARRA — development tasks.
#
# The entry point for the checks this repository already has, so that "did you run
# it?" has one answer. Adds no behaviour: every target is a script that is equally
# runnable by hand.
#
# The interpreter is .venv/bin/python when Poetry has made one (`make install`), and
# a bare python3 otherwise — the scripts depend on nothing that requires the venv.
# Override either way:  make test PYTHON=/usr/bin/python3.12

REPO   := $(shell pwd)
VENV   := $(REPO)/.venv/bin/python
PYTHON ?= $(if $(wildcard $(VENV)),$(VENV),python3)

SCRIPTS := $(REPO)/scripts
TESTS   := $(REPO)/tests

.DEFAULT_GOAL := help
.PHONY: help install test lint gate check status clean

help:  ## show this list
	@echo
	@echo "NARRA — development tasks"
	@echo
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-8s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  PYTHON=$(PYTHON)"
	@echo

install:  ## create .venv and install dependencies (Poetry)
	poetry install

test:  ## run the test suite
	$(PYTHON) -m pytest $(TESTS) -q

lint:  ## lint every prompt under prompts/ (structure, preservation, seeds)
	$(PYTHON) $(SCRIPTS)/generation/compile_prompt.py --lint

gate:  ## run the PHASE 6 gate — reports only, writes nothing
	$(PYTHON) $(SCRIPTS)/validation/lock_library.py

check: test lint  ## test + lint, the pre-commit pair

status:  ## where the project is: git, prompts, library, PHASE 6 gate
	@$(PYTHON) $(SCRIPTS)/utilities/status.py

# Python build artefacts only. Generated images, timelines, frames, and model
# weights are left alone — they are expensive, gitignored, and not this target's
# business (CLAUDE.md: never delete models).
clean:  ## remove Python caches (never touches assets, models, or metadata)
	@find $(SCRIPTS) $(TESTS) -type d -name __pycache__ -prune -exec rm -rf {} +
	@find $(SCRIPTS) $(TESTS) -type f -name '*.py[co]' -delete
	@rm -rf $(REPO)/.pytest_cache $(REPO)/.ruff_cache $(REPO)/.mypy_cache
	@echo "removed Python caches; assets, models, and metadata untouched"
