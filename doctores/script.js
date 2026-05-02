// Script — Plantilla Doctores / MedCenter

function initNavbarScroll() {
  const navbar = document.querySelector('.navbar');
  let rafId = null;

  function update() {
    if (window.scrollY > 60) {
      navbar.classList.add('navbar--scrolled');
    } else {
      navbar.classList.remove('navbar--scrolled');
    }
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
      toggle.setAttribute('aria-expanded', false);
    }
  });
}

function initFadeAnimations() {
  const elements = document.querySelectorAll('.fade-in-up');

  if (!('IntersectionObserver' in window)) {
    elements.forEach(el => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  elements.forEach(el => observer.observe(el));
}

function initActiveNavLink() {
  const links    = document.querySelectorAll('.nav-list a');
  const sections = document.querySelectorAll('section[id]');

  if (!('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      links.forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === `#${entry.target.id}`);
      });
    });
  }, { threshold: 0.4 });

  sections.forEach(section => observer.observe(section));
}

function initCitasForm() {
  const form     = document.querySelector('#citas-form');
  const feedback = document.querySelector('#form-feedback');
  if (!form) return;

  // Bloquear fechas pasadas
  const dateInput = form.querySelector('input[type="date"]');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.setAttribute('min', today);
  }

  form.addEventListener('submit', e => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Enviando solicitud...';

    setTimeout(() => {
      feedback.className = 'form-feedback success';
      feedback.innerHTML = '✅ Solicitud recibida. Te contactaremos dentro de las próximas 2 horas para confirmar tu cita.';
      form.reset();
      btn.disabled = false;
      btn.textContent = 'Solicitar cita';
    }, 1800);
  });
}

function initCurrentYear() {
  const el = document.querySelector('#current-year');
  if (el) el.textContent = new Date().getFullYear();
}

document.addEventListener('DOMContentLoaded', () => {
  initNavbarScroll();
  initMobileMenu();
  initFadeAnimations();
  initActiveNavLink();
  initCitasForm();
  initCurrentYear();
});
