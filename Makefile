.PHONY: format test lint check install build install-bin clean dist

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

# Build binary for current platform
build:
	PYTHONPATH=src uv run pyinstaller s2s.spec --clean

# Install binary to /usr/local/bin/s2s (run with sudo: sudo make install-bin)
install-bin: build
	install -m 755 dist/s2s /usr/local/bin/s2s
	@echo "Installed s2s to /usr/local/bin/s2s"

# Build binary and create distribution package
dist: clean build
	mkdir -p dist/s2s-$(shell uname -s)-$(shell uname -m)
	cp dist/s2s dist/s2s-$(shell uname -s)-$(shell uname -m)/
	cp README.md dist/s2s-$(shell uname -s)-$(shell uname -m)/
	cp docs/INSTALL.md dist/s2s-$(shell uname -s)-$(shell uname -m)/ || true
	cd dist && tar -czf s2s-$(shell uname -s)-$(shell uname -m).tar.gz s2s-$(shell uname -s)-$(shell uname -m)
	@echo "Distribution package created: dist/s2s-$(shell uname -s)-$(shell uname -m).tar.gz"

# Clean build artifacts
clean:
	rm -rf build dist __pycache__ *.spec.bak
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
