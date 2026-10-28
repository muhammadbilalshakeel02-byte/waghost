.PHONY: help dev test lint fmt build clean install

help:
	@grep -E '^[a-z-]+:' Makefile | cut -d: -f1

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest -q --cov=waghost

lint:
	ruff check waghost tests

fmt:
	ruff format waghost tests

build: clean
	python -m build

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} +