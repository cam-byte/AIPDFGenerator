# fields/inline_text_field.py - Inline text and fields for fill-in-the-blank paragraphs

import re
from reportlab.pdfbase.pdfmetrics import stringWidth
from ..utils import create_acrobat_compatible_field, _strip_html_tags


class InlineTextField:
    """
    Handles inline text rendering for fill-in-the-blank style paragraphs.
    Text and input fields flow together horizontally on the same line.
    """

    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.colors = generator.colors
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width

        # Inline-specific settings
        self.line_height = 18
        self.field_height = 14
        self.spacing = 4
        self.min_field_width = 80  # Minimum width for inline text fields
        self.default_field_width = 120  # Default width for inline text fields

    def draw_text(self, label):
        """Draw inline text segment (static text, not an input field)"""
        c = self.canvas

        # Get inline state
        if not hasattr(self.generator, 'inline_state') or self.generator.inline_state is None:
            # Not in inline mode, fall back to regular label
            return self._draw_as_regular_label(label)

        state = self.generator.inline_state

        # Strip HTML tags and get clean text
        text = _strip_html_tags(label).strip()
        if not text:
            return

        # Set font for text
        font_name = self.generator.font_family
        font_size = 10
        c.setFont(font_name, font_size)
        c.setFillColor(self.colors['primary'])

        # Split text into words for wrapping
        words = text.split()

        for i, word in enumerate(words):
            # Add space before word (except first word after line break or field)
            if i > 0 or (state['current_x'] > state['start_x'] and not state.get('just_drew_field', False)):
                word_with_space = ' ' + word
            else:
                word_with_space = word

            word_width = stringWidth(word_with_space, font_name, font_size)

            # Check if word fits on current line
            if state['current_x'] + word_width > state['max_x']:
                # Wrap to next line
                self._advance_line(state)
                word_with_space = word  # No leading space at start of line
                word_width = stringWidth(word_with_space, font_name, font_size)

            # Draw the word
            text_y = state['current_y'] - font_size + 2  # Baseline adjustment
            c.drawString(state['current_x'], text_y, word_with_space)
            state['current_x'] += word_width

        state['just_drew_field'] = False

    def draw_field(self, field_name, label=''):
        """Draw inline input field"""
        c = self.canvas

        # Get inline state
        if not hasattr(self.generator, 'inline_state') or self.generator.inline_state is None:
            # Not in inline mode, fall back to regular text field
            from .text_field import TextField
            text_field = TextField(self.generator, c)
            text_field.draw(field_name, label)
            return

        state = self.generator.inline_state

        # Calculate field width based on available space
        remaining_width = state['max_x'] - state['current_x']
        field_width = min(self.default_field_width, remaining_width - self.spacing)

        # If not enough space, wrap to next line
        if field_width < self.min_field_width:
            self._advance_line(state)
            field_width = self.default_field_width

        # Add spacing before field
        if state['current_x'] > state['start_x']:
            state['current_x'] += self.spacing

        # Calculate field position (vertically centered on line)
        field_y = state['current_y'] - self.field_height + 2

        # Draw the text field
        create_acrobat_compatible_field(c, 'textfield',
            name=field_name,
            tooltip=label or field_name,
            x=state['current_x'],
            y=field_y,
            width=field_width,
            height=self.field_height,
            fontSize=9,
            fieldFlags=0
        )

        # Update position
        state['current_x'] += field_width + self.spacing
        state['just_drew_field'] = True

    def _advance_line(self, state):
        """Move to the next line in the inline container"""
        state['current_x'] = state['start_x']
        state['current_y'] -= self.line_height
        state['line_count'] += 1

        # Check for page break
        if state['current_y'] < self.generator.margin_bottom:
            self.generator.current_page += 1
            self.generator.page_manager.initialize_page(self.canvas)
            state['current_y'] = self.generator.current_y
            state['line_count'] = 1

    def _draw_as_regular_label(self, label):
        """Fallback: draw as regular label when not in inline mode"""
        style = self.generator.label_manager.get_label_style('label', label)
        self.generator.label_manager.draw_label(self.canvas, label, style, False)


class InlineContainerManager:
    """
    Manages inline container state for fill-in-the-blank paragraphs.
    """

    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width

    def start_container(self):
        """Initialize inline container state"""
        # Add some spacing before the inline container
        self.generator.current_y -= 8

        self.generator.inline_state = {
            'start_x': self.margin_x,
            'max_x': self.margin_x + self.field_width,
            'current_x': self.margin_x,
            'current_y': self.generator.current_y,
            'line_height': 18,
            'line_count': 1,
            'just_drew_field': False
        }

    def end_container(self):
        """End inline container and update generator position"""
        if hasattr(self.generator, 'inline_state') and self.generator.inline_state:
            state = self.generator.inline_state
            # Move current_y below the container content
            self.generator.current_y = state['current_y'] - 20

        self.generator.inline_state = None
