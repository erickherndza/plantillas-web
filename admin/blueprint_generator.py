"""
blueprint_generator.py
Convierte el blueprint del scraper en configuración real del sitio.
Soporta tanto landing page como web de 5 páginas (web5).
"""
import json


# ── Variables por sección → config del template ──────────────────────────────
SECTION_CONFIG_MAP = {
    'topbar': {
        'show_topbar':        True,
        'topbar_phone':       '(809) 000-0000',
        'topbar_email':       'info@tusitio.com',
        'show_topbar_social': True,
    },
    'hero': {
        'hero_eyebrow':    'Bienvenidos',
        'hero_titulo':     'Tu empresa, tu solución',
        'hero_subtitulo':  'Descripción breve de lo que haces y por qué eres la mejor opción.',
        'hero_cta_texto':  'Descubrir más',
        'hero_cta_href':   '#servicios',
        'hero_cta2_texto': 'Contáctanos',
        'hero_cta2_href':  '#contacto',
    },
    'features_strip': {
        'show_features_strip': True,
        'features_count':      3,
        'features_dark_bg':    True,
    },
    'about': {
        'show_nosotros':        True,
        'nosotros_descripcion': 'Somos un equipo comprometido con la excelencia.',
        'nosotros_mision':      'Proveer soluciones de alta calidad.',
        'nosotros_vision':      'Ser referentes en nuestra industria.',
        'nosotros_valores':     'Integridad, Excelencia, Innovación, Compromiso',
    },
    'why_us': {
        'show_whyus':   True,
        'whyus_titulo': 'Por qué elegirnos',
        'whyus_count':  6,
    },
    'impact': {
        'show_impact':        True,
        'impact_titulo':      'Nuestro impacto en la comunidad',
        'impact_descripcion': 'Cada proyecto es una oportunidad para mejorar vidas.',
        'impact_cta':         'Descubrir más',
    },
    'services': {
        'show_servicios':        True,
        'servicios_descripcion': 'Soluciones adaptadas a las necesidades de cada cliente.',
        'menu_servicios':        'Servicios',
    },
    'newsletter': {
        'show_newsletter':   True,
        'newsletter_titulo': 'Mantente informado',
        'newsletter_texto':  'Recibe nuestras novedades directamente en tu bandeja.',
    },
    'footer': {
        'footer_descripcion': 'Comprometidos con la excelencia y satisfacción de nuestros clientes.',
        'show_footer_social': True,
    },
}

HERO_LAYOUT_MAP = {
    'fullscreen':      'hero-fullscreen',
    'fullscreen-bg':   'hero-fullscreen',
    'fullscreen-dark': 'hero-fullscreen hero-dark',
    'slider':          'hero-slider',
    'carousel':        'hero-carousel',
    'split':           'hero-split',
    'minimal':         'hero-minimal',
    'gradient':        'hero-gradient',
    'dark':            'hero-dark',
}

COMPONENTES_CONFIG_MAP = {
    'whatsapp':   {'show_whatsapp_float': True},
    'newsletter': {'show_newsletter':     True},
    'social':     {'show_social_icons':   True},
    'topbar':     {'show_topbar':         True},
    'citas':      {'show_citas': True, 'citas_titulo': 'Agenda tu cita'},
}

WEB5_PAGE_SECTIONS = {
    'inicio':    ['topbar', 'header', 'hero', 'features_strip', 'about', 'impact'],
    'nosotros':  ['about', 'why_us', 'equipo'],
    'servicios': ['services'],
    'proyectos': ['why_us', 'impact'],
    'contacto':  ['contacto'],
}

MENU_LABELS = {
    'services': {'menu_servicios': 'Servicios'},
    'why_us':   {'menu_proyectos': 'Por qué nosotros'},
    'about':    {'menu_nosotros':  'Nosotros'},
}


