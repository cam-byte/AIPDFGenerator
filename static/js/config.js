// =====================================================================
// 1. CONFIGURATION
// =====================================================================
window.MODEL_TIMING = {
	'claude-opus-4':      45,
	'claude-sonnet-4':    25,
	'claude-sonnet-3.5':  20,
	'claude-haiku':       10,
	'default':            25,
};
window.FIXED_OVERHEAD_SECONDS = 8;

// =====================================================================
// 2. DOM REFERENCES
// =====================================================================
window.logoInput        = document.getElementById('logo');
window.logoPreviewWrap  = document.getElementById('logoPreviewWrap');
window.logoPreviewImg   = document.getElementById('logoPreviewImg');
window.logoPreviewName  = document.getElementById('logoPreviewName');
window.logoPreviewMeta  = document.getElementById('logoPreviewMeta');
window.clearLogoBtn     = document.getElementById('clearLogoBtn');

window.dropzone           = document.getElementById('dropzone');
window.pdfInput           = document.getElementById('pdfInput');
window.pdfCountEl         = document.getElementById('pdfCount');
window.pdfPreviewWrap     = document.getElementById('pdfPreviewWrap');
window.pdfPreviewList     = document.getElementById('pdfPreviewList');
window.pdfPreviewErr      = document.getElementById('pdfPreviewErr');
window.clearAllPdfsBtn    = document.getElementById('clearAllPdfsBtn');

window.settingsHeader   = document.getElementById('settingsHeader');
window.settingsBody     = document.getElementById('settingsBody');
window.settingsBadge    = document.getElementById('settingsBadge');
window.settingsFeedback = document.getElementById('settingsFeedback');
window.providerEl       = document.getElementById('provider');
window.modelEl          = document.getElementById('model');
window.apiKeyEl         = document.getElementById('api_key');

window.form      = document.getElementById('mainForm');
window.resultEl  = document.getElementById('result');
window.resultMsg = document.getElementById('resultMessage');
window.submitBtn = document.getElementById('submitBtn');
window.btnText   = submitBtn ? submitBtn.querySelector('.btn-text') : null;
