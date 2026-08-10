# form_analyzer.py
import anthropic
import base64
import json
import io
import logging
import os
from pdf2image import convert_from_path
from PIL import Image
from typing import Dict, Any, Optional

from .config import (
    ANALYSIS_MAX_TOKENS,
    ANALYSIS_THINKING,
    DETECTION_MAX_TOKENS,
    DETECTION_THINKING,
)

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _thinking(enabled: bool) -> Dict[str, str]:
    """Map a config toggle to the API's thinking parameter."""
    return {"type": "adaptive"} if enabled else {"type": "disabled"}

# Quick prompt to detect form name/category from PDF
FORM_DETECTION_PROMPT = """Look at this PDF form and tell me:
1. What is the form's title/name? Keep it SHORT — 2 to 5 words max (e.g., "Patient Registration", "Medical History", "HIPAA Authorization", "Treatment Consent"). Do NOT use long verbose titles. Shorten and simplify.
2. What category does it belong to? (e.g., "Patient Intake", "Medical History", "Consent", "Insurance", "General") — 3-5 words max.

Respond in this exact JSON format only, no other text:
{"form_name": "Short Form Title", "category": "Category Name"}

Look for the form title at the top of the document, in headers, or any prominent text that indicates what this form is for. Always simplify the title — never copy it verbatim if it's long."""

