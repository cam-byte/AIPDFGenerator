#!/usr/bin/env python3
"""
Custom PDF Form Generator
=========================
Drop a PDF form and logo in this folder, run the script, and get a fillable PDF.

Workflow:
1. Drop your PDF form and logo.png in this folder
2. Run: python3 custompdf.py
3. Answer the prompts for form details and business info
4. Get your fillable PDF!

Batch Mode:
  python3 custompdf.py --batch
  Processes all PDFs in the folder, outputs to json/ and pdf/ subdirectories.

  To set up an alias, add to your ~/.zshrc or ~/.bashrc:
    alias createmultiplepdf='python3 /Users/camerondyas/Desktop/CustomPDF/custompdf.py --batch'
"""

import os
import sys
import json
import glob
import shutil
import argparse

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_output_dirs():
    """Create/clear json and pdf output directories for batch mode."""
    json_dir = os.path.join(SCRIPT_DIR, "json")
    pdf_dir = os.path.join(SCRIPT_DIR, "pdf")

    for dir_path in [json_dir, pdf_dir]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)

    return json_dir, pdf_dir


def find_all_pdfs():
    """Find all PDFs in the CustomPDF folder for batch processing."""
    pdfs = glob.glob(os.path.join(SCRIPT_DIR, "*.pdf"))
    # Exclude any output PDFs we created
    pdfs = [p for p in pdfs if not p.endswith("_fillable.pdf")]
    return pdfs


def find_pdf():
    """Find PDF in the CustomPDF folder."""
    pdfs = glob.glob(os.path.join(SCRIPT_DIR, "*.pdf"))
    # Exclude any output PDFs we created
    pdfs = [p for p in pdfs if not p.endswith("_fillable.pdf")]

    if not pdfs:
        print("\n[X] No PDF found!")
        print(f"   Drop a PDF form in: {SCRIPT_DIR}/")
        sys.exit(1)

    if len(pdfs) > 1:
        print("\n[PDF] Multiple PDFs found:")
        for i, pdf in enumerate(pdfs, 1):
            print(f"   {i}. {os.path.basename(pdf)}")
        choice = input("\nWhich one? [1]: ").strip() or "1"
        try:
            return pdfs[int(choice) - 1]
        except (ValueError, IndexError):
            return pdfs[0]

    return pdfs[0]


def find_logo():
    """Find logo in the CustomPDF folder."""
    logo_patterns = ["logo.png", "logo.jpg", "logo.jpeg", "*.png", "*.jpg"]
    for pattern in logo_patterns:
        logos = glob.glob(os.path.join(SCRIPT_DIR, pattern))
        # Filter out PDFs converted to images
        logos = [l for l in logos if not any(x in l.lower() for x in ['form', 'page', 'output'])]
        if logos:
            return logos[0]
    return None


def detect_form_info(pdf_path):
    """Use Claude to detect form name and category from PDF."""
    from analyzer.config import ANTHROPIC_API_KEY, MODEL_NAME
    from analyzer.form_analyzer import FormAnalyzer

    # Create analyzer with empty inputs (we're just detecting)
    analyzer = FormAnalyzer(ANTHROPIC_API_KEY, MODEL_NAME, {})
    return analyzer.detect_form_info(pdf_path)


def prompt_form_details(suggestion=None):
    """Prompt for form name and category, with optional suggestion."""
    print("\n" + "-" * 40)
    print("[FORM] FORM DETAILS")
    print("-" * 40)

    if suggestion:
        suggested_name = suggestion.get('form_name', '')
        suggested_category = suggestion.get('category', 'General')
        print(f"[AUTO] Detected: {suggested_name} ({suggested_category})")
        form_name = input(f"Form Name [{suggested_name}]: ").strip() or suggested_name
        category = input(f"Category [{suggested_category}]: ").strip() or suggested_category
    else:
        form_name = input("Form Name (e.g., Patient Intake Form): ").strip()
        category = input("Category (e.g., Patient Intake): ").strip()

    if not form_name:
        print("[X] Form name is required")
        sys.exit(1)

    if not category:
        category = "General"

    return {"form_name": form_name, "category": category}


