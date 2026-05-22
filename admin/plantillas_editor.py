"""
plantillas_editor.py — Rutas del editor avanzado de plantillas CMS
Montado en app.py via register_blueprint o import directo.
"""

from flask import Blueprint, render_template, request, jsonify, session, abort
import json, logging
from db import (
    obtener_plantilla_por_id,
    actualizar_plantilla,
    get_menu_items, create_menu_item, update_menu_item, delete_menu_item, reorder_menu_items,
    get_slider_data, save_slider_config, create_slide, update_slide, delete_slide,
    get_footer_config, save_footer_config,
    get_custom_codes, create_custom_code, toggle_custom_code, delete_custom_code,
    get_secciones_habilitadas, save_secciones_habilitadas,
)

log = logging.getLogger('editor')
bp = Blueprint('plantillas_editor', __name__)

_SECCIONES_TODAS = [
    ('apariencia', 'Apariencia'),
    ('marca',      'Marca'),
    ('hero',       'Hero'),
    ('slider',     'Slider'),
    ('nosotros',   'Nosotros'),
    ('servicios',  'Servicios'),
    ('proyectos',  'Proyectos'),
    ('equipo',     'Equipo'),
    ('contacto',   'Contacto'),
    ('footer',     'Footer builder'),
]


def _admin_check():
    if session.get('plan') != 'admin':
        abort(403)


def _get_p(pid):
    p = obtener_plantilla_por_id(pid)
    if not p:
        abort(404)
    return p


# ── Editor principal ──────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/editor')
def editor(pid):
    _admin_check()
    p = _get_p(pid)
    return render_template('plantilla_editor.html',
        p=dict(p),
        secciones_todas=_SECCIONES_TODAS,
        secciones_hab=get_secciones_habilitadas(pid),
        menu_items=get_menu_items(pid),
        slider=get_slider_data(pid),
        footer=get_footer_config(pid),
        custom_codes=get_custom_codes(pid),
        nombre=session.get('nombre', ''),
    )


# ── General ───────────────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/guardar-general', methods=['POST'])
def guardar_general(pid):
    _admin_check()
    p = _get_p(pid)
    d = request.get_json(force=True)
    actualizar_plantilla(
        pid,
        d.get('nombre', p['nombre']),
        d.get('tipo', p['tipo']),
        d.get('descripcion', p['descripcion']),
        d.get('preview_img', p['preview_img']),
        p['campos_schema'],
    )
    return jsonify(ok=True)


# ── Secciones habilitadas ─────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/secciones', methods=['POST'])
def guardar_secciones(pid):
    _admin_check()
    _get_p(pid)
    d = request.get_json(force=True)
    save_secciones_habilitadas(pid, d.get('secciones', []))
    return jsonify(ok=True)


# ── Menú ──────────────────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/menu', methods=['GET'])
def menu_list(pid):
    _admin_check()
    return jsonify(get_menu_items(pid))


@bp.route('/admin/plantillas/<int:pid>/menu', methods=['POST'])
def menu_create(pid):
    _admin_check()
    d = request.get_json(force=True)
    items = get_menu_items(pid)
    orden = len(items)
    parent_id = d.get('parent_id') or None
    iid = create_menu_item(pid, d['label'], d.get('url', '#'), orden, parent_id)
    return jsonify(ok=True, id=iid)


@bp.route('/admin/plantillas/<int:pid>/menu/<int:iid>', methods=['PUT'])
def menu_update(pid, iid):
    _admin_check()
    d = request.get_json(force=True)
    parent_id = d.get('parent_id') or None
    update_menu_item(iid, d['label'], d.get('url', '#'), parent_id)
    return jsonify(ok=True)


@bp.route('/admin/plantillas/<int:pid>/menu/<int:iid>', methods=['DELETE'])
def menu_delete(pid, iid):
    _admin_check()
    delete_menu_item(iid)
    return jsonify(ok=True)


@bp.route('/admin/plantillas/<int:pid>/menu/reordenar', methods=['POST'])
def menu_reorder(pid):
    _admin_check()
    d = request.get_json(force=True)
    reorder_menu_items(d.get('orden', []))
    return jsonify(ok=True)


# ── Slider ────────────────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/slider', methods=['GET'])
def slider_get(pid):
    _admin_check()
    return jsonify(get_slider_data(pid))


@bp.route('/admin/plantillas/<int:pid>/slider/config', methods=['POST'])
def slider_config(pid):
    _admin_check()
    _get_p(pid)
    save_slider_config(pid, request.get_json(force=True))
    return jsonify(ok=True)


@bp.route('/admin/plantillas/<int:pid>/slider/slides', methods=['POST'])
def slide_create(pid):
    _admin_check()
    d = request.get_json(force=True)
    existing = get_slider_data(pid)['slides']
    iid = create_slide(pid, d.get('imagen_url',''), d.get('titulo',''), d.get('subtitulo',''), len(existing))
    return jsonify(ok=True, id=iid)


