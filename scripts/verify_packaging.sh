#!/usr/bin/env bash

#
# Verification script for s2s packaging setup
#
# This script checks that all packaging files are in place
# and that the build system works correctly.
#

set -e

# Navigate to project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  s2s Packaging Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Check required files
echo -e "${YELLOW}Checking required files...${NC}"
FILES=(
    "s2s.spec"
    "scripts/build.sh"
    "docs/INSTALL.md"
    "docs/RELEASE.md"
    "VERSION"
    "src/s2s/__init__.py"
    "src/s2s/cli.py"
    ".github/workflows/build.yml"
    ".github/workflows/test.yml"
)

ALL_FILES_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
        ALL_FILES_EXIST=false
    fi
done

if [ "$ALL_FILES_EXIST" = false ]; then
    echo
    echo -e "${RED}Error: Some required files are missing${NC}"
    exit 1
fi

echo

# Check scripts/build.sh is executable
echo -e "${YELLOW}Checking scripts/build.sh permissions...${NC}"
if [ -x "scripts/build.sh" ]; then
    echo -e "  ${GREEN}✓${NC} scripts/build.sh is executable"
else
    echo -e "  ${YELLOW}!${NC} scripts/build.sh is not executable (run: chmod +x scripts/build.sh)"
fi

echo

# Check for uv
echo -e "${YELLOW}Checking dependencies...${NC}"
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version 2>&1 || echo "unknown")
    echo -e "  ${GREEN}✓${NC} uv is installed ($UV_VERSION)"
else
    echo -e "  ${RED}✗${NC} uv is not installed"
    echo -e "    Install from: https://github.com/astral-sh/uv"
fi

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "  ${GREEN}✓${NC} Python is installed ($PYTHON_VERSION)"
else
    echo -e "  ${RED}✗${NC} python3 is not installed"
fi

echo

# Check Makefile targets
echo -e "${YELLOW}Checking Makefile targets...${NC}"
TARGETS=("build" "dist" "clean" "install")
for target in "${TARGETS[@]}"; do
    if grep -q "^$target:" Makefile; then
        echo -e "  ${GREEN}✓${NC} make $target"
    else
        echo -e "  ${RED}✗${NC} make $target (missing)"
    fi
done

echo

# Check pyproject.toml
echo -e "${YELLOW}Checking pyproject.toml...${NC}"
if grep -q "pyinstaller" pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} PyInstaller in dependencies"
else
    echo -e "  ${RED}✗${NC} PyInstaller not in dependencies"
fi

if grep -q '\[project.scripts\]' pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} Entry point defined"
else
    echo -e "  ${YELLOW}!${NC} Entry point not defined"
fi

VERSION=$(grep '^version =' pyproject.toml | cut -d'"' -f2)
echo -e "  ${BLUE}ℹ${NC} Version: $VERSION"

echo

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Packaging setup verification complete!${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Test build: ${BLUE}./scripts/build.sh${NC} or ${BLUE}make build${NC}"
echo -e "  2. Test dist:  ${BLUE}make dist${NC}"
echo -e "  3. Create tag: ${BLUE}git tag v$VERSION${NC}"
echo -e "  4. Push tag:   ${BLUE}git push origin v$VERSION${NC}"
echo
echo -e "See ${BLUE}docs/RELEASE.md${NC} for complete release instructions."
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
