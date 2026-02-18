# label_styles.py - CLEAN READABLE SPACING
from reportlab.lib import colors

class LabelStyle:
    """Simple class to hold label styling information"""
    def __init__(self, font_name, font_size, color, spacing_before=0, spacing_after=0, alignment='left'):
        self.font_name = font_name
        self.font_size = font_size
        self.color = color
        self.spacing_before = spacing_before
        self.spacing_after = spacing_after
        self.alignment = alignment

# Font family mapping: family name -> (regular, bold)
FONT_FAMILIES = {
    'Helvetica':   ('Helvetica', 'Helvetica-Bold'),
    'Times':       ('Times-Roman', 'Times-Bold'),
    'Courier':     ('Courier', 'Courier-Bold'),
}

DEFAULT_FONT_FAMILY = 'Helvetica'

def build_label_styles(font_family=None):
    """Build label styles for a given font family."""
    family = font_family or DEFAULT_FONT_FAMILY
    regular, bold = FONT_FAMILIES.get(family, FONT_FAMILIES[DEFAULT_FONT_FAMILY])

    return {
        'h1': LabelStyle(
            font_name=bold,
            font_size=13.5,
            color=colors.black,
            spacing_before=0,
            spacing_after=0,
            alignment='center'
        ),
        'h3': LabelStyle(
            font_name=bold,
            font_size=10,
            color=colors.black,
            spacing_before=4,
            spacing_after=1,
            alignment='left'
        ),
        'h4': LabelStyle(
            font_name=bold,
            font_size=8.5,
            color=colors.black,
            spacing_before=2,
            spacing_after=1,
            alignment='left'
        ),
        'span': LabelStyle(
            font_name=regular,
            font_size=7,
            color=colors.black,
            spacing_before=6,
            spacing_after=6,
            alignment='left'
        ),
        'h5': LabelStyle(
            font_name=regular,
            font_size=7.5,
            color=colors.Color(0.4, 0.4, 0.4),
            spacing_before=2,
            spacing_after=1,
            alignment='left'
        ),
        'p': LabelStyle(
            font_name=regular,
            font_size=7.5,
            color=colors.black,
            spacing_before=2,
            spacing_after=2,
            alignment='left'
        ),
        'regular': LabelStyle(
            font_name=regular,
            font_size=8.5,
            color=colors.black,
            spacing_before=2,
            spacing_after=4,
            alignment='left'
        ),
        'field_label': LabelStyle(
            font_name=regular,
            font_size=7.5,
            color=colors.Color(0.3, 0.3, 0.3),
            spacing_before=4,
            spacing_after=3,
            alignment='left'
        ),
        'ul': LabelStyle(
            font_name=regular,
            font_size=8.5,
            spacing_before=8,
            spacing_after=4,
            alignment='left',
            color=colors.black
        ),
        'checkbox': LabelStyle(
            font_name=regular,
            font_size=7.5,
            color=colors.black,
            spacing_before=2,
            spacing_after=2,
            alignment='left'
        ),
    }

# Default styles (Helvetica) — used when no font_family override is provided
LABEL_STYLES = build_label_styles()
