"""
css_engine.py — Motor de generación CSS para el CMS de plantillas-web
Recibe design_tokens + section_variants → produce custom_css completo.

Almacenamiento en configuracion_sitio (clave/valor):
  design_tokens   → JSON string
  section_variants→ JSON string
  custom_css      → CSS generado (se inyecta en <head>)
  css_version     → entero, incrementa en cada rebuild
"""

import json
from db import get_db, set_config_sitio, get_config_sitio

# ── Helpers ───────────────────────────────────────────────────────────────────

def card_hover_css(tokens: dict) -> str:
    ch = tokens['effects']['card_hover']
    if ch == 'lift':   return "transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.25);"
    if ch == 'glow':   return "box-shadow:0 0 0 2px var(--color-primary);"
    if ch == 'border': return "border-color:var(--color-primary);"
    return ""


def _radius(tokens: dict) -> str:
    r = tokens['shape']['radius']
    return {'sharp': '4px', 'rounded': '12px', 'pill': '999px'}.get(r, '12px')


def _section_pad(tokens: dict) -> str:
    d = tokens['spacing']['density']
    return {'compact': '48px', 'normal': '72px', 'airy': '96px'}.get(d, '72px')


def _font_size(tokens: dict) -> str:
    s = tokens['typography']['scale']
    return {'compact': '15px', 'normal': '16px', 'large': '17px'}.get(s, '16px')


def _border_color(tokens: dict) -> str:
    bs = tokens['shape']['border_style']
    mode = tokens['colors']['mode']
    if bs == 'none':   return 'transparent'
    if bs == 'strong': return 'rgba(255,255,255,.30)' if mode == 'dark' else 'rgba(0,0,0,.30)'
    return 'rgba(255,255,255,.10)' if mode == 'dark' else 'rgba(0,0,0,.10)'


def _is_dark(tokens: dict) -> bool:
    return tokens['colors']['mode'] == 'dark'


def _surface(tokens: dict) -> str:
    """Color de superficie para cards en modo dark/light."""
    return 'rgba(255,255,255,.05)' if _is_dark(tokens) else 'rgba(0,0,0,.04)'


def _gf_url(*families: str) -> str:
    """Genera URL de Google Fonts para las familias dadas."""
    parts = [f.replace(' ', '+') + ':wght@300;400;600;700' for f in dict.fromkeys(families)]
    return f"https://fonts.googleapis.com/css2?{'&'.join('family=' + p for p in parts)}&display=swap"


# ── Generadores base ──────────────────────────────────────────────────────────

def generate_root(tokens: dict) -> str:
    c  = tokens['colors']
    ty = tokens['typography']
    sp = tokens['spacing']

    fonts_url = _gf_url(ty['display'], ty['body'])

    return f"""@import url('{fonts_url}');

:root {{
  /* Colores */
  --color-primary:   {c['primary']};
  --color-secondary: {c['secondary']};
  --color-accent:    {c['accent']};
  --color-neutral:   {c['neutral']};
  --color-bg:        {c['secondary']};
  --color-text:      {c['neutral']};
  --color-surface:   {_surface(tokens)};
  --color-border:    {_border_color(tokens)};

  /* Tipografía */
  --font-display: '{ty['display']}', Georgia, serif;
  --font-body:    '{ty['body']}', system-ui, sans-serif;
  --font-size-base: {_font_size(tokens)};
  --font-weight-display: {ty['weight_display']};

  /* Forma */
  --radius: {_radius(tokens)};
  --radius-sm: calc(var(--radius) / 2);
  --radius-lg: calc(var(--radius) * 1.5);

  /* Espaciado */
  --section-pad: {_section_pad(tokens)};
  --container-max: {sp['container_max']};
  --gap: 24px;

  /* Efectos */
  --transition: 0.25s ease;
  --shadow-sm: 0 2px 8px rgba(0,0,0,.12);
  --shadow-md: 0 8px 24px rgba(0,0,0,.18);
  --shadow-lg: 0 16px 48px rgba(0,0,0,.24);
}}
"""


def generate_base(tokens: dict) -> str:
    text_color  = 'var(--color-text)'
    bg_color    = 'var(--color-bg)'
    font_size   = _font_size(tokens)

    return f"""
/* ── Reset & Base ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: var(--font-body);
  font-size: {font_size};
  line-height: 1.65;
  color: {text_color};
  background-color: {bg_color};
  -webkit-font-smoothing: antialiased;
}}

a {{ color: var(--color-primary); text-decoration: none; transition: color var(--transition); }}
a:hover {{ color: var(--color-accent); }}

img {{ max-width: 100%; height: auto; display: block; }}

/* Contenedor principal */
.container {{
  width: 100%;
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: 24px;
}}

/* Secciones */
.section-inner {{
  padding-block: var(--section-pad);
}}

.section-header {{
  text-align: center;
  margin-bottom: 48px;
}}

.section-label {{
  display: inline-block;
  font-family: var(--font-body);
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 10px;
}}

.section-title {{
  font-family: var(--font-display);
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: var(--font-weight-display);
  color: var(--color-text);
  line-height: 1.2;
  margin-bottom: 12px;
}}

.section-subtitle {{
  font-size: 1.05rem;
  opacity: .75;
  max-width: 580px;
  margin-inline: auto;
}}
"""


