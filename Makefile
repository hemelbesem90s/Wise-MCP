.PHONY: install format lint test check build clean

install:
	python -m pip install -e ".[dev]"

format:
	ruff check --fix .
	ruff format .

lint:
	ruff check .
	ruff format --check .
	mypy .
	bandit -q -r wise wise_mcp

test:
	pytest --cov=wise --cov=wise_mcp --cov-report=term-missing -q

check: lint test build

build:
	python -m build
	python -m twine check dist/*

clean:
	rm -rf build dist .coverage htmlcov .pytest_cache .mypy_cache .ruff_cache
