.PHONY: install seed run eval test lint bench clean

install:
	pip install -e ".[dev]"

# Builds data/index.sqlite from the synthetic KB. First run downloads the
# MiniLM encoder (about 90 MB); after that it is offline.
seed:
	python -m api.ingest.cli --source ./demo/sample_kb --db ./data/index.sqlite

run:
	uvicorn api.main:app --port 8000

eval:
	python -m eval.run_eval

test:
	pytest tests/ -q

lint:
	ruff check .

bench: eval

clean:
	rm -rf .pytest_cache .ruff_cache *.egg-info data
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