def generate_breadcrumb(tokens: dict) -> str:
    return """
/* ── Breadcrumb ── */
.breadcrumb {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  list-style: none;
  padding: 12px 0;
  font-size: .875rem;
  opacity: .75;
}}

.breadcrumb li:not(:last-child)::after {{
  content: '›';
  margin-left: 4px;
  opacity: .5;
}}

.breadcrumb li:last-child {{
  color: var(--color-primary);
  font-weight: 600;
}}

.breadcrumb a:hover {{ text-decoration: underline; }}
""".format()


def generate_buttons(tokens: dict) -> str:
    hover_primary = card_hover_css(tokens) if tokens['effects']['card_hover'] == 'lift' else "transform:translateY(-2px);box-shadow:var(--shadow-md);"

    return f"""
/* ── Botones ── */
.btn-primary,
.btn-secondary,
.btn-outline {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: .65em 1.5em;
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: .95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition);
  border: 2px solid transparent;
  text-decoration: none;
  white-space: nowrap;
}}

.btn-primary {{
  background: var(--color-primary);
  color: var(--color-secondary);
  border-color: var(--color-primary);
}}
.btn-primary:hover {{
  {hover_primary}
  color: var(--color-secondary);
}}

.btn-secondary {{
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
}}
.btn-secondary:hover {{
  filter: brightness(1.15);
  transform: translateY(-2px);
}}

.btn-outline {{
  background: transparent;
  color: var(--color-primary);
  border-color: var(--color-primary);
}}
.btn-outline:hover {{
  background: var(--color-primary);
  color: var(--color-secondary);
}}
"""


# ── Header variantes ──────────────────────────────────────────────────────────

def _header_base(cfg: dict, tokens: dict) -> str:
    """Estilos compartidos entre todas las variantes de header."""
    is_dark = _is_dark(tokens)
    topbar  = cfg.get('topbar', False)
    sticky  = cfg.get('sticky', True)
    glass   = cfg.get('glass', False)

    topbar_css = ""
    if topbar:
        topbar_css = """
.topbar {
  background: var(--color-primary);
  color: var(--color-secondary);
  font-size: .8rem;
  padding: 6px 0;
  text-align: center;
}"""

    glass_css = "backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);" if glass else ""
    sticky_css = "position:sticky;top:0;z-index:100;" if sticky else ""
    bg_css = f"background:{'rgba(10,15,30,.72)' if is_dark else 'rgba(255,255,255,.82)'};" if glass else "background:var(--color-secondary);"

    return f"""
{topbar_css}
.site-header {{
  {sticky_css}
  {bg_css}
  {glass_css}
  border-bottom:1px solid var(--color-border);
  padding-block: 14px;
  z-index: 100;
  transition: background var(--transition), box-shadow var(--transition);
}}
.navbar--scrolled {{
  box-shadow: var(--shadow-sm);
}}
.header-brand {{
  font-family: var(--font-display);
  font-weight: var(--font-weight-display);
  font-size: 1.3rem;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 10px;
}}
.header-brand img {{ height: 40px; width: auto; }}
.nav-list {{
  display: flex;
  align-items: center;
  gap: 28px;
  list-style: none;
}}
.nav-list a {{
  color: var(--color-text);
  font-size: .9rem;
  font-weight: 500;
  opacity: .8;
  transition: opacity var(--transition), color var(--transition);
}}
.nav-list a:hover {{ opacity: 1; color: var(--color-primary); }}
.nav-list a.active {{ color: var(--color-primary); opacity: 1; }}
.header-contact {{
  font-size: .85rem;
  opacity: .7;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.nav-toggle {{
  display: none;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  background: none;
  border: none;
  padding: 4px;
}}
.nav-toggle span {{
  display: block;
  width: 22px;
  height: 2px;
  background: var(--color-text);
  border-radius: 2px;
  transition: transform var(--transition);
}}"""


