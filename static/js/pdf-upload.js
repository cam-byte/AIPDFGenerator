// =====================================================================
// 5. PDF UPLOAD & PREVIEW
// =====================================================================
(function () {
	window.selectedPdfs = [];
	window.pdfPageCount = 0;
	var pdfObjectUrls = [];

	// Configure PDF.js worker
	if (window.pdfjsLib) {
		pdfjsLib.GlobalWorkerOptions.workerSrc =
			'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.4.120/legacy/build/pdf.worker.min.js';
	}

	function showPdfError(msg) {
		pdfPreviewErr.textContent = msg;
		pdfPreviewErr.style.display = 'block';
	}

	function clearPdfError() {
		pdfPreviewErr.textContent = '';
		pdfPreviewErr.style.display = 'none';
	}

	function cleanupPdfObjectUrls() {
		for (var i = 0; i < pdfObjectUrls.length; i++) {
			try { URL.revokeObjectURL(pdfObjectUrls[i]); } catch (e) { }
		}
		pdfObjectUrls = [];
	}

	function updateDropzoneCount() {
		var count = window.selectedPdfs.length;
		if (count > 0) {
			var pdfCount = window.selectedPdfs.filter(isPdfFile).length;
			var imgCount = window.selectedPdfs.filter(isImageFile).length;
			var parts = [];
			if (pdfCount > 0) parts.push(pdfCount + ' PDF' + (pdfCount === 1 ? '' : 's'));
			if (imgCount > 0) parts.push(imgCount + ' image' + (imgCount === 1 ? '' : 's'));
			pdfCountEl.textContent = parts.join(', ');
			pdfCountEl.style.display = '';
		} else {
			pdfCountEl.textContent = '';
			pdfCountEl.style.display = 'none';
		}
	}

	function clearSelectedPdfs() {
		window.selectedPdfs = [];
		window.pdfPageCount = 0;
		pdfInput.value = '';

		updateDropzoneCount();

		cleanupPdfObjectUrls();
		pdfPreviewList.innerHTML = '';
		pdfPreviewList.classList.remove('scrollable');
		pdfPreviewWrap.style.display = 'none';
		clearPdfError();
	}

	function isPdfFile(file) {
		return file && (
			file.type === 'application/pdf' ||
			file.name.toLowerCase().endsWith('.pdf')
		);
	}

	var IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif'];
	function isImageFile(file) {
		if (!file) return false;
		var name = file.name.toLowerCase();
		return IMAGE_EXTENSIONS.some(function (ext) { return name.endsWith(ext); });
	}

	function renderPdfPage1ToCanvas(file, canvas, targetWidth) {
		if (!window.pdfjsLib) return Promise.reject(new Error('PDF.js not loaded'));

		var objectUrl = URL.createObjectURL(file);
		pdfObjectUrls.push(objectUrl);

		var loadingTask = pdfjsLib.getDocument(objectUrl);
		return loadingTask.promise.then(function (pdf) {
			return pdf.getPage(1).then(function (page) {
				var viewport1 = page.getViewport({ scale: 1 });
				var scale = targetWidth / viewport1.width;
				var viewport = page.getViewport({ scale: scale });

				var ctx = canvas.getContext('2d', { alpha: false });
				canvas.width = Math.floor(viewport.width);
				canvas.height = Math.floor(viewport.height);

				ctx.clearRect(0, 0, canvas.width, canvas.height);
				return page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
					return { numPages: pdf.numPages };
				});
			});
		});
	}

	function buildPdfPreviewCards() {
		clearPdfError();
		pdfPreviewList.innerHTML = '';

		if (!window.selectedPdfs.length) {
			pdfPreviewWrap.style.display = 'none';
			return Promise.resolve();
		}

		if (!window.pdfjsLib && window.selectedPdfs.some(isPdfFile)) {
			showPdfError('PDF preview unavailable: PDF.js failed to load.');
			pdfPreviewWrap.style.display = 'block';
			return Promise.resolve();
		}

		// Scrollable once more than 3 PDFs
		if (window.selectedPdfs.length > 3) {
			pdfPreviewList.classList.add('scrollable');
		} else {
			pdfPreviewList.classList.remove('scrollable');
		}

		pdfPreviewWrap.style.display = 'block';

		var totalPages = 0;
		var chain = Promise.resolve();
		var THUMB_WIDTH = 80;

		window.selectedPdfs.forEach(function (file) {
			chain = chain.then(function () {
				var card = document.createElement('div');
				card.className = 'pdf-preview-card';

				var meta = document.createElement('div');
				meta.className = 'pdf-preview-meta';

				var name = document.createElement('div');
				name.className = 'name';
				name.textContent = file.name;

				var info = document.createElement('div');
				info.className = 'info';

				var removeBtn = document.createElement('button');
				removeBtn.type = 'button';
				removeBtn.className = 'btn-remove-pdf';
				removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
				removeBtn.title = 'Remove';

				removeBtn.addEventListener('click', function () {
					window.selectedPdfs = window.selectedPdfs.filter(function (f) { return f !== file; });
					updateDropzoneCount();

					if (window.selectedPdfs.length === 0) {
						clearSelectedPdfs();
						return;
					}

					cleanupPdfObjectUrls();
					buildPdfPreviewCards();
				});

				meta.appendChild(name);
				meta.appendChild(info);

				if (isImageFile(file)) {
					// Image preview using <img> tag
					var thumb = document.createElement('img');
					thumb.className = 'pdf-preview-canvas';
					thumb.style.objectFit = 'contain';
					thumb.alt = file.name;

					var objUrl = URL.createObjectURL(file);
					pdfObjectUrls.push(objUrl);
					thumb.src = objUrl;

					var kb = Math.round(file.size / 1024);
					info.textContent = kb + ' KB \u2022 image';
					totalPages += 1;

					card.appendChild(thumb);
					card.appendChild(meta);
					card.appendChild(removeBtn);
					pdfPreviewList.appendChild(card);

					return Promise.resolve();
				} else {
					// PDF preview using PDF.js canvas
					var canvas = document.createElement('canvas');
					canvas.className = 'pdf-preview-canvas';
					info.textContent = 'Rendering\u2026';

					card.appendChild(canvas);
					card.appendChild(meta);
					card.appendChild(removeBtn);
					pdfPreviewList.appendChild(card);

					return renderPdfPage1ToCanvas(file, canvas, THUMB_WIDTH).then(function (result) {
						totalPages += result.numPages;
						var kb = Math.round(file.size / 1024);
						info.textContent = kb + ' KB \u2022 ' + result.numPages + ' pg' + (result.numPages === 1 ? '' : 's');
					}).catch(function (err) {
						console.error(err);
						info.textContent = 'Preview failed';
					});
				}
			});
		});

		return chain.then(function () {
			window.pdfPageCount = totalPages;
		});
	}

	function addPdfs(fileList) {
		var newFiles = Array.from(fileList || []).filter(function (f) {
			return isPdfFile(f) || isImageFile(f);
		});

		if (!fileList || fileList.length === 0) return;

		if (newFiles.length === 0) {
			showPdfError('Please select PDF or image file(s).');
			pdfPreviewWrap.style.display = 'block';
			return;
		}

		// Dedupe by name+size to avoid adding the same file twice
		var existing = {};
		window.selectedPdfs.forEach(function (f) {
			existing[f.name + '|' + f.size] = true;
		});

		newFiles.forEach(function (f) {
			var key = f.name + '|' + f.size;
			if (!existing[key]) {
				window.selectedPdfs.push(f);
				existing[key] = true;
			}
		});

		updateDropzoneCount();
		cleanupPdfObjectUrls();
		buildPdfPreviewCards();
	}

	// Drag UI states
	dropzone.addEventListener('dragover', function (e) {
		e.preventDefault();
		dropzone.classList.add('dragover');
	});

	dropzone.addEventListener('dragleave', function () {
		dropzone.classList.remove('dragover');
	});

	dropzone.addEventListener('drop', function (e) {
		e.preventDefault();
		dropzone.classList.remove('dragover');
		addPdfs(e.dataTransfer.files);
	});

	pdfInput.addEventListener('change', function () {
		addPdfs(pdfInput.files);
		// Reset so the same file(s) can be re-selected
		pdfInput.value = '';
	});

	clearAllPdfsBtn.addEventListener('click', clearSelectedPdfs);
})();
