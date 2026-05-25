# ══════════════════════════════════════════════════════════════════════════════
# Admin — Scraper / Creación por Categoría
# ══════════════════════════════════════════════════════════════════════════════
# INSTRUCCIÓN PARA CLAUDE CODE:
# En ~/plantillas-web/admin/app.py, busca el bloque que empieza con:
#   @app.route('/admin/scraper/crear-desde-url', methods=['POST'])
# y reemplaza SOLO esa función (hasta el return jsonify final) con
# la versión corregida de abajo.
# NO toques _CATEGORIAS ni admin_scraper_crear_categoria.
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/scraper/crear-desde-url', methods=['POST'])
@admin_requerido
def admin_scraper_crear_url():
    import re as _re
    d = request.get_json(force=True)

    nombre      = d.get('nombre', '').strip()
    clave       = d.get('clave', '').strip().lower()
    tipo        = d.get('tipo', 'landing')
    blueprint   = d.get('blueprint')    # NUEVO — dict con secciones detectadas
    componentes = d.get('componentes', {})  # NUEVO — toggles del cliente

    if not nombre or not clave:
        return jsonify(ok=False, error='Nombre y clave son obligatorios.'), 400
    if not _re.match(r'^[a-z][a-z0-9_-]{1,29}$', clave):
        return jsonify(ok=False, error='Clave no válida: solo minúsculas, números, guiones.'), 400

    try:
        pid = crear_plantilla(clave, nombre, tipo, f'Creada desde scraper URL', '', '{}')
    except Exception:
        return jsonify(ok=False, error=f'La clave "{clave}" ya existe.'), 409

    # ── Construir layout desde blueprint real (no el genérico hardcodeado) ──
    layout = _blueprint_to_layout(blueprint, componentes)

    # ── Construir defaults_json desde blueprint + componentes ────────────────
    # Esto es lo que faltaba: antes siempre era '{}'.
    # Ahora guarda la estructura real detectada para que el generador la use.
    defaults = _blueprint_to_defaults(blueprint, componentes)

    campos_estilos = {
        'color_primary':   d.get('color_primario', '#185FA5'),
        'color_accent':    d.get('color_acento',   '#0088CC'),
        'color_secondary': d.get('color_footer',   '#0A0F1E'),
        'font_heading':    d.get('fuente_titulos', 'system-ui, sans-serif'),
        'font_body':       d.get('fuente_cuerpo',  'system-ui, sans-serif'),
        'layout_json':     json.dumps(layout,    ensure_ascii=False),
        'defaults_json':   json.dumps(defaults,  ensure_ascii=False),  # ← YA NO VACÍO
    }
    upsert_estilos(pid, campos_estilos)

    flash(f'Plantilla "{nombre}" creada desde scraper.', 'success')
    return jsonify(ok=True, pid=pid, redirect=url_for('admin_plantillas'))


# ── Helpers para convertir blueprint → layout y defaults ─────────────────────

