from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_from_directory, abort
)
import json, os, uuid, logging, time, threading
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    init_db, obtener_cliente, obtener_cliente_por_id,
    obtener_plantillas_cliente, listar_clientes,
    crear_cliente, actualizar_cliente, eliminar_cliente, set_accesos,
    # CMS multi-usuario
    listar_plantillas_activas, listar_todas_plantillas,
    obtener_plantilla_por_id, crear_plantilla, actualizar_plantilla,
    toggle_plantilla, contar_sitios_por_plantilla,
    crear_usuario, obtener_usuario_por_email, obtener_usuario_por_id,
    slug_disponible, crear_sitio as db_crear_sitio, obtener_sitios_usuario, obtener_sitio_por_id,
    obtener_sitio_por_slug,
    get_config_sitio, set_config_sitio, set_config_sitio_bulk,
    set_secciones_contenido, get_secciones_contenido,
    guardar_mensaje_contacto,
    listar_mensajes_sitio, marcar_mensaje_leido,
    verificar_disponibilidad, crear_cita, horas_ocupadas,
    listar_citas_sitio, actualizar_estado_cita,
    eliminar_sitio,
)
from parser import (
    extraer_valores, aplicar_cambios,
    extraer_repeater, reconstruir_seccion, git_push
)

app = Flask(__name__)

# ── SECRET_KEY desde variable de entorno (DT-002) ─────────────────────────────
_secret = os.environ.get('SECRET_KEY', '')
if not _secret:
    # Cargar .env manual si existe (evita dependencia de python-dotenv en dev)
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.isfile(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
        _secret = os.environ.get('SECRET_KEY', '')
if not _secret:
    import secrets as _sec
    _secret = _sec.token_hex(32)
    logging.warning('SECRET_KEY no configurada — usando clave temporal. Crea un archivo .env')

app.secret_key = _secret
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB máximo por imagen

BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE, 'shared', 'site-schema.json')
UPLOADS_DIR = os.path.join(app.static_folder, 'uploads')

# ── Rate limiter en memoria (DT-004) ──────────────────────────────────────────
# {ip: {'fails': int, 'last_fail': float, 'blocked_until': float}}
_rate_store: dict = {}
_rate_lock  = threading.Lock()
_MAX_FAILS  = 5       # intentos fallidos antes del bloqueo
_WINDOW_SEC = 300     # ventana de 5 minutos para contar fallos
_BLOCK_SEC  = 900     # bloqueo de 15 minutos

def _check_rate(ip: str) -> bool:
    """Devuelve True si la IP puede intentar login. False si está bloqueada."""
    now = time.time()
    with _rate_lock:
        entry = _rate_store.get(ip, {})
        if entry.get('blocked_until', 0) > now:
            return False
        # Limpiar ventana vencida
        if now - entry.get('last_fail', 0) > _WINDOW_SEC:
            _rate_store[ip] = {}
        return True

def _register_fail(ip: str):
    """Registra un fallo. Bloquea si supera _MAX_FAILS."""
    now = time.time()
    with _rate_lock:
        entry = _rate_store.setdefault(ip, {'fails': 0})
        if now - entry.get('last_fail', 0) > _WINDOW_SEC:
            entry['fails'] = 0
        entry['fails']     += 1
        entry['last_fail']  = now
        if entry['fails'] >= _MAX_FAILS:
            entry['blocked_until'] = now + _BLOCK_SEC
            logging.warning('Rate limit: IP %s bloqueada por %ds', ip, _BLOCK_SEC)

def _clear_rate(ip: str):
    """Limpia el contador tras login exitoso."""
    with _rate_lock:
        _rate_store.pop(ip, None)

# ── Magic bytes válidos para uploads (DT-003) ─────────────────────────────────
_MAGIC = {
    b'\xff\xd8\xff':       '.jpg',
    b'\x89PNG\r\n\x1a\n': '.png',
    b'GIF87a':             '.gif',
    b'GIF89a':             '.gif',
    b'RIFF':               '.webp',   # RIFF????WEBP
}

