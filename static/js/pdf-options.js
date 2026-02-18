// =====================================================================
// PDF OPTIONS — Granular style sliders + live preview
// =====================================================================
(function () {
	// Default values (~15% smaller than original built-ins, centered in ranges)
	var DEFAULTS = {
		h1_size: 13.5,
		h3_size: 10,
		h4_size: 8.5,
		p_size: 7.5,
		field_label_size: 7.5,
		check_radio_label_size: 7.5,
		input_height: 15,
		textarea_height: 42,
		checkbox_size: 9,
		field_spacing: 17,
		label_gap: 3,
		col_spacing: 17,
		group_row_height: 22,
		group_row_gap: 10,
		header_font_size: 8
	};

	// Presets as multipliers of defaults
	var PRESETS = {
		very_tight: 0.65,
		tight:   0.8,
		normal:  1.0,
		spacious: 1.2
	};

	// Slider configs: [min, max, step] — ranges centered around defaults
	var SLIDER_CONFIGS = {
		h1_size:          [8, 20, 0.5],
		h3_size:          [6, 16, 0.5],
		h4_size:          [5, 12, 0.5],
		p_size:           [5, 11, 0.5],
		field_label_size: [5, 11, 0.5],
		check_radio_label_size: [4, 11, 0.5],
		input_height:     [10, 24, 1],
		textarea_height:  [25, 65, 1],
		checkbox_size:    [6, 14, 1],
		field_spacing:    [6, 30, 1],
		label_gap:        [0, 8, 1],
		col_spacing:      [6, 30, 1],
		group_row_height: [10, 36, 1],
		group_row_gap:    [2, 20, 1],
		header_font_size: [6, 11, 0.5]
	};

	// Font family mapping for CSS
	var FONT_MAP = {
		'Helvetica': 'Helvetica, Arial, sans-serif',
		'Times': '"Times New Roman", Times, serif',
		'Courier': '"Courier New", Courier, monospace'
	};

	function getAllSliderKeys() {
		return Object.keys(DEFAULTS);
	}

	// Toggle the collapsible section
	window.togglePdfOptions = function () {
		var header = document.getElementById('pdfOptionsHeader');
		var body = document.getElementById('pdfOptionsBody');
		if (!header || !body) return;
		header.classList.toggle('open');
		body.classList.toggle('open');
	};

	// Apply a named preset
	window.applyPdfPreset = function (name) {
		var mult = PRESETS[name];
		if (mult == null) return;

		getAllSliderKeys().forEach(function (key) {
			var slider = document.getElementById('pdf_' + key);
			if (!slider) return;
			var cfg = SLIDER_CONFIGS[key];
			var raw = DEFAULTS[key] * mult;
			var val = Math.max(cfg[0], Math.min(cfg[1], raw));
			val = Math.round(val / cfg[2]) * cfg[2];
			slider.value = val;
		});

		document.querySelectorAll('.preset-btn').forEach(function (btn) {
			btn.classList.toggle('active', btn.dataset.preset === name);
		});

		updatePdfPreview();
	};

	// Read all slider values and update value displays + preview
	window.updatePdfPreview = function () {
		var vals = collectPdfOptions();

		// Update value displays next to sliders
		getAllSliderKeys().forEach(function (key) {
			var display = document.getElementById('pdf_' + key + '_val');
			if (display) {
				var v = vals[key];
				display.textContent = (v % 1 === 0) ? v : v.toFixed(1);
			}
		});

		// --- Update preview pages ---
		var pages = document.querySelectorAll('.pdf-page');
		if (!pages.length) return;

		var fontVal = vals.font_family || 'Helvetica';
		var cssFont = FONT_MAP[fontVal] || FONT_MAP['Helvetica'];

		// Apply font to all pages
		pages.forEach(function (page) { page.style.fontFamily = cssFont; });

		// H1, H3, H4, P (querySelectorAll across all pages)
		var container = document.getElementById('pdfPreviewPanel');
		if (!container) return;

		container.querySelectorAll('.prev-h1').forEach(function (el) { el.style.fontSize = vals.h1_size + 'px'; });
		container.querySelectorAll('.prev-h3').forEach(function (el) { el.style.fontSize = vals.h3_size + 'px'; });
		container.querySelectorAll('.prev-h4').forEach(function (el) { el.style.fontSize = vals.h4_size + 'px'; });
		container.querySelectorAll('.prev-p').forEach(function (el) { el.style.fontSize = vals.p_size + 'px'; });
		container.querySelectorAll('.prev-label').forEach(function (el) {
			el.style.fontSize = vals.field_label_size + 'px';
			el.style.marginBottom = vals.label_gap + 'px';
		});
		container.querySelectorAll('.prev-input').forEach(function (el) { el.style.height = vals.input_height + 'px'; });
		container.querySelectorAll('.prev-textarea').forEach(function (el) { el.style.height = vals.textarea_height + 'px'; });
		container.querySelectorAll('.prev-checkbox').forEach(function (el) {
			el.style.width = vals.checkbox_size + 'px';
			el.style.height = vals.checkbox_size + 'px';
		});
		container.querySelectorAll('.prev-check-label').forEach(function (el) {
			el.style.fontSize = vals.check_radio_label_size + 'px';
		});

		// Field spacing
		container.querySelectorAll('.prev-field').forEach(function (el) {
			el.style.marginBottom = vals.field_spacing + 'px';
		});

		// Column gaps
		container.querySelectorAll('.prev-row-2col, .prev-row-3col, .prev-row-4col').forEach(function (el) {
			el.style.columnGap = vals.col_spacing + 'px';
			el.style.rowGap = vals.group_row_gap + 'px';
		});

		// Header font size
		container.querySelectorAll('.prev-header-text').forEach(function (el) {
			el.style.fontSize = vals.header_font_size + 'px';
		});

		// Preset matching
		var matchedPreset = null;
		Object.keys(PRESETS).forEach(function (name) {
			var mult = PRESETS[name];
			var matches = true;
			getAllSliderKeys().forEach(function (key) {
				var cfg = SLIDER_CONFIGS[key];
				var expected = Math.max(cfg[0], Math.min(cfg[1], DEFAULTS[key] * mult));
				expected = Math.round(expected / cfg[2]) * cfg[2];
				if (Math.abs(vals[key] - expected) > 0.01) matches = false;
			});
			if (matches) matchedPreset = name;
		});
		document.querySelectorAll('.preset-btn').forEach(function (btn) {
			btn.classList.toggle('active', btn.dataset.preset === matchedPreset);
		});
	};

	// Collect all slider values as a dict (called by form-submit.js)
	window.collectPdfOptions = function () {
		var result = {};
		getAllSliderKeys().forEach(function (key) {
			var slider = document.getElementById('pdf_' + key);
			result[key] = slider ? parseFloat(slider.value) : DEFAULTS[key];
		});
		var fontSel = document.getElementById('pdf_font_family');
		result.font_family = fontSel ? fontSel.value : 'Helvetica';
		return result;
	};

	// Initialize on DOM ready
	document.addEventListener('DOMContentLoaded', function () {
		getAllSliderKeys().forEach(function (key) {
			var slider = document.getElementById('pdf_' + key);
			if (slider) {
				slider.value = DEFAULTS[key];
				slider.addEventListener('input', updatePdfPreview);
			}
		});
		// Font dropdown also triggers preview
		var fontSel = document.getElementById('pdf_font_family');
		if (fontSel) fontSel.addEventListener('change', updatePdfPreview);

		updatePdfPreview();
		document.querySelectorAll('.preset-btn').forEach(function (btn) {
			btn.classList.toggle('active', btn.dataset.preset === 'normal');
		});
	});
})();
