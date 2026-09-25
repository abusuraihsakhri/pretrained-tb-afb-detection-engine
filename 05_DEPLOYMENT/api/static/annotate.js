(() => {
  const fileInput = document.querySelector('#file-input');
  const fileLabel = document.querySelector('#file-label-text');
  const tokenInput = document.querySelector('#api-token');
  const canvas = document.querySelector('#annotation-canvas');
  const context = canvas.getContext('2d');
  const emptyState = document.querySelector('#empty-state');
  const boxList = document.querySelector('#box-list');
  const submitButton = document.querySelector('#submit-button');
  const status = document.querySelector('#status');
  let selectedFile = null;
  let image = null;
  let boxes = [];
  let drawing = null;

  function setStatus(message, state = '') {
    status.textContent = message;
    status.dataset.state = state;
  }

  function boxIsValid(box) {
    return box.width > 0 && box.height > 0
      && box.x - box.width / 2 >= 0 && box.x + box.width / 2 <= 1
      && box.y - box.height / 2 >= 0 && box.y + box.height / 2 <= 1;
  }

  function render() {
    if (!image) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    context.lineWidth = Math.max(2, canvas.width / 700);
    context.strokeStyle = '#176b4d';
    boxes.forEach((box) => {
      context.strokeRect(
        (box.x - box.width / 2) * canvas.width,
        (box.y - box.height / 2) * canvas.height,
        box.width * canvas.width,
        box.height * canvas.height,
      );
    });
    if (drawing) {
      context.strokeStyle = '#a82c2c';
      context.strokeRect(drawing.x, drawing.y, drawing.width, drawing.height);
    }
  }

  function renderList() {
    boxList.replaceChildren();
    if (!boxes.length) {
      const item = document.createElement('li');
      item.textContent = 'No boxes added.';
      boxList.appendChild(item);
    } else {
      boxes.forEach((box, index) => {
        const item = document.createElement('li');
        item.textContent = `${index + 1}: x ${box.x.toFixed(3)}, y ${box.y.toFixed(3)}, w ${box.width.toFixed(3)}, h ${box.height.toFixed(3)} `;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = `Remove box ${index + 1}`;
        remove.addEventListener('click', () => {
          boxes.splice(index, 1);
          renderList();
          render();
        });
        item.appendChild(remove);
        boxList.appendChild(item);
      });
    }
    submitButton.disabled = !selectedFile || boxes.length === 0;
  }

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    selectedFile = file;
    boxes = [];
    fileLabel.textContent = file.name;
    const url = URL.createObjectURL(file);
    const preview = new Image();
    preview.onload = () => {
      URL.revokeObjectURL(url);
      image = preview;
      const maxWidth = 1400;
      const scale = Math.min(1, maxWidth / image.naturalWidth);
      canvas.width = Math.round(image.naturalWidth * scale);
      canvas.height = Math.round(image.naturalHeight * scale);
      canvas.hidden = false;
      emptyState.hidden = true;
      renderList();
      render();
      setStatus('Image ready. Add candidate boxes for review.');
    };
    preview.onerror = () => {
      URL.revokeObjectURL(url);
      setStatus('The selected image cannot be rendered in this browser.', 'error');
    };
    preview.src = url;
  });

  document.querySelector('#add-box-button').addEventListener('click', () => {
    if (!selectedFile) {
      setStatus('Choose an image before adding boxes.', 'error');
      return;
    }
    const box = {
      x: Number(document.querySelector('#box-x').value),
      y: Number(document.querySelector('#box-y').value),
      width: Number(document.querySelector('#box-width').value),
      height: Number(document.querySelector('#box-height').value),
      label: 0,
    };
    if (!boxIsValid(box)) {
      setStatus('Box must have positive size and remain fully inside the image.', 'error');
      return;
    }
    boxes.push(box);
    renderList();
    render();
    setStatus(`Added box ${boxes.length}.`, 'success');
  });

  canvas.addEventListener('pointerdown', (event) => {
    canvas.setPointerCapture(event.pointerId);
    const bounds = canvas.getBoundingClientRect();
    drawing = { startX: event.clientX - bounds.left, startY: event.clientY - bounds.top, x: 0, y: 0, width: 0, height: 0 };
  });

  canvas.addEventListener('pointermove', (event) => {
    if (!drawing) return;
    const bounds = canvas.getBoundingClientRect();
    const endX = Math.max(0, Math.min(bounds.width, event.clientX - bounds.left));
    const endY = Math.max(0, Math.min(bounds.height, event.clientY - bounds.top));
    const scaleX = canvas.width / bounds.width;
    const scaleY = canvas.height / bounds.height;
    drawing.x = Math.min(drawing.startX, endX) * scaleX;
    drawing.y = Math.min(drawing.startY, endY) * scaleY;
    drawing.width = Math.abs(endX - drawing.startX) * scaleX;
    drawing.height = Math.abs(endY - drawing.startY) * scaleY;
    render();
  });

  canvas.addEventListener('pointerup', () => {
    if (!drawing) return;
    const candidate = {
      x: (drawing.x + drawing.width / 2) / canvas.width,
      y: (drawing.y + drawing.height / 2) / canvas.height,
      width: drawing.width / canvas.width,
      height: drawing.height / canvas.height,
      label: 0,
    };
    drawing = null;
    if (candidate.width >= 0.003 && candidate.height >= 0.003 && boxIsValid(candidate)) {
      boxes.push(candidate);
      setStatus(`Added box ${boxes.length}.`, 'success');
    } else {
      setStatus('Ignored a very small or out-of-bounds pointer box.', 'error');
    }
    renderList();
    render();
  });

  document.querySelector('#clear-button').addEventListener('click', () => {
    if (!boxes.length || window.confirm('Clear all unsaved boxes?')) {
      boxes = [];
      renderList();
      render();
      setStatus('Unsaved boxes cleared.');
    }
  });

  submitButton.addEventListener('click', async () => {
    const token = tokenInput.value.trim();
    if (!token) {
      setStatus('An API token is required for queue submission.', 'error');
      tokenInput.focus();
      return;
    }
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('boxes', JSON.stringify(boxes));
    submitButton.disabled = true;
    setStatus('Submitting to the provenance review queue…');
    try {
      const response = await fetch('/api/v1/save_annotation', {
        method: 'POST',
        headers: { 'X-API-Key': token },
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Queue submission failed.');
      boxes = [];
      renderList();
      render();
      setStatus(`${payload.message} Record: ${payload.record_id}`, 'success');
    } catch (error) {
      setStatus(`Submission failed: ${error.message}`, 'error');
    } finally {
      submitButton.disabled = !selectedFile || boxes.length === 0;
    }
  });

  renderList();
})();
