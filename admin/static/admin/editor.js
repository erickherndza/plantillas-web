/* editor.js — CMS Editor de plantillas */
'use strict';

const PID = window.PLANTILLA_ID;

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = 'success') {
  let el = document.getElementById('e-toast');
  if (!el) { el = document.createElement('div'); el.id = 'e-toast'; el.className = 'e-toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.className = `e-toast ${type} show`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3000);
}

// ── AJAX helper ───────────────────────────────────────────────────────────────
async function api(method, path, data) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (data !== undefined) opts.body = JSON.stringify(data);
  const r = await fetch(path, opts);
  const json = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(json.error || `HTTP ${r.status}`);
  return json;
}

// ── Tabs + Sidebar ────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.e-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.e-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      document.querySelectorAll('.e-sidebar-group').forEach(g => {
        g.style.display = g.dataset.tab === target || g.dataset.tab === 'all' ? '' : 'none';
      });
      // Activar primer link del tab
      const first = document.querySelector(`.e-sidebar-group[data-tab="${target}"] .e-sidebar-link`);
      if (first) first.click();
    });
  });

  document.querySelectorAll('.e-sidebar-link').forEach(link => {
    link.addEventListener('click', () => {
      document.querySelectorAll('.e-sidebar-link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      const panel = link.dataset.panel;
      document.querySelectorAll('.e-panel').forEach(p => p.classList.remove('active'));
      document.getElementById(`panel-${panel}`)?.classList.add('active');
    });
  });

  // Activar primer tab
  document.querySelector('.e-tab')?.click();
}

// ── Panel: General ────────────────────────────────────────────────────────────
function initGeneral() {
  document.getElementById('btn-save-general')?.addEventListener('click', async () => {
    try {
      await api('POST', `/admin/plantillas/${PID}/guardar-general`, {
        nombre:      document.getElementById('g-nombre').value,
        tipo:        document.getElementById('g-tipo').value,
        descripcion: document.getElementById('g-descripcion').value,
        preview_img: document.getElementById('g-preview').value,
      });
      toast('Información guardada');
    } catch(e) { toast(e.message, 'error'); }
  });
}

// ── Panel: Secciones ──────────────────────────────────────────────────────────
function initSecciones() {
  document.getElementById('btn-save-secciones')?.addEventListener('click', async () => {
    const secciones = [...document.querySelectorAll('.sec-toggle:checked')].map(c => c.value);
    try {
      await api('POST', `/admin/plantillas/${PID}/secciones`, { secciones });
      toast('Secciones guardadas');
    } catch(e) { toast(e.message, 'error'); }
  });
}

// ── Panel: Menú ───────────────────────────────────────────────────────────────
let menuItems = window.MENU_ITEMS || [];
let editingMenuItem = null;

function renderMenu() {
  const list = document.getElementById('menu-list');
  if (!list) return;
  const roots = menuItems.filter(i => !i.parent_id);
  const children = id => menuItems.filter(i => i.parent_id === id);
  let html = '';
  roots.forEach(item => {
    html += menuItemHTML(item, false);
    children(item.id).forEach(child => { html += menuItemHTML(child, true); });
  });
  list.innerHTML = html || '<p style="color:var(--e-muted);font-size:13px;padding:8px">Sin items. Agrega uno.</p>';
  list.querySelectorAll('.menu-edit').forEach(btn => {
    btn.addEventListener('click', () => openMenuForm(parseInt(btn.dataset.id)));
  });
  list.querySelectorAll('.menu-del').forEach(btn => {
    btn.addEventListener('click', () => deleteMenuItem(parseInt(btn.dataset.id)));
  });
  // Actualizar select de parent en el form
  const sel = document.getElementById('mi-parent');
  if (sel) {
    sel.innerHTML = '<option value="">Ninguno (raíz)</option>';
    roots.forEach(r => sel.innerHTML += `<option value="${r.id}">${r.label}</option>`);
  }
  if (window.Sortable && list.children.length > 1) {
    Sortable.create(list, { animation: 150, handle: '.grip', onEnd: saveMenuOrder });
  }
}

function menuItemHTML(item, isChild) {
  return `<div class="e-menu-item${isChild?' submenu':''}" data-id="${item.id}">
    <span class="grip">⠿</span>
    <span class="item-label">${item.label}</span>
    <span class="item-url">${item.url}</span>
    <div class="e-menu-item-actions">
      <button class="e-btn-icon menu-edit" data-id="${item.id}" title="Editar">✏️</button>
      <button class="e-btn-icon danger menu-del" data-id="${item.id}" title="Eliminar">🗑️</button>
    </div>
  </div>`;
}

