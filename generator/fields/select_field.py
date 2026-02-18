# fields/select_field.py - WITH TEXT WRAPPING
from ..utils import _get_options, _check_page_break, draw_wrapped_text, calculate_wrapped_text_height, create_acrobat_compatible_field

class SelectField:
    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.colors = generator.colors
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width
        self.field_height = generator.field_height

    def draw(self, field_name, label, options):
        c = self.canvas
        current_font = c._fontname
        current_size = c._fontsize
        current_color = c._fillColorObj

        self.generator.current_y -= 5  # Add this line

        # Calculate field positioning
        field_x, field_width, field_y = self._get_field_position()
        starting_y = field_y

        # Draw label with text wrapping
        if label:
            field_label_style = self.generator.label_styles['field_label']
            max_label_width = field_width * 0.9

            final_label_y = draw_wrapped_text(
                c, label, field_x, field_y + 3, max_label_width,
                field_label_style.font_name, field_label_style.font_size,
                field_label_style.color
            )

            field_y = final_label_y + self.generator.label_gap + 9

        # Set minimum field width to prevent ReportLab issues
        min_width = 100
        field_width = max(field_width, min_width)
        field_y_position = field_y - 5

        # Get options and create tooltip
        options_list = _get_options(options)
        if options_list:
            option_strings = [f"{value}: {option_label}" for value, option_label in options_list]
            tooltip_text = f"{label} - Options: {', '.join([ol for v, ol in options_list])}"
        else:
            tooltip_text = label

        # Draw as text field with options in tooltip
        create_acrobat_compatible_field(c, 'textfield',
            name=field_name,
            tooltip=tooltip_text,
            x=field_x,
            y=field_y_position - self.field_height,
            width=field_width,
            height=self.field_height,
            fontSize=self.generator.input_font_size,
            fieldFlags=0
        )

        final_field_y = field_y_position - self.field_height

        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, c)
            group_field.add_field_to_group(field_name, final_field_y, starting_y, field_x, field_width)

            # After row completion, apply proper spacing (matching text field gap)
            idx = len(self.generator.group_fields)
            if idx % self.generator.group_columns == 0:
                row_start = idx - self.generator.group_columns
                row_fields = self.generator.group_fields[row_start:]
                min_y = min(f.get('y', self.generator.current_y) for f in row_fields)
                self.generator.current_y = min_y - 15
        else:
            self.generator.current_y = final_field_y - self.generator.field_spacing

        c.setFont(current_font, current_size)
        c.setFillColor(current_color)

    def _get_field_position(self):
        """Calculate position for field within group or regular flow"""
        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, self.canvas)
            return group_field.get_field_position_in_group()
        else:
            return self.margin_x, self.field_width, self.generator.current_y

    def _handle_group_positioning(self, field_x, field_width, final_y, start_y):
        self.generator.group_fields.append({
            'name': 'select_field',
            'x': field_x,
            'y': final_y,
            'start_y': start_y,
            'width': field_width
        })

        if len(self.generator.group_fields) % self.generator.group_columns == 0:
            row_start = len(self.generator.group_fields) - self.generator.group_columns
            row_fields = self.generator.group_fields[row_start:]
            min_y = min(f.get('y', self.generator.current_y) for f in row_fields)
            self.generator.current_y = min_y - 15  # Increased from 10 for better separation between rows
