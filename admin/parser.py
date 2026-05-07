# parser.py — Lee, extrae y reconstruye contenido de plantillas HTML
# Dependencias: pip install beautifulsoup4

from bs4 import BeautifulSoup
import re, os, subprocess, copy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── I/O ───────────────────────────────────────────────────────────────────────

def leer_html(ruta_relativa):
    ruta = os.path.join(BASE, ruta_relativa.lstrip('../').lstrip('/'))
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir_html(ruta_relativa, html):
    ruta = os.path.join(BASE, ruta_relativa.lstrip('../').lstrip('/'))
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)


def _resolver_css(ruta_html):
    ruta_abs = os.path.join(BASE, ruta_html.lstrip('../').lstrip('/'))
    css = os.path.join(os.path.dirname(ruta_abs), 'style.css')
    return css if os.path.exists(css) else None


def _limpiar_emoji(texto):
    match = re.match(
        r'^([\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF✚✓★☆©®]\s*)', texto
    )
    return match.group(1) if match else ''


def _set_texto(el, valor):
    """Actualiza el texto de un elemento preservando íconos emoji al inicio."""
    icono = _limpiar_emoji(el.get_text())
    if el.find():
        for child in el.children:
            if hasattr(child, 'replace_with') and isinstance(child, str) and child.strip():
                child.replace_with(icono + valor)
                return
        el.string = icono + valor
    else:
        el.string = icono + valor


# ── extraer_valores ───────────────────────────────────────────────────────────

def extraer_valores(ruta_relativa, campos):
    """
    Extrae los valores actuales del HTML según el schema de campos.
    Soporta tipos: text, textarea, tel, email, color, imagen_src, imagen_bg, href
    """
    html = leer_html(ruta_relativa)
    soup = BeautifulSoup(html, 'html.parser')
    valores = {}

    for seccion, items in campos.items():
        valores[seccion] = {}
        for campo_id, config in items.items():
            tipo = config.get('tipo', 'text')

            if tipo == 'color':
                valores[seccion][campo_id] = config.get('valor_actual', '#000000')

            elif tipo == 'imagen_bg':
                el = soup.select_one(config['selector'])
                if el:
                    style = el.get('style', '')
                    m = re.search(
                        r"background-image:\s*url\(['\"]?([^'\")\s]+)['\"]?\)", style
                    )
                    valores[seccion][campo_id] = m.group(1) if m else ''
                else:
                    valores[seccion][campo_id] = ''

            elif tipo == 'imagen_src':
                el = soup.select_one(config['selector'])
                valores[seccion][campo_id] = el.get('src', '') if el else ''

            elif tipo == 'href':
                el = soup.select_one(config['selector'])
                valores[seccion][campo_id] = el.get('href', '') if el else ''

            elif 'selector' in config:
                el = soup.select_one(config['selector'])
                if el:
                    texto = el.get_text(strip=True)
                    texto = re.sub(
                        r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF✚✓★]\s*',
                        '', texto
                    )
                    valores[seccion][campo_id] = texto
                else:
                    valores[seccion][campo_id] = config.get('placeholder', '')
            else:
                valores[seccion][campo_id] = config.get('placeholder', '')

    return valores


# ── aplicar_cambios ───────────────────────────────────────────────────────────

def aplicar_cambios(ruta_relativa, campos, nuevos_valores):
    """
    Aplica los nuevos valores al HTML y lo guarda.
    Devuelve True si tuvo éxito.
    """
    try:
        html = leer_html(ruta_relativa)

        # ── Paso 1: Colores globales (string replacement en crudo) ────────────
        for seccion, items in campos.items():
            for campo_id, config in items.items():
                if config.get('tipo') != 'color':
                    continue
                nuevo_val = nuevos_valores.get(seccion, {}).get(campo_id, '').strip()
                if not nuevo_val:
                    continue
                color_viejo = config.get('valor_actual', '')
                if color_viejo and color_viejo.lower() != nuevo_val.lower():
                    for variante in {color_viejo, color_viejo.upper(), color_viejo.lower()}:
                        html = html.replace(variante, nuevo_val)
                    config['valor_actual'] = nuevo_val

                    css_path = _resolver_css(ruta_relativa)
                    if css_path and os.path.exists(css_path):
                        with open(css_path, 'r', encoding='utf-8') as f:
                            css = f.read()
                        for variante in {color_viejo, color_viejo.upper(), color_viejo.lower()}:
                            css = css.replace(variante, nuevo_val)
                        with open(css_path, 'w', encoding='utf-8') as f:
                            f.write(css)

        # ── Paso 2: Atributos y texto via BeautifulSoup ───────────────────────
        soup = BeautifulSoup(html, 'html.parser')

        for seccion, items in campos.items():
            for campo_id, config in items.items():
                tipo = config.get('tipo', 'text')
                if tipo == 'color' or 'selector' not in config:
                    continue

                nuevo_val = nuevos_valores.get(seccion, {}).get(campo_id, '').strip()
                if not nuevo_val:
                    continue

                el = soup.select_one(config['selector'])
                if not el:
                    continue

                if tipo == 'imagen_bg':
                    style = el.get('style', '')
                    new_style = re.sub(
                        r"background-image:\s*url\(['\"]?[^'\")\s]*['\"]?\)",
                        f"background-image:url('{nuevo_val}')",
                        style
                    )
                    if 'background-image' not in new_style:
                        new_style = new_style.rstrip(';') + f";background-image:url('{nuevo_val}')"
                    el['style'] = new_style

                elif tipo == 'imagen_src':
                    el['src'] = nuevo_val
                    style = el.get('style', '')
                    el['style'] = re.sub(r'display\s*:\s*none\s*;?\s*', '', style).strip(';')

                elif tipo == 'href':
                    el['href'] = nuevo_val

                else:
                    _set_texto(el, nuevo_val)

        escribir_html(ruta_relativa, str(soup))
        return True

    except Exception as e:
        print(f"[parser] Error en aplicar_cambios: {e}")
        import traceback; traceback.print_exc()
        return False


