// =====================================================================
// 4. LOGO PREVIEW
// =====================================================================
(function () {
	var logoObjectUrl = null;

	function clearLogo() {
		logoInput.value = '';
		logoPreviewImg.src = '';
		logoPreviewName.textContent = '';
		logoPreviewMeta.textContent = '';
		logoPreviewWrap.style.display = 'none';

		if (logoObjectUrl) {
			URL.revokeObjectURL(logoObjectUrl);
			logoObjectUrl = null;
		}
	}

	function setLogo(file) {
		if (!file) return clearLogo();

		var isImage = file.type.startsWith('image/');
		if (!isImage) return clearLogo();

		if (logoObjectUrl) URL.revokeObjectURL(logoObjectUrl);
		logoObjectUrl = URL.createObjectURL(file);

		logoPreviewImg.src = logoObjectUrl;
		logoPreviewName.textContent = file.name;

		var kb = Math.round(file.size / 1024);
		var type = file.type || 'image';
		logoPreviewMeta.textContent = type + ' \u2022 ' + kb + ' KB';

		logoPreviewWrap.style.display = 'block';
	}

	if (logoInput) {
		logoInput.addEventListener('change', function () {
			var file = logoInput.files && logoInput.files[0];
			setLogo(file);
		});
	}

	if (clearLogoBtn) clearLogoBtn.addEventListener('click', clearLogo);
})();