def header_centered(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: centered */
.site-header .container {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 24px;
}
.site-header .header-brand  { grid-column: 1; justify-self: start; }
.site-header .navbar        { grid-column: 2; }
.site-header .header-contact{ grid-column: 3; justify-self: end; }
"""


def header_left(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: left */
.site-header .container {
  display: flex;
  align-items: center;
  gap: 32px;
}
.site-header .navbar { flex: 0 0 auto; }
.site-header .header-contact { margin-left: auto; }
"""


def header_boxed(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: boxed */
.site-header { background: transparent; border-bottom: none; }
.site-header .container {
  display: flex;
  align-items: center;
  gap: 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 10px 24px;
  margin-top: 12px;
  backdrop-filter: blur(12px);
}
.site-header .header-contact { margin-left: auto; }
"""


def header_stacked(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: stacked */
.site-header .container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.site-header .header-contact { order: 3; }
"""


def header_minimal(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: minimal */
.site-header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.site-header .navbar {
  display: none;
  position: fixed;
  inset: 0;
  background: var(--color-bg);
  z-index: 200;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.site-header .navbar.is-open { display: flex; }
.nav-toggle { display: flex; z-index: 201; }
"""


def header_split(cfg: dict, tokens: dict) -> str:
    return _header_base(cfg, tokens) + """
/* Header: split */
.site-header .container {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
}
.site-header .header-brand { grid-column: 2; justify-self: center; }
.site-header .nav-left     { grid-column: 1; justify-self: end; display: flex; gap: 24px; list-style: none; }
.site-header .nav-right    { grid-column: 3; justify-self: start; display: flex; gap: 24px; list-style: none; }
"""


# ── Hero variantes ────────────────────────────────────────────────────────────

def _hero_base(tokens: dict) -> str:
    return """
.hero-section {
  position: relative;
  overflow: hidden;
}
.hero-eyebrow {
  display: inline-block;
  font-size: .8rem;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 14px;
}
.hero-title {
  font-family: var(--font-display);
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: var(--font-weight-display);
  line-height: 1.1;
  color: var(--color-text);
  margin-bottom: 18px;
}
.hero-subtitle {
  font-size: clamp(1rem, 2vw, 1.15rem);
  opacity: .75;
  max-width: 540px;
  margin-bottom: 32px;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
}
"""


def hero_full(cfg: dict, tokens: dict) -> str:
    glow = ""
    if tokens['effects']['hero_glow']:
        p = tokens['colors']['primary']
        glow = f"background: radial-gradient(ellipse at 50% 50%, {p}22 0%, transparent 70%);"

    return _hero_base(tokens) + f"""
/* Hero: full */
.hero-section {{
  min-height: min(100vh, 800px);
  display: flex;
  align-items: center;
  {glow}
  padding-block: 80px;
}}
.hero-content {{
  text-align: center;
  max-width: 720px;
  margin-inline: auto;
}}
.hero-subtitle {{ margin-inline: auto; }}
.hero-actions {{ justify-content: center; }}
"""


def hero_compact(cfg: dict, tokens: dict) -> str:
    return _hero_base(tokens) + """
/* Hero: compact */
.hero-section {
  padding: 56px 32px 48px;
  text-align: center;
}
.hero-content { max-width: 640px; margin-inline: auto; }
.hero-subtitle { margin-inline: auto; }
.hero-actions { justify-content: center; }
"""


def hero_split(cfg: dict, tokens: dict) -> str:
    return _hero_base(tokens) + """
/* Hero: split */
.hero-section { padding-block: 80px; }
.hero-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  align-items: center;
}
.hero-text { /* primer hijo */ }
.hero-image {
  border-radius: var(--radius-lg);
  overflow: hidden;
  aspect-ratio: 4/3;
  object-fit: cover;
  width: 100%;
}
"""


def hero_video(cfg: dict, tokens: dict) -> str:
    return _hero_base(tokens) + """
/* Hero: video */
.hero-section {
  position: relative;
  min-height: min(100vh, 800px);
  display: flex;
  align-items: center;
  color: #fff;
}
.hero-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.hero-bg video,
.hero-bg img { width: 100%; height: 100%; object-fit: cover; }
.hero-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(var(--color-secondary), .65);
}
.hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
  max-width: 720px;
  margin-inline: auto;
}
.hero-title, .hero-subtitle, .hero-eyebrow { color: #fff !important; }
.hero-actions { justify-content: center; }
"""


# ── Servicios variantes ───────────────────────────────────────────────────────

def _card_base(tokens: dict) -> str:
    hover = card_hover_css(tokens)
    return f"""
.service-card,
.team-card,
.portfolio-card {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 28px 24px;
  transition: all var(--transition);
}}
.service-card:hover,
.team-card:hover,
.portfolio-card:hover {{ {hover} }}
"""


def services_grid3(cfg: dict, tokens: dict) -> str:
    return _card_base(tokens) + f"""
/* Services: grid3 */
.services-section {{ padding-block: var(--section-pad); }}
.services-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--gap);
}}
.service-icon {{
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  font-size: 1.4rem;
  margin-bottom: 16px;
}}
.service-title {{
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text);
}}
.service-desc {{ font-size: .9rem; opacity: .75; }}
"""


def services_grid2(cfg: dict, tokens: dict) -> str:
    return _card_base(tokens) + """
/* Services: grid2 */
.services-section { padding-block: var(--section-pad); }
.services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--gap);
}
.service-icon {
  width: 48px; height: 48px;
  background: var(--color-primary);
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.4rem; margin-bottom: 16px;
}
.service-title { font-family: var(--font-display); font-size: 1.15rem; font-weight: 600; margin-bottom: 8px; }
.service-desc { font-size: .95rem; opacity: .75; }
"""


def services_list(cfg: dict, tokens: dict) -> str:
    return """
/* Services: list */
.services-section { padding-block: var(--section-pad); }
.services-grid { display: flex; flex-direction: column; gap: 20px; }
.service-card {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 20px 24px;
  transition: all var(--transition);
}
.service-icon {
  flex-shrink: 0;
  width: 48px; height: 48px;
  background: var(--color-primary);
  color: var(--color-secondary);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
}
.service-title { font-weight: 600; margin-bottom: 6px; }
.service-desc { font-size: .9rem; opacity: .75; }
"""


def services_tabs(cfg: dict, tokens: dict) -> str:
    return """
