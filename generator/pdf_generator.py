import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
import json

from .constants import (
    MARGINS,
    FIELD_DIMENSIONS,
    COLORS,
    GROUP_CONFIGS,
    FULL_WIDTH_FIELDS,
    AUTO_FLOW_FIELD_TYPES,
    FLOW_BREAK_FIELD_TYPES,
    AUTO_FLOW_CONFIG
)
from .label_styles import LABEL_STYLES, LabelStyle, FONT_FAMILIES, DEFAULT_FONT_FAMILY, build_label_styles
from .page_manager import PageManager
from .label_manager import LabelManager
from .fields.text_field import TextField
from .fields.text_area import TextArea
from .fields.check_box import CheckBox
from .fields.radio_button import RadioButton
from .fields.group_field import GroupField
from .fields.select_field import SelectField
from .utils import _calculate_field_height

class ModernPDFFormGenerator:
    def __init__(self, json_data, business_info=None):
        self.data = json_data
        self.page_width, self.page_height = letter

        # Clean, reasonable settings
        self.margin_x = MARGINS['x']
        self.margin_bottom = MARGINS['bottom']
        self.current_y = self.page_height - MARGINS['x']
        self.field_width = FIELD_DIMENSIONS['width']
        self.field_height = FIELD_DIMENSIONS['height']
        self.current_page = 1

        # Use provided business_info or fall back to empty defaults
        biz = business_info or {}
        self.logo_path = biz.get('logo_path')
        self.address = biz.get('address', '')
        self.phone = biz.get('phone', '')
        self.email = biz.get('email', '')
        self.business_name = biz.get('business_name', '')
        # Support multiple locations - each with street, city_state_zip, phone
        self.locations = biz.get('locations')

        # PDF options — granular style overrides
        pdf_opts = biz.get('pdf_options') or {}

        self.field_height = int(pdf_opts.get('input_height', 15))
        self.textarea_height = int(pdf_opts.get('textarea_height', 42))
        self.checkbox_size = int(pdf_opts.get('checkbox_size', 9))
        self.radio_size = int(pdf_opts.get('checkbox_size', 9))
        self.check_radio_label_size = float(pdf_opts.get('check_radio_label_size', 7.5))
        self.input_font_size = min(self.field_height * 0.55, 12)
        self.field_spacing = float(pdf_opts.get('field_spacing', 17))
        self.label_gap = float(pdf_opts.get('label_gap', 3))
        self.col_spacing = float(pdf_opts.get('col_spacing', 17))
        self.group_row_height_setting = int(pdf_opts.get('group_row_height', 22))
        self.group_row_gap_setting = int(pdf_opts.get('group_row_gap', 10))
        self.header_font_size = float(pdf_opts.get('header_font_size', 8))

        # Font family
        font_family_name = pdf_opts.get('font_family', DEFAULT_FONT_FAMILY)
        if font_family_name not in FONT_FAMILIES:
            font_family_name = DEFAULT_FONT_FAMILY
        self.font_family, self.font_family_bold = FONT_FAMILIES[font_family_name]

        self.colors = COLORS

        # Build label styles for the selected font family, then apply size overrides
        base_styles = build_label_styles(font_family_name)

        size_overrides = {
            'h1': pdf_opts.get('h1_size'),
            'h3': pdf_opts.get('h3_size'),
            'h4': pdf_opts.get('h4_size'),
            'p': pdf_opts.get('p_size'),
            'field_label': pdf_opts.get('field_label_size'),
            'checkbox': pdf_opts.get('check_radio_label_size'),
        }
        has_overrides = any(v is not None for v in size_overrides.values())

        if has_overrides or self.label_gap != 3:
            self.label_styles = {}
            for key, style in base_styles.items():
                override_size = size_overrides.get(key)
                self.label_styles[key] = LabelStyle(
                    font_name=style.font_name,
                    font_size=float(override_size) if override_size is not None else style.font_size,
                    color=style.color,
                    spacing_before=style.spacing_before,
                    spacing_after=float(self.label_gap) if key == 'field_label' else style.spacing_after,
                    alignment=style.alignment,
                )
        else:
            self.label_styles = base_styles

        # Group handling
        self.current_group = None
        self.group_fields = []
        self.group_configs = GROUP_CONFIGS
        self.column_widths = None
        self.group_spacing = None
        self.group_columns = None
        self.group_start_y = None
        self.group_stack = []

        self.page_manager = PageManager(self)
        self.label_manager = LabelManager(self)

        # Inline container state (for fill-in-the-blank paragraphs)
        self.inline_state = None

        # Auto-flow state (CSS flexbox-like 2-column layout for text fields)
        self.auto_flow_active = False
        self.auto_flow_field_count = 0

        # Get the first key and parse form data
        self.form_key = self._get_first_form_key()
        self.form_data = self._find_form_data()

    def _setup_canvas_for_acrobat(self, c):
        """CRITICAL: Set up canvas for Adobe Acrobat compatibility"""
        c.setFont(self.font_family, 12)
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0, 0, 0)

    def _get_first_form_key(self):
        """Get the first key from the JSON data (the main form identifier)"""
        if isinstance(self.data, dict) and self.data:
            first_key = list(self.data.keys())[0]
            return first_key
        return None

    def _find_form_data(self):
        """Find the actual form data structure in the JSON"""
        if not self.form_key:
            return self.data

        # Navigate through the structure: first_key -> content -> nested_form_key -> fields
        try:
            main_section = self.data[self.form_key]
            if 'content' in main_section:
                content = main_section['content']
                # Look for the nested form key (usually similar to main key but different)
                for key, value in content.items():
                    if isinstance(value, dict) and 'fields' in value:
                        return value

            # Fallback: search recursively
            def search_for_fields(obj, path=""):
                if isinstance(obj, dict):
                    if 'fields' in obj:
                        return obj, path
                    for key, value in obj.items():
                        result, result_path = search_for_fields(value, f"{path}.{key}" if path else key)
                        if result:
                            return result, result_path
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        result, result_path = search_for_fields(item, f"{path}[{i}]" if path else f"[{i}]")
                        if result:
                            return result, result_path
                return None, ""

            form_data, path = search_for_fields(self.data)
            if form_data:
                print(f"Found form data at: {path}")
                return form_data
            else:
                print("No 'fields' key found, using entire JSON as form data")
                return self.data

        except KeyError as e:
            print(f"Key error when parsing form data: {e}")
            return self.data

    def _get_form_title(self):
        """Extract form title from various possible locations"""
        title_fields = ['form_name', 'title', 'name', 'form_title']

        for field in title_fields:
            if field in self.form_data:
                return self.form_data[field]

        for field in title_fields:
            if field in self.data:
                return self.data[field]

        def find_title(obj):
            if isinstance(obj, dict):
                for field in title_fields:
                    if field in obj and isinstance(obj[field], str):
                        return obj[field]
                for value in obj.values():
                    result = find_title(value)
                    if result:
                        return result
            return None

        title = find_title(self.data)
        return title if title else "Generated Form"

    def _get_fields(self):
        """Extract fields from the form data"""
        if 'fields' in self.form_data:
            return self.form_data['fields']
        elif isinstance(self.form_data, list):
            return self.form_data
        else:
            print("Warning: No fields found in form data")
            return []

    def _draw_field(self, c, field_type, field_name, label, options):
        current_font = c._fontname
        current_size = c._fontsize
        current_color = c._fillColorObj

        if field_type == 'group_start':
            group_field = GroupField(self, c)
            group_field.start_group(field_name)
            return
        elif field_type == 'group_end':
            group_field = GroupField(self, c)
            group_field.end_group()
            return

        # Handle inline_text fields (for fill-in-the-blank paragraphs)
        if field_type == 'inline_text':
            from .fields.inline_text_field import InlineTextField
            inline_field = InlineTextField(self, c)
            inline_field.draw_text(label)
            return

        # Handle label-only fields
        if field_type == 'label':
            style = self.label_manager.get_label_style(field_type, label)
            self.label_manager.draw_label(c, label, style, draw_line=False)
        else:
            # Handle form fields
            try:
                if field_type in ['text', 'email', 'date']:
                    # Check if we're inside an inline container
                    if hasattr(self, 'inline_state') and self.inline_state is not None:
                        from .fields.inline_text_field import InlineTextField
                        inline_field = InlineTextField(self, c)
                        inline_field.draw_field(field_name, label)
                    else:
                        text_field = TextField(self, c)
                        text_field.draw(field_name, label)
                elif field_type == 'select':
                    select_field = SelectField(self, c)
                    select_field.draw(field_name, label, options)
                elif field_type == 'textarea':
                    text_area = TextArea(self, c)
                    text_area.draw(field_name, label)
                elif field_type == 'radio':
                    radio_button = RadioButton(self, c)
                    radio_button.draw(field_name, label, options)
                elif field_type == 'checkbox':
                    check_box = CheckBox(self, c)
                    check_box.draw(field_name, label, options)
                else:
                    # Fallback for unknown field types
                    text_field = TextField(self, c)
                    text_field.draw(field_name, label)
            except Exception as e:
                print(f"Error drawing field '{field_name}' of type '{field_type}': {e}")
                # Fallback to text field
                text_field = TextField(self, c)
                text_field.draw(field_name, f"{label} (Error: treated as text)")

        c.setFont(current_font, current_size)
        c.setFillColor(current_color)

    def _handle_group_page_break(self, c):
        """Handle page breaks - properly end/restart groups across pages"""
        if self.current_group is not None:
            temp_group = self.current_group

            group_field = GroupField(self, c)
            group_field.end_group()

            c.showPage()
            self.current_page += 1
            self.page_manager.initialize_page(c)

            group_field.start_group(temp_group)
        else:
            c.showPage()
            self.current_page += 1
            self.page_manager.initialize_page(c)

    def _start_auto_flow(self, c):
        """Start auto-flow 2-column layout (CSS flexbox-like behavior)"""
        if self.auto_flow_active:
            return

        self.auto_flow_active = True
        self.auto_flow_field_count = 0

        group_field = GroupField(self, c)
        group_field.start_group('__auto_flow__')

    def _end_auto_flow(self, c):
        """End auto-flow layout"""
        if not self.auto_flow_active:
            return

        group_field = GroupField(self, c)
        group_field.end_group()

        self.auto_flow_active = False
        self.auto_flow_field_count = 0

    def _process_fields(self, c, total_pages=None):
        fields = self._get_fields()
        num_fields = len(fields)

        i = 0
        while i < num_fields:
            field = fields[i]

            label = field.get('label', '')
            field_name = field.get('name', '')
            field_type = field.get('type', '').lower().strip()

            prev_field_type = fields[i-1].get('type', '').lower().strip() if i > 0 else None
            next_field_type = fields[i+1].get('type', '').lower().strip() if i+1 < num_fields else None

            # Skip submission fields
            if field_type in ['pdf_download', 'submit']:
                i += 1
                continue

            # --- AUTO-FLOW LOGIC: CSS flexbox-like 2-column layout for text fields ---
            in_explicit_group = (self.current_group is not None and
                                self.current_group != '__auto_flow__')

            if not in_explicit_group:
                is_flowable = field_type in AUTO_FLOW_FIELD_TYPES
                is_flow_breaker = field_type in FLOW_BREAK_FIELD_TYPES
                next_is_flowable = next_field_type in AUTO_FLOW_FIELD_TYPES if next_field_type else False
                prev_was_group_end = prev_field_type == 'group_end'
                next_is_group_or_label = next_field_type in ('group_start', 'label') if next_field_type else True

                if is_flowable and next_is_flowable and not prev_was_group_end:
                    if not self.auto_flow_active:
                        self._start_auto_flow(c)
                    self.auto_flow_field_count += 1
                elif is_flowable and self.auto_flow_active:
                    self.auto_flow_field_count += 1
                    if not next_is_flowable:
                        pass  # Will be handled after drawing
                elif is_flow_breaker or (is_flowable and not next_is_flowable and not self.auto_flow_active):
                    if self.auto_flow_active:
                        self._end_auto_flow(c)

            # --- DYNAMIC LOGIC: Force new row for specific fields or radio between text fields ---
            is_women_only_label = (field_type == 'label' and
                                'women only' in label.lower() and
                                'are you' in label.lower())

            if (field_name in FULL_WIDTH_FIELDS or
                is_women_only_label or
                (field_type == 'radio' and
                (prev_field_type == 'text' or next_field_type == 'text') and
                self.current_group is None)):

                temp_group = self.current_group
                was_auto_flow = self.auto_flow_active
                if self.current_group:
                    group_field = GroupField(self, c)
                    group_field.end_group()
                    self.current_group = None
                    if was_auto_flow:
                        self.auto_flow_active = False

                self._draw_field(c, field_type, field_name, label, field.get('option', {}))
                i += 1

                if temp_group and not was_auto_flow:
                    group_field = GroupField(self, c)
                    group_field.start_group(temp_group)

                continue

            # group_start: ensure enough room for at least a few rows so
            # content doesn't immediately break to the next page.
            # group_end: zero height, no check needed.
            if field_type in ('group_start', 'group_end'):
                if field_type == 'group_start':
                    min_group_space = 70  # ~3 rows of checkboxes / fields
                    if self.current_y - min_group_space < self.margin_bottom:
                        self._handle_group_page_break(c)
                self._draw_field(c, field_type, field_name, label, field.get('option', {}))
                i += 1
                continue

            needed_height = _calculate_field_height(
                field_type, label, field.get('option', {}),
                self.field_width, self.field_height,
                self.label_styles,
                textarea_height=self.textarea_height,
                field_spacing=self.field_spacing,
                checkbox_size=self.checkbox_size,
                radio_size=self.radio_size,
            )

            is_section_title = field_type == 'label' and '<h3>' in label.lower()
            if is_section_title:
                needed_height = max(needed_height, 80)

            # Keep labels together with a following group — don't orphan a
            # heading at the bottom of a page when the group it introduces
            # will immediately jump to the next page.
            if field_type == 'label' and i + 1 < num_fields:
                next_ft = fields[i + 1].get('type', '').lower().strip()
                if next_ft == 'group_start':
                    needed_height = max(needed_height, 80)

            if self.current_y - needed_height < self.margin_bottom:
                self._handle_group_page_break(c)

            self._draw_field(c, field_type, field_name, label, field.get('option', {}))

            if self.auto_flow_active and not in_explicit_group:
                next_type = fields[i+1].get('type', '').lower().strip() if i+1 < num_fields else None
                if next_type not in AUTO_FLOW_FIELD_TYPES:
                    self._end_auto_flow(c)

            i += 1

        if self.auto_flow_active:
            self._end_auto_flow(c)

    def generate_pdf(self, output_filename):
        """Updated with minimal Adobe Acrobat compatibility fixes"""
        # First pass to count pages
        c = canvas.Canvas(
            output_filename,
            pagesize=letter,
            pageCompression=0,
            encoding='WinAnsiEncoding'
        )

        form_title = self._get_form_title()
        c.setTitle(form_title)
        c.acroForm.needAppearances = True
        c.acroForm.sigFlags = 0

        self._setup_canvas_for_acrobat(c)

        self.page_manager.initialize_page(c)
        self._process_fields(c)
        total_pages = c.getPageNumber()
        c.save()

        # Second pass with page numbers - reset state
        self.current_page = 1
        self.current_y = self.page_height - self.margin_x
        self.current_group = None
        self.group_fields = []
        self.group_stack = []
        self.inline_state = None
        self.auto_flow_active = False
        self.auto_flow_field_count = 0

        c = canvas.Canvas(
            output_filename,
            pagesize=letter,
            pageCompression=0,
            encoding='WinAnsiEncoding'
        )
        c.setTitle(form_title)
        c.acroForm.needAppearances = True
        c.acroForm.sigFlags = 0

        self._setup_canvas_for_acrobat(c)

        self.page_manager.initialize_page(c)
        self._process_fields(c, total_pages)
        c.save()


def generate_form_pdf(json_file_path, output_pdf_path, business_info=None):
    """Generate form PDF from JSON file.

    Args:
        json_file_path: Path to the JSON form definition
        output_pdf_path: Path for the output PDF
        business_info: Optional dict with keys: logo_path, business_name, address, phone, email
    """
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")

    with open(json_file_path, 'r', encoding='utf-8') as file:
        form_data = json.load(file)

    generator = ModernPDFFormGenerator(form_data, business_info=business_info)
    generator.generate_pdf(output_pdf_path)