def prompt_business_info(logo_path):
    """Prompt for business header information."""
    print("\n" + "-" * 40)
    print("[BUSINESS] BUSINESS INFO (for PDF header)")
    print("-" * 40)

    if logo_path:
        print(f"[OK] Logo found: {os.path.basename(logo_path)}")
    else:
        print("[!] No logo found - header will be text only")
        new_logo = input("Logo path (or press Enter to skip): ").strip()
        if new_logo and os.path.exists(new_logo):
            logo_path = new_logo

    business_name = input("Business Name: ").strip()

    # Collect locations - each with street, city/state/zip, phone
    locations = []
    print("\n[LOCATION] Enter business location(s):")
    while True:
        loc_num = len(locations) + 1
        print(f"\n  --- Location {loc_num} ---")
        street = input(f"  Street Address: ").strip()
        if street:
            city_state_zip = input(f"  City, State Zip: ").strip()
            phone = input(f"  Phone: ").strip()
            locations.append({
                "street": street,
                "city_state_zip": city_state_zip,
                "phone": phone
            })
            another = input("\n  Does this client have more locations? (y/n) [n]: ").strip().lower()
            if another not in ('y', 'yes'):
                break
        else:
            if not locations:
                print("  [!] At least one location is required")
            else:
                break

    # Build backwards-compatible fields from first location
    first_loc = locations[0] if locations else {}

    return {
        "logo_path": logo_path,
        "business_name": business_name,
        "locations": locations,
        # Backwards compatible single-location fields
        "address": f"{first_loc.get('street', '')} {first_loc.get('city_state_zip', '')}".strip(),
        "phone": first_loc.get('phone', ''),
        "email": ""
    }


def analyze_pdf_with_claude(pdf_path, form_details):
    """Use Claude to analyze PDF and generate JSON."""
    from analyzer.config import ANTHROPIC_API_KEY, MODEL_NAME
    from analyzer.form_analyzer import FormAnalyzer

    analyzer = FormAnalyzer(ANTHROPIC_API_KEY, MODEL_NAME, form_details)
    return analyzer.analyze_pdf(pdf_path)


def generate_fillable_pdf(json_path, output_path, business_info):
    """Generate fillable PDF with custom business info."""
    from generator.pdf_generator import generate_form_pdf
    generate_form_pdf(json_path, output_path, business_info=business_info)


def process_single_pdf(pdf_path, business_info, json_dir=None, pdf_dir=None, auto_detect=False):
    """
    Process a single PDF file.

    Args:
        pdf_path: Path to the input PDF
        business_info: Business info dict (reused across forms)
        json_dir: Output directory for JSON (None = SCRIPT_DIR)
        pdf_dir: Output directory for PDF (None = SCRIPT_DIR)
        auto_detect: If True, auto-detect form name/category without prompting

    Returns:
        tuple: (success: bool, form_key: str)
    """
    print(f"\n[PDF] Input: {os.path.basename(pdf_path)}")

    # Get form details - auto-detect in batch mode, prompt in interactive mode
    if auto_detect:
        detected = detect_form_info(pdf_path)
        if detected:
            form_details = detected
            print(f"[AUTO] Using: {form_details['form_name']} ({form_details.get('category', 'General')})")
        else:
            # Fallback to filename if detection fails
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            form_details = {"form_name": base_name.replace('_', ' ').title(), "category": "General"}
            print(f"[AUTO] Detection failed, using filename: {form_details['form_name']}")
    else:
        # Interactive mode - detect and show as suggestion
        detected = detect_form_info(pdf_path)
        form_details = prompt_form_details(suggestion=detected)

    # Create form key for filenames
    form_name = form_details['form_name']
    form_key = form_name.lower().replace(' ', '_').replace('-', '_')
    form_key = ''.join(c for c in form_key if c.isalnum() or c == '_')

    # Output paths
    json_output_dir = json_dir or SCRIPT_DIR
    pdf_output_dir = pdf_dir or SCRIPT_DIR
    json_output = os.path.join(json_output_dir, f"{form_key}.json")
    pdf_output = os.path.join(pdf_output_dir, f"{form_key}_fillable.pdf")

    # Step 1: Analyze PDF with Claude
    print("\n" + "-" * 40)
    print("[SEARCH] STEP 1: Analyzing PDF with Claude AI...")
    print("-" * 40)

    try:
        form_data = analyze_pdf_with_claude(pdf_path, form_details)
    except Exception as e:
        print(f"\n[X] Claude analysis failed: {e}")
        return False, form_key

    if not form_data:
        print("\n[X] Failed to generate form structure")
        return False, form_key

    # Save JSON
    with open(json_output, 'w') as f:
        json.dump(form_data, indent=2, fp=f)
    print(f"[OK] JSON saved: {os.path.basename(json_output)}")

    # Step 2: Generate fillable PDF
    print("\n" + "-" * 40)
    print("[PRINT] STEP 2: Generating fillable PDF...")
    print("-" * 40)

    try:
        generate_fillable_pdf(json_output, pdf_output, business_info)
        print(f"[OK] PDF saved: {os.path.basename(pdf_output)}")
    except Exception as e:
        print(f"\n[!] PDF generation failed: {e}")
        print("   JSON was saved - you can fix and regenerate manually")
        return False, form_key

    return True, form_key


