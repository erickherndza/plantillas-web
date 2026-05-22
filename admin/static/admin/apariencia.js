/* apariencia.js — Panel de Apariencia CMS */

// ── Panel navigation ──────────────────────────────────────────────────────────

function showPanel(name, item) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const p = document.getElementById('panel-' + name);
  if (p) p.classList.add('active');
  document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));
  if (item) item.classList.add('active');
}

// ── Mode toggle (admin/client) ────────────────────────────────────────────────

function setMode(mode) {
  const btnA = document.getElementById('btn-admin');
  const btnC = document.getElementById('btn-client');
  if (btnA) btnA.classList.toggle('active', mode === 'admin');
  if (btnC) btnC.classList.toggle('active', mode === 'client');
  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = mode === 'admin' ? '' : 'none';
  });
}

// ── Color sync ────────────────────────────────────────────────────────────────

function syncColor(picker, key) {
  const sw = document.getElementById('sw-' + key);
  const hex = document.getElementById('hex-' + key);
  if (sw)  sw.style.background = picker.value;
  if (hex) hex.value = picker.value;
}

function syncHex(input, key) {
  if (/^#[0-9A-Fa-f]{6}$/.test(input.value)) {
    const sw = document.getElementById('sw-' + key);
    if (sw) sw.style.background = input.value;
    const picker = input.closest('.color-swatch-wrap')
      ? input.closest('.color-row').querySelector('.color-picker-native')
      : null;
    if (picker) picker.value = input.value;
  }
}

// ── Font preview ──────────────────────────────────────────────────────────────

function previewFont() {
  const fh = document.getElementById('font-heading');
  const fb = document.getElementById('font-body');
  const h  = document.getElementById('fp-h');
  const p  = document.getElementById('fp-p');
  if (fh && h) h.style.fontFamily = fh.value;
  if (fb && p) p.style.fontFamily = fb.value;

  // Cargar Google Font bajo demanda
  [fh?.value, fb?.value].forEach(fam => {
    if (!fam) return;
    const m = fam.match(/['"]([^'"]+)['"]/);
    if (m) {
      const name = m[1].replace(/ /g, '+');
      const id = 'gf-' + name;
      if (!document.getElementById(id)) {
        const l = document.createElement('link');
        l.id = id; l.rel = 'stylesheet';
        l.href = `https://fonts.googleapis.com/css2?family=${name}:wght@400;600&display=swap`;
        document.head.appendChild(l);
      }
    }
  });
}

// ── Presets ───────────────────────────────────────────────────────────────────

function applyPreset(card, key) {
  const p = PRESETS[key];
  if (!p) return;

  ['primary','secondary','accent','neutral'].forEach(k => {
    const sw  = document.getElementById('sw-' + k);
    const hex = document.getElementById('hex-' + k);
    if (sw)  sw.style.background = p[k];
    if (hex) hex.value = p[k];
    // Actualizar color picker nativo
    const row = hex?.closest('.color-row');
    const picker = row?.querySelector('.color-picker-native');
    if (picker) picker.value = p[k];
  });

  document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('active'));
  card.classList.add('active');

  guardarColores(true);
}

function buildPresets() {
  const grid = document.getElementById('presets-grid');
  if (!grid) return;

  Object.entries(PRESETS).forEach(([key, p]) => {
    const card = document.createElement('div');
    card.className = 'preset-card';
    card.onclick = () => applyPreset(card, key);

    const dots = ['primary','secondary','accent'].map(k =>
      `<div class="preset-dot" style="background:${p[k]}"></div>`
    ).join('');

    card.innerHTML = `<div class="preset-dots">${dots}</div><div class="preset-name">${p.label}</div>`;
    grid.appendChild(card);
  });
}

// ── Toggle secciones ──────────────────────────────────────────────────────────

function toggleSeccion(el) {
  el.classList.toggle('on');
}

// ── API helper ────────────────────────────────────────────────────────────────

