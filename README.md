# AIPDFGenerator (Python — original)

> **A Go rewrite of this app exists at `~/Documents/FormForge`.** FormForge has the same features, same UI, same JSON schema, and same API endpoints. If you're starting fresh or iterating, prefer FormForge. This Python version is kept as reference.

Takes proprietary medical/dental office forms (PDFs or images), sends them to Claude's vision API to extract the field structure, writes a JSON schema for the PHP form builder, and generates a fillable PDF from that JSON — all from a local web UI.

---

## Quick Start

```bash
cd ~/Documents/AIPDFGenerator
source env/bin/activate
python app.py
# Opens Chromium at http://127.0.0.1:5000
```

**Requirements:**
- Python 3.x + virtualenv (`env/`)
- `pdftoppm` (poppler) — `brew install poppler`
- Chromium at `/Applications/Chromium.app/Contents/MacOS/Chromium` (for FlaskWebGUI)
- An Anthropic API key (enter in Settings panel, saved to `settings.json`)

---

## What It Does

1. Upload a PDF or image of a paper form
2. Claude's vision API reads it and outputs a JSON definition matching the PHP form builder's schema
3. That JSON generates a fillable PDF (AcroForm fields the PHP system pre-fills)
4. You download a ZIP with:
   - `json/<form_key>.json` — form definition for the PHP builder
   - `html/<form_key>.html` — autofill template tag for PHP
   - `pdf/<form_key>_fillable.pdf` — PDF with named fillable fields

**Regenerate mode:** Upload a JSON you've already tweaked → skip the AI step → fresh PDF.

---

## Project Structure

```
AIPDFGenerator/
├── app.py                       # Flask server: routes, settings, upload handling
├── custompdf.py                 # Standalone CLI for direct PDF generation
├── requirements.txt             # Python dependencies
├── settings.json                # API key/model (gitignored)
├── analyzer/
│   ├── form_analyzer.py         # Claude API: PDF/image → JSON schema
│   └── config.py                # API key loading from .env
├── generator/
│   ├── pdf_generator.py         # Main PDF rendering orchestrator
│   ├── page_manager.py          # Business header (logo + locations) and page footer
│   ├── label_manager.py         # HTML label parsing (h1/h3/h4/p) and drawing
│   ├── label_styles.py          # Font/size/color per label type
│   ├── constants.py             # Margins, group configs, colors
│   ├── utils.py                 # Text wrap, field height, AcroForm field creation
│   └── fields/
│       ├── text_field.py        # Single-line text input
│       ├── text_area.py         # Multi-line text input
│       ├── check_box.py         # Checkboxes (single and multi-option)
│       ├── radio_button.py      # Radio groups
│       ├── select_field.py      # Dropdown (renders as text field in PDF)
│       ├── group_field.py       # Column layout engine
│       └── inline_text_field.py # Fill-in-the-blank paragraph fields
├── static/
│   ├── css/main.css
│   └── js/                      # Form submission, settings, locations, logo preview, etc.
└── templates/
    └── index.html               # Single-page UI (Jinja2 + fetch() API calls)
```

---

## JSON Schema (what the AI produces)

```json
{
  "form_key": {
    "settings": {},
    "content": {
      "form_key": {
        "form_name": "form_key",
        "submission_url": "{{%/processors/forms/pdf_form_email}}",
        "subject": "New Form Submission",
        "confirmation": "/custom/content/thank_you/thank_you.html",
        "pdf": "/custom/pdfs/form_key.pdf",
        "category": "Patient Intake",
        "type": "intake",
        "fields": [ ... ]
      }
    }
  }
}
```

**Field types:**

| type | purpose |
|---|---|
| `pdf_download` | UI-only download link, skipped by PDF generator |
| `label` | Static text — label HTML contains `<h1>`, `<h3>`, `<h4>`, `<p>` tags |
| `text` / `email` / `date` | Single-line text input |
| `textarea` | Multi-line text input |
| `radio` | Radio group. `option`: `{"yes":"Yes","no":"No"}` or `["A","B"]` |
| `checkbox` | One or more checkboxes. `option`: `{"key":"Label"}` or `{"checked":"agreement text"}` |
| `select` | Dropdown (rendered as text field in PDF) |
| `inline_text` | Text segment inside an `inline_container` group |
| `submit` | UI-only, skipped by PDF generator |
| `group_start` | Opens a layout group — `name` controls layout |
| `group_end` | Closes the most recently opened group |

**Layout group names:**

| name | layout |
|---|---|
| `name_details` | 3 col: Last Name (43%), First Name (43%), M.I. (14%) |
| `address_details` | 4 col: Address, City, State, Zip |
| `two_columns` | 50/50 — 2 separate group_start/group_end pairs (one per column) |
| `four_columns` | 25/25/25/25 — 4 separate pairs |
| `inline_container` | Inline fill-in-the-blank flow |
| `form_container` / `form_content_container` | Structural only, no layout effect |
| `permanent` / `deciduous` / `top_row` / `bottom_row` / `tooth_container` / `tooth` | Dental chart |

---

## Settings File

`settings.json` in the project root (same schema in both this app and FormForge):

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-sonnet-4-20250514"
}
```

---

## Known Issues

### 1. Inline container over-generation
The prompt causes Claude to wrap too many things in `inline_container` — standalone "Date: ____" lines, signature lines, etc. You have to manually edit the JSON to remove them.

**Fix location:** `analyzer/form_analyzer.py` → `FORM_ANALYSIS_PROMPT` — tighten the `## INLINE TEXT CONTAINERS` section with explicit rules about when NOT to use inline containers.

### 2. Spacing/formatting inconsistencies
PDF spacing options sometimes produce fields too close or too far apart depending on field type mix.

**Fix location:** `generator/fields/` — each field renderer's spacing logic at the bottom of its `draw()` method, and `generator/constants.py` for default values.

### 3. FlaskWebGUI / Chromium dependency
The app requires Chromium at a hardcoded path. If Chromium moves or is missing, run `app.py` with `app.run(debug=True)` instead and open `http://127.0.0.1:5000` manually.

---

## Go Rewrite (FormForge)

`~/Documents/FormForge` is a complete 1:1 port to Go:
- Same UI, same endpoints, same JSON schema
- From-scratch PDF 1.7 writer (no external PDF lib — avoids license issues)
- Auto-opens system browser instead of requiring Chromium
- Run: `cd ~/Documents/FormForge && go run ./cmd`

The Go version's README has a full breakdown of every file, every struct, and every layout mechanism.
