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

# Clean, readable spacing that prevents overlapping
LABEL_STYLES = {
    'h1': LabelStyle(
        font_name='Helvetica-Bold',  # Standard font
        font_size=16,
        color=colors.black,
        spacing_before=0,
        spacing_after=0,
        alignment='center'
    ),
    'h3': LabelStyle(
        font_name='Helvetica-Bold',  # Standard font
        font_size=12,
        color=colors.black,
        spacing_before=10,
        spacing_after=8,
        alignment='left'
    ),
    'h4': LabelStyle(
        font_name='Helvetica-Bold',  # Standard font
        font_size=10,
        color=colors.black,
        spacing_before=6,
        spacing_after=6,
        alignment='left'
    ),
    'span': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=8,
        color=colors.black,
        spacing_before=6,
        spacing_after=6,
        alignment='left'
    ),
    'h5': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=9,
        color=colors.Color(0.4, 0.4, 0.4),
        spacing_before=6,
        spacing_after=4,
        alignment='left'
    ),
    'p': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=10,
        color=colors.black,
        spacing_before=10,
        spacing_after=10,
        alignment='left'
    ),
    'regular': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=10,
        color=colors.black,
        spacing_before=2,
        spacing_after=4,
        alignment='left'
    ),
    'field_label': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=9,
        color=colors.Color(0.3, 0.3, 0.3),
        spacing_before=4,
        spacing_after=3,
        alignment='left'
    ),
    'ul': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=10,
        spacing_before=8,
        spacing_after=4,
        alignment='left',
        color=colors.black
    ),
    'checkbox': LabelStyle(
        font_name='Helvetica',  # Standard font
        font_size=9,
        color=colors.black,
        spacing_before=2,
        spacing_after=2,
        alignment='left'
    ),
}
