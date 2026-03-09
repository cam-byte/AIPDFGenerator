// =====================================================================
// 9. FORM SUBMISSION (supports single + batch + regenerate from JSON)
// =====================================================================
(function () {
	function collectLocations() {
		var rows = document.querySelectorAll('#locations .location-row');
		var locations = [];
		rows.forEach(function (row) {
			var streetEl = row.querySelector('[data-field="street"]');
			var cityEl = row.querySelector('[data-field="city_state_zip"]');
			var phoneEl = row.querySelector('[data-field="phone"]');
			var street = (streetEl && streetEl.value) ? streetEl.value.trim() : '';
			var city_state_zip = (cityEl && cityEl.value) ? cityEl.value.trim() : '';
			var phone = (phoneEl && phoneEl.value) ? phoneEl.value.trim() : '';
			if (street || city_state_zip || phone) {
				locations.push({ street: street, city_state_zip: city_state_zip, phone: phone });
			}
		});
		return locations;
	}

	function showResult(ok, msg) {
		if (!resultEl || !resultMsg) return;
		resultEl.classList.add('visible');
		resultEl.classList.toggle('success', ok);
		resultEl.classList.toggle('error', !ok);
		resultMsg.textContent = msg;
	}

	form.addEventListener('submit', function (e) {
		e.preventDefault();

		var isRegenerate = window.currentMode === 'regenerate';

		var fd = new FormData();
		var businessNameEl = document.getElementById('business_name');
		fd.append('business_name', (businessNameEl && businessNameEl.value) || '');

		var logoFile = document.getElementById('logo');
		if (logoFile && logoFile.files && logoFile.files[0]) {
			fd.append('logo', logoFile.files[0]);
		}

		fd.append('locations', JSON.stringify(collectLocations()));

		var sepEl = document.getElementById('separate_locations');
		fd.append('separate_locations', sepEl && sepEl.checked ? '1' : '0');

		fd.append('pdf_options', JSON.stringify(typeof collectPdfOptions === 'function' ? collectPdfOptions() : {}));

		if (isRegenerate) {
			// Regenerate mode: require JSON files
			if (!window.selectedJsons || window.selectedJsons.length === 0) {
				showResult(false, 'Please upload at least one JSON file.');
				return;
			}
			for (var j = 0; j < window.selectedJsons.length; j++) {
				fd.append('json', window.selectedJsons[j]);
			}
		} else {
			// Upload mode: require PDF files
			if (!window.selectedPdfs || window.selectedPdfs.length === 0) {
				showResult(false, 'Please upload at least one PDF or image.');
				return;
			}
			for (var i = 0; i < window.selectedPdfs.length; i++) {
				fd.append('pdf', window.selectedPdfs[i]);
			}
		}

		// Clear old result
		resultEl.classList.remove('visible', 'success', 'error');
		resultMsg.textContent = '';

		// Start progress timer (regenerate is fast — use short estimate)
		var totalSec = isRegenerate ? 5 : calculateTotalSeconds();
		var fileCount = isRegenerate ? window.selectedJsons.length : window.selectedPdfs.length;
		var timer = new ProgressTimer(submitBtn, totalSec, window.pdfPageCount || 1, fileCount);
		timer.start();

		var endpoint = isRegenerate ? '/regenerate' : '/process';

		fetch(endpoint, { method: 'POST', body: fd })
			.then(function (res) {
				if (!res.ok) {
					return res.json().catch(function () { return null; }).then(function (data) {
						throw new Error((data && data.error) || 'Request failed (' + res.status + ')');
					});
				}
				return res.blob().then(function (blob) {
					// Derive filename from Content-Disposition or fall back to type
					var disposition = res.headers.get('Content-Disposition') || '';
					var match = disposition.match(/filename="?([^";\n]+)"?/);
					var filename = match ? match[1] : (blob.type === 'application/pdf' ? 'output.pdf' : 'output.zip');
					return { blob: blob, filename: filename };
				});
			})
			.then(function (result) {
				var url = URL.createObjectURL(result.blob);

				var a = document.createElement('a');
				a.href = url;
				a.download = result.filename;
				document.body.appendChild(a);
				a.click();
				a.remove();

				setTimeout(function () { URL.revokeObjectURL(url); }, 5000);

				timer.complete(true);
				showResult(true, 'Done. Download should start automatically.');
			})
			.catch(function (err) {
				console.error(err);
				timer.complete(false);
				showResult(false, err.message || 'Failed');
			});
	});
})();