def batch_process():
    """Process all PDFs in the folder in batch mode."""
    print("\n" + "=" * 50)
    print("  [BATCH] BATCH PDF FORM GENERATOR")
    print("=" * 50)

    # Find all PDFs
    pdfs = find_all_pdfs()
    if not pdfs:
        print("\n[X] No PDFs found!")
        print(f"   Drop PDF forms in: {SCRIPT_DIR}/")
        sys.exit(1)

    print(f"\n[QUEUE] Found {len(pdfs)} PDF(s) to process:")
    for pdf in pdfs:
        print(f"   - {os.path.basename(pdf)}")

    # Set up output directories (clears if exists, creates if not)
    json_dir, pdf_dir = setup_output_dirs()
    print(f"\n[FOLDER] Output directories created:")
    print(f"   - {json_dir}/")
    print(f"   - {pdf_dir}/")

    # Find logo
    logo_path = find_logo()

    # Get business info once for all forms
    business_info = prompt_business_info(logo_path)

    # Process each PDF
    results = []
    for i, pdf_path in enumerate(pdfs, 1):
        print("\n" + "=" * 50)
        print(f"  [{i}/{len(pdfs)}] Processing: {os.path.basename(pdf_path)}")
        print("=" * 50)

        success, form_key = process_single_pdf(
            pdf_path, business_info, json_dir=json_dir, pdf_dir=pdf_dir, auto_detect=True
        )
        results.append((os.path.basename(pdf_path), success, form_key))

    # Summary
    print("\n" + "=" * 50)
    print("  [DONE] BATCH COMPLETE!")
    print("=" * 50)

    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"\n[OK] Successful: {len(successful)}/{len(results)}")
    if successful:
        for pdf_name, _, form_key in successful:
            print(f"   - {pdf_name} -> {form_key}_fillable.pdf")

    if failed:
        print(f"\n[X] Failed: {len(failed)}/{len(results)}")
        for pdf_name, _, form_key in failed:
            print(f"   - {pdf_name}")

    print(f"\n[FOLDER] Output locations:")
    print(f"   JSON files: {json_dir}/")
    print(f"   PDF files:  {pdf_dir}/")


def main():
    """Interactive mode - process PDFs one at a time with option to repeat."""
    business_info = None
    logo_path = None

    while True:
        print("\n" + "=" * 50)
        print("  [CYCLE] CUSTOM PDF FORM GENERATOR")
        print("=" * 50)

        # Find PDF
        pdf_path = find_pdf()

        # Find logo (only on first run)
        if logo_path is None:
            logo_path = find_logo()

        # Get business info (only on first run)
        if business_info is None:
            business_info = prompt_business_info(logo_path)
        else:
            print("\n[REUSE] Using saved business info:")
            print(f"   Business: {business_info.get('business_name', 'N/A')}")
            locations = business_info.get('locations', [])
            if locations:
                for i, loc in enumerate(locations, 1):
                    print(f"   Location {i}: {loc.get('street', '')} | {loc.get('city_state_zip', '')} | {loc.get('phone', '')}")
            else:
                print(f"   Address: {business_info.get('address', 'N/A')}")
                print(f"   Phone:   {business_info.get('phone', 'N/A')}")

        success, form_key = process_single_pdf(pdf_path, business_info)

        # Summary for this form
        print("\n" + "=" * 50)
        if success:
            print("  [OK] COMPLETE!")
        else:
            print("  [!] COMPLETED WITH ERRORS")
        print("=" * 50)
        print(f"\n[FOLDER] Output files in {SCRIPT_DIR}/:")
        print(f"   - {form_key}.json")
        json_output = os.path.join(SCRIPT_DIR, f"{form_key}.json")
        pdf_output = os.path.join(SCRIPT_DIR, f"{form_key}_fillable.pdf")
        if os.path.exists(pdf_output):
            print(f"   - {form_key}_fillable.pdf")

        # Ask if they want to create another form
        print("\n" + "-" * 40)
        another = input("Create another form? (y/n) [n]: ").strip().lower()
        if another not in ('y', 'yes'):
            print("\n[BYE] Done! Your business info was reused for all forms.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Custom PDF Form Generator - Convert PDFs to fillable forms"
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Batch mode: process all PDFs in folder, output to json/ and pdf/ subdirectories'
    )
    args = parser.parse_args()

    try:
        if args.batch:
            batch_process()
        else:
            main()
    except KeyboardInterrupt:
        print("\n\n[!] Cancelled")
        sys.exit(1)