function openMenuForm(id) {
  editingMenuItem = id ? menuItems.find(i => i.id === id) : null;
  const item = editingMenuItem;
  document.getElementById('mi-label').value = item?.label || '';
  document.getElementById('mi-url').value   = item?.url   || '#';
  document.getElementById('mi-parent').value = item?.parent_id || '';
  document.getElementById('menu-form').style.display = 'block';
  document.getElementById('menu-form-title').textContent = item ? 'Editar item' : 'Nuevo item';
}

async function saveMenuOrder() {
  const ids = [...document.querySelectorAll('#menu-list .e-menu-item')].map(el => parseInt(el.dataset.id));
  await api('POST', `/admin/plantillas/${PID}/menu/reordenar`, { orden: ids }).catch(() => {});
}

async function deleteMenuItem(id) {
  if (!confirm('¿Eliminar este item y sus submenús?')) return;
  try {
    await api('DELETE', `/admin/plantillas/${PID}/menu/${id}`);
    menuItems = menuItems.filter(i => i.id !== id && i.parent_id !== id);
    renderMenu();
    toast('Item eliminado');
  } catch(e) { toast(e.message, 'error'); }
}

function initMenu() {
  renderMenu();
  document.getElementById('btn-add-menu')?.addEventListener('click', () => openMenuForm(null));
  document.getElementById('btn-cancel-menu')?.addEventListener('click', () => {
    document.getElementById('menu-form').style.display = 'none';
  });
  document.getElementById('btn-save-menu')?.addEventListener('click', async () => {
    const label = document.getElementById('mi-label').value.trim();
    const url   = document.getElementById('mi-url').value.trim();
    const parent_id = document.getElementById('mi-parent').value || null;
    if (!label) { toast('El label es obligatorio', 'error'); return; }
    try {
      if (editingMenuItem) {
        await api('PUT', `/admin/plantillas/${PID}/menu/${editingMenuItem.id}`, { label, url, parent_id });
        const idx = menuItems.findIndex(i => i.id === editingMenuItem.id);
        if (idx >= 0) menuItems[idx] = { ...menuItems[idx], label, url, parent_id: parent_id ? parseInt(parent_id) : null };
      } else {
        const res = await api('POST', `/admin/plantillas/${PID}/menu`, { label, url, parent_id });
        menuItems.push({ id: res.id, label, url, parent_id: parent_id ? parseInt(parent_id) : null, orden: menuItems.length });
      }
      document.getElementById('menu-form').style.display = 'none';
      renderMenu();
      toast('Menú guardado');
    } catch(e) { toast(e.message, 'error'); }
  });
}

// ── Panel: Slider ─────────────────────────────────────────────────────────────
let sliderData = window.SLIDER_DATA || { config: {}, slides: [] };
let activeSlideIdx = -1;

function renderSlides() {
  const grid = document.getElementById('slides-grid');
  if (!grid) return;
  grid.innerHTML = sliderData.slides.map((s, i) => `
    <div class="e-slide-thumb${i === activeSlideIdx ? ' active' : ''}" data-idx="${i}" onclick="openSlide(${i})">
      ${s.imagen_url ? `<img src="${s.imagen_url}" alt="">` : `<div style="width:120px;height:70px;background:#e2e8f0;display:flex;align-items:center;justify-content:center;font-size:22px;">🖼️</div>`}
      <span class="slide-no">${i+1}</span>
      <button class="slide-del" onclick="event.stopPropagation();deleteSlide(${i})">✕</button>
    </div>
  `).join('') || '<p style="color:var(--e-muted);font-size:13px">Sin slides</p>';
}

function openSlide(idx) {
  activeSlideIdx = idx;
  const s = sliderData.slides[idx];
  document.getElementById('slide-img').value   = s.imagen_url || '';
  document.getElementById('slide-title').value = s.titulo     || '';
  document.getElementById('slide-sub').value   = s.subtitulo  || '';
  document.getElementById('slide-form').style.display = 'block';
  renderSlides();
}

async function deleteSlide(idx) {
  const s = sliderData.slides[idx];
  if (!s.id) return;
  try {
    await api('DELETE', `/admin/plantillas/${PID}/slider/slides/${s.id}`);
    sliderData.slides.splice(idx, 1);
    activeSlideIdx = -1;
    document.getElementById('slide-form').style.display = 'none';
    renderSlides();
    toast('Slide eliminado');
  } catch(e) { toast(e.message, 'error'); }
}

