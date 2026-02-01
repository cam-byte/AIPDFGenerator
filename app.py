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
import shutil
import tempfile
import traceback
import zipfile

from flask import Flask, render_template, request, send_file, jsonify

from analyzer.form_analyzer import FormAnalyzer
from generator.pdf_generator import generate_form_pdf

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, 'settings.json')

DEFAULT_PROVIDER = 'anthropic'
DEFAULT_MODEL = 'claude-sonnet-4-20250514'


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


def mask_key(key):
    """Mask an API key for display: first 6 + ... + last 4."""
    if not key or len(key) <= 12:
        return key
    return key[:6] + '...' + key[-4:]


# ---------------------------------------------------------------------------
# Process-PDF helpers
# ---------------------------------------------------------------------------

def _validate_uploads(req, tmpdir):
    """Validate and save uploaded files. Returns (pdf_paths, logo_path)."""
    pdf_files = req.files.getlist('pdf')
    pdf_files = [f for f in pdf_files if f and f.filename]

    if not pdf_files:
        raise ValueError('No PDF file uploaded')

    pdf_paths = []
    for pdf_file in pdf_files:
        if not pdf_file.filename.lower().endswith('.pdf'):
            raise ValueError(f'File must be a PDF: {pdf_file.filename}')
        pdf_path = os.path.join(tmpdir, pdf_file.filename)
        pdf_file.save(pdf_path)
        pdf_paths.append(pdf_path)

    logo_path = None
    logo_file = req.files.get('logo')
    if logo_file and logo_file.filename:
        logo_path = os.path.join(tmpdir, logo_file.filename)
        logo_file.save(logo_path)

    return pdf_paths, logo_path


def _build_business_info(req, logo_path):
    """Build business_info dict from form fields."""
    business_name = req.form.get('business_name', '').strip()

    locations = []
    locations_json = req.form.get('locations', '[]')
    try:
        locations = json.loads(locations_json)
    except json.JSONDecodeError:
        pass

    first_loc = locations[0] if locations else {}
    return {
        'logo_path': logo_path,
        'business_name': business_name,
        'locations': locations,
        'address': f"{first_loc.get('street', '')} {first_loc.get('city_state_zip', '')}".strip(),
        'phone': first_loc.get('phone', ''),
        'email': '',
    }


def _detect_and_analyze(pdf_path, api_key, model, filename):
    """Auto-detect form info and analyze PDF. Returns (form_details, form_data)."""
    analyzer = FormAnalyzer(api_key, model, {})
    form_details = analyzer.detect_form_info(pdf_path)
    if not form_details:
        base_name = os.path.splitext(filename)[0]
        form_details = {
            'form_name': base_name.replace('_', ' ').replace('-', ' ').title(),
            'category': 'General',
        }

    analyzer = FormAnalyzer(api_key, model, form_details)
    form_data = analyzer.analyze_pdf(pdf_path)

    if not form_data:
        raise RuntimeError('Analysis returned no data')

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

        pdf_paths, logo_path = _validate_uploads(request, tmpdir)
        business_info = _build_business_info(request, logo_path)

        # Collect all generated files across PDFs
        all_output_files = []  # list of (arcname, filepath)

        for pdf_path in pdf_paths:
            filename = os.path.basename(pdf_path)
            form_details, form_data = _detect_and_analyze(
                pdf_path, api_key, model, filename
            )

            form_name = form_details['form_name']
            form_key = form_name.lower().replace(' ', '_').replace('-', '_')
            form_key = ''.join(c for c in form_key if c.isalnum() or c == '_')

            json_path = os.path.join(tmpdir, f'{form_key}.json')
            with open(json_path, 'w') as f:
                json.dump(form_data, indent=2, fp=f)

            pdf_output = os.path.join(tmpdir, f'{form_key}_fillable.pdf')
            generate_form_pdf(json_path, pdf_output, business_info=business_info)

            all_output_files.append((f'{form_key}.json', json_path))
            all_output_files.append((f'{form_key}_fillable.pdf', pdf_output))

        # Build single zip with all results
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for arcname, filepath in all_output_files:
                zf.write(filepath, arcname)
        zip_buffer.seek(0)

        download_name = 'batch_output.zip' if len(pdf_paths) > 1 else f'{os.path.splitext(os.path.basename(pdf_paths[0]))[0]}.zip'

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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
