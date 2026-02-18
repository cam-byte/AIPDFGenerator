# utils.py - COMPLETE VERSION with all functions

import re
import os
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

def _strip_html_tags(text):
    """Remove HTML tags from text"""
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def _sanitize_option(text):
    """Make option text PDF-safe by replacing characters that break PDF form fields."""
    return str(text).replace('/', '-')

def _get_options(option_data):
    """Extract options from various formats. Value = label, both PDF-safe."""
    if not option_data:
        return []

    if isinstance(option_data, dict):
        return [(_sanitize_option(value), _sanitize_option(value)) for key, value in option_data.items()]
    elif isinstance(option_data, list):
        return [(_sanitize_option(item), _sanitize_option(item)) for item in option_data]
    else:
        return []

def _check_page_break(generator, canvas, needed_height):
    """Check if a new page is needed"""
    if generator.current_y - needed_height < generator.margin_bottom:
        canvas.showPage()
        generator.current_page += 1
        generator.current_y = generator.page_height - generator.margin_x
        return True
    return False

def _calculate_field_height(field_type, label, options, field_width, field_height, label_styles,
                            textarea_height=42, field_spacing=17, checkbox_size=9, radio_size=9):
    """Enhanced field height calculation"""
    if field_type in ('group_start', 'group_end'):
        return 0
    if field_type == 'checkbox':
        # For checkboxes with long text, we need to account for wrapping
        if isinstance(options, dict) and 'checked' in options:
            text = options['checked']
            if text and len(text) > 50:
                char_width = 6
                chars_per_line = max(field_width // char_width, 20)
                lines = len(text) // chars_per_line + 1
                return max(30, lines * 15)
        return checkbox_size + 14
    elif field_type == 'textarea':
        return textarea_height + 30
    elif field_type in ['radio']:
        option_count = len(_get_options(options)) if options else 2
        return 20 + (option_count * (radio_size + 7))
    elif field_type == 'label':
        if '<h1>' in str(label).lower():
            return 30
        elif '<h3>' in str(label).lower():
            return 25
        elif '<h4>' in str(label).lower():
            return 20
        elif '<p>' in str(label).lower():
            return 40
        return 15
    elif field_type in ('text', 'email', 'date', 'select'):
        return field_height + field_spacing + 25
    else:
        return field_height

def _prepare_logo_image(logo_path):
    """Prepare logo image for PDF inclusion"""
    if not logo_path or not os.path.exists(logo_path):
        return None

    try:
        return ImageReader(logo_path)
    except Exception as e:
        print(f"Error preparing logo image: {e}")
        return None

def _calculate_logo_dimensions(logo_path, max_width=150, max_height=50):
    """Calculate appropriate logo dimensions for PDF"""
    if not logo_path or not os.path.exists(logo_path):
        return 0, 0

    try:
        from PIL import Image
        with Image.open(logo_path) as img:
            width, height = img.size

            # Calculate scaling to fit within max dimensions
            width_ratio = max_width / width if width > 0 else 1
            height_ratio = max_height / height if height > 0 else 1
            scale_ratio = min(width_ratio, height_ratio, 1)  # Don't scale up

            return int(width * scale_ratio), int(height * scale_ratio)
    except ImportError:
        # PIL not available, use default dimensions
        return max_width, max_height
    except Exception as e:
        print(f"Error calculating logo dimensions: {e}")
        return max_width, max_height

def wrap_text(canvas, text, max_width, font_name="Helvetica", font_size=10):
    """
    Wrap text to fit within specified width
    Returns list of lines and total height needed
    """
    if not text:
        return [], 0

    canvas.setFont(font_name, font_size)
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        # Test if adding this word would exceed max width
        test_line = current_line + (" " if current_line else "") + word
        text_width = canvas.stringWidth(test_line, font_name, font_size)

        if text_width <= max_width:
            current_line = test_line
        else:
            # If current line has content, save it and start new line
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Single word is too long, force it on the line
                lines.append(word)
                current_line = ""

    # Add the last line if it has content
    if current_line:
        lines.append(current_line)

    # Calculate total height (font_size + small spacing between lines)
    line_height = font_size + 4
    total_height = len(lines) * line_height if lines else 0

    return lines, total_height

def draw_wrapped_text(canvas, text, x, y, max_width, font_name="Helvetica", font_size=10, color=None):
    """
    Draw wrapped text starting at x, y position
    Returns the final Y position after drawing all lines
    """
    if not text:
        return y

    # Save current state
    current_font = canvas._fontname
    current_size = canvas._fontsize
    current_color = canvas._fillColorObj

    # Set font and color
    canvas.setFont(font_name, font_size)
    if color:
        canvas.setFillColor(color)

    # Get wrapped lines
    lines, total_height = wrap_text(canvas, text, max_width, font_name, font_size)

    # Draw each line
    line_height = font_size + 2
    current_y = y

    for line in lines:
        canvas.drawString(x, current_y, line)
        current_y -= line_height

    # Restore previous state
    canvas.setFont(current_font, current_size)
    canvas.setFillColor(current_color)

    return current_y

def calculate_wrapped_text_height(canvas, text, max_width, font_name="Helvetica", font_size=10):
    """
    Calculate the height needed for wrapped text without drawing it
    """
    if not text:
        return 0

    lines, total_height = wrap_text(canvas, text, max_width, font_name, font_size)
    return total_height

def get_effective_field_width(generator):
    """Get the effective width for text wrapping based on current context"""
    if generator.current_group is not None and generator.column_widths:
        group_index = len(generator.group_fields)
        column_index = group_index % generator.group_columns
        effective_width = generator.column_widths[column_index]
        return effective_width
    else:
        return generator.field_width

def _wrap_text(text, max_width, font_size=10, font_name="Helvetica"):
    """Wrap text based on actual string width in points using ReportLab."""
    if not text:
        return []

    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        # Measure the width of the test_line
        line_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def format_phone_number(phone):
    """Format phone number for display"""
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Format as (XXX) XXX-XXXX if 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Return original if can't format

def validate_email(email):
    """Basic email validation"""
    if not email:
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def sanitize_field_name(name):
    """Sanitize field name for PDF form fields"""
    if not name:
        return "field"

    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "field_" + sanitized

    return sanitized or "field"

def convert_to_points(value, unit='pt'):
    """Convert various units to points"""
    if unit == 'pt':
        return value
    elif unit == 'in':
        return value * 72
    elif unit == 'cm':
        return value * 28.35
    elif unit == 'mm':
        return value * 2.835
    else:
        return value  # Assume points if unknown

def create_acrobat_compatible_field(canvas, field_type, **kwargs):
    """Create form fields with explicit Adobe Acrobat compatibility settings"""
    form = canvas.acroForm

    # Convert color tuples to proper Color objects
    def fix_color(color_value):
        if isinstance(color_value, tuple):
            if len(color_value) == 3:
                return colors.Color(color_value[0], color_value[1], color_value[2])
            elif len(color_value) == 4:
                return colors.Color(color_value[0], color_value[1], color_value[2], color_value[3])
        return color_value

    # Force explicit settings that Adobe Acrobat expects with proper Color objects
    if field_type == 'textfield':
        # Fix color parameters
        kwargs['borderColor'] = fix_color(kwargs.get('borderColor', colors.black))
        kwargs['fillColor'] = fix_color(kwargs.get('fillColor', colors.white))
        kwargs['textColor'] = fix_color(kwargs.get('textColor', colors.black))

        form.textfield(
            borderWidth=kwargs.get('borderWidth', 1),
            forceBorder=True,  # Ensure borders are visible
            **kwargs
        )
    elif field_type == 'checkbox':
        # Fix color parameters
        kwargs['borderColor'] = fix_color(kwargs.get('borderColor', colors.black))
        kwargs['fillColor'] = fix_color(kwargs.get('fillColor', colors.white))
        kwargs['textColor'] = fix_color(kwargs.get('textColor', colors.black))

        form.checkbox(
            borderWidth=kwargs.get('borderWidth', 1),
            **kwargs
        )
    elif field_type == 'radio':
        kwargs['borderColor'] = fix_color(kwargs.get('borderColor', colors.black))
        kwargs['fillColor'] = fix_color(kwargs.get('fillColor', colors.white))
        kwargs['textColor'] = fix_color(kwargs.get('textColor', colors.black))
        kwargs['borderWidth'] = kwargs.get('borderWidth', 1)

        form.radio(**kwargs)
