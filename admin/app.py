from flask import (
    Flask, render_template, render_template_string, request, redirect,
    url_for, session, flash, jsonify, abort
)
import json, os, uuid, logging, time, threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    init_db, obtener_cliente, obtener_cliente_por_id,
    obtener_plantillas_cliente, listar_clientes,
    crear_cliente, actualizar_cliente, eliminar_cliente, set_accesos,
    # CMS multi-usuario
    listar_plantillas_activas, listar_todas_plantillas,
    obtener_plantilla_por_id, crear_plantilla, actualizar_plantilla,
    toggle_plantilla, contar_sitios_por_plantilla, eliminar_plantilla,
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
    get_estilos, upsert_estilos,
    crear_reset_token, obtener_usuario_por_reset_token,
    invalidar_reset_token, actualizar_password_usuario,
    crear_o_vincular_google,
    obtener_cliente_por_email, actualizar_email_cliente,
    crear_admin_reset_token, obtener_cliente_por_reset_token,
    invalidar_admin_reset_token, actualizar_password_cliente,
    # Planes
    listar_planes, listar_todos_planes, obtener_plan, obtener_plan_por_clave,
    asignar_plan_cliente,
    registrar_cliente_publico, activar_usuario,
    listar_usuarios_pendientes, contar_clientes_por_plan,
    toggle_plan, crear_plan,
    obtener_usuario_por_email_cualquier_estado,
)
app = Flask(__name__)

from plantillas_editor import bp as _editor_bp
app.register_blueprint(_editor_bp)

# ── SECRET_KEY desde variable de entorno (DT-002) ─────────────────────────────
# Cargar .env siempre (setdefault no sobreescribe variables del sistema)
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
import json as _json
app.jinja_env.filters['from_json'] = _json.loads
app.jinja_env.filters['fromjson'] = _json.loads
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB máximo por imagen

