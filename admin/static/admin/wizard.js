/* ── Wizard JS — crear_plantilla_wizard.html ──────────────────────────── */

(function () {
  'use strict';

  const TOTAL_STEPS = 4;
  let currentStep = 1;

  // ── DOM refs ────────────────────────────────────────────────────────────
  const btnNext      = document.getElementById('btnNext');
  const btnBack      = document.getElementById('btnBack');
  const btnSubmit    = document.getElementById('btnSubmit');
  const progressBar  = document.getElementById('progressBar');
  const stepNumEl    = document.getElementById('currentStepNum');
  const wizardError  = document.getElementById('wizardError');
  const wizardSuccess = document.getElementById('wizardSuccess');

  // ── Navigation ──────────────────────────────────────────────────────────
  function showStep(n) {
    document.querySelectorAll('.wizard-step').forEach((s, i) => {
      s.classList.toggle('active', i + 1 === n);
    });
    document.querySelectorAll('.step-dot').forEach((d, i) => {
      d.classList.remove('active', 'done');
      if (i + 1 === n)   d.classList.add('active');
      if (i + 1 < n)     d.classList.add('done');
    });
    progressBar.style.width = (n / TOTAL_STEPS * 100) + '%';
    stepNumEl.textContent   = n;
    btnBack.style.visibility = n === 1 ? 'hidden' : 'visible';
    // Last step: hide Next, show Submit inside the step
    btnNext.style.display = n === TOTAL_STEPS ? 'none' : '';
  }

  function validateStep(n) {
    if (n === 1) {
      const nombre = document.getElementById('nombre').value.trim();
      const clave  = document.getElementById('clave').value.trim();
      if (!nombre) { showStepError('El nombre es obligatorio.'); return false; }
      if (!clave)  { showStepError('La clave es obligatoria.'); return false; }
      const pattern = /^[a-z][a-z0-9_-]{1,29}$/;
      if (!pattern.test(clave)) {
        showStepError('La clave no es válida. Solo letras minúsculas, números, guiones.');
        return false;
      }
    }
    hideStepError();
    return true;
  }

  function showStepError(msg) {
    wizardError.textContent = msg;
    wizardError.style.display = 'block';
  }
  function hideStepError() {
    wizardError.style.display = 'none';
    wizardError.textContent = '';
  }

  btnNext.addEventListener('click', () => {
    if (!validateStep(currentStep)) return;
    if (currentStep < TOTAL_STEPS) {
      currentStep++;
      showStep(currentStep);
    }
  });

  btnBack.addEventListener('click', () => {
    if (currentStep > 1) {
      currentStep--;
      showStep(currentStep);
      hideStepError();
    }
  });

  // ── Auto-slug desde nombre ───────────────────────────────────────────────
  const nombreInput = document.getElementById('nombre');
  const claveInput  = document.getElementById('clave');
  let claveManual = false;

  nombreInput.addEventListener('input', () => {
    if (claveManual) return;
    const slug = nombreInput.value.trim()
      .toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')  // quitar acentos
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9_-]/g, '')
      .slice(0, 30);
    claveInput.value = slug;
    validateClave(slug);
  });

  claveInput.addEventListener('input', () => {
    claveManual = true;
    validateClave(claveInput.value);
  });

  function validateClave(val) {
    const msg = document.getElementById('claveMsg');
    const pattern = /^[a-z][a-z0-9_-]{1,29}$/;
    if (!val) {
      msg.textContent = '';
      msg.className = 'wiz-validation';
    } else if (pattern.test(val)) {
      msg.textContent = 'Clave válida.';
      msg.className = 'wiz-validation ok';
    } else {
      msg.textContent = 'Solo letras minúsculas, números, guiones. Mínimo 2 caracteres, sin espacios.';
      msg.className = 'wiz-validation error';
    }
  }

  // ── Tabs Step 2 ─────────────────────────────────────────────────────────
  document.querySelectorAll('.wiz-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.wiz-tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.wiz-tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + tab).classList.add('active');
    });
  });

  // ── Color pickers sync ───────────────────────────────────────────────────
  function syncColorPicker(pickerId, textId) {
    const picker = document.getElementById(pickerId);
    const text   = document.getElementById(textId);
    if (!picker || !text) return;
    picker.addEventListener('input', () => { text.value = picker.value; });
    text.addEventListener('input', () => {
      if (/^#[0-9a-fA-F]{6}$/.test(text.value)) picker.value = text.value;
    });
  }
  syncColorPicker('colorPrimarioPicker', 'colorPrimario');
  syncColorPicker('colorAcentoPicker',   'colorAcento');
  syncColorPicker('colorFooterPicker',   'colorFooter');
  syncColorPicker('colorClaroPicker',    'colorClaro');

  // ── Scraper ─────────────────────────────────────────────────────────────
  const btnScraper     = document.getElementById('btnScraper');
  const scraperUrl     = document.getElementById('scraperUrl');
  const scraperResults = document.getElementById('scraperResults');
  const scraperColors  = document.getElementById('scraperColors');
  const scraperError   = document.getElementById('scraperError');
  const scraperLoading = document.getElementById('scraperLoading');

  let _scraperSelected = {};  // {role: hex}  role = 'primario' | 'acento' | 'footer'

  btnScraper && btnScraper.addEventListener('click', async () => {
    const url = scraperUrl.value.trim();
    if (!url) { scraperError.textContent = 'Ingresa una URL.'; scraperError.style.display = 'block'; return; }

    scraperError.style.display   = 'none';
    scraperResults.style.display = 'none';
    scraperLoading.style.display = 'block';

    try {
      const resp = await fetch('/admin/scraper/analizar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      });
      const data = await resp.json();
      scraperLoading.style.display = 'none';

      if (!data.ok) {
        scraperError.textContent   = data.error || 'No se pudo analizar el sitio.';
        scraperError.style.display = 'block';
        return;
      }

      // Render swatches
      const colores = data.colores || [];
      scraperColors.innerHTML = '';
      colores.forEach(hex => {
        const swatch = document.createElement('div');
        swatch.className = 'scraper-color-swatch';
        swatch.innerHTML = `<div class="scraper-swatch-box" style="background:${hex};"></div><span class="scraper-swatch-hex">${hex}</span>`;
        swatch.addEventListener('click', () => {
          swatch.classList.toggle('selected');
          // Aplicar colores en orden: primario, acento, footer
          applyScraperColors();
        });
        scraperColors.appendChild(swatch);
      });

      scraperResults.style.display = 'block';
    } catch(e) {
      scraperLoading.style.display = 'none';
      scraperError.textContent   = 'Error de red al contactar el servidor.';
      scraperError.style.display = 'block';
    }
  });

  function applyScraperColors() {
    const selected = [...document.querySelectorAll('.scraper-color-swatch.selected')]
      .map(s => s.querySelector('.scraper-swatch-hex').textContent);
    const roles = ['colorPrimario', 'colorAcento', 'colorFooter'];
    roles.forEach((id, i) => {
      if (selected[i]) {
        document.getElementById(id).value = selected[i];
        const pickerId = id + 'Picker';
        const picker = document.getElementById(pickerId);
        if (picker) picker.value = selected[i];
      }
    });
  }

  // ── Layout card highlight (already handled via :has CSS, but add JS for older browsers) ─
  document.querySelectorAll('.wiz-layout-options').forEach(group => {
    group.querySelectorAll('.layout-card').forEach(card => {
      card.addEventListener('click', () => {
        group.querySelectorAll('.layout-card').forEach(c => c.classList.remove('_selected'));
        card.classList.add('_selected');
      });
    });
  });

  // ── Form submit ──────────────────────────────────────────────────────────
  document.getElementById('wizardForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    hideStepError();
    wizardSuccess.style.display = 'none';

    if (btnSubmit) { btnSubmit.disabled = true; btnSubmit.textContent = 'Creando...'; }

    // Gather data
    const nombre      = document.getElementById('nombre').value.trim();
    const clave       = document.getElementById('clave').value.trim();
    const tipo        = document.querySelector('input[name="tipo"]:checked')?.value || 'landing';
    const descripcion = document.getElementById('descripcion').value.trim();

    const colorPrimario  = document.getElementById('colorPrimario').value || '#185FA5';
    const colorAcento    = document.getElementById('colorAcento').value   || '#0088CC';
    const colorFooterBg  = document.getElementById('colorFooter').value   || '#0A0F1E';
    const fuenteTitulos  = document.getElementById('fuenteTitulos').value;
    const fuenteCuerpo   = document.getElementById('fuenteCuerpo').value;

    const layout = {
      hero:     document.querySelector('input[name="layout_hero"]:checked')?.value     || 'fullscreen',
      services: document.querySelector('input[name="layout_services"]:checked')?.value || 'grid',
      projects: document.querySelector('input[name="layout_projects"]:checked')?.value || 'grid',
      team:     document.querySelector('input[name="layout_team"]:checked')?.value     || 'cards',
    };

    const defaults = {
      hero_eyebrow:          document.getElementById('heroEyebrow').value.trim(),
      hero_titulo:           document.getElementById('heroTitulo').value.trim(),
      hero_subtitulo:        document.getElementById('heroSubtitulo').value.trim(),
      hero_cta_texto:        document.getElementById('heroCtaTexto').value.trim(),
      menu_servicios:        document.getElementById('menuServicios').value.trim(),
      menu_proyectos:        document.getElementById('menuProyectos').value.trim(),
      menu_equipo:           document.getElementById('menuEquipo').value.trim(),
      nosotros_descripcion:  document.getElementById('nosotrosDesc').value.trim(),
      nosotros_mision:       document.getElementById('nosotrosMision').value.trim(),
    };

    const payload = {
      nombre, clave, tipo, descripcion,
      color_primario: colorPrimario, color_acento: colorAcento,
      color_footer_bg: colorFooterBg,
      fuente_titulos: fuenteTitulos, fuente_cuerpo: fuenteCuerpo,
      layout, defaults
    };

    try {
      const resp = await fetch('/admin/plantillas/wizard/crear', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (data.ok) {
        wizardSuccess.textContent  = 'Plantilla creada correctamente. Redirigiendo...';
        wizardSuccess.style.display = 'block';
        setTimeout(() => { window.location.href = data.redirect || '/admin/plantillas'; }, 1200);
      } else {
        showStepError(data.error || 'Error al crear la plantilla.');
        if (btnSubmit) { btnSubmit.disabled = false; btnSubmit.textContent = 'Crear plantilla'; }
      }
    } catch(err) {
      showStepError('Error de red. Intenta de nuevo.');
      if (btnSubmit) { btnSubmit.disabled = false; btnSubmit.textContent = 'Crear plantilla'; }
    }
  });

  // Init
  showStep(1);

})();
