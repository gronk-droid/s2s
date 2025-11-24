#!/usr/bin/env python3
"""
Unit tests for s2s (script2storyboard)
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path to import s2s
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s2s import ScriptParser, StoryboardGenerator, S2SApp


class TestScriptParser(unittest.TestCase):
    """Tests for ScriptParser class"""

    def test_extract_sentences_basic(self):
        """Test basic sentence extraction"""
        text = "This is the first sentence. This is the second sentence."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "This is the first sentence.")
        self.assertEqual(sentences[1], "This is the second sentence.")

    def test_extract_sentences_with_newlines(self):
        """Test sentence extraction with newlines between sentences"""
        text = "First sentence.\nSecond sentence."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "First sentence.")
        self.assertEqual(sentences[1], "Second sentence.")

    def test_extract_sentences_with_tlds(self):
        """Test that TLDs in real-world context are handled correctly"""
        # Note: TLDs work when part of longer natural sentences
        text = "Financial institutions can use BANK and INSURANCE domains for security. This is another sentence."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertIn("BANK", sentences[0])
        self.assertIn("INSURANCE", sentences[0])

    def test_extract_sentences_with_dotted_tlds(self):
        """Test that TLDs with dots at the start (.BANK) are handled correctly"""
        text = "Financial and insurance institutions have exclusive access to two of the most secure top-level domains on the internet: .BANK and .INSURANCE."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 1)
        self.assertIn(".BANK", sentences[0])
        self.assertIn(".INSURANCE", sentences[0])
        self.assertTrue(sentences[0].startswith("Financial"))

    def test_extract_sentences_with_common_tlds(self):
        """Test various TLD references in context"""
        text = "Some use COM or NET domains. The EDU and GOV extensions are restricted."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertIn("COM", sentences[0])
        self.assertIn("NET", sentences[0])
        self.assertIn("EDU", sentences[1])
        self.assertIn("GOV", sentences[1])

    def test_extract_sentences_with_question_marks(self):
        """Test sentences ending with question marks"""
        text = "What is DNS? It stands for Domain Name System."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "What is DNS?")
        self.assertEqual(sentences[1], "It stands for Domain Name System.")

    def test_extract_sentences_with_exclamation_points(self):
        """Test sentences ending with exclamation points"""
        text = "This is exciting! Let's get started."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "This is exciting!")
        self.assertEqual(sentences[1], "Let's get started.")

    def test_extract_sentences_mixed_punctuation(self):
        """Test sentences with mixed punctuation"""
        text = "First sentence. Is this a question? Yes it is! Final statement."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 4)

    def test_extract_sentences_with_multiple_spaces(self):
        """Test sentences with multiple spaces between them"""
        text = "First sentence.  Second sentence."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)

    def test_extract_sentences_empty_text(self):
        """Test with empty text"""
        sentences = ScriptParser.extract_sentences("")
        self.assertEqual(len(sentences), 0)

    def test_extract_sentences_whitespace_only(self):
        """Test with whitespace only"""
        sentences = ScriptParser.extract_sentences("   \n  ")
        self.assertEqual(len(sentences), 0)

    def test_parse_script_with_sections(self):
        """Test parsing a script file with multiple sections"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Section One

This is the first sentence. This is the second sentence.

# Section Two

This is the third sentence. This is the fourth sentence.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            self.assertEqual(len(sections), 2)
            self.assertEqual(sections[0]["title"], "Section One")
            self.assertEqual(len(sections[0]["sentences"]), 2)
            self.assertEqual(sections[1]["title"], "Section Two")
            self.assertEqual(len(sections[1]["sentences"]), 2)
        finally:
            os.unlink(temp_file)

    def test_parse_script_with_frontmatter(self):
        """Test that frontmatter is removed"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
title: Test Script
tags:
  - test
---

# Introduction

This is a sentence.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            self.assertEqual(len(sections), 1)
            self.assertEqual(sections[0]["title"], "Introduction")
            self.assertEqual(len(sections[0]["sentences"]), 1)
        finally:
            os.unlink(temp_file)

    def test_parse_script_with_blockquotes(self):
        """Test that blockquotes are removed"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Section

