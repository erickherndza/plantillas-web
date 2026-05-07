// admin.js — Panel de administración · Plantillas Web RD

// ── 1. Navegación por secciones ───────────────────────────────────────────────
function initSectionNav() {
  const navItems = document.querySelectorAll('.section-nav-item');
  const sections = document.querySelectorAll('.form-section');
  if (!navItems.length) return;

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      const target = item.dataset.section;
      sections.forEach(s => {
        s.classList.toggle('hidden', s.id !== `section-${target}`);
      });
    });
  });
}

// ── 2. Color picker ───────────────────────────────────────────────────────────
function initColorPickers() {
  document.querySelectorAll('.color-input').forEach(input => {
    const previewId = input.dataset.preview;
    const preview   = previewId ? document.getElementById(previewId) : null;
    const hexId     = previewId ? previewId.replace('_preview', '_hex') : null;
    const hexLabel  = hexId ? document.getElementById(hexId) : null;

    function update() {
      if (preview)  preview.style.background = input.value;
      if (hexLabel) hexLabel.textContent = input.value.toUpperCase();
    }
    input.addEventListener('input', update);
    input.addEventListener('change', update);
    update();
  });
}

// ── 3. Upload de logo (imagen_src) ────────────────────────────────────────────
function initImageUploads() {
  document.querySelectorAll('.img-upload-zone').forEach(zone => {
    const fileInput  = zone.querySelector('.img-file-input');
    const hiddenInput = zone.querySelector('.img-url-hidden');
    const thumb      = zone.querySelector('.img-thumb');
    const placeholder = zone.querySelector('.img-placeholder');
    const plantillaId = zone.dataset.plantilla;

    if (!fileInput) return;

    fileInput.addEventListener('change', async () => {
      const file = fileInput.files[0];
      if (!file) return;

      const btn = zone.querySelector('.btn-upload-label');
      const originalText = btn ? btn.childNodes[0].textContent.trim() : '';
      if (btn) btn.childNodes[0].textContent = 'Subiendo...';

      const formData = new FormData();
      formData.append('imagen', file);

      try {
        const res  = await fetch(`/upload/${plantillaId}`, { method: 'POST', body: formData });
        const data = await res.json();

        if (data.ok) {
          hiddenInput.value = data.url;
          if (thumb) {
            thumb.src = data.url;
            thumb.style.display = 'block';
          } else if (placeholder) {
            // Replace placeholder with img
            const img = document.createElement('img');
            img.src = data.url;
            img.className = 'img-thumb';
            img.alt = 'Logo';
            placeholder.replaceWith(img);
          }
          // Show remove button if not present
          if (!zone.querySelector('.btn-remove-img')) {
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-remove-img';
            removeBtn.dataset.target = hiddenInput.name;
            removeBtn.textContent = 'Quitar logo';
            zone.querySelector('.img-upload-actions').appendChild(removeBtn);
            removeBtn.addEventListener('click', () => clearLogoHandler(zone));
          }
        } else {
          alert('Error al subir: ' + data.error);
        }
      } catch (e) {
        alert('Error de conexión al subir la imagen.');
      } finally {
        if (btn) btn.childNodes[0].textContent = originalText;
      }
    });

    // Remove logo
    zone.querySelector('.btn-remove-img')?.addEventListener('click', () => clearLogoHandler(zone));
  });
}

function clearLogoHandler(zone) {
  const hiddenInput = zone.querySelector('.img-url-hidden');
  const thumb = zone.querySelector('.img-thumb');
  hiddenInput.value = '';
  if (thumb) {
    thumb.src = '';
    thumb.style.display = 'none';
  }
  const removeBtn = zone.querySelector('.btn-remove-img');
  if (removeBtn) removeBtn.remove();
}

