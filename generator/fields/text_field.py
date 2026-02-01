# fields/text_field.py - SIMPLIFIED WITH PROPER GROUP HANDLING

from ..utils import draw_wrapped_text, create_acrobat_compatible_field, _check_page_break

class TextField:
    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.colors = generator.colors
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width
        self.field_height = generator.field_height

    def draw(self, field_name, label):
        c = self.canvas
        current_font = c._fontname
        current_size = c._fontsize
        current_color = c._fillColorObj

        # Get field position (handles groups automatically)
        field_x, field_width, field_y = self._get_field_position()
        starting_y = field_y

        # Check for page break
        needed_height = self.field_height + 25
        if label:
            needed_height += 20

        if self.generator.current_y - needed_height < self.generator.margin_bottom:
            if self.generator.current_group is not None:
                self.generator._handle_group_page_break(c)
            else:
                _check_page_break(self.generator, c, needed_height)
                self.generator.page_manager.initialize_page(c)
            field_x, field_width, field_y = self._get_field_position()
            starting_y = field_y

        # Draw label if present
        if label and label.strip():
            field_label_style = self.generator.label_styles['field_label']
            max_label_width = field_width * 0.9

            final_label_y = draw_wrapped_text(
                c, label, field_x, field_y + 3, max_label_width,
                field_label_style.font_name, field_label_style.font_size,
                field_label_style.color
            )
            field_y = final_label_y + 12

        # Draw text field
        field_y_position = field_y - 5
        create_acrobat_compatible_field(c, 'textfield',
            name=field_name,
            tooltip=label or field_name,
            x=field_x,
            y=field_y_position - self.field_height,
            width=field_width,
            height=self.field_height,
            fontSize=10,
            fieldFlags=0
        )

        final_field_y = field_y_position - self.field_height

        # Handle group positioning or update current_y
        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, c)
            group_field.add_field_to_group(field_name, final_field_y, starting_y, field_x, field_width)
        else:
            self.generator.current_y = final_field_y - 20

        # Restore canvas state
        c.setFont(current_font, current_size)
        c.setFillColor(current_color)

    def _get_field_position(self):
        """Get field position, handling groups if active"""
        if self.generator.current_group is not None:
            from .group_field import GroupField
            group_field = GroupField(self.generator, self.canvas)
            return group_field.get_field_position_in_group()
        else:
            return self.margin_x, self.field_width, self.generator.current_y
