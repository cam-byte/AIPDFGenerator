// =====================================================================
// 10. JSON BACKGROUND ANIMATION
// =====================================================================
(function () {
	var jsonSnippets = [
		'{\n' +
		'    "dental_patient_intake_v2": {\n' +
		'        "settings": {},\n' +
		'        "content": {\n' +
		'            "dental_patient_intake_v2": {\n' +
		'                "form_name": "dental_patient_intake_v2",\n' +
		'                "submission_url": "...",\n' +
		'                "subject": "Form Submission: Patient Intake Form",\n' +
		'                "confirmation": "thankyouhtml",\n' +
		'                "pdf": "pdf",\n' +
		'                "category": "Patient Intake (Dental)",\n' +
		'                "type": "intake",\n' +
		'                "fields": [\n' +
		'                    {\n' +
		'                        "name": "pdf_download",\n' +
		'                        "label": "<i class=\\"fad fa-file-download\\"></i>Download Printable Version",\n' +
		'                        "type": "pdf_download"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "form_container",\n' +
		'                        "type": "group_start"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "form_header",\n' +
		'                        "label": "<h1>Patient Intake Form</h1>",\n' +
		'                        "type": "label"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "form_content_container",\n' +
		'                        "type": "group_start"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "email_address",\n' +
		'                        "label": "Email Address",\n' +
		'                        "email_label": "Email Address",\n' +
		'                        "type": "email",\n' +
		'                        "required": false\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "todays_date",\n' +
		'                        "label": "Today\'s Date",\n' +
		'                        "email_label": "Today\'s Date",\n' +
		'                        "type": "date",\n' +
		'                        "required": true\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "content",\n' +
		'                        "label": "<p>As required by law, our office adheres to written policies and procedures to protect the privacy of information about you that we create, receive, or maintain. Your answers are for our records only and will be kept confidential subject to applicable laws. Please note that you will be asked some questions about your responses to this questionnaire and there may be additional questions concerning your health. This information is vital to allow us to provide appropriate care for you. This office does not use this information to discriminate.</p>",\n' +
		'                        "type": "label"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "",\n' +
		'                        "label": "<h3>Patient Information</h3>",\n' +
		'                        "type": "label"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "*name_details",\n' +
		'                        "type": "group_start"\n' +
		'                    },\n' +
		'                    {\n' +
		'                        "name": "first",\n' +
		'                        "label": "First Name",\n' +
		'                        "email_label": "First Name",\n' +
		'                        "type": "text",\n' +
		'                        "required": true\n' +
		'                    }'
	];

	function normalizeIndent(str, spaces) {
		var lines = str.trimStart().split('\n');
		var indents = [];
		for (var i = 1; i < lines.length; i++) {
			if (lines[i].trim().length) {
				var match = lines[i].match(/^(\s*)/);
				indents.push(match ? match[1].length : 0);
			}
		}

		var minIndent = indents.length ? Math.min.apply(null, indents) : 0;

		return lines
			.map(function (line, i) {
				if (i === 0) return line.trimEnd();
				var cut = (minIndent === 0) ? line.trimEnd() : line.slice(minIndent).trimEnd();
				var pad = '';
				for (var s = 0; s < spaces; s++) pad += ' ';
				return pad + cut;
			})
			.join('\n');
	}

	function createTypingColumn(el, snippets, options) {
		if (!el) return function () { };

		options = options || {};
		var startDelay = options.startDelay || 0;
		var typeMin = options.typeMin || 20;
		var typeJitter = options.typeJitter || 35;
		var deleteSpeed = options.deleteSpeed || 10;
		var donePause = options.donePause || 1800;

		var currentSnippet = 0;
		var displayed = '';
		var isDeleting = false;
		var isPaused = true;
		var t = null;

		function clearTimer() {
			if (t) {
				clearTimeout(t);
				t = null;
			}
		}

		function tick() {
			if (isPaused) return;

			var full = normalizeIndent(snippets[currentSnippet], 4);

			if (!isDeleting) {
				if (displayed.length < full.length) {
					displayed = full.slice(0, displayed.length + 1);
					el.textContent = displayed;

					var speed = typeMin + Math.random() * typeJitter;
					t = setTimeout(tick, speed);
				} else {
					t = setTimeout(function () {
						isDeleting = true;
						tick();
					}, donePause);
				}
			} else {
				if (displayed.length > 0) {
					displayed = displayed.slice(0, -1);
					el.textContent = displayed;
					t = setTimeout(tick, deleteSpeed);
				} else {
					isDeleting = false;
					currentSnippet = (currentSnippet + 1) % snippets.length;
					t = setTimeout(tick, 200);
				}
			}
		}

		// Reduced motion: show static
		if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
			el.textContent = normalizeIndent(snippets[0], 4);
			return function () { };
		}

		setTimeout(function () {
			isPaused = false;
			tick();
		}, startDelay);

		return function () { clearTimer(); };
	}

	var leftEl = document.getElementById('jsonLeft');
	var rightEl = document.getElementById('jsonRight');

	createTypingColumn(leftEl, jsonSnippets.slice(0, 3), { startDelay: 0 });

	if (rightEl) {
		createTypingColumn(rightEl, jsonSnippets.slice(1, 3), { startDelay: 1800 });
	}
})();