// ── 4. Upload de imagen de fondo (imagen_bg) ──────────────────────────────────
function initImageBgUploads() {
  document.querySelectorAll('.img-file-bg-input').forEach(fileInput => {
    const label       = fileInput.closest('label');
    const plantillaId = label ? label.dataset.plantilla : null;
    const targetName  = label ? label.dataset.target : null;
    if (!plantillaId || !targetName) return;

    fileInput.addEventListener('change', async () => {
      const file = fileInput.files[0];
      if (!file) return;

      const urlInput = document.querySelector(`input[name="${targetName}"]`);
      const formData = new FormData();
      formData.append('imagen', file);

      try {
        const res  = await fetch(`/upload/${plantillaId}`, { method: 'POST', body: formData });
        const data = await res.json();
        if (data.ok) {
          if (urlInput) urlInput.value = data.url;
          // Update inline preview
          const field   = fileInput.closest('.img-bg-field');
          let   preview = field.querySelector('.img-bg-preview');
          if (!preview) {
            preview = document.createElement('div');
            preview.className = 'img-bg-preview';
            field.appendChild(preview);
          }
          preview.style.backgroundImage = `url('${data.url}')`;
        } else {
          alert('Error: ' + data.error);
        }
      } catch (e) {
        alert('Error de conexión.');
      }
    });
  });

  // Update bg preview when URL is typed manually
  document.querySelectorAll('.img-bg-url-input').forEach(input => {
    input.addEventListener('change', () => {
      const field   = input.closest('.img-bg-field');
      let   preview = field.querySelector('.img-bg-preview');
      if (!input.value) return;
      if (!preview) {
        preview = document.createElement('div');
        preview.className = 'img-bg-preview';
        field.appendChild(preview);
      }
      preview.style.backgroundImage = `url('${input.value}')`;
    });
  });
}

// ── 5. Repeaters ─────────────────────────────────────────────────────────────
function initRepeaters() {
  document.querySelectorAll('.repeater-container').forEach(container => {
    const puedeAgregar = container.dataset.puedeAgregar === 'true';

    // Botón agregar
    if (puedeAgregar) {
      container.querySelector('.btn-add-item')?.addEventListener('click', () => {
        addRepeaterItem(container);
      });
    }

    // Botones eliminar (delegación)
    container.addEventListener('click', e => {
      const btn = e.target.closest('.btn-remove-item');
      if (!btn) return;
      const list  = container.querySelector('.repeater-list');
      const items = list.querySelectorAll('.repeater-item');
      if (items.length > 1) {
        btn.closest('.repeater-item').remove();
        reindexRepeater(container);
      } else {
        btn.closest('.repeater-item').querySelectorAll('input,textarea').forEach(el => el.value = '');
      }
    });
  });
}

function addRepeaterItem(container) {
  const list     = container.querySelector('.repeater-list');
  const template = list.querySelector('.repeater-item');
  if (!template) return;

  const clone = template.cloneNode(true);
  const newIdx = list.querySelectorAll('.repeater-item').length;

  clone.querySelectorAll('[name]').forEach(el => {
    el.name  = el.name.replace(/__\d+__/, `__${newIdx}__`);
    el.value = '';
  });
  clone.querySelector('.repeater-item-num').textContent = newIdx + 1;

  list.appendChild(clone);
}

function reindexRepeater(container) {
  container.querySelectorAll('.repeater-item').forEach((item, idx) => {
    item.querySelector('.repeater-item-num').textContent = idx + 1;
    item.querySelectorAll('[name]').forEach(el => {
      el.name = el.name.replace(/__\d+__/, `__${idx}__`);
    });
  });
}

// ── 6. Submit: spinner ────────────────────────────────────────────────────────
function initFormSubmit() {
  const form = document.getElementById('editor-form');
  const btn  = document.getElementById('btn-guardar');
  if (!form || !btn) return;

  form.addEventListener('submit', () => {
    btn.disabled = true;
    btn.querySelector('.btn-text')?.classList.add('hidden');
    btn.querySelector('.btn-loading')?.classList.remove('hidden');
  });
}

// ── 7. Flash auto-dismiss ─────────────────────────────────────────────────────
function initFlashDismiss() {
  document.querySelectorAll('.flash-success, .flash-info').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSectionNav();
  initColorPickers();
  initImageUploads();
  initImageBgUploads();
  initRepeaters();
  initFormSubmit();
  initFlashDismiss();
});
