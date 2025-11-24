# Release Process

This document describes how to build and release s2s binaries for macOS and Linux.

## Prerequisites

- Git
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- GitHub CLI (optional, for creating releases)

## Version Numbering

s2s follows [Semantic Versioning](https://semver.org/):
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- Increment MAJOR for breaking changes
- Increment MINOR for new features
- Increment PATCH for bug fixes

## Local Build

### Build for Current Platform

```bash
# Build binary
./build.sh

# Or use make
make build

# Create distribution package
make dist
```

The binary will be in `dist/s2s` and the distribution package in `dist/s2s-{OS}-{ARCH}.tar.gz`.

### Test the Binary

```bash
# Test basic functionality
./dist/s2s

# Test with an example
./dist/s2s "examples/Vanity Name Servers Script.md"
```

## Creating a Release

### 1. Update Version

Update the version in `pyproject.toml`:

```toml
[project]
version = "X.Y.Z"
```

### 2. Commit Changes

```bash
git add pyproject.toml
git commit -m "Bump version to vX.Y.Z"
```

### 3. Create and Push Tag

```bash
# Create annotated tag
git tag -a vX.Y.Z -m "Release version X.Y.Z"

# Push commits and tags
git push origin trunk
git push origin vX.Y.Z
```

### 4. GitHub Actions Builds

Once the tag is pushed, GitHub Actions will automatically:
1. Build binaries for macOS and Linux
2. Create a GitHub release
3. Upload the distribution packages

Monitor the build at: https://github.com/dnsimple/s2s/actions

### 5. Update Release Notes

After the release is created:
1. Go to https://github.com/dnsimple/s2s/releases
2. Edit the release for your tag
3. Add release notes following this template:

```markdown
## What's New

- Feature 1
- Feature 2
- Bug fix 1

## Installation

Download the appropriate binary for your platform:

**macOS (Apple Silicon):**
```bash
curl -LO https://github.com/dnsimple/s2s/releases/download/vX.Y.Z/s2s-Darwin-arm64.tar.gz
tar -xzf s2s-Darwin-arm64.tar.gz
sudo mv s2s-Darwin-arm64/s2s /usr/local/bin/
chmod +x /usr/local/bin/s2s
```

**macOS (Intel):**
```bash
curl -LO https://github.com/dnsimple/s2s/releases/download/vX.Y.Z/s2s-Darwin-x86_64.tar.gz
tar -xzf s2s-Darwin-x86_64.tar.gz
sudo mv s2s-Darwin-x86_64/s2s /usr/local/bin/
chmod +x /usr/local/bin/s2s
```

**Linux:**
```bash
curl -LO https://github.com/dnsimple/s2s/releases/download/vX.Y.Z/s2s-Linux-x86_64.tar.gz
tar -xzf s2s-Linux-x86_64.tar.gz
sudo mv s2s-Linux-x86_64/s2s /usr/local/bin/
chmod +x /usr/local/bin/s2s
```

## Checksums

[GitHub will auto-generate these]

## Full Changelog

https://github.com/dnsimple/s2s/compare/vX.Y.Z-1...vX.Y.Z
```

## Manual Release (Without CI)

If you need to create a release manually:

### Build on macOS

```bash
# On macOS (Intel or Apple Silicon)
./build.sh
make dist
```

### Build on Linux

```bash
# On Linux (x86_64)
./build.sh
make dist
```

### Create GitHub Release

Using GitHub CLI:

```bash
# Create release with files
gh release create vX.Y.Z \
  dist/s2s-*.tar.gz \
  --title "Release vX.Y.Z" \
  --notes "Release notes here"
```

Or manually:
1. Go to https://github.com/dnsimple/s2s/releases/new
2. Select your tag
3. Add title and release notes
4. Upload the `dist/s2s-*.tar.gz` files
5. Publish release

## Testing Releases

Before publishing:

```bash
# Extract the package
tar -xzf dist/s2s-*.tar.gz

# Test the binary
./s2s-*/s2s "examples/Vanity Name Servers Script.md"

# Check file size (should be ~9-10MB compressed)
ls -lh dist/s2s-*.tar.gz
```

## Troubleshooting

### Build fails with "uv not found"

Install uv: https://github.com/astral-sh/uv

### Binary size is too large

Check that PyInstaller is using the correct settings in `s2s.spec`. The binary should be around 9-10MB compressed.

### Binary doesn't work on older macOS/Linux

Ensure you're building on a system with compatible minimum versions:
- macOS: 10.13+ (High Sierra)
- Linux: glibc 2.17+ (Ubuntu 14.04+, CentOS 7+)

### GitHub Actions fails

Check:
1. The workflow file syntax in `.github/workflows/build.yml`
2. GitHub Actions are enabled for the repository
3. You have push access to the repository

## Version History

- v0.1.0 - Initial release with basic functionality