# ── Configuración SMTP (variables de entorno en PythonAnywhere) ───────────────
MAIL_SERVER   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
MAIL_PORT     = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USER     = os.environ.get('MAIL_USER',     '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_FROM     = os.environ.get('MAIL_FROM',     MAIL_USER)

# ── SendGrid ──────────────────────────────────────────────────────────────────
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDGRID_FROM    = os.environ.get('SENDGRID_FROM', MAIL_FROM)

# ── Configuración Google OAuth ────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_AUTH_URL      = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL     = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL  = 'https://www.googleapis.com/oauth2/v3/userinfo'


def _enviar_email_reset(destinatario: str, nombre: str, reset_url: str):
    """Envía email de reset via SendGrid API (HTTPS — funciona en PythonAnywhere free)."""
    if not SENDGRID_API_KEY or not SENDGRID_FROM:
        logging.warning('[mail] SENDGRID_API_KEY o SENDGRID_FROM no configurados')
        return
    import urllib.request
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#0bb180">Restablecer contraseña</h2>
      <p>Hola <strong>{nombre}</strong>,</p>
      <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>
      <p style="margin:24px 0">
        <a href="{reset_url}"
           style="background:#0bb180;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold">
          Crear nueva contraseña
        </a>
      </p>
      <p style="color:#666;font-size:13px">Este enlace expira en <strong>24 horas</strong>.<br>
      Si no solicitaste esto, ignora este correo.</p>
    </div>"""
    payload = _json.dumps({
        'personalizations': [{'to': [{'email': destinatario}]}],
        'from': {'email': SENDGRID_FROM, 'name': 'Plantillas Web RD'},
        'subject': 'Restablecer contraseña — Plantillas Web RD',
        'content': [{'type': 'text/html', 'value': html}],
    }).encode()
    try:
        req = urllib.request.Request(
            'https://api.sendgrid.com/v3/mail/send',
            data=payload,
            headers={
                'Authorization': f'Bearer {SENDGRID_API_KEY}',
                'Content-Type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            logging.info(f'[mail] Reset enviado a {destinatario} — status {resp.status}')
    except Exception as e:
        logging.warning(f'[mail] Error SendGrid enviando a {destinatario}: {e}')


def _enviar_email_notificacion(destinatario: str, sitio_nombre: str,
                                nombre: str, email_c: str,
                                telefono: str, mensaje: str):
    """Envía notificación de nuevo mensaje al dueño del sitio. Falla silenciosamente."""
    if not MAIL_USER or not MAIL_PASSWORD or not destinatario:
        return
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'📬 Nuevo mensaje en {sitio_nombre}'
        msg['From']    = f'Plantillas Web <{MAIL_FROM}>'
        msg['To']      = destinatario

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
          <div style="background:#1e40af;padding:24px;border-radius:8px 8px 0 0;">
            <h2 style="color:#fff;margin:0;font-size:18px;">
              📬 Nuevo mensaje en <strong>{sitio_nombre}</strong>
            </h2>
          </div>
          <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <tr><td style="padding:8px 0;color:#64748b;width:110px;vertical-align:top"><strong>Nombre</strong></td>
                  <td style="padding:8px 0;color:#1e293b">{nombre}</td></tr>
              <tr><td style="padding:8px 0;color:#64748b;vertical-align:top"><strong>Email</strong></td>
                  <td style="padding:8px 0"><a href="mailto:{email_c}" style="color:#1e40af">{email_c}</a></td></tr>
              {'<tr><td style="padding:8px 0;color:#64748b;vertical-align:top"><strong>Teléfono</strong></td><td style="padding:8px 0;color:#1e293b">' + telefono + '</td></tr>' if telefono else ''}
              <tr><td style="padding:8px 0;color:#64748b;vertical-align:top"><strong>Mensaje</strong></td>
                  <td style="padding:8px 0;color:#1e293b;white-space:pre-wrap">{mensaje}</td></tr>
            </table>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
            <p style="font-size:12px;color:#94a3b8;margin:0;">
              Puedes responder directamente a este correo o ver todos los mensajes en tu panel.
            </p>
          </div>
        </div>"""

        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(MAIL_USER, MAIL_PASSWORD)
            s.sendmail(MAIL_FROM, destinatario, msg.as_string())
    except Exception as e:
        logging.warning(f'[mail] Error enviando notificación a {destinatario}: {e}')

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


init_db()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('admin')


# ── Helpers ───────────────────────────────────────────────────────────────────


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


@app.route('/login/recuperar', methods=['GET', 'POST'])
def login_recuperar():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        cliente = obtener_cliente_por_email(email)
        flash('Si ese email está registrado, recibirás un enlace en unos minutos.', 'info')
        if cliente:
            token = crear_admin_reset_token(cliente['id'])
            reset_url = url_for('login_reset', token=token, _external=True)
            _enviar_email_reset(email, cliente['nombre'] or cliente['usuario'], reset_url)
        return redirect(url_for('login_recuperar'))
    return render_template('login_recuperar.html')


@app.route('/login/reset/<token>', methods=['GET', 'POST'])
def login_reset(token):
    cliente = obtener_cliente_por_reset_token(token)
    if not cliente:
        flash('El enlace no es válido o ya expiró.', 'error')
        return redirect(url_for('login_recuperar'))
    if request.method == 'POST':
        nueva    = request.form.get('password', '').strip()
        confirmar = request.form.get('confirm', '').strip()
        if len(nueva) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
        elif nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'error')
        else:
            actualizar_password_cliente(cliente['id'], generate_password_hash(nueva))
            invalidar_admin_reset_token(token)
            flash('Contraseña actualizada. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('login_reset.html', token=token)


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
    flash('El editor legado fue desactivado. Usa el panel de sitios para personalizar tu sitio.', 'warning')
    return redirect(url_for('mi_panel'))


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
        email     = request.form.get('email', '').strip().lower()
        pw_raw    = request.form.get('password', '').strip()
        # Si el admin dejó el campo vacío, conservar la contraseña actual
        if pw_raw:
            password = generate_password_hash(pw_raw)
        else:
            password = cliente['password']
        plan      = request.form.get('plan', 'landing')
        seleccion = request.form.getlist('plantillas')
        actualizar_cliente(cliente_id, nombre, password, plan)
        if email:
            actualizar_email_cliente(cliente_id, email)
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


@app.route('/admin/debug-sitio/<slug>')
@admin_requerido
def admin_debug_sitio(slug):
    """Ruta de diagnóstico — muestra qué template y estilo se resuelve para un sitio."""
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        return jsonify(error='Sitio no encontrado'), 404
    _estilos_p = get_estilos(sitio['plantilla_id'])
    _defaults_p = json.loads((_estilos_p or {}).get('defaults_json', '{}') or '{}')
    _layout_p   = json.loads((_estilos_p or {}).get('layout_json',   '{}') or '{}')
    _config_p   = dict(get_config_sitio(sitio['id']))
    template_resuelto = _resolver_template_sitio(sitio, 'inicio')
    template_existe   = _template_existe(template_resuelto)
    return jsonify(
        slug=slug,
        plantilla_clave=sitio['plantilla_clave'],
        plantilla_id=sitio['plantilla_id'],
        formato=sitio['formato'] if 'formato' in sitio.keys() else '(no formato col)',
        estilo_en_defaults=_defaults_p.get('estilo_detectado', '—'),
        estilo_en_layout=_layout_p.get('estilo_detectado', '—'),
        estilo_en_config=_config_p.get('estilo_detectado', '—'),
        template_resuelto=template_resuelto,
        template_existe_en_disco=template_existe,
        defaults_keys=list(_defaults_p.keys()),
    )


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


@app.route('/admin/plantillas/<int:plantilla_id>/eliminar', methods=['POST'])
@admin_requerido
def admin_plantilla_eliminar(plantilla_id):
    p = obtener_plantilla_por_id(plantilla_id)
    if not p:
        flash('Plantilla no encontrada.', 'error')
        return redirect(url_for('admin_plantillas'))
    ok, motivo = eliminar_plantilla(plantilla_id)
    if ok:
        flash(f'Plantilla "{p["nombre"]}" eliminada correctamente.', 'success')
    else:
        flash(f'No se pudo eliminar "{p["nombre"]}": {motivo}', 'error')
    return redirect(url_for('admin_plantillas'))


# ══════════════════════════════════════════════════════════════════════════════
# Admin — Gestión de Planes
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/planes')
@admin_requerido
def admin_planes():
    planes  = listar_todos_planes()
    conteos = contar_clientes_por_plan()
    return render_template('admin/admin_planes.html',
                           planes=planes, conteos=conteos,
                           nombre=session.get('nombre'))


@app.route('/admin/planes/nuevo', methods=['POST'])
@admin_requerido
def admin_plan_nuevo():
    clave       = request.form.get('clave', '').strip().lower()
    nombre      = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    precio_raw  = request.form.get('precio', '0').strip()
    tipo_acceso = request.form.get('tipo_acceso', 'landing').strip()
    max_sitios  = request.form.get('max_sitios', '1').strip()

    if not clave or not nombre:
        flash('La clave y el nombre son obligatorios.', 'error')
        return redirect(url_for('admin_planes'))

    try:
        precio     = float(precio_raw)
        max_sitios = int(max_sitios)
    except ValueError:
        flash('Precio y max_sitios deben ser números.', 'error')
        return redirect(url_for('admin_planes'))

    if tipo_acceso not in ('landing', 'web5', 'ambos'):
        tipo_acceso = 'landing'

    try:
        crear_plan(clave, nombre, descripcion, precio, tipo_acceso, max_sitios)
        flash(f'Plan "{nombre}" creado correctamente.', 'success')
    except Exception:
        flash(f'La clave "{clave}" ya existe.', 'error')

    return redirect(url_for('admin_planes'))


@app.route('/admin/planes/<int:plan_id>/toggle', methods=['POST'])
@admin_requerido
def admin_plan_toggle(plan_id):
    plan = obtener_plan(plan_id)
    if not plan:
        flash('Plan no encontrado.', 'error')
    else:
        toggle_plan(plan_id)
        estado = 'desactivado' if plan['activo'] else 'activado'
        flash(f'Plan "{plan["nombre"]}" {estado}.', 'success')
    return redirect(url_for('admin_planes'))


# ── Admin — Activar usuarios pendientes ───────────────────────────────────────

@app.route('/admin/usuarios-pendientes')
@admin_requerido
def admin_usuarios_pendientes():
    pendientes = listar_usuarios_pendientes()
    return render_template('admin/admin_usuarios_pendientes.html',
                           pendientes=pendientes,
                           nombre=session.get('nombre'))


@app.route('/admin/usuarios/<int:uid>/activar', methods=['POST'])
@admin_requerido
def admin_activar_usuario(uid):
    activar_usuario(uid)
    flash('Usuario activado correctamente.', 'success')
    return redirect(url_for('admin_usuarios_pendientes'))


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


# ── Registro público ──────────────────────────────────────────────────────────

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'uid' in session:
        return redirect(url_for('mi_panel'))

    planes = listar_planes()

    if request.method == 'POST':
        nombre    = request.form.get('nombre', '').strip()
        email     = request.form.get('email', '').strip().lower()
        password  = request.form.get('password', '').strip()
        confirm   = request.form.get('confirm', '').strip()
        plan_clave = request.form.get('plan_clave', 'basico').strip()

        error = None
        if not nombre or not email or not password:
            error = 'Todos los campos son obligatorios.'
        elif '@' not in email or '.' not in email:
            error = 'Ingresa un email válido.'
        elif len(password) < 8:
            error = 'La contraseña debe tener al menos 8 caracteres.'
        elif password != confirm:
            error = 'Las contraseñas no coinciden.'
        elif obtener_usuario_por_email_cualquier_estado(email):
            error = 'Ya existe una cuenta con ese email.'

        if error:
            flash(error, 'error')
        else:
            try:
                plan_obj = obtener_plan_por_clave(plan_clave)
                plan_id  = plan_obj['id'] if plan_obj else None
                uid = registrar_cliente_publico(
                    email, generate_password_hash(password), nombre,
                    plan_id or 0
                )
                return redirect(url_for('registro_gracias'))
            except ValueError:
                flash('Ya existe una cuenta con ese email.', 'error')
            except Exception as e:
                log.error('[registro] error: %s', e)
                flash('Error al crear la cuenta. Intenta de nuevo.', 'error')

    return render_template('registro.html', planes=planes)


@app.route('/registro/gracias')
def registro_gracias():
    return render_template('registro_gracias.html')


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

        usuario = obtener_usuario_por_email_cualquier_estado(email)
        if usuario and check_password_hash(usuario['password'], password):
            if not usuario['activo']:
                flash('Tu cuenta está pendiente de activación por el administrador.', 'warning')
                return render_template('entrar.html')
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


# ── Olvidé mi contraseña ─────────────────────────────────────────────────────

@app.route('/olvide-contrasena', methods=['GET', 'POST'])
def olvide_contrasena():
    if 'uid' in session:
        return redirect(url_for('mi_panel'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = obtener_usuario_por_email(email)
        # Siempre mostrar el mismo mensaje para no revelar si el email existe
        flash('Si ese email está registrado, recibirás un enlace en unos minutos.', 'info')
        if usuario:
            token = crear_reset_token(usuario['id'])
            reset_url = url_for('reset_password', token=token, _external=True)
            _enviar_email_reset(email, usuario['nombre'] or email.split('@')[0], reset_url)
        return redirect(url_for('olvide_contrasena'))
    return render_template('olvide_contrasena.html')


@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    usuario = obtener_usuario_por_reset_token(token)
    if not usuario:
        flash('El enlace no es válido o ya expiró. Solicita uno nuevo.', 'error')
        return redirect(url_for('olvide_contrasena'))
    if request.method == 'POST':
        nueva = request.form.get('password', '').strip()
        confirmar = request.form.get('confirm', '').strip()
        if len(nueva) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
        elif nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'error')
        else:
            actualizar_password_usuario(usuario['id'], generate_password_hash(nueva))
            invalidar_reset_token(token)
            flash('Contraseña actualizada. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('entrar'))
    return render_template('reset_password.html', token=token)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@app.route('/auth/google')
def auth_google():
    if not GOOGLE_CLIENT_ID:
        flash('Login con Google no está configurado aún.', 'error')
        return redirect(url_for('entrar'))
    import urllib.parse
    callback = url_for('auth_google_callback', _external=True)
    params = urllib.parse.urlencode({
        'client_id':     GOOGLE_CLIENT_ID,
        'redirect_uri':  callback,
        'response_type': 'code',
        'scope':         'openid email profile',
        'access_type':   'online',
    })
    return redirect(f'{GOOGLE_AUTH_URL}?{params}')


@app.route('/auth/google/callback')
def auth_google_callback():
    import urllib.parse, urllib.request
    code = request.args.get('code')
    if not code:
        flash('No se pudo autenticar con Google.', 'error')
        return redirect(url_for('entrar'))
    try:
        callback = url_for('auth_google_callback', _external=True)
        # Intercambiar code por token
        data = urllib.parse.urlencode({
            'code':          code,
            'client_id':     GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri':  callback,
            'grant_type':    'authorization_code',
        }).encode()
        req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data,
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_data = _json.loads(resp.read())
        access_token = token_data.get('access_token')
        if not access_token:
            raise ValueError('Sin access_token')
        # Obtener info del usuario
        req2 = urllib.request.Request(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'}
        )
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            info = _json.loads(resp2.read())
        google_id = info.get('sub')
        email     = info.get('email', '').lower().strip()
        nombre    = info.get('name', email.split('@')[0])
        if not google_id or not email:
            raise ValueError('Datos incompletos de Google')
        usuario = crear_o_vincular_google(email, nombre, google_id)
        session['uid']      = usuario['id']
        session['u_email']  = usuario['email']
        session['u_nombre'] = usuario.get('nombre') or nombre
        return redirect(url_for('mi_panel'))
    except Exception as e:
        logging.warning(f'[google-oauth] Error: {e}')
        flash('Error al autenticar con Google. Intenta de nuevo.', 'error')
        return redirect(url_for('entrar'))


# ── Panel del usuario ─────────────────────────────────────────────────────────

@app.route('/mi-panel')
@usuario_requerido
def mi_panel():
    sitios = obtener_sitios_usuario(session['uid'])
    # Conteo de mensajes no leídos por sitio
    mensajes_nuevos = {}
    for s in sitios:
        nuevos = listar_mensajes_sitio(s['id'], solo_no_leidos=True)
        mensajes_nuevos[s['id']] = len(nuevos)
    return render_template('mi_panel.html',
        nombre=session['u_nombre'],
        email=session['u_email'],
        sitios=sitios,
        mensajes_nuevos=mensajes_nuevos
    )


# ── Crear sitio ───────────────────────────────────────────────────────────────

@app.route('/crear-sitio', methods=['GET', 'POST'])
@usuario_requerido
def crear_sitio():
    # Mostrar todas las plantillas activas en el selector del portal.
    # El filtro por plan se está ocultando plantillas válidas para el usuario.
    plantillas = listar_plantillas_activas()

    if request.method == 'POST':
        plantilla_id  = request.form.get('plantilla_id', '').strip()
        nombre_sitio  = request.form.get('nombre_sitio', '').strip()
        slug          = request.form.get('slug', '').strip().lower()
        formato       = request.form.get('formato', '').strip()
        # Auto-detectar formato desde el tipo de la plantilla
        if plantilla_id and plantilla_id.isdigit():
            _p_tmp = obtener_plantilla_por_id(int(plantilla_id))
            if _p_tmp and not formato:
                formato = 'landing' if _p_tmp['tipo'] == 'landing' else 'web5'
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

                # Leer estilos scrapeados/wizard de plantilla_estilos
                from db import get_estilos as _get_estilos
                _pe = _get_estilos(int(plantilla_id))

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

                # Si la plantilla fue creada con wizard/scraper, sus estilos tienen prioridad
                # sobre los defaults genéricos (pero no sobre _temas hardcodeados)
                if _pe and _clave not in _temas:
                    _defaults_tema = {
                        'color_primario':  _pe.get('color_primary',  '#0bb180'),
                        'color_acento':    _pe.get('color_accent',   '#38b2ac'),
                        'color_footer_bg': _pe.get('color_secondary','#0d1b2a'),
                        'color_navbar_bg': _pe.get('color_primary',  '#0bb180'),
                        'fuente_titulos':  _pe.get('font_heading',   'Inter'),
                        'fuente_cuerpo':   _pe.get('font_body',      'Inter'),
                    }

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

                # Para plantillas creadas por scraper/wizard, los defaults JSON
                # dejan su huella inicial en el sitio recién creado.
                if _pe and _clave not in _temas:
                    _defaults_scraper = _leer_json_dict(_pe.get('defaults_json'))
                    if _defaults_scraper:
                        _config_base.update(_defaults_scraper)

                set_config_sitio_bulk(sitio_id, _config_base)

                # ── Blueprint scraper: configuración inteligente ──────────────────────────
                _estilos_p   = get_estilos(int(plantilla_id)) if plantilla_id else {}
                _defaults_raw = (_estilos_p or {}).get('defaults_json', '{}')
                try:
                    _defaults_bp = json.loads(_defaults_raw) if _defaults_raw else {}
                except Exception:
                    _defaults_bp = {}

                _blueprint  = _defaults_bp.get('_blueprint')
                _tipo_web   = _defaults_bp.get('_tipo_web', formato)

                if _blueprint and isinstance(_blueprint, dict):
                    from blueprint_generator import blueprint_to_config, blueprint_to_secciones

                    # ── Normalizar formato del scraper al formato del generator ──
                    # El scraper envía {secciones:[str,...], layout:{...}, hero_tipo:'...'}
                    # El generator espera {sections:[{id,layout,...}], detected_sections:[...]}
                    if 'secciones' in _blueprint and 'sections' not in _blueprint:
                        _secs_str  = _blueprint.get('secciones', [])
                        _bp_layout = _blueprint.get('layout', {})
                        _blueprint = {
                            'sections': [
                                {
                                    'id':         s,
                                    'layout':     _bp_layout.get(s, ''),
                                    'card_count': 4 if s == 'services'  else 3,
                                    'item_count': 6 if s == 'why_us'   else 4,
                                    'has_stats':  'about'  in _secs_str,
                                    'has_image':  True,
                                    'has_social': 'footer' in _secs_str,
                                }
                                for s in _secs_str
                            ],
                            'detected_sections': _secs_str,
                            'estilo': _defaults_bp.get('_estilo', 'clean'),
                        }

                    _comp = {k: _defaults_bp.get(f'comp_{k}', False)
                             for k in ['whatsapp','newsletter','social','topbar','citas']}
                    _comp['hero_type'] = _defaults_bp.get('hero_tipo', 'static')

                    _cfg = blueprint_to_config(
                        _blueprint, _estilos_p, nombre_sitio, slug,
                        tipo=_tipo_web, componentes=_comp
                    )
                    _secc = blueprint_to_secciones(_blueprint, tipo=_tipo_web)

                    set_config_sitio_bulk(sitio_id, _cfg)
                    for _sn, _si in _secc.items():
                        if _si:
                            set_secciones_contenido(sitio_id, _sn, _si)

                    flash(f'Sitio "{nombre_sitio}" creado con estructura personalizada.', 'success')
                    return redirect(url_for('mi_panel'))
                # ─────────────────────────────────────────────────────────────────────────

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
        form_data = {}
        for key, val in request.form.items():
            if key.startswith('cfg__'):
                form_data[key[5:]] = val.strip()

        # ── Procesar visibilidad de secciones (checkboxes desmarcados no envían) ──
        for _sec in ['nosotros','servicios','proyectos','equipo','testimonios','citas','contacto']:
            key = f'seccion_{_sec}_visible'
            if key not in form_data:
                form_data[key] = '0'

        # ── Procesar menú personalizado ────────────────────────────────────────
        menu_items = []
        menu_idx = 0
        while True:
            label = request.form.get(f'rep__menu__{menu_idx}__label', None)
            if label is None:
                break
            href    = request.form.get(f'rep__menu__{menu_idx}__href', '#')
            externo = request.form.get(f'rep__menu__{menu_idx}__externo', '') == 'true'
            hijos_raw = request.form.get(f'rep__menu__{menu_idx}__hijos_raw', '')
            hijos = []
            for line in hijos_raw.strip().splitlines():
                if '|' in line:
                    parts = line.split('|', 1)
                    hijos.append({'label': parts[0].strip(), 'href': parts[1].strip()})
            if label.strip():
                menu_items.append({'label': label.strip(), 'href': href.strip(), 'externo': externo, 'hijos': hijos})
            menu_idx += 1
        # Siempre guardar menu_items: '' vacío limpia el valor anterior
        # y activa el fallback de labels individuales en el template
        form_data['menu_items'] = json.dumps(menu_items, ensure_ascii=False) if menu_items else ''

        # ── Procesar hero slides ───────────────────────────────────────────────
        hero_slides = []
        slide_idx = 0
        while True:
            # Usa 'imagen' como centinela — si no está el campo, no hay más slides
            imagen = request.form.get(f'rep__hero-slides__{slide_idx}__imagen', None)
            if imagen is None:
                break
            hero_slides.append({
                'titulo':      request.form.get(f'rep__hero-slides__{slide_idx}__titulo', ''),
                'subtitulo':   request.form.get(f'rep__hero-slides__{slide_idx}__subtitulo', ''),
                'imagen':      imagen.strip(),
                'cta1_texto':  request.form.get(f'rep__hero-slides__{slide_idx}__cta1_texto', ''),
                'cta1_href':   request.form.get(f'rep__hero-slides__{slide_idx}__cta1_href', ''),
                'cta2_texto':  request.form.get(f'rep__hero-slides__{slide_idx}__cta2_texto', ''),
                'cta2_href':   request.form.get(f'rep__hero-slides__{slide_idx}__cta2_href', ''),
            })
            slide_idx += 1
        if hero_slides:
            form_data['hero_slides'] = json.dumps(hero_slides, ensure_ascii=False)

        if form_data:
            set_config_sitio_bulk(sitio_id, form_data)

        # ── Repeaters (rep__seccion__idx__campo) ──────────────────────────────
        secciones_nuevas = {}
        for key, val in request.form.items():
            if key.startswith('rep__'):
                parts = key.split('__')
                if len(parts) == 4:
                    _, seccion, idx_str, campo = parts
                    # Skip the special repeaters handled above
                    if seccion in ('menu', 'hero-slides'):
                        continue
                    try:
                        idx = int(idx_str)
                    except ValueError:
                        continue
                    secciones_nuevas.setdefault(seccion, {}).setdefault(idx, {})[campo] = val.strip()

        for seccion, items_dict in secciones_nuevas.items():
            items = [items_dict[i] for i in sorted(items_dict.keys())]
            set_secciones_contenido(sitio_id, seccion, items)

        flash('Cambios guardados. Tu sitio está actualizado.', 'success')
        log.info('[editar_sitio] guardado OK sitio_id=%s keys=%s', sitio_id, list(form_data.keys()))
        return redirect(url_for('editar_sitio', sitio_id=sitio_id))

    config   = get_config_sitio(sitio_id)
    secciones = {
        'servicios': get_secciones_contenido(sitio_id, 'servicios'),
        'proyectos': get_secciones_contenido(sitio_id, 'proyectos'),
        'equipo':    get_secciones_contenido(sitio_id, 'equipo'),
        'galeria':   get_secciones_contenido(sitio_id, 'galeria'),
    }
    # Secciones habilitadas según el schema de la plantilla
    plantilla = obtener_plantilla_por_id(sitio['plantilla_id'])
    try:
        schema = json.loads(plantilla['campos_schema'] or '{}') if plantilla else {}
    except Exception:
        schema = {}
    _todas = ['apariencia', 'marca', 'hero', 'nosotros', 'servicios', 'proyectos', 'equipo', 'galeria', 'contacto']
    secciones_editor = schema.get('secciones', _todas)

    return render_template('editor_sitio.html',
        sitio=sitio,
        config=config,
        secciones=secciones,
        nombre=session['u_nombre'],
        secciones_editor=secciones_editor,
    )


@app.route('/debug-sitio/<int:sitio_id>')
@usuario_requerido
def debug_sitio(sitio_id):
    """Diagnóstico: muestra config y secciones guardadas en la BD."""
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    config = get_config_sitio(sitio_id)
    secciones = {
        'menu_items': config.get('menu_items', 'NO GUARDADO'),
        'hero_slides': config.get('hero_slides', 'NO GUARDADO'),
        'galeria_items': get_secciones_contenido(sitio_id, 'galeria'),
        'todos_los_config': config,
    }
    return jsonify(secciones)


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


def _template_existe(ruta_template: str) -> bool:
    """Comprueba si existe un template en el árbol de templates."""
    return os.path.exists(os.path.join(app.root_path, 'templates', ruta_template))


def _resolver_template_sitio(sitio, pagina='inicio'):
    """Resuelve qué template debe renderizar un sitio según su plantilla y la página."""
    clave = sitio['plantilla_clave']
    formato = sitio['formato'] if 'formato' in sitio.keys() else 'web5'

    # Mapa estilo → directorio de templates web5 especializados
    _ESTILO_WEB5_DIR = {
        'apple-minimal': 'tech',
        # 'saas':       'saas',      # futuro
        # 'ecommerce':  'ecommerce', # futuro
    }
    # Para landing: template único one-page
    _ESTILO_LANDING_MAP = {
        'apple-minimal': 'sites/tech/index.html',
    }

    def _get_estilo_plantilla():
        if 'plantilla_id' not in sitio.keys():
            return 'clean'
        _ep = get_estilos(sitio['plantilla_id'])
        _d  = json.loads((_ep or {}).get('defaults_json', '{}') or '{}')
        _l  = json.loads((_ep or {}).get('layout_json',   '{}') or '{}')
        return (_d.get('estilo_detectado')
                or _l.get('estilo_detectado')
                or get_config_sitio(sitio['id']).get('estilo_detectado')
                or 'clean')

    # ── LANDING — one-page ──
    if formato == 'landing':
        if pagina == 'inicio':
            ruta = f'sites/{clave}/index.html'
            if _template_existe(ruta):
                return ruta
            _estilo_p = _get_estilo_plantilla()
            _t = _ESTILO_LANDING_MAP.get(_estilo_p)
            if _t and _template_existe(_t):
                return _t
            return 'sites/_universal/index.html'
        ruta = f'sites/{clave}/{pagina}.html'
        if _template_existe(ruta):
            return ruta
        return 'sites/_universal/index.html'

    # ── WEB5 — 5 páginas ──
    # 1. Template especifico de la plantilla
    ruta = f'sites/{clave}/{pagina}.html'
    if _template_existe(ruta):
        return ruta
    if pagina == 'inicio':
        ruta_idx = f'sites/{clave}/index.html'
        if _template_existe(ruta_idx):
            return ruta_idx
    # 2. Directorio por estilo detectado
    _estilo_p = _get_estilo_plantilla()
    _dir = _ESTILO_WEB5_DIR.get(_estilo_p)
    if _dir:
        _pf = 'inicio.html' if pagina == 'inicio' else f'{pagina}.html'
        _t = f'sites/{_dir}/{_pf}'
        if _template_existe(_t):
            return _t
    # 3. Fallback empresa
    _pf = 'inicio.html' if pagina == 'inicio' else f'{pagina}.html'
    return f'sites/empresa/{_pf}'

def _leer_json_dict(valor):
    """Normaliza valores JSON guardados en DB a un dict seguro."""
    if isinstance(valor, dict):
        return valor
    if not valor:
        return {}
    if isinstance(valor, str):
        try:
            parsed = json.loads(valor)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _defaults_desde_payload(payload: dict, layout=None):
    """Convierte el payload del scraper en defaults JSON consumibles por el render.

    Versión mejorada: incluye tokens mobile-first, secciones detectadas,
    colores derivados, componentes inferidos y metadata de layout.
    """
    # ── Colores base ──────────────────────────────────────────────────────────
    color_primario  = payload.get('color_primario') or '#185FA5'
    color_acento    = payload.get('color_acento')   or '#0088CC'
    color_footer    = payload.get('color_footer')   or '#0A0F1E'
    color_navbar    = payload.get('color_navbar_bg') or color_primario
    color_texto     = payload.get('color_texto')     or '#1f2937'
    color_texto_inv = payload.get('color_texto_inverso') or '#ffffff'

    # ── Detectar si el tema es oscuro para ajustar contraste ─────────────────
    def _es_oscuro(hex_color: str) -> bool:
        try:
            h = hex_color.lstrip('#')
            if len(h) == 3:
                h = ''.join(c * 2 for c in h)
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminancia < 0.5
        except Exception:
            return False

    tema_oscuro = _es_oscuro(color_primario)

    defaults = {}

    # ── Campos básicos (igual que antes, sin romper compatibilidad) ───────────
    for clave, valor in (
        ('color_primario',   color_primario),
        ('color_acento',     color_acento),
        ('color_footer_bg',  color_footer),
        ('color_navbar_bg',  color_navbar),
        ('color_texto',      color_texto),
        ('color_texto_inverso', color_texto_inv),
        ('fuente_titulos',   payload.get('fuente_titulos')),
        ('fuente_cuerpo',    payload.get('fuente_cuerpo')),
        ('hero_titulo',      payload.get('hero_titulo')),
        ('hero_subtitulo',   payload.get('hero_subtitulo')),
        ('hero_cta_texto',   payload.get('hero_cta_texto')),
        ('hero_cta_href',    payload.get('hero_cta_href')),
        ('hero_eyebrow',     payload.get('hero_eyebrow')),
        ('menu_servicios',   payload.get('menu_servicios')),
        ('menu_proyectos',   payload.get('menu_proyectos')),
        ('menu_equipo',      payload.get('menu_equipo')),
        ('menu_contacto',    payload.get('menu_contacto')),
        ('nombre_empresa',   payload.get('nombre_empresa') or payload.get('nombre')),
        ('tagline',          payload.get('tagline')),
        ('descripcion',      payload.get('descripcion') or payload.get('nosotros_descripcion')),
        ('logo_url',         payload.get('logo_url')),
        ('telefono',         payload.get('telefono')),
        ('email',            payload.get('email')),
        ('direccion',        payload.get('direccion')),
        ('ciudad',           payload.get('ciudad')),
        ('horario',          payload.get('horario')),
    ):
        if valor:
            defaults[clave] = valor

    # ── Tokens mobile-first ───────────────────────────────────────────────────
    # Breakpoints y comportamientos responsivos por sección
    mobile_bp = payload.get('mobile_breakpoints') or {}
    defaults['mobile_nav']      = mobile_bp.get('nav', 'hamburger')       # hamburger | bottom_bar | drawer
    defaults['mobile_hero']     = mobile_bp.get('hero', 'stack')           # stack | fullscreen | centered | full_bleed
    defaults['mobile_services'] = mobile_bp.get('services', 'accordion')   # accordion | swipe_cards | grid_2col
    defaults['mobile_team']     = mobile_bp.get('team', 'swipe_cards')     # swipe_cards | grid_2col | list
    defaults['mobile_gallery']  = mobile_bp.get('gallery', 'swipe_cards')  # swipe_cards | masonry_2col | grid

    # ── Spacing y tipografía responsiva ──────────────────────────────────────
    defaults['font_size_hero_mobile']   = payload.get('font_size_hero_mobile', '2.2rem')
    defaults['font_size_hero_desktop']  = payload.get('font_size_hero_desktop', '4rem')
    defaults['font_size_h2_mobile']     = payload.get('font_size_h2_mobile', '1.6rem')
    defaults['font_size_h2_desktop']    = payload.get('font_size_h2_desktop', '2.4rem')
    defaults['section_padding_mobile']  = payload.get('section_padding_mobile', '3rem 1.25rem')
    defaults['section_padding_desktop'] = payload.get('section_padding_desktop', '6rem 2rem')

    # ── Secciones detectadas / habilitadas ────────────────────────────────────
    secciones_activas = payload.get('secciones_activas') or payload.get('secciones') or []
    if not secciones_activas and layout:
        # Inferir secciones activas desde el layout
        secciones_activas = ['hero', 'servicios', 'contacto']
        if layout.get('projects'):
            secciones_activas.append('proyectos')
        if layout.get('team'):
            secciones_activas.append('equipo')

    defaults['secciones_activas'] = json.dumps(secciones_activas, ensure_ascii=False)

    # Visibilidad individual de cada sección
    for sec in ('hero', 'servicios', 'proyectos', 'equipo', 'testimonios',
                'galeria', 'nosotros', 'precios', 'faq', 'mapa', 'ctas_flotantes'):
        defaults[f'sec_{sec}'] = '1' if (
            not secciones_activas or sec in secciones_activas
        ) else '0'
    # Hero siempre visible
    defaults['sec_hero'] = '1'

    # ── Componentes opcionales ────────────────────────────────────────────────
    comp = payload.get('componentes') or {}
    defaults['comp_whatsapp']   = '1' if comp.get('whatsapp')  or comp.get('whatsApp')  else '0'
    defaults['comp_newsletter'] = '1' if comp.get('newsletter')                          else '0'
    defaults['comp_redes']      = '1' if comp.get('redes')     or comp.get('social')    else '0'
    defaults['comp_topbar']     = '1' if comp.get('topbar')                              else '0'
    defaults['comp_citas']      = '1' if comp.get('citas')                               else '0'
    defaults['comp_chat']       = '1' if comp.get('chat')                                else '0'
    defaults['comp_cookies']    = '1' if comp.get('cookies',  True)                      else '0'
    defaults['comp_back_top']   = '1' if comp.get('back_top', True)                      else '0'

    # ── Hero avanzado ─────────────────────────────────────────────────────────
    defaults['hero_tipo']          = payload.get('hero_tipo') or (layout.get('hero') if layout else 'static')
    defaults['hero_overlay_opac']  = payload.get('hero_overlay_opacity', '0.55')
    defaults['hero_alineacion']    = payload.get('hero_alineacion', 'left')   # left | center | right
    defaults['hero_imagen_url']    = payload.get('hero_imagen_url', '')
    defaults['hero_video_url']     = payload.get('hero_video_url', '')
    defaults['hero_badge_texto']   = payload.get('hero_badge_texto', '')
    defaults['hero_cta2_texto']    = payload.get('hero_cta2_texto', '')
    defaults['hero_cta2_href']     = payload.get('hero_cta2_href', '')

    # ── Navbar ────────────────────────────────────────────────────────────────
    defaults['navbar_sticky']      = '1' if payload.get('navbar_sticky', True) else '0'
    defaults['navbar_transparente']= '1' if payload.get('navbar_transparente', defaults['hero_tipo'] == 'fullscreen') else '0'
    defaults['navbar_logo_pos']    = payload.get('navbar_logo_pos', 'left')  # left | center

    # ── Features de landing page (persuasión / conversión) ───────────────────
    features = payload.get('features') or []
    feature_map = {
        'booking':            'comp_citas',
        'team_profiles':      'sec_equipo',
        'service_list':       'sec_servicios',
        'testimonials':       'sec_testimonios',
        'portfolio_masonry':  'sec_proyectos',
        'gallery':            'sec_galeria',
        'pricing_table':      'sec_precios',
        'faq':                'sec_faq',
        'map':                'sec_mapa',
        'newsletter':         'comp_newsletter',
    }
    for feat in features:
        mapped = feature_map.get(feat)
        if mapped:
            defaults[mapped] = '1'

    # ── SEO básico ────────────────────────────────────────────────────────────
    defaults['meta_titulo']       = payload.get('meta_titulo') or defaults.get('hero_titulo', '')
    defaults['meta_descripcion']  = payload.get('meta_descripcion') or defaults.get('descripcion', '')
    defaults['og_imagen']         = payload.get('og_imagen') or defaults.get('hero_imagen_url', '')

    # ── Scraper mejorado — señales de estilo y nav ───────────────────────────
    defaults['estilo_detectado']   = payload.get('estilo',         'clean')
    defaults['nav_style']          = payload.get('nav_style',      'standard')
    defaults['content_layout']     = payload.get('content_layout', 'standard')
    defaults['font_scale']         = payload.get('font_scale',     'medium')
    defaults['tagline_style']      = payload.get('tagline_style',  'descriptive')
    defaults['has_promo_grid']     = '1' if payload.get('has_promo_grid') else '0'

    # ── Tema ──────────────────────────────────────────────────────────────────
    defaults['tema_oscuro']        = '1' if tema_oscuro else '0'
    defaults['hero_texto_color']   = '#ffffff' if (tema_oscuro or defaults['hero_tipo'] in ('dark', 'fullscreen', 'gradient')) else color_texto

    # ── Layout JSON ───────────────────────────────────────────────────────────
    if layout:
        defaults['layout'] = layout

    return defaults


def _blueprint_to_layout(blueprint=None, fallback=None):
    """Convierte el blueprint detectado a layout JSON para el render.

    Versión mejorada: detecta variantes de sección más granulares,
    soporta tokens mobile-first y toma decisiones contextuales de layout.
    """
    layout = fallback if isinstance(fallback, dict) else {
        'hero': 'split',
        'services': 'grid',
        'projects': 'masonry',
        'team': 'cards',
        # Nuevos slots
        'testimonials': 'carousel',
        'pricing': 'cards',
        'faq': 'accordion',
        'gallery': 'masonry',
        'cta': 'centered',
        'features': 'grid_3col',
        'footer': 'columns',
    }

    if isinstance(blueprint, dict):
        _layout_extra = blueprint.get('layout')
        if isinstance(_layout_extra, dict):
            layout = {**layout, **_layout_extra}

    def _normalizar_item(item):
        if isinstance(item, str):
            return item.strip().lower()
        if isinstance(item, dict):
            for clave in ('tipo', 'nombre', 'section', 'slug', 'id'):
                valor = item.get(clave)
                if isinstance(valor, str) and valor.strip():
                    return valor.strip().lower()
        return ''

    secciones = []
    if isinstance(blueprint, dict):
        for clave in ('secciones', 'sections', 'detected_sections', 'detectedSections', 'items'):
            valor = blueprint.get(clave)
            if isinstance(valor, list):
                secciones = [_normalizar_item(item) for item in valor]
                break
    elif isinstance(blueprint, (list, tuple)):
        secciones = [_normalizar_item(item) for item in blueprint]

    texto = ' '.join([s for s in secciones if s]).lower()

    # ── Hero ──────────────────────────────────────────────────────────────────
    if any(t in texto for t in ('fullscreen', 'full', 'hero_fullscreen', 'slider', 'video_bg')):
        layout['hero'] = 'fullscreen'
    elif any(t in texto for t in ('gradient', 'gradiente', 'hero_gradient')):
        layout['hero'] = 'gradient'
    elif any(t in texto for t in ('dark', 'oscuro', 'hero_dark')):
        layout['hero'] = 'dark'
    elif any(t in texto for t in ('minimal', 'simple', 'clean', 'hero_minimal')):
        layout['hero'] = 'minimal'
    elif any(t in texto for t in ('split', 'dos columnas', 'two column', 'hero_split')):
        layout['hero'] = 'split'
    elif any(t in texto for t in ('centered', 'centrado', 'hero_centered')):
        layout['hero'] = 'centered'

    # ── Servicios ─────────────────────────────────────────────────────────────
    if any(t in texto for t in ('services_menu', 'menu_servicios', 'menu')):
        layout['services'] = 'menu'
    elif any(t in texto for t in ('services_list', 'listado', 'lista')):
        layout['services'] = 'list'
    elif any(t in texto for t in ('services_cards', 'cards', 'tarjetas')):
        layout['services'] = 'cards'
    elif any(t in texto for t in ('services_accordion', 'accordion', 'acordeon')):
        layout['services'] = 'accordion'
    elif any(t in texto for t in ('services_tabs', 'tabs', 'pestanas')):
        layout['services'] = 'tabs'
    elif any(t in texto for t in ('services_grid', 'grid_servicios')):
        layout['services'] = 'grid'

    # ── Proyectos / Portafolio ────────────────────────────────────────────────
    if any(t in texto for t in ('projects_masonry', 'masonry', 'portfolio', 'galeria')):
        layout['projects'] = 'masonry'
    elif any(t in texto for t in ('projects_carousel', 'carousel', 'carrusel')):
        layout['projects'] = 'carousel'
    elif any(t in texto for t in ('projects_grid', 'grid_proyectos')):
        layout['projects'] = 'grid'
    elif any(t in texto for t in ('projects_list', 'lista_proyectos')):
        layout['projects'] = 'list'

    # ── Equipo ────────────────────────────────────────────────────────────────
    if any(t in texto for t in ('team_grid', 'grid_equipo')):
        layout['team'] = 'grid'
    elif any(t in texto for t in ('team_minimal', 'minimal_team')):
        layout['team'] = 'minimal'
    elif any(t in texto for t in ('team_carousel', 'carousel_equipo')):
        layout['team'] = 'carousel'
    elif any(t in texto for t in ('team_cards', 'cards_equipo')):
        layout['team'] = 'cards'

    # ── Testimonios ───────────────────────────────────────────────────────────
    if any(t in texto for t in ('testimonios_grid', 'reviews_grid')):
        layout['testimonials'] = 'grid'
    elif any(t in texto for t in ('testimonios_carousel', 'reviews_carousel')):
        layout['testimonials'] = 'carousel'
    elif any(t in texto for t in ('testimonios_masonry', 'reviews_masonry')):
        layout['testimonials'] = 'masonry'

    # ── Precios ───────────────────────────────────────────────────────────────
    if any(t in texto for t in ('pricing_table', 'tabla_precios')):
        layout['pricing'] = 'table'
    elif any(t in texto for t in ('pricing_toggle', 'precios_toggle')):
        layout['pricing'] = 'toggle'

    # ── Features strip ────────────────────────────────────────────────────────
    if any(t in texto for t in ('features_strip', 'highlights', 'icon_features')):
        layout['features'] = 'strip'
    elif any(t in texto for t in ('features_grid', 'ventajas_grid')):
        layout['features'] = 'grid_3col'

    # ── Footer ────────────────────────────────────────────────────────────────
    if any(t in texto for t in ('footer_minimal', 'footer_simple')):
        layout['footer'] = 'minimal'
    elif any(t in texto for t in ('footer_columns', 'footer_columnas', 'footer_full')):
        layout['footer'] = 'columns'

    # ── CTA flotante ──────────────────────────────────────────────────────────
    if any(t in texto for t in ('cta_sticky', 'cta_flotante', 'sticky_bar')):
        layout['cta'] = 'sticky_bar'
    elif any(t in texto for t in ('cta_centered', 'cta_centrado')):
        layout['cta'] = 'centered'

    # ── Número de columnas mobile para grids ─────────────────────────────────
    layout['mobile_cols_services']  = 1
    layout['mobile_cols_projects']  = 2
    layout['mobile_cols_team']      = 2
    layout['mobile_cols_features']  = 2

    return layout


def _blueprint_to_defaults(payload=None, layout=None, blueprint=None, componentes=None):
    """Genera defaults JSON ricos a partir del blueprint y componentes opcionales.

    Versión mejorada: extrae secciones, comportamientos mobile-first,
    tokens de diseño, features habilitadas y metadata de conversión.
    """
    payload     = payload     if isinstance(payload,     dict) else {}
    componentes = componentes if isinstance(componentes, dict) else {}

    # ── Extraer lista de secciones desde el blueprint ─────────────────────────
    secciones = []
    if isinstance(blueprint, dict):
        for clave in ('secciones', 'sections', 'detected_sections', 'detectedSections', 'items'):
            valor = blueprint.get(clave)
            if isinstance(valor, list):
                secciones = [
                    (item.strip().lower() if isinstance(item, str) else
                     next((item.get(k, '') for k in ('tipo', 'nombre', 'section', 'slug', 'id')
                           if isinstance(item.get(k), str) and item.get(k).strip()), ''))
                    for item in valor
                ]
                secciones = [s for s in secciones if s]
                break
    elif isinstance(blueprint, (list, tuple)):
        secciones = [item.strip().lower() for item in blueprint
                     if isinstance(item, str) and item.strip()]

    # ── Features del blueprint ────────────────────────────────────────────────
    features_bp = []
    if isinstance(blueprint, dict):
        features_bp = blueprint.get('features') or []
    features_all = list(set(
        (payload.get('features') or []) + features_bp
    ))

    # ── Colores con fallback inteligente ──────────────────────────────────────
    color_primario = (payload.get('color_primario') or payload.get('color_primary') or '#185FA5')
    color_acento   = (payload.get('color_acento')   or payload.get('color_accent')  or '#0088CC')
    color_footer   = (payload.get('color_footer')   or payload.get('color_secondary') or '#0A0F1E')
    color_navbar   = (payload.get('color_navbar_bg') or payload.get('color_navbar') or color_primario)
    color_texto    = payload.get('color_texto') or '#1f2937'

    # Detectar luminancia para tema oscuro
    def _lum(hex_c):
        try:
            h = hex_c.lstrip('#')
            if len(h) == 3: h = ''.join(c*2 for c in h)
            r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
            return (0.299*r + 0.587*g + 0.114*b) / 255
        except Exception:
            return 0.5

    tema_oscuro = _lum(color_primario) < 0.45

    # ── Hero tipo ─────────────────────────────────────────────────────────────
    hero_tipo = (
        payload.get('hero_tipo')
        or (blueprint.get('hero_tipo') if isinstance(blueprint, dict) else None)
        or (layout.get('hero') if isinstance(layout, dict) else 'static')
    )

    # ── Mobile breakpoints desde categoría o blueprint ────────────────────────
    mobile_bp = (
        (blueprint.get('mobile_breakpoints') if isinstance(blueprint, dict) else None)
        or payload.get('mobile_breakpoints')
        or {}
    )

    defaults = {
        # Identidad
        'nombre_empresa':       payload.get('nombre_empresa') or payload.get('nombre') or '',
        'tagline':              payload.get('tagline') or '',
        'descripcion':          payload.get('descripcion') or payload.get('nosotros_descripcion') or '',
        'logo_url':             payload.get('logo_url') or '',
        'favicon_url':          payload.get('favicon_url') or '',

        # Colores
        'color_primario':       color_primario,
        'color_acento':         color_acento,
        'color_footer_bg':      color_footer,
        'color_navbar_bg':      color_navbar,
        'color_texto':          color_texto,
        'color_texto_inverso':  payload.get('color_texto_inverso') or '#ffffff',
        'tema_oscuro':          '1' if tema_oscuro else '0',

        # Tipografía
        'fuente_titulos':       payload.get('fuente_titulos') or payload.get('font_heading') or 'system-ui, sans-serif',
        'fuente_cuerpo':        payload.get('fuente_cuerpo')  or payload.get('font_body')    or 'system-ui, sans-serif',
        'font_weight_heading':  payload.get('font_weight_heading') or '700',
        'font_size_base':       payload.get('font_size_base') or '16px',

        # Tipografía responsive
        'font_size_hero_mobile':   payload.get('font_size_hero_mobile',   '2.2rem'),
        'font_size_hero_desktop':  payload.get('font_size_hero_desktop',  '4rem'),
        'font_size_h2_mobile':     payload.get('font_size_h2_mobile',     '1.6rem'),
        'font_size_h2_desktop':    payload.get('font_size_h2_desktop',    '2.4rem'),
        'section_padding_mobile':  payload.get('section_padding_mobile',  '3rem 1.25rem'),
        'section_padding_desktop': payload.get('section_padding_desktop', '6rem 2rem'),

        # Hero
        'hero_titulo':          payload.get('hero_titulo') or payload.get('titulo_principal') or payload.get('nombre') or 'Mi plantilla',
        'hero_subtitulo':       payload.get('hero_subtitulo') or payload.get('subtitulo_principal') or 'Soluciones profesionales para tu negocio.',
        'hero_eyebrow':         payload.get('hero_eyebrow') or payload.get('eyebrow') or '',
        'hero_badge_texto':     payload.get('hero_badge_texto') or '',
        'hero_cta_texto':       payload.get('hero_cta_texto') or 'Contáctanos',
        'hero_cta_href':        payload.get('hero_cta_href') or '#contacto',
        'hero_cta2_texto':      payload.get('hero_cta2_texto') or '',
        'hero_cta2_href':       payload.get('hero_cta2_href') or '',
        'hero_tipo':            hero_tipo,
        'hero_overlay_opac':    payload.get('hero_overlay_opacity') or '0.55',
        'hero_alineacion':      payload.get('hero_alineacion') or 'left',
        'hero_imagen_url':      payload.get('hero_imagen_url') or '',
        'hero_video_url':       payload.get('hero_video_url') or '',
        'hero_texto_color':     '#ffffff' if (tema_oscuro or hero_tipo in ('dark','fullscreen','gradient')) else color_texto,

        # Navbar
        'navbar_sticky':        '1' if payload.get('navbar_sticky',   True)  else '0',
        'navbar_transparente':  '1' if payload.get('navbar_transparente', hero_tipo == 'fullscreen') else '0',
        'navbar_logo_pos':      payload.get('navbar_logo_pos', 'left'),

        # Nav items
        'menu_servicios':       payload.get('menu_servicios') or 'Servicios',
        'menu_proyectos':       payload.get('menu_proyectos') or 'Proyectos',
        'menu_equipo':          payload.get('menu_equipo')    or 'Equipo',
        'menu_contacto':        payload.get('menu_contacto')  or 'Contacto',
        'menu_nosotros':        payload.get('menu_nosotros')  or 'Nosotros',

        # Contacto / footer
        'telefono':             payload.get('telefono') or '',
        'email':                payload.get('email') or '',
        'direccion':            payload.get('direccion') or '',
        'ciudad':               payload.get('ciudad') or '',
        'horario':              payload.get('horario') or '',
        'whatsapp_numero':      payload.get('whatsapp_numero') or payload.get('telefono') or '',

        # Redes sociales
        'facebook_url':         payload.get('facebook_url') or '',
        'instagram_url':        payload.get('instagram_url') or '',
        'twitter_url':          payload.get('twitter_url') or '',
        'linkedin_url':         payload.get('linkedin_url') or '',
        'tiktok_url':           payload.get('tiktok_url') or '',

        # Descripciones de sección
        'servicios_titulo':     payload.get('servicios_titulo') or 'Nuestros Servicios',
        'servicios_descripcion':payload.get('servicios_descripcion') or 'Servicios adaptados a tus necesidades.',
        'proyectos_titulo':     payload.get('proyectos_titulo') or 'Nuestros Proyectos',
        'proyectos_descripcion':payload.get('proyectos_descripcion') or 'Una muestra de nuestros trabajos más destacados.',
        'equipo_titulo':        payload.get('equipo_titulo') or 'Nuestro Equipo',
        'equipo_descripcion':   payload.get('equipo_descripcion') or 'Conoce al equipo que hace posible tu proyecto.',
        'nosotros_titulo':      payload.get('nosotros_titulo') or 'Sobre Nosotros',
        'nosotros_descripcion': payload.get('nosotros_descripcion') or payload.get('descripcion') or '',
        'testimonios_titulo':   payload.get('testimonios_titulo') or 'Lo que dicen de nosotros',
        'precios_titulo':       payload.get('precios_titulo') or 'Nuestros Planes',

        # Mobile-first: comportamientos por sección
        'mobile_nav':           mobile_bp.get('nav',      'hamburger'),
        'mobile_hero':          mobile_bp.get('hero',     'stack'),
        'mobile_services':      mobile_bp.get('services', 'accordion'),
        'mobile_team':          mobile_bp.get('team',     'swipe_cards'),
        'mobile_gallery':       mobile_bp.get('gallery',  'swipe_cards'),
        'mobile_cols_services': str(mobile_bp.get('cols_services', 1)),
        'mobile_cols_projects': str(mobile_bp.get('cols_projects', 2)),
        'mobile_cols_team':     str(mobile_bp.get('cols_team',     2)),

        # SEO
        'meta_titulo':          payload.get('meta_titulo') or payload.get('hero_titulo') or '',
        'meta_descripcion':     payload.get('meta_descripcion') or payload.get('descripcion') or '',
        'og_imagen':            payload.get('og_imagen') or payload.get('hero_imagen_url') or '',

        # Secciones detectadas (raw para debugging)
        '_detected_sections':   json.dumps(secciones, ensure_ascii=False),
    }

    # ── Visibilidad de secciones ──────────────────────────────────────────────
    sec_defaults = {
        'sec_hero':        '1',  # siempre
        'sec_servicios':   '1',
        'sec_proyectos':   '0',
        'sec_equipo':      '0',
        'sec_testimonios': '0',
        'sec_galeria':     '0',
        'sec_nosotros':    '0',
        'sec_precios':     '0',
        'sec_faq':         '0',
        'sec_mapa':        '0',
        'sec_ctas_flotantes': '0',
    }
    # Activar según secciones detectadas
    sec_map = {
        'servicios': 'sec_servicios', 'services': 'sec_servicios',
        'proyectos': 'sec_proyectos', 'projects': 'sec_proyectos',  'portfolio': 'sec_proyectos',
        'equipo':    'sec_equipo',    'team':     'sec_equipo',
        'testimonios': 'sec_testimonios', 'testimonials': 'sec_testimonios', 'reviews': 'sec_testimonios',
        'galeria':   'sec_galeria',   'gallery':  'sec_galeria',
        'nosotros':  'sec_nosotros',  'about':    'sec_nosotros',
        'precios':   'sec_precios',   'pricing':  'sec_precios',   'planes': 'sec_precios',
        'faq':       'sec_faq',       'faqs':     'sec_faq',
        'mapa':      'sec_mapa',      'map':      'sec_mapa',      'ubicacion': 'sec_mapa',
    }
    for sec in secciones:
        key = sec_map.get(sec)
        if key:
            sec_defaults[key] = '1'
    # Activar secciones inferidas por features
    feature_sec_map = {
        'booking':           'comp_citas',
        'team_profiles':     'sec_equipo',
        'service_list':      'sec_servicios',
        'testimonials':      'sec_testimonios',
        'portfolio_masonry': 'sec_proyectos',
        'gallery':           'sec_galeria',
        'pricing_table':     'sec_precios',
        'faq':               'sec_faq',
        'map':               'sec_mapa',
        'newsletter':        'comp_newsletter',
    }
    for feat in features_all:
        mapped = feature_sec_map.get(feat)
        if mapped and mapped in sec_defaults:
            sec_defaults[mapped] = '1'

    defaults.update(sec_defaults)

    # ── Componentes opcionales ────────────────────────────────────────────────
    defaults['comp_whatsapp']   = '1' if (componentes.get('whatsapp') or componentes.get('whatsApp')
                                          or 'whatsapp' in features_all) else '0'
    defaults['comp_newsletter'] = '1' if (componentes.get('newsletter')
                                          or 'newsletter' in features_all) else '0'
    defaults['comp_redes']      = '1' if (componentes.get('redes') or componentes.get('social')) else '0'
    defaults['comp_topbar']     = '1' if componentes.get('topbar')   else '0'
    defaults['comp_citas']      = '1' if (componentes.get('citas')
                                          or 'booking' in features_all) else '0'
    defaults['comp_chat']       = '1' if componentes.get('chat')     else '0'
    defaults['comp_cookies']    = '1' if componentes.get('cookies', True) else '0'
    defaults['comp_back_top']   = '1' if componentes.get('back_top', True) else '0'

    # ── Secciones activas serializada (para templates) ────────────────────────
    secciones_activas = [k.replace('sec_', '') for k, v in sec_defaults.items()
                         if k.startswith('sec_') and v == '1']
    defaults['secciones_activas'] = json.dumps(secciones_activas, ensure_ascii=False)

    if layout:
        defaults['layout'] = layout

    return defaults


def _normalizar_sitio(sitio):
    """Convierte filas SQLite en dict para que el código use una interfaz uniforme."""
    if isinstance(sitio, dict):
        return sitio
    if hasattr(sitio, 'keys') and hasattr(sitio, '__getitem__'):
        return dict(sitio)
    return {}


def _contexto_sitio(sitio):
    """Carga config + secciones comunes para cualquier sitio."""
    sitio_dict = _normalizar_sitio(sitio)
    sid = sitio_dict.get('id')
    plantilla_id = sitio_dict.get('plantilla_id')
    _estilos = get_estilos(plantilla_id) if plantilla_id else {}
    _defaults = _leer_json_dict(_estilos.get('defaults_json'))
    _config = dict(get_config_sitio(sid))
    for _clave, _valor in _defaults.items():
        if _config.get(_clave) in (None, ''):
            _config[_clave] = _valor
    return {
        'config':   _config,
        'defaults': _defaults,
        'layout':   _leer_json_dict(_estilos.get('layout_json')),
        'secciones': {
            'servicios':   get_secciones_contenido(sid, 'servicios'),
            'proyectos':   get_secciones_contenido(sid, 'proyectos'),
            'equipo':      get_secciones_contenido(sid, 'equipo'),
            'galeria':     get_secciones_contenido(sid, 'galeria'),
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
    template = _resolver_template_sitio(sitio, 'inicio')
    return render_template(template, sitio=sitio, pagina_activa='inicio', **ctx)


@app.route('/s/<slug>/<pagina>/')
@app.route('/s/<slug>/<pagina>')
def ver_pagina(slug, pagina):
    from flask import redirect
    sitio = obtener_sitio_por_slug(slug)
    if not sitio:
        abort(404)
    _formato = sitio['formato'] if 'formato' in sitio.keys() else 'web5'
    if _formato != 'web5':
        return redirect(f'/s/{slug}/#{pagina}', 302)
    if pagina not in _PAGINAS_WEB5:
        abort(404)
    ctx = _contexto_sitio(sitio)

    # Enriquecer contexto de página con blueprint si existe
    _cfg_sitio     = get_config_sitio(sitio['id'])
    _blueprint_raw = _cfg_sitio.get('_blueprint') if _cfg_sitio else None

    if _blueprint_raw:
        try:
            import json as _j
            _bp = _j.loads(_blueprint_raw) if isinstance(_blueprint_raw, str) else _blueprint_raw
            from blueprint_generator import get_web5_page_context, blueprint_to_secciones
            from db import get_estilos as _get_estilos
            _estilos = _get_estilos(sitio['plantilla_id']) or {}
            _secc    = blueprint_to_secciones(_bp, tipo='web5')
            _page_ctx = get_web5_page_context(pagina, _bp, ctx.get('cfg', {}), _secc)
            ctx.update(_page_ctx)
        except Exception:
            pass

    template = _resolver_template_sitio(sitio, pagina)
    return render_template(template, sitio=sitio, pagina_activa=pagina, **ctx)


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
    # Notificar al dueño del sitio por email (en hilo para no bloquear la respuesta)
    dueno = obtener_usuario_por_id(sitio['usuario_id'])
    if dueno:
        threading.Thread(
            target=_enviar_email_notificacion,
            args=(dueno['email'], sitio['nombre'], nombre, email_c, telefono, mensaje),
            daemon=True
        ).start()
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


@app.route('/mis-mensajes/<int:sitio_id>')
@usuario_requerido
def mis_mensajes(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    mensajes = listar_mensajes_sitio(sitio_id)
    return render_template('mis_mensajes.html',
        sitio=sitio, mensajes=mensajes, nombre=session['u_nombre'])

@app.route('/mis-mensajes/<int:sitio_id>/marcar-leido', methods=['POST'])
@usuario_requerido
def marcar_leido(sitio_id):
    sitio = obtener_sitio_por_id(sitio_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(403)
    mensaje_id = request.form.get('mensaje_id', type=int)
    if mensaje_id:
        marcar_mensaje_leido(mensaje_id)
    return redirect(url_for('mis_mensajes', sitio_id=sitio_id))


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


# ── CSS Builder API ───────────────────────────────────────────────────────────

@app.route('/admin/sites/<int:site_id>/css-builder')
@usuario_requerido
def css_builder(site_id):
    """Panel visual del CSS Builder."""
    from css_engine import get_tokens
    from css_presets import list_presets

    sitio = obtener_sitio_por_id(site_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        abort(404)

    tokens, variants = get_tokens(site_id)
    presets = list_presets()

    return render_template('css_builder_panel.html',
        site_id=site_id,
        site=sitio,
        sitio=sitio,
        tokens=tokens,
        variants=variants,
        presets=presets,
    )


@app.route('/api/sites/<int:site_id>/css/rebuild', methods=['POST'])
@usuario_requerido
def rebuild_css(site_id):
    """Guarda tokens + variants y regenera el CSS del sitio."""
    import json as _json
    from css_engine import save_tokens, generate_css
    from db import get_config_sitio

    sitio = obtener_sitio_por_id(site_id)
    if not sitio or sitio['usuario_id'] != session['uid']:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    data = request.get_json(silent=True) or {}

    design_tokens    = data.get('design_tokens')
    section_variants = data.get('section_variants')
    mobile_tokens    = data.get('mobile_tokens')

    if design_tokens is None and section_variants is None:
        return jsonify({'ok': False, 'error': 'Faltan design_tokens o section_variants'}), 400

    # Guardar JSONs primero
    if design_tokens is not None and section_variants is not None:
        save_tokens(site_id, design_tokens, section_variants)
    elif design_tokens is not None:
        from db import set_config_sitio as _set
        _set(site_id, 'design_tokens', _json.dumps(design_tokens, ensure_ascii=False))
    elif section_variants is not None:
        from db import set_config_sitio as _set
        _set(site_id, 'section_variants', _json.dumps(section_variants, ensure_ascii=False))

    if mobile_tokens is not None:
        from db import set_config_sitio as _set
        _set(site_id, 'mobile_tokens', _json.dumps(mobile_tokens, ensure_ascii=False))

    # Generar CSS
    css = generate_css(site_id)
    config = get_config_sitio(site_id)
    version = int(config.get('css_version', '1') or '1')

    return jsonify({'ok': True, 'css_length': len(css), 'version': version})


# ══════════════════════════════════════════════════════════════════════════════
# Admin — Wizard para crear plantillas
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/plantillas/wizard')
@admin_requerido
def admin_plantilla_wizard_form():
    return render_template('admin/crear_plantilla_wizard.html',
                           nombre=session.get('nombre'))


@app.route('/admin/plantillas/wizard/crear', methods=['POST'])
@admin_requerido
def admin_plantilla_wizard():
    d = request.get_json(force=True)

    nombre      = d.get('nombre', '').strip()
    clave       = d.get('clave', '').strip().lower()
    tipo        = d.get('tipo', 'landing')
    descripcion = d.get('descripcion', '').strip()
    layout      = d.get('layout', {})
    defaults    = d.get('defaults', {})

    import re as _re
    if not clave or not nombre:
        return jsonify(ok=False, error='Nombre y clave son obligatorios.'), 400
    if not _re.match(r'^[a-z][a-z0-9_-]{1,29}$', clave):
        return jsonify(ok=False, error='Clave no válida.'), 400

    try:
        pid = crear_plantilla(clave, nombre, tipo, descripcion, '', '{}')
    except Exception as e:
        return jsonify(ok=False, error=f'La clave "{clave}" ya existe.'), 409

    # Guardar estilos, layout y defaults
    campos_estilos = {
        'color_primary':  d.get('color_primario', '#185FA5'),
        'color_accent':   d.get('color_acento',   '#0088CC'),
        'color_secondary': d.get('color_footer_bg', '#0A0F1E'),
        'font_heading':   d.get('fuente_titulos', 'system-ui, sans-serif'),
        'font_body':      d.get('fuente_cuerpo',  'system-ui, sans-serif'),
        'layout_json':    json.dumps(layout, ensure_ascii=False),
        'defaults_json':  json.dumps(defaults, ensure_ascii=False),
    }
    upsert_estilos(pid, campos_estilos)

    flash(f'Plantilla "{nombre}" creada con wizard.', 'success')
    return jsonify(ok=True, redirect=url_for('admin_plantillas'))


# ══════════════════════════════════════════════════════════════════════════════
# Admin — Scraper / Creación por Categoría
# ══════════════════════════════════════════════════════════════════════════════

_CATEGORIAS = {
    # ── Salud ──────────────────────────────────────────────────────────────────
    'clinica': {
        'color_primary': '#0077B6', 'color_accent': '#00B4D8',
        'color_secondary': '#03045E', 'font_heading': 'Montserrat', 'font_body': 'Open Sans',
        'layout': {'hero': 'split', 'services': 'list', 'projects': 'grid', 'team': 'cards'},
        'secciones': ['hero', 'servicios', 'equipo', 'testimonios', 'citas', 'contacto'],
        'mobile_breakpoints': {'hero': 'stack', 'nav': 'hamburger', 'services': 'accordion'},
        'componentes': {'citas': True, 'whatsapp': True, 'topbar': True},
        'hero_tipo': 'split',
        'features': ['booking', 'team_profiles', 'service_list', 'testimonials'],
    },
    'restaurante': {
        'color_primary': '#C1440E', 'color_accent': '#F4A261',
        'color_secondary': '#1A0A00', 'font_heading': 'Playfair Display', 'font_body': 'Lato',
        'layout': {'hero': 'fullscreen', 'services': 'menu', 'projects': 'masonry', 'team': 'minimal'},
        'secciones': ['hero', 'menu', 'galeria', 'ubicacion', 'reservas', 'contacto'],
        'mobile_breakpoints': {'hero': 'fullscreen', 'nav': 'bottom_bar', 'menu': 'accordion'},
        'componentes': {'whatsapp': True, 'redes': True},
        'hero_tipo': 'fullscreen',
        'features': ['menu_display', 'gallery', 'map', 'reservations'],
    },
    'abogados': {
        'color_primary': '#1B2A4A', 'color_accent': '#C9A84C',
        'color_secondary': '#0D1B2A', 'font_heading': 'Cormorant Garamond', 'font_body': 'Source Sans Pro',
        'layout': {'hero': 'minimal', 'services': 'list', 'projects': 'grid', 'team': 'cards'},
        'secciones': ['hero', 'areas_practica', 'equipo', 'casos', 'testimonios', 'contacto'],
        'mobile_breakpoints': {'hero': 'centered', 'nav': 'hamburger', 'services': 'accordion'},
        'componentes': {'whatsapp': True, 'topbar': True},
        'hero_tipo': 'minimal',
        'features': ['practice_areas', 'attorney_profiles', 'case_results', 'contact_form'],
    },
    'creativo': {
        'color_primary': '#6D28D9', 'color_accent': '#F59E0B',
        'color_secondary': '#1F1135', 'font_heading': 'Space Grotesk', 'font_body': 'Inter',
        'layout': {'hero': 'gradient', 'services': 'cards', 'projects': 'masonry', 'team': 'grid'},
        'secciones': ['hero', 'portafolio', 'servicios', 'proceso', 'testimonios', 'contacto'],
        'mobile_breakpoints': {'hero': 'full_bleed', 'nav': 'hamburger', 'portfolio': 'swipe_carousel'},
        'componentes': {'redes': True, 'whatsapp': True},
        'hero_tipo': 'gradient',
        'features': ['portfolio_masonry', 'process_steps', 'testimonials', 'contact_form'],
    },
    'educacion': {
        'color_primary': '#F97316', 'color_accent': '#3B82F6',
        'color_secondary': '#1E3A5F', 'font_heading': 'Nunito', 'font_body': 'Open Sans',
        'layout': {'hero': 'split', 'services': 'cards', 'projects': 'grid', 'team': 'grid'},
        'secciones': ['hero', 'cursos', 'docentes', 'metodologia', 'testimonios', 'inscripcion'],
        'mobile_breakpoints': {'hero': 'stack', 'nav': 'hamburger', 'courses': 'swipe_cards'},
        'componentes': {'newsletter': True, 'whatsapp': True, 'topbar': True},
        'hero_tipo': 'split',
        'features': ['course_catalog', 'instructor_profiles', 'enrollment_cta', 'testimonials'],
    },
    'tecnologia': {
        'color_primary': '#06B6D4', 'color_accent': '#8B5CF6',
        'color_secondary': '#030712', 'font_heading': 'Space Grotesk', 'font_body': 'Inter',
        'layout': {'hero': 'dark', 'services': 'grid', 'projects': 'masonry', 'team': 'minimal'},
        'secciones': ['hero', 'soluciones', 'tecnologias', 'proyectos', 'equipo', 'contacto'],
        'mobile_breakpoints': {'hero': 'full_bleed', 'nav': 'hamburger', 'solutions': 'swipe_cards'},
        'componentes': {'redes': True, 'topbar': True},
        'hero_tipo': 'dark',
        'features': ['solutions_grid', 'tech_stack', 'case_studies', 'team_minimal'],
    },
    'inmobiliaria': {
        'color_primary': '#78716C', 'color_accent': '#D97706',
        'color_secondary': '#1C1917', 'font_heading': 'Cormorant Garamond', 'font_body': 'Lato',
        'layout': {'hero': 'fullscreen', 'services': 'list', 'projects': 'masonry', 'team': 'cards'},
        'secciones': ['hero', 'propiedades', 'servicios', 'agentes', 'testimonios', 'contacto'],
        'mobile_breakpoints': {'hero': 'fullscreen', 'nav': 'hamburger', 'properties': 'swipe_cards'},
        'componentes': {'whatsapp': True, 'redes': True},
        'hero_tipo': 'fullscreen',
        'features': ['property_listings', 'agent_profiles', 'map_search', 'contact_form'],
    },
    'belleza': {
        'color_primary': '#DB2777', 'color_accent': '#F59E0B',
        'color_secondary': '#4A0E2A', 'font_heading': 'Playfair Display', 'font_body': 'Lato',
        'layout': {'hero': 'gradient', 'services': 'cards', 'projects': 'grid', 'team': 'minimal'},
        'secciones': ['hero', 'servicios', 'galeria', 'equipo', 'precios', 'reservas'],
        'mobile_breakpoints': {'hero': 'full_bleed', 'nav': 'hamburger', 'services': 'swipe_cards'},
        'componentes': {'citas': True, 'whatsapp': True, 'redes': True, 'topbar': True},
        'hero_tipo': 'gradient',
        'features': ['service_menu', 'gallery', 'booking', 'pricing_table'],
    },
    # ── Nuevas categorías ──────────────────────────────────────────────────────
    'gym_fitness': {
        'color_primary': '#EF4444', 'color_accent': '#F97316',
        'color_secondary': '#0F0F0F', 'font_heading': 'Oswald', 'font_body': 'Roboto',
        'layout': {'hero': 'dark', 'services': 'cards', 'projects': 'grid', 'team': 'cards'},
        'secciones': ['hero', 'clases', 'entrenadores', 'membresias', 'galeria', 'contacto'],
        'mobile_breakpoints': {'hero': 'full_bleed', 'nav': 'bottom_bar', 'classes': 'swipe_cards'},
        'componentes': {'citas': True, 'whatsapp': True, 'topbar': True},
        'hero_tipo': 'dark',
        'features': ['class_schedule', 'trainer_profiles', 'membership_plans', 'gallery'],
    },
    'veterinaria': {
        'color_primary': '#16A34A', 'color_accent': '#FCD34D',
        'color_secondary': '#052E16', 'font_heading': 'Nunito', 'font_body': 'Open Sans',
        'layout': {'hero': 'split', 'services': 'cards', 'projects': 'grid', 'team': 'cards'},
        'secciones': ['hero', 'servicios', 'equipo', 'citas', 'galeria', 'contacto'],
        'mobile_breakpoints': {'hero': 'stack', 'nav': 'hamburger', 'services': 'accordion'},
        'componentes': {'citas': True, 'whatsapp': True},
        'hero_tipo': 'split',
        'features': ['service_list', 'vet_profiles', 'booking', 'gallery'],
    },
    'transporte': {
        'color_primary': '#1D4ED8', 'color_accent': '#FBBF24',
        'color_secondary': '#0F172A', 'font_heading': 'Barlow Condensed', 'font_body': 'Barlow',
        'layout': {'hero': 'fullscreen', 'services': 'grid', 'projects': 'grid', 'team': 'minimal'},
        'secciones': ['hero', 'servicios', 'flota', 'cobertura', 'cotizacion', 'contacto'],
        'mobile_breakpoints': {'hero': 'fullscreen', 'nav': 'hamburger', 'fleet': 'swipe_cards'},
        'componentes': {'whatsapp': True, 'topbar': True},
        'hero_tipo': 'fullscreen',
        'features': ['fleet_display', 'coverage_map', 'quote_form', 'contact_form'],
    },
    'ecommerce': {
        'color_primary': '#7C3AED', 'color_accent': '#10B981',
        'color_secondary': '#1E1B4B', 'font_heading': 'DM Sans', 'font_body': 'DM Sans',
        'layout': {'hero': 'gradient', 'services': 'grid', 'projects': 'masonry', 'team': 'minimal'},
        'secciones': ['hero', 'productos_destacados', 'categorias', 'ofertas', 'resenas', 'footer'],
        'mobile_breakpoints': {'hero': 'stack', 'nav': 'bottom_bar', 'products': 'swipe_cards'},
        'componentes': {'whatsapp': True, 'redes': True, 'newsletter': True},
        'hero_tipo': 'gradient',
        'features': ['product_grid', 'category_nav', 'promo_banner', 'reviews'],
    },
}


@app.route('/admin/scraper')
@admin_requerido
def admin_scraper():
    return render_template('admin/scraper_plantillas.html',
                           nombre=session.get('nombre'))


@app.route('/admin/scraper/categorias')
@admin_requerido
def admin_scraper_categorias():
    """Devuelve el catálogo completo de categorías con metadatos para el frontend."""
    resultado = {}
    for slug, cat in _CATEGORIAS.items():
        resultado[slug] = {
            'color_primary':   cat['color_primary'],
            'color_accent':    cat['color_accent'],
            'color_secondary': cat['color_secondary'],
            'font_heading':    cat['font_heading'],
            'font_body':       cat['font_body'],
            'layout':          cat['layout'],
            'secciones':       cat.get('secciones', []),
            'mobile_breakpoints': cat.get('mobile_breakpoints', {}),
            'componentes':     cat.get('componentes', {}),
            'hero_tipo':       cat.get('hero_tipo', 'split'),
            'features':        cat.get('features', []),
        }
    return jsonify(categorias=resultado)


@app.route('/admin/scraper/crear-desde-url', methods=['POST'])
@admin_requerido
def admin_scraper_crear_url():
    import re as _re
    d = request.get_json(force=True)

    nombre      = d.get('nombre', '').strip()
    clave       = d.get('clave', '').strip().lower()
    tipo        = d.get('tipo', 'landing')
    blueprint   = d.get('blueprint')
    componentes = d.get('componentes', {})

    if not nombre or not clave:
        return jsonify(ok=False, error='Nombre y clave son obligatorios.'), 400

    # Sanear clave: quitar acentos, reemplazar espacios/especiales por guión,
    # asegurar que empieza con letra, límite 30 chars
    import unicodedata as _ud
    clave = _ud.normalize('NFD', clave)
    clave = ''.join(c for c in clave if _ud.category(c) != 'Mn')
    clave = _re.sub(r'[^a-z0-9]+', '-', clave).strip('-')[:30]
    if not clave:
        clave = 'plantilla'
    if not clave[0].isalpha():          # empieza con número → prefijo 'p-'
        clave = 'p-' + clave
    clave = clave[:30]

    if not _re.match(r'^[a-z][a-z0-9_-]{1,29}$', clave):
        return jsonify(ok=False, error=f'Clave generada inválida: "{clave}". Escríbela manualmente.'), 400

    try:
        pid = crear_plantilla(clave, nombre, tipo, 'Creada desde scraper URL', '', '{}')
    except Exception:
        return jsonify(ok=False, error=f'La clave "{clave}" ya existe.'), 409

    # ── Extraer datos reales del blueprint del scraper ───────────────────
    _bp_secciones = []
    _bp_layout_raw = {}
    _hero_tipo    = componentes.get('hero_type', 'static')

    if blueprint:
        _bp_secciones  = (blueprint.get('secciones') or
                          blueprint.get('detected_sections') or [])
        _bp_layout_raw = blueprint.get('layout') or {}

    # Mapear hero_tipo → variante de template (hero_fullscreen.html, etc.)
    _HERO_MAP = {
        'static':     'fullscreen',
        'fullscreen': 'fullscreen',
        'slider':     'fullscreen',   # no hay hero_slider.html — usa fullscreen
        'carousel':   'fullscreen',
        'dark':       'dark',
        'gradient':   'gradient',
        'split':      'split',
        'minimal':    'minimal',
    }
    _hero_variant = _HERO_MAP.get(_hero_tipo, _bp_layout_raw.get('hero', 'fullscreen'))

    _estilo_detectado = d.get('estilo', 'clean')

    defaults = {
        '_blueprint':          blueprint,
        '_tipo_web':           tipo,
        '_componentes':        componentes,
        # ↓ nivel raíz — el template lee _defaults.get('_detected_sections')
        '_detected_sections':  json.dumps(_bp_secciones, ensure_ascii=False),
        'hero_tipo':           _hero_tipo,
        'comp_whatsapp':       componentes.get('whatsapp',    False),
        'comp_newsletter':     componentes.get('newsletter',  True),
        'comp_social':         componentes.get('social',      True),
        'comp_redes':          componentes.get('social',      True),
        'comp_topbar':         componentes.get('topbar',      False),
        'comp_citas':          componentes.get('citas',       False),
        # Scraper mejorado
        'estilo_detectado':    _estilo_detectado,
        'nav_style':           d.get('nav_style',     'standard'),
        'font_scale':          d.get('font_scale',    'medium'),
        'tagline_style':       d.get('tagline_style', 'descriptive'),
        'has_promo_grid':      '1' if d.get('has_promo_grid') else '0',
    } if blueprint else {
        '_tipo_web':        tipo,
        'estilo_detectado': _estilo_detectado,
    }

    layout = {
        'hero':              _hero_variant,
        'services':          _bp_layout_raw.get('services',  'cards'),
        'projects':          _bp_layout_raw.get('projects',  'masonry'),
        'team':              _bp_layout_raw.get('team',      'cards'),
        'tipo_web':          tipo,
        'section_order':     _bp_secciones,
        # Señales del scraper mejorado
        'estilo_detectado':  _estilo_detectado,
        'nav_style':         d.get('nav_style',     'standard'),
        'font_scale':        d.get('font_scale',    'medium'),
        'spacing':           _bp_layout_raw.get('spacing',   'standard'),
        'has_promo_grid':    d.get('has_promo_grid', False),
    }

    campos_estilos = {
        'color_primary':   d.get('color_primario', '#185FA5'),
        'color_accent':    d.get('color_acento',   '#0088CC'),
        'color_secondary': d.get('color_footer',   '#0A0F1E'),
        'font_heading':    d.get('fuente_titulos', 'system-ui, sans-serif'),
        'font_body':       d.get('fuente_cuerpo',  'system-ui, sans-serif'),
        'layout_json':     json.dumps(layout,    ensure_ascii=False),
        'defaults_json':   json.dumps(defaults,  ensure_ascii=False),
    }
    upsert_estilos(pid, campos_estilos)

    flash(f'Plantilla "{nombre}" creada desde scraper ({tipo}).', 'success')
    return jsonify(ok=True, pid=pid, redirect=url_for('admin_plantillas'))


# ══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN CON IA — Claude genera HTML/CSS+Jinja2 único por estilo
# ══════════════════════════════════════════════════════════════════════════════

def _extraer_html_ia(texto):
    """Extrae HTML limpio de la respuesta de Claude (puede venir en markdown)."""
    import re as _re
    m = _re.search(r'```html\s*([\s\S]+?)```', texto)
    if m:
        return m.group(1).strip()
    m = _re.search(r'```\s*([\s\S]+?)```', texto)
    if m:
        return m.group(1).strip()
    idx = texto.find('<!DOCTYPE')
    if idx == -1:
        idx = texto.find('<html')
    if idx != -1:
        return texto[idx:].strip()
    return texto.strip()


def _build_ia_prompt(a):
    """Construye el prompt para Claude a partir del análisis del scraper."""
    estilo_desc = {
        'apple-minimal': 'minimalista tipo Apple — espaciado generoso, tipografía bold sin sombras, líneas limpias, fondos blancos/gris-claro alternados',
        'ecommerce':     'tienda online — cards de producto con imagen dominante, precios visibles, CTAs urgentes en color',
        'portfolio':     'portafolio creativo — imágenes full-bleed, tipografía editorial enorme, contraste alto',
        'saas':          'SaaS/tecnología — hero oscuro con glow, features en cards, gradientes sutiles',
        'editorial':     'magazine — múltiples columnas, fotos prominentes, jerarquía tipográfica marcada',
        'dark':          'tema oscuro premium — negro profundo, acentos brillantes, sensación de lujo',
        'gradient':      'vibrante moderno — gradientes audaces, formas orgánicas, color como protagonista',
        'clean':         'corporativo limpio — profesional, secciones definidas, confianza',
    }.get(a.get('estilo', 'clean'), 'diseño web moderno y profesional')

    nav_desc = {
        'transparent-overlay': 'navbar transparente superpuesta al hero, con blur/glass al hacer scroll',
        'dark':     'navbar oscura sólida con texto claro',
        'colored':  'navbar con el color primario sólido',
        'minimal':  'navbar ultra-minimalista: solo logo + links, sin fondo visible',
        'standard': 'navbar blanca clásica con sombra sutil',
    }.get(a.get('nav_style', 'standard'), 'navbar blanca con sombra sutil')

    scale_desc = {
        'display-xl': 'títulos gigantes clamp(4rem,10vw,8rem), impacto máximo',
        'display':    'títulos grandes clamp(3rem,7vw,5.5rem)',
        'large':      'títulos medianos-grandes clamp(2.2rem,5vw,3.8rem)',
        'medium':     'títulos estándar clamp(1.8rem,4vw,2.8rem)',
    }.get(a.get('font_scale', 'medium'), 'títulos estándar clamp(1.8rem,4vw,2.8rem)')

    hero_map = {
        'fullscreen': 'hero pantalla completa con imagen de fondo y overlay',
        'split':      'hero dividido en dos columnas: texto izquierda, imagen/media derecha',
        'minimal':    'hero minimalista: texto centrado grande, sin imagen de fondo, mucho espacio',
        'gradient':   'hero con fondo de gradiente sin imagen',
        'dark':       'hero oscuro con texto claro y efecto de iluminación',
        'static':     'hero con imagen de fondo estática',
    }
    hero_desc = hero_map.get(a.get('hero_tipo', 'fullscreen'), 'hero con imagen de fondo')

    secciones = a.get('secciones', ['hero', 'servicios', 'nosotros', 'contacto'])
    if not secciones:
        secciones = ['hero', 'servicios', 'nosotros', 'contacto']

    seccion_map = {
        'hero': 'sección hero principal',
        'services': 'sección de servicios/productos',
        'servicios': 'sección de servicios/productos',
        'projects': 'galería o portafolio de proyectos',
        'proyectos': 'galería o portafolio de proyectos',
        'team': 'sección del equipo',
        'equipo': 'sección del equipo',
        'about': 'sección sobre nosotros',
        'nosotros': 'sección sobre nosotros',
        'contact': 'sección de contacto con formulario',
        'contacto': 'sección de contacto con formulario',
        'testimonials': 'testimonios de clientes',
        'newsletter': 'sección de newsletter/suscripción',
        'pricing': 'tabla de precios',
        'features': 'grid de características/beneficios',
        'stats': 'estadísticas o números clave',
        'gallery': 'galería de imágenes',
        'cta': 'banda de call-to-action',
    }
    secciones_legible = ' → '.join(seccion_map.get(s, s) for s in secciones)

    fh = (a.get('fuente_titulos') or 'Inter').split(',')[0].strip()
    fb = (a.get('fuente_cuerpo') or 'Inter').split(',')[0].strip()
    sys_f = ('system-ui', '-apple-system', 'sans-serif', 'serif', 'monospace', '')
    fh_gf = '' if fh in sys_f else fh
    fb_gf = '' if fb in sys_f else fb
    fonts_line = ''
    if fh_gf or fb_gf:
        fonts_line = f'- Fuentes: {fh_gf or "Inter"} para títulos, {fb_gf or "Inter"} para cuerpo (cargar desde Google Fonts)'

    densidad_desc = {
        'airy':    'espaciado muy generoso (padding 80-120px), mucho whitespace, sensación de lujo',
        'dense':   'compacto, información densa, padding reducido (32-48px)',
        'standard': 'espaciado estándar (padding 64-80px)',
    }.get(a.get('densidad', 'standard'), 'espaciado estándar')

    cp  = a.get('color_primario', '#1e40af')
    ca  = a.get('color_acento',   '#f59e0b')
    cfb = a.get('color_footer',   '#0f172a')

    return f"""Eres un diseñador web experto. Genera un template HTML landing page ÚNICO con CSS integrado.

ANÁLISIS VISUAL DEL SITIO A EMULAR (captura su estructura y personalidad, no su contenido):
- Estilo: {estilo_desc}
- Nav: {nav_desc} con {a.get('nav_items', 5)} items
- Hero: {hero_desc}
- Flujo de secciones: {secciones_legible}
- Escala tipográfica: {scale_desc}
- Densidad: {densidad_desc}
- Paleta: primario {cp}, acento {ca}, footer {cfb}
{fonts_line}
{'- Layout especial: grid de promoción/destacados' if a.get('has_promo_grid') else ''}

VARIABLES JINJA2 — ÚSALAS EXACTAMENTE ASÍ EN EL HTML:
{{{{ config.get('nombre_negocio', sitio.nombre) }}}}
{{{{ config.get('hero_eyebrow', '') }}}}
{{{{ config.get('hero_titulo', sitio.nombre) }}}}
{{{{ config.get('hero_subtitulo', '') }}}}
{{{{ config.get('hero_cta_texto', 'Contáctanos') }}}}
{{{{ config.get('hero_cta_href', '#contacto') }}}}
{{{{ config.get('hero_imagen', '') }}}}
{{{{ config.get('logo_url', '') }}}}
{{{{ config.get('color_primario', '{cp}') }}}}
{{{{ config.get('color_acento', '{ca}') }}}}
{{{{ config.get('color_footer_bg', '{cfb}') }}}}
{{{{ config.get('color_texto', '#1e293b') }}}}
{{{{ config.get('fuente_titulos', '{fh}') }}}}
{{{{ config.get('fuente_cuerpo', '{fb}') }}}}
{{{{ config.get('nosotros_titulo', 'Sobre nosotros') }}}}
{{{{ config.get('nosotros_descripcion', '') }}}}
{{{{ config.get('nosotros_imagen', '') }}}}
{{{{ config.get('contacto_email', '') }}}}
{{{{ config.get('contacto_telefono', '') }}}}
{{{{ config.get('contacto_direccion', '') }}}}
{{{{ sitio.slug }}}}

LOOPS DE SECCIONES DINÁMICAS (incluir si aplica al estilo):
{{% if secciones.servicios %}}
{{% for srv in secciones.servicios %}}
  {{{{ srv.get('titulo','') }}}}  {{{{ srv.get('descripcion','') }}}}
  {{{{ srv.get('icono','') }}}}   {{{{ srv.get('imagen','') }}}}
  {{{{ srv.get('precio','') }}}}  {{{{ srv.get('cta_texto','Ver más') }}}}
{{% endfor %}}
{{% endif %}}

{{% if secciones.proyectos %}}
{{% for p in secciones.proyectos %}}
  {{{{ p.get('titulo','') }}}}  {{{{ p.get('imagen','') }}}}  {{{{ p.get('categoria','') }}}}
{{% endfor %}}
{{% endif %}}

{{% if secciones.equipo %}}
{{% for m in secciones.equipo %}}
  {{{{ m.get('nombre','') }}}}  {{{{ m.get('cargo','') }}}}  {{{{ m.get('imagen','') }}}}
{{% endfor %}}
{{% endif %}}

REQUISITOS TÉCNICOS OBLIGATORIOS:
1. HTML5 completo: <!DOCTYPE html>, <html lang="es">, <head> con <meta charset>, <meta viewport>, <title>
2. TODO el CSS en un único bloque <style> al final del <head>
3. :root con variables: --c-primary, --c-accent, --c-dark, --c-text, --font-title, --font-body (inicializadas con config.get)
4. Responsive: @media (max-width: 768px) y @media (max-width: 480px)
5. JS inline al final del body: hamburger menu + IntersectionObserver para .fade-up
6. Formulario de contacto: <form method="POST" action="/s/{{{{ sitio.slug }}}}/enviar-contacto">
7. Sin Bootstrap, sin jQuery, sin dependencias externas (solo Google Fonts si corresponde)

REGLA CRÍTICA: Responde ÚNICAMENTE con el código HTML. Sin explicaciones, sin markdown, sin comentarios fuera del HTML. Empieza con <!DOCTYPE html>"""


@app.route('/admin/scraper/generar-con-ia', methods=['POST'])
@admin_requerido
def admin_scraper_generar_ia():
    import re as _re, unicodedata as _ud

    # ── Leer API key ──────────────────────────────────────────────────────────
    _ak = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not _ak:
        # Intentar desde .env local
        _env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(_env_path):
            for _ln in open(_env_path):
                _ln = _ln.strip()
                if _ln.startswith('ANTHROPIC_API_KEY='):
                    _ak = _ln.split('=', 1)[1].strip().strip('"').strip("'")
    if not _ak:
        return jsonify(ok=False, error='ANTHROPIC_API_KEY no configurada. Agrégala al .env de PythonAnywhere.'), 400

    d = request.get_json(force=True)

    nombre = d.get('nombre', '').strip()
    clave  = d.get('clave',  '').strip().lower()
    if not nombre or not clave:
        return jsonify(ok=False, error='Nombre y clave son obligatorios.'), 400

    # Sanear clave
    clave = _ud.normalize('NFD', clave)
    clave = ''.join(c for c in clave if _ud.category(c) != 'Mn')
    clave = _re.sub(r'[^a-z0-9]+', '-', clave).strip('-')[:30]
    if not clave or not clave[0].isalpha():
        clave = 'p-' + clave
    clave = clave[:30]

    # ── Construir prompt ──────────────────────────────────────────────────────
    analisis = {
        'estilo':          d.get('estilo',          'clean'),
        'nav_style':       d.get('nav_transparente') and 'transparent-overlay' or d.get('nav_style', 'standard'),
        'nav_items':       d.get('nav_items',        5),
        'hero_tipo':       d.get('hero_tipo',        'fullscreen'),
        'font_scale':      d.get('font_scale',       'medium'),
        'densidad':        d.get('densidad',         'standard'),
        'has_promo_grid':  d.get('has_promo_grid',   False),
        'secciones':       d.get('secciones',        []),
        'color_primario':  d.get('color_primario',   '#1e40af'),
        'color_acento':    d.get('color_acento',     '#f59e0b'),
        'color_footer':    d.get('color_footer',     '#0f172a'),
        'fuente_titulos':  d.get('fuente_titulos',   'Inter'),
        'fuente_cuerpo':   d.get('fuente_cuerpo',    'Inter'),
        'url_analizada':   d.get('url_analizada',    ''),
        'weight_style':    d.get('weight_style',     'balanced'),
        'is_image_dominant': d.get('is_image_dominant', False),
    }
    prompt = _build_ia_prompt(analisis)

    # ── Llamar a Claude API (urllib — sin dependencias externas) ─────────────
    try:
        import urllib.request as _urlreq
        import urllib.error  as _urlerr
        import json as _json
        _body = _json.dumps({
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 4096,
            'messages': [{'role': 'user', 'content': prompt}]
        }).encode('utf-8')
        _req = _urlreq.Request(
            'https://api.anthropic.com/v1/messages',
            data=_body,
            headers={
                'x-api-key':         _ak,
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json',
            },
            method='POST'
        )
        with _urlreq.urlopen(_req, timeout=60) as _resp:
            _data = _json.loads(_resp.read().decode('utf-8'))
        html_raw = _data['content'][0]['text']
    except _urlerr.HTTPError as e:
        _err_body = e.read().decode('utf-8', errors='replace')
        return jsonify(ok=False, error=f'API error {e.code}: {_err_body[:300]}'), 500
    except Exception as e:
        return jsonify(ok=False, error=f'Error llamando a Claude API: {str(e)}'), 500

    html_generado = _extraer_html_ia(html_raw)

    # Validación básica
    if len(html_generado) < 800 or '<!DOCTYPE' not in html_generado.upper():
        return jsonify(ok=False, error='La IA no generó HTML válido. Intenta de nuevo o ajusta los parámetros.'), 500

    # ── Guardar plantilla en DB ───────────────────────────────────────────────
    try:
        pid = crear_plantilla(clave, nombre, 'landing',
                              f'Generada con IA — {analisis["url_analizada"]}', '', '{}')
    except Exception:
        return jsonify(ok=False, error=f'La clave "{clave}" ya existe. Cambia el nombre.'), 409

    campos_estilos = {
        'color_primary':   analisis['color_primario'],
        'color_accent':    analisis['color_acento'],
        'color_secondary': analisis['color_footer'],
        'font_heading':    analisis['fuente_titulos'],
        'font_body':       analisis['fuente_cuerpo'],
        'defaults_json':   json.dumps({
            'estilo_detectado': analisis['estilo'],
            'url_origen':       analisis['url_analizada'],
            'generado_ia':      '1',
            'color_primario':   analisis['color_primario'],
            'color_acento':     analisis['color_acento'],
            'color_footer_bg':  analisis['color_footer'],
            'fuente_titulos':   analisis['fuente_titulos'],
            'fuente_cuerpo':    analisis['fuente_cuerpo'],
        }),
    }
    upsert_estilos(pid, campos_estilos)

    # ── Guardar template HTML en disco ────────────────────────────────────────
    tpl_dir  = os.path.join(app.root_path, 'templates', 'sites', clave)
    os.makedirs(tpl_dir, exist_ok=True)
    tpl_path = os.path.join(tpl_dir, 'index.html')
    with open(tpl_path, 'w', encoding='utf-8') as _f:
        _f.write(html_generado)

    flash(f'Plantilla "{nombre}" generada con IA ✨', 'success')
    return jsonify(ok=True, pid=pid, redirect=url_for('admin_plantillas'))


@app.route('/admin/scraper/crear-desde-categoria', methods=['POST'])
@admin_requerido
def admin_scraper_crear_categoria():
    import re as _re
    d = request.get_json(force=True)

    categoria = d.get('categoria', '').strip().lower()
    nombre    = d.get('nombre', '').strip()
    clave     = d.get('clave', '').strip().lower()
    tipo      = d.get('tipo', 'landing')

    if categoria not in _CATEGORIAS:
        return jsonify(ok=False, error=f'Categoría "{categoria}" no reconocida. '
                       f'Disponibles: {", ".join(_CATEGORIAS.keys())}'), 400
    if not nombre or not clave:
        return jsonify(ok=False, error='Nombre y clave son obligatorios.'), 400
    if not _re.match(r'^[a-z][a-z0-9_-]{1,29}$', clave):
        return jsonify(ok=False, error='Clave no válida: solo minúsculas, números, guiones.'), 400

    cat = _CATEGORIAS[categoria]
    layout = cat['layout']

    # Construir payload enriquecido desde la categoría + overrides del usuario
    payload_cat = {
        'color_primario':     d.get('color_primario', cat['color_primary']),
        'color_acento':       d.get('color_acento',   cat['color_accent']),
        'color_footer':       d.get('color_footer',   cat['color_secondary']),
        'fuente_titulos':     cat['font_heading'],
        'fuente_cuerpo':      cat['font_body'],
        # Nuevos campos mobile-first y de secciones desde la categoría
        'secciones_activas':  cat.get('secciones', []),
        'mobile_breakpoints': cat.get('mobile_breakpoints', {}),
        'componentes':        cat.get('componentes', {}),
        'hero_tipo':          cat.get('hero_tipo', layout.get('hero', 'split')),
        'features':           cat.get('features', []),
        # Pasar cualquier override del usuario
        **{k: v for k, v in d.items() if k not in (
            'categoria', 'nombre', 'clave', 'tipo',
            'color_primario', 'color_acento', 'color_footer',
        )},
    }

    defaults = _defaults_desde_payload(payload_cat, layout)

    try:
        pid = crear_plantilla(clave, nombre, tipo,
                              f'Plantilla {categoria} — generada desde categoría', '', '{}')
    except Exception:
        return jsonify(ok=False, error=f'La clave "{clave}" ya existe.'), 409

    campos_estilos = {
        'color_primary':   d.get('color_primario', cat['color_primary']),
        'color_accent':    d.get('color_acento',   cat['color_accent']),
        'color_secondary': d.get('color_footer',   cat['color_secondary']),
        'font_heading':    cat['font_heading'],
        'font_body':       cat['font_body'],
        'layout_json':     json.dumps(layout, ensure_ascii=False),
        'defaults_json':   json.dumps(defaults, ensure_ascii=False),
    }
    upsert_estilos(pid, campos_estilos)

    flash(f'Plantilla "{nombre}" ({categoria}) creada con layout mobile-first.', 'success')
    return jsonify(ok=True, pid=pid, redirect=url_for('admin_plantillas'))


if __name__ == '__main__':
    app.run(debug=True, port=5002)