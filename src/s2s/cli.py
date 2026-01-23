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
        """Parse script file into sections and content items (sentences, tables, code blocks)"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

        # Remove blockquotes and their content
        content = re.sub(r"^>.*$", "", content, flags=re.MULTILINE)

        # Split content by headers
        section_pattern = r"^(#{1,6})\s+(.+?)$"

        sections = []
        current_section = None
        current_content_lines = []

        # State for code blocks
        in_code_block = False
        code_block_lines = []
        code_lang = None

        # State for tables
        table_lines = []

        def flush_table():
            """Flush accumulated table lines as a table content item"""
            nonlocal table_lines
            if table_lines:
                raw = "\n".join(table_lines)
                current_content_lines.append(
                    {
                        "type": "table",
                        "content": f"[TABLE: {ScriptParser._extract_table_summary(table_lines)}]",
                        "raw_content": raw,
                    }
                )
                table_lines = []

        def flush_code_block():
            """Flush accumulated code block as a code content item"""
            nonlocal code_block_lines, code_lang
            if code_block_lines or code_lang is not None:
                raw = "\n".join(code_block_lines)
                lang_display = code_lang.upper() if code_lang else "CODE"
                # Get first meaningful line for preview
                first_line = ""
                for line in code_block_lines:
                    if line.strip():
                        first_line = line.strip()[:40]
                        if len(line.strip()) > 40:
                            first_line += "..."
                        break
                summary = (
                    f"[{lang_display}] {first_line}"
                    if first_line
                    else f"[{lang_display}]"
                )
                current_content_lines.append(
                    {
                        "type": "code",
                        "content": summary,
                        "raw_content": raw,
                        "lang": code_lang,
                    }
                )
                code_block_lines = []
                code_lang = None

        for line in content.split("\n"):
            stripped = line.strip()

            # Handle code block boundaries
            if stripped.startswith("```"):
                if in_code_block:
                    # End of code block
                    flush_code_block()
                    in_code_block = False
                else:
                    # Start of code block - flush any pending table first
                    flush_table()
                    in_code_block = True
                    code_lang = stripped[3:].strip() or None
                    code_block_lines = []
                continue

            # If inside code block, accumulate lines
            if in_code_block:
                code_block_lines.append(line.rstrip())
                continue

            # Check for header
            header_match = re.match(section_pattern, stripped)

            if header_match:
                # Flush any pending table before processing header
                flush_table()

                # Save previous section if exists
                if current_section:
                    content_items = ScriptParser.extract_content_items(
                        current_content_lines
                    )
                    current_section["content_items"] = content_items
                    sections.append(current_section)

                # Start new section
                header_text = header_match.group(2).strip()
                current_section = {"title": header_text, "content_items": []}
                current_content_lines = []
            elif current_section:
                # Check if this is a table line
                if stripped.startswith("|"):
                    table_lines.append(stripped)
                else:
                    # Flush any pending table when we hit non-table content
                    flush_table()

                    # Add non-empty, non-link lines as regular content
                    if stripped and not stripped.startswith("["):
                        current_content_lines.append(stripped)

        # Flush any remaining code block or table
        if in_code_block:
            flush_code_block()
        flush_table()

        # Add last section
        if current_section:
            content_items = ScriptParser.extract_content_items(current_content_lines)
            current_section["content_items"] = content_items
            sections.append(current_section)

        # If no sections were found (no headers), create a default section
        if not sections:
            all_lines = [
                line.strip()
                for line in content.split("\n")
                if line.strip() and not line.strip().startswith("[")
            ]
            if all_lines:
                content_items = ScriptParser.extract_content_items(all_lines)
                if content_items:
                    sections.append({"title": "Script", "content_items": content_items})

        return sections

    @staticmethod
    def _extract_table_summary(table_lines: List[str]) -> str:
        """Extract a summary description from table header"""
        if not table_lines:
            return "Table"
        # Get header row and extract column names
        header = table_lines[0]
        # Remove leading/trailing pipes and split
        cells = [c.strip() for c in header.strip("|").split("|")]
        # Remove markdown bold markers
        cells = [re.sub(r"\*\*(.+?)\*\*", r"\1", c) for c in cells if c.strip()]
        if cells:
            # Return first 2-3 column names as summary
            summary_cols = cells[:3]
            summary = ", ".join(summary_cols)
            if len(cells) > 3:
                summary += f" +{len(cells) - 3} more"
            row_count = len(
                [
                    line
                    for line in table_lines
                    if not line.strip().startswith("|--")
                    and not line.strip().startswith("|-")
                ]
            )
            return f"{summary} ({row_count} rows)"
        return f"Table ({len(table_lines)} rows)"

    @staticmethod
    def extract_content_items(content_lines: List) -> List[Dict]:
        """Extract content items from lines, handling sentences, tables, and code blocks"""
        items = []

        # Separate already-parsed items (dicts) from raw text lines
        text_buffer = []

        for line in content_lines:
            if isinstance(line, dict):
                # Flush text buffer first
                if text_buffer:
                    sentences = ScriptParser._extract_sentences_from_text(
                        "\n".join(text_buffer)
                    )
                    for sentence in sentences:
                        items.append(
                            {
                                "type": "sentence",
                                "content": sentence,
                                "raw_content": None,
                            }
                        )
                    text_buffer = []
                # Add the pre-parsed item (table or code block)
                items.append(line)
            else:
                text_buffer.append(line)

        # Flush remaining text buffer
        if text_buffer:
            sentences = ScriptParser._extract_sentences_from_text(
                "\n".join(text_buffer)
            )
            for sentence in sentences:
                items.append(
                    {"type": "sentence", "content": sentence, "raw_content": None}
                )

        return items

    @staticmethod
    def _extract_sentences_from_text(text: str) -> List[str]:
        """Extract sentences from text, handling numbered lists with nested bullets"""
        if not text.strip():
            return []

        lines = text.split("\n")
        sentences = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check if this is a numbered list item
            numbered_match = re.match(r"^(\d+\.)\s+(.+)$", line)

            if numbered_match:
                # Start collecting the numbered item and its nested bullets
                list_parts = [line]
                i += 1

                # Collect all nested bullets that follow
                while i < len(lines):
                    next_line = lines[i].strip()

                    # Check if it's a bullet point (starts with * or -)
                    if next_line and re.match(r"^[\*\-]\s+", next_line):
                        list_parts.append(next_line)
                        i += 1
                    # Check if it's another numbered item (stop collecting)
                    elif re.match(r"^\d+\.", next_line):
                        break
                    # Empty line or other content (stop collecting)
                    elif not next_line or re.match(r"^[A-Z]", next_line):
                        break
                    else:
                        # Might be a continuation, add it
                        list_parts.append(next_line)
                        i += 1

                # Merge all parts into one sentence
                merged = " ".join(list_parts)
                # Clean up whitespace
                merged = re.sub(r"\s+", " ", merged)
                sentences.append(merged.strip())

            elif line:
                # Regular text - extract sentences normally
                sentence_pattern = r"[A-Z].*?[.!?](?=\s|$)"

                found_sentences = re.findall(sentence_pattern, line, re.DOTALL)

                for sentence in found_sentences:
                    sentence = re.sub(r"\s+", " ", sentence)
                    sentence = sentence.strip()
                    if sentence and len(sentence) > 1:
                        sentences.append(sentence)

                i += 1
            else:
                i += 1

        return sentences

    # Keep old method for backwards compatibility
    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """Extract sentences from text (backwards compatibility wrapper)"""
        return ScriptParser._extract_sentences_from_text(text)


class ScriptGenerator:
    """Generate script markdown files from edited items"""

    @staticmethod
    def generate(items: List[Dict]) -> str:
        """Generate script markdown content from items"""
        lines = []

        # Group items by section, keeping full item info
        sections = {}
        section_order = []
        for item in items:
            section_title = item["section"]
            if section_title not in sections:
                sections[section_title] = []
                section_order.append(section_title)
            sections[section_title].append(item)

        # Generate markdown
        for section_title in section_order:
            lines.append(f"# {section_title}")
            lines.append("")

            # Add all content items for this section
            for item in sections[section_title]:
                item_type = item.get("type", "sentence")
                raw_content = item.get("raw_content")
                sentence = item.get("sentence", "")

                if not sentence.strip() and not raw_content:
                    continue

                if item_type == "table" and raw_content:
                    # Output full table
                    lines.append(raw_content)
                    lines.append("")
                elif item_type == "code" and raw_content:
                    # Output full code block with language
                    lang = item.get("lang", "")
                    lines.append(f"```{lang}")
                    lines.append(raw_content)
                    lines.append("```")
                    lines.append("")
                elif sentence.strip():
                    # Regular sentence handling
                    # Check if this is a merged numbered list item
                    numbered_match = re.match(r"^(\d+\.)\s+(.+)$", sentence)

                    if numbered_match:
                        # This is a numbered list item, possibly with nested bullets
                        # Split on bullet markers (* or -) while preserving them
                        parts = re.split(r"\s+([\*\-])\s+", sentence)

                        if len(parts) > 1:
                            # Has nested bullets - format properly
                            lines.append(parts[0])  # The numbered item

                            # Process remaining parts (marker, content, marker, content, ...)
                            i = 1
                            while i < len(parts):
                                if i + 1 < len(parts):
                                    marker = parts[i]
                                    content = parts[i + 1]
                                    lines.append(f"   {marker} {content}")
                                    i += 2
                                else:
                                    i += 1
                        else:
                            # Just a numbered item without bullets
                            lines.append(sentence)
                    else:
                        # Regular sentence
                        lines.append(sentence)

                    lines.append("")

        return "\n".join(lines)


class StoryboardGenerator:
    """Generate storyboard markdown files"""

    @staticmethod
    def generate(
        input_file: str,
        sections: List[Dict],
        animations: Dict[str, List[str]],
        items: List[Dict] = None,
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

        # Build a lookup for items by content key to get raw_content
        item_lookup = {}
        if items:
            for item in items:
                item_lookup[item["sentence"]] = item

        # Add sections with animations
        for section in sections:
            lines.append(f"# {section['title']}")
            lines.append("")

            # Handle both new format (content_items) and old format (sentences)
            content_items = section.get("content_items", [])
            if not content_items and "sentences" in section:
                content_items = [
                    {"type": "sentence", "content": s, "raw_content": None}
                    for s in section["sentences"]
                ]

            for content_item in content_items:
                content_key = content_item["content"]
                item_type = content_item.get("type", "sentence")
                raw_content = content_item.get("raw_content")

                # For tables and code blocks, include the full content as a reference
                if item_type == "table" and raw_content:
                    lines.append("**Table:**")
                    lines.append("")
                    lines.append(raw_content)
                    lines.append("")
                elif item_type == "code" and raw_content:
                    lang = content_item.get("lang", "")
                    lines.append(f"```{lang}")
                    lines.append(raw_content)
                    lines.append("```")
                    lines.append("")

                # Add animations for this content
                if content_key in animations and animations[content_key]:
                    for animation in animations[content_key]:
                        lines.append(f"- [ ] {animation}")
                    lines.append("")

        return "\n".join(lines)


class S2SApp:
    """Main application for s2s"""

    def __init__(self, script_file: str):
        self.script_file = script_file
        self.sections = ScriptParser.parse_script(script_file)

        # Flatten content items with section references
        self.items = []
        for section in self.sections:
            # Handle both new format (content_items) and old format (sentences) for backwards compatibility
            content_items = section.get("content_items", [])
            if not content_items and "sentences" in section:
                # Old format - convert sentences to content items
                content_items = [
                    {"type": "sentence", "content": s, "raw_content": None}
                    for s in section["sentences"]
                ]

            for item in content_items:
                self.items.append(
                    {
                        "section": section["title"],
                        "sentence": item[
                            "content"
                        ],  # Keep "sentence" key for compatibility
                        "type": item.get("type", "sentence"),
                        "raw_content": item.get("raw_content"),
                        "lang": item.get("lang"),  # For code blocks
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

        # Fixed column position for animations in line-by-line mode
        self.ANIMATION_START_COL = 10

        # Track if script content has been modified
        self.script_modified = False

        # Load progress from cache if it exists
        self._load_progress()

        # Final safety check: ensure current_index is valid
        # This handles edge cases where cache or parsing might have issues
        if self.items and self.current_index >= len(self.items):
            self.current_index = len(self.items) - 1
        elif not self.items:
            self.current_index = 0

    def _compute_script_hash(self) -> str:
        """Compute hash of the script file content"""
        with open(self.script_file, "r", encoding="utf-8") as f:
            content = f.read()
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _merge_animations_after_script_change(self, cached_items: List[Dict]):
        """Merge animations from cached items into newly parsed items after script file changed"""
        # Build a mapping of old sentences to their animations
        old_animations = {}
        for cached_item in cached_items:
            sentence = cached_item["sentence"]
            if cached_item["animations"]:
                old_animations[sentence] = cached_item["animations"]

        # Try to match new sentences with old ones
        # Use exact matching first, then fuzzy matching for modified sentences
        for item in self.items:
            sentence = item["sentence"]

            # Exact match
            if sentence in old_animations:
                item["animations"] = old_animations[sentence]
            else:
                # Try fuzzy matching - find sentences that are similar
                # Use simple word-based similarity
                best_match = None
                best_similarity = 0.0

                sentence_words = set(sentence.lower().split())

                for old_sentence, animations in old_animations.items():
                    old_words = set(old_sentence.lower().split())

                    # Calculate Jaccard similarity (intersection / union)
                    if len(sentence_words) > 0 and len(old_words) > 0:
                        intersection = len(sentence_words & old_words)
                        union = len(sentence_words | old_words)
                        similarity = intersection / union

                        # Only consider matches above 70% similarity
                        if similarity > best_similarity and similarity > 0.7:
                            best_similarity = similarity
                            best_match = old_sentence

                # If we found a good match, use those animations
                if best_match:
                    item["animations"] = old_animations[best_match]

    def _rebuild_sections_from_items(self):
        """Rebuild sections list from items (used when script is modified)"""
        sections = []
        current_section = None

        for item in self.items:
            section_title = item["section"]

            # Start new section if needed
            if current_section is None or current_section["title"] != section_title:
                if current_section:
                    sections.append(current_section)
                current_section = {"title": section_title, "content_items": []}

            # Add content item to current section
            if item["sentence"].strip():
                content_item = {
                    "type": item.get("type", "sentence"),
                    "content": item["sentence"],
                    "raw_content": item.get("raw_content"),
                    "lang": item.get("lang"),
                }
                current_section["content_items"].append(content_item)

        # Add last section
        if current_section:
            sections.append(current_section)

        self.sections = sections

    def _get_cache_dir(self) -> Path:
        """Get cache directory path in the script's directory"""
        script_path = Path(self.script_file).resolve()
        cache_dir = script_path.parent / ".s2s"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_cache_file(self) -> Path:
        """Get cache file path for current script"""
        # Use script filename (without extension) as cache filename
        script_path = Path(self.script_file).resolve()
        cache_filename = script_path.stem + ".json"
        cache_dir = self._get_cache_dir()
        return cache_dir / cache_filename

    def _save_progress(self):
        """Save current progress to cache"""
        cache_file = self._get_cache_file()
        cache_dir = self._get_cache_dir()

        # Store script file path relative to the cache directory for portability
        # This allows moving the .s2s directory with the script file
        script_path = Path(self.script_file).resolve()
        try:
            relative_script_path = os.path.relpath(script_path, cache_dir)
        except ValueError:
            # On Windows, relpath fails if paths are on different drives
            relative_script_path = str(script_path)

        # Prepare data to cache
        cache_data = {
            "script_file": relative_script_path,
            "current_index": self.current_index,
            "items": self.items,
            "script_modified": self.script_modified,
            "script_hash": (
                self._compute_script_hash() if not self.script_modified else None
            ),
        }

        # Write cache file
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

    def _load_progress(self):
        """Load progress from cache if available"""
        cache_file = self._get_cache_file()
        cache_dir = self._get_cache_dir()

        if not cache_file.exists():
            return

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Verify this is the same script file
            cached_script = cache_data.get("script_file")
            current_script_resolved = Path(self.script_file).resolve()

            # Handle both relative paths (new format) and absolute paths (backwards compatibility)
            cached_script_path = Path(cached_script)
            if cached_script_path.is_absolute():
                # Old format: absolute path
                cached_script_resolved = cached_script_path
            else:
                # New format: relative to cache directory
                cached_script_resolved = (cache_dir / cached_script).resolve()

            if cached_script_resolved == current_script_resolved:
                cached_items = cache_data.get("items", [])
                self.script_modified = cache_data.get("script_modified", False)
                cached_hash = cache_data.get("script_hash")

                # Check if script file has been modified externally
                current_hash = self._compute_script_hash()
                script_changed_externally = (
                    cached_hash is not None
                    and current_hash != cached_hash
                    and not self.script_modified
                )

                if script_changed_externally:
                    # Script file was modified externally
                    # Re-parse the script and merge animations
                    self.sections = ScriptParser.parse_script(self.script_file)

                    # Rebuild items from new sections
                    self.items = []
                    for section in self.sections:
                        content_items = section.get("content_items", [])
                        if not content_items and "sentences" in section:
                            content_items = [
                                {"type": "sentence", "content": s, "raw_content": None}
                                for s in section["sentences"]
                            ]

                        for item in content_items:
                            self.items.append(
                                {
                                    "section": section["title"],
                                    "sentence": item["content"],
                                    "type": item.get("type", "sentence"),
                                    "raw_content": item.get("raw_content"),
                                    "lang": item.get("lang"),
                                    "animations": [],
                                }
                            )

                    # Merge animations from cached items
                    if cached_items:
                        self._merge_animations_after_script_change(cached_items)

                    # Reset current index if it's out of bounds
                    cached_index = cache_data.get("current_index", 0)
                    self.current_index = (
                        min(cached_index, len(self.items) - 1) if self.items else 0
                    )

                    # Mark that we've detected external changes (don't overwrite script)
                    self.script_modified = False

                elif self.script_modified and cached_items:
                    # Script was modified through s2s, use cached items entirely
                    self.items = cached_items
                    self._rebuild_sections_from_items()
                    cached_index = cache_data.get("current_index", 0)
                    # Ensure index is within bounds
                    self.current_index = (
                        min(cached_index, len(self.items) - 1) if self.items else 0
                    )

                else:
                    # No external changes, restore progress normally
                    cached_index = cache_data.get("current_index", 0)
                    # Ensure index is within bounds
                    self.current_index = (
                        min(cached_index, len(self.items) - 1) if self.items else 0
                    )

                    # Merge cached animations with current items
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

        # Previous item (if exists)
        if self.current_index > 0:
            prev_item = self.items[self.current_index - 1]
            prev_type = prev_item.get("type", "sentence")

            # For tables/code, show the summary; for sentences, show the sentence
            if prev_type in ("table", "code"):
                prev_text = prev_item["sentence"]  # This is already the summary
            else:
                prev_text = prev_item["sentence"]

            TerminalControl.move_cursor(5, 1)
            # Truncate if too long
            max_width = cols - 4
            if len(prev_text) > max_width:
                prev_text = prev_text[: max_width - 3] + "..."

            prev_x = (cols - len(prev_text)) // 2
            TerminalControl.move_cursor(5, max(1, prev_x))
            print(f"{Colors.DIM}{prev_text}{Colors.RESET}", end="")

        # Current content in a box
        sentence = current_item["sentence"]
        item_type = current_item.get("type", "sentence")
        box_y = rows // 2 - 5

        # Format content based on type
        max_box_width = min(cols - 10, 80)
        content_width = (
            max_box_width - 8
        )  # Account for left padding (2) + right padding (2)

        if item_type == "table":
            raw_content = current_item.get("raw_content", "")
            wrapped_lines = self.format_table_preview(raw_content, content_width)
        elif item_type == "code":
            raw_content = current_item.get("raw_content", "")
            lang = current_item.get("lang")
            wrapped_lines = self.format_code_preview(raw_content, lang, content_width)
        else:
            # Regular sentence - handles numbered lists with bullets on separate lines
            wrapped_lines = self.format_list_item(sentence, content_width)

        # Draw box
        # Box width = longest line + left padding (2) + right padding (2) + borders (2)
        box_width = min(max_box_width, max(len(line) for line in wrapped_lines) + 6)
        box_x = (cols - box_width) // 2

        # Top border
        TerminalControl.move_cursor(box_y, box_x)
        print(f"{Colors.BLUE}╔{'═' * (box_width - 2)}╗{Colors.RESET}", end="")

        # Content lines (left-aligned)
        for i, line in enumerate(wrapped_lines):
            TerminalControl.move_cursor(box_y + 1 + i, box_x)
            left_padding = 2  # Fixed left padding for alignment
            right_padding = max(
                0, box_width - 2 - len(line) - left_padding
            )  # Prevent negative
            print(f"{Colors.BLUE}║{Colors.RESET}", end="")
            print(" " * left_padding, end="")
            print(f"{Colors.WHITE}{line}{Colors.RESET}", end="")
            print(" " * right_padding, end="")
            print(f"{Colors.BLUE}║{Colors.RESET}", end="")

        # Bottom border
        TerminalControl.move_cursor(box_y + 1 + len(wrapped_lines), box_x)
        print(f"{Colors.BLUE}╚{'═' * (box_width - 2)}╝{Colors.RESET}", end="")

        # Show existing animations for this sentence
        if current_item["animations"]:
            anim_y = box_y + len(wrapped_lines) + 3
            TerminalControl.move_cursor(anim_y, self.ANIMATION_START_COL)
            print(f"{Colors.GREEN}Animations:{Colors.RESET}", end="")

            # Track current row position for wrapped animations
            current_anim_row = 0

            for i, anim in enumerate(current_item["animations"]):
                # Calculate available width for animation text
                # Account for prefix "- [ ] " (6 chars) or "> [ ] " (6 chars), margins
                prefix_width = 6  # "- [ ] " or "> [ ] "
                available_width = (
                    cols - self.ANIMATION_START_COL - prefix_width - 4
                )  # 4 for margin

                # Wrap the animation text if needed
                wrapped_anim = self.wrap_text(
                    anim, max(available_width, 20)
                )  # Min width of 20

                # Display first line with checkbox prefix
                TerminalControl.move_cursor(
                    anim_y + 1 + current_anim_row, self.ANIMATION_START_COL + 2
                )

                if (
                    self.mode in ["browse", "edit"]
                    and i == self.selected_animation_index
                ):
                    # Highlight selected animation
                    print(
                        f"{Colors.CYAN}{Colors.BOLD}> [ ] {wrapped_anim[0]}{Colors.RESET}",
                        end="",
                    )
                else:
                    print(f"{Colors.DIM}- [ ] {wrapped_anim[0]}{Colors.RESET}", end="")

                current_anim_row += 1

                # Display continuation lines indented by one tab (4 spaces from the checkbox)
                for continuation_line in wrapped_anim[1:]:
                    TerminalControl.move_cursor(
                        anim_y + 1 + current_anim_row,
                        self.ANIMATION_START_COL + 2 + 6 + 4,
                    )
                    if (
                        self.mode in ["browse", "edit"]
                        and i == self.selected_animation_index
                    ):
                        print(
                            f"{Colors.CYAN}{Colors.BOLD}{continuation_line}{Colors.RESET}",
                            end="",
                        )
                    else:
                        print(f"{Colors.DIM}{continuation_line}{Colors.RESET}", end="")
                    current_anim_row += 1

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

            # Calculate space for this content item
            left_col_width = mid_col - 4
            item_type = item.get("type", "sentence")
            if item_type in ("table", "code"):
                # Tables and code show as single summary line in review mode
                wrapped_sentence = [item["sentence"]]
            else:
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

            # Draw content (left side) - with full word wrapping
            sentence = item["sentence"]
            item_type = item.get("type", "sentence")
            left_col_width = mid_col - 4

            # Format based on content type
            if item_type == "table":
                # For review mode, show summary line for tables
                wrapped_sentence = [sentence]  # Already formatted as summary
            elif item_type == "code":
                # For review mode, show summary line for code
                wrapped_sentence = [sentence]  # Already formatted as summary
            else:
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

    def format_list_item(self, text: str, width: int) -> List[str]:
        """Format numbered list items with nested bullets on separate lines"""
        # Check if this is a numbered list item
        numbered_match = re.match(r"^(\d+\.\s+)(.+)$", text)

        if not numbered_match:
            # Regular text - use normal wrapping
            return self.wrap_text(text, width)

        # Extract the numbered prefix and rest
        prefix = numbered_match.group(1)
        rest = numbered_match.group(2)

        # Split on bullet markers while preserving them
        parts = re.split(r"\s+([\*\-])\s+", rest)

        lines = []

        if len(parts) == 1:
            # No nested bullets - just wrap normally
            full_text = prefix + parts[0]
            return self.wrap_text(full_text, width)

        # First part is the numbered item text (before first bullet)
        numbered_line = prefix + parts[0]
        lines.append(numbered_line)

        # Process bullets (marker, content, marker, content, ...)
        i = 1
        while i < len(parts):
            if i + 1 < len(parts):
                marker = parts[i]
                content = parts[i + 1]
                # Wrap bullet content if needed
                bullet_text = f"   {marker} {content}"
                if len(bullet_text) <= width:
                    lines.append(bullet_text)
                else:
                    # Wrap long bullet content
                    wrapped = self.wrap_text(content, width - 5)
                    lines.append(f"   {marker} {wrapped[0]}")
                    for wrapped_line in wrapped[1:]:
                        lines.append(f"     {wrapped_line}")
                i += 2
            else:
                i += 1

        return lines

    def format_table_preview(
        self, raw_content: str, width: int, max_rows: int = 4
    ) -> List[str]:
        """Format table for display, showing header + limited rows with truncation"""
        if not raw_content:
            return ["[TABLE]"]

        table_lines = raw_content.split("\n")
        result = []

        for i, line in enumerate(table_lines):
            if i >= max_rows + 1:  # +1 to account for separator row
                remaining = len(table_lines) - i
                result.append(f"  ... {remaining} more rows")
                break

            # Truncate line if too long
            if len(line) > width:
                line = line[: width - 3] + "..."
            result.append(line)

        return result if result else ["[TABLE]"]

    def format_code_preview(
        self, raw_content: str, lang: str, width: int, max_lines: int = 4
    ) -> List[str]:
        """Format code block for display with truncation"""
        header = f"[CODE: {lang.upper()}]" if lang else "[CODE]"
        result = [header]

        if not raw_content:
            return result

        code_lines = raw_content.split("\n")

        for i, line in enumerate(code_lines):
            if i >= max_lines:
                remaining = len(code_lines) - i
                result.append(f"  ... {remaining} more lines")
                break

            # Truncate line if too long
            if len(line) > width:
                line = line[: width - 3] + "..."
            result.append(line)

        return result

    def get_default_output_path(self) -> str:
        """Generate default output path based on input script name"""
        input_path = Path(self.script_file)

        # Always remove " Script" from the end of the filename
        video_name = input_path.stem
        if video_name.endswith(" Script"):
            video_name = video_name[:-7]  # Remove " Script"

        # Create storyboard filename in script's directory
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
        # First, save script file if it has been modified
        if self.script_modified:
            script_content = ScriptGenerator.generate(self.items)
            with open(self.script_file, "w", encoding="utf-8") as f:
                f.write(script_content)
            # Rebuild sections from items to reflect changes
            self._rebuild_sections_from_items()
            self.script_modified = False

        # Build animations dict
        animations = {}
        for item in self.items:
            if item["animations"]:
                animations[item["sentence"]] = item["animations"]

        # Get output path - always prompt when requested
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
            self.script_file, self.sections, animations, self.items
        )

        # Write file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(output_path)

    def run(self):
        """Run the main application loop"""
        # Check if script has any parseable content
        if not self.items:
            print(
                f"{Colors.RED}Error: No parseable sentences found in script file.{Colors.RESET}"
            )
            print(f"\n{Colors.WHITE}The script must contain:{Colors.RESET}")
            print("  • Markdown headers (# Section Title)")
            print(
                "  • Sentences that start with a capital letter and end with . ! or ?"
            )
            print(f"\n{Colors.DIM}Example format:{Colors.RESET}")
            print("  # Introduction")
            print("  This is sentence one. This is sentence two!")
            print()
            return

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
                        self.script_modified = True
                        # Auto-save progress after updating sentence
                        self._save_progress()
                elif action == "delete_sentence":
                    # Delete the current sentence and its animations
                    if len(self.items) > 1:  # Don't delete if it's the only sentence
                        self.items.pop(self.current_index)
                        self.script_modified = True
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
                    self.script_modified = True

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
                    self.script_modified = True

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
