SHELL := bash
.DEFAULT_GOAL := help

# Auto-detect a Python executable
PY := $(shell command -v python3 >/dev/null 2>&1 && echo python3 || echo python)
VENV := .venv
BIN := $(VENV)/bin
ACT := $(BIN)/activate
ARGS ?=

.PHONY: venv install dev test fmt lint check clean help

## Create virtualenv if missing
venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)

## Install/refresh dependencies
install: venv
	@$(BIN)/python -m pip install -U pip
	@$(BIN)/python -m pip install -r requirements.txt

## Run the FastAPI dev server (hot reload)
dev: install
	@echo "Running dev server (DW_DB_PATH=$${DW_DB_PATH:-worldweaver.db})"
	@$(BIN)/uvicorn main:app --reload

## Run tests (pass extra args via ARGS="...")
test: install
	@$(BIN)/pytest -q $(ARGS)

## Format code with black (if installed)
fmt: venv
	@if [ -x "$(BIN)/black" ]; then $(BIN)/black .; else echo "black not installed. Optionally: $(BIN)/python -m pip install black"; fi

## Lint with flake8 (if installed)
lint: venv
	@if [ -x "$(BIN)/flake8" ]; then $(BIN)/flake8; else echo "flake8 not installed. Optionally: $(BIN)/python -m pip install flake8"; fi

## Check format, lint, and run tests
check: install
	@if [ -x "$(BIN)/black" ]; then echo "Running black --check"; $(BIN)/black --check .; else echo "black not installed. Skipping format check."; fi
	@if [ -x "$(BIN)/flake8" ]; then echo "Running flake8"; $(BIN)/flake8; else echo "flake8 not installed. Skipping lint."; fi
	@$(BIN)/pytest -q $(ARGS)

## Remove venv, caches, and local DBs
clean:
	@rm -rf $(VENV)
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@rm -f worldweaver.db test_database.db *.pyc

## Show available targets
help:
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:\n\t|^## ' Makefile | \
		awk 'BEGIN{FS=":|## "} /^[a-zA-Z_-]+:/{t=$$1} /^## /{printf "  %-8s %s\n", t, $$2}'

## Run StorySmoother smoke test
smoke-smoother: install
	@echo "Running StorySmoother smoke test (DW_DB_PATH=$${DW_DB_PATH:-test_smoother.db})"
	@PYTHONPATH=. DW_DB_PATH=$${DW_DB_PATH:-test_smoother.db} $(BIN)/python -m py_scripts.test_smoother_smoke

## Generate spatial map HTML (reports/spatial_map.html)
spatial-map: install
	@echo "Generating spatial map (DW_DB_PATH=$${DW_DB_PATH:-test_smoother.db})"
	@PYTHONPATH=. DW_DB_PATH=$${DW_DB_PATH:-test_smoother.db} $(BIN)/python -m tests.diagnostic.test_spatial_map_visual