def _es_imagen_valida(stream) -> bool:
    """Lee los primeros 12 bytes y verifica la firma del archivo."""
    header = stream.read(12)
    stream.seek(0)
    for magic, _ in _MAGIC.items():
        if header[:len(magic)] == magic:
            if magic == b'RIFF':
                return header[8:12] == b'WEBP'
            return True
    return False


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
        ip       = request.remote_addr or '0.0.0.0'
        usuario  = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()

        if not _check_rate(ip):
            flash('Demasiados intentos fallidos. Espera 15 minutos e intenta de nuevo.', 'error')
            return render_template('login.html')

        cliente = obtener_cliente(usuario)
        # Compatibilidad: acepta hash werkzeug O texto plano (para cuentas viejas)
        autenticado = False
        if cliente:
            stored = cliente['password']
            if stored.startswith('pbkdf2:') or stored.startswith('scrypt:'):
                autenticado = check_password_hash(stored, password)
            else:
                autenticado = (stored == password)
                if autenticado:
                    # Re-hashear la contraseña en caliente
                    actualizar_cliente(cliente['id'], cliente['nombre'],
                                       generate_password_hash(password), cliente['plan'])

        if autenticado:
            _clear_rate(ip)
            session['usuario']    = cliente['usuario']
            session['nombre']     = cliente['nombre'] or cliente['usuario']
            session['plan']       = cliente['plan']
            session['cliente_id'] = cliente['id']
            session['plantillas'] = obtener_plantillas_cliente(cliente['id'])
            return redirect(url_for('dashboard'))

        _register_fail(ip)
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

    if not _es_imagen_valida(archivo.stream):
        return jsonify({'ok': False, 'error': 'El archivo no es una imagen válida'}), 400

    carpeta = os.path.join(UPLOADS_DIR, plantilla_id)
    os.makedirs(carpeta, exist_ok=True)

    nombre = f"{uuid.uuid4().hex[:10]}{ext}"
    archivo.save(os.path.join(carpeta, nombre))

    url = url_for('static', filename=f'uploads/{plantilla_id}/{nombre}')
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
                cid = crear_cliente(usuario, generate_password_hash(password), nombre, plan)
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
        pw_raw    = request.form.get('password', '').strip()
        # Si el admin dejó el campo vacío, conservar la contraseña actual
        if pw_raw:
            password = generate_password_hash(pw_raw)
        else:
            password = cliente['password']
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


# ══════════════════════════════════════════════════════════════════════════════
# Admin — CRUD de Plantillas CMS
# ══════════════════════════════════════════════════════════════════════════════

_SECCIONES_DISPONIBLES = [
    ('apariencia', 'Apariencia (colores y tipografía)'),
    ('marca',      'Marca (logo y nombre)'),
    ('hero',       'Hero (imagen y títulos de portada)'),
    ('nosotros',   'Nosotros (descripción, misión, visión, valores)'),
    ('servicios',  'Servicios (lista de servicios)'),
    ('proyectos',  'Proyectos (portafolio)'),
    ('equipo',     'Equipo (integrantes)'),
    ('contacto',   'Contacto (info y formulario)'),
]


@app.route('/admin/plantillas')
@admin_requerido
def admin_plantillas():
    plantillas = listar_todas_plantillas()
    conteos = {p['id']: contar_sitios_por_plantilla(p['id']) for p in plantillas}
    return render_template('admin_plantillas.html',
                           plantillas=plantillas, conteos=conteos)


@app.route('/admin/plantillas/nueva', methods=['GET', 'POST'])
@admin_requerido
def admin_plantilla_nueva():
    if request.method == 'POST':
        clave       = request.form.get('clave', '').strip().lower()
        nombre      = request.form.get('nombre', '').strip()
        tipo        = request.form.get('tipo', 'landing')
        descripcion = request.form.get('descripcion', '').strip()
        preview_img = request.form.get('preview_img', '').strip()
        secciones   = request.form.getlist('secciones')

        if not clave or not nombre:
            flash('La clave y el nombre son obligatorios.', 'error')
            return render_template('admin_plantilla_form.html',
                                   modo='nueva', p=None,
                                   secciones_disponibles=_SECCIONES_DISPONIBLES,
                                   secciones_activas=[])

        import re as _re
        if not _re.match(r'^[a-z][a-z0-9_-]{1,29}$', clave):
            flash('La clave solo puede tener letras minúsculas, números, guiones y guiones bajos.', 'error')
            return render_template('admin_plantilla_form.html',
                                   modo='nueva', p=None,
                                   secciones_disponibles=_SECCIONES_DISPONIBLES,
                                   secciones_activas=secciones)

        campos_schema = json.dumps({'secciones': secciones}, ensure_ascii=False)
        try:
            crear_plantilla(clave, nombre, tipo, descripcion, preview_img, campos_schema)
            flash(f'Plantilla "{nombre}" creada correctamente.', 'success')
            return redirect(url_for('admin_plantillas'))
        except Exception as e:
            flash(f'Error: la clave "{clave}" ya existe.', 'error')
            return render_template('admin_plantilla_form.html',
                                   modo='nueva', p=None,
                                   secciones_disponibles=_SECCIONES_DISPONIBLES,
                                   secciones_activas=secciones)

    return render_template('admin_plantilla_form.html',
                           modo='nueva', p=None,
                           secciones_disponibles=_SECCIONES_DISPONIBLES,
                           secciones_activas=[s[0] for s in _SECCIONES_DISPONIBLES])


