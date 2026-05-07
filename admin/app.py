from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os

from db import (
    init_db, obtener_cliente, obtener_cliente_por_id,
    obtener_plantillas_cliente, listar_clientes,
    crear_cliente, actualizar_cliente, eliminar_cliente, set_accesos
)
from parser import extraer_valores, aplicar_cambios, git_push

app = Flask(__name__)
app.secret_key = 'admin-plantillas-rd-2026'

BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE, 'shared', 'site-schema.json')


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
    """Solo usuarios con plan='admin' pueden acceder."""
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


# ── Inicializar DB al arrancar ────────────────────────────────────────────────
init_db()


# ── Rutas públicas ────────────────────────────────────────────────────────────

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

        cliente = obtener_cliente(usuario)

        if cliente and cliente['password'] == password:
            plantillas = obtener_plantillas_cliente(cliente['id'])
            session['usuario']    = cliente['usuario']
            session['nombre']     = cliente['nombre'] or cliente['usuario']
            session['plan']       = cliente['plan']
            session['cliente_id'] = cliente['id']
            session['plantillas'] = plantillas
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
    plantillas = {
        k: v for k, v in schema['plantillas'].items()
        if k in plantillas_cliente
    }
    return render_template('dashboard.html',
        plantillas=plantillas,
        usuario=session['usuario'],
        nombre=session.get('nombre', session['usuario']),
        es_admin=(session.get('plan') == 'admin')
    )


# ── Editor / Preview ──────────────────────────────────────────────────────────

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

    valores   = extraer_valores(plantilla['ruta'], plantilla['campos'])
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


# ── Panel de admin — gestión de clientes ─────────────────────────────────────

@app.route('/admin/clientes')
@admin_requerido
def admin_clientes():
    schema    = cargar_schema()
    clientes  = listar_clientes()
    # Adjuntar plantillas de cada cliente para mostrarlas en la tabla
    clientes_data = []
    for c in clientes:
        plantillas = obtener_plantillas_cliente(c['id'])
        clientes_data.append({
            'id':        c['id'],
            'usuario':   c['usuario'],
            'nombre':    c['nombre'],
            'plan':      c['plan'],
            'activo':    c['activo'],
            'plantillas': plantillas,
        })
    return render_template('admin_clientes.html',
        clientes=clientes_data,
        nombre=session.get('nombre'),
        plantillas_disponibles=list(schema['plantillas'].keys())
    )


@app.route('/admin/clientes/nuevo', methods=['GET', 'POST'])
@admin_requerido
def admin_cliente_nuevo():
    schema = cargar_schema()
    plantillas_disponibles = list(schema['plantillas'].keys())

    if request.method == 'POST':
        usuario    = request.form.get('usuario', '').strip()
        password   = request.form.get('password', '').strip()
        nombre     = request.form.get('nombre', '').strip()
        plan       = request.form.get('plan', 'landing')
        seleccion  = request.form.getlist('plantillas')

        if not usuario or not password:
            flash('Usuario y contraseña son obligatorios.', 'error')
        else:
            try:
                import sqlite3
                cliente_id = crear_cliente(usuario, password, nombre, plan)
                set_accesos(cliente_id, seleccion)
                flash(f'Cliente "{usuario}" creado correctamente.', 'success')
                return redirect(url_for('admin_clientes'))
            except Exception:
                flash(f'El usuario "{usuario}" ya existe.', 'error')

    return render_template('admin_cliente_form.html',
        modo='nuevo',
        cliente=None,
        plantillas_asignadas=[],
        plantillas_disponibles=plantillas_disponibles,
        nombre=session.get('nombre')
    )


@app.route('/admin/clientes/<int:cliente_id>/editar', methods=['GET', 'POST'])
@admin_requerido
def admin_cliente_editar(cliente_id):
    schema = cargar_schema()
    plantillas_disponibles = list(schema['plantillas'].keys())

    cliente = obtener_cliente_por_id(cliente_id)
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

        # Refrescar sesión si el admin editó su propia cuenta
        if session.get('cliente_id') == cliente_id:
            session['nombre']     = nombre or session['nombre']
            session['plan']       = plan
            session['plantillas'] = seleccion

        flash(f'Cliente "{cliente["usuario"]}" actualizado.', 'success')
        return redirect(url_for('admin_clientes'))

    plantillas_asignadas = obtener_plantillas_cliente(cliente_id)

    return render_template('admin_cliente_form.html',
        modo='editar',
        cliente=dict(cliente),
        plantillas_asignadas=plantillas_asignadas,
        plantillas_disponibles=plantillas_disponibles,
        nombre=session.get('nombre')
    )


@app.route('/admin/clientes/<int:cliente_id>/eliminar', methods=['POST'])
@admin_requerido
def admin_cliente_eliminar(cliente_id):
    cliente = obtener_cliente_por_id(cliente_id)
    if not cliente:
        flash('Cliente no encontrado.', 'error')
        return redirect(url_for('admin_clientes'))

    # No permitir que el admin se elimine a sí mismo
    if session.get('cliente_id') == cliente_id:
        flash('No puedes eliminar tu propia cuenta.', 'error')
        return redirect(url_for('admin_clientes'))

    eliminar_cliente(cliente_id)
    flash(f'Cliente "{cliente["usuario"]}" eliminado.', 'success')
    return redirect(url_for('admin_clientes'))


if __name__ == '__main__':
    app.run(debug=True, port=5002)
