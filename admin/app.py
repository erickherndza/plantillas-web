from flask import Flask, render_template, request, redirect, url_for, session, flash
import json, os
from parser import extraer_valores, aplicar_cambios, git_push

app = Flask(__name__)
app.secret_key = 'admin-plantillas-rd-2026'

BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH   = os.path.join(BASE, 'shared', 'site-schema.json')
CLIENTES_PATH = os.path.join(BASE, 'admin', 'clientes.json')


def cargar_schema():
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def cargar_clientes():
    if not os.path.exists(CLIENTES_PATH):
        return {}
    with open(CLIENTES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def login_requerido(f):
    """Decorator simple para rutas protegidas."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def plantilla_autorizada(plantilla_id):
    return plantilla_id in session.get('plantillas', [])


# ── Rutas ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        usuario  = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        clientes = cargar_clientes()

        if usuario in clientes and clientes[usuario]['password'] == password:
            session['usuario']    = usuario
            session['nombre']     = clientes[usuario].get('nombre', usuario)
            session['plantillas'] = clientes[usuario].get('plantillas', [])
            return redirect(url_for('dashboard'))

        flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_requerido
def dashboard():
    schema             = cargar_schema()
    plantillas_cliente = session.get('plantillas', [])
    plantillas = {
        k: v for k, v in schema['plantillas'].items()
        if k in plantillas_cliente
    }
    return render_template('dashboard.html',
        plantillas=plantillas,
        usuario=session['usuario'],
        nombre=session.get('nombre', session['usuario'])
    )


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
        # Reconstruir nuevos_valores desde el form
        nuevos_valores = {}
        for seccion, items in plantilla['campos'].items():
            nuevos_valores[seccion] = {}
            for campo_id in items:
                key = f"{seccion}__{campo_id}"
                nuevos_valores[seccion][campo_id] = request.form.get(key, '')

        exito = aplicar_cambios(plantilla['ruta'], plantilla['campos'], nuevos_valores)

        if exito:
            ok, msg = git_push(f"Admin: {session['usuario']} actualizó {plantilla_id}")
            if ok:
                flash('¡Cambios publicados! Tu sitio se actualizará en ~30 segundos.', 'success')
            else:
                flash(f'Guardado localmente. Error al publicar: {msg}', 'warning')
        else:
            flash('Error al guardar los cambios. Revisa los logs.', 'error')

        return redirect(url_for('editor', plantilla_id=plantilla_id))

    # GET: cargar valores actuales del HTML
    valores = extraer_valores(plantilla['ruta'], plantilla['campos'])
    secciones = list(plantilla['campos'].keys())

    return render_template('editor.html',
        plantilla_id=plantilla_id,
        plantilla=plantilla,
        valores=valores,
        secciones=secciones,
        usuario=session['usuario'],
        nombre=session.get('nombre', session['usuario'])
    )


@app.route('/preview/<plantilla_id>')
@login_requerido
def preview(plantilla_id):
    if not plantilla_autorizada(plantilla_id):
        flash('No tienes acceso a esta plantilla', 'error')
        return redirect(url_for('dashboard'))

    schema    = cargar_schema()
    plantilla = schema['plantillas'].get(plantilla_id, {})
    url       = plantilla.get('preview_url', 'https://plantillas-web.themethoner.workers.dev/')
    return redirect(url)


if __name__ == '__main__':
    app.run(debug=True, port=5002)
