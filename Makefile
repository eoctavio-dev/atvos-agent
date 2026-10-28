PYTHON := python
PYTHON_FILES := agents check_setup.py

.PHONY: install install-dev lint format typecheck complexity test validate clean

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff format --check $(PYTHON_FILES)
	$(PYTHON) -m ruff check $(PYTHON_FILES)

format:
	$(PYTHON) -m ruff format $(PYTHON_FILES)

typecheck:
	$(PYTHON) -m mypy $(PYTHON_FILES)

complexity:
	$(PYTHON) -m xenon --max-absolute B --max-modules A --max-average A $(PYTHON_FILES)

test:
	$(PYTHON) -m pytest

validate: lint typecheck complexity test

clean:
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .adk -prune -exec rm -rf {} +
