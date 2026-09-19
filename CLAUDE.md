# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv run` as the package manager.

**Run all tests:**

```bash
uv run -m unittest tests/test_create_intro_cards.py
```

**Run a single test:**

```bash
uv run -m unittest tests.test_create_intro_cards.TestMakePDF.test_pdf_file_created
```

**Format and lint:**

```bash
uv run ruff format create_intro_cards.py tests/test_create_intro_cards.py
uv run ruff check create_intro_cards.py tests/test_create_intro_cards.py
uv run docformatter --in-place create_intro_cards.py tests/test_create_intro_cards.py
```

**Run all checks locally (format, lint, test, docs):**

```bash
./format-test-and-build-docs.sh
```

## Architecture

The entire library lives in a single module: `create_intro_cards.py`. There are two public functions:

- **`make_pdf()`** — Primary entry point. Takes a Pandas DataFrame plus column name arguments, generates a PDF of intro cards (4 per page), PNG images of each page, and a timestamped log file. Returns a `StatsDict`.
- **`make_pdf_preview()`** — Renders the first page inline in Jupyter for layout tuning. Same signature minus `output_dir`.

### Data flow

```
DataFrame
  → _format_data_and_derive_full_names()   # null→"", cast to str, strip, escape Mathtext special chars
  → _make_figs() / _make_fig_preview()     # batch into groups of 4
      → _make_page_fig()                   # create 2×2 matplotlib subplot figure
          → _make_card()                   # render one person per subplot
              → _get_description_string_from_row()  # format custom attributes
              → _resolve_photo()           # pick person photo or fall back to default
              → _WrapText                  # matplotlib.Text subclass for word-wrap
  → save PNGs → combine into PDF + write log
```

### Key design details

**Mathtext rendering:** Card text uses matplotlib's Mathtext engine (bold context `{"mathtext.default": "bf"}`). This means custom column names and values are escaped when needed. Column names have `~`, `^`, `\` stripped, and `space #$%_{}` escaped. Column values only have `$` escaped. Name/photo columns are left untouched.

**`_CardLayout` dataclass:** All visual parameters (figure size, font sizes, photo bounds, name/description positioning) are internally bundled into this private dataclass. It is not part of the public API; the public functions still take these as flat keyword arguments and construct a `_CardLayout` instance internally.

**`_WrapText`:** Subclasses `matplotlib.Text` to enable word-wrapping within a specified pixel width. Used for both name and description rendering. Description font size is reduced iteratively by `_FONT_SHRINK_FACTOR = 0.95` until text fits.

**Logging:** `_log_to_stream_and_file()` and `_log_to_stream()` are context managers that temporarily attach handlers to the module logger and clean them up on exit.

**Photo resolution:** `_resolve_photo()` tries the person's specified path first, falls back to the default photo if missing or unreadable (PIL exception), and records warnings in `StatsDict["people_with_photo_warnings"]`.

**Backend:** Agg for PDF generation; switches to inline for Jupyter preview.
