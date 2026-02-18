# fields/check_box.py
# FIXED: robust option parsing -> (key, label)
# FIXED: field names = f"{field_name}_{key}"
# FIXED: tries to set export value to the full name (fallback-safe)

from ..utils import _strip_html_tags, wrap_text, create_acrobat_compatible_field, _check_page_break

# ===== CheckBox visual tuning (points) =====
CHECKBOX_BOX_SIZE = 11          # square size
CHECKBOX_GAP = 6                # gap between square and text
CHECKBOX_LINE_GAP = 1           # tighter extra spacing between wrapped lines (was 3)
CHECKBOX_VPAD = 0               # vertical breathing room inside a row (was 2 / your -0)
CHECKBOX_BASELINE_NUDGE = -9    # tiny nudge for the first text line (your -10 was extreme)

# Compact rules for multi-option lists in two-column groups
# Keep rows as short as content allows and ignore any tall group_row_height.
MULTI_MIN_ROW = 0               # force minimum row to 0 for multi-option lists


class CheckBox:
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

        self.current_options = options

        # Only apply extra spacing when we're NOT inside a layout group
        if self.generator.current_group is None:
            spacing = self._calculate_dynamic_spacing(field_name, label, options)
            self.generator.current_y -= spacing

        field_x, field_width, field_y = self._get_field_position()
        starting_y = field_y

        # Parse options as (key, label)
        options_list = self._options_as_key_label(options)

        if len(options_list) == 1:
            self._draw_single_checkbox(c, field_name, label, options_list, field_x, field_width, field_y, starting_y)
        else:
            self._draw_multiple_checkboxes(c, field_name, label, options_list, field_x, field_width, field_y, starting_y)

        c.setFont(current_font, current_size)
        c.setFillColor(current_color)

    # ---------- option normalization ----------

    def _options_as_key_label(self, options):
        """
        Return list[(key, label)].
        Supports:
          - {"option": {"key": "Label", ...}}
          - {"options": {"key": "Label", ...}}
          - {"key": "Label", ...}
          - [("key","Label"), ...]
          - [{"value":"key","label":"Label"}, ...]
          - ["Label1","Label2", ...] -> [("label1","Label1"), ...]
          - anything else -> [(normalized(str), str)]
        """
        # Case: full field spec with nested dict under "option" or "options"
        if isinstance(options, dict):
            nested = None
            if "option" in options and isinstance(options["option"], dict):
                nested = options["option"]
            elif "options" in options and isinstance(options["options"], dict):
                nested = options["options"]

            if nested is not None:
                return [(str(k), str(v)) for k, v in nested.items()]

            # Plain mapping of key->label
            if all(isinstance(k, (str, int)) for k in options.keys()):
                keys = list(options.keys())
                if not {"name", "label", "email_label", "type"} & set(keys):
                    return [(str(k), str(v)) for k, v in options.items()]

        # List/tuple style
        if isinstance(options, (list, tuple)):
            out = []
            for item in options:
                if isinstance(item, tuple) and len(item) == 2:
                    k, v = item
                    out.append((str(k), str(v)))
                elif isinstance(item, dict):
                    if "value" in item and "label" in item:
                        out.append((str(item["value"]), str(item["label"])))
                    else:
                        for k, v in item.items():
                            out.append((str(k), str(v)))
                else:
                    s = str(item)
                    out.append((self._normalize_field_value(s), s))
            return out

        # Fallback: single string or anything else
        s = str(options)
        return [(self._normalize_field_value(s), s)]

    # ---------- helpers ----------

    def _normalize_field_value(self, value):
        """Normalize to lowercase_with_underscores and strip non-alnum."""
        if value is None:
            return ""
        import re
        normalized = str(value).lower().replace(" ", "_")
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        normalized = re.sub(r'_+', '_', normalized)
        return normalized.strip('_')

    def _calculate_dynamic_spacing(self, field_name, label, options):
        base_spacing = 5
        checkbox_text = self._get_checkbox_text(label, options)
        if len(checkbox_text) > 200:
            text_spacing = 10
        elif len(checkbox_text) > 100:
            text_spacing = 5
        else:
            text_spacing = 0
        return min(base_spacing + text_spacing, 60)

    def _get_checkbox_text(self, label, options):
        checkbox_text = label or ""
        if not checkbox_text or not checkbox_text.strip():
            if options and isinstance(options, dict):
                if 'checked' in options:
                    checkbox_text = options['checked']
                elif len(options) == 1:
                    checkbox_text = list(options.values())[0]
        return _strip_html_tags(checkbox_text or "")

    def _create_checkbox_field(self, c, *, name, tooltip, x, y, size, checked=False, fieldFlags=0):
        """
        Wrap create_acrobat_compatible_field with a best-effort attempt to set an export value.
        Some wrappers accept export_value= or value=. If not, we fall back cleanly.
        """
        export_val = name
        try:
            create_acrobat_compatible_field(
                c, 'checkbox',
                name=name,
                tooltip=tooltip,
                x=x, y=y, size=size,
                checked=checked,
                fieldFlags=fieldFlags,
                export_value=export_val
            )
            return
        except TypeError:
            pass

        try:
            create_acrobat_compatible_field(
                c, 'checkbox',
                name=name,
                tooltip=tooltip,
                x=x, y=y, size=size,
                checked=checked,
                fieldFlags=fieldFlags,
                value=export_val
            )
            return
        except TypeError:
            pass

        # Final fallback: no explicit export/value support
        create_acrobat_compatible_field(
            c, 'checkbox',
            name=name,
            tooltip=tooltip,
            x=x, y=y, size=size,
            checked=checked,
            fieldFlags=fieldFlags
        )

    # ---------- drawing ----------

    def _draw_single_checkbox(self, c, field_name, label, options_list, field_x, field_width, field_y, starting_y):
        value_key, option_label = options_list[0]
        checkbox_text = _strip_html_tags(option_label)

        style = self.generator.label_manager.get_label_style('checkbox', checkbox_text)
        font_name = style.font_name
        font_size = style.font_size
        color = style.color

        checkbox_size = self.generator.checkbox_size
        gap = CHECKBOX_GAP
        v_pad = CHECKBOX_VPAD
        line_gap = CHECKBOX_LINE_GAP
        baseline_nudge = CHECKBOX_BASELINE_NUDGE

        in_multi_col = (
            self.generator.current_group is not None and
            self.generator.group_columns is not None and
            self.generator.group_columns >= 2 and
            self.generator.column_widths is not None
        )

        if in_multi_col:
            # Wrap text within the column (minus square + gap)
            usable_text_w = max(0, field_width - (checkbox_size + gap))
            c.setFont(font_name, font_size)
            lines, _ = wrap_text(c, checkbox_text, usable_text_w, font_name, font_size)
            line_height = font_size + line_gap
            text_block_h = max(font_size, len(lines) * line_height)

            # Row height is the max of square size and wrapped text height (honor group min height too)
            content_row_h = max(checkbox_size, text_block_h) + v_pad
            enforced_min = getattr(self.generator, "group_row_height", 0) or 0
            row_h = max(content_row_h, enforced_min)

            # Vertically center the square and the text block within the row
            box_y = field_y - (row_h - checkbox_size) / 2 - checkbox_size
            first_line_y = field_y - (row_h - text_block_h) / 2 + baseline_nudge

            # Field name
            normalized_value = self._normalize_field_value(value_key)
            checkbox_name = f"{field_name}_{normalized_value}"

            # Draw form field
            self._create_checkbox_field(
                c,
                name=checkbox_name,
                tooltip=(checkbox_text[:50] + "...") if len(checkbox_text) > 50 else checkbox_text,
                x=field_x,
                y=box_y,
                size=checkbox_size,
                checked=False,
                fieldFlags=0
            )

            # Draw wrapped label
            c.setFont(font_name, font_size)
            c.setFillColor(color)
            text_x = field_x + checkbox_size + gap
            y = first_line_y
            for line in lines:
                c.drawString(text_x, y, line)
                y -= line_height

            # Tell the group how tall this row is
            final_y = field_y - row_h
            self._handle_group_positioning(field_x, field_width, final_y, field_y)

            # Only after the row is complete (both columns) should we move current_y
            idx = len(self.generator.group_fields)
            if idx % self.generator.group_columns == 0:
                self.generator.current_y = final_y - getattr(self.generator, 'group_row_gap', 6)  # tighter default
            return

        # ----- non-group branch -----
        lines, total_text_height = wrap_text(
            c, checkbox_text,
            self.generator.page_width - (field_x + checkbox_size + gap) - self.generator.margin_x,
            font_name, font_size
        )
        needed_height = max(checkbox_size, total_text_height) + 20
        if (field_y - needed_height) < self.generator.margin_bottom:
            if _check_page_break(self.generator, c, needed_height + 20):
                self.generator.page_manager.initialize_page(c)
                field_x, field_width, field_y = self._get_field_position()

        normalized_value = self._normalize_field_value(value_key)
        checkbox_name = f"{field_name}_{normalized_value}"

        # Align checkbox box with text on the SAME LINE
        text_y = field_y
        box_y = text_y - 3  # Position checkbox so it's vertically centered with text

        self._create_checkbox_field(
            c,
            name=checkbox_name,
            tooltip=(checkbox_text[:50] + "...") if len(checkbox_text) > 50 else checkbox_text,
            x=field_x,
            y=box_y,
            size=checkbox_size,
            checked=False,
            fieldFlags=0
        )

        c.setFont(font_name, font_size)
        c.setFillColor(color)
        text_x = field_x + checkbox_size + gap
        # Draw text on same line as checkbox
        c.drawString(text_x, text_y, lines[0] if lines else checkbox_text)
        # Draw any additional wrapped lines below
        line_y = text_y - font_size - max(1, line_gap)
        for line in lines[1:]:
            c.drawString(text_x, line_y, line)
            line_y -= font_size + max(1, line_gap)

        after_spacing = 8  # fixed, tighter
        # Calculate final_y based on the lowest point (either checkbox bottom or last text line)
        lowest_text_y = line_y if len(lines) > 1 else text_y - font_size
        final_y = min(box_y, lowest_text_y) - after_spacing
        self.generator.current_y = final_y

        if self.generator.current_group is not None:
            self.generator.group_fields.append({'y': final_y, 'name': field_name})

    def _calculate_optimal_spacing(self, options_list):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        checkbox_size = CHECKBOX_BOX_SIZE
        padding = CHECKBOX_GAP

        if self.generator.current_group is not None and self.generator.column_widths:
            group_index = len(self.generator.group_fields)
            column_index = group_index % self.generator.group_columns
            available_width = self.generator.column_widths[column_index]
        else:
            available_width = self.field_width

        total_width_needed = 0
        for _, option_label in options_list:
            clean_label = _strip_html_tags(option_label)
            label_width = stringWidth(clean_label, self.generator.font_family, self.generator.check_radio_label_size)
            item_width = checkbox_size + padding + label_width + 8
            total_width_needed += item_width

        if total_width_needed <= available_width:
            return total_width_needed / len(options_list) if options_list else available_width

        items_per_row = 2 if len(options_list) > 2 else len(options_list)
        item_spacing = available_width / items_per_row if items_per_row > 0 else available_width
        min_viable = checkbox_size + padding + 80
        return max(item_spacing, min_viable)

    def _draw_multiple_checkboxes(self, c, field_name, label, options_list, field_x, field_width, field_y, starting_y):
        # Optional field label above the option list
        if label and label.strip():
            style = self.generator.label_manager.get_label_style('checkbox', label)
            self.generator.label_manager.draw_label(c, label, style, spacing_before=0, tight=True)

        in_multi_col = (
            self.generator.current_group is not None and
            self.generator.group_columns is not None and
            self.generator.group_columns >= 2 and
            self.generator.column_widths is not None
        )

        checkbox_size = CHECKBOX_BOX_SIZE
        gap = CHECKBOX_GAP
        line_gap = CHECKBOX_LINE_GAP
        v_pad = CHECKBOX_VPAD
        baseline_nudge = CHECKBOX_BASELINE_NUDGE

        check_label_size = self.generator.check_radio_label_size

        if in_multi_col:
            # Column-constrained vertical list with centered rows (compact)
            usable_text_w = max(0, field_width - (checkbox_size + gap))
            c.setFont(self.generator.font_family, check_label_size)
            c.setFillColor(self.colors['primary'])

            # Compact: ignore any tall group_row_height for multi-option lines
            enforced_min = MULTI_MIN_ROW

            y_top = self.generator.current_y
            y_cursor = y_top

            for value_key, option_label in options_list:
                clean_label = _strip_html_tags(option_label)

                lines, _ = wrap_text(c, clean_label, usable_text_w, self.generator.font_family, check_label_size)
                line_height = check_label_size + line_gap
                text_block_h = max(check_label_size, len(lines) * line_height)

                content_row_h = max(checkbox_size, text_block_h) + v_pad
                row_h = max(content_row_h, enforced_min)

                # Page break if necessary
                if (y_cursor - row_h) < self.generator.margin_bottom:
                    if self.generator.current_group is not None:
                        self.generator._handle_group_page_break(c)
                    else:
                        _check_page_break(self.generator, c, row_h + 20)
                        self.generator.page_manager.initialize_page(c)
                    c.setFont(self.generator.font_family, check_label_size)
                    c.setFillColor(self.colors['primary'])
                    y_top = self.generator.current_y
                    y_cursor = y_top

                # Center square + text inside the item row
                box_y = y_cursor - (row_h - checkbox_size) / 2 - checkbox_size
                first_line_y = y_cursor - (row_h - text_block_h) / 2 + baseline_nudge

                normalized_value = self._normalize_field_value(value_key)
                checkbox_name = f"{field_name}_{normalized_value}"

                self._create_checkbox_field(
                    c,
                    name=checkbox_name,
                    tooltip=f"{field_name} - {clean_label}",
                    x=field_x,
                    y=box_y,
                    size=checkbox_size,
                    checked=False,
                    fieldFlags=0
                )

                text_x = field_x + checkbox_size + gap
                y = first_line_y
                for line in lines:
                    c.drawString(text_x, y, line)
                    y -= line_height

                y_cursor -= row_h

            # Whole block height
            block_h = y_top - y_cursor
            final_field_y = field_y - block_h

            if self.generator.current_group is not None:
                self._handle_group_positioning(field_x, field_width, final_field_y, field_y)
                # End-of-row step uses a smaller default gap (6)
                idx = len(self.generator.group_fields)
                if idx % self.generator.group_columns == 0:
                    self.generator.current_y = final_field_y - getattr(self.generator, 'group_row_gap', 6)
            else:
                self.generator.current_y = y_cursor - 3  # slightly tighter
            return

        # --------- non-group behavior (horizontal packing) ----------
        checkbox_size = self.generator.checkbox_size
        gap = CHECKBOX_GAP
        label_to_checkbox_gap = -8   # slightly less negative to tighten
        self.generator.current_y -= label_to_checkbox_gap

        c.setFont(self.generator.font_family, check_label_size)
        c.setFillColor(self.colors['primary'])

        row_height = checkbox_size + 4  # tighter
        available_width = field_width
        start_x = field_x

        from reportlab.pdfbase.pdfmetrics import stringWidth
        item_widths = []
        for _, option_label in options_list:
            clean_label = _strip_html_tags(option_label)
            label_width = stringWidth(clean_label, self.generator.font_family, check_label_size)
            item_width = checkbox_size + gap + label_width + 12
            item_widths.append(item_width)

        current_row_width = 0
        current_x = start_x
        items_in_current_row = 0

        for i, (value_key, option_label) in enumerate(options_list):
            clean_option_label = _strip_html_tags(option_label)
            item_width = item_widths[i]

            if current_row_width + item_width > available_width and items_in_current_row > 0:
                current_x = start_x
                self.generator.current_y -= row_height
                items_in_current_row = 0
                current_row_width = 0

            checkbox_y_position = self.generator.current_y - checkbox_size + 2
            if checkbox_y_position < self.generator.margin_bottom:
                if _check_page_break(self.generator, c, checkbox_size + 20):
                    self.generator.page_manager.initialize_page(c)
                    current_x = start_x
                    items_in_current_row = 0
                    current_row_width = 0
                    c.setFont(self.generator.font_family, check_label_size)
                    c.setFillColor(self.colors['primary'])

            normalized_value = self._normalize_field_value(value_key)
            checkbox_name = f"{field_name}_{normalized_value}"
            final_checkbox_y = self.generator.current_y - checkbox_size + 2

            self._create_checkbox_field(
                c,
                name=checkbox_name,
                tooltip=f"{field_name} - {clean_option_label}",
                x=current_x,
                y=final_checkbox_y,
                size=checkbox_size,
                checked=False,
                fieldFlags=0
            )

            label_x = current_x + checkbox_size + gap
            label_y = self.generator.current_y - 6   # tighter baseline
            c.drawString(label_x, label_y, clean_option_label)

            current_x += item_width
            current_row_width += item_width
            items_in_current_row += 1

        final_field_y = self.generator.current_y - checkbox_size - 8  # tighter
        if self.generator.current_group is not None:
            self._handle_group_positioning(field_x, field_width, final_field_y, starting_y)
        else:
            self.generator.current_y = final_field_y - 3

    # ---------- layout helpers ----------

    def _get_field_position(self):
        field_x = self.margin_x
        field_width = self.field_width
        field_y = self.generator.current_y

        if self.generator.current_group is not None:
            group_index = len(self.generator.group_fields)
            column_index = group_index % self.generator.group_columns

            field_x = self.margin_x
            if column_index > 0:
                field_x += sum(self.generator.column_widths[:column_index])
                field_x += self.generator.group_spacing * column_index

            field_width = self.generator.column_widths[column_index]

            if column_index > 0 and self.generator.group_fields:
                row_index = group_index // self.generator.group_columns
                first_in_row_index = row_index * self.generator.group_columns
                if first_in_row_index < len(self.generator.group_fields):
                    first_field = self.generator.group_fields[first_in_row_index]
                    field_y = first_field.get('start_y', first_field.get('y', field_y))

        return field_x, field_width, field_y

    def _handle_group_positioning(self, field_x, field_width, final_y, start_y):
        self.generator.group_fields.append({
            'name': 'checkbox',
            'x': field_x,
            'y': final_y,
            'start_y': start_y,
            'width': field_width
        })

        # End-of-row gap uses group_row_gap when available, else a tighter default of 6
        if len(self.generator.group_fields) % self.generator.group_columns == 0:
            row_start = len(self.generator.group_fields) - self.generator.group_columns
            row_fields = self.generator.group_fields[row_start:]
            min_y = min(f.get('y', self.generator.current_y) for f in row_fields)
            self.generator.current_y = min_y - getattr(self.generator, 'group_row_gap', 6)
