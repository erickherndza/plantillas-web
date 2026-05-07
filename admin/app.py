from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_from_directory
)
import json, os, uuid, logging

from db import (
    init_db, obtener_cliente, obtener_cliente_por_id,
    obtener_plantillas_cliente, listar_clientes,
    crear_cliente, actualizar_cliente, eliminar_cliente, set_accesos
)
from parser import (
    extraer_valores, aplicar_cambios,
    extraer_repeater, reconstruir_seccion, git_push
)

app = Flask(__name__)
app.secret_key = 'admin-plantillas-rd-2026'

BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE, 'shared', 'site-schema.json')
UPLOADS_DIR = os.path.join(app.static_folder, 'uploads')


def cargar_schema():
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


# ── Decorators ────────────────────────────────────────────────────────────────

def login_requerido(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_requerido(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('plan') != 'admin':
            flash('No tienes permisos para acceder a esa sección.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper


def plantilla_autorizada(plantilla_id):
    return plantilla_id in session.get('plantillas', [])


init_db()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('admin')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parsear_repeaters_del_form(form, repeaters_schema):
    """
    Extrae los datos de repeaters del form.
    Nombres de campo: rep__<rep_id>__<idx>__<campo_id>
    Devuelve: { rep_id: [ {campo_id: valor, ...}, ... ] }
    """
    resultado = {}
    for rep_id, rep_conf in repeaters_schema.items():
        items = {}
        for key, valor in form.items():
            partes = key.split('__')
            if len(partes) == 4 and partes[0] == 'rep' and partes[1] == rep_id:
                idx      = int(partes[2])
                campo_id = partes[3]
                items.setdefault(idx, {})[campo_id] = valor
        if items:
            resultado[rep_id] = [items[i] for i in sorted(items)]
    return resultado


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'usuario' in session else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        usuario  = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        cliente  = obtener_cliente(usuario)
        if cliente and cliente['password'] == password:
            session['usuario']    = cliente['usuario']
            session['nombre']     = cliente['nombre'] or cliente['usuario']
            session['plan']       = cliente['plan']
            session['cliente_id'] = cliente['id']
            session['plantillas'] = obtener_plantillas_cliente(cliente['id'])
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_requerido
def dashboard():
    schema             = cargar_schema()
    plantillas_cliente = session.get('plantillas', [])
    plantillas = {k: v for k, v in schema['plantillas'].items() if k in plantillas_cliente}
    return render_template('dashboard.html',
        plantillas=plantillas,
        usuario=session['usuario'],
        nombre=session.get('nombre'),
        es_admin=(session.get('plan') == 'admin')
    )


# ── Editor ────────────────────────────────────────────────────────────────────

@app.route('/editor/<plantilla_id>', methods=['GET', 'POST'])
@login_requerido
def editor(plantilla_id):
    if not plantilla_autorizada(plantilla_id):
        flash('No tienes acceso a esta plantilla', 'error')
        return redirect(url_for('dashboard'))

    schema    = cargar_schema()
    plantilla = schema['plantillas'].get(plantilla_id)
    if not plantilla:
        flash('Plantilla no encontrada', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # ── Debug: log all form keys received ─────────────────────────────────
        rep_keys = [k for k in request.form if k.startswith('rep__')]
        log.debug('[editor POST] plantilla=%s  rep_keys=%d  sample=%s',
                  plantilla_id, len(rep_keys), rep_keys[:6])

        # ── Campos regulares ──────────────────────────────────────────────────
        nuevos_valores = {}
        for seccion, items in plantilla['campos'].items():
            nuevos_valores[seccion] = {}
            for campo_id in items:
                key = f"{seccion}__{campo_id}"
                nuevos_valores[seccion][campo_id] = request.form.get(key, '')

        exito_campos = aplicar_cambios(
            plantilla['ruta'], plantilla['campos'], nuevos_valores
        )

        # ── Repeaters ─────────────────────────────────────────────────────────
        repeaters_data = _parsear_repeaters_del_form(
            request.form, plantilla.get('repeaters', {})
        )
        log.debug('[editor POST] repeaters_data keys=%s', list(repeaters_data.keys()))

        exito_repeaters = True
        for rep_id, items in repeaters_data.items():
            rep_conf = plantilla['repeaters'][rep_id]
            log.debug('[editor POST] reconstruir_seccion rep_id=%s  items=%d', rep_id, len(items))
            ok = reconstruir_seccion(
                plantilla['ruta'],
                rep_conf['contenedor'],
                rep_conf['item_selector'],
                rep_conf['campos'],
                items
            )
            log.debug('[editor POST] reconstruir_seccion rep_id=%s  ok=%s', rep_id, ok)
            if not ok:
                exito_repeaters = False

        if exito_campos and exito_repeaters:
            ok, msg = git_push(f"{session['usuario']} actualizó {plantilla_id}")
            if ok:
                flash('¡Cambios publicados! Tu sitio se actualizará en ~30 s.', 'success')
            else:
                flash(f'Guardado localmente (git: {msg})', 'warning')
        else:
            flash('Error al guardar algunos cambios. Revisa los logs del servidor.', 'error')

        return redirect(url_for('editor', plantilla_id=plantilla_id))

    # ── GET: cargar valores actuales ──────────────────────────────────────────
    valores   = extraer_valores(plantilla['ruta'], plantilla['campos'])
    secciones = list(plantilla['campos'].keys())

    repeaters_valores = {}
    for rep_id, rep_conf in plantilla.get('repeaters', {}).items():
        repeaters_valores[rep_id] = extraer_repeater(
            plantilla['ruta'],
            rep_conf['contenedor'],
            rep_conf['item_selector'],
            rep_conf['campos']
        )

    return render_template('editor.html',
        plantilla_id=plantilla_id,
        plantilla=plantilla,
        valores=valores,
        secciones=secciones,
        repeaters_valores=repeaters_valores,
        usuario=session['usuario'],
        nombre=session.get('nombre')
    )


# ── Upload de imágenes ────────────────────────────────────────────────────────

@app.route('/upload/<plantilla_id>', methods=['POST'])
@login_requerido
def upload_imagen(plantilla_id):
    if not plantilla_autorizada(plantilla_id):
        return jsonify({'ok': False, 'error': 'Sin acceso'}), 403

    archivo = request.files.get('imagen')
    if not archivo or not archivo.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
        return jsonify({'ok': False, 'error': 'Formato no permitido. Usa PNG, JPG o WebP'}), 400

    carpeta = os.path.join(UPLOADS_DIR, plantilla_id)
    os.makedirs(carpeta, exist_ok=True)

    nombre = f"{uuid.uuid4().hex[:10]}{ext}"
    archivo.save(os.path.join(carpeta, nombre))

    url = url_for('static', filename=f'uploads/{plantilla_id}/{nombre}', _external=True)
    return jsonify({'ok': True, 'url': url})


# ── Preview (Cloudflare) ──────────────────────────────────────────────────────

@app.route('/preview/<plantilla_id>')
@login_requerido
def preview(plantilla_id):
    if not plantilla_autorizada(plantilla_id):
        flash('No tienes acceso a esta plantilla', 'error')
        return redirect(url_for('dashboard'))
    schema    = cargar_schema()
    plantilla = schema['plantillas'].get(plantilla_id, {})
    return redirect(plantilla.get('preview_url', '/'))


# ── Preview local (sirve el HTML desde disco, sin necesitar git push) ─────────

@app.route('/local/<plantilla_id>/')
@app.route('/local/<plantilla_id>')
@login_requerido
def preview_local(plantilla_id):
    if not plantilla_autorizada(plantilla_id):
        return redirect(url_for('dashboard'))
    schema    = cargar_schema()
    plantilla = schema['plantillas'].get(plantilla_id)
    if not plantilla:
        return 'Plantilla no encontrada', 404
    # ruta es relativa a admin/, e.g. '../index.html' → plantillas-web/index.html
    ruta_abs   = os.path.normpath(os.path.join(BASE, 'admin', plantilla['ruta']))
    directorio = os.path.dirname(ruta_abs)
    return send_from_directory(directorio, os.path.basename(ruta_abs))


@app.route('/local/<plantilla_id>/<path:filename>')
@login_requerido
def site_asset(plantilla_id, filename):
    """Sirve CSS/JS/imágenes relativos a la carpeta de la plantilla."""
    if not plantilla_autorizada(plantilla_id):
        return 'No autorizado', 403
    schema    = cargar_schema()
    plantilla = schema['plantillas'].get(plantilla_id)
    if not plantilla:
        return 'Plantilla no encontrada', 404
    ruta_abs   = os.path.normpath(os.path.join(BASE, 'admin', plantilla['ruta']))
    directorio = os.path.dirname(ruta_abs)
    return send_from_directory(directorio, filename)


# ── Admin: gestión de clientes ────────────────────────────────────────────────

@app.route('/admin/clientes')
@admin_requerido
def admin_clientes():
    schema   = cargar_schema()
    clientes = listar_clientes()
    data = [{
        'id':         c['id'],
        'usuario':    c['usuario'],
        'nombre':     c['nombre'],
        'plan':       c['plan'],
        'activo':     c['activo'],
        'plantillas': obtener_plantillas_cliente(c['id']),
    } for c in clientes]
    return render_template('admin_clientes.html',
        clientes=data,
        nombre=session.get('nombre'),
        plantillas_disponibles=list(schema['plantillas'].keys())
    )


@app.route('/admin/clientes/nuevo', methods=['GET', 'POST'])
@admin_requerido
def admin_cliente_nuevo():
    schema = cargar_schema()
    disponibles = list(schema['plantillas'].keys())
    if request.method == 'POST':
        usuario   = request.form.get('usuario', '').strip()
        password  = request.form.get('password', '').strip()
        nombre    = request.form.get('nombre', '').strip()
        plan      = request.form.get('plan', 'landing')
        seleccion = request.form.getlist('plantillas')
        if not usuario or not password:
            flash('Usuario y contraseña son obligatorios.', 'error')
        else:
            try:
                cid = crear_cliente(usuario, password, nombre, plan)
                set_accesos(cid, seleccion)
                flash(f'Cliente "{usuario}" creado correctamente.', 'success')
                return redirect(url_for('admin_clientes'))
            except Exception:
                flash(f'El usuario "{usuario}" ya existe.', 'error')
    return render_template('admin_cliente_form.html',
        modo='nuevo', cliente=None,
        plantillas_asignadas=[], plantillas_disponibles=disponibles,
        nombre=session.get('nombre')
    )


@app.route('/admin/clientes/<int:cliente_id>/editar', methods=['GET', 'POST'])
@admin_requerido
def admin_cliente_editar(cliente_id):
    schema      = cargar_schema()
    disponibles = list(schema['plantillas'].keys())
    cliente     = obtener_cliente_por_id(cliente_id)
    if not cliente:
        flash('Cliente no encontrado.', 'error')
        return redirect(url_for('admin_clientes'))
    if request.method == 'POST':
        nombre    = request.form.get('nombre', '').strip()
        password  = request.form.get('password', '').strip() or cliente['password']
        plan      = request.form.get('plan', 'landing')
        seleccion = request.form.getlist('plantillas')
        actualizar_cliente(cliente_id, nombre, password, plan)
        set_accesos(cliente_id, seleccion)
        if session.get('cliente_id') == cliente_id:
            session['nombre']     = nombre or session['nombre']
            session['plan']       = plan
            session['plantillas'] = seleccion
        flash(f'Cliente "{cliente["usuario"]}" actualizado.', 'success')
        return redirect(url_for('admin_clientes'))
    return render_template('admin_cliente_form.html',
        modo='editar', cliente=dict(cliente),
        plantillas_asignadas=obtener_plantillas_cliente(cliente_id),
        plantillas_disponibles=disponibles,
        nombre=session.get('nombre')
    )


@app.route('/admin/clientes/<int:cliente_id>/eliminar', methods=['POST'])
@admin_requerido
def admin_cliente_eliminar(cliente_id):
    cliente = obtener_cliente_por_id(cliente_id)
    if not cliente:
        flash('Cliente no encontrado.', 'error')
        return redirect(url_for('admin_clientes'))
    if session.get('cliente_id') == cliente_id:
        flash('No puedes eliminar tu propia cuenta.', 'error')
        return redirect(url_for('admin_clientes'))
    eliminar_cliente(cliente_id)
    flash(f'Cliente "{cliente["usuario"]}" eliminado.', 'success')
    return redirect(url_for('admin_clientes'))


if __name__ == '__main__':
    app.run(debug=True, port=5002)