def blueprint_to_config(
    blueprint:    dict,
    estilos:      dict,
    nombre_sitio: str,
    slug:         str,
    tipo:         str  = 'landing',
    componentes:  dict = None,
) -> dict:
    componentes = componentes or {}
    sections    = {s['id']: s for s in blueprint.get('sections', [])}
    estilo      = blueprint.get('estilo', 'clean')
    is_dark     = estilo in ('dark', 'gradient')

    config = {
        'nombre_negocio':    nombre_sitio,
        'contacto_email':    f'info@{slug}.com',
        'contacto_telefono': '(809) 000-0000',
        'contacto_direccion':'Calle Principal 123, Ciudad',
        'logo_url':          '',
        '_blueprint_estilo': estilo,
        '_tipo_web':         tipo,
        '_section_order':    json.dumps(blueprint.get('detected_sections', [])),
    }

    config.update({
        'color_primario':   estilos.get('color_primary',   '#185FA5'),
        'color_acento':     estilos.get('color_accent',    '#0088CC'),
        'color_footer_bg':  estilos.get('color_secondary', '#0A0F1E'),
        'color_navbar_bg':  estilos.get('color_primary',   '#185FA5'),
        'color_texto':      '#ffffff' if is_dark else '#1e293b',
        'fuente_titulos':   estilos.get('font_heading',    'system-ui, sans-serif'),
        'fuente_cuerpo':    estilos.get('font_body',       'system-ui, sans-serif'),
    })

    hero_sec    = sections.get('hero', {})
    hero_layout = hero_sec.get('layout', 'fullscreen-bg')
    hero_type   = componentes.get('hero_type', 'static')

    if   hero_type == 'slider':   hero_class = 'hero-slider'
    elif hero_type == 'carousel': hero_class = 'hero-carousel'
    else:                         hero_class = HERO_LAYOUT_MAP.get(hero_layout, 'hero-fullscreen')

    config['hero_layout_class'] = hero_class
    config['hero_tipo']         = hero_type

    for sid, sdata in sections.items():
        if sid in SECTION_CONFIG_MAP:
            config.update(SECTION_CONFIG_MAP[sid])

        if sid == 'about' and sdata.get('has_stats'):
            config['nosotros_show_stats'] = True
            config['nosotros_stats'] = json.dumps([
                {'valor': '10+',  'label': 'Años de experiencia'},
                {'valor': '500+', 'label': 'Clientes satisfechos'},
                {'valor': '98%',  'label': 'Tasa de satisfacción'},
            ])
        if sid == 'services':
            cols = 3 if sdata.get('card_count', 3) >= 4 else 2
            config['servicios_cols']  = cols
            config['servicios_count'] = sdata.get('card_count', 3)
        if sid == 'why_us':
            config['whyus_count']  = sdata.get('item_count', 6)
            config['whyus_layout'] = 'grid-3col' if sdata.get('item_count', 6) >= 6 else 'grid-2col'
            config['menu_proyectos'] = 'Proyectos'
        if sid == 'footer':
            raw_cols = sdata.get('layout', '4-col-grid').split('-')[0]
            config['footer_cols']        = int(raw_cols) if raw_cols.isdigit() else 4
            config['show_footer_social'] = sdata.get('has_social', True)

    OPTIONAL_SECTIONS = ['topbar', 'features_strip', 'why_us', 'impact', 'newsletter']
    for sec in OPTIONAL_SECTIONS:
        if sec not in sections:
            config[f'show_{sec}'] = False

    for comp, active in componentes.items():
        if comp in COMPONENTES_CONFIG_MAP and active:
            config.update(COMPONENTES_CONFIG_MAP[comp])
        elif comp == 'whatsapp' and not active:
            config['show_whatsapp_float'] = False

    if tipo == 'web5':
        config.update(_web5_extra_config(sections, nombre_sitio, componentes))
    else:
        config.update(_landing_extra_config(sections))

    return config


