// ── MedCenter · Plantilla Doctores ──────────────────────────────────────────
// Módulos: Navbar, Fade, ActiveLink, Calendario, Horarios, Formulario → Google Calendar

// ── 1. Navbar ────────────────────────────────────────────────────────────────
function initNavbarScroll() {
  const navbar = document.querySelector('.navbar');
  let rafId = null;

  function update() {
    navbar.classList.toggle('navbar--scrolled', window.scrollY > 60);
  }

  window.addEventListener('scroll', () => {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(update);
  });

  update();
}

function initMobileMenu() {
  const toggle = document.querySelector('.nav-toggle');
  const list   = document.querySelector('.nav-list');

  toggle.addEventListener('click', () => {
    const open = list.classList.toggle('nav--open');
    toggle.setAttribute('aria-expanded', open);
  });

  list.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      list.classList.remove('nav--open');
      toggle.setAttribute('aria-expanded', false);
    });
  });

  document.addEventListener('click', e => {
    if (!list.contains(e.target) && !toggle.contains(e.target)) {
      list.classList.remove('nav--open');
    }
  });
}

// ── 2. Animaciones fade ──────────────────────────────────────────────────────
function initFadeAnimations() {
  const els = document.querySelectorAll('.fade-in-up');

  if (!('IntersectionObserver' in window)) {
    els.forEach(el => el.classList.add('is-visible'));
    return;
  }

  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  els.forEach(el => io.observe(el));
}

function initActiveNavLink() {
  const links    = Array.from(document.querySelectorAll('.nav-list a'));
  const sections = document.querySelectorAll('section[id]');

  if (!('IntersectionObserver' in window)) return;

  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      links.forEach(l => l.classList.toggle('active', l.getAttribute('href') === `#${entry.target.id}`));
    });
  }, { threshold: 0.4 });

  sections.forEach(s => io.observe(s));
}

// ── 3. Año footer ────────────────────────────────────────────────────────────
function initCurrentYear() {
  const el = document.querySelector('#current-year');
  if (el) el.textContent = new Date().getFullYear();
}

// ── 4. Calendario de citas ───────────────────────────────────────────────────