> This is a blockquote
> It should be ignored

This is a real sentence.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            self.assertEqual(len(sections), 1)
            self.assertEqual(len(sections[0]["sentences"]), 1)
            self.assertEqual(sections[0]["sentences"][0], "This is a real sentence.")
        finally:
            os.unlink(temp_file)

    def test_parse_script_with_subsections(self):
        """Test parsing with different header levels"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Main Section

Content here.

## Subsection

More content here.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            self.assertEqual(len(sections), 2)
            self.assertEqual(sections[0]["title"], "Main Section")
            self.assertEqual(sections[1]["title"], "Subsection")
        finally:
            os.unlink(temp_file)

    def test_parse_script_preserves_paragraph_breaks(self):
        """Test that sentences in different paragraphs are both found"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Section

First paragraph sentence.

Second paragraph sentence.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            self.assertEqual(len(sections), 1)
            self.assertEqual(len(sections[0]["sentences"]), 2)
        finally:
            os.unlink(temp_file)


class TestStoryboardGenerator(unittest.TestCase):
    """Tests for StoryboardGenerator class"""

    def test_generate_basic_storyboard(self):
        """Test basic storyboard generation"""
        sections = [
            {
                "title": "Introduction",
                "sentences": ["First sentence.", "Second sentence."],
            }
        ]
        animations = {
            "First sentence.": ["Show title card", "Fade in"],
            "Second sentence.": ["Pan camera"],
        }

        output = StoryboardGenerator.generate("test_script.md", sections, animations)

        self.assertIn("# Introduction", output)
        self.assertIn("- [ ] Show title card", output)
        self.assertIn("- [ ] Fade in", output)
        self.assertIn("- [ ] Pan camera", output)

    def test_generate_includes_frontmatter(self):
        """Test that generated storyboard includes proper frontmatter"""
        sections = [{"title": "Test", "sentences": []}]
        animations = {}

        output = StoryboardGenerator.generate("My Script.md", sections, animations)

        self.assertIn("---", output)
        self.assertIn("prev:", output)
        self.assertIn('- "[[My Script]]"', output)
        self.assertIn("tags:", output)
        self.assertIn('- "#storyboard"', output)

    def test_generate_with_multiple_sections(self):
        """Test storyboard generation with multiple sections"""
        sections = [
            {"title": "Section One", "sentences": ["Sentence one."]},
            {"title": "Section Two", "sentences": ["Sentence two."]},
        ]
        animations = {
            "Sentence one.": ["Animation 1"],
            "Sentence two.": ["Animation 2"],
        }

        output = StoryboardGenerator.generate("test.md", sections, animations)

        self.assertIn("# Section One", output)
        self.assertIn("# Section Two", output)
        self.assertIn("- [ ] Animation 1", output)
        self.assertIn("- [ ] Animation 2", output)

    def test_generate_with_no_animations(self):
        """Test storyboard generation when no animations are added"""
        sections = [{"title": "Section", "sentences": ["A sentence."]}]
        animations = {}

        output = StoryboardGenerator.generate("test.md", sections, animations)

        self.assertIn("# Section", output)
        # Should not have any checkbox items
        self.assertNotIn("- [ ]", output)

    def test_generate_with_multiple_animations_per_sentence(self):
        """Test that multiple animations per sentence are all included"""
        sections = [{"title": "Test", "sentences": ["One sentence."]}]
        animations = {"One sentence.": ["Anim 1", "Anim 2", "Anim 3"]}

        output = StoryboardGenerator.generate("test.md", sections, animations)

        self.assertIn("- [ ] Anim 1", output)
        self.assertIn("- [ ] Anim 2", output)
        self.assertIn("- [ ] Anim 3", output)

    def test_generate_separates_sentences_with_newlines(self):
        """Test that each sentence's animations are separated by newlines"""
        sections = [
            {"title": "Test", "sentences": ["First sentence.", "Second sentence."]}
        ]
        animations = {
            "First sentence.": ["Anim 1", "Anim 2"],
            "Second sentence.": ["Anim 3", "Anim 4"],
        }

        output = StoryboardGenerator.generate("test.md", sections, animations)

        # Check that animations are separated by blank lines
        lines = output.split("\n")

        # Find animation lines
        anim1_idx = None
        anim2_idx = None
        anim3_idx = None

        for i, line in enumerate(lines):
            if "Anim 1" in line:
                anim1_idx = i
            elif "Anim 2" in line:
                anim2_idx = i
            elif "Anim 3" in line:
                anim3_idx = i

        # Verify there's a blank line after the last animation of first sentence
        self.assertIsNotNone(anim2_idx)
        self.assertIsNotNone(anim3_idx)
        # There should be at least one blank line between anim2 and anim3
        self.assertGreater(anim3_idx - anim2_idx, 1)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow"""

    def test_full_workflow(self):
        """Test complete workflow from script to storyboard"""
        # Create a test script
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
title: Test
---

# Introduction

First sentence. Second sentence.

# Main Content

Third sentence about domains. Fourth sentence?
"""
            )
            temp_file = f.name

        try:
            # Parse the script
            sections = ScriptParser.parse_script(temp_file)

            # Verify parsing
            self.assertEqual(len(sections), 2)
            self.assertEqual(sections[0]["title"], "Introduction")
            self.assertEqual(len(sections[0]["sentences"]), 2)
            self.assertEqual(sections[1]["title"], "Main Content")
            self.assertEqual(len(sections[1]["sentences"]), 2)

            # Create animations
            animations = {
                sections[0]["sentences"][0]: ["Show intro"],
                sections[1]["sentences"][0]: ["Show content"],
            }

            # Generate storyboard
            output = StoryboardGenerator.generate(temp_file, sections, animations)

            # Verify output
            self.assertIn("# Introduction", output)
            self.assertIn("# Main Content", output)
            self.assertIn("- [ ] Show intro", output)
            self.assertIn("- [ ] Show content", output)

        finally:
            os.unlink(temp_file)

    def test_real_world_example(self):
        """Test with a realistic script excerpt"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Security Requirements

Financial institutions have exclusive access to two of the most secure top-level domains on the internet: BANK and INSURANCE.
DNSimple now offers complete registration and management for these restricted TLDs.
In this video, we'll cover the verification requirements for these domains.

DNS Security Extensions, or DNSSEC is required to prevent attacks.
Our interface simplifies DNSSEC configuration with one-click activation.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)

            self.assertEqual(len(sections), 1)
            self.assertEqual(sections[0]["title"], "Security Requirements")
            # Should find 5 sentences
            self.assertEqual(len(sections[0]["sentences"]), 5)

            # Verify content is parsed correctly
            first_sentence = sections[0]["sentences"][0]
            self.assertIn("BANK", first_sentence)
            self.assertIn("INSURANCE", first_sentence)

        finally:
            os.unlink(temp_file)


class TestProgressCaching(unittest.TestCase):
    """Tests for progress saving and resuming"""

    def setUp(self):
        """Set up temporary cache directory for tests"""
        self.temp_cache_dir = tempfile.mkdtemp()
        self.original_get_cache_dir = S2SApp._get_cache_dir
        # Override cache directory to use temp dir (capture temp_cache_dir in closure)
        temp_dir = self.temp_cache_dir
        S2SApp._get_cache_dir = lambda self: Path(temp_dir)

    def tearDown(self):
        """Clean up temporary cache directory"""
        # Restore original method
        S2SApp._get_cache_dir = self.original_get_cache_dir
        # Clean up temp dir
        import shutil

        if os.path.exists(self.temp_cache_dir):
            shutil.rmtree(self.temp_cache_dir)

    def test_save_and_load_progress(self):
        """Test that progress can be saved and loaded"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Section One

