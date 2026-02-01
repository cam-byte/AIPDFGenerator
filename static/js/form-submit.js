// =====================================================================
// 9. FORM SUBMISSION (supports single + batch)
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

		var fd = new FormData();
		var businessNameEl = document.getElementById('business_name');
		fd.append('business_name', (businessNameEl && businessNameEl.value) || '');

		var logoFile = document.getElementById('logo');
		if (logoFile && logoFile.files && logoFile.files[0]) {
			fd.append('logo', logoFile.files[0]);
		}

		fd.append('locations', JSON.stringify(collectLocations()));

		if (!window.selectedPdfs || window.selectedPdfs.length === 0) {
			showResult(false, 'Please upload at least one PDF.');
			return;
		}

		// Append every selected PDF under the same field name
		for (var i = 0; i < window.selectedPdfs.length; i++) {
			fd.append('pdf', window.selectedPdfs[i]);
		}

		// Clear old result
		resultEl.classList.remove('visible', 'success', 'error');
		resultMsg.textContent = '';

		// Start progress timer
		var totalSec = calculateTotalSeconds();
		var pdfCount = window.selectedPdfs.length;
		var timer = new ProgressTimer(submitBtn, totalSec, window.pdfPageCount || 1, pdfCount);
		timer.start();

		fetch('/process', { method: 'POST', body: fd })
			.then(function (res) {
				if (!res.ok) {
					return res.json().catch(function () { return null; }).then(function (data) {
						throw new Error((data && data.error) || 'Request failed (' + res.status + ')');
					});
				}
				return res.blob();
			})
			.then(function (blob) {
				var url = URL.createObjectURL(blob);

				var a = document.createElement('a');
				a.href = url;
				a.download = 'output.zip';
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
