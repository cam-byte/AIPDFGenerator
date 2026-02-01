// =====================================================================
// 7. LOCATIONS
// =====================================================================
window.addLocation = function () {
	var locations = document.getElementById('locations');
	var row = document.createElement('div');
	row.className = 'location-row';
	row.innerHTML =
		'<input type="text" placeholder="123 Main St" data-field="street">' +
		'<input type="text" placeholder="Austin, TX 78701" data-field="city_state_zip">' +
		'<input type="text" placeholder="(512) 555-0100" data-field="phone">' +
		'<button type="button" class="btn-remove" onclick="removeLocation(this)" title="Remove">' +
		'<i class="fa-solid fa-xmark"></i>' +
		'</button>';
	locations.appendChild(row);
};

window.removeLocation = function (btn) {
	var row = btn.closest('.location-row');
	if (row) row.remove();
};
