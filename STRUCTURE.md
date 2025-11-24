# Project Structure

This document describes the reorganized structure of the s2s project following Python best practices.

## Directory Layout

```
s2s/
├── src/                    # Source code
│   └── s2s/
│       ├── __init__.py     # Package initialization
│       ├── __main__.py     # Entry point for 'python -m s2s'
│       └── cli.py          # Main application code
│
├── docs/                   # Documentation
│   ├── BUILD.md            # Build instructions
│   ├── INSTALL.md          # Installation guide
│   ├── PACKAGING_SUMMARY.md # Packaging overview
│   ├── QUICKSTART.md       # Quick start guide
│   └── RELEASE.md          # Release process
│
├── scripts/                # Development scripts
│   ├── build.sh            # Build binary
│   └── verify_packaging.sh # Verify setup
│
├── tests/                  # Test suite
│   ├── __init__.py
│   └── test_s2s.py         # Unit tests
│
├── examples/               # Example scripts
├── storyboards/            # Generated storyboards
│
├── .github/                # GitHub Actions workflows
│   └── workflows/
│       ├── build.yml       # Binary builds
│       └── test.yml        # CI tests
│
├── README.md               # Main documentation
├── pyproject.toml          # Project configuration
├── Makefile                # Build automation
├── s2s.spec                # PyInstaller config
├── s2s.py                  # Backwards compat wrapper
├── requirements.txt        # Dependencies (none!)
└── VERSION                 # Version tracking
```

## Key Changes from Original Structure

### Before
```
s2s/
├── s2s.py                  # Monolithic script
├── BUILD.md
├── INSTALL.md
├── QUICKSTART.md
├── RELEASE.md
├── build.sh
├── verify_packaging.sh
└── tests/
```

### After (Standard Python Layout)
```
s2s/
├── src/s2s/               # Proper package
├── docs/                   # All documentation
├── scripts/                # Development tools
└── tests/                  # Tests
```

## Benefits

1. **Standard Layout**: Follows Python packaging best practices
2. **Clean Root**: Root directory is uncluttered with only essential files
3. **Clear Separation**: Source, docs, and scripts are clearly separated
4. **Easier Navigation**: Related files are grouped together
5. **Better IDE Support**: Modern IDEs recognize this structure
6. **Easier Testing**: Test imports are more straightforward

## How to Use

### Running from Source

```bash
# As a module (recommended)
python3 -m s2s "path/to/script.md"

# Using the wrapper (backwards compatibility)
./s2s.py "path/to/script.md"

# After installing in development mode
pip install -e .
s2s "path/to/script.md"
```

### Building

```bash
# Using the build script
./scripts/build.sh

# Or using make
make build

# Create distribution
make dist
```

### Running Tests

```bash
# With pytest
PYTHONPATH=src pytest tests/ -v

# Or using make
make test
```

### Verification

```bash
# Check packaging setup
./scripts/verify_packaging.sh
```

## Import Structure

The package is now properly structured for imports:

```python
# Main entry point
from s2s import main

# Internal modules (from within the package)
from s2s.cli import ScriptParser, StoryboardGenerator, S2SApp
```

## Configuration Updates

All configuration files have been updated to work with the new structure:

- **pyproject.toml**: Entry point updated to `s2s.cli:main`, packages configured
- **s2s.spec**: PyInstaller points to `src/s2s/cli.py`
- **Makefile**: PYTHONPATH includes `src/`
- **tests/**: Import paths updated
- **.gitignore**: Updated to include new directories

## Backwards Compatibility

The root `s2s.py` file is maintained as a wrapper for backwards compatibility:
- Existing scripts that run `./s2s.py` will continue to work
- The wrapper adds `src/` to the Python path and imports the real module

## Migration Notes

If you have existing code that imports from s2s:

**Old:**
```python
from s2s import ScriptParser
```

**New:**
```python
from s2s.cli import ScriptParser
```

Or install the package and use:
```python
from s2s import main
```

## Documentation Organization

All user-facing documentation is now in `docs/`:

- **BUILD.md**: Technical build instructions
- **INSTALL.md**: User installation guide
- **QUICKSTART.md**: Quick getting started
- **RELEASE.md**: Release process for maintainers
- **PACKAGING_SUMMARY.md**: Overview of packaging setup

Keep README.md in the root for GitHub/project homepage.

## Scripts Organization

Development and build scripts are in `scripts/`:

- **build.sh**: Interactive build script
- **verify_packaging.sh**: Packaging verification

All scripts are designed to run from the project root:
```bash
./scripts/build.sh
```

## Future Improvements

With this structure, you can easily add:

1. **src/s2s/modules/**: Separate modules for different functionality
2. **docs/api/**: API documentation
3. **scripts/release.sh**: Automated release script
4. **benchmarks/**: Performance benchmarks
5. **docker/**: Docker configurations

The structure scales well as the project grows!