/* Services: tabs */
.services-section { padding-block: var(--section-pad); }
.services-tabs { display: flex; gap: 4px; border-bottom: 2px solid var(--color-border); margin-bottom: 32px; }
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: .9rem;
  color: var(--color-text);
  opacity: .6;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--transition);
}
.tab-btn.active { opacity: 1; border-bottom-color: var(--color-primary); color: var(--color-primary); font-weight: 600; }
.service-panel { display: none; }
.service-panel.active { display: block; }
"""


# ── Nosotros variantes ────────────────────────────────────────────────────────

def about_mvv(cfg: dict, tokens: dict) -> str:
    return f"""
/* About: mvv */
.about-section {{ padding-block: var(--section-pad); }}
.mvv-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--gap);
  margin-top: 48px;
}}
.mvv-card {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 32px 24px;
  text-align: center;
  transition: all var(--transition);
}}
.mvv-card:hover {{ {card_hover_css(tokens)} }}
.mvv-icon {{
  font-size: 2rem;
  margin-bottom: 16px;
  color: var(--color-primary);
  display: block;
}}
.mvv-card-title {{
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--color-text);
}}
"""


def about_text_photo(cfg: dict, tokens: dict) -> str:
    return """
/* About: text_photo */
.about-section { padding-block: var(--section-pad); }
.about-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  align-items: center;
}
.about-image {
  border-radius: var(--radius-lg);
  overflow: hidden;
  aspect-ratio: 4/3;
}
.about-image img { width: 100%; height: 100%; object-fit: cover; }
.about-text h2 { font-family: var(--font-display); font-size: 2rem; font-weight: var(--font-weight-display); margin-bottom: 20px; }
.about-text p { opacity: .8; line-height: 1.7; margin-bottom: 16px; }
"""


def about_timeline(cfg: dict, tokens: dict) -> str:
    return """
/* About: timeline */
.about-section { padding-block: var(--section-pad); }
.timeline { position: relative; padding-left: 32px; }
.timeline::before {
  content: '';
  position: absolute;
  left: 8px; top: 0; bottom: 0;
  width: 2px;
  background: var(--color-primary);
  opacity: .3;
}
.timeline-item { position: relative; margin-bottom: 40px; }
.timeline-item::before {
  content: '';
  position: absolute;
  left: -28px; top: 4px;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--color-primary);
}
.timeline-year { font-size: .8rem; font-weight: 700; color: var(--color-primary); margin-bottom: 4px; }
.timeline-title { font-weight: 600; margin-bottom: 6px; }
.timeline-desc { font-size: .9rem; opacity: .75; }
"""


# ── Equipo variantes ──────────────────────────────────────────────────────────

def team_avatars(cfg: dict, tokens: dict) -> str:
    return f"""
/* Team: avatars */
.team-section {{ padding-block: var(--section-pad); }}
.team-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--gap);
}}
.team-card {{
  text-align: center;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 32px 20px 24px;
  transition: all var(--transition);
}}
.team-card:hover {{ {card_hover_css(tokens)} }}
.team-avatar {{
  width: 80px; height: 80px;
  border-radius: 50%;
  object-fit: cover;
  margin: 0 auto 16px;
  border: 3px solid var(--color-primary);
}}
.team-name {{ font-family: var(--font-display); font-weight: 600; font-size: 1rem; margin-bottom: 4px; }}
.team-role {{ font-size: .85rem; color: var(--color-primary); }}
"""


def team_list(cfg: dict, tokens: dict) -> str:
    return """
/* Team: list */
.team-section { padding-block: var(--section-pad); }
.team-grid { display: flex; flex-direction: column; gap: 16px; }
.team-card {
  display: flex;
  align-items: center;
  gap: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 16px 24px;
}
.team-avatar { width: 56px; height: 56px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.team-name { font-weight: 600; margin-bottom: 2px; }
.team-role { font-size: .85rem; color: var(--color-primary); }
"""


def team_cards_large(cfg: dict, tokens: dict) -> str:
    return f"""
/* Team: cards_large */
.team-section {{ padding-block: var(--section-pad); }}
.team-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--gap);
}}
.team-card {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all var(--transition);
}}
.team-card:hover {{ {card_hover_css(tokens)} }}
.team-avatar {{
  width: 100%;
  aspect-ratio: 3/4;
  object-fit: cover;
  display: block;
}}
.team-info {{ padding: 20px; }}
.team-name {{ font-family: var(--font-display); font-size: 1.15rem; font-weight: 600; margin-bottom: 4px; }}
.team-role {{ font-size: .85rem; color: var(--color-primary); }}
"""


# ── Portfolio variantes ───────────────────────────────────────────────────────

def portfolio_grid(cfg: dict, tokens: dict) -> str:
    return f"""
