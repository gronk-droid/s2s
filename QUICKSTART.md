# Quick Start Guide

## Running s2s

1. **Navigate to the s2s directory:**
```bash
cd /Users/gronk-droid/gh/dnsimple/s2s
```

2. **Run the tool with a script file:**
```bash
./s2s.py "examples/Bulk API Release Short Script.md"
```

or

```bash
./s2s.py "examples/Vanity Name Servers Script.md"
```

## Workflow

1. **The interface will show:**
   - Current section title at the top center
   - Previous sentence in dim text (for context)
   - Current sentence in a highlighted box
   - Previously added animations for this sentence
   - Input box at the bottom

2. **Adding animations:**
   - Type your animation description (e.g., "Show DNSimple Logomark with API")
   - Press `Enter` to add it and start a new animation
   - Continue adding as many animations as needed for this sentence

3. **Moving to next sentence:**
   - When done with all animations for current sentence, press `Ctrl+N`
   - Or just press `Ctrl+N` on empty input to skip a sentence

4. **Editing Animations:**
   - Press `Tab` to enter browse mode
   - Use arrow keys or `j`/`k` to navigate through existing animations
   - Press `i` to edit a selected animation
   - Press `d` to delete a selected animation
   - Press `Esc` to return to adding new animations

5. **Navigation:**
   - `[` - Go back to previous sentence
   - `]` - Skip to next sentence
   - `Ctrl+S` - Save progress at any time

6. **Saving and Resuming:**
   - Progress is automatically saved as you work
   - Press `Ctrl+S` to manually save your storyboard at any time
   - Press `Ctrl+C` to quit - your progress is saved automatically
   - When you run s2s on the same script again, it resumes where you left off
   - Output storyboards are saved in the `storyboards/` directory
   - File will be named: `[Original Name] Storyboard.md`

7. **Finishing:**
   - When you reach the last sentence, the tool auto-saves
   - Cache is automatically cleared when you complete all sentences

## Example Session

```
s2s                                                          3/24

                    Bulk API Release

    Previously, if you wanted to alter multiple records...

╔═══════════════════════════════════════════════════════╗
║  Now, we have expanded the API to allow batch         ║
║  changes to DNS Zone Records.                         ║
╚═══════════════════════════════════════════════════════╝

Animations:
  - [ ] Show grid of records
  - [ ] Highlight batch operation

Enter animation:
┌─────────────────────────────────────────────────────┐
│ Show API endpoint receiving multiple records_      │
└─────────────────────────────────────────────────────┘
```

## Tips

- **Be descriptive:** Write clear animation descriptions that explain what should happen visually
- **Reference objects:** Feel free to reference elements from previous sentences
- **Break it down:** Complex actions can be split into multiple animation steps
- **Save often:** Use `Ctrl+S` to save your progress periodically
- **Edit freely:** Navigate back and forth to add or revise animations
- **Vim-like editing:** Press `Tab` to browse, use `j`/`k` to navigate, `i` to edit, `d` to delete
- **Quick fixes:** Made a typo? Press `Tab`, navigate with `j`/`k`, press `i` to edit, fix it, and press Enter

## Troubleshooting

**Terminal display issues?**
- Make sure your terminal supports ANSI colors
- Try resizing your terminal if text appears cut off
- Minimum recommended size: 80 columns × 24 rows

**Keyboard shortcuts not working?**
- Some terminal emulators may intercept certain key combinations
- On macOS, you may need to configure your terminal's keyboard settings
- If `Ctrl+N` doesn't work, complete the sentence's animations and use `]` to skip ahead

**Want to quit?**
- Press `Ctrl+C` to exit
- Your progress is automatically saved when you quit
- Simply run s2s on the same script to resume where you left off
- Cache files are stored in `~/.cache/s2s/`
