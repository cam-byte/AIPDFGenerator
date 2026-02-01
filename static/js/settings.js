// =====================================================================
// 6. SETTINGS PANEL
// =====================================================================
(function () {
	function setBadgeConfigured(isConfigured) {
		if (!settingsBadge) return;
		settingsBadge.textContent = isConfigured ? 'Configured' : 'Missing';
		settingsBadge.className = 'settings-badge ' + (isConfigured ? 'ok' : 'missing');
	}

	function showFeedback(msg, ok) {
		if (!settingsFeedback) return;
		settingsFeedback.textContent = msg;
		settingsFeedback.className = 'settings-feedback show ' + (ok ? 'ok' : 'err');
		setTimeout(function () { settingsFeedback.classList.remove('show'); }, 2000);
	}

	window.toggleSettings = function () {
		if (settingsHeader) settingsHeader.classList.toggle('open');
		if (settingsBody) settingsBody.classList.toggle('open');
	};

	window.loadSettingsFromServer = function () {
		return fetch('/settings', { method: 'GET' })
			.then(function (res) {
				if (!res.ok) throw new Error('Failed to load settings');
				return res.json();
			})
			.then(function (data) {
				if (providerEl && data.provider) providerEl.value = data.provider;
				if (modelEl && data.model) modelEl.value = data.model;

				if (apiKeyEl) apiKeyEl.value = data.api_key_masked || '';
				setBadgeConfigured(!!data.has_key);
			})
			.catch(function (e) {
				console.error(e);
				setBadgeConfigured(false);
			});
	};

	window.saveSettings = function () {
		var payload = {
			provider: (providerEl && providerEl.value) || 'anthropic',
			model: ((modelEl && modelEl.value) || '').trim(),
			api_key: ((apiKeyEl && apiKeyEl.value) || '').trim(),
		};

		return fetch('/settings', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
		})
			.then(function (res) {
				if (!res.ok) {
					return res.json().catch(function () { return {}; }).then(function (err) {
						throw new Error(err.error || 'Failed to save settings');
					});
				}
				return res.json();
			})
			.then(function (data) {
				if (apiKeyEl && data.api_key_masked) apiKeyEl.value = data.api_key_masked;
				setBadgeConfigured(!!(apiKeyEl && apiKeyEl.value && apiKeyEl.value.trim()));
				showFeedback('Saved', true);
			})
			.catch(function (e) {
				console.error(e);
				showFeedback(e.message || 'Save failed', false);
				setBadgeConfigured(false);
			});
	};
})();