@app.route('/admin/plantillas/<int:plantilla_id>/editar', methods=['GET', 'POST'])
@admin_requerido
def admin_plantilla_editar(plantilla_id):
    p = obtener_plantilla_por_id(plantilla_id)
    if not p:
        flash('Plantilla no encontrada.', 'error')
        return redirect(url_for('admin_plantillas'))

    try:
        schema_actual = json.loads(p['campos_schema'] or '{}')
    except Exception:
        schema_actual = {}
    secciones_activas = schema_actual.get('secciones', [s[0] for s in _SECCIONES_DISPONIBLES])

    if request.method == 'POST':
        nombre      = request.form.get('nombre', '').strip()
        tipo        = request.form.get('tipo', 'landing')
        descripcion = request.form.get('descripcion', '').strip()
        preview_img = request.form.get('preview_img', '').strip()
        secciones   = request.form.getlist('secciones')

        if not nombre:
            flash('El nombre es obligatorio.', 'error')
            return render_template('admin_plantilla_form.html',
                                   modo='editar', p=p,
                                   secciones_disponibles=_SECCIONES_DISPONIBLES,
                                   secciones_activas=secciones)

        campos_schema = json.dumps({'secciones': secciones}, ensure_ascii=False)
        actualizar_plantilla(plantilla_id, nombre, tipo, descripcion, preview_img, campos_schema)
        flash(f'Plantilla "{nombre}" actualizada.', 'success')
        return redirect(url_for('admin_plantillas'))

    return render_template('admin_plantilla_form.html',
                           modo='editar', p=p,
                           secciones_disponibles=_SECCIONES_DISPONIBLES,
                           secciones_activas=secciones_activas)


@app.route('/admin/plantillas/<int:plantilla_id>/toggle', methods=['POST'])
@admin_requerido
def admin_plantilla_toggle(plantilla_id):
    p = obtener_plantilla_por_id(plantilla_id)
    if not p:
        flash('Plantilla no encontrada.', 'error')
    else:
        toggle_plantilla(plantilla_id)
        estado = 'desactivada' if p['activo'] else 'activada'
        flash(f'Plantilla "{p["nombre"]}" {estado}.', 'success')
    return redirect(url_for('admin_plantillas'))


# ══════════════════════════════════════════════════════════════════════════════
# CMS — Rutas para usuarios finales (registro, login, panel, crear sitio)
# Session keys: 'uid', 'u_email', 'u_nombre' (distintos de los del admin)
# ══════════════════════════════════════════════════════════════════════════════

import re

_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$')