/* Portfolio: grid */
.portfolio-section {{ padding-block: var(--section-pad); }}
.portfolio-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--gap);
}}
.portfolio-card {{
  position: relative;
  border-radius: var(--radius);
  overflow: hidden;
  aspect-ratio: 4/3;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  transition: all var(--transition);
}}
.portfolio-card:hover {{ {card_hover_css(tokens)} }}
.portfolio-card img {{ width: 100%; height: 100%; object-fit: cover; }}
.portfolio-overlay {{
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,.7) 0%, transparent 60%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 20px;
  opacity: 0;
  transition: opacity var(--transition);
}}
.portfolio-card:hover .portfolio-overlay {{ opacity: 1; }}
.portfolio-title {{ color: #fff; font-weight: 600; margin-bottom: 4px; }}
.portfolio-category {{ color: var(--color-primary); font-size: .8rem; }}
"""


def portfolio_masonry(cfg: dict, tokens: dict) -> str:
    return portfolio_grid(cfg, tokens).replace('/* Portfolio: grid */', '/* Portfolio: masonry */').replace(
        'aspect-ratio: 4/3;', ''
    )


# ── Testimonials variantes ────────────────────────────────────────────────────

def testimonials_cards(cfg: dict, tokens: dict) -> str:
    return f"""
/* Testimonials: cards */
.testimonials-section {{ padding-block: var(--section-pad); }}
.testimonials-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--gap);
}}
.testimonial-card {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 28px 24px;
  transition: all var(--transition);
}}
.testimonial-card:hover {{ {card_hover_css(tokens)} }}
.testimonial-text {{
  font-size: .95rem;
  line-height: 1.7;
  opacity: .85;
  margin-bottom: 20px;
  font-style: italic;
}}
.testimonial-text::before {{ content: '"'; color: var(--color-primary); font-size: 1.5rem; }}
.testimonial-author {{ font-weight: 600; font-size: .9rem; }}
.testimonial-role {{ font-size: .8rem; opacity: .6; }}
"""


def testimonials_slider(cfg: dict, tokens: dict) -> str:
    return testimonials_cards(cfg, tokens).replace('/* Testimonials: cards */', '/* Testimonials: slider */')


# ── CTA variantes ─────────────────────────────────────────────────────────────

def cta_flex(cfg: dict, tokens: dict) -> str:
    return """
/* CTA: flex */
.cta-section { padding-block: var(--section-pad); }
.cta-strip {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.cta-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 40px 48px;
  flex-wrap: wrap;
}
.cta-inner .cta-text { flex: 1; min-width: 240px; }
.cta-inner h2 { font-family: var(--font-display); font-size: 1.75rem; color: var(--color-secondary); margin-bottom: 8px; }
.cta-inner p  { color: var(--color-secondary); opacity: .85; }
.cta-inner .btn-primary {
  background: var(--color-secondary);
  color: var(--color-primary);
  border-color: var(--color-secondary);
  flex-shrink: 0;
}
"""


def cta_centered(cfg: dict, tokens: dict) -> str:
    return """
/* CTA: centered */
.cta-section { padding-block: var(--section-pad); }
.cta-strip {
  background: rgba(var(--color-primary-rgb, 0,212,160), .08);
  border: 1px solid rgba(var(--color-primary-rgb, 0,212,160), .25);
  border-radius: var(--radius-lg);
  text-align: center;
}
.cta-inner { padding: 56px 40px; }
.cta-inner h2 { font-family: var(--font-display); font-size: 2rem; margin-bottom: 14px; }
.cta-inner p  { opacity: .75; margin-bottom: 28px; max-width: 480px; margin-inline: auto; }
.cta-inner .btn-primary { margin-inline: auto; }
"""


def cta_bg_image(cfg: dict, tokens: dict) -> str:
    return """
/* CTA: bg_image */
.cta-section {
  padding-block: var(--section-pad);
  position: relative;
  overflow: hidden;
}
.cta-section .cta-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.cta-section .cta-bg img { width: 100%; height: 100%; object-fit: cover; }
.cta-section .cta-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,.7);
}
.cta-strip { position: relative; z-index: 1; }
.cta-inner { text-align: center; padding: 56px 40px; }
.cta-inner h2, .cta-inner p { color: #fff; }
.cta-inner h2 { font-family: var(--font-display); font-size: 2rem; margin-bottom: 14px; }
.cta-inner p  { opacity: .85; margin-bottom: 28px; }
"""


# ── Contacto variantes ────────────────────────────────────────────────────────

def _form_base() -> str:
    return """
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.form-group label { font-size: .85rem; font-weight: 600; opacity: .8; }
.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: .65em 1em;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-body);
  font-size: .95rem;
  transition: border-color var(--transition);
}
.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0,212,160,.12);
}
.form-group textarea { min-height: 120px; resize: vertical; }
.form-feedback { font-size: .85rem; margin-top: 8px; display: none; }
.form-feedback.success { color: #22c55e; display: block; }
.form-feedback.error   { color: #ef4444; display: block; }
"""


def contact_form_info(cfg: dict, tokens: dict) -> str:
    return _form_base() + """
/* Contact: form_info */
.contact-section { padding-block: var(--section-pad); }
.contact-grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 48px;
  align-items: start;
}
.contact-info { display: flex; flex-direction: column; gap: 20px; }
.contact-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.contact-item .icon {
  flex-shrink: 0;
  width: 40px; height: 40px;
  background: var(--color-primary);
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
}
.contact-item .label { font-weight: 600; font-size: .85rem; margin-bottom: 2px; }
.contact-item .value { opacity: .75; font-size: .9rem; }
.contact-form { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 32px; }
"""


def contact_form_only(cfg: dict, tokens: dict) -> str:
    return _form_base() + """
/* Contact: form_only */
.contact-section { padding-block: var(--section-pad); }
.contact-form {
  max-width: 640px;
  margin-inline: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 40px;
}
"""


def contact_map_form(cfg: dict, tokens: dict) -> str:
    return _form_base() + """
/* Contact: map_form */
.contact-section { padding-block: var(--section-pad); }
.contact-map {
  width: 100%;
  height: 320px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 40px;
  border: 1px solid var(--color-border);
}
.contact-map iframe { width: 100%; height: 100%; border: none; }
.contact-grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 48px;
  align-items: start;
}
.contact-info { display: flex; flex-direction: column; gap: 20px; }
.contact-form { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 32px; }
"""


# ── Footer variantes ──────────────────────────────────────────────────────────

def _footer_base(tokens: dict) -> str:
    is_dark = _is_dark(tokens)
    bg = 'rgba(0,0,0,.25)' if is_dark else 'rgba(0,0,0,.04)'
    return f"""