# The prompt template for form analysis
FORM_ANALYSIS_PROMPT = """Analyze this PDF form and generate a complete JSON structure for my fillable PDF form generator.

**User Provided Info:**
- Form Name: {form_name}
- Category: {category}

## OUTPUT FORMAT

{{
  "{form_name_key}": {{
    "settings": {{}},
    "content": {{
      "{form_name_key}": {{
        "form_name": "{form_name_key}",
        "submission_url": "{{{{%/processors/forms/pdf_form_email}}}}",
        "subject": "<generate a concise email subject line for this form submission notification, e.g. 'New Patient Intake Form Submission'>",
        "confirmation": "/custom/content/thank_you/thank_you.html",
        "pdf": "/custom/pdfs/{form_name_key}.pdf",
        "category": "{category}",
        "type": "intake",
        "fields": [
          // ALL FIELDS GO HERE
        ]
      }}
    }}
  }}
}}

---

## IMPORTANT NOTES ON METADATA FIELDS
- **subject**: This is the EMAIL SUBJECT LINE sent to the client when the form is submitted. Generate a clear, professional subject like "New Patient Intake Form Submission" or "New Medical History Form Received". It should tell the recipient what form was submitted.

## REQUIRED WRAPPER (Start of fields array)

{{"name": "pdf_download", "label": "<i class=\\"fad fa-file-download\\"></i>Download Printable Version", "type": "pdf_download"}},
{{"name": "form_container", "type": "group_start"}},
{{"name": "form_header", "label": "<h1>{form_name}</h1>", "type": "label"}},
{{"name": "form_content_container", "type": "group_start"}},

## REQUIRED CLOSING (End of fields array)

{{"label": "Submit", "type": "submit"}},
{{"type": "group_end"}},
{{"type": "group_end"}}

---

## FIELD TYPES

**Text input:** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "text", "required": false}}`

**Date field:** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "date", "required": false}}`

**Email:** `{{"name": "email_address", "label": "Email Address", "email_label": "Email Address", "type": "email", "required": false}}`

**Textarea (for "explain", "describe", "list" fields):** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "textarea", "required": false}}`

**Select dropdown:** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "select", "option": ["Option 1", "Option 2"]}}`

**Yes/No question (use radio):** `{{"name": "field_name", "label": "Question?", "email_label": "Question?", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}}`

**Multiple choice - pick ONE (use radio):** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "radio", "option": ["Option A", "Option B", "Option C"]}}`

**Multiple choice - pick MANY (use checkbox):** `{{"name": "field_name", "label": "Label", "email_label": "Label", "type": "checkbox", "option": {{"option_1": "Option 1", "option_2": "Option 2", "option_3": "Option 3"}}}}`

**Agreement checkbox:** `{{"name": "acknowledgement", "label": "", "email_label": "", "type": "checkbox", "option": {{"checked": "<p>I certify that the information provided is accurate...</p>"}}}}`

**Section header (h3):** `{{"name": "content", "label": "<h3>Section Title</h3>", "type": "label"}}`

**Subheader with instruction (h4):** `{{"name": "", "label": "<h4>Subheader <span>Instructions go in span tags</span></h4>", "type": "label"}}`

**Paragraph content:** `{{"name": "", "label": "<p>Paragraph text here...</p>", "type": "label"}}`

**Inline text (for fill-in-the-blank paragraphs):** `{{"label": "<p>Text segment here</p>", "type": "inline_text"}}`

---

## INLINE TEXT CONTAINERS (Fill-in-the-blank paragraphs)

Use inline containers when you see paragraphs with blank lines for user input embedded within the text. These create fill-in-the-blank style forms where text and input fields flow together on the same line.

**HOW TO RECOGNIZE:** Look for sentences/paragraphs with underlined blank spaces (______) or boxes within the text flow, like:
- "I, _______, hereby authorize..."
- "Patient Name: _______ Date of Birth: _______"
- "I certify that I have insurance coverage with _______ and assign directly to Dr. _______"

**STRUCTURE:**
1. Wrap everything in `inline_container` group
2. Use `inline_text` type for text segments (with `<p>` tags)
3. Use regular `text` fields with empty labels for the blanks
4. Close with `group_end`

**Example: Authorization paragraph with blanks**

PDF shows: "I, _______, hereby authorize Dr. _______ to release my medical records."

{{"name": "inline_container", "type": "group_start"}},
{{"label": "<p>I,</p>", "type": "inline_text"}},
{{"name": "patient_name_auth", "label": "", "email_label": "Patient Name", "type": "text", "required": false}},
{{"label": "<p>hereby authorize Dr.</p>", "type": "inline_text"}},
{{"name": "doctor_name_auth", "label": "", "email_label": "Doctor Name", "type": "text", "required": false}},
{{"label": "<p>to release my medical records.</p>", "type": "inline_text"}},
{{"type": "group_end"}}

**Example: Insurance assignment**

PDF shows: "I certify that I have insurance coverage with _______ and assign directly to Dr. _______ all insurance benefits..."

{{"name": "inline_container", "type": "group_start"}},
{{"label": "<p>I certify that I have insurance coverage with</p>", "type": "inline_text"}},
{{"name": "insurance_company", "label": "", "email_label": "Insurance Company", "type": "text", "required": false}},
{{"label": "<p>and assign directly to Dr.</p>", "type": "inline_text"}},
{{"name": "assigned_doctor", "label": "", "email_label": "Assigned Doctor", "type": "text", "required": false}},
{{"label": "<p>all insurance benefits, if any, otherwise payable to me for services rendered.</p>", "type": "inline_text"}},
{{"type": "group_end"}}

**Example: Signature and Date line**

PDF shows: "All information is true and complete. SIGNATURE: _________________ DATE: _________"

{{"name": "inline_container", "type": "group_start"}},
{{"label": "<p>All information is true and complete. SIGNATURE:</p>", "type": "inline_text"}},
{{"name": "patient_signature", "label": "", "email_label": "Patient Signature", "type": "text", "required": false}},
{{"label": "<p>DATE:</p>", "type": "inline_text"}},
{{"name": "signature_date", "label": "", "email_label": "Signature Date", "type": "text", "required": false}},
{{"type": "group_end"}}

**Example: Initials line**

PDF shows: "I understand this policy. INITIALS: _______"

{{"name": "inline_container", "type": "group_start"}},
{{"label": "<p>I understand this policy. INITIALS:</p>", "type": "inline_text"}},
{{"name": "patient_initials", "label": "", "email_label": "Patient Initials", "type": "text", "required": false}},
{{"type": "group_end"}}

**IMPORTANT:**
- Text fields inside inline containers should have empty `label` but descriptive `email_label`
- Break text at EACH blank - don't combine multiple blanks in one inline_text
- Include punctuation and spacing naturally in the text segments

---

## LAYOUT GROUPS - MANDATORY USAGE

**CRITICAL RULES:**
1. You MUST use the exact group names below - no custom names
2. You MUST use name_details when you see Last Name, First Name, Initial/M.I. fields
3. You MUST use address_details when you see Address, City, State, Zip fields
4. You MUST use inline_container when you see paragraphs with blanks (___) for user input
5. Keep related fields TOGETHER - don't split address fields with phone numbers

**VALID LAYOUT GROUPS:**

1. **name_details** - REQUIRED when form has Last Name, First Name, and Initial/M.I. fields
   {{"name": "*name_details", "type": "group_start"}}
   {{"name": "last_name", "label": "Last Name", "email_label": "Last Name", "type": "text", "required": false}}
   {{"name": "first_name", "label": "First Name", "email_label": "First Name", "type": "text", "required": false}}
   {{"name": "middle_initial", "label": "M.I.", "email_label": "Middle Initial", "type": "text", "required": false}}
   {{"type": "group_end"}}

2. **address_details** - REQUIRED when form has Address, City, State, Zip fields (keep phone OUTSIDE this group)
   {{"name": "*address_details", "type": "group_start"}}
   {{"name": "mailing_address", "label": "Address", "email_label": "Address", "type": "text", "required": false}}
   {{"name": "city", "label": "City", "email_label": "City", "type": "text", "required": false}}
   {{"name": "state", "label": "State", "email_label": "State", "type": "text", "required": false}}
   {{"name": "zip", "label": "Zip", "email_label": "Zip", "type": "text", "required": false}}
   {{"type": "group_end"}}
   {{"name": "home_phone", "label": "Home Ph.", "email_label": "Home Phone", "type": "text", "required": false}}

3. **two_columns** - Use for lists of 8-15 similar Yes/No radio questions or checkboxes.
   {{"name": "two_columns", "type": "group_start"}}
   ... put ALL related fields here ...
   {{"type": "group_end"}}

4. **four_columns** - Use for lists of 16 or more similar Yes/No radio questions or checkboxes.
   {{"name": "four_columns", "type": "group_start"}}
   ... put ALL related fields here ...
   {{"type": "group_end"}}

5. **Dental chart groups** - For tooth selection diagrams (see DENTAL CHART section below)
   - `permanent` - Container for adult teeth section
   - `deciduous` - Container for baby teeth section
   - `top_row` - Container for upper teeth row
   - `bottom_row` - Container for lower teeth row
   - `tooth_container` - Container for teeth within a row
   - `tooth` - Wrapper for each individual tooth checkbox (REQUIRED around each tooth)

5. **inline_container** - REQUIRED for ANY paragraph containing blanks/underscores for user input
   This includes SIGNATURE:_____, DATE:_____, INITIALS:_____ lines
   {{"name": "inline_container", "type": "group_start"}}
   ... inline_text and text fields alternating ...
   {{"type": "group_end"}}

**Container groups (for structure only, no layout effect):**
- form_container
- form_content_container

---

## DENTAL CHART GROUPS (Tooth Selection)

**HOW TO RECOGNIZE DENTAL CHARTS:** Look for checkboxes with numbers 1-32 OR letters A-T, often with tooth illustrations. The PDF may call them anything ("Adult", "Primary", "Baby", etc.) or nothing at all - **recognize them by the numbering pattern:**

- **Checkboxes numbered 1-32** = PERMANENT (adult) teeth → Always label as "Permanent"
- **Checkboxes lettered A-T** = DECIDUOUS (baby) teeth → Always label as "Deciduous"

**ALWAYS INCLUDE BOTH PERMANENT AND DECIDUOUS SECTIONS** - even if the PDF only shows one type, include both. The user can remove what they don't need.

**CRITICAL: Use this EXACT nested group structure. Each tooth must be wrapped in its own "tooth" group.**

**PERMANENT TEETH STRUCTURE (teeth 1-16 top, 32-17 bottom):**

{{"name": "", "label": "<h4>Permanent</h4>", "type": "label"}},
{{"name": "permanent", "type": "group_start"}},
{{"name": "top_row", "type": "group_start"}},
{{"name": "tooth_container", "type": "group_start"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_1", "label": "1", "email_label": "1", "type": "checkbox", "option": {{"checked": "1"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_2", "label": "2", "email_label": "2", "type": "checkbox", "option": {{"checked": "2"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_3", "label": "3", "email_label": "3", "type": "checkbox", "option": {{"checked": "3"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_4", "label": "4", "email_label": "4", "type": "checkbox", "option": {{"checked": "4"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_5", "label": "5", "email_label": "5", "type": "checkbox", "option": {{"checked": "5"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_6", "label": "6", "email_label": "6", "type": "checkbox", "option": {{"checked": "6"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_7", "label": "7", "email_label": "7", "type": "checkbox", "option": {{"checked": "7"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_8", "label": "8", "email_label": "8", "type": "checkbox", "option": {{"checked": "8"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_9", "label": "9", "email_label": "9", "type": "checkbox", "option": {{"checked": "9"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_10", "label": "10", "email_label": "10", "type": "checkbox", "option": {{"checked": "10"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_11", "label": "11", "email_label": "11", "type": "checkbox", "option": {{"checked": "11"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_12", "label": "12", "email_label": "12", "type": "checkbox", "option": {{"checked": "12"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_13", "label": "13", "email_label": "13", "type": "checkbox", "option": {{"checked": "13"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_14", "label": "14", "email_label": "14", "type": "checkbox", "option": {{"checked": "14"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_15", "label": "15", "email_label": "15", "type": "checkbox", "option": {{"checked": "15"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_16", "label": "16", "email_label": "16", "type": "checkbox", "option": {{"checked": "16"}}}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"name": "bottom_row", "type": "group_start"}},
{{"name": "tooth_container", "type": "group_start"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_32", "label": "32", "email_label": "32", "type": "checkbox", "option": {{"checked": "32"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_31", "label": "31", "email_label": "31", "type": "checkbox", "option": {{"checked": "31"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_30", "label": "30", "email_label": "30", "type": "checkbox", "option": {{"checked": "30"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_29", "label": "29", "email_label": "29", "type": "checkbox", "option": {{"checked": "29"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_28", "label": "28", "email_label": "28", "type": "checkbox", "option": {{"checked": "28"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_27", "label": "27", "email_label": "27", "type": "checkbox", "option": {{"checked": "27"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_26", "label": "26", "email_label": "26", "type": "checkbox", "option": {{"checked": "26"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_25", "label": "25", "email_label": "25", "type": "checkbox", "option": {{"checked": "25"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_24", "label": "24", "email_label": "24", "type": "checkbox", "option": {{"checked": "24"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_23", "label": "23", "email_label": "23", "type": "checkbox", "option": {{"checked": "23"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_22", "label": "22", "email_label": "22", "type": "checkbox", "option": {{"checked": "22"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_21", "label": "21", "email_label": "21", "type": "checkbox", "option": {{"checked": "21"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_20", "label": "20", "email_label": "20", "type": "checkbox", "option": {{"checked": "20"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_19", "label": "19", "email_label": "19", "type": "checkbox", "option": {{"checked": "19"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_18", "label": "18", "email_label": "18", "type": "checkbox", "option": {{"checked": "18"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_17", "label": "17", "email_label": "17", "type": "checkbox", "option": {{"checked": "17"}}}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}},

**DECIDUOUS TEETH STRUCTURE (teeth A-J top, T-K bottom):**

{{"name": "", "label": "<h4>Deciduous</h4>", "type": "label"}},
{{"name": "deciduous", "type": "group_start"}},
{{"name": "top_row", "type": "group_start"}},
{{"name": "tooth_container", "type": "group_start"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_a", "label": "A", "email_label": "A", "type": "checkbox", "option": {{"checked": "A"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_b", "label": "B", "email_label": "B", "type": "checkbox", "option": {{"checked": "B"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_c", "label": "C", "email_label": "C", "type": "checkbox", "option": {{"checked": "C"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_d", "label": "D", "email_label": "D", "type": "checkbox", "option": {{"checked": "D"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_e", "label": "E", "email_label": "E", "type": "checkbox", "option": {{"checked": "E"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_f", "label": "F", "email_label": "F", "type": "checkbox", "option": {{"checked": "F"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_g", "label": "G", "email_label": "G", "type": "checkbox", "option": {{"checked": "G"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_h", "label": "H", "email_label": "H", "type": "checkbox", "option": {{"checked": "H"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_i", "label": "I", "email_label": "I", "type": "checkbox", "option": {{"checked": "I"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_j", "label": "J", "email_label": "J", "type": "checkbox", "option": {{"checked": "J"}}}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"name": "bottom_row", "type": "group_start"}},
{{"name": "tooth_container", "type": "group_start"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_t", "label": "T", "email_label": "T", "type": "checkbox", "option": {{"checked": "T"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_s", "label": "S", "email_label": "S", "type": "checkbox", "option": {{"checked": "S"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_r", "label": "R", "email_label": "R", "type": "checkbox", "option": {{"checked": "R"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_q", "label": "Q", "email_label": "Q", "type": "checkbox", "option": {{"checked": "Q"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_p", "label": "P", "email_label": "P", "type": "checkbox", "option": {{"checked": "P"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_o", "label": "O", "email_label": "O", "type": "checkbox", "option": {{"checked": "O"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_n", "label": "N", "email_label": "N", "type": "checkbox", "option": {{"checked": "N"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_m", "label": "M", "email_label": "M", "type": "checkbox", "option": {{"checked": "M"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_l", "label": "L", "email_label": "L", "type": "checkbox", "option": {{"checked": "L"}}}},
{{"type": "group_end"}},
{{"name": "tooth", "type": "group_start"}},
{{"name": "tooth_k", "label": "K", "email_label": "K", "type": "checkbox", "option": {{"checked": "K"}}}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}},
{{"type": "group_end"}}

**IMPORTANT:**
- Copy this EXACT nested structure when you see ANY dental chart with numbered/lettered checkboxes
- Always include BOTH Permanent AND Deciduous sections (user will remove what's not needed)
- Always use headers "<h4>Permanent</h4>" and "<h4>Deciduous</h4>" regardless of what the PDF calls them
- Each tooth checkbox MUST be wrapped in its own "tooth" group_start/group_end
- Do NOT include tooth images - just use the number/letter as the checkbox value

---

## HOW TO USE COLUMN GROUPS (VERY IMPORTANT - READ CAREFULLY)

Column groups (two_columns and four_columns) require a SPECIFIC structure where EACH COLUMN has its own group_start/group_end wrapper. This is the most common mistake - do NOT put all items in a single wrapper.

### STEP 1: Count the items

Count the total number of Yes/No radio questions OR checkboxes in the section:
- **Under 8 items** → No column group needed, just list the fields normally
- **8-15 items** → Use "two_columns" (you will create 2 column groups)
- **16+ items** → Use "four_columns" (you will create 4 column groups)

### STEP 2: Calculate items per column

- For **two_columns**: Divide total items by 2
- For **four_columns**: Divide total items by 4
- Round up if the number doesn't divide evenly (extra items go in early columns)

### STEP 3: Create SEPARATE group wrappers for EACH column

This is critical: You must create MULTIPLE group_start/group_end pairs - one for EACH column.

**For two_columns:** You need exactly 2 group_start/group_end pairs
**For four_columns:** You need exactly 4 group_start/group_end pairs

---

### COMPLETE EXAMPLE: four_columns with 16 items

**Calculation:** 16 items / 4 columns = 4 items per column
**Result:** You will create 4 separate four_columns groups, each containing 4 items

// COLUMN 1 (items 1-4)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "abnormal_bleeding", "label": "Abnormal Bleeding", "email_label": "Abnormal Bleeding", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "blood_disease", "label": "Blood Disease", "email_label": "Blood Disease", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "tuberculosis", "label": "Tuberculosis", "email_label": "Tuberculosis", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "heart_disease", "label": "Heart Disease", "email_label": "Heart Disease", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}},
// COLUMN 2 (items 5-8)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "diabetes", "label": "Diabetes", "email_label": "Diabetes", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "asthma", "label": "Asthma", "email_label": "Asthma", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergies", "label": "Allergies", "email_label": "Allergies", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "high_blood_pressure", "label": "High Blood Pressure", "email_label": "High Blood Pressure", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}},
// COLUMN 3 (items 9-12)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "hepatitis", "label": "Hepatitis", "email_label": "Hepatitis", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "hiv_aids", "label": "HIV/AIDS", "email_label": "HIV/AIDS", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "kidney_disease", "label": "Kidney Disease", "email_label": "Kidney Disease", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "liver_disease", "label": "Liver Disease", "email_label": "Liver Disease", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}},
// COLUMN 4 (items 13-16)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "cancer", "label": "Cancer", "email_label": "Cancer", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "stroke", "label": "Stroke", "email_label": "Stroke", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "seizures", "label": "Seizures", "email_label": "Seizures", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "arthritis", "label": "Arthritis", "email_label": "Arthritis", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}}

**Notice:** There are 4 separate {{"name": "four_columns", "type": "group_start"}} and 4 matching {{"type": "group_end"}} pairs.

---

### COMPLETE EXAMPLE: two_columns with 10 items

**Calculation:** 10 items / 2 columns = 5 items per column
**Result:** You will create 2 separate two_columns groups, each containing 5 items

// COLUMN 1 (items 1-5)
{{"name": "two_columns", "type": "group_start"}},
{{"name": "allergy_aspirin", "label": "Aspirin", "email_label": "Allergy - Aspirin", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_penicillin", "label": "Penicillin", "email_label": "Allergy - Penicillin", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_sulfa", "label": "Sulfa", "email_label": "Allergy - Sulfa", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_codeine", "label": "Codeine", "email_label": "Allergy - Codeine", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_latex", "label": "Latex", "email_label": "Allergy - Latex", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}},
// COLUMN 2 (items 6-10)
{{"name": "two_columns", "type": "group_start"}},
{{"name": "allergy_iodine", "label": "Iodine", "email_label": "Allergy - Iodine", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_local_anesthetic", "label": "Local Anesthetic", "email_label": "Allergy - Local Anesthetic", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_erythromycin", "label": "Erythromycin", "email_label": "Allergy - Erythromycin", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_tetracycline", "label": "Tetracycline", "email_label": "Allergy - Tetracycline", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"name": "allergy_other", "label": "Other", "email_label": "Allergy - Other", "type": "radio", "option": {{"yes": "Yes", "no": "No"}}}},
{{"type": "group_end"}}

**Notice:** There are 2 separate {{"name": "two_columns", "type": "group_start"}} and 2 matching {{"type": "group_end"}} pairs.

---

### COMPLETE EXAMPLE: four_columns with 20 items (uneven division)

**Calculation:** 20 items / 4 columns = 5 items per column
**Result:** You will create 4 separate four_columns groups, each containing 5 items

// COLUMN 1 (items 1-5)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "condition_1", ...}},
{{"name": "condition_2", ...}},
{{"name": "condition_3", ...}},
{{"name": "condition_4", ...}},
{{"name": "condition_5", ...}},
{{"type": "group_end"}},
// COLUMN 2 (items 6-10)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "condition_6", ...}},
{{"name": "condition_7", ...}},
{{"name": "condition_8", ...}},
{{"name": "condition_9", ...}},
{{"name": "condition_10", ...}},
{{"type": "group_end"}},
// COLUMN 3 (items 11-15)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "condition_11", ...}},
{{"name": "condition_12", ...}},
{{"name": "condition_13", ...}},
{{"name": "condition_14", ...}},
{{"name": "condition_15", ...}},
{{"type": "group_end"}},
// COLUMN 4 (items 16-20)
{{"name": "four_columns", "type": "group_start"}},
{{"name": "condition_16", ...}},
{{"name": "condition_17", ...}},
{{"name": "condition_18", ...}},
{{"name": "condition_19", ...}},
{{"name": "condition_20", ...}},
{{"type": "group_end"}}

---

### WRONG WAY - NEVER DO THIS

**WRONG - Single wrapper for all items (THIS IS INCORRECT):**

{{"name": "four_columns", "type": "group_start"}},
{{"name": "condition_1", ...}},
{{"name": "condition_2", ...}},
{{"name": "condition_3", ...}},
... all 16+ items here in one group ...
{{"name": "condition_16", ...}},
{{"type": "group_end"}}

**Why this is wrong:** This puts ALL items in a single group_start/group_end pair. The form generator will NOT split these into columns correctly. You MUST have separate group wrappers for each column.

**WRONG - Only one group for two_columns (THIS IS INCORRECT):**

{{"name": "two_columns", "type": "group_start"}},
{{"name": "allergy_1", ...}},
{{"name": "allergy_2", ...}},
... all 10 items here ...
{{"name": "allergy_10", ...}},
{{"type": "group_end"}}

**Why this is wrong:** For two_columns you need 2 separate groups, not 1.

---

### ADDITIONAL NOTES

**It's OK to include 1-2 text fields** (like "Type and Date:" follow-ups) within a column group. Base your column choice on the radio button/checkbox count, not strict uniformity.

**Single-item checkboxes:** For checkboxes with only one option (like agreement checkboxes), the label can be empty since the value contains the text. Example: `{{"name": "acknowledgement", "label": "", "email_label": "", "type": "checkbox", "option": {{"checked": "I agree to the terms..."}}}}`

### SUMMARY CHECKLIST

Before finalizing column groups, verify:
- [ ] Did I count the total number of radio/checkbox items?
- [ ] Did I divide by 2 (for two_columns) or 4 (for four_columns)?
- [ ] Did I create SEPARATE group_start/group_end pairs for EACH column?
- [ ] For four_columns: Do I have exactly 4 group_start and 4 group_end?
- [ ] For two_columns: Do I have exactly 2 group_start and 2 group_end?

---

## CRITICAL RULES

1. Field naming: lowercase, underscores, no special characters
2. Every group_start MUST have a matching group_end
3. **ONLY use the exact group names listed above (two_columns, four_columns, name_details, address_details, inline_container, permanent, deciduous, top_row, bottom_row, tooth_container, tooth, form_container, form_content_container). Do NOT invent custom group names.**
4. "If yes, explain" patterns - A few follow-up text fields within a column group are OK, but lengthy explanations should go outside
5. Column groups should be MOSTLY similar field types - 1-2 text fields mixed in with radios is fine
6. Return ONLY valid JSON - no comments, no trailing commas
7. **COUNT Yes/No radio questions OR checkboxes in a section: use "two_columns" for 8-15 items, use "four_columns" for 16+ items, no column group for under 8 items**
8. **COLUMN WRAPPING: Each column must have its own group_start/group_end pair. For four_columns, divide total items by 4 and create 4 separate wrapped groups. For two_columns, divide by 2 and create 2 separate wrapped groups. NEVER wrap all items in a single group_start/group_end.**

Now analyze the PDF form image(s) and generate the complete JSON structure."""


