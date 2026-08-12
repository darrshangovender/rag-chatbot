.PHONY: install seed run eval test clean fmt

PYTHON ?= python
VENV ?= .venv

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/Scripts/pip install -e ".[dev]" || $(VENV)/bin/pip install -e ".[dev]"

seed:
	$(PYTHON) -m api.ingest.cli --source ./demo/sample_kb --db ./data/index.sqlite

run:
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

eval:
	$(PYTHON) -m eval.run_eval --db ./data/index.sqlite --questions ./eval/golden_questions.yml

test:
	$(PYTHON) -m pytest

fmt:
	ruff format .
	ruff check --fix .

clean:
	rm -rf data/index.sqlite data/tickets.jsonl .pytest_cache __pycache__
