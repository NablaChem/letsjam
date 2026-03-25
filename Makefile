.PHONY: test install clean help

help:
	@echo "Available targets:"
	@echo "  test      - Run pytest on the test suite"
	@echo "  install   - Install the package in editable mode"
	@echo "  clean     - Remove build artifacts and cache"

test:
	python -m pytest tests/ -v

install:
	pip install -e .

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache
