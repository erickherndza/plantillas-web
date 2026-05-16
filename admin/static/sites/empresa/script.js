// Script JavaScript para Codesign Architecture & interior Django HTML Template

// 1. initNavbarScroll()
/**
 * Agrega o quita la clase .navbar--scrolled según la posición de la ventana.
 */
function initNavbarScroll() {
  const navbar = document.querySelector('.navbar');
  const scrollY = window.scrollY;
  const requestAnimationFrameId = null;

  function updateNavbarScroll() {
    if (scrollY > 60) {
      navbar.classList.add('navbar--scrolled');
    } else {
      navbar.classList.remove('navbar--scrolled');
    }
  }

  window.addEventListener('scroll', () => {
    if (requestAnimationFrameId !== null) {
      window.cancelAnimationFrame(requestAnimationFrameId);
    }
    requestAnimationFrameId = window.requestAnimationFrame(updateNavbarScroll);
  });

  updateNavbarScroll();
}

// 2. initMobileMenu()
/**
 * Abre y cierra el menú de navegación en dispositivos móviles.
 */
function initMobileMenu() {
  const navToggle = document.querySelector('.nav-toggle');
  const navList = document.querySelector('.nav-list');
  const navLinks = document.querySelectorAll('.nav-list a');

  navToggle.addEventListener('click', () => {
    navList.classList.toggle('nav--open');
    navToggle.setAttribute('aria-expanded', navList.classList.contains('nav--open'));
  });

  navLinks.forEach((link) => {
    link.addEventListener('click', () => {
      navList.classList.remove('nav--open');
      navToggle.setAttribute('aria-expanded', false);
    });
  });

  document.addEventListener('click', (event) => {
    if (!navList.contains(event.target) && !navToggle.contains(event.target)) {
      navList.classList.remove('nav--open');
      navToggle.setAttribute('aria-expanded', false);
    }
  });
}

// 3. initSmoothScroll()
/**
 * Permite el desplazamiento suave a los enlaces internos.
 */
function initSmoothScroll() {
  const links = document.querySelectorAll('a[href^="#"]');

  links.forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const target = document.querySelector(link.getAttribute('href'));
      target.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

// 4. initFadeAnimations()
/**
 * Agrega animaciones de entrada para los elementos con la clase .fade-in-up.
 */
function initFadeAnimations() {
  const fadeUpElements = document.querySelectorAll('.fade-in-up');

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px',
    });

    fadeUpElements.forEach((element) => {
      observer.observe(element);
    });
  } else {
    fadeUpElements.forEach((element) => {
      element.classList.add('is-visible');
    });
  }
}

// 5. initContactForm()
/**
 * Valida y envía el formulario de contacto.
 */
function initContactForm() {
  const form = document.querySelector('#contact-form');
  const feedback = document.querySelector('.form-feedback');
  const submitButton = form.querySelector('button[type="submit"]');

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const name = form.querySelector('input[name="name"]').value;
    const email = form.querySelector('input[name="email"]').value;
    const message = form.querySelector('textarea[name="message"]').value;

    const requiredFields = ['name', 'email', 'message'];
    const errors = [];

    requiredFields.forEach((field) => {
      if (!name || !email || !message) {
        errors.push(field);
      }
    });

    if (errors.length > 0) {
      errors.forEach((error) => {
        feedback.querySelector(`.${error}-feedback`).classList.remove('hidden');
      });
    } else {
      submitButton.disabled = true;
      submitButton.textContent = 'Enviando...';

      setTimeout(() => {
        feedback.innerHTML = '<p>✅ Mensaje enviado. Te contactaremos pronto.</p>';
        form.reset();
        submitButton.disabled = false;
        submitButton.textContent = 'Enviar';
      }, 1800);
    }
  });
}

// 6. initCurrentYear()
/**
 * Actualiza el año actual en el elemento #current-year.
 */
function initCurrentYear() {
  const currentYear = document.querySelector('#current-year');
  currentYear.textContent = new Date().getFullYear();
}

// 7. initActiveNavLink()
/**
 * Agrega la clase .active a los enlaces del menú según la sección actual.
 */
function initActiveNavLink() {
  const navLinks = document.querySelectorAll('.nav-list a');
  const sections = document.querySelectorAll('section');

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const link = navLinks.find((link) => link.href === `#${entry.target.id}`);
          link.classList.add('active');
        }
      });
    }, {
      threshold: 0.4,
    });

    sections.forEach((section) => {
      observer.observe(section);
    });
  }
}

// Portfolio filters
function initPortfolioFilters() {
  const btns  = document.querySelectorAll('.filter-btn');
  const items = document.querySelectorAll('.portfolio-item');
  if (!btns.length) return;

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      items.forEach(item => {
        item.style.display = (filter === 'all' || item.dataset.cat === filter) ? '' : 'none';
      });
    });
  });
}

// DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  initNavbarScroll();
  initMobileMenu();
  initSmoothScroll();
  initFadeAnimations();
  initContactForm();
  initCurrentYear();
  initActiveNavLink();
  initPortfolioFilters();
});