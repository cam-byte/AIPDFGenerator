# page_manager.py - HEADER ONLY ON FIRST PAGE
from .utils import _prepare_logo_image, _calculate_logo_dimensions

class PageManager:
    def __init__(self, generator):
        self.generator = generator
        self.colors = generator.colors
        self.page_width = generator.page_width
        self.page_height = generator.page_height
        self.margin_x = generator.margin_x

    def initialize_page(self, canvas):
        """Initialize a new page with conditional header"""
        # Reset Y position to top of page
        self.generator.current_y = self.page_height - self.margin_x

        # Only draw business header on first page
        if self.generator.current_page == 1:
            # Get the actual Y position after header is drawn
            header_end_y = self._draw_clean_business_header(canvas)
            # Set current_y to just below the header with extra spacing for main title
            self.generator.current_y = header_end_y - 30
        else:
            # Less space from top on subsequent pages
            self.generator.current_y -= 15

    def _draw_clean_business_header(self, canvas):
        """Draw clean, professional business header (first page only)

        Layout: Logo on LEFT, location columns on RIGHT (right-aligned)
        Each location column: street / city state zip / phone

        Returns:
            float: The Y position after the header (position of the bottom line)
        """
        current_font = canvas._fontname
        current_size = canvas._fontsize
        current_color = canvas._fillColorObj

        # Header positioning
        header_y = self.page_height - 25
        line_height = 12  # Line spacing within location columns
        col_gap = 20  # Gap between location columns

        # Calculate logo dimensions first to know where to align text
        logo_height = 0
        logo_width = 0
        logo_img = None
        if self.generator.logo_path:
            logo_img = _prepare_logo_image(self.generator.logo_path)
            if logo_img:
                logo_width, logo_height = _calculate_logo_dimensions(
                    self.generator.logo_path,
                    max_width=150,
                    max_height=55
                )

        # Logo top position (where both logo and text should align)
        logo_top_y = header_y
        logo_bottom_y = header_y - logo_height if logo_height else header_y

        # Draw logo on the LEFT if available
        if logo_img:
            canvas.drawImage(
                logo_img,
                self.margin_x,
                logo_bottom_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask='auto'
            )

        # Draw location columns on the RIGHT (right-aligned, columns fill from right)
        # Text should start at logo_top_y minus a small offset for text baseline
        hfs = self.generator.header_font_size
        canvas.setFont(self.generator.font_family, hfs)
        canvas.setFillColor(self.colors['primary'])

        locations = getattr(self.generator, 'locations', None)
        locations_bottom_y = header_y

        # Calculate text start Y - align first line of text with logo top
        text_start_y = header_y - 15  # Push text down to align with logo visual top

        if locations and isinstance(locations, list) and len(locations) > 0:
            # Calculate column widths based on content
            col_widths = []
            for loc in locations:
                street = loc.get('street', '')
                city_state_zip = loc.get('city_state_zip', '')
                phone = loc.get('phone', '')
                max_width = max(
                    canvas.stringWidth(street, self.generator.font_family, hfs),
                    canvas.stringWidth(city_state_zip, self.generator.font_family, hfs),
                    canvas.stringWidth(phone, self.generator.font_family, hfs)
                )
                col_widths.append(max_width)

            # Draw columns from right to left
            right_edge = self.page_width - self.margin_x
            for i, loc in enumerate(locations):
                col_width = col_widths[i]
                col_x = right_edge - col_width

                street = loc.get('street', '')
                city_state_zip = loc.get('city_state_zip', '')
                phone = loc.get('phone', '')

                # Draw right-aligned text for this column, starting aligned with logo top
                y = text_start_y
                if street:
                    canvas.drawRightString(right_edge, y, street)
                    y -= line_height
                if city_state_zip:
                    canvas.drawRightString(right_edge, y, city_state_zip)
                    y -= line_height
                if phone:
                    canvas.drawRightString(right_edge, y, phone)
                    y -= line_height

                locations_bottom_y = min(locations_bottom_y, y)

                # Move right_edge left for next column
                right_edge = col_x - col_gap

        else:
            # Backwards compatible: single address/phone on the right
            canvas.setFont(self.generator.font_family, hfs)
            if self.generator.address:
                text_width = canvas.stringWidth(self.generator.address, self.generator.font_family, hfs)
                canvas.drawString(self.page_width - self.margin_x - text_width, header_y, self.generator.address)
            if self.generator.phone:
                text_width = canvas.stringWidth(self.generator.phone, self.generator.font_family, hfs)
                canvas.drawString(self.page_width - self.margin_x - text_width, header_y - line_height, self.generator.phone)
            locations_bottom_y = header_y - (line_height * 2)

        # Determine where the header ends (lowest of logo or locations)
        header_bottom = min(logo_bottom_y, locations_bottom_y) - 5

        # Draw divider line
        canvas.setStrokeColor(self.colors['border'])
        canvas.setLineWidth(0.5)
        canvas.line(self.margin_x, header_bottom,
                   self.page_width - self.margin_x, header_bottom)

        # Restore original font settings
        canvas.setFont(current_font, current_size)
        canvas.setFillColor(current_color)

        # Return the Y position after the header line
        return header_bottom
