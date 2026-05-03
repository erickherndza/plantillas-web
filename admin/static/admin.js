// admin.js — Panel de administración · Plantillas Web RD

// ── 1. Navegación por secciones (sidebar) ──────────────────────────────────
function initSectionNav() {
  const navItems = document.querySelectorAll('.section-nav-item');
  const sections = document.querySelectorAll('.form-section');

  if (!navItems.length) return;

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const target = item.dataset.section;

      // Activar ítem del sidebar
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      // Mostrar sección correspondiente
      sections.forEach(s => {
        s.classList.toggle('hidden', s.id !== `section-${target}`);
      });
    });
  });
}

// ── 2. Color picker con preview en tiempo real ────────────────────────────
function initColorPickers() {
  const inputs = document.querySelectorAll('.color-input');

  inputs.forEach(input => {
    const previewId = input.dataset.preview;
    const preview   = previewId ? document.getElementById(previewId) : null;
    const hexId     = previewId ? previewId.replace('_preview', '_hex') : null;
    const hexLabel  = hexId ? document.getElementById(hexId) : null;

    function update() {
      const color = input.value;
      if (preview)  preview.style.background = color;
      if (hexLabel) hexLabel.textContent = color.toUpperCase();
    }

    input.addEventListener('input', update);
    input.addEventListener('change', update);
    update(); // estado inicial
  });
}

// ── 3. Submit: deshabilitar botón + spinner ───────────────────────────────
function initFormSubmit() {
  const form   = document.getElementById('editor-form');
  const btn    = document.getElementById('btn-guardar');
  if (!form || !btn) return;

  form.addEventListener('submit', () => {
    const textEl    = btn.querySelector('.btn-text');
    const loadingEl = btn.querySelector('.btn-loading');

    btn.disabled = true;
    if (textEl)    textEl.classList.add('hidden');
    if (loadingEl) loadingEl.classList.remove('hidden');
  });
}

// ── 4. Auto-dismiss flash messages (éxito) ───────────────────────────────
function initFlashDismiss() {
  const flashes = document.querySelectorAll('.flash-success, .flash-info');
  flashes.forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSectionNav();
  initColorPickers();
  initFormSubmit();
  initFlashDismiss();
});