def _landing_extra_config(sections: dict) -> dict:
    extra = {}
    if 'services' in sections:
        extra['hero_cta_href']  = '#servicios'
        extra['hero_cta2_href'] = '#contacto'
    if 'newsletter' in sections:
        extra['show_newsletter'] = True
        extra['newsletter_position'] = 'before_footer'
    return extra


def _web5_extra_config(sections: dict, nombre_sitio: str, componentes: dict) -> dict:
    extra = {
        'hero_cta_href':  '/servicios',
        'hero_cta2_href': '/contacto',
        'menu_inicio':     'Inicio',
        'menu_nosotros':   'Nosotros'   if 'about'    in sections else '',
        'menu_servicios':  'Servicios'  if 'services' in sections else '',
        'menu_proyectos':  'Proyectos'  if 'why_us'   in sections else '',
        'menu_contacto':   'Contacto',
        'nosotros_resumen': f'Conoce más sobre {nombre_sitio} y nuestro compromiso con la calidad.',
        'servicios_intro': 'Soluciones diseñadas para cubrir todas tus necesidades.',
        'proyectos_titulo': 'Por qué elegirnos',
        'proyectos_desc':   'Descubre las razones por las que nuestros clientes confían en nosotros.',
        'contacto_titulo':       'Hablemos',
        'contacto_descripcion':  '¿Tienes un proyecto en mente? Nos encantaría escucharte.',
        'contacto_mapa_embed':   '',
        'newsletter_position': 'footer',
    }
    if componentes.get('citas'):
        extra['show_citas_page'] = True
        extra['menu_citas']      = 'Citas'
    return extra


def blueprint_to_secciones(blueprint: dict, tipo: str = 'landing') -> dict:
    sections = {s['id']: s for s in blueprint.get('sections', [])}
    result   = {}

    services_sec   = sections.get('services', {})
    services_count = min(services_sec.get('card_count', 3), 6 if tipo == 'web5' else 4)
    SERVICIOS_LABELS = [
        ('Servicio Principal',  'Descripción del servicio más importante que ofreces.'),
        ('Segundo Servicio',    'Descripción del segundo servicio destacado.'),
        ('Tercer Servicio',     'Descripción de este servicio especializado.'),
        ('Cuarto Servicio',     'Otro servicio que diferencia tu negocio.'),
        ('Quinto Servicio',     'Solución adicional para tus clientes.'),
        ('Servicio Adicional',  'Más opciones para cubrir todas las necesidades.'),
    ]
    result['servicios'] = [
        {'titulo': SERVICIOS_LABELS[i][0], 'desc': SERVICIOS_LABELS[i][1], 'imagen': ''}
        for i in range(services_count)
    ]

    why_sec   = sections.get('why_us', {})
    why_count = min(why_sec.get('item_count', 4), 9 if tipo == 'web5' else 6)
    WHY_LABELS = [
        ('A la vanguardia',       'Tecnología avanzada para soluciones de alto rendimiento.'),
        ('Soporte técnico',       'Mantenimiento preventivo para optimizar rendimiento.'),
        ('Orientado a objetivos', 'Soluciones a medida para necesidades específicas.'),
        ('Seguridad',             'Sistemas robustos para proteger tus intereses.'),
        ('Calidad garantizada',   'Cumplimos estándares internacionales de calidad.'),
        ('Responsabilidad',       'Impacto positivo en cada proyecto que ejecutamos.'),
        ('Prestigio',             'Reconocidos por excelencia y resultados.'),
        ('Asesoría experta',      'Estudios detallados para mejorar tu operación.'),
        ('Escalabilidad',         'Adaptamos la solución a tu crecimiento.'),
    ]
    result['proyectos'] = [
        {'titulo': WHY_LABELS[i][0], 'categoria': WHY_LABELS[i][1], 'imagen': ''}
        for i in range(why_count)
    ]

    about_sec = sections.get('about', {})
    show_equipo = tipo == 'web5' or about_sec.get('has_stats') or about_sec.get('has_image')
    result['equipo'] = [
        {'nombre': 'Nombre Apellido', 'rol': 'Director General',   'foto': '',
         'credenciales': 'MBA · Universidad Nacional'},
        {'nombre': 'Nombre Apellido', 'rol': 'Gerente Operativo',  'foto': '',
         'credenciales': 'Ing. Industrial · INTEC'},
        {'nombre': 'Nombre Apellido', 'rol': 'Coordinador',        'foto': '',
         'credenciales': 'Lic. Administración · PUCMM'},
    ] if show_equipo else []

    if 'features_strip' in sections:
        feat_count = sections['features_strip'].get('item_count', 3)
        FEAT_LABELS = [
            ('⚡', 'Soluciones',  'Infraestructuras a medida con los más altos estándares.'),
            ('🛠', 'Servicios',   'Asistencia técnica para mantener tu operación activa.'),
            ('🌟', 'Productos',   'Tecnología de punta garantizando calidad y velocidad.'),
            ('🔒', 'Seguridad',   'Sistemas robustos que protegen la integridad de tu negocio.'),
        ]
        result['features'] = [
            {'icono': FEAT_LABELS[i][0], 'titulo': FEAT_LABELS[i][1], 'texto': FEAT_LABELS[i][2]}
            for i in range(min(feat_count, 4))
        ]

    if 'why_us' in sections:
        result['whyus_items'] = [
            {'icono': WHY_LABELS[i][0], 'titulo': WHY_LABELS[i][0], 'texto': WHY_LABELS[i][1]}
            for i in range(why_count)
        ]

    if tipo == 'web5':
        result['testimonios'] = [
            {'nombre': 'María García',  'texto': 'Excelente servicio. Profesionales de primer nivel. Lo recomiendo sin dudarlo.',        'especialidad': 'Cliente satisfecho'},
            {'nombre': 'Juan Pérez',    'texto': 'Resultados excepcionales. Cumplieron en tiempo y forma, superando nuestras expectativas.', 'especialidad': 'Empresa cliente'},
            {'nombre': 'Ana Rodríguez', 'texto': 'Servicio de primera calidad. El equipo siempre dispuesto a ayudar y orientar.',          'especialidad': 'Cliente recurrente'},
        ]

    return result