# ── Repeaters ────────────────────────────────────────────────────────────────

def extraer_repeater(ruta_relativa, contenedor_sel, item_sel, campos_item):
    """
    Extrae la lista de items de una sección repetida (servicios, menú, equipo, etc.)
    Devuelve: [ {campo_id: valor, ...}, ... ]
    """
    try:
        html  = leer_html(ruta_relativa)
        soup  = BeautifulSoup(html, 'html.parser')
        cont  = soup.select_one(contenedor_sel)
        if not cont:
            return []

        resultado = []
        for card in cont.select(item_sel):
            item = {}
            for campo_id, config in campos_item.items():
                tipo = config.get('tipo', 'text')
                el   = card.select_one(config['selector'])
                if not el:
                    item[campo_id] = ''
                    continue

                if tipo == 'href':
                    item[campo_id] = el.get('href', '')
                elif tipo == 'imagen_src':
                    item[campo_id] = el.get('src', '')
                else:
                    texto = el.get_text(strip=True)
                    texto = re.sub(
                        r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF✚✓★]\s*',
                        '', texto
                    )
                    item[campo_id] = texto

            resultado.append(item)
        return resultado

    except Exception as e:
        print(f"[parser] Error en extraer_repeater: {e}")
        return []


def reconstruir_seccion(ruta_relativa, contenedor_sel, item_sel, campos_item, nuevos_items):
    """
    Reconstruye todos los cards de una sección desde nuevos_items.
    Clona el primer card existente como template HTML para cada nuevo item.
    Devuelve True si tuvo éxito.
    """
    try:
        html = leer_html(ruta_relativa)
        soup = BeautifulSoup(html, 'html.parser')

        contenedor = soup.select_one(contenedor_sel)
        if not contenedor:
            print(f"[parser] contenedor '{contenedor_sel}' no encontrado")
            return False

        existentes = contenedor.select(item_sel)
        if not existentes:
            print(f"[parser] items '{item_sel}' no encontrados")
            return False

        template_str = str(existentes[0])

        # Eliminar todos los items actuales
        for card in existentes:
            card.decompose()

        # Reconstruir desde nuevos_items
        for item_data in nuevos_items:
            card_soup = BeautifulSoup(template_str, 'html.parser')
            card      = card_soup.find()

            for campo_id, config in campos_item.items():
                tipo  = config.get('tipo', 'text')
                valor = item_data.get(campo_id, '').strip()
                el    = card.select_one(config['selector'])
                if not el:
                    continue

                if tipo == 'href':
                    if valor:
                        el['href'] = valor
                elif tipo == 'imagen_src':
                    if valor:
                        el['src'] = valor
                else:
                    if valor:
                        _set_texto(el, valor)

            contenedor.append(card)

        escribir_html(ruta_relativa, str(soup))
        return True

    except Exception as e:
        print(f"[parser] Error en reconstruir_seccion: {e}")
        import traceback; traceback.print_exc()
        return False


# ── Git push ──────────────────────────────────────────────────────────────────

def git_push(mensaje="Admin: actualización de contenido"):
    try:
        subprocess.run(['git', '-C', BASE, 'add', '-A'], check=True, capture_output=True)
        result = subprocess.run(
            ['git', '-C', BASE, 'commit', '-m', mensaje],
            capture_output=True, text=True
        )
        if result.returncode != 0 and 'nothing to commit' not in result.stdout:
            return False, f"Error en commit: {result.stderr}"
        subprocess.run(
            ['git', '-C', BASE, 'push', 'github', 'master'],
            check=True, capture_output=True, text=True
        )
        return True, "Publicado correctamente en Cloudflare Pages"
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
        return False, f"Error al publicar: {stderr}"