function initSlider() {
  renderSlides();
  // Config save
  document.getElementById('btn-save-slider-config')?.addEventListener('click', async () => {
    const cfg = {
      efecto:    document.getElementById('sl-efecto').value,
      intervalo: parseInt(document.getElementById('sl-intervalo').value) || 4,
      flechas:   document.getElementById('sl-flechas').value === '1',
      puntos:    document.getElementById('sl-puntos').value  === '1',
      modo:      document.getElementById('sl-modo').value,
    };
    try {
      await api('POST', `/admin/plantillas/${PID}/slider/config`, cfg);
      toast('Configuración guardada');
    } catch(e) { toast(e.message, 'error'); }
  });
  // Add slide
  document.getElementById('btn-add-slide')?.addEventListener('click', async () => {
    try {
      const res = await api('POST', `/admin/plantillas/${PID}/slider/slides`, { imagen_url:'', titulo:'', subtitulo:'' });
      sliderData.slides.push({ id: res.id, imagen_url:'', titulo:'', subtitulo:'', orden: sliderData.slides.length });
      openSlide(sliderData.slides.length - 1);
      renderSlides();
    } catch(e) { toast(e.message, 'error'); }
  });
  // Save slide
  document.getElementById('btn-save-slide')?.addEventListener('click', async () => {
    if (activeSlideIdx < 0) return;
    const s = sliderData.slides[activeSlideIdx];
    const data = {
      imagen_url: document.getElementById('slide-img').value,
      titulo:     document.getElementById('slide-title').value,
      subtitulo:  document.getElementById('slide-sub').value,
      orden:      activeSlideIdx,
    };
    try {
      await api('PUT', `/admin/plantillas/${PID}/slider/slides/${s.id}`, data);
      Object.assign(sliderData.slides[activeSlideIdx], data);
      renderSlides();
      toast('Slide guardado');
    } catch(e) { toast(e.message, 'error'); }
  });
}

// ── Panel: Footer ─────────────────────────────────────────────────────────────
function initFooter() {
  const colsEl = document.getElementById('footer-cols-count');
  if (colsEl) {
    colsEl.addEventListener('change', () => {
      const n = parseInt(colsEl.value);
      document.getElementById('footer-cols-grid').style.gridTemplateColumns = `repeat(${n}, 1fr)`;
    });
  }
  document.getElementById('btn-save-footer')?.addEventListener('click', async () => {
    const cols = [...document.querySelectorAll('.footer-col-data')].map(el => ({
      tipo: el.querySelector('.footer-col-tipo').value,
      contenido: el.querySelector('.footer-col-content').value,
    }));
    const cfg = {
      columnas:  parseInt(document.getElementById('footer-cols-count').value) || 3,
      bg_color:  document.getElementById('footer-bg').value,
      copyright: document.getElementById('footer-copy').value,
      cols,
    };
    try {
      await api('POST', `/admin/plantillas/${PID}/footer`, cfg);
      toast('Footer guardado');
    } catch(e) { toast(e.message, 'error'); }
  });
}

// ── Panel: Custom Code ────────────────────────────────────────────────────────
function initCustomCode() {
  document.getElementById('btn-save-code')?.addEventListener('click', async () => {
    const codigo = document.getElementById('cc-codigo').value.trim();
    if (!codigo) { toast('El código no puede estar vacío', 'error'); return; }
    const data = {
      tipo:           document.getElementById('cc-tipo').value,
      inject_in:      document.getElementById('cc-inject').value,
      seccion_target: document.getElementById('cc-seccion').value || null,
      codigo,
    };
    try {
      const res = await api('POST', `/admin/plantillas/${PID}/custom-code`, data);
      document.getElementById('cc-codigo').value = '';
      const list = document.getElementById('code-list');
      const div = document.createElement('div');
      div.className = 'e-code-item';
      div.dataset.id = res.id;
      div.innerHTML = `<span class="e-code-badge ${data.tipo}">${data.tipo.toUpperCase()}</span>
        <span style="font-size:12px;color:var(--e-muted);">${data.inject_in}</span>
        <span style="flex:1;font-size:12px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${codigo.substring(0,60)}…</span>
        <button class="e-btn-icon" onclick="toggleCode(${res.id},this)">⏸</button>
        <button class="e-btn-icon danger" onclick="deleteCode(${res.id},this)">🗑️</button>`;
      list.appendChild(div);
      toast('Bloque de código guardado');
    } catch(e) { toast(e.message, 'error'); }
  });
}

async function toggleCode(id, btn) {
  await api('POST', `/admin/plantillas/${PID}/custom-code/${id}/toggle`).catch(() => {});
  const item = btn.closest('.e-code-item');
  item.classList.toggle('e-code-inactive');
  toast('Estado actualizado');
}

async function deleteCode(id, btn) {
  if (!confirm('¿Eliminar este bloque?')) return;
  await api('DELETE', `/admin/plantillas/${PID}/custom-code/${id}`).catch(() => {});
  btn.closest('.e-code-item').remove();
  toast('Bloque eliminado');
}

// ── Panel: Scraper (client-side via allorigins.win) ───────────────────────────
let scraperResult = null;

