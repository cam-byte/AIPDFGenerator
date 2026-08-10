# AIPDFGenerator

Takes proprietary medical/dental office forms (PDFs or images), sends them to Claude's vision API to extract the field structure, writes a JSON schema for the PHP form builder, and generates a fillable PDF from that JSON — all from a local web UI.

---

## Quick Start

```bash
git clone https://github.com/cam-byte/AIPDFGenerator
cd AIPDFGenerator
./setup.sh
```

`setup.sh` will install dependencies, set up the Python environment, and create **SchemaForm.app** on your Desktop. Double-click it to launch.

Enter your Anthropic API key in the Settings panel on first run.

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

## Requirements

- macOS with [Homebrew](https://brew.sh)
- Python 3.x
- Chromium at `/Applications/Chromium.app` (for the desktop launcher) — if missing, open `http://127.0.0.1:5000` manually after running `./run.sh`
- An Anthropic API key

---

## Project Structure

```
AIPDFGenerator/
├── app.py                       # Flask server: routes, settings, upload handling
├── custompdf.py                 # Standalone CLI for direct PDF generation
├── requirements.txt             # Python dependencies
├── settings.json                # API key/model (gitignored)
├── settings.example.json        # Template for settings.json
├── setup.sh                     # One-time setup: deps, venv, Desktop app
├── run.sh                       # Launch without the Desktop app
├── analyzer/
│   ├── form_analyzer.py         # Claude API: PDF/image → JSON schema
│   └── config.py                # API key, model, token budgets, thinking toggles
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

`settings.json` in the project root (gitignored). Copy `settings.example.json` to get started, or just save once from the Settings panel — the app writes the file for you:

```bash
cp settings.example.json settings.json
```

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-sonnet-5"
}
```

**These three keys override `analyzer/config.py`.** If `settings.json` exists, `load_settings()` returns it as-is and `ANTHROPIC_API_KEY` / `MODEL_NAME` from `.env` and config are never read. Everything else — output token budgets and thinking toggles — lives only in `analyzer/config.py`:

| Setting | Purpose |
|---|---|
| `MODEL_NAME` | Model used when `settings.json` is absent |
| `ANALYSIS_MAX_TOKENS` | Output budget for form → JSON analysis (streamed) |
| `ANALYSIS_THINKING` | Extended thinking on/off for analysis |
| `DETECTION_MAX_TOKENS` | Output budget for form name/category detection |
| `DETECTION_THINKING` | Extended thinking on/off for detection |

---

## Troubleshooting

Analysis errors surface in the UI as `Analysis returned no data: <reason>`. The reasons map to specific causes:

| Message | Cause | Fix |
|---|---|---|
| `The model '<x>' isn't available — it may be retired or misspelled` | The model in Settings no longer exists. Anthropic retires older models on a published schedule — `claude-sonnet-4-20250514` was retired 2026-06-15. | Set a current model in Settings (`claude-sonnet-5`), or clear the field to fall back to `MODEL_NAME` |
| `Your Anthropic API key was rejected` | Bad, revoked, or empty key | Update it in Settings |
| `Your API key doesn't have access to '<x>'` | Key is valid but the account can't use that model | Different model, or a key with access |
| `The API rejected the request for '<x>': <detail>` | A request parameter isn't supported by that model | Read the detail — it names the parameter |
| `Rate limited by the Anthropic API` | Too many requests | Wait, then retry |
| `Claude's response was cut off ... (hit the N-token output limit)` | Form JSON exceeded `ANALYSIS_MAX_TOKENS` | Run fewer pages per batch, or raise the budget in `analyzer/config.py` |

**Models are validated when you save Settings.** A retired or misspelled model is rejected immediately with a message in the Settings panel, rather than failing later mid-run. The save also checks the model's output ceiling against `ANALYSIS_MAX_TOKENS` and refuses combinations that would fail — e.g. `claude-haiku-4-5` caps output at 64,000 tokens.

**Detection failures are non-fatal.** If form name/category detection fails, the app falls back to the filename and continues; the underlying reason is written to `app.log`.

---

## Known Issues

### 1. Inline container over-generation
The prompt causes Claude to wrap too many things in `inline_container` — standalone "Date: ____" lines, signature lines, etc. You have to manually edit the JSON to remove them.

**Fix location:** `analyzer/form_analyzer.py` → `FORM_ANALYSIS_PROMPT` — tighten the `## INLINE TEXT CONTAINERS` section with explicit rules about when NOT to use inline containers.

### 2. Spacing/formatting inconsistencies
PDF spacing options sometimes produce fields too close or too far apart depending on field type mix.

**Fix location:** `generator/fields/` — each field renderer's spacing logic at the bottom of its `draw()` method, and `generator/constants.py` for default values.

### 3. FlaskWebGUI / Chromium dependency
The app requires Chromium at a hardcoded path. If Chromium moves or is missing, run `./run.sh` and open `http://127.0.0.1:5000` manually in any browser.
