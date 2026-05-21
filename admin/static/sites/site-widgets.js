/* site-widgets.js — Hero slider, carousel, lightbox */

// ── Hero Slider ──────────────────────────────────────────────────────────────
(function(){
  const track = document.getElementById('hs-track');
  if (!track) return;
  const slides = track.children;
  const total  = slides.length;
  if (total <= 1) return;
  let cur = 0;
  const dots = document.querySelectorAll('.hs-dot');
  const go = (n) => {
    cur = (n + total) % total;
    track.style.transform = `translateX(-${cur * 100}%)`;
    dots.forEach((d,i) => d.classList.toggle('active', i === cur));
  };
  document.getElementById('hs-prev')?.addEventListener('click', () => go(cur - 1));
  document.getElementById('hs-next')?.addEventListener('click', () => go(cur + 1));
  dots.forEach((d,i) => d.addEventListener('click', () => go(i)));
  // Autoplay
  const speed = parseInt(document.querySelector('.hs-hero')?.dataset.speed || '5000');
  if (speed > 0) setInterval(() => go(cur + 1), speed);
  // Touch swipe
  let sx = 0;
  track.addEventListener('touchstart', e => sx = e.touches[0].clientX, {passive:true});
  track.addEventListener('touchend',   e => { const dx = e.changedTouches[0].clientX - sx; if (Math.abs(dx)>40) go(cur + (dx<0?1:-1)); }, {passive:true});
})();

// ── Portfolio Carousel ───────────────────────────────────────────────────────
(function(){
  const carousel = document.getElementById('port-carousel');
  if (!carousel) return;
  const track = carousel.querySelector('.port-track');
  const items  = track.children;
  const perView = window.innerWidth <= 768 ? 1 : 3;
  let cur = 0;
  const maxIdx = Math.max(0, items.length - perView);
  const getW   = () => items[0].getBoundingClientRect().width + 20;
  const go = (n) => {
    cur = Math.max(0, Math.min(n, maxIdx));
    track.style.transform = `translateX(-${cur * getW()}px)`;
    document.getElementById('port-prev')?.classList.toggle('hidden', cur === 0);
    document.getElementById('port-next')?.classList.toggle('hidden', cur >= maxIdx);
  };
  document.getElementById('port-prev')?.addEventListener('click', () => go(cur - 1));
  document.getElementById('port-next')?.addEventListener('click', () => go(cur + 1));
  // Category filter
  document.querySelectorAll('.port-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const cat = btn.dataset.cat;
      document.querySelectorAll('.port-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      Array.from(items).forEach(item => {
        item.style.display = (cat === 'all' || item.dataset.cat === cat) ? '' : 'none';
      });
    });
  });
})();

// ── Lightbox ─────────────────────────────────────────────────────────────────
(function(){
  const box   = document.getElementById('lb-lightbox');
  if (!box) return;
  const img   = box.querySelector('.lb-lbox-img');
  const close = box.querySelector('.lb-lbox-close');
  const prev  = box.querySelector('.lb-lbox-prev');
  const next  = box.querySelector('.lb-lbox-next');
  let items = [], cur = 0;

  document.querySelectorAll('[data-lightbox]').forEach((el, i) => {
    el.style.cursor = 'zoom-in';
    el.addEventListener('click', () => {
      items = Array.from(document.querySelectorAll('[data-lightbox]'));
      cur   = items.indexOf(el);
      show(cur);
    });
  });
  const show = (n) => {
    cur = (n + items.length) % items.length;
    img.src = items[cur].dataset.lightbox || items[cur].src || items[cur].style.backgroundImage.replace(/url\(['"]?|['"]?\)/g,'');
    box.classList.add('open');
  };
  close?.addEventListener('click', () => box.classList.remove('open'));
  prev?.addEventListener('click',  () => show(cur - 1));
  next?.addEventListener('click',  () => show(cur + 1));
  box.addEventListener('click', e => { if (e.target === box) box.classList.remove('open'); });
  document.addEventListener('keydown', e => {
    if (!box.classList.contains('open')) return;
    if (e.key === 'Escape') box.classList.remove('open');
    if (e.key === 'ArrowLeft')  show(cur - 1);
    if (e.key === 'ArrowRight') show(cur + 1);
  });
})();

/* ── Galería Carrusel ─────────────────────────────────────────────────────── */
(function(){
  const wrap  = document.querySelector('.gal-carousel-wrap');
  if (!wrap) return;
  const track  = wrap.querySelector('.gal-track');
  const slides = Array.from(track.querySelectorAll('.gal-slide'));
  if (!slides.length) return;

  const dotsWrap = document.querySelector('.gal-dots');
  let cur = 0, slideW = 0, visible = 1;

  function calc(){
    slideW  = slides[0].offsetWidth + 24; // width + margin*2
    visible = Math.max(1, Math.floor(wrap.offsetWidth / slideW));
  }

  function goTo(idx){
    const max = Math.max(0, slides.length - visible);
    cur = Math.min(Math.max(idx, 0), max);
    track.style.transform = `translateX(-${cur * slideW}px)`;
    if (dotsWrap) dotsWrap.querySelectorAll('.gal-dot').forEach((d,i)=>
      d.classList.toggle('active', i===cur));
  }

  // dots
  if (dotsWrap){
    slides.forEach((_,i)=>{
      const d = document.createElement('span');
      d.className = 'gal-dot' + (i===0?' active':'');
      d.addEventListener('click',()=>goTo(i));
      dotsWrap.appendChild(d);
    });
  }

  // buttons
  const prev = document.getElementById('gal-prev');
  const next = document.getElementById('gal-next');
  if (prev) prev.addEventListener('click', ()=>goTo(cur-1));
  if (next) next.addEventListener('click', ()=>goTo(cur+1));

  // touch
  let tx=0;
  track.addEventListener('touchstart', e=>{ tx=e.touches[0].clientX; },{passive:true});
  track.addEventListener('touchend',   e=>{ const dx=e.changedTouches[0].clientX-tx; if(Math.abs(dx)>40) goTo(cur+(dx<0?1:-1)); },{passive:true});

  // autoplay
  let timer = setInterval(()=>goTo(cur+1 > slides.length-visible ? 0 : cur+1), 4000);
  wrap.addEventListener('mouseenter',()=>clearInterval(timer));
  wrap.addEventListener('mouseleave',()=>{ timer=setInterval(()=>goTo(cur+1>slides.length-visible?0:cur+1),4000); });

  calc();
  goTo(0);
  window.addEventListener('resize', ()=>{ calc(); goTo(cur); });
})();
