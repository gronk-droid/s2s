#!/usr/bin/env bash

#
# Build script for s2s binary
#
# Usage:
#   ./build.sh           # Build for current platform
#   ./build.sh --clean   # Clean and build
#

set -e

# Navigate to project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
CLEAN=false
if [[ "$1" == "--clean" ]]; then
    CLEAN=true
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Building s2s binary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Detect platform
OS=$(uname -s)
ARCH=$(uname -m)
echo -e "${YELLOW}Platform:${NC} $OS $ARCH"
echo

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed${NC}"
    echo "Install it from: https://github.com/astral-sh/uv"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${YELLOW}Python version:${NC} $PYTHON_VERSION"
echo

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    make clean
    echo
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
uv sync
echo

# Build binary
echo -e "${YELLOW}Building binary with PyInstaller...${NC}"
PYTHONPATH=src uv run pyinstaller s2s.spec --clean
echo

# Check if build succeeded
if [ -f "dist/s2s" ]; then
    echo -e "${GREEN}✓ Build successful!${NC}"
    echo

    # Get file info
    FILE_SIZE=$(du -h "dist/s2s" | cut -f1)
    echo -e "${YELLOW}Binary location:${NC} dist/s2s"
    echo -e "${YELLOW}Binary size:${NC} $FILE_SIZE"
    echo

    # Test the binary
    echo -e "${YELLOW}Testing binary...${NC}"
    if ./dist/s2s 2>&1 | grep -q "Usage"; then
        echo -e "${GREEN}✓ Binary is working${NC}"
    else
        echo -e "${YELLOW}! Binary runs but usage message not detected${NC}"
    fi
    echo

    echo -e "${GREEN}You can now run:${NC}"
    echo -e "  ${BLUE}./dist/s2s \"path/to/script.md\"${NC}"
    echo
    echo -e "${GREEN}To create a distribution package:${NC}"
    echo -e "  ${BLUE}make dist${NC}"
    echo
else
    echo -e "${RED}✗ Build failed${NC}"
    echo "Check the output above for errors."
    exit 1
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