.site-footer {{
  background: {bg};
  border-top: 1px solid var(--color-border);
  padding-block: 48px 24px;
}}
.footer-brand {{
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: var(--font-weight-display);
  color: var(--color-text);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}}
.footer-brand img {{ height: 36px; width: auto; }}
.footer-desc {{ font-size: .875rem; opacity: .65; max-width: 280px; line-height: 1.6; }}
.footer-nav h4 {{
  font-size: .8rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 14px;
}}
.footer-nav ul {{ list-style: none; display: flex; flex-direction: column; gap: 8px; }}
.footer-nav a {{
  font-size: .875rem;
  opacity: .7;
  transition: opacity var(--transition), color var(--transition);
}}
.footer-nav a:hover {{ opacity: 1; color: var(--color-primary); }}
.footer-col h4 {{
  font-size: .8rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 14px;
}}
.footer-bottom {{
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
  margin-top: 40px;
  text-align: center;
  font-size: .8rem;
  opacity: .5;
}}
"""


def footer_3col(cfg: dict, tokens: dict) -> str:
    return _footer_base(tokens) + """
/* Footer: 3col */
.footer-inner {
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: 24px;
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr;
  gap: 48px;
}
"""


def footer_2col(cfg: dict, tokens: dict) -> str:
    return _footer_base(tokens) + """
/* Footer: 2col */
.footer-inner {
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: 24px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 48px;
}
"""


def footer_1col(cfg: dict, tokens: dict) -> str:
    return _footer_base(tokens) + """
/* Footer: 1col */
.footer-inner {
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 28px;
}
.footer-desc { max-width: 480px; }
.footer-nav ul { align-items: center; }
"""


def footer_minimal(cfg: dict, tokens: dict) -> str:
    return _footer_base(tokens) + """
