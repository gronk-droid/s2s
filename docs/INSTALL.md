# Installation Guide

## Binary Installation (Recommended)

Pre-built binaries are available for macOS and Linux. Download the appropriate binary for your platform from the [releases page](https://github.com/dnsimple/s2s/releases).

### macOS

```bash
# Download the latest release (replace VERSION with actual version)
curl -LO https://github.com/dnsimple/s2s/releases/download/VERSION/s2s-Darwin-arm64.tar.gz

# For Intel Macs, use:
# curl -LO https://github.com/dnsimple/s2s/releases/download/VERSION/s2s-Darwin-x86_64.tar.gz

# Extract
tar -xzf s2s-Darwin-arm64.tar.gz

# Move to a directory in your PATH
sudo mv s2s-Darwin-arm64/s2s /usr/local/bin/

# Make it executable (if needed)
chmod +x /usr/local/bin/s2s

# Verify installation
s2s
```

### Linux

```bash
# Download the latest release (replace VERSION with actual version)
curl -LO https://github.com/dnsimple/s2s/releases/download/VERSION/s2s-Linux-x86_64.tar.gz

# Extract
tar -xzf s2s-Linux-x86_64.tar.gz

# Move to a directory in your PATH
sudo mv s2s-Linux-x86_64/s2s /usr/local/bin/

# Make it executable (if needed)
chmod +x /usr/local/bin/s2s

# Verify installation
s2s
```

## From Source

If you prefer to run from source or want to contribute:

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/dnsimple/s2s.git
cd s2s

# Install dependencies
make install

# Run directly
uv run python s2s.py "path/to/script.md"
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/dnsimple/s2s.git
cd s2s

# Install in development mode
pip install -e .

# Run
s2s "path/to/script.md"
```

### Using Python directly

```bash
# Clone the repository
git clone https://github.com/dnsimple/s2s.git
cd s2s

# Run (no dependencies needed!)
python3 s2s.py "path/to/script.md"
```

## Building from Source

If you want to build your own binary:

```bash
# Install development dependencies
make install

# Build binary for your platform
make build

# The binary will be in dist/s2s
./dist/s2s "path/to/script.md"

# Create distribution package
make dist
```

The built binary will work on any compatible system without requiring Python to be installed.

## System Requirements

### Runtime
- macOS 10.13+ or Linux with glibc 2.17+
- Terminal with ANSI color support
- No Python installation required for binary installations

### Development
- Python 3.10+
- make
- uv (or pip)

## Troubleshooting

### macOS: "cannot be opened because the developer cannot be verified"

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine /usr/local/bin/s2s
```

### Linux: Permission denied

```bash
# Make the binary executable
chmod +x /usr/local/bin/s2s
```

### Binary not found in PATH

Make sure `/usr/local/bin` is in your PATH:

```bash
echo $PATH
```

If not, add it to your shell configuration (~/.bashrc, ~/.zshrc, etc.):

```bash
export PATH="/usr/local/bin:$PATH"
```

## Uninstallation

### Binary Installation

```bash
sudo rm /usr/local/bin/s2s
```

### Source Installation

```bash
pip uninstall s2s
```

Or simply delete the cloned repository directory.