@bp.route('/admin/plantillas/<int:pid>/slider/slides/<int:sid>', methods=['PUT'])
def slide_update(pid, sid):
    _admin_check()
    d = request.get_json(force=True)
    update_slide(sid, d.get('imagen_url',''), d.get('titulo',''), d.get('subtitulo',''), d.get('orden',0))
    return jsonify(ok=True)


@bp.route('/admin/plantillas/<int:pid>/slider/slides/<int:sid>', methods=['DELETE'])
def slide_delete(pid, sid):
    _admin_check()
    delete_slide(sid)
    return jsonify(ok=True)


# ── Footer ────────────────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/footer', methods=['POST'])
def footer_save(pid):
    _admin_check()
    _get_p(pid)
    save_footer_config(pid, request.get_json(force=True))
    return jsonify(ok=True)


# ── Custom code ───────────────────────────────────────────────────────────────

@bp.route('/admin/plantillas/<int:pid>/custom-code', methods=['POST'])
def custom_code_create(pid):
    _admin_check()
    d = request.get_json(force=True)
    iid = create_custom_code(pid, d['tipo'], d['inject_in'], d.get('seccion_target'), d['codigo'])
    return jsonify(ok=True, id=iid)


@bp.route('/admin/plantillas/<int:pid>/custom-code/<int:cid>/toggle', methods=['POST'])
def custom_code_toggle(pid, cid):
    _admin_check()
    toggle_custom_code(cid)
    return jsonify(ok=True)


@bp.route('/admin/plantillas/<int:pid>/custom-code/<int:cid>', methods=['DELETE'])
def custom_code_delete(pid, cid):
    _admin_check()
    delete_custom_code(cid)
    return jsonify(ok=True)


# ── Scraper ───────────────────────────────────────────────────────────────────

@bp.route('/admin/scraper/analizar', methods=['POST'])
def scraper_analizar():
    _admin_check()
    d = request.get_json(force=True)
    url = d.get('url', '').strip()
    if not url:
        return jsonify(error='URL requerida'), 400
    try:
        import urllib.request
        from bs4 import BeautifulSoup
        import re

        # Verificar robots.txt básico
        from urllib.parse import urlparse
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            with urllib.request.urlopen(robots_url, timeout=5) as r:
                robots = r.read().decode(errors='ignore')
                if 'Disallow: /' in robots and 'User-agent: *' in robots:
                    return jsonify(error='El sitio no permite scraping (robots.txt)'), 403
        except Exception:
            pass  # Si no hay robots.txt, continuar

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode(errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')

        # Extraer colores del CSS inline y style tags
        colores = []
        for tag in soup.find_all(style=True):
            matches = re.findall(r'#[0-9a-fA-F]{3,6}', tag.get('style', ''))
            colores.extend(matches)
        for style in soup.find_all('style'):
            matches = re.findall(r'#[0-9a-fA-F]{3,6}', style.get_text())
            colores.extend(matches)
        colores = list(dict.fromkeys(colores))[:8]

        # Fuentes
        fuentes = []
        for style in soup.find_all('style'):
            matches = re.findall(r"font-family:\s*['\"']?([^,;'\"]+)", style.get_text())
            fuentes.extend([f.strip() for f in matches])
        fuentes = list(dict.fromkeys(fuentes))[:4]

        # Imágenes
        imagenes = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and src.startswith('http'):
                imagenes.append(src)
        imagenes = imagenes[:6]

        # Textos
        titulo = ''
        for tag in ['h1', 'h2', 'title']:
            el = soup.find(tag)
            if el:
                titulo = el.get_text(strip=True)[:100]
                break
        descripcion = ''
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            descripcion = meta.get('content', '')[:200]

        # Logo
        logo_url = ''
        for img in soup.find_all('img'):
            alt = img.get('alt', '').lower()
            src = img.get('src', '')
            if 'logo' in alt or 'logo' in src.lower():
                logo_url = src
                break

        return jsonify({
            'colores': colores,
            'fuentes': fuentes,
            'imagenes': imagenes,
            'textos': {'titulo': titulo, 'descripcion': descripcion},
            'logo_url': logo_url,
        })
    except Exception as e:
        log.warning(f'[scraper] Error analizando {url}: {e}')
        return jsonify(error=str(e)), 500


@bp.route('/admin/scraper/aplicar/<int:pid>', methods=['POST'])
def scraper_aplicar(pid):
    _admin_check()
    _get_p(pid)
    # La aplicación se hace vía configuracion_sitio del sitio o config de plantilla
    # Por ahora devuelve OK — el cliente JS gestiona la aplicación visual
    return jsonify(ok=True)
