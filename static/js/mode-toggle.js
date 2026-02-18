// =====================================================================
// MODE TOGGLE — switch between "Upload PDF" and "Regenerate from JSON"
// =====================================================================
(function () {
	window.selectedJsons = [];
	window.currentMode = 'upload';

	var modeSelect = document.getElementById('modeSelect');
	var settingsSection = document.getElementById('settingsSection');
	var pdfUploadSection = document.getElementById('pdfUploadSection');
	var jsonUploadSection = document.getElementById('jsonUploadSection');
	var submitBtn = document.getElementById('submitBtn');
	var btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;

	// JSON dropzone elements
	var jsonDropzone = document.getElementById('jsonDropzone');
	var jsonInput = document.getElementById('jsonInput');
	var jsonCount = document.getElementById('jsonCount');
	var jsonPreviewWrap = document.getElementById('jsonPreviewWrap');
	var jsonPreviewList = document.getElementById('jsonPreviewList');
	var clearAllJsonBtn = document.getElementById('clearAllJsonBtn');

	if (!modeSelect) return;

	modeSelect.addEventListener('change', function () {
		window.currentMode = modeSelect.value;

		if (modeSelect.value === 'regenerate') {
			settingsSection.style.display = 'none';
			pdfUploadSection.style.display = 'none';
			jsonUploadSection.style.display = '';
			if (btnText) btnText.textContent = 'Regenerate PDF';
		} else {
			settingsSection.style.display = '';
			pdfUploadSection.style.display = '';
			jsonUploadSection.style.display = 'none';
			if (btnText) btnText.textContent = 'Process PDF';
		}
	});

	// --- JSON file handling ---
	function renderJsonPreviews() {
		if (!jsonPreviewList) return;
		jsonPreviewList.innerHTML = '';

		if (window.selectedJsons.length === 0) {
			jsonPreviewWrap.style.display = 'none';
			jsonCount.textContent = '';
			return;
		}

		jsonPreviewWrap.style.display = '';
		jsonCount.textContent = window.selectedJsons.length + ' file' + (window.selectedJsons.length > 1 ? 's' : '') + ' selected';

		window.selectedJsons.forEach(function (file, idx) {
			var card = document.createElement('div');
			card.className = 'pdf-preview-card';
			card.style.gridTemplateColumns = '1fr 28px';

			var meta = document.createElement('div');
			meta.className = 'pdf-preview-meta';

			var nameEl = document.createElement('div');
			nameEl.className = 'name';
			nameEl.textContent = file.name;

			var infoEl = document.createElement('div');
			infoEl.className = 'info';
			infoEl.textContent = (file.size / 1024).toFixed(1) + ' KB';

			meta.appendChild(nameEl);
			meta.appendChild(infoEl);

			var removeBtn = document.createElement('button');
			removeBtn.type = 'button';
			removeBtn.className = 'btn-remove-pdf';
			removeBtn.title = 'Remove';
			removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
			removeBtn.addEventListener('click', function () {
				window.selectedJsons.splice(idx, 1);
				renderJsonPreviews();
			});

			card.appendChild(meta);
			card.appendChild(removeBtn);
			jsonPreviewList.appendChild(card);
		});

		if (window.selectedJsons.length > 3) {
			jsonPreviewList.classList.add('scrollable');
		} else {
			jsonPreviewList.classList.remove('scrollable');
		}
	}

	function addJsonFiles(files) {
		for (var i = 0; i < files.length; i++) {
			var file = files[i];
			if (file.name.toLowerCase().endsWith('.json')) {
				window.selectedJsons.push(file);
			}
		}
		renderJsonPreviews();
	}

	if (jsonInput) {
		jsonInput.addEventListener('change', function () {
			if (jsonInput.files && jsonInput.files.length) {
				addJsonFiles(jsonInput.files);
				jsonInput.value = '';
			}
		});
	}

	if (jsonDropzone) {
		jsonDropzone.addEventListener('dragover', function (e) {
			e.preventDefault();
			jsonDropzone.classList.add('dragover');
		});
		jsonDropzone.addEventListener('dragleave', function () {
			jsonDropzone.classList.remove('dragover');
		});
		jsonDropzone.addEventListener('drop', function (e) {
			e.preventDefault();
			jsonDropzone.classList.remove('dragover');
			if (e.dataTransfer && e.dataTransfer.files) {
				addJsonFiles(e.dataTransfer.files);
			}
		});
	}

	if (clearAllJsonBtn) {
		clearAllJsonBtn.addEventListener('click', function () {
			window.selectedJsons = [];
			renderJsonPreviews();
		});
	}
})();
