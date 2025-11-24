# s2s (script2storyboard)

A command-line tool to convert video scripts into animation storyboards interactively.

## Features

- **Interactive TUI**: Clean terminal interface with ANSI colors
- **Sentence-by-sentence workflow**: Process each sentence individually
- **Multiple animations per sentence**: Add as many animation checkboxes as needed
- **Easy navigation**: Jump between sentences with keyboard shortcuts
- **Auto-save**: Generates formatted markdown storyboard files
- **Progress persistence**: Automatically saves progress and resumes where you left off

## Installation

### Binary Installation (Recommended)

Download pre-built binaries for macOS and Linux from the [releases page](https://github.com/dnsimple/s2s/releases).

**Quick install (macOS/Linux):**
```bash
# Download and extract the latest release for your platform
# Then move to your PATH
sudo mv s2s /usr/local/bin/
chmod +x /usr/local/bin/s2s
```

See [docs/INSTALL.md](docs/INSTALL.md) for detailed installation instructions.

### From Source

No external dependencies required! Uses only Python 3 standard library.

```bash
# Run as a module
python3 -m s2s "path/to/script.md"

# Or install in development mode
pip install -e .
s2s "path/to/script.md"
```

### Development Setup

For development, we use `uv` for dependency management:

```bash
# Install dependencies
make install
# or manually:
uv sync
uv run pre-commit install
```

Available make commands:
- `make format` - Format code with Black
- `make test` - Run tests
- `make lint` - Run all pre-commit checks
- `make check` - Check formatting without modifying files
- `make build` - Build binary for current platform
- `make dist` - Create distribution package
- `make clean` - Clean build artifacts

## Usage

If you installed the binary:
```bash
s2s "path/to/script.md"
```

Or run from source:
```bash
python3 -m s2s "path/to/script.md"
```

### Example

```bash
s2s "examples/Vanity Name Servers Script.md"
```

## Interface

```
s2s                                                           1/25

                        Section Title

        Previous sentence appears here in dim text

    ╔════════════════════════════════════════════╗
    ║      Current sentence appears here         ║
    ╚════════════════════════════════════════════╝

    Animations:
      - [ ] Animation 1
      - [ ] Animation 2

    Enter animation:
    ┌──────────────────────────────────────────────┐
    │ Type your animation description here         │
    └──────────────────────────────────────────────┘
```

## Keyboard Shortcuts

### Input Mode (Default)
| Key | Action |
|-----|--------|
| `Enter` | Add current animation and prepare for next |
| `Ctrl+N` | Save current animation (if any) and move to next sentence |
| `Tab` | Enter browse mode to navigate existing animations |
| `[` | Go to previous sentence |
| `]` | Skip to next sentence |
| `Ctrl+S` | Save storyboard to file |
| `Ctrl+C` | Quit application |

### Browse Mode (Navigating Animations)
| Key | Action |
|-----|--------|
| `↑`/`k` | Move to previous animation |
| `↓`/`j` | Move to next animation |
| `i` | Edit selected animation |
| `d` | Delete selected animation |
| `Esc` | Return to input mode |
| `[` | Go to previous sentence |
| `]` | Skip to next sentence |
| `Ctrl+S` | Save storyboard to file |
| `Ctrl+C` | Quit application |

### Edit Mode (Modifying Animation)
| Key | Action |
|-----|--------|
| `Enter` | Save changes and return to browse mode |
| `Esc` | Cancel changes and return to browse mode |
| `←`/`→` | Move cursor left/right |
| `Backspace` | Delete character |
| `Ctrl+S` | Save storyboard to file |
| `Ctrl+C` | Quit application |

## Input Format

The tool expects markdown script files with:
- Frontmatter (optional, will be filtered out)
- Section headers (`#`, `##`, etc.)
- Body text with sentences

Example:
```markdown
---
tags:
  - project/video
---

# Introduction

This is the first sentence. This is the second sentence.

# Main Content

More content here.
```

## Output Format

Generates a storyboard markdown file in the `storyboards/` directory with:
- Original frontmatter reference
- Section headers
- Checkbox list items for each animation
- Newline separation between each sentence's animations

Example output:
```markdown
---
prev:
  - "[[Original Script]]"
tags:
  - "#storyboard"
---

# Introduction

- [ ] Show title card
- [ ] Fade in presenter

# Main Content

- [ ] Display diagram
- [ ] Highlight key points
```

## Editing Animations

s2s includes a vim-like interface for editing and managing animations:

### Modes

- **Input Mode** (default): Type and add new animations
- **Browse Mode**: Navigate through existing animations
- **Edit Mode**: Modify a selected animation

### How to Edit

1. **Enter Browse Mode**: Press `Tab` from input mode
2. **Navigate**: Use arrow keys or `j`/`k` to move between animations
3. **Edit**: Press `i` to edit the selected animation (highlighted in cyan)
4. **Save Changes**: Press `Enter` to save, or `Esc` to cancel
5. **Delete**: Press `d` in browse mode to remove an animation
6. **Return to Input**: Press `Esc` to go back to adding new animations

This makes it easy to fix typos, reword animations, or remove ones you no longer need without having to restart. The Tab key ensures you can type letters like 'j' or 'k' in your animation text without accidentally switching modes.

## Progress Persistence

s2s automatically saves your progress as you work, so you can stop at any time and pick up where you left off:

- **Automatic caching**: Progress is saved after each animation and navigation action
- **Resume work**: Simply run s2s on the same script file to continue from where you stopped
- **Cache location**: Progress is stored in `~/.cache/s2s/`
- **Storyboard output**: Generated files are saved in the `storyboards/` directory
- **Completion**: Cache is automatically cleared when you finish the entire script

To save your current storyboard and progress, press `Ctrl+S`. When you're ready to quit, press `Ctrl+C` - your progress will be saved automatically, and you can resume later.

## Tips

- One sentence can have multiple animations
- Animations can reference objects from previous sentences
- The tool auto-saves at the end of the session
- Use `Ctrl+S` to save progress at any time
- Navigate freely between sentences to revise animations
- You can stop work at any point and resume later without losing progress

## Testing

Run the test suite to verify functionality:

```bash
# Run all tests
python3 -m unittest discover tests -v

# Or run the test file directly
python3 tests/test_s2s.py -v
```

The test suite includes 27 tests covering:
- Sentence extraction and parsing
- TLD handling and preservation
- Script parsing with frontmatter and blockquotes
- Storyboard generation
- Integration workflows
- Edge cases

## Compatibility

Works with all modern terminals supporting ANSI escape codes:
- macOS Terminal
- iTerm2
- Linux terminals (gnome-terminal, konsole, etc.)
- Windows Terminal
- VS Code integrated terminal
