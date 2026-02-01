# fields/group_field.py - SIMPLIFIED AND FIXED

class GroupField:
    def __init__(self, generator, canvas):
        self.generator = generator
        self.canvas = canvas
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width
        self.colors = generator.colors

        # Simplified group types - only track functional layout groups
        # Note: widths are percentages of available_width (field_width - total_spacing)
        # Widths MUST sum to exactly 1.0 to fill the full page width
        self.layout_groups = {
            # Auto-flow group (internal use - CSS flexbox-like 2-column layout)
            '__auto_flow__': {'columns': 2, 'widths': [0.5, 0.5], 'spacing': 10},
            'two_columns': {'columns': 2, 'widths': [0.5, 0.5], 'spacing': 10},
            'four_columns': {'columns': 4, 'widths': [0.25, 0.25, 0.25, 0.25], 'spacing': 8},
            'name_details': {'columns': 3, 'widths': [0.45, 0.40, 0.15], 'spacing': 10},
            'address_details': {'columns': 4, 'widths': [0.40, 0.28, 0.15, 0.17], 'spacing': 8},
            'patient_contact': {'columns': 2, 'widths': [0.5, 0.5], 'spacing': 10},
            'phone_details': {'columns': 3, 'widths': [0.34, 0.33, 0.33], 'spacing': 10},
            # Dental chart layouts - 16 columns for permanent teeth, 10 for deciduous
            'tooth_container': {'columns': 16, 'widths': [1/16]*16, 'spacing': 2},
        }

        # Container groups that we ignore for layout purposes
        self.container_groups = {
            'form_container', 'form_content_container', 'primary_insurance',
            'secondary_insurance', 'permanent', 'deciduous', 'top_row',
            'bottom_row', 'tooth', 'indent_x1', 'substance_details',
            'pharmacy_information'
        }

        # Track nested groups with a stack
        if not hasattr(self.generator, 'group_stack'):
            self.generator.group_stack = []

    def start_group(self, group_name):
        """Simplified group start - only handle layout groups"""
        clean_group_name = group_name.lstrip('*')

        # Initialize stack if needed
        if not hasattr(self.generator, 'group_stack'):
            self.generator.group_stack = []

        # Handle inline_container specially - it uses a different rendering mode
        if clean_group_name == 'inline_container':
            from .inline_text_field import InlineContainerManager
            self.generator.group_stack.append(('inline', clean_group_name))
            inline_manager = InlineContainerManager(self.generator, self.canvas)
            inline_manager.start_container()
            return

        # If this is a container group, push it to stack but don't affect layout
        if clean_group_name in self.container_groups:
            self.generator.group_stack.append(('container', clean_group_name))
            return

        # If we're already in a layout group, end it first
        if self.generator.current_group is not None:
            self.end_group()

        # Only start if this is a recognized layout group
        if clean_group_name in self.layout_groups:
            self.generator.group_stack.append(('layout', clean_group_name))
            # Check if tooth_container needs 10 or 16 columns based on parent context
            if clean_group_name == 'tooth_container':
                # Check if we're inside a deciduous context (10 teeth) or permanent (16 teeth)
                in_deciduous = any(name == 'deciduous' for _, name in self.generator.group_stack)
                if in_deciduous:
                    self._initialize_group_with_config(clean_group_name, 10)
                else:
                    self._initialize_group_with_config(clean_group_name, 16)
            else:
                self._initialize_group(clean_group_name)

    def _initialize_group(self, group_name):
        self.generator.current_group = group_name
        self.generator.group_fields = []
        self.generator.group_start_y = self.generator.current_y

        config = self.layout_groups[group_name]
        columns = config['columns']
        widths = config['widths']
        spacing = config['spacing']

        total_spacing = spacing * (columns - 1) if columns > 1 else 0
        available_width = self.field_width - total_spacing

        self.generator.column_widths = [w * available_width for w in widths]
        self.generator.group_spacing = spacing
        self.generator.group_columns = columns

        # NEW: consistent vertical rhythm used by checkbox rows
        # works well with 12px boxes + 9/10pt labels
        self.generator.group_row_height = 22
        self.generator.group_row_gap = 10  # gap added after a completed row

    def _initialize_group_with_config(self, group_name, num_columns):
        """Initialize a group with a custom column count (for tooth_container)"""
        self.generator.current_group = group_name
        self.generator.group_fields = []
        self.generator.group_start_y = self.generator.current_y

        spacing = 2  # tight spacing for teeth
        widths = [1.0 / num_columns] * num_columns

        total_spacing = spacing * (num_columns - 1) if num_columns > 1 else 0
        available_width = self.field_width - total_spacing

        self.generator.column_widths = [w * available_width for w in widths]
        self.generator.group_spacing = spacing
        self.generator.group_columns = num_columns

        # Tighter settings for dental charts
        self.generator.group_row_height = 20
        self.generator.group_row_gap = 8

    def end_group(self):
        """End the current group and align fields properly"""
        # Initialize stack if needed
        if not hasattr(self.generator, 'group_stack'):
            self.generator.group_stack = []

        # Pop from stack to see what we're ending
        if self.generator.group_stack:
            group_type, group_name = self.generator.group_stack.pop()

            # If it's a container group, just pop and return - don't affect layout
            if group_type == 'container':
                return

            # If it's an inline container, end the inline mode
            if group_type == 'inline':
                from .inline_text_field import InlineContainerManager
                inline_manager = InlineContainerManager(self.generator, self.canvas)
                inline_manager.end_container()
                return

        # Only proceed with ending if we have an active layout group
        if self.generator.current_group is None:
            return

        # Calculate the final Y position based on all fields in the group
        if self.generator.group_fields:
            # Find the lowest Y position among all fields
            min_y = min(field.get('y', self.generator.current_y) for field in self.generator.group_fields)
            # Add some spacing after the group
            proposed_y = min_y - 15
            if proposed_y < self.generator.margin_bottom:
                proposed_y = self.generator.current_y
            self.generator.current_y = proposed_y

        # Reset group state
        self.generator.current_group = None
        self.generator.group_fields = []
        self.generator.column_widths = None
        self.generator.group_spacing = None
        self.generator.group_columns = None
        self.generator.group_start_y = None

    def get_field_position_in_group(self):
        """Get the position for the next field in the current group"""
        if self.generator.current_group is None:
            return self.margin_x, self.field_width, self.generator.current_y

        group_index = len(self.generator.group_fields)
        column_index = group_index % self.generator.group_columns
        row_index = group_index // self.generator.group_columns

        # Calculate X position
        field_x = self.margin_x
        if column_index > 0:
            field_x += sum(self.generator.column_widths[:column_index])
            field_x += self.generator.group_spacing * column_index

        field_width = self.generator.column_widths[column_index]

        # Calculate Y position - use row-based positioning
        field_y = self.generator.group_start_y

        if row_index > 0:
            # For subsequent rows, look at the previous row's minimum Y
            prev_row_start = (row_index - 1) * self.generator.group_columns
            prev_row_end = min(prev_row_start + self.generator.group_columns, len(self.generator.group_fields))
            if prev_row_end > prev_row_start:
                prev_row_fields = self.generator.group_fields[prev_row_start:prev_row_end]
                prev_row_min_y = min(f.get('y', field_y) for f in prev_row_fields)
                field_y = prev_row_min_y - 18  # Reduced row spacing from 35 to 18

        # For column > 0 in any row, align with first field in row's start_y
        if column_index > 0 and self.generator.group_fields:
            first_in_row_index = row_index * self.generator.group_columns
            if first_in_row_index < len(self.generator.group_fields):
                first_field = self.generator.group_fields[first_in_row_index]
                field_y = first_field.get('start_y', field_y)

        # Page break detection: if calculated Y is much lower than current_y,
        # a page break happened and we should use current_y instead
        if field_y < self.generator.current_y - 100:
            field_y = self.generator.current_y
            # Update group_start_y for this new page
            if column_index == 0:
                self.generator.group_start_y = field_y

        return field_x, field_width, field_y

    def add_field_to_group(self, field_name, final_y, start_y=None, field_x=None, field_width=None):
        """Add a field to the current group tracking"""
        if self.generator.current_group is None:
            return

        self.generator.group_fields.append({
            'name': field_name,
            'y': final_y,
            'start_y': start_y or final_y,
            'x': field_x or self.margin_x,
            'width': field_width or self.field_width
        })

        # Handle row completion - update current_y when row is complete
        if len(self.generator.group_fields) % self.generator.group_columns == 0:
            row_start = len(self.generator.group_fields) - self.generator.group_columns
            row_fields = self.generator.group_fields[row_start:]
            min_y = min(f.get('y', self.generator.current_y) for f in row_fields)
            self.generator.current_y = min_y - 8  # Reduced from 20 for tighter spacing