async function _scraperClientSide(targetUrl) {
  const proxy = `https://api.allorigins.win/get?url=${encodeURIComponent(targetUrl)}`;
  const resp  = await fetch(proxy, { signal: AbortSignal.timeout(15000) });
  if (!resp.ok) throw new Error(`Proxy ${resp.status}`);
  const json = await resp.json();
  const html = json.contents || '';
  const doc  = new DOMParser().parseFromString(html, 'text/html');

  const hexRe = /#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g;
  const rawSet = new Set();
  const norm = h => { h=h.toLowerCase(); return h.length===4?'#'+h[1]+h[1]+h[2]+h[2]+h[3]+h[3]:h; };

  doc.querySelectorAll('[style]').forEach(el => { for (const [c] of el.getAttribute('style').matchAll(hexRe)) rawSet.add(norm(c)); });
  doc.querySelectorAll('style').forEach(st => { for (const [c] of st.textContent.matchAll(hexRe)) rawSet.add(norm(c)); });

  const colores = [...rawSet].filter(h => {
    const r=parseInt(h.slice(1,3),16), g=parseInt(h.slice(3,5),16), b=parseInt(h.slice(5,7),16);
    return Math.max(r,g,b)-Math.min(r,g,b) > 30;
  }).slice(0,10);

  const fontRe = /font-family:\s*['"]?([^,;'"}{]+)/gi;
  const fuentes = new Set();
  doc.querySelectorAll('style').forEach(st => {
    for (const [,f] of st.textContent.matchAll(fontRe)) {
      const c=f.trim().replace(/['"]/g,'');
      if (c && !c.toLowerCase().includes('system') && !c.toLowerCase().includes('sans-serif')) fuentes.add(c);
    }
  });

  let logo_url = '';
  for (const img of doc.querySelectorAll('img')) {
    const src=(img.getAttribute('src')||'');
    if ((img.getAttribute('alt')||'').toLowerCase().includes('logo')||src.toLowerCase().includes('logo')) {
      if (src.startsWith('http')) { logo_url=src; break; }
    }
  }

  const imagenes = [...doc.querySelectorAll('img')].map(i=>i.getAttribute('src')||'').filter(s=>s.startsWith('http')).slice(0,6);
  const titulo   = (doc.querySelector('h1,h2,title')?.textContent||'').trim().slice(0,100);
  const descMeta = doc.querySelector('meta[name="description"]');
  const descripcion = (descMeta?.getAttribute('content')||'').slice(0,200);

  return { colores, fuentes:[...fuentes].slice(0,4), logo_url, imagenes, textos:{titulo,descripcion} };
}

function initScraper() {
  document.getElementById('btn-analizar')?.addEventListener('click', async () => {
    const url = document.getElementById('scraper-url').value.trim();
    if (!url) { toast('Ingresa una URL', 'error'); return; }
    const btn = document.getElementById('btn-analizar');
    btn.textContent = 'Analizando…'; btn.disabled = true;
    try {
      scraperResult = await _scraperClientSide(url);
      renderScraperResult(scraperResult);
      toast('Análisis completado');
    } catch(e) {
      toast(e.name==='TimeoutError' ? 'Tiempo agotado. Intenta otra URL.' : 'No se pudo acceder al sitio.', 'error');
    }
    finally { btn.textContent = 'Analizar'; btn.disabled = false; }
  });
  document.getElementById('btn-aplicar')?.addEventListener('click', async () => {
    if (!scraperResult) return;
    await api('POST', `/admin/scraper/aplicar/${PID}`, scraperResult).catch(() => {});
    toast('Selección aplicada');
  });
}

function renderScraperResult(r) {
  const el = document.getElementById('scraper-result');
  if (!el) return;
  el.style.display = 'block';
  // Colores
  const colorsEl = document.getElementById('sr-colores');
  if (colorsEl) colorsEl.innerHTML = r.colores.map(c =>
    `<div class="e-color-chip" style="background:${c}" title="${c}" onclick="this.classList.toggle('selected')"></div>`
  ).join('');
  // Imágenes
  const imgsEl = document.getElementById('sr-imagenes');
  if (imgsEl) imgsEl.innerHTML = r.imagenes.map(src =>
    `<img class="e-img-chip" src="${src}" onclick="this.classList.toggle('selected')" title="${src}">`
  ).join('');
  // Textos
  document.getElementById('sr-titulo').value = r.textos?.titulo || '';
  document.getElementById('sr-desc').value   = r.textos?.descripcion || '';
  document.getElementById('sr-logo').value   = r.logo_url || '';
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initGeneral();
  initSecciones();
  initMenu();
  initSlider();
  initFooter();
  initCustomCode();
  initScraper();
});
