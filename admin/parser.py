# parser.py — Lee y escribe contenido de plantillas HTML
# Dependencia: pip install beautifulsoup4

from bs4 import BeautifulSoup
import re, os, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer_html(ruta_relativa):
    """Carga el HTML de una plantilla."""
    ruta = os.path.join(BASE, ruta_relativa.lstrip('../').lstrip('/'))
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir_html(ruta_relativa, html):
    """Guarda el HTML modificado."""
    ruta = os.path.join(BASE, ruta_relativa.lstrip('../').lstrip('/'))
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)


def _limpiar_emoji(texto):
    """Extrae el ícono emoji del inicio de un texto, si lo tiene."""
    match = re.match(r'^([\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF✚✓★☆©®]\s*)', texto)
    return match.group(1) if match else ''


def extraer_valores(ruta_relativa, campos):
    """
    Recibe el schema de campos de una plantilla.
    Devuelve dict con los valores actuales encontrados en el HTML.
    """
    html = leer_html(ruta_relativa)
    soup = BeautifulSoup(html, 'html.parser')
    valores = {}

    for seccion, items in campos.items():
        valores[seccion] = {}
        for campo_id, config in items.items():
            if config['tipo'] == 'color':
                # Usar valor_actual del schema (el color está en el CSS separado)
                valores[seccion][campo_id] = config.get('valor_actual', '#000000')
            elif 'selector' in config:
                el = soup.select_one(config['selector'])
                if el:
                    texto = el.get_text(strip=True)
                    # Limpiar íconos emoji del inicio (📞 ✉ ✚ etc.)
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


def aplicar_cambios(ruta_relativa, campos, nuevos_valores):
    """
    Aplica los nuevos valores al HTML y lo guarda.
    Estrategia:
      1. Aplicar reemplazos de color directamente sobre el string HTML + CSS
      2. Aplicar cambios de texto sobre BeautifulSoup
      3. Serializar y guardar
    Devuelve True si tuvo éxito, False si falló.
    """
    try:
        html = leer_html(ruta_relativa)

        # ── Paso 1: Colores (reemplazo directo en el string) ─────────────────
        for seccion, items in campos.items():
            for campo_id, config in items.items():
                if config['tipo'] != 'color':
                    continue
                nuevo_val = nuevos_valores.get(seccion, {}).get(campo_id, '').strip()
                if not nuevo_val:
                    continue
                color_viejo = config.get('valor_actual', '')
                if color_viejo and color_viejo.lower() != nuevo_val.lower():
                    # Reemplazar todas las variantes de capitalización
                    for variante in {color_viejo, color_viejo.upper(), color_viejo.lower()}:
                        html = html.replace(variante, nuevo_val)
                    config['valor_actual'] = nuevo_val

                # También actualizar el CSS separado si existe
                css_path = _resolver_css(ruta_relativa)
                if css_path and os.path.exists(css_path):
                    with open(css_path, 'r', encoding='utf-8') as f:
                        css = f.read()
                    for variante in {color_viejo, color_viejo.upper(), color_viejo.lower()}:
                        css = css.replace(variante, nuevo_val)
                    with open(css_path, 'w', encoding='utf-8') as f:
                        f.write(css)

        # ── Paso 2: Texto/selectores via BeautifulSoup ────────────────────────
        soup = BeautifulSoup(html, 'html.parser')

        for seccion, items in campos.items():
            for campo_id, config in items.items():
                if config['tipo'] == 'color' or 'selector' not in config:
                    continue
                nuevo_val = nuevos_valores.get(seccion, {}).get(campo_id, '').strip()
                if not nuevo_val:
                    continue
                el = soup.select_one(config['selector'])
                if not el:
                    continue

                # Preservar ícono emoji al inicio si lo había
                icono = _limpiar_emoji(el.get_text())

                # Si el elemento tiene hijos (ej: span dentro de a), limpiar solo el texto directo
                if el.find():
                    # Tiene hijos — actualizar NavigableString directo si existe
                    for child in el.children:
                        if hasattr(child, 'replace_with') and isinstance(child, str) and child.strip():
                            child.replace_with(icono + nuevo_val)
                            break
                    else:
                        el.string = icono + nuevo_val
                else:
                    el.string = icono + nuevo_val

        escribir_html(ruta_relativa, str(soup))
        return True

    except Exception as e:
        print(f"[parser] Error en aplicar_cambios: {e}")
        return False


def _resolver_css(ruta_html):
    """Dado el path del HTML, devuelve el path del CSS de la misma carpeta."""
    ruta_abs = os.path.join(BASE, ruta_html.lstrip('../').lstrip('/'))
    directorio = os.path.dirname(ruta_abs)
    css = os.path.join(directorio, 'style.css')
    return css if os.path.exists(css) else None


def git_push(mensaje="Admin: actualización de contenido"):
    """Hace git add + commit + push para redesplegar en Cloudflare Pages."""
    try:
        subprocess.run(
            ['git', '-C', BASE, 'add', '-A'],
            check=True, capture_output=True
        )
        result = subprocess.run(
            ['git', '-C', BASE, 'commit', '-m', mensaje],
            capture_output=True, text=True
        )
        # "nothing to commit" no es error
        if result.returncode != 0 and 'nothing to commit' not in result.stdout:
            return False, f"Error en commit: {result.stderr}"

        push = subprocess.run(
            ['git', '-C', BASE, 'push', 'github', 'master'],
            check=True, capture_output=True, text=True
        )
        return True, "Publicado correctamente en Cloudflare Pages"
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
        return False, f"Error al publicar: {stderr}"