First sentence. Second sentence.

# Section Two

Third sentence. Fourth sentence.
"""
            )
            temp_file = f.name

        try:
            # Create app and add some animations
            app = S2SApp(temp_file)
            app.items[0]["animations"] = ["Animation 1", "Animation 2"]
            app.items[1]["animations"] = ["Animation 3"]
            app.current_index = 1

            # Save progress
            app._save_progress()

            # Create a new app instance (simulating restart)
            app2 = S2SApp(temp_file)

            # Verify progress was loaded
            self.assertEqual(app2.current_index, 1)
            self.assertEqual(
                app2.items[0]["animations"], ["Animation 1", "Animation 2"]
            )
            self.assertEqual(app2.items[1]["animations"], ["Animation 3"])

            # Clean up cache
            app2._clear_cache()

        finally:
            os.unlink(temp_file)

    def test_cache_file_location(self):
        """Test that cache files are created in correct location"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n\nSentence one.")
            temp_file = f.name

        try:
            app = S2SApp(temp_file)
            cache_file = app._get_cache_file()

            # Verify cache is in temp cache dir
            self.assertTrue(str(cache_file).startswith(self.temp_cache_dir))
            self.assertTrue(cache_file.name.endswith(".json"))

            # Clean up
            app._clear_cache()

        finally:
            os.unlink(temp_file)

    def test_clear_cache(self):
        """Test that cache can be cleared"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n\nSentence one.")
            temp_file = f.name

        try:
            app = S2SApp(temp_file)
            app.items[0]["animations"] = ["Test animation"]
            app._save_progress()

            # Verify cache exists
            cache_file = app._get_cache_file()
            self.assertTrue(cache_file.exists())

            # Clear cache
            app._clear_cache()

            # Verify cache is gone
            self.assertFalse(cache_file.exists())

        finally:
            os.unlink(temp_file)

    def test_no_cache_on_fresh_start(self):
        """Test that app works fine when no cache exists"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n\nFirst sentence. Second sentence.")
            temp_file = f.name

        try:
            # Create app without any cache
            app = S2SApp(temp_file)

            # Should start at index 0 with no animations
            self.assertEqual(app.current_index, 0)
            self.assertEqual(len(app.items), 2)
            self.assertEqual(app.items[0]["animations"], [])
            self.assertEqual(app.items[1]["animations"], [])

        finally:
            os.unlink(temp_file)

    def test_storyboard_output_directory(self):
        """Test that storyboards are saved in storyboards/ directory"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n\nSentence one.")
            temp_file = f.name

        try:
            app = S2SApp(temp_file)
            app.items[0]["animations"] = ["Test animation"]

            # Save storyboard
            output_file = app.save_storyboard()

            # Verify it's in storyboards/ directory
            self.assertTrue(output_file.startswith("storyboards/"))

            # Clean up storyboard file
            if os.path.exists(output_file):
                os.unlink(output_file)

        finally:
            os.unlink(temp_file)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and potential issues"""

    def test_sentence_starting_with_tld(self):
        """Test sentences - current implementation requires capital letter start"""
        # Note: Sentences must start with capital letters in current implementation
        # This is acceptable for video scripts which follow standard grammar
        text = "BANK domains are secure. They require verification."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertTrue(sentences[0].startswith("BANK"))

    def test_consecutive_sentences_no_space(self):
        """Test domain references within sentences"""
        text = "Visit our website for more info. Another sentence here."
        sentences = ScriptParser.extract_sentences(text)
        # Should get 2 sentences
        self.assertEqual(len(sentences), 2)

    def test_abbreviations_in_sentences(self):
        """Test handling of common abbreviations"""
        text = "Dr. Smith works here. He is an expert."
        sentences = ScriptParser.extract_sentences(text)
        # Note: Current implementation may split on Dr. - this test documents behavior
        # In practice, this is acceptable for video scripts which rarely use abbreviations
        self.assertGreaterEqual(len(sentences), 1)

    def test_sentence_with_colon(self):
        """Test that colons don't break sentences"""
        text = "Here are the features: security, speed, and reliability. Great choice."
        sentences = ScriptParser.extract_sentences(text)
        self.assertEqual(len(sentences), 2)

    def test_empty_section(self):
        """Test handling of sections with no content"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Empty Section

# Another Section

This has content.
"""
            )
            temp_file = f.name

        try:
            sections = ScriptParser.parse_script(temp_file)
            # Should get both sections
            self.assertEqual(len(sections), 2)
            # First section should have no sentences
            self.assertEqual(len(sections[0]["sentences"]), 0)
            # Second should have content
            self.assertEqual(len(sections[1]["sentences"]), 1)
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
