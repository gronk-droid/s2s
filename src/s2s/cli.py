#!/usr/bin/env python3
"""
s2s (script2storyboard) - Convert video scripts to animation storyboards
"""

import sys
import os
import re
import tty
import termios
import json
import hashlib
from typing import List, Dict, Tuple
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_WHITE = "\033[47m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_WHITE = "\033[97m"


class TerminalControl:
    """Terminal control utilities"""

    @staticmethod
    def clear_screen():
        """Clear the terminal screen"""
        print("\033[2J", end="")

    @staticmethod
    def move_cursor(row, col):
        """Move cursor to specific position (1-indexed)"""
        print(f"\033[{row};{col}H", end="")

    @staticmethod
    def hide_cursor():
        """Hide the cursor"""
        print("\033[?25l", end="")

    @staticmethod
    def show_cursor():
        """Show the cursor"""
        print("\033[?25h", end="")

    @staticmethod
    def get_terminal_size():
        """Get terminal dimensions"""
        try:
            size = os.get_terminal_size()
            return size.lines, size.columns
        except (OSError, ValueError):
            return 24, 80  # Default fallback


class ScriptParser:
    """Parse markdown script files"""

    @staticmethod
    def parse_script(filepath: str) -> List[Dict]:
        """Parse script file into sections and sentences"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

        # Remove blockquotes and their content
        content = re.sub(r"^>.*$", "", content, flags=re.MULTILINE)

        # Split content by headers
        # Match headers and capture both the header and the content until the next header
        section_pattern = r"^(#{1,6})\s+(.+?)$"

        sections = []
        current_section = None
        current_content = []

        for line in content.split("\n"):
            header_match = re.match(section_pattern, line.strip())

            if header_match:
                # Save previous section if exists
                if current_section:
                    # Join content lines preserving line breaks (use newline for paragraph breaks)
                    full_text = "\n".join(current_content)
                    sentences = ScriptParser.extract_sentences(full_text)
                    current_section["sentences"] = sentences
                    sections.append(current_section)

                # Start new section
                header_text = header_match.group(2).strip()
                current_section = {"title": header_text, "sentences": []}
                current_content = []
            elif current_section:
                # Add non-empty lines to current content
                stripped = line.strip()
                if stripped and not stripped.startswith("["):
                    current_content.append(stripped)

        # Add last section
        if current_section:
            full_text = "\n".join(current_content)
            sentences = ScriptParser.extract_sentences(full_text)
            current_section["sentences"] = sentences
            sections.append(current_section)

        return sections

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """Extract sentences from text using regex"""
        if not text.strip():
            return []

        # Find all sentences with their punctuation
        # Pattern: starts with capital letter, matches any content (including .BANK etc),
        # ends with .!? followed by whitespace or end of text
        # Use non-greedy matching to stop at the first sentence-ending punctuation
        sentence_pattern = r"[A-Z].*?[.!?](?=\s|$)"

        sentences = re.findall(sentence_pattern, text, re.DOTALL)

        # Clean up sentences - remove extra whitespace and newlines within sentences
        cleaned = []
        for sentence in sentences:
            # Replace multiple whitespace/newlines with single space
            sentence = re.sub(r"\s+", " ", sentence)
            sentence = sentence.strip()
            if sentence and len(sentence) > 1:
                cleaned.append(sentence)

        return cleaned


class StoryboardGenerator:
    """Generate storyboard markdown files"""

    @staticmethod
    def generate(
        input_file: str, sections: List[Dict], animations: Dict[str, List[str]]
    ) -> str:
        """Generate storyboard markdown content"""
        lines = []

        # Add frontmatter
        input_name = Path(input_file).stem
        lines.append("---")
        lines.append("prev:")
        lines.append(f'  - "[[{input_name}]]"')
        lines.append("tags:")
        lines.append('  - "#storyboard"')
        lines.append("---")
        lines.append("")

        # Add sections with animations
        for section in sections:
            lines.append(f"# {section['title']}")
            lines.append("")

            for sentence in section["sentences"]:
                if sentence in animations and animations[sentence]:
                    for animation in animations[sentence]:
                        lines.append(f"- [ ] {animation}")
                lines.append("")

        return "\n".join(lines)


class S2SApp:
    """Main application for s2s"""

    def __init__(self, script_file: str):
        self.script_file = script_file
        self.sections = ScriptParser.parse_script(script_file)

        # Flatten sentences with section references
        self.items = []
        for section in self.sections:
            for sentence in section["sentences"]:
                self.items.append(
                    {
                        "section": section["title"],
                        "sentence": sentence,
                        "animations": [],
                    }
                )

        self.current_index = 0
        self.current_animation = ""
        self.old_settings = None

        # Mode system for vim-like editing
        self.mode = "input"  # 'input', 'browse', 'edit', 'edit_sentence'
        self.selected_animation_index = (
            -1
        )  # -1 means input box, 0+ means animation index
        self.current_sentence_edit = ""  # Buffer for editing sentences

        # View mode system
        self.view_mode = "line-by-line"  # 'line-by-line', 'review'
        self.review_scroll_offset = (
            0  # For scrolling through all sentences in review mode
        )
        self.review_focus = "script"  # 'script' or 'animations' - which column is focused in review mode
        self.show_help = False  # Toggle detailed help with ?

        # Load progress from cache if it exists
        self._load_progress()

    def _get_cache_dir(self) -> Path:
        """Get cache directory path"""
        cache_dir = Path.home() / ".cache" / "s2s"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_cache_file(self) -> Path:
        """Get cache file path for current script"""
        # Use hash of absolute script path to create unique cache filename
        script_path = Path(self.script_file).resolve()
        script_hash = hashlib.md5(str(script_path).encode()).hexdigest()
        cache_dir = self._get_cache_dir()
        return cache_dir / f"{script_hash}.json"

    def _save_progress(self):
        """Save current progress to cache"""
        cache_file = self._get_cache_file()

        # Prepare data to cache
        cache_data = {
            "script_file": str(Path(self.script_file).resolve()),
            "current_index": self.current_index,
            "items": self.items,
        }

        # Write cache file
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

    def _load_progress(self):
        """Load progress from cache if available"""
        cache_file = self._get_cache_file()

        if not cache_file.exists():
            return

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Verify this is the same script file
            cached_script = cache_data.get("script_file")
            if cached_script == str(Path(self.script_file).resolve()):
                # Restore progress
                self.current_index = cache_data.get("current_index", 0)
                cached_items = cache_data.get("items", [])

                # Merge cached animations with current items
                # This handles cases where the script might have changed
                for i, item in enumerate(self.items):
                    if i < len(cached_items):
                        cached_item = cached_items[i]
                        # If sentence matches, restore animations
                        if cached_item["sentence"] == item["sentence"]:
                            item["animations"] = cached_item["animations"]
        except (json.JSONDecodeError, KeyError, IOError):
            # If cache is corrupted or invalid, just start fresh
            pass

    def _clear_cache(self):
        """Clear cache file for current script"""
        cache_file = self._get_cache_file()
        if cache_file.exists():
            cache_file.unlink()

    def setup_terminal(self):
        """Setup terminal for raw input"""
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

    def restore_terminal(self):
        """Restore terminal settings"""
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def read_key(self) -> str:
        """Read a single key or key sequence"""
        char = sys.stdin.read(1)

        # Handle escape sequences
        if char == "\x1b":  # ESC
            next_char = sys.stdin.read(1)
            if next_char == "[":
                # Read the rest of the sequence
                third = sys.stdin.read(1)
                # Check for modified keys (like Shift+Enter: ESC[13;2~)
                if third.isdigit():
                    # Read until we get the final character
                    sequence = third
                    while True:
                        next_c = sys.stdin.read(1)
                        sequence += next_c
                        if next_c.isalpha() or next_c == "~":
                            break
                    return f"\x1b[{sequence}"
                return f"\x1b[{third}"
            return char

        return char

    def find_next_word_boundary(self, text: str, pos: int) -> int:
        """Find the next word boundary for cursor movement"""
        if pos >= len(text):
            return len(text)

        # Skip current word
        while pos < len(text) and text[pos] not in (" ", "\t", "\n"):
            pos += 1

        # Skip whitespace
        while pos < len(text) and text[pos] in (" ", "\t", "\n"):
            pos += 1

        return pos

    def find_prev_word_boundary(self, text: str, pos: int) -> int:
        """Find the previous word boundary for cursor movement"""
        if pos <= 0:
            return 0

        # Move back one position
        pos -= 1

        # Skip whitespace
        while pos > 0 and text[pos] in (" ", "\t", "\n"):
            pos -= 1

        # Skip current word
        while pos > 0 and text[pos - 1] not in (" ", "\t", "\n"):
            pos -= 1

        return pos

    def delete_word_backward(self, buffer: list, cursor_pos: int) -> tuple:
        """Delete word backward from cursor position, returns (new_buffer, new_cursor_pos)"""
        if cursor_pos <= 0:
            return buffer, cursor_pos

        text = "".join(buffer)
        new_pos = self.find_prev_word_boundary(text, cursor_pos)

        # Delete from new_pos to cursor_pos
        del buffer[new_pos:cursor_pos]

        return buffer, new_pos

    def delete_word_forward(self, buffer: list, cursor_pos: int) -> tuple:
        """Delete word forward from cursor position, returns (new_buffer, new_cursor_pos)"""
        if cursor_pos >= len(buffer):
            return buffer, cursor_pos

        text = "".join(buffer)
        end_pos = self.find_next_word_boundary(text, cursor_pos)

        # Delete from cursor_pos to end_pos
        del buffer[cursor_pos:end_pos]

        return buffer, cursor_pos

    def get_input_line(self) -> Tuple[str, str]:
        """Get input line with editing support, returns (text, action)"""
        # Determine which buffer to use based on mode
        if self.mode == "edit_sentence":
            buffer = list(self.current_sentence_edit)
        else:
            buffer = list(self.current_animation)
        cursor_pos = len(buffer)

        while True:
            # Redraw the input area
            self.draw_screen()

            rows, cols = TerminalControl.get_terminal_size()

            # Display buffer in appropriate location based on view mode
            if self.view_mode == "review":
                # In review mode, render inline input based on focus
                if self.review_focus == "script" and self.mode == "edit_sentence":
                    # Editing sentence on the left side
                    mid_col = cols // 2
                    left_col_width = mid_col - 4
                    max_text_width = left_col_width - 4  # Account for "► " prefix

                    # Calculate which row the current sentence is on
                    content_start_row = 5
                    sentence_row = content_start_row
                    last_section = None
                    for i in range(self.review_scroll_offset, self.current_index + 1):
                        if i == self.current_index:
                            break
                        item = self.items[i]

                        # Account for section headers
                        if item["section"] != last_section:
                            if last_section is not None:
                                sentence_row += 1  # spacing before section
                            sentence_row += 1  # section header row
                            last_section = item["section"]

                        wrapped = self.wrap_text(item["sentence"], left_col_width)
                        sentence_row += (
                            max(
                                len(wrapped),
                                len(item["animations"]) if item["animations"] else 1,
                            )
                            + 1
                        )

                    # Check if current sentence is in a new section
                    current_item = self.items[self.current_index]
                    if current_item["section"] != last_section:
                        if last_section is not None:
                            sentence_row += 1  # spacing before section
                        sentence_row += 1  # section header row

                    display_text = "".join(buffer)
                    wrapped_edit = self.wrap_text(
                        display_text if display_text else " ", left_col_width - 2
                    )

                    # Display wrapped text inline
                    for line_idx, line in enumerate(wrapped_edit):
                        if sentence_row + line_idx < rows:
                            TerminalControl.move_cursor(sentence_row + line_idx, 4)
                            if line_idx == 0:
                                print(f"{Colors.CYAN}► {line}{Colors.RESET}", end="")
                            else:
                                print(f"{Colors.CYAN}  {line}{Colors.RESET}", end="")
                            # Clear rest of line
                            remaining = left_col_width - len(line) - 2
                            if remaining > 0:
                                print(" " * remaining, end="")

                    # Position cursor on the appropriate wrapped line
                    char_count = 0
                    cursor_line = 0
                    cursor_col = 0
                    for line_idx, line in enumerate(wrapped_edit):
                        if char_count + len(line) >= cursor_pos:
                            cursor_line = line_idx
                            cursor_col = cursor_pos - char_count
                            break
                        char_count += len(line) + 1  # +1 for space

                    TerminalControl.move_cursor(
                        sentence_row + cursor_line, 4 + cursor_col + 2
                    )
                    TerminalControl.show_cursor()

                elif self.review_focus == "animations":
                    # Render inline on the right side
                    mid_col = cols // 2
                    right_col_width = cols - mid_col - 4
                    max_text_width = right_col_width - 6  # Account for "- [ ] " prefix

                    # Calculate which row the current sentence is on
                    # This requires finding the current sentence in the visible area
                    content_start_row = 5
                    sentence_row = content_start_row
                    last_section = None
                    for i in range(self.review_scroll_offset, self.current_index + 1):
                        if i == self.current_index:
                            break
                        item = self.items[i]

                        # Account for section headers
                        if item["section"] != last_section:
                            if last_section is not None:
                                sentence_row += 1  # spacing before section
                            sentence_row += 1  # section header row
                            last_section = item["section"]

                        left_col_width = mid_col - 4
                        wrapped = self.wrap_text(item["sentence"], left_col_width)
                        sentence_row += (
                            max(
                                len(wrapped),
                                len(item["animations"]) if item["animations"] else 1,
                            )
                            + 1
                        )

                    # Check if current sentence is in a new section
                    current_item = self.items[self.current_index]
                    if current_item["section"] != last_section:
                        if last_section is not None:
                            sentence_row += 1  # spacing before section
                        sentence_row += 1  # section header row
                    if self.mode == "edit":
                        # Check if editing existing or adding new
                        if (
                            self.selected_animation_index >= 0
                            and self.selected_animation_index
                            < len(current_item["animations"])
                        ):
                            # Editing existing animation
                            animation_row = sentence_row + self.selected_animation_index
                        else:
                            # Adding new animation (selected_animation_index is invalid)
                            animation_row = sentence_row + len(
                                current_item["animations"]
                            )
                    else:
                        # Adding new animation
                        animation_row = sentence_row + len(current_item["animations"])

                    display_text = "".join(buffer)
                    text_offset = 0
                    if cursor_pos > max_text_width:
                        text_offset = cursor_pos - max_text_width

                    visible_text = display_text[
                        text_offset : text_offset + max_text_width
                    ]
                    visible_cursor_pos = cursor_pos - text_offset

                    # Display text inline
                    TerminalControl.move_cursor(
                        animation_row, mid_col + 8
                    )  # After "> [ ] "
                    print(f"{Colors.CYAN}{visible_text}{Colors.RESET}", end="")

                    # Clear rest of line
                    remaining_space = max_text_width - len(visible_text)
                    if remaining_space > 0:
                        print(" " * remaining_space, end="")

                    # Position cursor (only show when editing/adding animations)
                    if self.mode == "browse":
                        TerminalControl.hide_cursor()
                    else:
                        TerminalControl.move_cursor(
                            animation_row, mid_col + 8 + visible_cursor_pos
                        )
                        TerminalControl.show_cursor()
                else:
                    # Focused on script - just hide cursor, don't render anything inline
                    TerminalControl.hide_cursor()
            else:
                # In line-by-line mode, use the input box at bottom
                input_y = rows - 6
                input_box_width = min(cols - 4, 80)
                input_x = (cols - input_box_width) // 2
                max_text_width = input_box_width - 4

                display_text = "".join(buffer)
                text_offset = 0
                if cursor_pos > max_text_width:
                    text_offset = cursor_pos - max_text_width

                visible_text = display_text[text_offset : text_offset + max_text_width]
                visible_cursor_pos = cursor_pos - text_offset

                TerminalControl.move_cursor(input_y + 1, input_x + 2)
                print(f"{Colors.CYAN}{visible_text}{Colors.RESET}", end="")

                remaining_space = max_text_width - len(visible_text)
                if remaining_space > 0:
                    print(" " * remaining_space, end="")

                if self.mode == "browse":
                    TerminalControl.hide_cursor()
                else:
                    TerminalControl.move_cursor(
                        input_y + 1, input_x + 2 + visible_cursor_pos
                    )
                    TerminalControl.show_cursor()

            sys.stdout.flush()

            # Read key
            key = self.read_key()

            # Handle keys based on mode
            if self.mode == "edit_sentence":
                # Edit sentence mode: modify the current sentence
                if key == "\r" or key == "\n":  # Enter - save edit
                    result = "".join(buffer)
                    self.mode = "input"
                    self.current_sentence_edit = ""
                    return result, "update_sentence"
                elif key == "\x1b":  # Escape - cancel edit
                    self.mode = "input"
                    self.current_sentence_edit = ""
                    buffer = []
                    cursor_pos = 0
                elif key == "\x03":  # Ctrl+C
                    return "", "quit"
                elif key == "\x13":  # Ctrl+S
                    return "", "save"
                elif key == "\x7f":  # Backspace
                    if cursor_pos > 0:
                        buffer.pop(cursor_pos - 1)
                        cursor_pos -= 1
                        self.current_sentence_edit = "".join(buffer)
                elif key == "\x17":  # Ctrl+W - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_sentence_edit = "".join(buffer)
                elif key == "\x1b\x7f":  # Alt+Backspace - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_sentence_edit = "".join(buffer)
                elif key == "\x1bd":  # Alt+D - Delete word forward
                    buffer, cursor_pos = self.delete_word_forward(buffer, cursor_pos)
                    self.current_sentence_edit = "".join(buffer)
                elif key == "\x15":  # Ctrl+U - Delete to beginning of line
                    del buffer[0:cursor_pos]
                    cursor_pos = 0
                    self.current_sentence_edit = "".join(buffer)
                elif key == "\x0b":  # Ctrl+K - Delete to end of line
                    del buffer[cursor_pos:]
                    self.current_sentence_edit = "".join(buffer)
                elif key == "\x1b[C":  # Right arrow
                    if cursor_pos < len(buffer):
                        cursor_pos += 1
                elif key == "\x1b[D":  # Left arrow
                    if cursor_pos > 0:
                        cursor_pos -= 1
                elif key == "\x1b[1;5C":  # Ctrl+Right arrow - next word
                    text = "".join(buffer)
                    cursor_pos = self.find_next_word_boundary(text, cursor_pos)
                elif key == "\x1b[1;5D":  # Ctrl+Left arrow - previous word
                    text = "".join(buffer)
                    cursor_pos = self.find_prev_word_boundary(text, cursor_pos)
                elif key == "\x1b[H" or key == "\x01":  # Home or Ctrl+A
                    cursor_pos = 0
                elif key == "\x1b[F" or key == "\x05":  # End or Ctrl+E
                    cursor_pos = len(buffer)
                elif len(key) == 1 and 32 <= ord(key) <= 126:  # Printable characters
                    buffer.insert(cursor_pos, key)
                    cursor_pos += 1
                    self.current_sentence_edit = "".join(buffer)
            elif self.mode == "browse":
                # Browse mode: navigate through animations
                if key == "\x1b":  # Escape - return to input mode
                    self.mode = "input"
                    self.selected_animation_index = -1
                elif key in ["j", "\x1b[B"]:  # Down arrow or j
                    current_item = self.items[self.current_index]
                    if (
                        self.selected_animation_index
                        < len(current_item["animations"]) - 1
                    ):
                        self.selected_animation_index += 1
                    elif self.view_mode == "review":
                        # In review mode, move to next sentence's animations when at end of animations
                        return "", "navigate_animation_down"
                elif key in ["k", "\x1b[A"]:  # Up arrow or k
                    if self.selected_animation_index > 0:
                        self.selected_animation_index -= 1
                    elif (
                        self.view_mode == "review"
                        and self.selected_animation_index == 0
                    ):
                        # In review mode, move to previous sentence's animations when at first animation
                        return "", "navigate_animation_up"
                elif key == "i":  # Enter edit mode
                    if self.selected_animation_index >= 0:
                        current_item = self.items[self.current_index]
                        if self.selected_animation_index < len(
                            current_item["animations"]
                        ):
                            self.mode = "edit"
                            self.current_animation = current_item["animations"][
                                self.selected_animation_index
                            ]
                            buffer = list(self.current_animation)
                            cursor_pos = len(buffer)
                elif key == "d":  # Delete animation
                    if self.selected_animation_index >= 0:
                        return "", "delete"
                elif key in ["\x1b[13;2~", "o"]:  # Shift+Enter or 'o' - insert below
                    if self.view_mode == "review" and self.review_focus == "animations":
                        return "", "insert_animation"
                    elif self.view_mode == "review" and self.review_focus == "script":
                        return "", "insert_sentence"
                elif key == "O":  # Shift+O - insert above
                    if self.view_mode == "review" and self.review_focus == "animations":
                        return "", "insert_animation_above"
                    elif self.view_mode == "review" and self.review_focus == "script":
                        return "", "insert_sentence_above"
                elif (
                    key == "]"
                ):  # Focus animations (review mode) or next sentence (line-by-line)
                    if self.view_mode == "review":
                        # Loop: if on animations, go to script
                        if self.review_focus == "animations":
                            return "", "focus_script"
                        else:
                            return "", "focus_animations"
                    else:
                        return "", "skip_next"
                elif (
                    key == "["
                ):  # Focus script (review mode) or previous sentence (line-by-line)
                    if self.view_mode == "review":
                        # Loop: if on script, go to animations
                        if self.review_focus == "script":
                            return "", "focus_animations"
                        else:
                            return "", "focus_script"
                    else:
                        return "", "skip_prev"
                elif key == "\x1b[C":  # Right arrow - switch panes with looping
                    if self.view_mode == "review":
                        # Loop: if on animations, go to script
                        if self.review_focus == "animations":
                            return "", "focus_script"
                        else:
                            return "", "focus_animations"
                elif key == "\x1b[D":  # Left arrow - switch panes with looping
                    if self.view_mode == "review":
                        # Loop: if on script, go to animations
                        if self.review_focus == "script":
                            return "", "focus_animations"
                        else:
                            return "", "focus_script"
                elif key == "\x03":  # Ctrl+C
                    return "", "quit"
                elif key == "\x13":  # Ctrl+S
                    return "", "save"
                elif key == "\x16":  # Ctrl+V - Toggle view mode
                    return "", "toggle_view"
                elif key == "?":  # Toggle help
                    self.show_help = not self.show_help
            elif self.mode == "edit":
                # Edit mode: modify the selected animation
                if key == "\r" or key == "\n":  # Enter - save edit
                    result = "".join(buffer)
                    current_item = self.items[self.current_index]
                    # Check if we're updating an existing animation or adding a new one
                    if (
                        self.selected_animation_index >= 0
                        and self.selected_animation_index
                        < len(current_item["animations"])
                    ):
                        # Updating existing animation
                        self.mode = "browse"
                        self.current_animation = ""
                        return result, "update"
                    else:
                        # Adding new animation
                        self.mode = "input"
                        self.selected_animation_index = -1
                        self.current_animation = ""
                        return result, "add"
                elif (
                    key == "\x1b[13;2~"
                ):  # Shift+Enter - save and move to next sentence
                    result = "".join(buffer)
                    current_item = self.items[self.current_index]
                    # Check if we're updating an existing animation or adding a new one
                    if (
                        self.selected_animation_index >= 0
                        and self.selected_animation_index
                        < len(current_item["animations"])
                    ):
                        # Updating existing animation
                        self.mode = "input"
                        self.current_animation = ""
                        return result, "update_and_next"
                    else:
                        # Adding new animation
                        self.mode = "input"
                        self.selected_animation_index = -1
                        self.current_animation = ""
                        return result, "add_and_next"
                elif key == "\x1b":  # Escape - cancel edit
                    current_item = self.items[self.current_index]
                    # Return to appropriate mode based on whether we were editing or adding
                    if (
                        self.selected_animation_index >= 0
                        and self.selected_animation_index
                        < len(current_item["animations"])
                    ):
                        # Was editing existing, return to browse
                        self.mode = "browse"
                    else:
                        # Was adding new, return to input
                        self.mode = "input"
                        self.selected_animation_index = -1
                    self.current_animation = ""
                    buffer = []
                    cursor_pos = 0
                elif key == "\x03":  # Ctrl+C
                    return "", "quit"
                elif key == "\x13":  # Ctrl+S
                    return "", "save"
                elif key == "\x7f":  # Backspace
                    if cursor_pos > 0:
                        buffer.pop(cursor_pos - 1)
                        cursor_pos -= 1
                        self.current_animation = "".join(buffer)
                elif key == "\x17":  # Ctrl+W - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x1b\x7f":  # Alt+Backspace - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x1bd":  # Alt+D - Delete word forward
                    buffer, cursor_pos = self.delete_word_forward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x15":  # Ctrl+U - Delete to beginning of line
                    del buffer[0:cursor_pos]
                    cursor_pos = 0
                    self.current_animation = "".join(buffer)
                elif key == "\x0b":  # Ctrl+K - Delete to end of line
                    del buffer[cursor_pos:]
                    self.current_animation = "".join(buffer)
                elif key == "\x1b[C":  # Right arrow
                    if cursor_pos < len(buffer):
                        cursor_pos += 1
                elif key == "\x1b[D":  # Left arrow
                    if cursor_pos > 0:
                        cursor_pos -= 1
                elif key == "\x1b[1;5C":  # Ctrl+Right arrow - next word
                    text = "".join(buffer)
                    cursor_pos = self.find_next_word_boundary(text, cursor_pos)
                elif key == "\x1b[1;5D":  # Ctrl+Left arrow - previous word
                    text = "".join(buffer)
                    cursor_pos = self.find_prev_word_boundary(text, cursor_pos)
                elif key == "\x1b[H" or key == "\x01":  # Home or Ctrl+A
                    cursor_pos = 0
                elif key == "\x1b[F" or key == "\x05":  # End or Ctrl+E
                    cursor_pos = len(buffer)
                elif len(key) == 1 and 32 <= ord(key) <= 126:  # Printable characters
                    buffer.insert(cursor_pos, key)
                    cursor_pos += 1
                    self.current_animation = "".join(buffer)
            else:
                # Input mode: navigate or prepare to add animations
                if key == "\r" or key == "\n":  # Enter - save current input
                    result = "".join(buffer)
                    if result.strip():
                        return result, "add"
                    # Empty enter, do nothing
                    continue
                elif key == "\x0e":  # Ctrl+N
                    result = "".join(buffer)
                    return result, "next"
                elif (
                    key == "\t" and self.view_mode == "line-by-line"
                ):  # Tab - enter browse mode (line-by-line only)
                    current_item = self.items[self.current_index]
                    if current_item["animations"]:
                        self.mode = "browse"
                        self.selected_animation_index = 0
                elif (
                    key == "]"
                ):  # Focus animations (review mode) or next sentence (line-by-line)
                    if self.view_mode == "review":
                        # Loop: if on animations, go to script
                        if self.review_focus == "animations":
                            return "", "focus_script"
                        else:
                            return "", "focus_animations"
                    else:
                        return "", "skip_next"
                elif (
                    key == "["
                ):  # Focus script (review mode) or previous sentence (line-by-line)
                    if self.view_mode == "review":
                        # Loop: if on script, go to animations
                        if self.review_focus == "script":
                            return "", "focus_animations"
                        else:
                            return "", "focus_script"
                    else:
                        return "", "skip_prev"
                elif key == "\x03":  # Ctrl+C
                    return "", "quit"
                elif key == "\x13":  # Ctrl+S
                    return "", "save"
                elif key == "\x16":  # Ctrl+V - Toggle view mode
                    return "", "toggle_view"
                elif (
                    key == "i"
                    and self.view_mode == "review"
                    and self.review_focus == "script"
                ):
                    # Enter sentence edit mode when focused on script
                    current_item = self.items[self.current_index]
                    self.mode = "edit_sentence"
                    self.current_sentence_edit = current_item["sentence"]
                    buffer = list(self.current_sentence_edit)
                    cursor_pos = len(buffer)
                elif (
                    key == "d"
                    and self.view_mode == "review"
                    and self.review_focus == "script"
                ):
                    # Delete sentence when focused on script
                    return "", "delete_sentence"
                elif key == "\x7f":  # Backspace
                    if cursor_pos > 0:
                        buffer.pop(cursor_pos - 1)
                        cursor_pos -= 1
                        self.current_animation = "".join(buffer)
                elif key == "\x17":  # Ctrl+W - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x1b\x7f":  # Alt+Backspace - Delete word backward
                    buffer, cursor_pos = self.delete_word_backward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x1bd":  # Alt+D - Delete word forward
                    buffer, cursor_pos = self.delete_word_forward(buffer, cursor_pos)
                    self.current_animation = "".join(buffer)
                elif key == "\x15":  # Ctrl+U - Delete to beginning of line
                    del buffer[0:cursor_pos]
                    cursor_pos = 0
                    self.current_animation = "".join(buffer)
                elif key == "\x0b":  # Ctrl+K - Delete to end of line
                    del buffer[cursor_pos:]
                    self.current_animation = "".join(buffer)
                elif key == "\x1b[C":  # Right arrow
                    # In review mode with no buffer, switch panes (with looping)
                    if self.view_mode == "review" and len(buffer) == 0:
                        # Loop: if on animations, go to script
                        if self.review_focus == "animations":
                            return "", "focus_script"
                        else:
                            return "", "focus_animations"
                    elif cursor_pos < len(buffer):
                        cursor_pos += 1
                elif key == "\x1b[D":  # Left arrow
                    # In review mode with no buffer, switch panes (with looping)
                    if self.view_mode == "review" and len(buffer) == 0:
                        # Loop: if on script, go to animations
                        if self.review_focus == "script":
                            return "", "focus_animations"
                        else:
                            return "", "focus_script"
                    elif cursor_pos > 0:
                        cursor_pos -= 1
                elif key == "\x1b[1;5C":  # Ctrl+Right arrow - next word
                    text = "".join(buffer)
                    cursor_pos = self.find_next_word_boundary(text, cursor_pos)
                elif key == "\x1b[1;5D":  # Ctrl+Left arrow - previous word
                    text = "".join(buffer)
                    cursor_pos = self.find_prev_word_boundary(text, cursor_pos)
                elif key == "\x1b[H" or key == "\x01":  # Home or Ctrl+A
                    cursor_pos = 0
                elif key == "\x1b[F" or key == "\x05":  # End or Ctrl+E
                    cursor_pos = len(buffer)
                elif (
                    key == "\x1b[A"
                ):  # Up arrow - navigate in review mode, history in line-by-line
                    if self.view_mode == "review":
                        if self.review_focus == "script":
                            return "", "navigate_up"
                        else:  # focused on animations
                            return "", "navigate_animation_up"
                elif (
                    key == "\x1b[B"
                ):  # Down arrow - navigate in review mode, history in line-by-line
                    if self.view_mode == "review":
                        if self.review_focus == "script":
                            return "", "navigate_down"
                        else:  # focused on animations
                            return "", "navigate_animation_down"
                elif key in ["j", "k"] and self.view_mode == "review":
                    # j/k navigation in review mode (vim-like, only when not in edit mode)
                    if key == "j":
                        if self.review_focus == "script":
                            return "", "navigate_down"
                        else:
                            return "", "navigate_animation_down"
                    else:  # k
                        if self.review_focus == "script":
                            return "", "navigate_up"
                        else:
                            return "", "navigate_animation_up"
                elif (
                    key == "i"
                    and self.view_mode == "review"
                    and self.review_focus == "animations"
                ):
                    # Enter insert mode (vim-like) when focused on animations
                    self.mode = "edit"
                    current_item = self.items[self.current_index]
                    if (
                        self.selected_animation_index >= 0
                        and current_item["animations"]
                    ):
                        # Editing existing animation
                        self.current_animation = current_item["animations"][
                            self.selected_animation_index
                        ]
                    else:
                        # Adding new animation
                        self.current_animation = ""
                    buffer = list(self.current_animation)
                    cursor_pos = len(buffer)
                elif (
                    key == "d"
                    and self.view_mode == "review"
                    and self.review_focus == "animations"
                ):
                    # Delete animation when focused on animations
                    current_item = self.items[self.current_index]
                    if current_item["animations"]:
                        if self.selected_animation_index < 0:
                            self.selected_animation_index = 0
                        return "", "delete"
                elif (
                    key in ["\x1b[13;2~", "o"]
                    and self.view_mode == "review"
                    and self.review_focus == "animations"
                ):
                    # Shift+Enter or 'o': Insert blank animation after current selection
                    return "", "insert_animation"
                elif (
                    key == "O"
                    and self.view_mode == "review"
                    and self.review_focus == "animations"
                ):
                    # Shift+O: Insert blank animation before current selection
                    return "", "insert_animation_above"
                elif (
                    key in ["\x1b[13;2~", "o"]
                    and self.view_mode == "review"
                    and self.review_focus == "script"
                ):
                    # Shift+Enter or 'o': Insert blank sentence after current one
                    return "", "insert_sentence"
                elif (
                    key == "O"
                    and self.view_mode == "review"
                    and self.review_focus == "script"
                ):
                    # Shift+O: Insert blank sentence before current one
                    return "", "insert_sentence_above"
                elif key == "?" and len(buffer) == 0:
                    # Toggle help only when buffer is empty (not actively typing)
                    self.show_help = not self.show_help
                elif len(key) == 1 and 32 <= ord(key) <= 126:
                    # Printable characters in input mode
                    if self.view_mode == "review":
                        # In review mode, ignore other keys - user must press 'i' or 'o' to edit
                        # This prevents hotkeys like 'd', 'j', 'k', etc. from being typed accidentally
                        pass
                    else:
                        # In line-by-line mode, add character directly
                        buffer.insert(cursor_pos, key)
                        cursor_pos += 1
                        self.current_animation = "".join(buffer)

    def draw_screen(self):
        """Draw the main screen - delegates to specific view mode"""
        if self.view_mode == "review":
            self.draw_review_screen()
        else:
            self.draw_line_by_line_screen()

        # Overlay help if toggled
        if self.show_help:
            self.draw_help_overlay()

    def draw_help_overlay(self):
        """Draw help overlay with keybindings"""
        rows, cols = TerminalControl.get_terminal_size()

        # Define help content
        help_lines = [
            "Keyboard Shortcuts",
            "",
            "Navigation:",
            "  ↑/k         Move up (Review mode)",
            "  ↓/j         Move down (Review mode)",
            "  [ or ←      Switch to script/prev sentence (loops in Review)",
            "  ] or →      Switch to animations/next sentence (loops in Review)",
            "",
            "Editing (Review Mode):",
            "  i           Edit sentence (script) / Edit animation (animations)",
            "  o/Shift+↵   Insert blank sentence/animation below current",
            "  O           Insert blank sentence/animation above current",
            "  d           Delete sentence (script) / Delete animation (animations)",
            "",
            "Editing (Line-by-line Mode):",
            "  Tab         Browse/edit existing animations",
            "  i           Edit selected animation (when browsing)",
            "  d           Delete selected animation (when browsing)",
            "",
            "Common:",
            "  Enter       Save changes / Add animation",
            "  Esc         Cancel edit / Return to normal mode",
            "  Ctrl+V      Toggle between Line-by-line and Review",
            "  ?           Toggle this help",
            "  Ctrl+S      Save progress",
            "  Ctrl+N      Add animation and move to next sentence",
            "  Ctrl+C      Quit",
            "",
            "Press ? to close",
        ]

        # Calculate box dimensions
        max_width = max(len(line) for line in help_lines)
        box_width = min(max_width + 4, cols - 4)
        box_height = len(help_lines) + 2

        # Calculate starting position to center the box
        start_row = max(3, (rows - box_height) // 2)
        start_col = max(2, (cols - box_width) // 2)

        # Draw semi-transparent background
        for i in range(box_height):
            TerminalControl.move_cursor(start_row + i, start_col)
            print(
                f"{Colors.BG_BLACK}{Colors.WHITE}{' ' * box_width}{Colors.RESET}",
                end="",
            )

        # Draw box border
        TerminalControl.move_cursor(start_row, start_col)
        print(f"{Colors.BLUE}╔{'═' * (box_width - 2)}╗{Colors.RESET}", end="")

        for i, line in enumerate(help_lines, 1):
            TerminalControl.move_cursor(start_row + i, start_col)
            # Truncate line if needed
            display_line = line[: box_width - 4]
            padding = box_width - 2 - len(display_line)

            # Highlight title
            if i == 1:
                print(
                    f"{Colors.BLUE}║{Colors.BOLD}{Colors.WHITE}{display_line}{' ' * padding}{Colors.RESET}{Colors.BLUE}║{Colors.RESET}",
                    end="",
                )
            else:
                print(
                    f"{Colors.BLUE}║{Colors.WHITE}{display_line}{' ' * padding}{Colors.RESET}{Colors.BLUE}║{Colors.RESET}",
                    end="",
                )

        TerminalControl.move_cursor(start_row + box_height - 1, start_col)
        print(f"{Colors.BLUE}╚{'═' * (box_width - 2)}╝{Colors.RESET}", end="")

        sys.stdout.flush()

    def draw_line_by_line_screen(self):
        """Draw the line-by-line view (original view)"""
        TerminalControl.hide_cursor()
        TerminalControl.clear_screen()

        rows, cols = TerminalControl.get_terminal_size()

        # Top bar with view mode indicator
        TerminalControl.move_cursor(1, 1)
        print(
            f"{Colors.BOLD}{Colors.CYAN}s2s{Colors.RESET} {Colors.DIM}[Line-by-line]{Colors.RESET}",
            end="",
        )

        # Progress indicator
        total = len(self.items)
        current = self.current_index + 1
        progress = f"{current}/{total}"
        TerminalControl.move_cursor(1, cols - len(progress) + 1)
        print(f"{Colors.BOLD}{Colors.YELLOW}{progress}{Colors.RESET}", end="")

        if self.current_index >= len(self.items):
            TerminalControl.move_cursor(rows // 2, cols // 2 - 10)
            print(f"{Colors.GREEN}{Colors.BOLD}All done!{Colors.RESET}")
            return

        current_item = self.items[self.current_index]

        # Section title
        TerminalControl.move_cursor(3, 1)
        section_title = current_item["section"]
        title_x = (cols - len(section_title)) // 2
        TerminalControl.move_cursor(3, max(1, title_x))
        print(f"{Colors.BOLD}{Colors.MAGENTA}{section_title}{Colors.RESET}", end="")

        # Previous sentence (if exists)
        if self.current_index > 0:
            prev_item = self.items[self.current_index - 1]
            prev_sentence = prev_item["sentence"]

            TerminalControl.move_cursor(5, 1)
            # Truncate if too long
            max_width = cols - 4
            if len(prev_sentence) > max_width:
                prev_sentence = prev_sentence[: max_width - 3] + "..."

            prev_x = (cols - len(prev_sentence)) // 2
            TerminalControl.move_cursor(5, max(1, prev_x))
            print(f"{Colors.DIM}{prev_sentence}{Colors.RESET}", end="")

        # Current sentence in a box
        sentence = current_item["sentence"]
        box_y = rows // 2 - 5

        # Word wrap the sentence if needed
        max_box_width = min(cols - 10, 80)
        wrapped_lines = self.wrap_text(sentence, max_box_width - 4)

        # Draw box
        box_width = min(max_box_width, max(len(line) for line in wrapped_lines) + 4)
        box_x = (cols - box_width) // 2

        # Top border
        TerminalControl.move_cursor(box_y, box_x)
        print(f"{Colors.BLUE}╔{'═' * (box_width - 2)}╗{Colors.RESET}", end="")

        # Content lines
        for i, line in enumerate(wrapped_lines):
            TerminalControl.move_cursor(box_y + 1 + i, box_x)
            padding = (box_width - 2 - len(line)) // 2
            print(f"{Colors.BLUE}║{Colors.RESET}", end="")
            print(" " * padding, end="")
            print(f"{Colors.WHITE}{line}{Colors.RESET}", end="")
            print(" " * (box_width - 2 - len(line) - padding), end="")
            print(f"{Colors.BLUE}║{Colors.RESET}", end="")

        # Bottom border
        TerminalControl.move_cursor(box_y + 1 + len(wrapped_lines), box_x)
        print(f"{Colors.BLUE}╚{'═' * (box_width - 2)}╝{Colors.RESET}", end="")

        # Show existing animations for this sentence
        if current_item["animations"]:
            anim_y = box_y + len(wrapped_lines) + 3
            TerminalControl.move_cursor(anim_y, box_x)
            print(f"{Colors.GREEN}Animations:{Colors.RESET}", end="")

            for i, anim in enumerate(current_item["animations"]):
                TerminalControl.move_cursor(anim_y + 1 + i, box_x + 2)
                # Highlight selected animation in browse/edit mode
                if (
                    self.mode in ["browse", "edit"]
                    and i == self.selected_animation_index
                ):
                    print(
                        f"{Colors.CYAN}{Colors.BOLD}> [ ] {anim}{Colors.RESET}", end=""
                    )
                else:
                    print(f"{Colors.DIM}- [ ] {anim}{Colors.RESET}", end="")

        # Input box at bottom
        input_y = rows - 6
        input_box_width = min(cols - 4, 80)
        input_x = (cols - input_box_width) // 2

        # Input label with mode indicator
        TerminalControl.move_cursor(input_y - 1, input_x)
        if self.mode == "edit":
            print(f"{Colors.YELLOW}Edit animation:{Colors.RESET}", end="")
        elif self.mode == "browse":
            print(
                f"{Colors.YELLOW}Browse mode (i: edit, d: delete, Esc: back):{Colors.RESET}",
                end="",
            )
        else:
            print(f"{Colors.YELLOW}Enter animation:{Colors.RESET}", end="")

        # Input box border
        TerminalControl.move_cursor(input_y, input_x)
        print(f"{Colors.YELLOW}┌{'─' * (input_box_width - 2)}┐{Colors.RESET}", end="")

        TerminalControl.move_cursor(input_y + 1, input_x)
        print(f"{Colors.YELLOW}│{Colors.RESET}", end="")

        TerminalControl.move_cursor(input_y + 1, input_x + input_box_width - 1)
        print(f"{Colors.YELLOW}│{Colors.RESET}", end="")

        TerminalControl.move_cursor(input_y + 2, input_x)
        print(f"{Colors.YELLOW}└{'─' * (input_box_width - 2)}┘{Colors.RESET}", end="")

        # Help text (always at bottom of window, concise to fit on one line)
        TerminalControl.move_cursor(rows, 2)
        if self.mode == "browse":
            help_text = f"{Colors.DIM}i: edit | d: delete | Esc: back | [: prev | ]: next | Ctrl+V: review | Ctrl+S: save | Ctrl+C: quit{Colors.RESET}"
        elif self.mode == "edit":
            help_text = f"{Colors.DIM}Enter: save | Shift+↵: save & next | Esc: cancel | Ctrl+S: save all | Ctrl+C: quit{Colors.RESET}"
        else:
            help_text = f"{Colors.DIM}Enter: add | Tab: browse | Ctrl+N: next | [: prev | ]: next | Ctrl+V: review | Ctrl+S: save | Ctrl+C: quit{Colors.RESET}"

        # Truncate to terminal width to prevent wrapping
        print(help_text[: cols - 2], end="")

        sys.stdout.flush()

    def draw_review_screen(self):
        """Draw the review mode with side-by-side script and animations"""
        TerminalControl.hide_cursor()
        TerminalControl.clear_screen()

        rows, cols = TerminalControl.get_terminal_size()

        # Top bar with view mode indicator
        TerminalControl.move_cursor(1, 1)
        print(
            f"{Colors.BOLD}{Colors.CYAN}s2s{Colors.RESET} {Colors.DIM}[Review]{Colors.RESET}",
            end="",
        )

        # Progress indicator
        total = len(self.items)
        current = self.current_index + 1
        progress = f"{current}/{total}"
        TerminalControl.move_cursor(1, cols - len(progress) + 1)
        print(f"{Colors.BOLD}{Colors.YELLOW}{progress}{Colors.RESET}", end="")

        # Column headers with focus indicator
        mid_col = cols // 2
        TerminalControl.move_cursor(3, 2)
        if self.review_focus == "script":
            print(
                f"{Colors.BOLD}{Colors.MAGENTA}Script {Colors.CYAN}◄{Colors.RESET}",
                end="",
            )
        else:
            print(f"{Colors.BOLD}{Colors.DIM}Script{Colors.RESET}", end="")
        TerminalControl.move_cursor(3, mid_col + 2)
        if self.review_focus == "animations":
            print(
                f"{Colors.BOLD}{Colors.GREEN}Animations {Colors.CYAN}◄{Colors.RESET}",
                end="",
            )
        else:
            print(f"{Colors.BOLD}{Colors.DIM}Animations{Colors.RESET}", end="")

        # Calculate visible area first to determine section header positions
        content_start_row = 5
        content_end_row = rows - 3  # Leave room for help text at bottom

        # First pass: collect section header row positions
        section_header_rows = set()
        current_row = content_start_row
        sentence_index = self.review_scroll_offset
        last_section = None

        while current_row < content_end_row and sentence_index < len(self.items):
            item = self.items[sentence_index]

            # Track section header positions
            if item["section"] != last_section:
                if current_row > content_start_row:
                    section_header_rows.add(current_row)  # Space before section
                    current_row += 1
                if current_row >= content_end_row:
                    break

                section_header_rows.add(current_row)  # Section header row itself
                current_row += 1
                last_section = item["section"]

                if current_row >= content_end_row:
                    break

            # Calculate space for this sentence
            left_col_width = mid_col - 4
            wrapped_sentence = self.wrap_text(item["sentence"], left_col_width)
            animations = item["animations"]
            sentence_lines = len(wrapped_sentence)
            num_anims = len(animations) if animations else 1

            current_row += max(sentence_lines, num_anims)
            current_row += 1  # spacing after sentence
            sentence_index += 1

        # Draw vertical separator with gaps for section headers
        for row in range(4, rows):
            if row not in section_header_rows:
                TerminalControl.move_cursor(row, mid_col)
                print(f"{Colors.DIM}│{Colors.RESET}", end="")

        # Second pass: Draw sentences and animations side-by-side
        current_row = content_start_row
        sentence_index = self.review_scroll_offset
        last_section = None

        while current_row < content_end_row and sentence_index < len(self.items):
            item = self.items[sentence_index]
            is_current = sentence_index == self.current_index

            # Draw section header if this is a new section
            if item["section"] != last_section:
                if current_row > content_start_row:
                    current_row += 1  # Add spacing before new section
                if current_row >= content_end_row:
                    break

                # Draw section title across both columns
                TerminalControl.move_cursor(current_row, 2)
                section_title = f"─── {item['section']} "
                title_with_line = section_title + "─" * (cols - len(section_title) - 2)
                print(
                    f"{Colors.BOLD}{Colors.MAGENTA}{title_with_line[:cols-2]}{Colors.RESET}",
                    end="",
                )
                current_row += 1
                last_section = item["section"]

                if current_row >= content_end_row:
                    break

            # Highlight current sentence
            if is_current and self.mode == "input":
                prefix = f"{Colors.CYAN}► {Colors.RESET}"
            elif is_current:
                prefix = f"{Colors.CYAN}• {Colors.RESET}"
            else:
                prefix = "  "

            # Draw sentence (left side) - with full word wrapping
            sentence = item["sentence"]
            left_col_width = mid_col - 4
            wrapped_sentence = self.wrap_text(sentence, left_col_width)

            # Draw all wrapped lines for this sentence
            for line_idx, line in enumerate(wrapped_sentence):
                if current_row + line_idx >= content_end_row:
                    break
                TerminalControl.move_cursor(current_row + line_idx, 2)
                if line_idx == 0:
                    # First line with prefix
                    if is_current:
                        print(f"{prefix}{Colors.WHITE}{line}{Colors.RESET}", end="")
                    else:
                        print(f"{prefix}{Colors.DIM}{line}{Colors.RESET}", end="")
                else:
                    # Continuation lines (indented to match)
                    if is_current:
                        print(f"  {Colors.WHITE}{line}{Colors.RESET}", end="")
                    else:
                        print(f"  {Colors.DIM}{line}{Colors.RESET}", end="")

            sentence_lines = len(wrapped_sentence)

            # Draw animations (right side)
            animations = item["animations"]
            right_col_width = cols - mid_col - 4

            if animations:
                for i, anim in enumerate(animations):
                    anim_row = current_row + i
                    if anim_row >= content_end_row:
                        break

                    # Show edit box inline if editing this animation
                    if (
                        is_current
                        and self.mode == "edit"
                        and i == self.selected_animation_index
                    ):
                        TerminalControl.move_cursor(anim_row, mid_col + 2)
                        # The actual text rendering will happen in get_input_line
                        print(f"{Colors.CYAN}{Colors.BOLD}> [ ] {Colors.RESET}", end="")
                    # Highlight selected animation if in browse mode and this is current sentence
                    elif (
                        is_current
                        and self.mode == "browse"
                        and i == self.selected_animation_index
                    ):
                        TerminalControl.move_cursor(anim_row, mid_col + 2)
                        print(
                            f"{Colors.CYAN}{Colors.BOLD}> [ ] {anim[:right_col_width-6]}{Colors.RESET}",
                            end="",
                        )
                    else:
                        TerminalControl.move_cursor(anim_row, mid_col + 2)
                        anim_display = anim[: right_col_width - 6]
                        if is_current:
                            print(
                                f"{Colors.WHITE}- [ ] {anim_display}{Colors.RESET}",
                                end="",
                            )
                        else:
                            print(
                                f"{Colors.DIM}- [ ] {anim_display}{Colors.RESET}",
                                end="",
                            )

                # Move to next row after max of sentence lines or animations
                current_row += max(sentence_lines, len(animations))
            else:
                # No animations for this sentence
                if (
                    is_current
                    and self.review_focus == "animations"
                    and self.mode == "input"
                ):
                    # Show input prompt when focused on empty animations in input mode
                    TerminalControl.move_cursor(current_row, mid_col + 2)
                    print(f"{Colors.CYAN}> [ ] {Colors.RESET}", end="")
                    # The actual text will be rendered by get_input_line
                elif (
                    is_current
                    and self.review_focus == "animations"
                    and self.mode == "edit"
                ):
                    # Show edit prompt when editing new animation on empty animations
                    TerminalControl.move_cursor(current_row, mid_col + 2)
                    print(f"{Colors.CYAN}{Colors.BOLD}> [ ] {Colors.RESET}", end="")
                    # The actual text will be rendered by get_input_line
                elif is_current:
                    TerminalControl.move_cursor(current_row, mid_col + 2)
                    print(f"{Colors.DIM}(no animations){Colors.RESET}", end="")
                current_row += max(sentence_lines, 1)

            # Handle input for adding new animation to current sentence
            if (
                is_current
                and self.review_focus == "animations"
                and self.mode in ["input", "edit"]
                and animations
            ):
                # Determine if we're adding a new animation (not editing an existing one)
                adding_new = self.mode == "input" or (
                    self.mode == "edit"
                    and (
                        self.selected_animation_index < 0
                        or self.selected_animation_index >= len(animations)
                    )
                )

                if adding_new:
                    # Show input line below last animation
                    new_anim_row = (
                        current_row
                        - max(sentence_lines, len(animations))
                        + len(animations)
                    )
                    if new_anim_row < content_end_row:
                        TerminalControl.move_cursor(new_anim_row, mid_col + 2)
                        if self.mode == "edit":
                            print(
                                f"{Colors.CYAN}{Colors.BOLD}> [ ] {Colors.RESET}",
                                end="",
                            )
                        else:
                            print(f"{Colors.CYAN}> [ ] {Colors.RESET}", end="")
                        # The actual text will be rendered by get_input_line

            # Add small spacing between sentences
            current_row += 1
            sentence_index += 1

        # Help text (always at bottom of window, concise to fit on one line)
        TerminalControl.move_cursor(rows, 2)
        if self.mode == "browse":
            help_text = f"{Colors.DIM}i: edit | o/O: insert | d: delete | ←/→: switch panes | Ctrl+V: line-by-line | Ctrl+C: quit{Colors.RESET}"
        elif self.mode == "edit":
            if self.view_mode == "review" and self.review_focus == "animations":
                help_text = f"{Colors.DIM}EDIT MODE | Enter: save | Shift+↵: save & next | Esc: cancel | Ctrl+S: save all{Colors.RESET}"
            else:
                help_text = f"{Colors.DIM}EDIT MODE | Enter: save | Esc: cancel | Ctrl+S: save all | Ctrl+C: quit{Colors.RESET}"
        elif self.mode == "edit_sentence":
            help_text = f"{Colors.DIM}EDIT SENTENCE | Enter: save | Esc: cancel | Ctrl+S: save all | Ctrl+C: quit{Colors.RESET}"
        else:
            if self.review_focus == "script":
                help_text = f"{Colors.DIM}i: edit | o/O: insert | d: delete | ←/→: switch | ↑/↓: navigate | Ctrl+V: line-by-line{Colors.RESET}"
            else:
                help_text = f"{Colors.DIM}i: edit | o/O: insert | d: delete | ←/→: switch | ↑/↓: navigate | Ctrl+V: line-by-line{Colors.RESET}"

        # Truncate to terminal width to prevent wrapping
        print(help_text[: cols - 2], end="")

        sys.stdout.flush()

    def wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit within width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_len = len(word)
            if current_length + word_len + len(current_line) <= width:
                current_line.append(word)
                current_length += word_len
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_len

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def get_default_output_path(self) -> str:
        """Generate default output path based on input script name"""
        input_path = Path(self.script_file)

        # Remove " Script" from the end of the filename if present
        video_name = input_path.stem
        if video_name.endswith(" Script"):
            video_name = video_name[:-7]  # Remove " Script"

        # Create storyboard filename (without "Script" word) in script's directory
        output_filename = video_name + " Storyboard.md"
        output_path = input_path.parent / output_filename
        return str(output_path)

    def get_output_path_from_user(self) -> str:
        """Interactive dialog to get output file path from user"""
        default_path = self.get_default_output_path()

        # Show dialog screen
        TerminalControl.clear_screen()
        rows, cols = TerminalControl.get_terminal_size()

        TerminalControl.move_cursor(1, 1)
        print(f"{Colors.BOLD}{Colors.CYAN}Export Storyboard{Colors.RESET}")

        TerminalControl.move_cursor(3, 1)
        print(f"{Colors.WHITE}Enter output file path:{Colors.RESET}")

        # Input box for path
        input_y = 5
        input_box_width = min(cols - 4, 100)
        input_x = 2

        TerminalControl.move_cursor(input_y, input_x)
        print(f"{Colors.YELLOW}┌{'─' * (input_box_width - 2)}┐{Colors.RESET}")
        TerminalControl.move_cursor(input_y + 1, input_x)
        print(f"{Colors.YELLOW}│{Colors.RESET}", end="")
        TerminalControl.move_cursor(input_y + 1, input_x + input_box_width - 1)
        print(f"{Colors.YELLOW}│{Colors.RESET}")
        TerminalControl.move_cursor(input_y + 2, input_x)
        print(f"{Colors.YELLOW}└{'─' * (input_box_width - 2)}┘{Colors.RESET}")

        TerminalControl.move_cursor(input_y + 4, 2)
        print(f"{Colors.DIM}Press Enter to confirm, Esc to cancel{Colors.RESET}")

        # Get user input with editing
        buffer = list(default_path)
        cursor_pos = len(buffer)

        while True:
            # Display buffer
            max_text_width = input_box_width - 4
            text_offset = 0
            if cursor_pos > max_text_width:
                text_offset = cursor_pos - max_text_width

            display_text = "".join(buffer)
            visible_text = display_text[text_offset : text_offset + max_text_width]
            visible_cursor_pos = cursor_pos - text_offset

            TerminalControl.move_cursor(input_y + 1, input_x + 2)
            print(f"{Colors.WHITE}{visible_text}{Colors.RESET}", end="")

            # Clear rest of line
            remaining_space = max_text_width - len(visible_text)
            if remaining_space > 0:
                print(" " * remaining_space, end="")

            # Position cursor
            TerminalControl.move_cursor(input_y + 1, input_x + 2 + visible_cursor_pos)
            TerminalControl.show_cursor()
            sys.stdout.flush()

            # Read key
            key = self.read_key()

            if key == "\r" or key == "\n":  # Enter
                result = "".join(buffer)
                return result if result.strip() else default_path
            elif key == "\x1b":  # Escape - cancel
                return ""
            elif key == "\x7f":  # Backspace
                if cursor_pos > 0:
                    buffer.pop(cursor_pos - 1)
                    cursor_pos -= 1
            elif key == "\x1b[C":  # Right arrow
                if cursor_pos < len(buffer):
                    cursor_pos += 1
            elif key == "\x1b[D":  # Left arrow
                if cursor_pos > 0:
                    cursor_pos -= 1
            elif key == "\x1b[H":  # Home
                cursor_pos = 0
            elif key == "\x1b[F":  # End
                cursor_pos = len(buffer)
            elif len(key) == 1 and 32 <= ord(key) <= 126:  # Printable characters
                buffer.insert(cursor_pos, key)
                cursor_pos += 1

    def save_storyboard(self, prompt_for_path=False):
        """Save current progress to storyboard file"""
        # Build animations dict
        animations = {}
        for item in self.items:
            if item["animations"]:
                animations[item["sentence"]] = item["animations"]

        # Get output path
        if prompt_for_path:
            output_path_str = self.get_output_path_from_user()
            if not output_path_str:  # User cancelled
                return None
            output_path = Path(output_path_str)
        else:
            # Use default path in storyboards/ directory (for quick saves)
            input_path = Path(self.script_file)
            video_name = input_path.stem
            # Remove " Script" from the end of the filename if present
            if video_name.endswith(" Script"):
                video_name = video_name[:-7]  # Remove " Script"
            output_filename = video_name + " Storyboard.md"
            storyboards_dir = Path("storyboards")
            storyboards_dir.mkdir(exist_ok=True)
            output_path = storyboards_dir / output_filename

        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate content
        content = StoryboardGenerator.generate(
            self.script_file, self.sections, animations
        )

        # Write file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(output_path)

    def run(self):
        """Run the main application loop"""
        try:
            self.setup_terminal()

            while self.current_index < len(self.items):
                self.draw_screen()

                # Get input
                text, action = self.get_input_line()

                if action == "quit":
                    # Save progress before quitting
                    self._save_progress()
                    break
                elif action == "save":
                    # Save both storyboard and progress
                    output_file = self.save_storyboard()
                    self._save_progress()
                    # Show success message
                    TerminalControl.clear_screen()
                    TerminalControl.move_cursor(1, 1)
                    print(f"{Colors.GREEN}Saved to: {output_file}{Colors.RESET}")
                    print(
                        f"{Colors.DIM}Progress cached for resuming later{Colors.RESET}"
                    )
                    # Wait for key
                    sys.stdin.read(1)
                elif action == "add":
                    if text.strip():
                        self.items[self.current_index]["animations"].append(
                            text.strip()
                        )
                        self.current_animation = ""
                        # Auto-save progress after adding animation
                        self._save_progress()
                elif action == "update":
                    # Update the selected animation
                    if text.strip() and self.selected_animation_index >= 0:
                        current_item = self.items[self.current_index]
                        if self.selected_animation_index < len(
                            current_item["animations"]
                        ):
                            current_item["animations"][
                                self.selected_animation_index
                            ] = text.strip()
                        # Auto-save progress after updating
                        self._save_progress()
                elif action == "add_and_next":
                    # Add animation and move to next sentence
                    if text.strip():
                        self.items[self.current_index]["animations"].append(
                            text.strip()
                        )
                    # Move to next sentence
                    if self.current_index < len(self.items) - 1:
                        self.current_index += 1
                        self.current_animation = ""
                        self.selected_animation_index = -1

                        # Adjust scroll to keep current sentence visible in review mode
                        if self.view_mode == "review":
                            rows, cols = TerminalControl.get_terminal_size()
                            mid_col = cols // 2
                            left_col_width = mid_col - 4

                            # Calculate cumulative rows from scroll offset to current
                            cumulative_rows = 0
                            last_section = None
                            for i in range(
                                self.review_scroll_offset, self.current_index + 1
                            ):
                                if i >= len(self.items):
                                    break
                                item = self.items[i]

                                # Add section header space
                                if item["section"] != last_section:
                                    if last_section is not None:
                                        cumulative_rows += 1  # spacing before section
                                    cumulative_rows += 1  # section title
                                    last_section = item["section"]

                                # Add sentence space
                                wrapped = self.wrap_text(
                                    item["sentence"], left_col_width
                                )
                                num_anims = (
                                    len(item["animations"]) if item["animations"] else 1
                                )
                                cumulative_rows += max(len(wrapped), num_anims)
                                cumulative_rows += 1  # spacing after sentence

                            # Scroll down if current sentence is below visible area
                            visible_rows = rows - 8  # Account for headers and help text
                            if cumulative_rows > visible_rows:
                                self.review_scroll_offset += 1

                        # Keep focus on animations
                        self.review_focus = "animations"
                        self.mode = "input"
                    # Auto-save progress after adding and moving
                    self._save_progress()
                elif action == "update_and_next":
                    # Update animation and move to next sentence
                    if text.strip() and self.selected_animation_index >= 0:
                        current_item = self.items[self.current_index]
                        if self.selected_animation_index < len(
                            current_item["animations"]
                        ):
                            current_item["animations"][
                                self.selected_animation_index
                            ] = text.strip()

                    # Move to next sentence
                    if self.current_index < len(self.items) - 1:
                        self.current_index += 1
                        self.current_animation = ""
                        self.selected_animation_index = -1

                        # Adjust scroll to keep current sentence visible in review mode
                        if self.view_mode == "review":
                            rows, cols = TerminalControl.get_terminal_size()
                            mid_col = cols // 2
                            left_col_width = mid_col - 4

                            # Calculate cumulative rows from scroll offset to current
                            cumulative_rows = 0
                            last_section = None
                            for i in range(
                                self.review_scroll_offset, self.current_index + 1
                            ):
                                if i >= len(self.items):
                                    break
                                item = self.items[i]

                                # Add section header space
                                if item["section"] != last_section:
                                    if last_section is not None:
                                        cumulative_rows += 1  # spacing before section
                                    cumulative_rows += 1  # section title
                                    last_section = item["section"]

                                # Add sentence space
                                wrapped = self.wrap_text(
                                    item["sentence"], left_col_width
                                )
                                num_anims = (
                                    len(item["animations"]) if item["animations"] else 1
                                )
                                cumulative_rows += max(len(wrapped), num_anims)
                                cumulative_rows += 1  # spacing after sentence

                            # Scroll down if current sentence is below visible area
                            visible_rows = rows - 8  # Account for headers and help text
                            if cumulative_rows > visible_rows:
                                self.review_scroll_offset += 1

                        # Keep focus on animations
                        self.review_focus = "animations"
                        self.mode = "input"
                    # Auto-save progress after updating and moving
                    self._save_progress()
                elif action == "delete":
                    # Delete the selected animation
                    if self.selected_animation_index >= 0:
                        current_item = self.items[self.current_index]
                        if self.selected_animation_index < len(
                            current_item["animations"]
                        ):
                            current_item["animations"].pop(
                                self.selected_animation_index
                            )
                            # Adjust selected index if needed
                            if self.selected_animation_index >= len(
                                current_item["animations"]
                            ):
                                self.selected_animation_index = max(
                                    0, len(current_item["animations"]) - 1
                                )
                            # If no animations left, go back to input mode
                            if not current_item["animations"]:
                                self.mode = "input"
                                self.selected_animation_index = -1
                        # Auto-save progress after deleting
                        self._save_progress()
                elif action == "update_sentence":
                    # Update the current sentence
                    if text.strip():
                        self.items[self.current_index]["sentence"] = text.strip()
                        # Auto-save progress after updating sentence
                        self._save_progress()
                elif action == "delete_sentence":
                    # Delete the current sentence and its animations
                    if len(self.items) > 1:  # Don't delete if it's the only sentence
                        self.items.pop(self.current_index)
                        # Adjust current index if needed
                        if self.current_index >= len(self.items):
                            self.current_index = len(self.items) - 1
                        # Reset mode and selection
                        self.mode = "input"
                        self.selected_animation_index = -1
                        # Auto-save progress after deleting
                        self._save_progress()
                elif action == "insert_animation":
                    # Insert a blank animation after the currently selected one
                    current_item = self.items[self.current_index]
                    # Determine insert position
                    if (
                        self.selected_animation_index < 0
                        or not current_item["animations"]
                    ):
                        # No selection or no animations, insert at beginning
                        insert_pos = 0
                    else:
                        # Insert after the selected animation
                        insert_pos = self.selected_animation_index + 1

                    # Insert blank animation
                    current_item["animations"].insert(insert_pos, "")

                    # Enter edit mode for the new animation
                    self.selected_animation_index = insert_pos
                    self.mode = "edit"
                    self.current_animation = ""
                    # Don't save yet - wait for user to add content
                elif action == "insert_animation_above":
                    # Insert a blank animation before the currently selected one
                    current_item = self.items[self.current_index]
                    # Determine insert position
                    if (
                        self.selected_animation_index < 0
                        or not current_item["animations"]
                    ):
                        # No selection or no animations, insert at beginning
                        insert_pos = 0
                    else:
                        # Insert before the selected animation
                        insert_pos = self.selected_animation_index

                    # Insert blank animation
                    current_item["animations"].insert(insert_pos, "")

                    # Enter edit mode for the new animation
                    self.selected_animation_index = insert_pos
                    self.mode = "edit"
                    self.current_animation = ""
                    # Don't save yet - wait for user to add content
                elif action == "insert_sentence":
                    # Insert a blank sentence after the current one
                    current_item = self.items[self.current_index]

                    # Create new sentence item with same section
                    new_item = {
                        "section": current_item["section"],
                        "sentence": "",
                        "animations": [],
                    }

                    # Insert after current sentence
                    insert_pos = self.current_index + 1
                    self.items.insert(insert_pos, new_item)

                    # Move to the new sentence and enter edit mode
                    self.current_index = insert_pos
                    self.mode = "edit_sentence"
                    self.current_sentence_edit = ""
                    self.selected_animation_index = -1
                    # Don't save yet - wait for user to add content
                elif action == "insert_sentence_above":
                    # Insert a blank sentence before the current one
                    current_item = self.items[self.current_index]

                    # Create new sentence item with same section
                    new_item = {
                        "section": current_item["section"],
                        "sentence": "",
                        "animations": [],
                    }

                    # Insert before current sentence
                    insert_pos = self.current_index
                    self.items.insert(insert_pos, new_item)

                    # Move to the new sentence and enter edit mode (index stays the same since we inserted before)
                    self.current_index = insert_pos
                    self.mode = "edit_sentence"
                    self.current_sentence_edit = ""
                    self.selected_animation_index = -1
                    # Don't save yet - wait for user to add content
                elif action == "next":
                    if text.strip():
                        self.items[self.current_index]["animations"].append(
                            text.strip()
                        )
                    self.current_index += 1
                    self.current_animation = ""
                    # Reset mode when moving to next sentence
                    self.mode = "input"
                    self.selected_animation_index = -1
                    # Auto-save progress after moving to next
                    self._save_progress()
                elif action == "skip_prev":
                    if self.current_index > 0:
                        self.current_index -= 1
                        self.current_animation = ""
                        # Reset mode when navigating
                        self.mode = "input"
                        self.selected_animation_index = -1
                        # Auto-save progress after navigation
                        self._save_progress()
                elif action == "skip_next":
                    if self.current_index < len(self.items) - 1:
                        self.current_index += 1
                        self.current_animation = ""
                        # Reset mode when navigating
                        self.mode = "input"
                        self.selected_animation_index = -1
                        # Auto-save progress after navigation
                        self._save_progress()
                elif action == "toggle_view":
                    # Toggle between line-by-line and review modes
                    if self.view_mode == "line-by-line":
                        self.view_mode = "review"
                        # Adjust scroll to show current sentence
                        self.review_scroll_offset = max(0, self.current_index - 2)
                        self.review_focus = "script"
                    else:
                        self.view_mode = "line-by-line"
                    # Reset to input mode when switching views
                    self.mode = "input"
                    self.selected_animation_index = -1
                elif action == "focus_script":
                    # Focus on script column in review mode
                    self.review_focus = "script"
                    self.mode = "input"
                    self.selected_animation_index = -1
                elif action == "focus_animations":
                    # Focus on animations column in review mode
                    self.review_focus = "animations"
                    current_item = self.items[self.current_index]
                    if current_item["animations"]:
                        self.mode = "browse"
                        self.selected_animation_index = 0
                    else:
                        # No animations, stay in input mode but focused on animations
                        self.mode = "input"
                        self.selected_animation_index = -1
                elif action == "navigate_animation_up":
                    # Navigate up through animations in review mode
                    current_item = self.items[self.current_index]
                    if current_item["animations"] and self.selected_animation_index > 0:
                        # Move up in the current animation list
                        self.selected_animation_index -= 1
                        self.mode = "browse"
                    else:
                        # At the top of current animations or no animations - move to previous sentence
                        if self.current_index > 0:
                            self.current_index -= 1
                            self.current_animation = ""
                            # Adjust scroll to keep current sentence visible
                            if self.current_index < self.review_scroll_offset:
                                self.review_scroll_offset = self.current_index

                            # Select the last animation of the previous sentence if it has any
                            prev_item = self.items[self.current_index]
                            if prev_item["animations"]:
                                self.selected_animation_index = (
                                    len(prev_item["animations"]) - 1
                                )
                                self.mode = "browse"
                            else:
                                # Previous sentence has no animations, stay in input mode
                                self.selected_animation_index = -1
                                self.mode = "input"

                            # Auto-save progress
                            self._save_progress()
                elif action == "navigate_animation_down":
                    # Navigate down through animations in review mode
                    current_item = self.items[self.current_index]
                    if self.selected_animation_index < 0 and current_item["animations"]:
                        # First time navigating in this sentence, select first animation
                        self.selected_animation_index = 0
                        self.mode = "browse"
                    elif (
                        current_item["animations"]
                        and self.selected_animation_index
                        < len(current_item["animations"]) - 1
                    ):
                        # Move down in the current animation list
                        self.selected_animation_index += 1
                        self.mode = "browse"
                    else:
                        # At the bottom of current animations or no animations - move to next sentence
                        if self.current_index < len(self.items) - 1:
                            self.current_index += 1
                            self.current_animation = ""

                            # Adjust scroll to keep current sentence visible
                            rows, cols = TerminalControl.get_terminal_size()
                            mid_col = cols // 2
                            left_col_width = mid_col - 4

                            # Calculate cumulative rows from scroll offset to current
                            cumulative_rows = 0
                            last_section = None
                            for i in range(
                                self.review_scroll_offset, self.current_index + 1
                            ):
                                if i >= len(self.items):
                                    break
                                item = self.items[i]

                                # Add section header space
                                if item["section"] != last_section:
                                    if last_section is not None:
                                        cumulative_rows += 1  # spacing before section
                                    cumulative_rows += 1  # section title
                                    last_section = item["section"]

                                # Add sentence space
                                wrapped = self.wrap_text(
                                    item["sentence"], left_col_width
                                )
                                num_anims = (
                                    len(item["animations"]) if item["animations"] else 1
                                )
                                cumulative_rows += max(len(wrapped), num_anims)
                                cumulative_rows += 1  # spacing after sentence

                            # Scroll down if current sentence is below visible area
                            visible_rows = rows - 8  # Account for headers and help text
                            if cumulative_rows > visible_rows:
                                self.review_scroll_offset += 1

                            # Select the first animation of the next sentence if it has any
                            next_item = self.items[self.current_index]
                            if next_item["animations"]:
                                self.selected_animation_index = 0
                                self.mode = "browse"
                            else:
                                # Next sentence has no animations, stay in input mode
                                self.selected_animation_index = -1
                                self.mode = "input"

                            # Auto-save progress
                            self._save_progress()
                elif action == "navigate_up":
                    # Navigate to previous sentence (review mode)
                    if self.current_index > 0:
                        self.current_index -= 1
                        self.current_animation = ""
                        # Adjust scroll to keep current sentence visible
                        # Scroll up if current sentence is above visible area
                        if self.current_index < self.review_scroll_offset:
                            self.review_scroll_offset = self.current_index
                        # Reset animation selection
                        self.selected_animation_index = -1
                        # Auto-save progress
                        self._save_progress()
                elif action == "navigate_down":
                    # Navigate to next sentence (review mode)
                    if self.current_index < len(self.items) - 1:
                        self.current_index += 1
                        self.current_animation = ""
                        # Adjust scroll to keep current sentence visible
                        # Calculate how many rows the current sentence will take
                        rows, cols = TerminalControl.get_terminal_size()
                        mid_col = cols // 2
                        left_col_width = mid_col - 4

                        # Calculate cumulative rows from scroll offset to current
                        cumulative_rows = 0
                        last_section = None
                        for i in range(
                            self.review_scroll_offset, self.current_index + 1
                        ):
                            if i >= len(self.items):
                                break
                            item = self.items[i]

                            # Add section header space
                            if item["section"] != last_section:
                                if last_section is not None:
                                    cumulative_rows += 1  # spacing before section
                                cumulative_rows += 1  # section title
                                last_section = item["section"]

                            # Add sentence space
                            wrapped = self.wrap_text(item["sentence"], left_col_width)
                            num_anims = (
                                len(item["animations"]) if item["animations"] else 1
                            )
                            cumulative_rows += max(len(wrapped), num_anims)
                            cumulative_rows += 1  # spacing after sentence

                        # Scroll down if current sentence is below visible area
                        visible_rows = rows - 8  # Account for headers and help text
                        if cumulative_rows > visible_rows:
                            self.review_scroll_offset += 1

                        # Reset animation selection
                        self.selected_animation_index = -1
                        # Auto-save progress
                        self._save_progress()

            # Final save with export dialog
            if self.current_index >= len(self.items):
                output_file = self.save_storyboard(prompt_for_path=True)
                if output_file:  # User didn't cancel
                    # Clear cache since work is complete
                    self._clear_cache()
                    TerminalControl.clear_screen()
                    TerminalControl.move_cursor(1, 1)
                    print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Complete!{Colors.RESET}")
                    print(
                        f"{Colors.WHITE}Storyboard saved to: {Colors.CYAN}{output_file}{Colors.RESET}\n"
                    )
                else:
                    # User cancelled, keep progress cache
                    TerminalControl.clear_screen()
                    TerminalControl.move_cursor(1, 1)
                    print(
                        f"\n{Colors.YELLOW}Export cancelled. Progress saved.{Colors.RESET}\n"
                    )

        finally:
            self.restore_terminal()
            TerminalControl.show_cursor()
            TerminalControl.clear_screen()
            TerminalControl.move_cursor(1, 1)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(f"{Colors.RED}Usage: s2s.py <script_file.md>{Colors.RESET}")
        print(
            f"{Colors.WHITE}Example: s2s.py 'Bulk API Release Short Script.md'{Colors.RESET}"
        )
        sys.exit(1)

    script_file = sys.argv[1]

    if not os.path.exists(script_file):
        print(f"{Colors.RED}Error: File not found: {script_file}{Colors.RESET}")
        sys.exit(1)

    app = S2SApp(script_file)
    app.run()


if __name__ == "__main__":
    main()