const CAL = {
  // Estado
  hoy:           new Date(),
  anio:          new Date().getFullYear(),
  mes:           new Date().getMonth(),   // 0-based
  fechaSeleccionada: null,
  horaSeleccionada:  null,

  // Horarios por tipo de día
  SLOTS_SEMANA: ['7:00', '7:30', '8:00', '8:30', '9:00', '9:30',
                 '10:00','10:30','11:00','11:30','12:00','12:30',
                 '14:00','14:30','15:00','15:30','16:00','16:30',
                 '17:00','17:30','18:00','18:30'],
  SLOTS_SABADO: ['8:00', '8:30', '9:00', '9:30', '10:00','10:30',
                 '11:00','11:30','12:00','12:30','13:00','13:30'],

  MESES: ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
          'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'],
  DIAS_LARGO: ['domingo','lunes','martes','miércoles','jueves','viernes','sábado'],
  MESES_GENITIVO: ['enero','febrero','marzo','abril','mayo','junio',
                   'julio','agosto','septiembre','octubre','noviembre','diciembre'],

  // ── Renderiza el grid del mes ──
  renderMes() {
    const titulo = document.getElementById('cal-title');
    const grid   = document.getElementById('cal-grid');

    titulo.textContent = `${this.MESES[this.mes]} ${this.anio}`;
    grid.innerHTML = '';

    // Día de la semana del 1ero (ajustar: 0=Dom → hacerlo 0=Lun)
    const primerDia  = new Date(this.anio, this.mes, 1).getDay();
    const offset     = (primerDia === 0) ? 6 : primerDia - 1;
    const diasMes    = new Date(this.anio, this.mes + 1, 0).getDate();
    const hoyStr     = this._fechaStr(this.hoy);

    // Celdas vacías
    for (let i = 0; i < offset; i++) {
      const empty = document.createElement('div');
      empty.className = 'cal-day empty';
      grid.appendChild(empty);
    }

    for (let d = 1; d <= diasMes; d++) {
      const fecha    = new Date(this.anio, this.mes, d);
      const fechaStr = this._fechaStr(fecha);
      const dow      = fecha.getDay(); // 0=Dom, 6=Sáb
      const esPasado = fecha < new Date(this.hoy.getFullYear(), this.hoy.getMonth(), this.hoy.getDate());

      const cell = document.createElement('button');
      cell.className = 'cal-day';
      cell.textContent = d;
      cell.setAttribute('data-fecha', fechaStr);

      if (dow === 0) {
        // Domingo
        cell.classList.add('domingo');
        cell.disabled = true;
        cell.title = 'Solo urgencias';
      } else if (esPasado) {
        cell.classList.add('disabled');
        cell.disabled = true;
      } else if (dow === 6) {
        cell.classList.add('limitado');
        cell.title = 'Horario reducido: 8am – 2pm';
      } else {
        cell.classList.add('disponible');
      }

      if (fechaStr === hoyStr) cell.classList.add('today');

      if (this.fechaSeleccionada && fechaStr === this._fechaStr(this.fechaSeleccionada)) {
        cell.classList.add('selected');
      }

      cell.addEventListener('click', () => this.seleccionarFecha(fecha));
      grid.appendChild(cell);
    }
  },

  // ── Seleccionar fecha ──
  seleccionarFecha(fecha) {
    this.fechaSeleccionada = fecha;
    this.horaSeleccionada  = null;

    // Actualizar pasos
    this._setStep(2);

    // Mostrar panel horarios
    document.getElementById('panel-calendario').classList.add('hidden');
    document.getElementById('panel-horarios').classList.remove('hidden');

    // Título del panel
    const dow      = this.DIAS_LARGO[fecha.getDay()];
    const mesNom   = this.MESES_GENITIVO[fecha.getMonth()];
    const titulo   = `${dow.charAt(0).toUpperCase() + dow.slice(1)}, ${fecha.getDate()} de ${mesNom}`;
    document.getElementById('horarios-fecha-titulo').textContent = titulo;

    this.renderHorarios(fecha.getDay() === 6);
  },

  // ── Renderiza slots de hora ──
  renderHorarios(esSabado) {
    const grid  = document.getElementById('horarios-grid');
    const slots = esSabado ? this.SLOTS_SABADO : this.SLOTS_SEMANA;
    grid.innerHTML = '';

    slots.forEach(hora => {
      const btn = document.createElement('button');
      btn.className = 'slot';
      btn.type = 'button';
      btn.textContent = hora;
      if (this.horaSeleccionada === hora) btn.classList.add('selected');
      btn.addEventListener('click', () => this.seleccionarHora(hora));
      grid.appendChild(btn);
    });
  },

  // ── Seleccionar hora ──
  seleccionarHora(hora) {
    this.horaSeleccionada = hora;

    // Marcar slot activo
    document.querySelectorAll('.slot').forEach(s => {
      s.classList.toggle('selected', s.textContent === hora);
    });

    // Mostrar formulario
    this._setStep(3);
    document.querySelector('.seleccion-resumen').classList.add('hidden');
    const form = document.getElementById('citas-form');
    form.classList.remove('hidden');

    // Badge
    const dow      = this.DIAS_LARGO[this.fechaSeleccionada.getDay()];
    const mesNom   = this.MESES_GENITIVO[this.fechaSeleccionada.getMonth()];
    document.getElementById('badge-fecha').textContent =
      `${dow.charAt(0).toUpperCase() + dow.slice(1)} ${this.fechaSeleccionada.getDate()} de ${mesNom}`;
    document.getElementById('badge-hora').textContent = hora;
  },

  // ── Volver al calendario ──
  volverCalendario() {
    document.getElementById('panel-horarios').classList.add('hidden');
    document.getElementById('panel-calendario').classList.remove('hidden');
    this.renderMes();
    this._setStep(1);
  },

  // ── Volver a horarios (desde el badge) ──
  volverHorarios() {
    document.getElementById('citas-form').classList.add('hidden');
    document.querySelector('.seleccion-resumen').classList.remove('hidden');
    document.getElementById('panel-calendario').classList.add('hidden');
    document.getElementById('panel-horarios').classList.remove('hidden');
    this._setStep(2);
  },

  // ── Helpers ──
  _fechaStr(fecha) {
    return `${fecha.getFullYear()}-${String(fecha.getMonth()+1).padStart(2,'0')}-${String(fecha.getDate()).padStart(2,'0')}`;
  },

  _setStep(n) {
    document.querySelectorAll('.step').forEach(s => {
      const num = parseInt(s.dataset.step);
      s.classList.toggle('active', num === n);
      s.classList.toggle('done', num < n);
    });
  },

  // ── Genera URL de Google Calendar ──
  buildGoogleCalendarURL({ nombre, telefono, email, especialidad, motivo }) {
    const fecha = this.fechaSeleccionada;
    const [hh, mm] = this.horaSeleccionada.split(':').map(Number);

    // Fecha inicio y fin (30 min)
    const inicio = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate(), hh, mm, 0);
    const fin    = new Date(inicio.getTime() + 30 * 60 * 1000);

    const fmt = d =>
      `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}` +
      `T${String(d.getHours()).padStart(2,'0')}${String(d.getMinutes()).padStart(2,'0')}00`;

    const detalles = [
      `Paciente: ${nombre}`,
      `Teléfono: ${telefono}`,
      email ? `Correo: ${email}` : '',
      `Especialidad: ${especialidad}`,
      motivo ? `Motivo: ${motivo}` : '',
      '',
      'Clínica MedCenter — Av. Abraham Lincoln 1205, Piantini, Santo Domingo',
    ].filter(Boolean).join('\n');

    const params = new URLSearchParams({
      action:   'TEMPLATE',
      text:     `Cita MedCenter · ${especialidad} — ${nombre}`,
      dates:    `${fmt(inicio)}/${fmt(fin)}`,
      details:  detalles,
      location: 'Av. Abraham Lincoln 1205, Piantini, Santo Domingo, Rep. Dom.',
    });

    return `https://calendar.google.com/calendar/render?${params.toString()}`;
  },

  // ── Init ──
  init() {
    this.renderMes();

    // Navegación mes
    document.getElementById('cal-prev').addEventListener('click', () => {
      this.mes--;
      if (this.mes < 0) { this.mes = 11; this.anio--; }
      this.renderMes();
    });

    document.getElementById('cal-next').addEventListener('click', () => {
      this.mes++;
      if (this.mes > 11) { this.mes = 0; this.anio++; }
      this.renderMes();
    });

    // Volver al calendario desde horarios
    document.getElementById('btn-back-cal').addEventListener('click', () => {
      this.volverCalendario();
    });

    // Badge cambiar → vuelve a horarios
    document.getElementById('badge-cambiar').addEventListener('click', () => {
      this.volverHorarios();
    });

    // Formulario → Google Calendar
    document.getElementById('citas-form').addEventListener('submit', e => {
      e.preventDefault();

      if (!this.fechaSeleccionada || !this.horaSeleccionada) {
        alert('Por favor selecciona una fecha y hora antes de continuar.');
        return;
      }

      const nombre      = document.getElementById('nombre-cita').value.trim();
      const telefono    = document.getElementById('telefono-cita').value.trim();
      const email       = document.getElementById('email-cita').value.trim();
      const especialidad = document.getElementById('especialidad-cita').value;
      const motivo      = document.getElementById('motivo-cita').value.trim();

      const url = this.buildGoogleCalendarURL({ nombre, telefono, email, especialidad, motivo });

      // Abrir Google Calendar en nueva pestaña
      window.open(url, '_blank', 'noopener,noreferrer');

      // Feedback
      this._setStep(4);
      const feedback = document.getElementById('form-feedback');
      feedback.className = 'form-feedback success';
      feedback.innerHTML = '✅ Se abrió Google Calendar con tu cita. Guárdala desde allá para recibirla en tu calendario.';

      // Reset suave
      const btn = e.target.querySelector('button[type="submit"]');
      btn.textContent = '✓ Abierto en Google Calendar';
      btn.disabled = true;
    });
  }
};

// ── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNavbarScroll();
  initMobileMenu();
  initFadeAnimations();
  initActiveNavLink();
  initCurrentYear();
  CAL.init();
});