def usuario_requerido(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            flash('Inicia sesión para acceder a tu panel.', 'warning')
            return redirect(url_for('entrar'))
        return f(*args, **kwargs)
    return wrapper


# ── Registro ──────────────────────────────────────────────────────────────────

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'uid' in session:
        return redirect(url_for('mi_panel'))

    if request.method == 'POST':
        nombre   = request.form.get('nombre', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm  = request.form.get('confirm', '').strip()

        error = None
        if not nombre or not email or not password:
            error = 'Todos los campos son obligatorios.'
        elif '@' not in email or '.' not in email:
            error = 'Ingresa un email válido.'
        elif len(password) < 8:
            error = 'La contraseña debe tener al menos 8 caracteres.'
        elif password != confirm:
            error = 'Las contraseñas no coinciden.'
        elif obtener_usuario_por_email(email):
            error = 'Ya existe una cuenta con ese email.'

        if error:
            flash(error, 'error')
        else:
            try:
                uid = crear_usuario(email, generate_password_hash(password), nombre)
                session['uid']      = uid
                session['u_email']  = email
                session['u_nombre'] = nombre
                flash(f'Bienvenido, {nombre}. Tu cuenta fue creada.', 'success')
                return redirect(url_for('crear_sitio'))
            except Exception:
                flash('Error al crear la cuenta. Intenta de nuevo.', 'error')

    return render_template('registro.html')


# ── Login usuario ─────────────────────────────────────────────────────────────

@app.route('/entrar', methods=['GET', 'POST'])
def entrar():
    if 'uid' in session:
        return redirect(url_for('mi_panel'))

    if request.method == 'POST':
        ip       = request.remote_addr or '0.0.0.0'
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not _check_rate(ip):
            flash('Demasiados intentos fallidos. Espera 15 minutos.', 'error')
            return render_template('entrar.html')

        usuario = obtener_usuario_por_email(email)
        if usuario and check_password_hash(usuario['password'], password):
            _clear_rate(ip)
            session['uid']      = usuario['id']
            session['u_email']  = usuario['email']
            session['u_nombre'] = usuario['nombre'] or email.split('@')[0]
            return redirect(url_for('mi_panel'))

        _register_fail(ip)
        flash('Email o contraseña incorrectos.', 'error')

    return render_template('entrar.html')


# ── Logout usuario ────────────────────────────────────────────────────────────

@app.route('/salir')
def salir():
    session.pop('uid', None)
    session.pop('u_email', None)
    session.pop('u_nombre', None)
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('entrar'))


# ── Panel del usuario ─────────────────────────────────────────────────────────

@app.route('/mi-panel')
@usuario_requerido
def mi_panel():
    sitios = obtener_sitios_usuario(session['uid'])
    return render_template('mi_panel.html',
        nombre=session['u_nombre'],
        email=session['u_email'],
        sitios=sitios
    )


# ── Crear sitio ───────────────────────────────────────────────────────────────

@app.route('/crear-sitio', methods=['GET', 'POST'])
@usuario_requerido
def crear_sitio():
    plantillas = listar_plantillas_activas()

    if request.method == 'POST':
        plantilla_id  = request.form.get('plantilla_id', '').strip()
        nombre_sitio  = request.form.get('nombre_sitio', '').strip()
        slug          = request.form.get('slug', '').strip().lower()
        formato       = request.form.get('formato', 'web5').strip()
        if formato not in ('landing', 'web5'):
            formato = 'web5'

        error = None
        if not plantilla_id or not plantilla_id.isdigit():
            error = 'Selecciona una plantilla.'
        elif not nombre_sitio:
            error = 'Ingresa el nombre de tu negocio.'
        elif not _SLUG_RE.match(slug):
            error = 'El nombre del sitio solo puede tener letras minúsculas, números y guiones (mínimo 3 caracteres).'
        elif not slug_disponible(slug):
            error = 'Ese nombre de sitio ya está en uso. Elige otro.'
        elif not obtener_plantilla_por_id(int(plantilla_id)):
            error = 'Plantilla no válida.'

        if error:
            flash(error, 'error')
        else:
            try:
                sitio_id = db_crear_sitio(
                    session['uid'], int(plantilla_id), slug, nombre_sitio, formato
                )
                # Obtener la clave de la plantilla elegida para aplicar defaults específicos
                _pobj = obtener_plantilla_por_id(int(plantilla_id))
                _clave = _pobj['clave'] if _pobj else 'empresa'

                # Identidades visuales por plantilla
                _temas = {
                    'doctores': {
                        'color_primario':  '#1e6abf',
                        'color_acento':    '#e53e3e',
                        'color_footer_bg': '#0f2952',
                        'color_navbar_bg': '#1e6abf',
                        'color_texto':     '#1e293b',
                        'fuente_titulos':  'Lato',
                        'fuente_cuerpo':   'Lato',
                        'estilo_esquinas': 'redondeado',
                        'estilo_icono':    'circulo',
                        'hero_eyebrow':    'ATENCIÓN MÉDICA DE CALIDAD',
                        'hero_titulo':     f'Bienvenidos a {nombre_sitio}',
                        'hero_subtitulo':  'Cuidamos tu salud con profesionalismo y dedicación. Agenda tu cita hoy.',
                        'hero_cta_texto':  'Agendar cita',
                        'menu_servicios':  'Especialidades',
                        'menu_proyectos':  'Casos de éxito',
                        'nosotros_mision': 'Brindar atención médica de excelencia con tecnología moderna y un trato humano.',
                        'nosotros_vision': 'Ser el consultorio médico de referencia de nuestra comunidad.',
                        'nosotros_valores':  'Ética, Precisión, Compasión, Compromiso',
                        'menu_equipo':       'Especialistas',
                        'menu_proyectos':    'Casos clínicos',
                        'menu_contacto':     'Agendar cita',
                        'hero_cta_href':     '#cita',
                        'servicios_descripcion': 'Contamos con las especialidades médicas que necesitas.',
                        'equipo_descripcion':    'Nuestro equipo de especialistas certificados a tu servicio.',
                    },
                    'restaurante': {
                        'color_primario':    '#c2410c',
                        'color_acento':      '#d97706',
                        'color_footer_bg':   '#1c0a00',
                        'color_navbar_bg':   '#7c2d12',
                        'color_seccion_bg':  '#fff7ed',
                        'color_texto':       '#1c1917',
                        'fuente_titulos':    'Playfair Display',
                        'fuente_cuerpo':     'Lato',
                        'estilo_esquinas':   'suave',
                        'estilo_icono':      'emoji',
                        'hero_alineacion':   'centro',
                        'hero_eyebrow':      'Gastronomía auténtica',
                        'hero_titulo':       nombre_sitio,
                        'hero_subtitulo':    'Sabores que despiertan los sentidos. Ven y disfruta una experiencia única.',
                        'hero_cta_texto':    'Ver menú',
                        'hero_cta2_texto':   'Reservar mesa',
                        'menu_servicios':    'Menú',
                        'menu_proyectos':    'Galería',
                        'menu_equipo':       'Chef',
                        'nosotros_mision':   'Ofrecer una experiencia gastronómica auténtica con ingredientes frescos y recetas tradicionales.',
                        'nosotros_vision':   'Ser el restaurante favorito de nuestra ciudad.',
                        'nosotros_valores':  'Frescura, Tradición, Hospitalidad, Pasión',
                        'servicios_descripcion': 'Una selección cuidadosa de platos preparados con ingredientes de primera.',
                        'proyectos_descripcion': 'Momentos especiales que hemos celebrado juntos.',
                    },
                    'arquitectura': {
                        'color_primario':  '#1a1a2e',
                        'color_acento':    '#c9a84c',
                        'color_footer_bg': '#0d0d1a',
                        'color_navbar_bg': '#1a1a2e',
                        'color_texto':     '#2d3748',
                        'fuente_titulos':  'Raleway',
                        'fuente_cuerpo':   'Open Sans',
                        'estilo_esquinas': 'cuadrado',
                        'estilo_sombra':   'marcada',
                        'hero_eyebrow':    'ARQUITECTURA & DISEÑO',
                        'hero_titulo':     nombre_sitio,
                        'hero_subtitulo':  'Transformamos espacios en experiencias. Diseño con propósito.',
                        'hero_cta_texto':  'Ver proyectos',
                        'menu_servicios':  'Servicios',
                        'menu_proyectos':  'Portafolio',
                        'nosotros_mision': 'Diseñar espacios funcionales y estéticamente superiores que mejoren la calidad de vida.',
                        'nosotros_vision': 'Ser referente del diseño arquitectónico en la región.',
                        'nosotros_valores':'Precisión, Creatividad, Sostenibilidad, Innovación',
                    },
                    'salon': {
                        'color_primario':  '#b4327a',
                        'color_acento':    '#f9a8d4',
                        'color_footer_bg': '#1a0a12',
                        'color_navbar_bg': '#b4327a',
                        'color_seccion_bg':'#fff0f6',
                        'fuente_titulos':  'Playfair Display',
                        'fuente_cuerpo':   'Lato',
                        'estilo_esquinas': 'muy-redondeado',
                        'estilo_icono':    'circulo',
                        'hero_eyebrow':    'Belleza & Bienestar',
                        'hero_titulo':     nombre_sitio,
                        'hero_subtitulo':  'Tu espacio de relajación y transformación. Luce y siéntete increíble.',
                        'hero_cta_texto':  'Reservar cita',
                        'menu_servicios':  'Tratamientos',
                        'menu_proyectos':  'Galería',
                        'menu_equipo':     'Nuestro equipo',
                        'nosotros_mision': 'Realzar la belleza natural de cada cliente con técnicas modernas y atención personalizada.',
                        'nosotros_valores':'Elegancia, Cuidado, Confianza, Creatividad',
                    },
                    'abogados': {
                        'color_primario':  '#1e3a5f',
                        'color_acento':    '#c9a84c',
                        'color_footer_bg': '#0d1b2a',
                        'color_navbar_bg': '#1e3a5f',
                        'color_texto':     '#1a202c',
                        'fuente_titulos':  'Merriweather',
                        'fuente_cuerpo':   'Open Sans',
                        'estilo_esquinas': 'cuadrado',
                        'estilo_sombra':   'sutil',
                        'hero_eyebrow':    'ASESORÍA LEGAL DE CONFIANZA',
                        'hero_titulo':     nombre_sitio,
                        'hero_subtitulo':  'Defendemos tus derechos con experiencia, ética y dedicación.',
                        'hero_cta_texto':  'Consulta gratuita',
                        'menu_servicios':  'Áreas de práctica',
                        'menu_proyectos':  'Casos',
                        'nosotros_mision': 'Proveer servicios legales de alta calidad con ética e integridad.',
                        'nosotros_valores':'Integridad, Confidencialidad, Justicia, Excelencia',
                    },
                }
                _defaults_tema = _temas.get(_clave, {})

                # Config base (aplica a todas las plantillas)
                _config_base = {
                    'nombre_negocio':       nombre_sitio,
                    'color_primario':       '#0bb180',
                    'color_footer_bg':      '#0d1b2a',
                    'color_texto':          '#2d3748',
                    'logo_url':             '',
                    'hero_eyebrow':         nombre_sitio.upper(),
                    'hero_titulo':          f'Bienvenidos a {nombre_sitio}',
                    'hero_subtitulo':       'Tu descripción va aquí. Cuéntanos sobre tu negocio.',
                    'hero_imagen':          '',
                    'hero_cta_texto':       'Contáctanos',
                    'hero_cta_href':        '#contacto',
                    'hero_cta2_texto':      'Ver servicios',
                    'hero_cta2_href':       '#servicios',
                    'nosotros_descripcion': f'Somos {nombre_sitio}, comprometidos con la excelencia y la satisfacción de nuestros clientes.',
                    'nosotros_mision':      'Nuestra misión es ofrecer soluciones de alta calidad que superen las expectativas de nuestros clientes.',
                    'nosotros_vision':      'Ser líderes en nuestra industria, reconocidos por nuestra innovación y compromiso con la calidad.',
                    'nosotros_valores':     'Integridad, Excelencia, Innovación, Compromiso',
                    'servicios_descripcion': 'Ofrecemos soluciones adaptadas a las necesidades de cada cliente.',
                    'proyectos_descripcion': 'Una muestra de nuestros trabajos más destacados.',
                    'equipo_descripcion':    'Profesionales comprometidos con tu éxito.',
                    'contacto_descripcion':  '¿Quieres saber más? Escríbenos y te responderemos pronto.',
                    'contacto_telefono':    '(809) 000-0000',
                    'contacto_email':       f'info@{slug}.com',
                    'contacto_direccion':   'Calle Principal 123, Ciudad',
                    'footer_descripcion':   'Comprometidos con la excelencia y satisfacción de nuestros clientes.',
                }
                # El tema de la plantilla sobreescribe los defaults base
                _config_base.update(_defaults_tema)
                set_config_sitio_bulk(sitio_id, _config_base)

                # Secciones de contenido por defecto — varían según la plantilla
                if _clave == 'doctores':
                    set_secciones_contenido(sitio_id, 'servicios', [
                        {'titulo': 'Medicina General', 'desc': 'Atención primaria, diagnóstico y tratamiento de enfermedades comunes.', 'imagen': ''},
                        {'titulo': 'Cardiología', 'desc': 'Diagnóstico y tratamiento de enfermedades del corazón y sistema circulatorio.', 'imagen': ''},
                        {'titulo': 'Pediatría', 'desc': 'Atención médica integral para niños y adolescentes.', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'proyectos', [
                        {'titulo': 'Caso clínico 1', 'categoria': 'Cardiología', 'imagen': ''},
                        {'titulo': 'Caso clínico 2', 'categoria': 'Medicina General', 'imagen': ''},
                        {'titulo': 'Caso clínico 3', 'categoria': 'Pediatría', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'equipo', [
                        {'nombre': 'Dr. Nombre Apellido', 'rol': 'Médico General', 'credenciales': 'Medicina General · Universidad Nacional', 'foto': '', 'email': '', 'telefono': '', 'whatsapp': ''},
                        {'nombre': 'Dra. Nombre Apellido', 'rol': 'Cardióloga', 'credenciales': 'Cardiología · Hospital Central', 'foto': '', 'email': '', 'telefono': '', 'whatsapp': ''},
                        {'nombre': 'Dr. Nombre Apellido', 'rol': 'Pediatra', 'credenciales': 'Pediatría · Instituto Médico', 'foto': '', 'email': '', 'telefono': '', 'whatsapp': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'testimonios', [
                        {'nombre': 'María García', 'texto': 'Excelente atención médica. Los especialistas son muy profesionales y el trato es muy humano. Lo recomiendo al 100%.', 'especialidad': 'Paciente de Cardiología'},
                        {'nombre': 'Juan Pérez', 'texto': 'Mi hijo ha sido atendido aquí desde pequeño. Los pediatras son increíbles, siempre con mucha paciencia y dedicación.', 'especialidad': 'Padre de paciente'},
                        {'nombre': 'Ana Rodríguez', 'texto': 'Servicio de primera calidad. Las instalaciones son modernas y el personal siempre está dispuesto a ayudar.', 'especialidad': 'Paciente de Medicina General'},
                    ])
                elif _clave == 'restaurante':
                    set_secciones_contenido(sitio_id, 'servicios', [
                        {'titulo': 'Entradas', 'desc': 'Selección de entradas frescas para comenzar tu experiencia.', 'imagen': ''},
                        {'titulo': 'Platos principales', 'desc': 'Nuestros platos estrella preparados con ingredientes de primera.', 'imagen': ''},
                        {'titulo': 'Postres', 'desc': 'Dulces tentaciones para cerrar con el mejor sabor.', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'proyectos', [
                        {'titulo': 'Cena romántica', 'categoria': 'Eventos', 'imagen': ''},
                        {'titulo': 'Celebración familiar', 'categoria': 'Eventos', 'imagen': ''},
                        {'titulo': 'Plato del día', 'categoria': 'Menú', 'imagen': ''},
                        {'titulo': 'Nuestro ambiente', 'categoria': 'Galería', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'equipo', [
                        {'nombre': 'Chef Nombre', 'rol': 'Chef Ejecutivo', 'foto': ''},
                        {'nombre': 'Nombre Apellido', 'rol': 'Sous Chef', 'foto': ''},
                        {'nombre': 'Nombre Apellido', 'rol': 'Sommelier', 'foto': ''},
                    ])
                else:
                    set_secciones_contenido(sitio_id, 'servicios', [
                        {'titulo': 'Servicio 1', 'desc': 'Descripción del primer servicio que ofreces.', 'imagen': ''},
                        {'titulo': 'Servicio 2', 'desc': 'Descripción del segundo servicio que ofreces.', 'imagen': ''},
                        {'titulo': 'Servicio 3', 'desc': 'Descripción del tercer servicio que ofreces.', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'proyectos', [
                        {'titulo': 'Proyecto 1', 'categoria': 'Categoría', 'imagen': ''},
                        {'titulo': 'Proyecto 2', 'categoria': 'Categoría', 'imagen': ''},
                        {'titulo': 'Proyecto 3', 'categoria': 'Categoría', 'imagen': ''},
                        {'titulo': 'Proyecto 4', 'categoria': 'Categoría', 'imagen': ''},
                    ])
                    set_secciones_contenido(sitio_id, 'equipo', [
                        {'nombre': 'Nombre Apellido', 'rol': 'Director General', 'foto': ''},
                        {'nombre': 'Nombre Apellido', 'rol': 'Gerente', 'foto': ''},
                        {'nombre': 'Nombre Apellido', 'rol': 'Coordinador', 'foto': ''},
                    ])
                flash(f'Sitio "{nombre_sitio}" creado. Ahora puedes personalizarlo.', 'success')
                return redirect(url_for('mi_panel'))
            except Exception as e:
                log.error('[crear_sitio] error: %s', e)
                flash('Error al crear el sitio. Intenta de nuevo.', 'error')

    return render_template('crear_sitio.html',
        nombre=session['u_nombre'],
        plantillas=plantillas
    )


# ══════════════════════════════════════════════════════════════════════════════
# Editor de sitio del usuario — /editar/<sitio_id>
# Naming fields: cfg__<clave>  y  rep__<seccion>__<idx>__<campo>
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/editar/<int:sitio_id>', methods=['GET', 'POST'])
@usuario_requerido
def editar_sitio(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)

    if request.method == 'POST':
        # ── Campos de configuración (cfg__clave) ─────────────────────────────
        config_nuevo = {}
        for key, val in request.form.items():
            if key.startswith('cfg__'):
                config_nuevo[key[5:]] = val.strip()
        if config_nuevo:
            set_config_sitio_bulk(sitio_id, config_nuevo)

        # ── Repeaters (rep__seccion__idx__campo) ──────────────────────────────
        secciones_nuevas = {}
        for key, val in request.form.items():
            if key.startswith('rep__'):
                parts = key.split('__')
                if len(parts) == 4:
                    _, seccion, idx_str, campo = parts
                    try:
                        idx = int(idx_str)
                    except ValueError:
                        continue
                    secciones_nuevas.setdefault(seccion, {}).setdefault(idx, {})[campo] = val.strip()

        for seccion, items_dict in secciones_nuevas.items():
            items = [items_dict[i] for i in sorted(items_dict.keys())]
            set_secciones_contenido(sitio_id, seccion, items)

        flash('Cambios guardados. Tu sitio está actualizado.', 'success')
        return redirect(url_for('editar_sitio', sitio_id=sitio_id))

    config   = get_config_sitio(sitio_id)
    secciones = {
        'servicios': get_secciones_contenido(sitio_id, 'servicios'),
        'proyectos': get_secciones_contenido(sitio_id, 'proyectos'),
        'equipo':    get_secciones_contenido(sitio_id, 'equipo'),
    }
    # Secciones habilitadas según el schema de la plantilla
    plantilla = obtener_plantilla_por_id(sitio['plantilla_id'])
    try:
        schema = json.loads(plantilla['campos_schema'] or '{}') if plantilla else {}
    except Exception:
        schema = {}
    _todas = ['apariencia', 'marca', 'hero', 'nosotros', 'servicios', 'proyectos', 'equipo', 'contacto']
    secciones_editor = schema.get('secciones', _todas)

    return render_template('editor_sitio.html',
        sitio=sitio,
        config=config,
        secciones=secciones,
        nombre=session['u_nombre'],
        secciones_editor=secciones_editor,
    )


@app.route('/upload-sitio/<int:sitio_id>', methods=['POST'])
@usuario_requerido
def upload_sitio(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        return jsonify({'ok': False, 'error': 'Sin acceso'}), 403

    archivo = request.files.get('imagen')
    if not archivo or not archivo.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
        return jsonify({'ok': False, 'error': 'Formato no permitido. Usa PNG, JPG o WebP'}), 400

    if not _es_imagen_valida(archivo.stream):
        return jsonify({'ok': False, 'error': 'El archivo no es una imagen válida'}), 400

    carpeta = os.path.join(UPLOADS_DIR, f'sitio_{sitio_id}')
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"{uuid.uuid4().hex[:10]}{ext}"
    archivo.save(os.path.join(carpeta, nombre))

    url = url_for('static', filename=f'uploads/sitio_{sitio_id}/{nombre}')
    return jsonify({'ok': True, 'url': url})


# ══════════════════════════════════════════════════════════════════════════════
# Sitios públicos — /s/<slug>/
# ══════════════════════════════════════════════════════════════════════════════

_PAGINAS_WEB5 = ['nosotros', 'servicios', 'proyectos', 'contacto']


def _contexto_sitio(sitio):
    """Carga config + secciones comunes para cualquier sitio."""
    sid = sitio['id']
    return {
        'config':   get_config_sitio(sid),
        'secciones': {
            'servicios':   get_secciones_contenido(sid, 'servicios'),
            'proyectos':   get_secciones_contenido(sid, 'proyectos'),
            'equipo':      get_secciones_contenido(sid, 'equipo'),
            'testimonios': get_secciones_contenido(sid, 'testimonios'),
        },
    }


@app.route('/s/<slug>/')
@app.route('/s/<slug>')
def ver_sitio(slug):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        abort(404)
    ctx = _contexto_sitio(sitio)
    clave  = sitio['plantilla_clave']
    # Formato: 'landing' = una sola página propia, 'web5' = multi-página empresa
    formato = sitio['formato'] if 'formato' in sitio.keys() else 'web5'
    if formato == 'landing':
        # Landing page: cada plantilla usa su propio index.html de una sola página
        template = f'sites/{clave}/index.html'
    else:
        # Web completa (web5): sistema multi-página basado en empresa
        template = 'sites/empresa/inicio.html'
    return render_template(template, sitio=sitio, pagina_activa='inicio', **ctx)


@app.route('/s/<slug>/<pagina>/')
@app.route('/s/<slug>/<pagina>')
def ver_pagina(slug, pagina):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio or sitio['plantilla_tipo'] != 'web5' or pagina not in _PAGINAS_WEB5:
        abort(404)
    ctx = _contexto_sitio(sitio)
    return render_template(
        f'sites/empresa/{pagina}.html',
        sitio=sitio, pagina_activa=pagina, **ctx
    )


@app.route('/s/<slug>/enviar-contacto', methods=['POST'])
def enviar_contacto(slug):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        return jsonify({'ok': False}), 404
    # Acepta JSON (fetch) o form-data
    if request.is_json:
        data     = request.get_json(silent=True) or {}
        nombre   = data.get('nombre', '').strip()
        email_c  = data.get('email', '').strip()
        telefono = data.get('telefono', '').strip()
        mensaje  = data.get('mensaje', '').strip()
    else:
        nombre   = request.form.get('nombre', '').strip()
        email_c  = request.form.get('email', '').strip()
        telefono = request.form.get('telefono', '').strip()
        mensaje  = request.form.get('mensaje', '').strip()
    if not nombre or not email_c or not mensaje:
        return jsonify({'ok': False, 'error': 'Nombre, email y mensaje son obligatorios.'}), 400
    guardar_mensaje_contacto(sitio['id'], nombre, email_c, telefono, mensaje)
    return jsonify({'ok': True, 'msg': '¡Mensaje recibido! Te contactaremos pronto.'})


# ── Sistema de citas ──────────────────────────────────────────────────────────

@app.route('/s/<slug>/agendar')
def agendar_cita(slug):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        abort(404)
    ctx = _contexto_sitio(sitio)
    especialistas = ctx['secciones'].get('equipo', [])
    return render_template('sites/empresa/cita.html',
        sitio=sitio, pagina_activa='cita',
        especialistas=especialistas, **ctx)

@app.route('/s/<slug>/horas-ocupadas')
def horas_ocupadas_api(slug):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        return jsonify([])
    especialista = request.args.get('especialista', '')
    fecha        = request.args.get('fecha', '')
    if not especialista or not fecha:
        return jsonify([])
    ocupadas = horas_ocupadas(sitio['id'], especialista, fecha)
    return jsonify(ocupadas)

@app.route('/s/<slug>/agendar', methods=['POST'])
def crear_cita_pub(slug):
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        return jsonify({'ok': False}), 404
    data = request.get_json(silent=True) or {}
    especialista    = data.get('especialista', '').strip()
    fecha           = data.get('fecha', '').strip()
    hora            = data.get('hora', '').strip()
    paciente_nombre = data.get('nombre', '').strip()
    paciente_email  = data.get('email', '').strip()
    paciente_tel    = data.get('telefono', '').strip()
    motivo          = data.get('motivo', '').strip()

    if not all([especialista, fecha, hora, paciente_nombre, paciente_tel]):
        return jsonify({'ok': False, 'error': 'Completa todos los campos obligatorios.'}), 400

    if not verificar_disponibilidad(sitio['id'], especialista, fecha, hora):
        return jsonify({'ok': False,
                        'error': f'Lo sentimos, el horario {hora} del {fecha} con {especialista} ya está reservado. Por favor elige otro horario.'}), 409

    crear_cita(sitio['id'], especialista, fecha, hora,
               paciente_nombre, paciente_email, paciente_tel, motivo)
    return jsonify({'ok': True,
                    'msg': f'¡Cita confirmada! {especialista} te atenderá el {fecha} a las {hora}. Recibirás un recordatorio.'})

# ── Panel de citas del dueño del sitio ───────────────────────────────────────

@app.route('/mis-citas/<int:sitio_id>')
@usuario_requerido
def mis_citas(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    citas = listar_citas_sitio(sitio_id)
    return render_template('mis_citas.html',
        sitio=sitio, citas=citas, nombre=session['u_nombre'])

@app.route('/mis-citas/<int:sitio_id>/cambiar-estado', methods=['POST'])
@usuario_requerido
def cambiar_estado_cita(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    cita_id = request.form.get('cita_id', type=int)
    estado  = request.form.get('estado', '')
    if cita_id and estado in ('pendiente', 'confirmada', 'cancelada'):
        actualizar_estado_cita(cita_id, estado)
    return redirect(url_for('mis_citas', sitio_id=sitio_id))


@app.route('/eliminar-sitio/<int:sitio_id>', methods=['POST'])
@usuario_requerido
def eliminar_sitio_route(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    nombre = sitio['nombre']
    eliminar_sitio(sitio_id)
    flash(f'El sitio "{nombre}" fue eliminado correctamente.', 'success')
    return redirect(url_for('mi_panel'))


if __name__ == '__main__':
    app.run(debug=True, port=5002)
