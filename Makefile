.PHONY: format test lint check install

# Format code with Black
format:
	uv run black .

# Run tests
test:
	uv run pytest tests/ -v

# Run linting checks
lint:
	uv run pre-commit run --all-files

# Check formatting without modifying files
check:
	uv run black --check .

# Install dependencies and pre-commit hooks
install:
	uv sync
	uv run pre-commit install