def _blueprint_to_layout(blueprint: dict | None, componentes: dict) -> dict:
    """
    Convierte el blueprint de secciones detectadas en el dict layout_json
    que usa el generador de plantillas.
    Si no hay blueprint (sitio no scrapeado), usa defaults razonables.
    """
    if not blueprint or not blueprint.get('sections'):
        # Sin blueprint: layout genérico como antes
        return {
            'hero':     'fullscreen',
            'services': 'grid',
            'projects': 'masonry',
            'team':     'cards',
        }

    sections = {s['id']: s for s in blueprint.get('sections', [])}
    estilo   = blueprint.get('estilo', 'clean')

    # Hero type viene del toggle del cliente, con fallback al detectado
    hero_type = componentes.get('hero_type', 'static')
    if hero_type == 'slider':
        hero_layout = 'slider'
    elif hero_type == 'carousel':
        hero_layout = 'carousel'
    else:
        # Usar el layout detectado del sitio
        detected = sections.get('hero', {}).get('layout', 'fullscreen-bg')
        hero_map = {
            'fullscreen-bg':   'fullscreen',
            'fullscreen-dark': 'dark',
            'slider':          'slider',
        }
        hero_layout = hero_map.get(detected, 'fullscreen')

    # Services layout según columnas detectadas
    services_sec = sections.get('services', {})
    card_count   = services_sec.get('card_count', 3)
    services_layout = 'grid' if card_count >= 4 else 'list'

    # Why us → projects slot en el sistema actual
    why_sec   = sections.get('why_us', {})
    why_count = why_sec.get('item_count', 6)
    projects_layout = 'masonry' if why_count >= 6 else 'grid'

    # About con stats → team con cards
    about_sec  = sections.get('about', {})
    team_layout = 'cards' if about_sec.get('has_stats') else 'minimal'

    return {
        'hero':          hero_layout,
        'services':      services_layout,
        'projects':      projects_layout,
        'team':          team_layout,
        # NUEVO: secciones adicionales detectadas
        'has_topbar':    'topbar'         in sections or componentes.get('topbar', False),
        'has_features':  'features_strip' in sections,
        'has_about':     'about'          in sections,
        'has_why_us':    'why_us'         in sections,
        'has_impact':    'impact'         in sections,
        'has_newsletter':componentes.get('newsletter', 'newsletter' in sections),
        'has_whatsapp':  componentes.get('whatsapp', False),
        'has_social':    componentes.get('social', True),
        'has_citas':     componentes.get('citas', False),
        # Orden de secciones para el generador
        'section_order': [s['id'] for s in blueprint.get('sections', [])],
        'estilo':        estilo,
    }


def _blueprint_to_defaults(blueprint: dict | None, componentes: dict) -> dict:
    """
    Genera el defaults_json con valores por defecto inteligentes
    derivados del blueprint detectado.
    El generador usa estos valores cuando el usuario aún no ha
    personalizado el sitio.
    """
    if not blueprint or not blueprint.get('sections'):
        return {}

    sections = {s['id']: s for s in blueprint.get('sections', [])}

    defaults = {
        # Metadatos de la plantilla
        '_source': 'scraper',
        '_blueprint_estilo': blueprint.get('estilo', 'clean'),
        '_detected_sections': blueprint.get('detected_sections', []),
        '_fallback': blueprint.get('fallback', False),

        # Hero
        'hero_type':     componentes.get('hero_type', 'static'),
        'hero_layout':   sections.get('hero', {}).get('layout', 'fullscreen-bg'),
        'hero_has_eyebrow': sections.get('hero', {}).get('has_eyebrow', True),

        # Features strip
        'features_count': sections.get('features_strip', {}).get('item_count', 3),
        'features_has_icons': sections.get('features_strip', {}).get('has_icons', True),
        'features_dark_bg': sections.get('features_strip', {}).get('dark_bg', True),

        # About
        'about_has_stats': sections.get('about', {}).get('has_stats', True),
        'about_has_image': sections.get('about', {}).get('has_image', True),
        'about_stats_count': 3,

        # Why us
        'whyus_count':  sections.get('why_us', {}).get('item_count', 6),
        'whyus_layout': 'grid-3col' if sections.get('why_us', {}).get('item_count', 6) >= 6 else 'grid-2col',
        'whyus_has_side_image': sections.get('why_us', {}).get('item_count', 0) >= 6,

        # Services
        'services_count': sections.get('services', {}).get('card_count', 6),
        'services_cols':  3 if sections.get('services', {}).get('card_count', 3) >= 4 else 2,
        'services_has_image': sections.get('services', {}).get('has_image', True),

        # Footer
        'footer_cols': int(sections.get('footer', {}).get('layout', '4-col-grid').split('-')[0]) if sections.get('footer') else 4,
        'footer_has_social': sections.get('footer', {}).get('has_social', True),

        # Componentes opcionales (toggles del cliente)
        'comp_whatsapp':   componentes.get('whatsapp', False),
        'comp_newsletter': componentes.get('newsletter', True),
        'comp_social':     componentes.get('social', True),
        'comp_topbar':     componentes.get('topbar', False) or ('topbar' in sections),
        'comp_citas':      componentes.get('citas', False),

        # Impact section
        'has_impact_section': 'impact' in sections,
    }

    return defaults
