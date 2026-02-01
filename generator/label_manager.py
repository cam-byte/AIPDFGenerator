# label_manager.py - Enhanced version with ol support and smart page break detection
import re
from .utils import _strip_html_tags, _wrap_text, _check_page_break

class LabelManager:
    def __init__(self, generator):
        self.generator = generator
        self.label_styles = generator.label_styles
        self.margin_x = generator.margin_x
        self.field_width = generator.field_width
        self.colors = generator.colors

    def get_label_style(self, field_type, label):
        """Determine the appropriate label style based on content"""
        if field_type == 'label':
            if '<h1>' in label.lower():
                return self.label_styles['h1']
            elif '<h3>' in label.lower():
                return self.label_styles['h3']
            elif '<h4>' in label.lower():
                return self.label_styles['h4']
            elif '<h5>' in label.lower():
                return self.label_styles['h5']
            elif '<p>' in label.lower():
                # Check if there are lists INSIDE the paragraph (both ul and ol)
                if '<ul>' in label.lower() or '<li>' in label.lower() or '<ol>' in label.lower():
                    return self.label_styles.get('ul', self.label_styles['p'])
                else:
                    return self.label_styles['p']
            elif '<ul>' in label.lower() or '<li>' in label.lower() or '<ol>' in label.lower():
                return self.label_styles.get('ul', self.label_styles['p'])
            else:
                return self.label_styles['regular']
        else:
            return self.label_styles['field_label']

    def _extract_link_text(self, html_text):
        """Extract text from links, preserving just the inner HTML of <a> tags"""
        # Pattern to match <a> tags and capture their inner content
        link_pattern = r'<a[^>]*>(.*?)</a>'

        def replace_link(match):
            return match.group(1)  # Return just the inner content

        return re.sub(link_pattern, replace_link, html_text, flags=re.IGNORECASE | re.DOTALL)

    def _process_list_content(self, html_text):
        """Process <ul>/<ol> and <li> tags to create formatted list text with proper numbering"""

        # Check if this is an ordered list (ol) or unordered list (ul)
        is_ordered_list = '<ol>' in html_text.lower() or '<ol ' in html_text.lower()

        # Handle nested lists by preserving structure
        # First, let's identify if we have multiple lists or nested lists
        ol_matches = list(re.finditer(r'<ol[^>]*>.*?</ol>', html_text, flags=re.IGNORECASE | re.DOTALL))
        ul_matches = list(re.finditer(r'<ul[^>]*>.*?</ul>', html_text, flags=re.IGNORECASE | re.DOTALL))

        if ol_matches or ul_matches:
            # We have structured lists, process them individually
            return self._process_structured_lists(html_text)
        else:
            # Legacy processing for simple list items
            return self._process_simple_list_items(html_text, is_ordered_list)

    def _process_structured_lists(self, html_text):
        """Process structured <ol> and <ul> lists with proper numbering and letter support"""
        result_lines = []
        current_pos = 0

        # Find all list blocks (both ol and ul)
        list_pattern = r'(<(ol|ul)[^>]*>.*?</\2>)'
        matches = list(re.finditer(list_pattern, html_text, flags=re.IGNORECASE | re.DOTALL))

        for match in matches:
            # Add any text before this list
            before_text = html_text[current_pos:match.start()].strip()
            if before_text:
                clean_before = _strip_html_tags(before_text).strip()
                if clean_before:
                    result_lines.extend(clean_before.split('\n'))

            # Process the list
            list_html = match.group(1)
            list_type = match.group(2).lower()

            # Check for letter-style attribute in ol tags
            is_letter_style = False
            use_uppercase = False
            if list_type == 'ol':
                # Check for type="a" or type="A" attributes
                type_match = re.search(r'type=["\']([aA])["\']', list_html, re.IGNORECASE)
                if type_match:
                    is_letter_style = True
                    use_uppercase = type_match.group(1) == 'A'

            # Extract list items
            li_pattern = r'<li[^>]*>(.*?)</li>'
            li_matches = re.findall(li_pattern, list_html, flags=re.IGNORECASE | re.DOTALL)

            list_counter = 1
            for li_content in li_matches:
                clean_content = _strip_html_tags(li_content).strip()
                if clean_content:
                    if list_type == 'ol':
                        if is_letter_style:
                            # Convert number to letter (1=a, 2=b, etc.)
                            letter = chr(ord('a') + list_counter - 1)
                            if use_uppercase:
                                letter = letter.upper()
                            result_lines.append(f"{letter}. {clean_content}")
                        else:
                            # Regular numbered list
                            result_lines.append(f"{list_counter}. {clean_content}")
                        list_counter += 1
                    else:  # ul
                        result_lines.append(f"• {clean_content}")

            current_pos = match.end()

        # Add any remaining text after the last list
        remaining_text = html_text[current_pos:].strip()
        if remaining_text:
            clean_remaining = _strip_html_tags(remaining_text).strip()
            if clean_remaining:
                result_lines.extend(clean_remaining.split('\n'))

        return '\n'.join(result_lines)

    def _process_simple_list_items(self, text, is_ordered_list):
        """Legacy processing for simple list items (fallback)"""
        # Remove <p> and </p> tags but keep the content
        text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)

        # Remove <ul>, </ul>, <ol>, and </ol> tags
        text = re.sub(r'</?[uo]l[^>]*>', '\n', text, flags=re.IGNORECASE)

        # Replace <li> tags with appropriate markers
        if is_ordered_list:
            # For ordered lists, we'll use a placeholder that we'll replace with numbers
            text = re.sub(r'<li[^>]*>', '\n##LISTITEM##', text, flags=re.IGNORECASE)
        else:
            # For unordered lists, use bullet points
            text = re.sub(r'<li[^>]*>', '\n• ', text, flags=re.IGNORECASE)

        text = re.sub(r'</li>', '', text, flags=re.IGNORECASE)

        # Clean up extra whitespace but preserve line breaks
        lines = text.split('\n')
        processed_lines = []
        list_counter = 1

        for line in lines:
            line = line.strip()
            if line:
                if line.startswith('##LISTITEM##'):
                    # Replace placeholder with numbered list item
                    line = f"{list_counter}. " + line[12:]  # Remove ##LISTITEM## and add number
                    list_counter += 1
                processed_lines.append(line)

        return '\n'.join(processed_lines)

    def _clean_html_content(self, html_text):
        """Clean HTML content by handling links and lists before stripping tags"""
        # First, extract link text (preserve inner HTML of <a> tags)
        text = self._extract_link_text(html_text)

        # Handle lists if present (both ul and ol)
        if '<ul>' in text.lower() or '<li>' in text.lower() or '<ol>' in text.lower():
            text = self._process_list_content(text)

        # Finally strip remaining HTML tags
        return _strip_html_tags(text)

    def draw_label(self, canvas, label, style, draw_line=False, spacing_before=None, tight=False):
        """Draw label with enhanced HTML processing"""
        self._draw_enhanced_label(canvas, label, style, draw_line, spacing_before, tight)

    def _draw_enhanced_label(self, canvas, label, style, draw_line=False, spacing_before=None, tight=False):
        """Enhanced label drawing with link and list support and smart wrapping control"""
        current_font = canvas._fontname
        current_size = canvas._fontsize
        current_color = canvas._fillColorObj

        # Clean the label text using enhanced HTML processing
        clean_text = self._clean_html_content(label)

        # Skip empty labels
        if not clean_text.strip():
            return

        # Check for splittable marker in the original label
        allow_splitting = 'data-split="true"' in label or 'data-splittable="true"' in label

        # Apply spacing_before if provided, otherwise use style's spacing_before
        if spacing_before is not None:
            self.generator.current_y -= spacing_before
        elif hasattr(style, 'spacing_before'):
            self.generator.current_y -= style.spacing_before

        # Set font and color
        canvas.setFont(style.font_name, style.font_size)
        canvas.setFillColor(style.color)

        # Determine content type - lists take absolute priority (both ul and ol)
        is_list = "<ul>" in label.lower() or "<li>" in label.lower() or "<ol>" in label.lower()
        is_paragraph = "<p>" in label.lower() and "</p>" in label.lower() and not is_list

        # Use full page width for paragraphs and lists, field width for others
        if is_paragraph or is_list:
            wrap_width = self.generator.page_width - 2 * self.generator.margin_x
            line_height = style.font_size + 6  # Increased line height for paragraphs and lists
        else:
            wrap_width = self.field_width
            line_height = style.font_size + 1  # Normal line height for other labels

        # Smart content handling based on splitting preference
        if allow_splitting:
            # Use smart splitting that breaks content naturally at page boundaries
            self._draw_content_with_smart_splitting(canvas, label, clean_text, style, wrap_width, line_height, is_list, is_paragraph, draw_line)
        else:
            # Use original keep-together logic
            self._draw_content_keep_together(canvas, label, clean_text, style, wrap_width, line_height, is_list, is_paragraph, draw_line)

        # Restore original settings
        canvas.setFont(current_font, current_size)
        canvas.setFillColor(current_color)

    def _draw_content_with_smart_splitting(self, canvas, original_label, clean_text, style, wrap_width, line_height, is_list, is_paragraph, draw_line):
        """Draw content with smart page break splitting"""

        # Handle paragraph margins if applicable
        if (is_paragraph or is_list) and hasattr(style, 'paragraph_margin_top'):
            self.generator.current_y -= style.paragraph_margin_top

        # For lists, we need to handle each line separately to preserve bullet formatting
        if is_list:
            # Let's see what method we're actually calling
            method = getattr(self, '_draw_list_with_smart_page_breaks')

            try:
                # Call with explicit arguments
                result = self._draw_list_with_smart_page_breaks(canvas, clean_text, style, wrap_width, line_height)
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Fallback to original method
                self._draw_list_content(canvas, clean_text, style, wrap_width, line_height)
        else:
            try:
                # Regular text wrapping for non-list content
                wrapped_lines = _wrap_text(clean_text, wrap_width, style.font_size, style.font_name)
                self._draw_text_lines_with_splitting(canvas, wrapped_lines, line_height, style)
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Fallback to original method
                wrapped_lines = _wrap_text(clean_text, wrap_width, style.font_size, style.font_name)
                self._draw_text_lines(canvas, wrapped_lines, line_height)

        # Handle margins and underlines
        if (is_paragraph or is_list) and hasattr(style, 'paragraph_margin_bottom'):
            self.generator.current_y -= style.paragraph_margin_bottom

        # Draw underline for h1 headers if requested
        if draw_line and clean_text.strip():
            line_y = self.generator.current_y + line_height + 7
            canvas.setStrokeColor(self.colors['accent'])
            canvas.setLineWidth(1)
            canvas.line(self.margin_x, line_y, self.margin_x + wrap_width, line_y)

    def _draw_list_with_smart_page_breaks(self, canvas, text, style, wrap_width, line_height):
        """Draw list content with smart page break splitting and proper text wrapping."""

        if not text:
            return

        # Split into logical lines first (e.g., paragraphs)
        paragraphs = text.split('\n')

        lines_drawn = 0

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                self.generator.current_y -= line_height // 2
                continue

            wrapped_lines = _wrap_text(para, wrap_width, style.font_size, style.font_name)

            for j, line in enumerate(wrapped_lines):
                if self.generator.current_y - line_height < self.generator.margin_bottom:
                    canvas.showPage()
                    self.generator.current_page += 1
                    self.generator.page_manager.initialize_page(canvas)
                    canvas.setFont(style.font_name, style.font_size)
                    canvas.setFillColor(style.color)

                canvas.drawString(self.margin_x, self.generator.current_y, line)
                self.generator.current_y -= line_height
                lines_drawn += 1


        if lines_drawn > 0:
            self.generator.current_y -= style.spacing_after


    def _draw_content_keep_together(self, canvas, original_label, clean_text, style, wrap_width, line_height, is_list, is_paragraph, draw_line):
        """Draw content keeping it together (original behavior)"""
        # Handle paragraph margins if applicable
        if (is_paragraph or is_list) and hasattr(style, 'paragraph_margin_top'):
            self.generator.current_y -= style.paragraph_margin_top

        # For lists, we need to handle each line separately to preserve bullet formatting
        if is_list:
            self._draw_list_content(canvas, clean_text, style, wrap_width, line_height)
        else:
            # Regular text wrapping for non-list content
            wrapped_lines = _wrap_text(clean_text, wrap_width, style.font_size, style.font_name)
            self._draw_text_lines(canvas, wrapped_lines, line_height)

        # Handle margins and underlines
        if (is_paragraph or is_list) and hasattr(style, 'paragraph_margin_bottom'):
            self.generator.current_y -= style.paragraph_margin_bottom

        # Draw underline for h1 headers if requested
        if draw_line and clean_text.strip():
            line_y = self.generator.current_y + line_height + 7
            canvas.setStrokeColor(self.colors['accent'])
            canvas.setLineWidth(1)
            canvas.line(self.margin_x, line_y, self.margin_x + wrap_width, line_y)

    def _draw_list_content_with_splitting(self, canvas, text, style, wrap_width, line_height):
        """Draw list content with smart page break splitting"""
        lines = text.split('\n')
        lines_drawn = 0
        list_counter = 1  # Track numbering across page breaks

        for line in lines:
            line = line.strip()
            if not line:
                # Empty line - add some spacing for paragraph breaks
                if self.generator.current_y - (line_height // 2) < self.generator.margin_bottom:
                    self._handle_page_break(canvas, style)
                self.generator.current_y -= line_height // 2
                continue

            # Check if this is a list item (bullet, numbered, or letter)
            is_bullet_item = line.startswith('•')
            is_numbered_item = re.match(r'^\d+\.\s', line)
            is_letter_item = re.match(r'^[a-zA-Z]\.\s', line)

            if is_bullet_item or is_numbered_item or is_letter_item:
                # This is a list item
                if is_bullet_item:
                    marker_part = '• '
                    text_part = line[2:].strip()
                elif is_numbered_item:
                    # Extract the number and period (e.g., "1. ")
                    match = re.match(r'^(\d+\.\s)(.*)', line)
                    marker_part = match.group(1)
                    text_part = match.group(2)
                else:  # letter item
                    # Extract the letter and period (e.g., "A. ")
                    match = re.match(r'^([a-zA-Z]\.\s)(.*)', line)
                    marker_part = match.group(1)
                    text_part = match.group(2)

                # Calculate indent for text after marker
                marker_width = canvas.stringWidth(marker_part, style.font_name, style.font_size)
                text_indent = self.margin_x + marker_width
                text_wrap_width = wrap_width - marker_width

                # Wrap the text part
                if text_part:
                    wrapped_text_lines = _wrap_text(text_part, text_wrap_width, style.font_size, style.font_name)

                    # Check if we have room for at least the first line
                    if self.generator.current_y - line_height < self.generator.margin_bottom:
                        self._handle_page_break(canvas, style)

                    # Draw first line on same line as marker
                    if wrapped_text_lines:
                        canvas.drawString(self.margin_x, self.generator.current_y, marker_part)
                        canvas.drawString(text_indent, self.generator.current_y, wrapped_text_lines[0])
                        self.generator.current_y -= line_height
                        lines_drawn += 1

                        # Draw continuation lines with same indent, checking for page breaks
                        for wrapped_line in wrapped_text_lines[1:]:
                            # Check page break for each continuation line
                            if self.generator.current_y - line_height < self.generator.margin_bottom:
                                self._handle_page_break(canvas, style)

                            canvas.drawString(text_indent, self.generator.current_y, wrapped_line)
                            self.generator.current_y -= line_height
                            lines_drawn += 1
                else:
                    # Just marker, no text
                    if self.generator.current_y - line_height < self.generator.margin_bottom:
                        self._handle_page_break(canvas, style)

                    canvas.drawString(self.margin_x, self.generator.current_y, marker_part)
                    self.generator.current_y -= line_height
                    lines_drawn += 1
            else:
                # Regular paragraph text (not a list item)
                wrapped_lines = _wrap_text(line, wrap_width, style.font_size, style.font_name)
                for wrapped_line in wrapped_lines:
                    if wrapped_line.strip():
                        # Check page break for each wrapped line
                        if self.generator.current_y - line_height < self.generator.margin_bottom:
                            self._handle_page_break(canvas, style)

                        canvas.drawString(self.margin_x, self.generator.current_y, wrapped_line)
                        self.generator.current_y -= line_height
                        lines_drawn += 1

        # Add spacing after list
        if lines_drawn > 0:
            self.generator.current_y -= style.spacing_after

    def _draw_text_lines_with_splitting(self, canvas, wrapped_lines, line_height, style):
        """Draw regular text lines with smart page break splitting"""
        lines_drawn = 0

        for line in wrapped_lines:
            if line.strip():
                # Check page break for each line
                if self.generator.current_y - line_height < self.generator.margin_bottom:
                    self._handle_page_break(canvas, style)

                canvas.drawString(self.margin_x, self.generator.current_y, line)
                self.generator.current_y -= line_height
                lines_drawn += 1

        # Add spacing after text
        if lines_drawn > 0:
            self.generator.current_y -= style.spacing_after

    def _handle_page_break(self, canvas, style):
        """Handle page break and restore styling"""
        canvas.showPage()
        self.generator.current_page += 1
        self.generator.page_manager.initialize_page(canvas)
        # Reset font and color after page break
        canvas.setFont(style.font_name, style.font_size)
        canvas.setFillColor(style.color)

    def _draw_list_content(self, canvas, text, style, wrap_width, line_height):
        """Draw list content with proper bullet point or numbered formatting"""
        lines = text.split('\n')
        lines_drawn = 0

        for line in lines:
            line = line.strip()
            if not line:
                # Empty line - add some spacing for paragraph breaks
                self.generator.current_y -= line_height // 2
                continue

            # Check if this is a list item (bullet or numbered)
            is_bullet_item = line.startswith('•')
            is_numbered_item = re.match(r'^\d+\.\s', line)

            if is_bullet_item or is_numbered_item:
                # This is a list item
                if is_bullet_item:
                    marker_part = '• '
                    text_part = line[2:].strip()  # Remove bullet and leading space
                else:  # numbered item
                    # Extract the number and period (e.g., "1. ")
                    match = re.match(r'^(\d+\.\s)(.*)', line)
                    marker_part = match.group(1)
                    text_part = match.group(2)

                # Draw marker (bullet or number)
                canvas.drawString(self.margin_x, self.generator.current_y, marker_part)

                # Calculate indent for text after marker
                marker_width = canvas.stringWidth(marker_part, style.font_name, style.font_size)
                text_indent = self.margin_x + marker_width
                text_wrap_width = wrap_width - marker_width

                # Wrap the text part
                if text_part:
                    wrapped_text_lines = _wrap_text(text_part, text_wrap_width, style.font_size, style.font_name)

                    # Draw first line on same line as marker
                    if wrapped_text_lines:
                        canvas.drawString(text_indent, self.generator.current_y, wrapped_text_lines[0])
                        self.generator.current_y -= line_height
                        lines_drawn += 1

                        # Draw continuation lines with same indent
                        for wrapped_line in wrapped_text_lines[1:]:
                            canvas.drawString(text_indent, self.generator.current_y, wrapped_line)
                            self.generator.current_y -= line_height
                            lines_drawn += 1
                else:
                    # Just marker, no text
                    self.generator.current_y -= line_height
                    lines_drawn += 1
            else:
                # Regular paragraph text (not a list item)
                wrapped_lines = _wrap_text(line, wrap_width, style.font_size, style.font_name)
                for wrapped_line in wrapped_lines:
                    if wrapped_line.strip():
                        canvas.drawString(self.margin_x, self.generator.current_y, wrapped_line)
                        self.generator.current_y -= line_height
                        lines_drawn += 1

        # Add spacing after list
        if lines_drawn > 0:
            self.generator.current_y -= style.spacing_after

    def _draw_text_lines(self, canvas, wrapped_lines, line_height, tight=False):
        """Draw regular text lines"""
        lines_drawn = 0

        for line in wrapped_lines:
            if line.strip():
                canvas.drawString(self.margin_x, self.generator.current_y, line)
                self.generator.current_y -= line_height - (10 if tight else 0)
                lines_drawn += 1

        # Add spacing after text
        if lines_drawn > 0 and not tight:
            self.generator.current_y -= self.label_styles['p'].spacing_after if hasattr(self, 'label_styles') else 5
