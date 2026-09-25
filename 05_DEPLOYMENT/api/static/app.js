(() => {
  const fileInput = document.querySelector('#file-input');
  const fileLabel = document.querySelector('#file-label-text');
  const tokenInput = document.querySelector('#api-token');
  const analyzeButton = document.querySelector('#analyze-button');
  const resetButton = document.querySelector('#reset-button');
  const downloadButton = document.querySelector('#download-button');
  const status = document.querySelector('#status');
  const canvas = document.querySelector('#slide-canvas');
  const context = canvas.getContext('2d');
  const emptyState = document.querySelector('#empty-state');
  const results = document.querySelector('#results');
  let selectedFile = null;
  let image = null;
  let lastResult = null;

  function headers(extra = {}) {
    const token = tokenInput.value.trim();
    return token ? { ...extra, 'X-API-Key': token } : extra;
  }

  function setStatus(message, state = '') {
    status.textContent = message;
    status.dataset.state = state;
  }

  function reset() {
    selectedFile = null;
    image = null;
    lastResult = null;
    fileInput.value = '';
    fileLabel.textContent = 'Choose a de-identified microscopy image';
    analyzeButton.disabled = true;
    results.dataset.visible = 'false';
    canvas.hidden = true;
    emptyState.hidden = false;
    context.clearRect(0, 0, canvas.width, canvas.height);
    setStatus('Choose an image to begin.');
  }

  function drawImageAndBoxes(detections = []) {
    if (!image) return;
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    context.drawImage(image, 0, 0);
    context.lineWidth = Math.max(2, image.naturalWidth / 700);
    context.strokeStyle = '#b42318';
    detections.forEach((detection) => {
      const [cx, cy, width, height] = detection.bbox;
      context.strokeRect(cx - width / 2, cy - height / 2, width, height);
    });
    canvas.hidden = false;
    emptyState.hidden = true;
  }

  async function loadPreview(file) {
    const url = URL.createObjectURL(file);
    const preview = new Image();
    try {
      await new Promise((resolve, reject) => {
        preview.onload = resolve;
        preview.onerror = reject;
        preview.src = url;
      });
      image = preview;
      drawImageAndBoxes();
    } catch {
      image = null;
      canvas.hidden = true;
      emptyState.hidden = false;
      emptyState.textContent = 'Preview unavailable for this raster format. The server will still validate it.';
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  fileInput.addEventListener('change', async () => {
    selectedFile = fileInput.files?.[0] || null;
    results.dataset.visible = 'false';
    lastResult = null;
    if (!selectedFile) {
      reset();
      return;
    }
    fileLabel.textContent = selectedFile.name;
    analyzeButton.disabled = false;
    setStatus('Image selected. Review the filename, then run inference.');
    await loadPreview(selectedFile);
  });

  analyzeButton.addEventListener('click', async () => {
    if (!selectedFile) return;
    analyzeButton.disabled = true;
    setStatus('Running tiled research inference…');
    const formData = new FormData();
    formData.append('file', selectedFile);
    try {
      const response = await fetch('/api/v1/analyze', {
        method: 'POST',
        headers: headers(),
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
      lastResult = payload;
      drawImageAndBoxes(payload.detections);
      document.querySelector('#candidate-count').textContent = payload.detections.length.toLocaleString();
      document.querySelector('#hardware').textContent = payload.hardware;
      document.querySelector('#result-message').textContent = payload.message;
      const confidences = payload.detections.map((item) => Number(item.confidence));
      document.querySelector('#confidence-range').textContent = confidences.length
        ? `${Math.min(...confidences).toFixed(2)}–${Math.max(...confidences).toFixed(2)}`
        : '—';
      results.dataset.visible = 'true';
      setStatus('Research inference completed.', 'success');
    } catch (error) {
      setStatus(`Inference failed: ${error.message}`, 'error');
    } finally {
      analyzeButton.disabled = false;
    }
  });

  downloadButton.addEventListener('click', async () => {
    if (!lastResult || !selectedFile) return;
    setStatus('Preparing research PDF…');
    try {
      const response = await fetch('/api/v1/export_report', {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          filename: selectedFile.name,
          grade: lastResult.grade,
          hardware: lastResult.hardware,
          reviewer_name: document.querySelector('#reviewer-name').value || 'Not specified',
          count: lastResult.detections.length,
        }),
      });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || 'Report generation failed.');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'TB_AFB_Research_Report.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setStatus('Research PDF downloaded.', 'success');
    } catch (error) {
      setStatus(`PDF export failed: ${error.message}`, 'error');
    }
  });

  resetButton.addEventListener('click', reset);
  reset();
})();
