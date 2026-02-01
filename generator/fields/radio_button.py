# fields/radio_button.py - FIXED: Color issue resolved
from ..utils import _get_options, _check_page_break, draw_wrapped_text, calculate_wrapped_text_height
from reportlab.lib import colors

class RadioButton:
    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.colors = generator.colors
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width

    def draw(self, field_name, label, options):
        c = self.canvas
        current_font = c._fontname
        current_size = c._fontsize
        current_color = c._fillColorObj

        # Calculate field positioning
        field_x, field_width, field_y = self._get_field_position()
        starting_y = field_y

        # Draw label with text wrapping using actual field width
        if label:
            field_label_style = self.generator.label_styles['field_label']
            max_label_width = field_width * 0.88

            final_label_y = draw_wrapped_text(
                c, label, field_x, field_y, max_label_width,
                field_label_style.font_name, field_label_style.font_size,
                field_label_style.color
            )

            field_y = final_label_y + 7

        # Get options and ensure proper capitalization
        options_list = _get_options(options)
        if not options_list:
            options_list = [('Yes', 'Yes'), ('No', 'No')]

        # Capitalize all option values and labels
        options_list = [(value.capitalize() if isinstance(value, str) else value,
                        label.capitalize() if isinstance(label, str) else label)
                       for value, label in options_list]

        # Ensure we have at least 2 options for ReportLab radio groups
        if len(options_list) < 2:
            options_list.append(('Not_Selected', 'Not Selected'))

        # Draw radio buttons
        final_y = self._draw_radio_buttons_clean(c, field_name, options_list, field_x, field_y, field_width)

        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, c)
            group_field.add_field_to_group(field_name, final_y, starting_y, field_x, field_width)
        else:
            self.generator.current_y = final_y - 20

        c.setFont(current_font, current_size)
        c.setFillColor(current_color)

    def _draw_radio_buttons_clean(self, c, field_name, options_list, field_x, field_y, field_width):
        """Draw radio buttons with clean positioning - ALWAYS HORIZONTAL"""
        c.setFont("Helvetica", 9)
        c.setFillColor(self.colors['primary'])

        return self._draw_horizontal_radio_buttons(c, field_name, options_list, field_x, field_y, field_width)

    def _draw_horizontal_radio_buttons(self, c, field_name, options_list, field_x, field_y, field_width):
        """FIXED: Use proper Color objects instead of strings"""
        x_offset = 0
        max_width = field_width * 0.95
        current_row_y = field_y

        for i, (value, option_label) in enumerate(options_list):
            option_text_width = c.stringWidth(option_label, "Helvetica", 9)
            option_width = 18 + option_text_width + 8

            if x_offset > 0 and x_offset + option_width > max_width:
                current_row_y -= 25
                x_offset = 0

            radio_x = field_x + x_offset
            radio_y = current_row_y - 15
            text_x = radio_x + 18
            text_y = current_row_y - 12

            # FIXED: Use shape="square" and buttonStyle="check" to avoid Adobe Acrobat rendering issues
            c.acroForm.radio(
                name=field_name,
                tooltip=f"{field_name}: {option_label}",
                value=value,
                x=radio_x,
                y=radio_y,
                size=12,
                selected=0,
                buttonStyle="check",   # Square with checkmark when selected
                shape="square",        # Square outline
                borderStyle="solid",   # Explicit border style for predictable rendering
                borderColor=colors.black,
                textColor=colors.black,
                borderWidth=1,
                forceBorder=True,
                fieldFlags=49152,
                annotationFlags=4
                # No fillColor - can cause rendering artifacts
            )

            # Draw option label
            c.setFillColor(colors.black)  # Use colors.black not string
            c.drawString(text_x, text_y, option_label)
            x_offset += option_width

        return current_row_y - 20

    def _can_fit_horizontally(self, c, options_list, field_width):
        """Check horizontal spacing - kept for potential future use"""
        c.setFont("Helvetica", 9)
        total_width = 0
        for value, option_label in options_list:
            option_width = 18 + c.stringWidth(option_label, "Helvetica", 9) + 25
            total_width += option_width

        return total_width <= (field_width * 0.9)

    def _get_field_position(self):
        """Calculate position for field within group or regular flow"""
        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, self.canvas)
            return group_field.get_field_position_in_group()
        else:
            return self.margin_x, self.field_width, self.generator.current_y

    def _handle_group_positioning(self, field_x, field_width, final_y, start_y):
        """Handle positioning when field is in a group"""
        self.generator.group_fields.append({
            'name': 'radio_button',
            'x': field_x,
            'y': final_y,
            'start_y': start_y,
            'width': field_width
        })

        if len(self.generator.group_fields) % self.generator.group_columns == 0:
            row_start = len(self.generator.group_fields) - self.generator.group_columns
            row_fields = self.generator.group_fields[row_start:]
            min_y = min(f.get('y', self.generator.current_y) for f in row_fields)
            self.generator.current_y = min_y - 8
