#!/usr/bin/env python3
"""
Flask Web UI for AIPDFGenerator
================================
Run: python3 app.py
Open: http://127.0.0.1:5000
"""

import os
import io
import json
import logging
import shutil
import tempfile
import traceback
import zipfile

from flask import Flask, render_template, request, send_file, jsonify

from analyzer.form_analyzer import FormAnalyzer
from generator.pdf_generator import generate_form_pdf
from flaskwebgui import FlaskUI

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, 'settings.json')

# The desktop launcher (SchemaForm.app) runs this with stdout/stderr sent to
# /dev/null, so anything printed there is unrecoverable. Log to a file too so
# analysis failures are diagnosable after the fact.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(SCRIPT_DIR, 'app.log')),
        logging.StreamHandler(),
    ],
)

DEFAULT_PROVIDER = 'anthropic'

try:
    from analyzer.config import MODEL_NAME as DEFAULT_MODEL
except ImportError:
    DEFAULT_MODEL = 'claude-sonnet-5'

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def load_settings():
    """Load settings from settings.json, falling back to .env / defaults."""
    settings = {
        'provider': DEFAULT_PROVIDER,
        'api_key': '',
        'model': DEFAULT_MODEL,
    }

    # Try settings.json first
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r') as f:
                saved = json.load(f)
            settings.update({k: v for k, v in saved.items() if v})
            return settings
        except (json.JSONDecodeError, IOError):
            pass

    # Fall back to .env via analyzer config
    try:
        from analyzer.config import ANTHROPIC_API_KEY, MODEL_NAME
        if ANTHROPIC_API_KEY:
            settings['api_key'] = ANTHROPIC_API_KEY
        if MODEL_NAME:
            settings['model'] = MODEL_NAME
    except ImportError:
        pass

    return settings


