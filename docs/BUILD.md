# Building s2s Binaries

This guide explains how to build standalone binaries of s2s for macOS and Linux.

## Prerequisites

- Python 3.10 or higher
- `uv` package manager (or standard pip/venv)

## Quick Start

```bash
# Install dependencies (including PyInstaller)
make install

# Build binary for your current platform
make build

# Binary will be in dist/s2s
./dist/s2s examples/VNS.md
```

## Building Distribution Packages

To create a distribution package with the binary and documentation:

```bash
make dist
```

This creates a compressed archive in `dist/` named like:
- `s2s-Darwin-arm64.tar.gz` (macOS Apple Silicon)
- `s2s-Darwin-x86_64.tar.gz` (macOS Intel)
- `s2s-Linux-x86_64.tar.gz` (Linux)

## Platform-Specific Instructions

### macOS

#### Build for your current architecture (Apple Silicon or Intel):
```bash
make build
```

#### Build universal binary (both architectures):
```bash
# On Apple Silicon Mac, build Intel version:
arch -x86_64 /usr/bin/python3 -m venv .venv-x86
source .venv-x86/bin/activate
pip install pyinstaller
pyinstaller s2s.spec --target-arch x86_64
deactivate

# Then build ARM version normally
make build
```

### Linux

```bash
make build
```

The binary will work on the same or newer Linux distributions. For maximum compatibility, build on the oldest Linux version you want to support (e.g., Ubuntu 20.04).

#### Building for different architectures:

To cross-compile for different architectures, use Docker:

```bash
# For x86_64
docker run -v $(pwd):/app -w /app python:3.10-slim bash -c "pip install pyinstaller && pyinstaller s2s.spec"

# For ARM64
docker run --platform linux/arm64 -v $(pwd):/app -w /app python:3.10-slim bash -c "pip install pyinstaller && pyinstaller s2s.spec"
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/build.yml`:

```yaml
name: Build Binaries

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install pyinstaller

      - name: Build binary
        run: pyinstaller s2s.spec --clean

      - name: Create distribution
        run: make dist

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: s2s-${{ runner.os }}-${{ runner.arch }}
          path: dist/*.tar.gz
```

## Testing the Binary

After building, test the binary:

```bash
# Run tests with the source
make test

# Test the binary
./dist/s2s examples/VNS.md

# Test on a fresh system by copying just the binary
cp dist/s2s /tmp/
cd /tmp
./s2s /path/to/script.md
```

## Binary Size Optimization

The default binary is ~10-15MB. To reduce size:

### Option 1: Use UPX (already enabled in s2s.spec)
```bash
# Install UPX
# macOS:
brew install upx

# Linux:
sudo apt-get install upx

# Build will automatically use UPX compression
make build
```

### Option 2: Exclude unnecessary modules

Edit `s2s.spec` and add to the `excludes` list:
```python
excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
```

## Troubleshooting

### "Permission denied" when running binary
```bash
chmod +x dist/s2s
```

### Binary crashes on startup
Check for missing shared libraries:
```bash
# macOS
otool -L dist/s2s

# Linux
ldd dist/s2s
```

### Import errors
Make sure all dependencies are declared in `hiddenimports` in `s2s.spec`.

### Terminal issues
The binary requires a terminal with ANSI color support. Test with:
```bash
echo $TERM
```

## Distribution

### Installing the binary

Users can install the binary by:

1. Download the appropriate archive for their platform
2. Extract it:
   ```bash
   tar -xzf s2s-*.tar.gz
   ```
3. Move the binary to a location in PATH:
   ```bash
   sudo mv s2s-*/s2s /usr/local/bin/
   # or for user-only install:
   mkdir -p ~/.local/bin
   mv s2s-*/s2s ~/.local/bin/
   ```
4. Make it executable:
   ```bash
   chmod +x /usr/local/bin/s2s
   # or
   chmod +x ~/.local/bin/s2s
   ```

### Homebrew (macOS)

To distribute via Homebrew, create a formula:

```ruby
class S2s < Formula
  desc "Convert video scripts to animation storyboards interactively"
  homepage "https://github.com/dnsimple/s2s"
  url "https://github.com/dnsimple/s2s/releases/download/v0.1.0/s2s-Darwin-arm64.tar.gz"
  sha256 "..." # Calculate with: shasum -a 256 s2s-Darwin-arm64.tar.gz
  version "0.1.0"

  def install
    bin.install "s2s"
  end

  test do
    assert_match "Usage:", shell_output("#{bin}/s2s 2>&1", 1)
  end
end
```

## Clean Up

Remove build artifacts:

```bash
make clean
```
