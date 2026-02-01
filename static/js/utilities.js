// =====================================================================
// 3. UTILITIES
// =====================================================================
window.calculateTotalSeconds = function () {
	var modelValue = (modelEl ? modelEl.value : '').trim().toLowerCase();
	var secondsPerPage = MODEL_TIMING['default'];

	for (var _i = 0, _a = Object.entries(MODEL_TIMING); _i < _a.length; _i++) {
		var key = _a[_i][0], val = _a[_i][1];
		if (key !== 'default' && modelValue.includes(key)) {
			secondsPerPage = val;
			break;
		}
	}

	var pages = window.pdfPageCount || 1;
	var pdfCount = (window.selectedPdfs && window.selectedPdfs.length) || 1;
	// Each PDF has its own detect + analyze overhead
	return (secondsPerPage * pages) + (FIXED_OVERHEAD_SECONDS * pdfCount);
};
