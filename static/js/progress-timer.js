// =====================================================================
// 8. PROGRESS TIMER
// =====================================================================
window.ProgressTimer = (function () {
	function ProgressTimer(button, totalSeconds, pageCount, pdfCount) {
		this.button = button;
		this.btnText = button.querySelector('.btn-text');
		this.totalMs = totalSeconds * 1000;
		this.pageCount = pageCount || 1;
		this.pdfCount = pdfCount || 1;
		this.elapsed = 0;
		this.interval = null;
		this.done = false;
	}

	ProgressTimer.prototype.start = function () {
		var self = this;
		this.elapsed = 0;
		this.done = false;
		this.button.disabled = true;
		this.button.classList.add('processing');
		this.button.style.setProperty('--progress', '0%');

		if (this.btnText) this.btnText.textContent = 'Detecting form type...';

		var TICK = 200;
		this.interval = setInterval(function () {
			self.elapsed += TICK;
			var rawPct = (self.elapsed / self.totalMs) * 100;
			var pct = Math.min(rawPct, 95);

			self.button.style.setProperty('--progress', pct + '%');
			self._updateStageText(pct);
		}, TICK);
	};

	ProgressTimer.prototype._updateStageText = function (pct) {
		if (!this.btnText || this.done) return;
		var batch = this.pdfCount > 1;

		if (pct < 10) {
			this.btnText.textContent = batch
				? 'Processing ' + this.pdfCount + ' PDFs \u2014 detecting form types...'
				: 'Detecting form type...';
		} else if (pct < 75) {
			var range = 75 - 10;
			var posInRange = pct - 10;
			if (batch) {
				var pdfIndex = Math.min(
					Math.floor((posInRange / range) * this.pdfCount),
					this.pdfCount - 1
				);
				this.btnText.textContent = 'Analyzing PDF ' + (pdfIndex + 1) + ' of ' + this.pdfCount + '...';
			} else {
				var pageIndex = Math.min(
					Math.floor((posInRange / range) * this.pageCount),
					this.pageCount - 1
				);
				this.btnText.textContent = 'Analyzing page ' + (pageIndex + 1) + ' of ' + this.pageCount + '...';
			}
		} else if (pct < 92) {
			this.btnText.textContent = batch ? 'Generating PDFs...' : 'Generating PDF...';
		} else {
			this.btnText.textContent = 'Finalizing...';
		}
	};

	ProgressTimer.prototype.complete = function (success) {
		if (this.done) return;
		this.done = true;

		if (this.interval) {
			clearInterval(this.interval);
			this.interval = null;
		}

		this.button.style.setProperty('--progress', '100%');
		this.button.classList.remove('processing');

		if (success) {
			this.button.classList.add('complete');
			if (this.btnText) this.btnText.textContent = 'Done!';
		} else {
			this.button.classList.add('error-flash');
			if (this.btnText) this.btnText.textContent = 'Error';
		}

		var self = this;
		setTimeout(function () { self._reset(); }, 2000);
	};

	ProgressTimer.prototype._reset = function () {
		this.button.style.setProperty('--progress', '0%');
		this.button.disabled = false;
		this.button.classList.remove('processing', 'complete', 'error-flash');
		if (this.btnText) this.btnText.textContent = 'Process PDF';
	};

	return ProgressTimer;
})();