async function api(path, data) {
  const r = await fetch(`/admin/plantillas/${PID}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 2800);
}

// ── Guardar colores ───────────────────────────────────────────────────────────

async function guardarColores(silent = false) {
  const data = {
    color_primary:   document.getElementById('hex-primary')?.value   || '#185FA5',
    color_secondary: document.getElementById('hex-secondary')?.value || '#0A0F1E',
    color_accent:    document.getElementById('hex-accent')?.value    || '#0088CC',
    color_neutral:   document.getElementById('hex-neutral')?.value   || '#E8EAF0',
    modo_tema:       document.getElementById('modo-tema')?.value     || 'dark',
  };
  const res = await api('/apariencia/colores', data);
  if (!silent) showToast(res.ok ? 'Colores guardados' : 'Error al guardar', res.ok ? 'success' : 'error');
  if (res.ok) actualizarCSS();
}

// ── Guardar tipografía ────────────────────────────────────────────────────────

async function guardarTipografia() {
  const lhEl = document.getElementById('line_height');
  const data = {
    font_heading:   document.getElementById('font-heading')?.value  || 'system-ui, sans-serif',
    font_body:      document.getElementById('font-body')?.value     || 'system-ui, sans-serif',
    font_size_h1:   parseInt(document.getElementById('font_size_h1')?.value) || 48,
    font_size_h2:   parseInt(document.getElementById('font_size_h2')?.value) || 32,
    font_size_body: parseInt(document.getElementById('font_size_body')?.value) || 16,
    line_height:    lhEl ? parseFloat(lhEl.value) / 10 : 1.6,
  };
  const res = await api('/apariencia/tipografia', data);
  showToast(res.ok ? 'Tipografía guardada' : 'Error al guardar', res.ok ? 'success' : 'error');
  if (res.ok) actualizarCSS();
}

// ── Guardar espacio ───────────────────────────────────────────────────────────

async function guardarEspacio() {
  const data = {
    radius_btn:      parseInt(document.getElementById('radius_btn')?.value)      || 8,
    radius_card:     parseInt(document.getElementById('radius_card')?.value)     || 12,
    radius_input:    parseInt(document.getElementById('radius_input')?.value)    || 6,
    section_padding: parseInt(document.getElementById('section_padding')?.value) || 80,
    gap_elements:    parseInt(document.getElementById('gap_elements')?.value)    || 24,
  };
  const res = await api('/apariencia/espacio', data);
  showToast(res.ok ? 'Espacio guardado' : 'Error al guardar', res.ok ? 'success' : 'error');
  if (res.ok) actualizarCSS();
}

// ── Guardar efectos ───────────────────────────────────────────────────────────

async function guardarEfectos() {
  const data = {
    entrada:   document.getElementById('ef-entrada')?.classList.contains('on')  ?? true,
    hover_btn: document.getElementById('ef-hover')?.classList.contains('on')    ?? true,
    parallax:  document.getElementById('ef-parallax')?.classList.contains('on') ?? false,
    cursor:    document.getElementById('ef-cursor')?.classList.contains('on')   ?? false,
    velocidad: document.getElementById('ef-velocidad')?.value || '400ms',
    easing:    document.getElementById('ef-easing')?.value    || 'ease-out',
  };
  const res = await api('/apariencia/efectos', data);
  showToast(res.ok ? 'Efectos guardados' : 'Error al guardar', res.ok ? 'success' : 'error');
}

// ── Guardar móvil ─────────────────────────────────────────────────────────────

async function guardarMovil() {
  const data = {
    h1:             parseInt(document.getElementById('mob_font')?.value)    || 15,
    padding:        parseInt(document.getElementById('mob_padding')?.value) || 40,
    hide_subtitle:  document.getElementById('chk-sub')?.checked  ?? false,
    stack_columns:  document.getElementById('chk-col')?.checked  ?? true,
    hamburguesa:    document.getElementById('chk-ham')?.checked  ?? true,
  };
  const res = await api('/apariencia/movil', data);
  showToast(res.ok ? 'Móvil guardado' : 'Error al guardar', res.ok ? 'success' : 'error');
}

// ── Guardar sección (header / hero / footer) ──────────────────────────────────

async function guardarSeccion(sec) {
  let data = { seccion: sec };

  if (sec === 'header') {
    data.bg         = document.getElementById('header-bg')?.value           || '#0A0F1E';
    data.text        = document.getElementById('header-text')?.value         || '#E8EAF0';
    data.menu_style  = document.getElementById('header-menu-style')?.value   || 'horizontal';
    data.posicion    = document.getElementById('header-pos')?.value           || 'sticky';
    data.show_logo   = document.getElementById('header-logo')?.classList.contains('on') ?? true;
    data.show_cta    = document.getElementById('header-cta')?.classList.contains('on')  ?? true;
  } else if (sec === 'hero') {
    data.layout  = document.getElementById('hero-layout')?.value  || 'centrado';
    data.height  = document.getElementById('hero-height')?.value  || '100vh';
    data.bg      = document.getElementById('hero-bg')?.value      || '#0A0F1E';
    data.overlay = parseInt(document.getElementById('hero-overlay')?.value) || 40;
    const ph     = document.getElementById('hero-ph');
    if (ph) {
      data.page_header = ph.classList.contains('on');
      data.ph_height   = document.getElementById('hero-ph-height')?.value || '300';
      data.ph_bg       = document.getElementById('hero-ph-bg')?.value     || '#0A0F1E';
    }
  } else if (sec === 'footer') {
    data.bg     = document.getElementById('footer-bg')?.value     || '#012840';
    data.text   = document.getElementById('footer-text')?.value   || '#9FE1CB';
    data.links  = document.getElementById('footer-links')?.value  || '#5DCAA5';
    data.border = document.getElementById('footer-border')?.value || 'none';
  }

  const res = await api('/apariencia/seccion', data);
  const nombre = { header: 'Header', hero: 'Hero', footer: 'Footer' }[sec] || sec;
  showToast(res.ok ? `${nombre} guardado` : 'Error al guardar', res.ok ? 'success' : 'error');
}

// ── Guardar secciones activas ─────────────────────────────────────────────────

async function guardarSecciones() {
  const activas = [...document.querySelectorAll('.toggle-item.on')].map(el => el.dataset.sec);
  const res = await api('/secciones', { secciones: activas });
  showToast(res.ok ? 'Secciones guardadas' : 'Error al guardar', res.ok ? 'success' : 'error');
}

// ── Guardar activo (topbar button) ────────────────────────────────────────────

function guardarActivo() {
  const active = document.querySelector('.sb-item.active');
  if (!active) return;

  const panelMap = {
    'colores':     () => guardarColores(),
    'tipografia':  () => guardarTipografia(),
    'espacio':     () => guardarEspacio(),
    'efectos':     () => guardarEfectos(),
    'movil':       () => guardarMovil(),
    'presets':     () => showToast('Selecciona un preset para aplicarlo', 'error'),
    'menu':        () => menuGuardar(),
    'header':      () => guardarSeccion('header'),
    'hero':        () => guardarSeccion('hero'),
    'footer-sec':  () => guardarSeccion('footer'),
    'secciones':   () => guardarSecciones(),
  };

  // Detectar cuál panel está activo buscando el que tiene onclick con el nombre
  const onclick = active.getAttribute('onclick') || '';
  const m = onclick.match(/showPanel\('([^']+)'/);
  const key = m?.[1];
  if (key && panelMap[key]) panelMap[key]();
}

// ── Ver CSS ───────────────────────────────────────────────────────────────────

async function verCSS() {
  try {
    const r = await fetch(`/admin/plantillas/${PID}/apariencia/css`);
    const d = await r.json();
    const box = document.getElementById('css-output');
    if (box) box.textContent = d.css;
    // Cambiar al panel de colores donde está el css-output-box
    showPanel('colores', document.querySelector('[onclick*="colores"]'));
  } catch (e) {
    showToast('Error obteniendo CSS', 'error');
  }
}

async function actualizarCSS() {
  const box = document.getElementById('css-output');
  if (!box) return;
  try {
    const r = await fetch(`/admin/plantillas/${PID}/apariencia/css`);
    const d = await r.json();
    box.textContent = d.css;
  } catch (_) {}
}

function copiarCSS() {
  const box = document.getElementById('css-output');
  if (!box) return;
  navigator.clipboard.writeText(box.textContent)
    .then(() => showToast('CSS copiado'))
    .catch(() => showToast('No se pudo copiar', 'error'));
}

// ── Menú ──────────────────────────────────────────────────────────────────────

function menuRender(items) {
  const list = document.getElementById('menu-list');
  if (!list) return;
  list.innerHTML = '';

  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'menu-row';
    row.dataset.id = item.id;
    row.innerHTML = `
      <i class="ti ti-grip-vertical drag-handle"></i>
      <input class="menu-label-input" type="text" value="${_esc(item.label)}" placeholder="Etiqueta">
      <input class="menu-url-input" type="text" value="${_esc(item.url)}" placeholder="${TIPO === 'landing' ? '#seccion' : '/ruta'}">
      <button class="btn-icon danger" onclick="menuEliminar(this,${item.id})"><i class="ti ti-trash"></i></button>
    `;
    list.appendChild(row);
  });
}

async function menuAgregar() {
  const defaultUrl = TIPO === 'landing' ? '#nueva-seccion' : '/nueva-pagina';
  const res = await api('/menu', { label: 'Nuevo item', url: defaultUrl });
  if (res.ok) {
    const r2 = await fetch(`/admin/plantillas/${PID}/menu`);
    menuRender(await r2.json());
    showToast('Item agregado');
  }
}

async function menuEliminar(btn, id) {
  const r = await fetch(`/admin/plantillas/${PID}/menu/${id}`, { method: 'DELETE' });
  const d = await r.json();
  if (d.ok) {
    btn.closest('.menu-row').remove();
    showToast('Item eliminado');
  }
}

async function menuGuardar() {
  const rows = document.querySelectorAll('#menu-list .menu-row');
  const saves = [...rows].map(row => {
    const id = row.dataset.id;
    const label = row.querySelector('.menu-label-input').value;
    const url   = row.querySelector('.menu-url-input').value;
    return fetch(`/admin/plantillas/${PID}/menu/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, url }),
    });
  });
  await Promise.all(saves);
  showToast('Menú guardado');
}

// ── Utils ─────────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  buildPresets();
  menuRender(typeof MENU_ITEMS !== 'undefined' ? MENU_ITEMS : []);
  if (MODO === 'admin') setMode('admin');
  previewFont();
});
