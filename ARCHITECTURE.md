# AIPDFGenerator Architecture

## Overview
Flask app that takes JSON form definitions, optionally analyzes PDFs via AI to produce them, and renders fillable PDF forms using ReportLab.

## Top-Level

| File | Purpose |
|------|---------|
| `app.py` | Flask server: upload JSON/PDF, configure AI provider, download generated PDF |
| `custompdf.py` | Standalone CLI entry point for direct PDF generation |
| `requirements.txt` | Python dependencies |

## `analyzer/` - AI Form Analysis

| File | Purpose |
|------|---------|
| `form_analyzer.py` | Sends uploaded PDFs/images to an LLM (Anthropic/OpenAI/Google) to extract structured JSON form definitions |
| `config.py` | Provider-specific API configuration and model lists |

## `generator/` - PDF Rendering Engine

### Core

| File | Purpose |
|------|---------|
| `pdf_generator.py` | **Orchestrator.** Parses JSON, iterates fields, manages auto-flow (2-col flexbox for consecutive text fields), delegates drawing to field classes. Two-pass: first counts pages, second renders with page numbers. |
| `page_manager.py` | Draws page chrome: header/logo, footer with page numbers, resets `current_y` on new pages |
| `label_manager.py` | Renders HTML-tagged labels (`<h1>`, `<h3>`, `<h4>`, `<p>`) with appropriate styles and spacing |
| `label_styles.py` | `LabelStyle` namedtuples defining font/size/color per label type |
| `constants.py` | Margins, field dimensions, colors, group configs, auto-flow field type lists |
| `utils.py` | Shared helpers: text wrapping, page-break checks, field height estimation, Acrobat-compatible form field creation |

### `generator/fields/` - Field Renderers

Each class takes `(generator, canvas)` and draws one field type:

| File | What it draws |
|------|--------------|
| `text_field.py` | Single-line text input with optional label. Group-aware page breaks. |
| `text_area.py` | Multi-line text input |
| `check_box.py` | Single or multi-option checkboxes. Handles horizontal packing (non-group) and vertical stacking (in-group). Group-aware page breaks. |
| `radio_button.py` | Radio button groups |
| `select_field.py` | Dropdown select fields |
| `group_field.py` | **Layout engine.** Manages multi-column groups (2-col, 3-col, 4-col, 16-col for dental charts). Tracks field positions via `group_fields[]`, handles row completion, nested group stacks. |
| `inline_text_field.py` | Fill-in-the-blank paragraph fields (inline text + input combos) |

## Key Mechanism: Group Layout

1. `group_start` -> `GroupField.start_group()` sets `current_group`, initializes `column_widths[]`, `group_fields[]`
2. Each field calls `get_field_position_in_group()` for its (x, width, y) based on column index
3. After drawing, field appends to `group_fields[]`; row-complete triggers `current_y` advance
4. `group_end` -> `end_group()` computes final `current_y` from `min(group_fields.y)`, resets state

## Key Fix: Group-Aware Page Breaks

**Problem:** `_check_page_break` did `showPage()` without ending the group, mixing Y-coordinates from two pages in `group_fields`. `end_group` then picked the old-page Y, creating blank gaps.

**Solution:** Fields check `current_group is not None` before breaking. If in a group, they call `_handle_group_page_break()` which: ends group (clears stale fields) -> `showPage` -> `initialize_page` -> restarts group (fresh state on new page). Safety net in `end_group` also clamps `proposed_y` above `margin_bottom`.

## Static / Frontend

| Path | Purpose |
|------|---------|
| `templates/index.html` | Single-page UI |
| `static/css/main.css` | Styling |
| `static/js/form-submit.js` | Handles form upload + PDF generation request |
| `static/js/settings.js` | AI provider/key/model configuration panel |
| `static/js/pdf-upload.js` | PDF drag-and-drop upload for AI analysis |
| `static/js/locations.js` | Multi-location business info management |
| `static/js/logo-preview.js` | Logo upload preview |
| `static/js/progress-timer.js` | Generation progress indicator |
| `static/js/config.js` | Provider-specific model options |
| `static/js/utilities.js` | Shared JS helpers |
| `static/js/init.js` | App initialization |
| `static/js/json-background.js` | Decorative JSON background animation |