/* Footer: minimal */
.footer-inner {
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.footer-bottom { margin-top: 0; padding-top: 0; border-top: none; }
"""


# ── Dispatcher ────────────────────────────────────────────────────────────────

# Mapeo section → variante → función
_SECTION_MAP = {
    'header': {
        'centered': header_centered,
        'left':     header_left,
        'boxed':    header_boxed,
        'stacked':  header_stacked,
        'minimal':  header_minimal,
        'split':    header_split,
    },
    'hero': {
        'full':    hero_full,
        'compact': hero_compact,
        'split':   hero_split,
        'video':   hero_video,
    },
    'services': {
        'grid3': services_grid3,
        'grid2': services_grid2,
        'list':  services_list,
        'tabs':  services_tabs,
    },
    'about': {
        'mvv':        about_mvv,
        'text_photo': about_text_photo,
        'timeline':   about_timeline,
    },
    'team': {
        'avatars':      team_avatars,
        'list':         team_list,
        'cards_large':  team_cards_large,
    },
    'portfolio': {
        'grid':    portfolio_grid,
        'masonry': portfolio_masonry,
    },
    'testimonials': {
        'cards':  testimonials_cards,
        'slider': testimonials_slider,
    },
    'cta': {
        'flex':      cta_flex,
        'centered':  cta_centered,
        'bg_image':  cta_bg_image,
    },
    'contact': {
        'form_info':  contact_form_info,
        'form_only':  contact_form_only,
        'map_form':   contact_map_form,
    },
    'footer': {
        '3col':    footer_3col,
        '2col':    footer_2col,
        '1col':    footer_1col,
        'minimal': footer_minimal,
    },
}

# Secciones que siempre deben estar activas
_ALWAYS_ACTIVE = {'header', 'footer'}


def dispatch_section(section: str, variants: dict, tokens: dict) -> str:
    """Router. Si active=False (y no es header/footer) retorna ""."""
    cfg = variants.get(section, {})

    # header y footer siempre activos
    if section not in _ALWAYS_ACTIVE and not cfg.get('active', True):
        return ""

    variant = cfg.get('variant', '')
    section_fns = _SECTION_MAP.get(section, {})
    fn = section_fns.get(variant)

    if fn is None:
        # Usar primera variante disponible como fallback
        if section_fns:
            fn = next(iter(section_fns.values()))
        else:
            return ""

    return fn(cfg, tokens)


# ── Responsive ────────────────────────────────────────────────────────────────

def generate_responsive(tokens: dict, variants: dict, mobile_tokens: dict = None) -> str:
    m = mobile_tokens or {}

    scale         = m.get('font_scale', 85) / 100
    section_pads  = {'compact': '40px', 'normal': '56px', 'spacious': '80px'}
    section_pad   = section_pads.get(m.get('section_pad', 'compact'), '40px')
    container_pad = m.get('container_pad', '20px')
    hero_heights  = {'auto': 'auto', 'medium': '60vh', 'full': '90vh'}
    hero_height   = hero_heights.get(m.get('hero_height', 'auto'), 'auto')
    hide_cta      = m.get('hide_header_cta', True)
    hide_hero_img = m.get('hide_hero_img', False)
    menu_style    = m.get('menu_style', 'overlay')   # overlay | slide | dropdown
    menu_speed    = m.get('menu_speed', '0.25s')

    hide_cta_rule      = '\n  .site-header .header-contact, .lb-nav-cta { display: none !important; }' if hide_cta else ''
    hide_hero_img_rule = '\n  .hero-media, .hero-image, .hero-bg-img { display: none; }' if hide_hero_img else ''

    # Posicion y comportamiento del menú segun estilo elegido
    if menu_style == 'slide':
        nav_closed = f'transform: translateX(100%); opacity: 0; pointer-events: none;'
        nav_open   = f'transform: translateX(0);    opacity: 1; pointer-events: auto;'
        nav_pos    = f'position: fixed; top: 0; right: 0; bottom: 0; width: min(320px, 85vw); padding: 80px 28px 40px;'
    elif menu_style == 'dropdown':
        nav_closed = f'transform: translateY(-8px); opacity: 0; pointer-events: none;'
        nav_open   = f'transform: translateY(0);    opacity: 1; pointer-events: auto;'
        nav_pos    = f'position: absolute; top: 100%; left: 0; right: 0; padding: 20px 24px 28px;'
    else:  # overlay (default)
        nav_closed = f'transform: translateX(100%); opacity: 0; pointer-events: none;'
        nav_open   = f'transform: translateX(0);    opacity: 1; pointer-events: auto;'
        nav_pos    = f'position: fixed; inset: 0; padding: 80px 28px 40px;'

    return f"""
/* ── Responsive (max-width: 768px) ── */
@media (max-width: 768px) {{

  /* Variables movil */
  :root {{
    --section-pad: {section_pad};
    --container-pad: {container_pad};
  }}

  /* Contenedor */
  .container {{ padding-inline: {container_pad}; }}

  /* ── Header base ── */
  .site-header {{ position: relative; }}
  .site-header .container,
  .lb-nav-wrap {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  /* ── Menú hamburguesa — familia .navbar (doctores, empresa, arquitectura) ── */
  .navbar {{
    {nav_pos}
    background: var(--color-bg, #0e1117);
    z-index: 999;
    display: flex !important;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    {nav_closed}
    transition: transform {menu_speed} ease, opacity {menu_speed} ease;
  }}
  .navbar.open,
  .navbar.nav--open {{
    {nav_open}
  }}

  /* ── Menú hamburguesa — familia .lb-nav (abogados, salon, restaurante) ── */
  .lb-nav {{
    {nav_pos}
    background: var(--color-bg, #0e1117);
    z-index: 999;
    display: flex !important;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    {nav_closed}
    transition: transform {menu_speed} ease, opacity {menu_speed} ease;
  }}
  .lb-nav.open {{
    {nav_open}
  }}

  /* Links verticales en ambas familias */
  .nav-list,
  .lb-nav-links {{
    flex-direction: column !important;
    gap: 20px;
    font-size: {round(1.1 * scale, 3)}rem;
    width: 100%;
  }}

  /* Mostrar boton hamburguesa, ocultar en desktop (se maneja fuera del @media) */
  .nav-toggle,
  .lb-nav-toggle {{
    display: flex !important;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    position: relative;
    background: none;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 6px;
    width: 38px; height: 38px;
    cursor: pointer;
    color: inherit;
    font-size: 18px;
  }}{hide_cta_rule}

  /* ── Hero ── */
  .hero-content,
  .about-grid,
  .contact-grid {{ grid-template-columns: 1fr !important; }}
  .hero-section {{ min-height: {hero_height}; padding-block: {section_pad}; }}{hide_hero_img_rule}

  /* ── Tipografia escalada ── */
  h1 {{ font-size: calc(var(--fs-h1, 3rem) * {scale}); }}
  h2 {{ font-size: calc(var(--fs-h2, 2rem) * {scale}); }}
  h3 {{ font-size: calc(var(--fs-h3, 1.4rem) * {scale}); }}
  p, li, .body-text {{ font-size: calc(var(--fs-body, 1rem) * {scale}); }}

  /* ── Grids a 1 columna ── */
  .services-grid,
  .mvv-grid,
  .team-grid,
  .portfolio-grid,
  .testimonials-grid {{ grid-template-columns: 1fr; }}

  /* ── CTA ── */
  .cta-inner {{ flex-direction: column; text-align: center; padding: 32px {container_pad}; }}

  /* ── Footer ── */
  .footer-inner {{ grid-template-columns: 1fr !important; gap: 28px; }}
}}

/* Boton hamburguesa oculto en desktop */
.nav-toggle,
.lb-nav-toggle {{ display: none; }}"""


# ── Animaciones ───────────────────────────────────────────────────────────────

def generate_animations(tokens: dict) -> str:
    if not tokens['effects']['animations']:
        return ""

    return """
/* ── Animaciones ── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}

.fade-in-up {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity .6s ease, transform .6s ease;
}

.fade-in-up.is-visible {
  opacity: 1;
  transform: translateY(0);
}
"""


# ── CSS order: todos los bloques de sección ───────────────────────────────────

_SECTION_ORDER = [
    'header', 'hero', 'services', 'about', 'team',
    'portfolio', 'testimonials', 'cta', 'contact', 'footer',
]


# ── Punto de entrada principal ────────────────────────────────────────────────

def generate_css(site_id: int) -> str:
    """
    Lee design_tokens y section_variants de configuracion_sitio,
    genera el CSS completo, lo guarda como 'custom_css' e incrementa css_version.
    Retorna el CSS generado.
    """
    config = get_config_sitio(site_id)

    # Leer tokens con defaults del preset modern_dark
    raw_tokens   = config.get('design_tokens', '{}')
    raw_variants = config.get('section_variants', '{}')
    raw_mobile   = config.get('mobile_tokens', '{}')

    try:
        tokens = json.loads(raw_tokens)
    except (json.JSONDecodeError, TypeError):
        tokens = {}

    try:
        variants = json.loads(raw_variants)
    except (json.JSONDecodeError, TypeError):
        variants = {}

    try:
        mobile = json.loads(raw_mobile)
    except (json.JSONDecodeError, TypeError):
        mobile = {}

    # Aplicar defaults si faltan claves
    tokens = _apply_token_defaults(tokens)
    variants = _apply_variant_defaults(variants)

    # Ensamblar CSS en orden correcto
    parts = [
        generate_root(tokens),
        generate_base(tokens),
        generate_breadcrumb(tokens),
        generate_buttons(tokens),
    ]

    for section in _SECTION_ORDER:
        css = dispatch_section(section, variants, tokens)
        if css:
            parts.append(css)

    parts.append(generate_responsive(tokens, variants, mobile))
    parts.append(generate_animations(tokens))

    css_output = "\n".join(parts)

    # Guardar en BD
    version = int(config.get('css_version', '0') or '0') + 1
    set_config_sitio(site_id, 'custom_css',      css_output)
    set_config_sitio(site_id, 'css_version',     str(version))

    return css_output


def _apply_token_defaults(tokens: dict) -> dict:
    """Completa tokens faltantes con valores del preset modern_dark."""
    defaults = {
        'colors': {
            'primary':   '#00d4a0',
            'secondary': '#0a0f1e',
            'accent':    '#0088cc',
            'neutral':   '#e8eaf0',
            'mode':      'dark',
        },
        'typography': {
            'display':        'Fraunces',
            'body':           'Plus Jakarta Sans',
            'scale':          'normal',
            'weight_display': 300,
        },
        'shape': {
            'radius':       'rounded',
            'border_style': 'subtle',
        },
        'spacing': {
            'density':       'normal',
            'container_max': '1100px',
        },
        'effects': {
            'glass':      True,
            'hero_glow':  True,
            'card_hover': 'lift',
            'animations': True,
        },
    }
    for group, values in defaults.items():
        if group not in tokens:
            tokens[group] = values
        else:
            for k, v in values.items():
                tokens[group].setdefault(k, v)
    return tokens


def _apply_variant_defaults(variants: dict) -> dict:
    """Completa variantes faltantes con defaults."""
    defaults = {
        'header':       {'variant': 'centered', 'sticky': True, 'glass': True, 'topbar': True, 'active': True},
        'hero':         {'variant': 'full',      'active': True},
        'services':     {'variant': 'grid3',     'active': True},
        'about':        {'variant': 'mvv',       'active': True},
        'team':         {'variant': 'avatars',   'active': True},
        'portfolio':    {'variant': 'grid',      'active': False},
        'testimonials': {'variant': 'cards',     'active': False},
        'cta':          {'variant': 'flex',      'active': True},
        'contact':      {'variant': 'form_info', 'active': True},
        'footer':       {'variant': '3col',      'active': True},
    }
    for section, cfg in defaults.items():
        if section not in variants:
            variants[section] = cfg
        else:
            for k, v in cfg.items():
                variants[section].setdefault(k, v)
    return variants


# ── Helpers públicos para la ruta Flask ──────────────────────────────────────

def save_tokens(site_id: int, design_tokens: dict, section_variants: dict):
    """Guarda los JSONs en BD sin regenerar CSS."""
    set_config_sitio(site_id, 'design_tokens',   json.dumps(design_tokens,   ensure_ascii=False))
    set_config_sitio(site_id, 'section_variants', json.dumps(section_variants, ensure_ascii=False))


def get_tokens(site_id: int) -> tuple[dict, dict]:
    """Lee design_tokens y section_variants de BD. Retorna (tokens, variants) con defaults."""
    config   = get_config_sitio(site_id)
    tokens   = _apply_token_defaults(json.loads(config.get('design_tokens',   '{}') or '{}'))
    variants = _apply_variant_defaults(json.loads(config.get('section_variants', '{}') or '{}'))
    return tokens, variants