def get_web5_page_context(pagina: str, blueprint: dict, config: dict, secciones: dict) -> dict:
    sections = {s['id']: s for s in blueprint.get('sections', [])}
    ctx = {'pagina_activa': pagina, 'config': config}

    if pagina == 'inicio':
        ctx['show_features']      = 'features_strip' in sections
        ctx['show_about_preview'] = 'about' in sections
        ctx['show_impact']        = 'impact' in sections
        ctx['features_items']     = secciones.get('features', [])
        ctx['servicios_preview']  = secciones.get('servicios', [])[:3]

    elif pagina == 'nosotros':
        ctx['show_stats']    = config.get('nosotros_show_stats', False)
        ctx['show_whyus']    = 'why_us' in sections
        ctx['equipo_items']  = secciones.get('equipo', [])
        ctx['testimonios']   = secciones.get('testimonios', [])
        ctx['whyus_items']   = secciones.get('whyus_items', [])

    elif pagina == 'servicios':
        ctx['servicios_items'] = secciones.get('servicios', [])
        ctx['servicios_cols']  = config.get('servicios_cols', 3)
        ctx['show_citas']      = config.get('show_citas', False)

    elif pagina == 'proyectos':
        ctx['proyectos_items'] = secciones.get('proyectos', [])
        ctx['whyus_items']     = secciones.get('whyus_items', [])
        ctx['show_impact']     = 'impact' in sections

    elif pagina == 'contacto':
        ctx['show_mapa']  = bool(config.get('contacto_mapa_embed', ''))
        ctx['show_citas'] = config.get('show_citas', False)

    return ctx