def save_settings(data):
    """Persist settings to settings.json."""
    with open(SETTINGS_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def validate_model(api_key, model):
    """Check a model is usable before saving it. Returns an error string, or None.

    Network problems return None — a flaky connection shouldn't block saving.
    """
    if not api_key or not model:
        return None

    import anthropic
    from analyzer.config import ANALYSIS_MAX_TOKENS

    try:
        info = anthropic.Anthropic(api_key=api_key).models.retrieve(model)
    except anthropic.NotFoundError:
        return (f"Model '{model}' isn't available — it may be retired or misspelled. "
                "Try claude-sonnet-5.")
    except anthropic.AuthenticationError:
        return "That API key was rejected by Anthropic."
    except anthropic.PermissionDeniedError:
        return f"This API key doesn't have access to '{model}'."
    except Exception:
        return None

    cap = getattr(info, 'max_tokens', None)
    if cap and ANALYSIS_MAX_TOKENS > cap:
        return (f"'{model}' caps output at {cap:,} tokens, but ANALYSIS_MAX_TOKENS in "
                f"analyzer/config.py is {ANALYSIS_MAX_TOKENS:,}. Lower it or pick another model.")

    return None


def mask_key(key):
    """Mask an API key for display: first 6 + ... + last 4."""
    if not key or len(key) <= 12:
        return key
    return key[:6] + '...' + key[-4:]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_city(city_state_zip):
    """Extract a slug from a city/state/zip string.

    'Austin, TX 78701' -> 'austin'
    'New York, NY 10001' -> 'new_york'
    """
    text = (city_state_zip or '').strip()
    if ',' in text:
        city = text.split(',')[0].strip()
    else:
        city = text.split()[0] if text else 'unknown'
    return city.lower().replace(' ', '_')


def _write_html(output_path, form_key):
    """Write an HTML file containing the autofill template tag."""
    with open(output_path, 'w') as f:
        f.write('{{!/autofills/forms/form_fields/' + form_key + '->content->' + form_key + '}}')


# ---------------------------------------------------------------------------
# Process-PDF helpers
# ---------------------------------------------------------------------------

def _sanitize_form_key(raw):
    """Normalize a form key to lowercase alphanumerics and underscores.

    Also makes user input safe to use as a filename. Returns '' when nothing
    usable remains, in which case the caller falls back to the detected name.
    """
    if not raw:
        return ''
    key = raw.strip().lower().replace(' ', '_').replace('-', '_')
    # ASCII only — the key becomes a filename and a CMS autofill tag
    key = ''.join(c for c in key if (c.isalnum() and c.isascii()) or c == '_')
    return key.strip('_')[:60]


def _validate_uploads(req, tmpdir):
    """Validate and save uploaded files. Returns (upload_paths, logo_path).

    upload_paths is a list of (file_path, file_type, form_key) tuples where
    file_type is 'pdf' or 'image' and form_key is the user's override ('' if none).
    """
    raw_files = req.files.getlist('pdf')
    raw_keys = req.form.getlist('form_key')

    # Pair by position before filtering, so each key stays with its own file
    paired = [(f, raw_keys[i] if i < len(raw_keys) else '')
              for i, f in enumerate(raw_files)]
    paired = [(f, k) for f, k in paired if f and f.filename]

    if not paired:
        raise ValueError('No file uploaded')

    upload_paths = []
    for pdf_file, raw_key in paired:
        ext = os.path.splitext(pdf_file.filename)[1].lower()
        if ext == '.pdf':
            file_type = 'pdf'
        elif ext in ALLOWED_IMAGE_EXTENSIONS:
            file_type = 'image'
        else:
            raise ValueError(f'Unsupported file type: {pdf_file.filename}. Accepted: PDF, PNG, JPEG, WEBP, GIF')
        file_path = os.path.join(tmpdir, pdf_file.filename)
        pdf_file.save(file_path)
        upload_paths.append((file_path, file_type, _sanitize_form_key(raw_key)))

    logo_path = None
    logo_file = req.files.get('logo')
    if logo_file and logo_file.filename:
        logo_path = os.path.join(tmpdir, logo_file.filename)
        logo_file.save(logo_path)

    return upload_paths, logo_path


def _build_business_info(req, logo_path):
    """Build business_info dict from form fields."""
    business_name = req.form.get('business_name', '').strip()

    locations = []
    locations_json = req.form.get('locations', '[]')
    try:
        locations = json.loads(locations_json)
    except json.JSONDecodeError:
        pass

    separate_locations = req.form.get('separate_locations', '0') == '1'

    try:
        pdf_options = json.loads(req.form.get('pdf_options', '{}'))
    except (json.JSONDecodeError, TypeError):
        pdf_options = {}

    first_loc = locations[0] if locations else {}
    return {
        'logo_path': logo_path,
        'business_name': business_name,
        'locations': locations,
        'separate_locations': separate_locations,
        'pdf_options': pdf_options,
        'address': f"{first_loc.get('street', '')} {first_loc.get('city_state_zip', '')}".strip(),
        'phone': first_loc.get('phone', ''),
        'email': '',
    }


def _detect_and_analyze(file_path, api_key, model, filename, file_type='pdf', form_key=''):
    """Auto-detect form info and analyze a PDF or image. Returns (form_details, form_data).

    form_key, when supplied, overrides the key derived from the detected name. The
    detected name still supplies the human-readable title on the form itself.
    """
    analyzer = FormAnalyzer(api_key, model, {})

    if file_type == 'image':
        form_details = analyzer.detect_form_info_from_image(file_path)
    else:
        form_details = analyzer.detect_form_info(file_path)

    if not form_details:
        base_name = os.path.splitext(filename)[0]
        form_details = {
            'form_name': base_name.replace('_', ' ').replace('-', ' ').title(),
            'category': 'General',
        }

    if form_key:
        form_details['form_key'] = form_key

    analyzer = FormAnalyzer(api_key, model, form_details)

    if file_type == 'image':
        form_data = analyzer.analyze_image(file_path)
    else:
        form_data = analyzer.analyze_pdf(file_path)

    if not form_data:
        reason = analyzer.last_error
        message = f'Analysis returned no data: {reason}' if reason else 'Analysis returned no data'
        raise RuntimeError(message)

    return form_details, form_data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/settings', methods=['GET'])
def get_settings():
    settings = load_settings()
    return jsonify({
        'provider': settings['provider'],
        'api_key_masked': mask_key(settings['api_key']),
        'has_key': bool(settings['api_key']),
        'model': settings['model'],
    })


@app.route('/settings', methods=['POST'])
def post_settings():
    data = request.get_json(silent=True) or {}

    current = load_settings()

    provider = data.get('provider', current['provider'])
    api_key = data.get('api_key', '').strip()
    model = data.get('model', '').strip() or current['model']

    # If the key field is empty or still the masked version, keep the old key
    if not api_key or '...' in api_key:
        api_key = current['api_key']

    invalid = validate_model(api_key, model)
    if invalid:
        return jsonify({'error': invalid}), 400

    save_settings({
        'provider': provider,
        'api_key': api_key,
        'model': model,
    })

    return jsonify({'ok': True, 'api_key_masked': mask_key(api_key)})


@app.route('/process', methods=['POST'])
def process_pdf():
    tmpdir = tempfile.mkdtemp()

    try:
        settings = load_settings()
        api_key = settings['api_key']
        model = settings['model']

        if not api_key:
            return jsonify({'error': 'No API key configured. Open Settings and add one.'}), 400

        upload_paths, logo_path = _validate_uploads(request, tmpdir)
        business_info = _build_business_info(request, logo_path)

        # Collect all generated files across uploads
        all_output_files = []  # list of (arcname, filepath)

        separate = business_info.get('separate_locations', False)
        locations = business_info.get('locations', [])

        for file_path, file_type, custom_key in upload_paths:
            filename = os.path.basename(file_path)
            form_details, form_data = _detect_and_analyze(
                file_path, api_key, model, filename, file_type, custom_key
            )

            form_key = custom_key or _sanitize_form_key(form_details['form_name']) or 'form'

            if separate and len(locations) >= 2:
                # Generate a separate set of files per location
                for loc in locations:
                    city = _extract_city(loc.get('city_state_zip', ''))
                    loc_key = f'{form_key}_{city}'

                    loc_info = dict(business_info)
                    loc_info['locations'] = [loc]
                    loc_info['address'] = f"{loc.get('street', '')} {loc.get('city_state_zip', '')}".strip()
                    loc_info['phone'] = loc.get('phone', '')

                    json_path = os.path.join(tmpdir, f'{loc_key}.json')
                    with open(json_path, 'w') as f:
                        json.dump(form_data, indent=2, fp=f)

                    pdf_output = os.path.join(tmpdir, f'{loc_key}_fillable.pdf')
                    generate_form_pdf(json_path, pdf_output, business_info=loc_info)

                    html_path = os.path.join(tmpdir, f'{loc_key}.html')
                    _write_html(html_path, loc_key)

                    all_output_files.append((f'json/{loc_key}.json', json_path))
                    all_output_files.append((f'html/{loc_key}.html', html_path))
                    all_output_files.append((f'pdf/{loc_key}_fillable.pdf', pdf_output))
            else:
                # Normal mode: single set of files
                json_path = os.path.join(tmpdir, f'{form_key}.json')
                with open(json_path, 'w') as f:
                    json.dump(form_data, indent=2, fp=f)

                pdf_output = os.path.join(tmpdir, f'{form_key}_fillable.pdf')
                generate_form_pdf(json_path, pdf_output, business_info=business_info)

                html_path = os.path.join(tmpdir, f'{form_key}.html')
                _write_html(html_path, form_key)

                all_output_files.append((f'json/{form_key}.json', json_path))
                all_output_files.append((f'html/{form_key}.html', html_path))
                all_output_files.append((f'pdf/{form_key}_fillable.pdf', pdf_output))

        # Build single zip with all results
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for arcname, filepath in all_output_files:
                zf.write(filepath, arcname)
        zip_buffer.seek(0)

        download_name = ('batch_output.zip' if len(upload_paths) > 1
                         else f'{os.path.splitext(os.path.basename(upload_paths[0][0]))[0]}.zip')

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=download_name,
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.route('/regenerate', methods=['POST'])
def regenerate_pdf():
    """Regenerate fillable PDFs from previously-exported JSON definitions."""
    tmpdir = tempfile.mkdtemp()

    try:
        json_files = request.files.getlist('json')
        json_files = [f for f in json_files if f and f.filename]

        if not json_files:
            return jsonify({'error': 'No JSON file uploaded'}), 400

        # Save logo if provided
        logo_path = None
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            logo_path = os.path.join(tmpdir, logo_file.filename)
            logo_file.save(logo_path)

        business_info = _build_business_info(request, logo_path)

        pdf_outputs = []
        separate = business_info.get('separate_locations', False)
        locations = business_info.get('locations', [])

        for json_file in json_files:
            if not json_file.filename.lower().endswith('.json'):
                raise ValueError(f'File must be JSON: {json_file.filename}')

            json_path = os.path.join(tmpdir, json_file.filename)
            json_file.save(json_path)

            # Load the JSON to extract form_key
            with open(json_path, 'r') as f:
                form_data = json.load(f)

            # The top-level key is the form_key
            form_key = list(form_data.keys())[0]

            if separate and len(locations) >= 2:
                for loc in locations:
                    city = _extract_city(loc.get('city_state_zip', ''))
                    loc_key = f'{form_key}_{city}'

                    loc_info = dict(business_info)
                    loc_info['locations'] = [loc]
                    loc_info['address'] = f"{loc.get('street', '')} {loc.get('city_state_zip', '')}".strip()
                    loc_info['phone'] = loc.get('phone', '')

                    pdf_output = os.path.join(tmpdir, f'{loc_key}_fillable.pdf')
                    generate_form_pdf(json_path, pdf_output, business_info=loc_info)
                    pdf_outputs.append(pdf_output)
            else:
                pdf_output = os.path.join(tmpdir, f'{form_key}_fillable.pdf')
                generate_form_pdf(json_path, pdf_output, business_info=business_info)
                pdf_outputs.append(pdf_output)

        # Single PDF: return it directly. Multiple: zip them flat.
        if len(pdf_outputs) == 1:
            return send_file(
                pdf_outputs[0],
                mimetype='application/pdf',
                as_attachment=True,
                download_name=os.path.basename(pdf_outputs[0]),
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf_path in pdf_outputs:
                zf.write(pdf_path, os.path.basename(pdf_path))
        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='regenerated.zip',
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    # app.run(debug=True, port=5000)
    FlaskUI(
        app=app,
        server="flask",
        width=1200,
        height=900,
        browser_path="/Applications/Chromium.app/Contents/MacOS/Chromium",
        extra_flags=["--password-store=basic", "--use-mock-keychain"],
        auto_close=True,
    ).run()
