/* apariencia.js — Panel CSS Builder */

const PRESETS = {
  'oceano-oscuro': { primary:'#185FA5', secondary:'#0A0F1E', accent:'#0088CC', neutral:'#E8EAF0' },
  'magenta-noche': { primary:'#b4327a', secondary:'#1a0a12', accent:'#f9a8d4', neutral:'#F1EFE8' },
  'caribe':        { primary:'#038C8C', secondary:'#024959', accent:'#9FE1CB', neutral:'#E1F5EE' },
  'bosque':        { primary:'#639922', secondary:'#173404', accent:'#C0DD97', neutral:'#EAF3DE' },
  'ambar':         { primary:'#BA7517', secondary:'#412402', accent:'#FAC775', neutral:'#FAEEDA' },
  'grafito':       { primary:'#5F5E5A', secondary:'#2C2C2A', accent:'#D3D1C7', neutral:'#F1EFE8' },
};

const PRESET_LABELS = {
  'oceano-oscuro': 'Océano Oscuro',
  'magenta-noche': 'Magenta Noche',
  'caribe':        'Caribe',
  'bosque':        'Bosque',
  'ambar':         'Ámbar',
  'grafito':       'Grafito',
};

const AP = (() => {
  /* ── helpers ── */
  const $ = id => document.getElementById(id);
  const BASE = `/admin/plantillas/${PID}`;

  async function api(path, data) {
    const r = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  }

  function toast(msg, ok = true) {
    const t = $('ap-toast');
    t.textContent = msg;
    t.className = 'ap-toast ' + (ok ? 'ok' : 'err') + ' visible';
    setTimeout(() => { t.className = 'ap-toast'; }, 3200);
  }

  /* ── panel navigation ── */
  function initNav() {
    document.querySelectorAll('.ap-nav-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const panel = btn.dataset.panel;
        document.querySelectorAll('.ap-nav-item').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.ap-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const el = $('panel-' + panel);
        if (el) el.classList.add('active');
      });
    });
  }

  /* ── color sync (swatch ↔ hex) ── */
  function bindColors() {
    const pairs = [
      ['color_primary', 'color_primary_hex'],
      ['color_secondary', 'color_secondary_hex'],
      ['color_accent', 'color_accent_hex'],
      ['color_neutral', 'color_neutral_hex'],
      ['header_bg', 'header_bg_hex'],
      ['header_text', 'header_text_hex'],
      ['hero_overlay_color', 'hero_overlay_color_hex'],
      ['footer_bg', 'footer_bg_hex'],
      ['footer_text', 'footer_text_hex'],
    ];

    pairs.forEach(([swatchId, hexId]) => {
      const swatch = $(swatchId);
      const hex = $(hexId);
      if (!swatch || !hex) return;

      swatch.addEventListener('input', () => {
        hex.value = swatch.value;
        updateColorPreview();
      });

      hex.addEventListener('input', () => {
        const v = hex.value.trim();
        if (/^#[0-9a-fA-F]{6}$/.test(v)) {
          swatch.value = v;
          updateColorPreview();
        }
      });
    });
  }

  function updateColorPreview() {
    const ids = ['cp-primary','cp-secondary','cp-accent','cp-neutral'];
    const fields = ['color_primary','color_secondary','color_accent','color_neutral'];
    ids.forEach((id, i) => {
      const el = $(id);
      const f = $(fields[i]);
      if (el && f) el.style.background = f.value;
    });
  }

  /* ── font preview ── */
  function bindFonts() {
    const heading = $('font_heading');
    const body = $('font_body');
    if (!heading || !body) return;

    function updateFontPreview() {
      const fh = $('fp-heading');
      const fb = $('fp-body');
      if (fh) fh.style.fontFamily = heading.value;
      if (fb) fb.style.fontFamily = body.value;

      // Cargar fuente de Google si es necesaria
      [heading.value, body.value].forEach(fam => {
        const match = fam.match(/['"]([^'"]+)['"]/);
        if (match) {
          const name = match[1].replace(/ /g, '+');
          const id = 'gf-' + name;
          if (!document.getElementById(id)) {
            const link = document.createElement('link');
            link.id = id;
            link.rel = 'stylesheet';
            link.href = `https://fonts.googleapis.com/css2?family=${name}:wght@400;700&display=swap`;
            document.head.appendChild(link);
          }
        }
      });
    }

    heading.addEventListener('change', updateFontPreview);
    body.addEventListener('change', updateFontPreview);
    updateFontPreview();
  }

  /* ── espacio preview ── */
  function previewEspacio() {
    const rb = $('radius_btn');
    const rc = $('radius_card');
    const ri = $('radius_input');
    if (rb) { const ep = $('ep-btn'); if (ep) ep.style.borderRadius = rb.value + 'px'; }
    if (rc) { const ep = $('ep-card'); if (ep) ep.style.borderRadius = rc.value + 'px'; }
    if (ri) { const ep = $('ep-input'); if (ep) ep.style.borderRadius = ri.value + 'px'; }
  }

  /* ── presets ── */
  function initPresets() {
    const grid = $('presets-grid');
    if (!grid) return;

    Object.entries(PRESETS).forEach(([key, colors]) => {
      const card = document.createElement('div');
      card.className = 'preset-card';
      card.dataset.key = key;

      const swatches = ['primary','secondary','accent','neutral'].map(k =>
        `<div class="preset-sw" style="background:${colors[k]}" title="${k}"></div>`
      ).join('');

      card.innerHTML = `
        <div class="preset-swatches">${swatches}</div>
        <div class="preset-name">${PRESET_LABELS[key] || key}</div>
      `;

      card.addEventListener('click', () => {
        document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        applyPreset(colors);
      });

      grid.appendChild(card);
    });
  }

  function applyPreset(colors) {
    const fields = {
      primary: ['color_primary', 'color_primary_hex'],
      secondary: ['color_secondary', 'color_secondary_hex'],
      accent: ['color_accent', 'color_accent_hex'],
      neutral: ['color_neutral', 'color_neutral_hex'],
    };
    Object.entries(colors).forEach(([k, v]) => {
      if (!fields[k]) return;
      const [sw, hx] = fields[k];
      if ($(sw)) $(sw).value = v;
      if ($(hx)) $(hx).value = v;
    });
    updateColorPreview();
    // Auto-guardar colores al aplicar preset
    guardarColores(true);
  }

  /* ── guardar colores ── */
  async function guardarColores(silent = false) {
    const modo_tema = document.querySelector('input[name="modo_tema"]:checked');
    const data = {
      color_primary:   $('color_primary')?.value || '#185FA5',
      color_secondary: $('color_secondary')?.value || '#0A0F1E',
      color_accent:    $('color_accent')?.value || '#0088CC',
      color_neutral:   $('color_neutral')?.value || '#E8EAF0',
      modo_tema:       modo_tema?.value || 'dark',
    };
    const res = await api('/apariencia/colores', data);
    if (!silent) toast(res.ok ? 'Colores guardados' : 'Error guardando', res.ok);
    if (res.ok) refreshCSS();
  }

  /* ── guardar tipografía ── */
  async function guardarTipografia() {
    const lh = $('line_height');
    const data = {
      font_heading:   $('font_heading')?.value || 'system-ui, sans-serif',
      font_body:      $('font_body')?.value || 'system-ui, sans-serif',
      font_size_h1:   parseInt($('font_size_h1')?.value) || 48,
      font_size_h2:   parseInt($('font_size_h2')?.value) || 32,
      font_size_body: parseInt($('font_size_body')?.value) || 16,
      line_height:    lh ? parseFloat(lh.value) / 10 : 1.6,
    };
    const res = await api('/apariencia/tipografia', data);
    toast(res.ok ? 'Tipografía guardada' : 'Error guardando', res.ok);
    if (res.ok) refreshCSS();
  }

  /* ── guardar espacio ── */
  async function guardarEspacio() {
    const data = {
      radius_btn:      parseInt($('radius_btn')?.value) || 8,
      radius_card:     parseInt($('radius_card')?.value) || 12,
      radius_input:    parseInt($('radius_input')?.value) || 6,
      section_padding: parseInt($('section_padding')?.value) || 80,
      gap_elements:    parseInt($('gap_elements')?.value) || 24,
    };
    const res = await api('/apariencia/espacio', data);
    toast(res.ok ? 'Espacio guardado' : 'Error guardando', res.ok);
    if (res.ok) refreshCSS();
  }

  /* ── guardar efectos ── */
  async function guardarEfectos() {
    const data = {
      fade_in:       $('ef_fade_in')?.checked ?? true,
      hover_scale:   $('ef_hover_scale')?.checked ?? true,
      smooth_scroll: $('ef_smooth_scroll')?.checked ?? true,
      parallax:      $('ef_parallax')?.checked ?? false,
    };
    const res = await api('/apariencia/efectos', data);
    toast(res.ok ? 'Efectos guardados' : 'Error guardando', res.ok);
  }

  /* ── guardar móvil ── */
  async function guardarMovil() {
    const data = {
      font_size_body:     parseInt($('mob_font_size_body')?.value) || 15,
      section_padding:    parseInt($('mob_section_padding')?.value) || 40,
      hide_hero_subtitle: $('mob_hide_hero_subtitle')?.checked ?? false,
      stack_columns:      $('mob_stack_columns')?.checked ?? true,
    };
    const res = await api('/apariencia/movil', data);
    toast(res.ok ? 'Móvil guardado' : 'Error guardando', res.ok);
  }

  /* ── guardar sección ── */
  async function guardarSeccion(sec) {
    let data = { seccion: sec };

    if (sec === 'header') {
      data.bg          = $('header_bg')?.value || '#0A0F1E';
      data.text        = $('header_text')?.value || '#FFFFFF';
      data.height      = parseInt($('header_height')?.value) || 64;
      data.sticky      = $('header_sticky')?.checked ?? true;
      data.transparent = $('header_transparent')?.checked ?? false;
    } else if (sec === 'hero') {
      data.height        = $('hero_height')?.value || '60vh';
      data.align         = document.querySelector('input[name="hero_align"]:checked')?.value || 'center';
      data.overlay       = parseInt($('hero_overlay')?.value) || 50;
      data.overlay_color = $('hero_overlay_color')?.value || '#000000';
    } else if (sec === 'footer') {
      data.bg   = $('footer_bg')?.value || '#0A0F1E';
      data.text = $('footer_text')?.value || '#94a3b8';
      data.cols = parseInt($('footer_cols')?.value) || 3;
    }

    const res = await api('/apariencia/seccion', data);
    toast(res.ok ? `${sec.charAt(0).toUpperCase()+sec.slice(1)} guardado` : 'Error guardando', res.ok);
  }

  /* ── guardar panel activo ── */
  function guardarActivo() {
    const active = document.querySelector('.ap-nav-item.active');
    if (!active) return;
    const panel = active.dataset.panel;
    const map = {
      colores:    guardarColores,
      tipografia: guardarTipografia,
      espacio:    guardarEspacio,
      efectos:    guardarEfectos,
      movil:      guardarMovil,
      presets:    () => toast('Selecciona un preset para aplicarlo', false),
      header:     () => guardarSeccion('header'),
      hero:       () => guardarSeccion('hero'),
      footer:     () => guardarSeccion('footer'),
    };
    if (map[panel]) map[panel]();
  }

  /* ── CSS preview ── */
  async function refreshCSS() {
    try {
      const r = await fetch(BASE + '/apariencia/css');
      const d = await r.json();
      const pre = $('css-output');
      if (pre) pre.textContent = d.css;
    } catch (_) {}
  }

  function verCSS() {
    $('css-modal').classList.add('open');
    refreshCSS();
  }

  function cerrarCSS(e) {
    if (!e || e.target === $('css-modal') || e.currentTarget?.classList?.contains('ap-modal-close')) {
      $('css-modal').classList.remove('open');
    }
  }

  function copiarCSS() {
    const pre = $('css-output');
    if (!pre) return;
    navigator.clipboard.writeText(pre.textContent)
      .then(() => toast('CSS copiado al portapapeles'))
      .catch(() => toast('No se pudo copiar', false));
  }

  /* ── init ── */
  function init() {
    initNav();
    bindColors();
    bindFonts();
    initPresets();
    updateColorPreview();

    // bind espacio preview ranges
    ['radius_btn','radius_card','radius_input'].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener('input', previewEspacio);
    });
    previewEspacio();
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    guardarColores,
    guardarTipografia,
    guardarEspacio,
    guardarEfectos,
    guardarMovil,
    guardarSeccion,
    guardarActivo,
    previewEspacio,
    verCSS,
    cerrarCSS,
    copiarCSS,
  };
})();