class FormAnalyzer:
    def __init__(self, api_key: str, model_name: str, inputs: Dict[str, str]):
        """Initialize with API key, model name, and user inputs."""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model_name
        self.inputs = inputs
        self.last_error: Optional[str] = None

    def _pdf_to_images(self, pdf_path: str) -> list:
        """Convert PDF pages to base64-encoded images."""
        logger.info("Converting PDF to images...")
        import shutil
        poppler_path = shutil.which('pdftoppm')
        poppler_path = os.path.dirname(poppler_path) if poppler_path else '/opt/homebrew/bin'
        images = convert_from_path(pdf_path, dpi=150, poppler_path=poppler_path)
        logger.info("Found %d page(s)", len(images))

        encoded_images = []
        for i, img in enumerate(images):
            # Convert to JPEG bytes
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            # Base64 encode
            encoded = base64.standard_b64encode(buffer.read()).decode('utf-8')
            encoded_images.append(encoded)
            logger.info("Encoded page %d", i + 1)

        return encoded_images

    def _image_file_to_base64(self, image_path: str) -> tuple:
        """Read an image file and return (base64_data, media_type) as JPEG."""
        logger.info("Encoding image: %s", os.path.basename(image_path))
        with open(image_path, 'rb') as f:
            raw = f.read()

        img = Image.open(io.BytesIO(raw))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        encoded = base64.standard_b64encode(buf.getvalue()).decode('utf-8')
        return encoded, 'image/jpeg'

    def _build_prompt(self) -> str:
        """Build the analysis prompt with user inputs."""
        form_name = self.inputs.get('form_name', 'Untitled Form')
        category = self.inputs.get('category', 'General')

        # Create snake_case key from form name
        form_name_key = form_name.lower().replace(' ', '_').replace('-', '_')
        # Remove any non-alphanumeric characters except underscore
        form_name_key = ''.join(c for c in form_name_key if c.isalnum() or c == '_')

        return FORM_ANALYSIS_PROMPT.format(
            form_name=form_name,
            form_name_key=form_name_key,
            category=category
        )

    def _extract_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from Claude's response."""
        # Try to find JSON in the response
        text = response_text.strip()

        # Look for JSON block
        if '```json' in text:
            start = text.find('```json') + 7
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()
        elif '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()

        # If text doesn't start with '{', search for the first '{' in the text
        if not text.startswith('{'):
            brace_pos = text.find('{')
            if brace_pos >= 0:
                text = text[brace_pos:]

        # Try to find JSON object boundaries
        if text.startswith('{'):
            # Find matching closing brace
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            if end_pos > 0:
                text = text[:end_pos]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.last_error = f"Claude's response wasn't valid JSON ({e})"
            logger.error("JSON parse error: %s", e)
            logger.error("Response starts with: %r", response_text[:200])
            return None

    def detect_form_info(self, pdf_path: str) -> Optional[Dict[str, str]]:
        """Quick detection of form name and category from PDF.

        Returns:
            dict with 'form_name' and 'category' keys, or None on failure
        """
        # Convert just first page to image for quick detection
        logger.info("Detecting form info...")
        images = self._pdf_to_images(pdf_path)
        if not images:
            return None

        # Use only first page for detection
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": images[0]
                }
            },
            {
                "type": "text",
                "text": FORM_DETECTION_PROMPT
            }
        ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=DETECTION_MAX_TOKENS,
                thinking=_thinking(DETECTION_THINKING),
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            response_text = next((b.text for b in response.content if b.type == "text"), "").strip()

            # Parse JSON response
            if response_text.startswith('{'):
                result = json.loads(response_text)
                logger.info("Detected: %s", result.get('form_name', 'Unknown'))
                return result

            # Try to extract JSON from response
            if '{' in response_text:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                result = json.loads(response_text[start:end])
                logger.info("Detected: %s", result.get('form_name', 'Unknown'))
                return result

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.warning("Detection failed: %s", e)

        return None

    def detect_form_info_from_image(self, image_path: str) -> Optional[Dict[str, str]]:
        """Quick detection of form name and category from an image file."""
        logger.info("Detecting form info from image...")
        img_data, media_type = self._image_file_to_base64(image_path)

        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": img_data}
            },
            {"type": "text", "text": FORM_DETECTION_PROMPT}
        ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=DETECTION_MAX_TOKENS,
                thinking=_thinking(DETECTION_THINKING),
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": content}]
            )
            response_text = next((b.text for b in response.content if b.type == "text"), "").strip()

            if response_text.startswith('{'):
                result = json.loads(response_text)
                logger.info("Detected: %s", result.get('form_name', 'Unknown'))
                return result

            if '{' in response_text:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                result = json.loads(response_text[start:end])
                logger.info("Detected: %s", result.get('form_name', 'Unknown'))
                return result

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.warning("Detection failed: %s", e)

        return None

    def _run_analysis(self, content: list) -> Optional[Dict[str, Any]]:
        """Send form content to Claude and parse the JSON structure it returns."""
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=ANALYSIS_MAX_TOKENS,
                thinking=_thinking(ANALYSIS_THINKING),
                messages=[{"role": "user", "content": content}]
            ) as stream:
                response = stream.get_final_message()

            response_text = next((b.text for b in response.content if b.type == "text"), "")
            logger.info("Received response (%d chars)", len(response_text))

            truncated = response.stop_reason == 'max_tokens'
            if truncated:
                logger.warning("Response was truncated (hit max_tokens limit)")

            result = self._extract_json(response_text)
            if result is None and truncated:
                self.last_error = (
                    f"Claude's response was cut off before it finished (hit the "
                    f"{ANALYSIS_MAX_TOKENS:,}-token output limit) — try running this form "
                    "in smaller chunks, a few pages at a time"
                )
            return result

        except anthropic.APIError as e:
            self.last_error = f"Claude API error: {e}"
            logger.error("API Error: %s", e)
            return None

    def analyze_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a form image using Claude's vision capabilities."""
        img_data, media_type = self._image_file_to_base64(image_path)

        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": img_data}
            },
            {"type": "text", "text": self._build_prompt()}
        ]

        logger.info("Sending image to Claude (%s)...", self.model)

        return self._run_analysis(content)

    def analyze_pdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a PDF form using Claude's vision capabilities."""
        # Convert PDF to images
        images = self._pdf_to_images(pdf_path)

        # Build the message content with images
        content = []

        # Add all page images
        for i, img_data in enumerate(images):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_data
                }
            })

        # Add the prompt
        content.append({
            "type": "text",
            "text": self._build_prompt()
        })

        logger.info("Sending to Claude (%s)...", self.model)

        return self._run_analysis(content)
