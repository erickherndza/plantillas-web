"""
db.py — Capa de datos para el panel admin de plantillas-web
Tablas (admin):
  clientes  — usuarios del panel de admin (admin + clientes legacy)
  accesos   — qué plantillas puede editar cada cliente (many-to-many)
Tablas (CMS multi-usuario):
  plantillas        — definición de plantillas disponibles (admin crea)
  usuarios          — usuarios finales que crean sus propios sitios
  sitios            — sitio de cada usuario (plantilla elegida + slug)
  configuracion_sitio — todos los valores customizados (clave/valor)
  secciones_contenido — contenido repetible (slider, servicios, equipo…)
"""

import sqlite3
import os
import secrets
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plantillas.db')


def get_db():
    """Abre una conexión con row_factory=Row para acceso por nombre de columna."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Crea las tablas si no existen. Idempotente — seguro de llamar siempre."""
    conn = get_db()
    conn.executescript("""
        -- ── Admin panel (legado) ─────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS clientes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario  TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            nombre   TEXT    DEFAULT '',
            plan     TEXT    DEFAULT 'landing',
            activo   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS accesos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            plantilla_clave TEXT    NOT NULL,
            UNIQUE(cliente_id, plantilla_clave)
        );

        -- ── CMS multi-usuario ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS plantillas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            clave       TEXT    UNIQUE NOT NULL,
            nombre      TEXT    NOT NULL,
            tipo        TEXT    DEFAULT 'landing',
            descripcion TEXT    DEFAULT '',
            preview_img TEXT    DEFAULT '',
            activo      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    UNIQUE NOT NULL,
            password   TEXT    NOT NULL,
            nombre     TEXT    DEFAULT '',
            plan       TEXT    DEFAULT 'landing',
            activo     INTEGER DEFAULT 1,
            created_at TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sitios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            plantilla_id INTEGER NOT NULL REFERENCES plantillas(id),
            slug         TEXT    UNIQUE NOT NULL,
            nombre       TEXT    NOT NULL,
            activo       INTEGER DEFAULT 1,
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS configuracion_sitio (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sitio_id INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
            clave    TEXT    NOT NULL,
            valor    TEXT    NOT NULL DEFAULT '',
            UNIQUE(sitio_id, clave)
        );

        CREATE TABLE IF NOT EXISTS secciones_contenido (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sitio_id INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
            seccion  TEXT    NOT NULL,
            orden    INTEGER DEFAULT 0,
            datos    TEXT    NOT NULL DEFAULT '{}'
        );
    """)

    # Tablas adicionales
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mensajes_contacto (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sitio_id   INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
            nombre     TEXT    NOT NULL,
            email      TEXT    NOT NULL,
            telefono   TEXT    DEFAULT '',
            mensaje    TEXT    NOT NULL,
            leido      INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now'))
        );
    """)

    # Tabla de citas médicas
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS citas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sitio_id        INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
            especialista    TEXT    NOT NULL DEFAULT '',
            fecha           TEXT    NOT NULL,
            hora            TEXT    NOT NULL,
            paciente_nombre TEXT    NOT NULL,
            paciente_email  TEXT    NOT NULL DEFAULT '',
            paciente_tel    TEXT    NOT NULL DEFAULT '',
            motivo          TEXT    DEFAULT '',
            estado          TEXT    DEFAULT 'pendiente',
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token      TEXT    UNIQUE NOT NULL,
            expires_at TEXT    NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now'))
        );
    """)

    # Migración: columna campos_schema en plantillas (idempotente)
    try:
        conn.execute("ALTER TABLE plantillas ADD COLUMN campos_schema TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Migración: columna formato en sitios (idempotente)
    try:
        conn.execute("ALTER TABLE sitios ADD COLUMN formato TEXT DEFAULT 'web5'")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Migración: columna google_id en usuarios (idempotente)
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN google_id TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Migración: columna email en clientes (idempotente)
    try:
        conn.execute("ALTER TABLE clientes ADD COLUMN email TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Tabla tokens reset para clientes/admin
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            token      TEXT    UNIQUE NOT NULL,
            expires_at TEXT    NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now'))
        );

        -- ── CMS Editor de plantillas ─────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS menu_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id INTEGER NOT NULL REFERENCES plantillas(id) ON DELETE CASCADE,
            label        TEXT    NOT NULL,
            url          TEXT    NOT NULL DEFAULT '#',
            orden        INTEGER DEFAULT 0,
            parent_id    INTEGER DEFAULT NULL REFERENCES menu_items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS slider_slides (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id INTEGER NOT NULL REFERENCES plantillas(id) ON DELETE CASCADE,
            imagen_url   TEXT    DEFAULT '',
            titulo       TEXT    DEFAULT '',
            subtitulo    TEXT    DEFAULT '',
            orden        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS custom_code (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id INTEGER NOT NULL REFERENCES plantillas(id) ON DELETE CASCADE,
            tipo         TEXT    CHECK(tipo IN ('css','js','html')) NOT NULL DEFAULT 'css',
            inject_in    TEXT    CHECK(inject_in IN ('head','body_end','seccion')) NOT NULL DEFAULT 'head',
            seccion_target TEXT  DEFAULT NULL,
            codigo       TEXT    NOT NULL DEFAULT '',
            activo       INTEGER DEFAULT 1,
            created_at   TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Tabla estilos de plantilla
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS plantilla_estilos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id     INTEGER NOT NULL UNIQUE REFERENCES plantillas(id) ON DELETE CASCADE,
            color_primary    TEXT DEFAULT '#185FA5',
            color_secondary  TEXT DEFAULT '#0A0F1E',
            color_accent     TEXT DEFAULT '#0088CC',
            color_neutral    TEXT DEFAULT '#E8EAF0',
            font_heading     TEXT DEFAULT 'system-ui, sans-serif',
            font_body        TEXT DEFAULT 'system-ui, sans-serif',
            font_size_h1     INTEGER DEFAULT 48,
            font_size_h2     INTEGER DEFAULT 32,
            font_size_body   INTEGER DEFAULT 16,
            line_height      REAL DEFAULT 1.6,
            radius_btn       INTEGER DEFAULT 8,
            radius_card      INTEGER DEFAULT 12,
            radius_input     INTEGER DEFAULT 6,
            section_padding  INTEGER DEFAULT 80,
            gap_elements     INTEGER DEFAULT 24,
            modo_tema        TEXT DEFAULT 'dark',
            efectos_json     TEXT DEFAULT '{"entrada":true,"hover_btn":true,"parallax":false,"cursor":false,"velocidad":"400ms","easing":"ease-out"}',
            header_json      TEXT DEFAULT '{}',
            hero_json        TEXT DEFAULT '{}',
            footer_json      TEXT DEFAULT '{}',
            movil_json       TEXT DEFAULT '{"h1":32,"padding":40,"hamburguesa":true}',
            preset_activo    TEXT DEFAULT 'oceano-oscuro'
        );
    """)
    conn.commit()

    # Migración: columnas layout_json y defaults_json en plantilla_estilos (idempotente)
    for _col, _def in [
        ('layout_json',   '\'{"hero":"fullscreen","services":"grid","projects":"grid","team":"cards"}\''),
        ('defaults_json', '\'{}\''),
    ]:
        try:
            conn.execute(f"ALTER TABLE plantilla_estilos ADD COLUMN {_col} TEXT DEFAULT {_def}")
            conn.commit()
        except Exception:
            pass  # ya existe

    # Migraciones columnas plantillas
    for col, default in [
        ('slider_config', '\'{"efecto":"fade","intervalo":4,"flechas":true,"puntos":true,"modo":"seccion"}\''),
        ('footer_config',  '\'{"columnas":3,"bg_color":"#012840","copyright":"© 2025 Mi Empresa.","cols":[]}\' '),
        ('secciones_habilitadas', '\'[]\''),
    ]:
        try:
            conn.execute(f"ALTER TABLE plantillas ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except Exception:
            pass

    # ── Tabla planes ─────────────────────────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS planes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            clave       TEXT UNIQUE NOT NULL,
            nombre      TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            precio      REAL DEFAULT 0,
            tipo_acceso TEXT DEFAULT 'landing',
            max_sitios  INTEGER DEFAULT 1,
            activo      INTEGER DEFAULT 1
        );
    """)
    conn.commit()

    # Migración: plan_id en clientes (idempotente)
    try:
        conn.execute("ALTER TABLE clientes ADD COLUMN plan_id INTEGER REFERENCES planes(id)")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Migración: plan_requerido en plantillas (idempotente)
    try:
        conn.execute("ALTER TABLE plantillas ADD COLUMN plan_requerido TEXT DEFAULT 'basico'")
        conn.commit()
    except Exception:
        pass  # ya existe

    # Seed planes si la tabla está vacía
    _count_planes = conn.execute("SELECT COUNT(*) FROM planes").fetchone()[0]
    if _count_planes == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO planes (clave, nombre, descripcion, precio, tipo_acceso, max_sitios) VALUES (?,?,?,?,?,?)",
            [
                ('basico',      'Plan Básico',      'Landing page para tu negocio.',          0,     'landing', 1),
                ('corporativo', 'Plan Corporativo',  'Sitio web completo de 5 páginas.',       29.99, 'web5',    3),
                ('premium',     'Plan Premium',      'Landing + web completa, múltiples sitios.', 49.99, 'ambos',   10),
            ]
        )
        conn.commit()

    # Seed plantillas base si no existen
    _schema_completo = '{"secciones": ["apariencia", "marca", "hero", "nosotros", "servicios", "proyectos", "equipo", "contacto"]}'
    _plantillas_seed = [
        ('arquitectura', 'Arquitectura / Diseño',         'web5', 'Para estudios de arquitectura, diseño e ingeniería.'),
        ('doctores',     'Consultorio / Clínica Médica',  'web5', 'Para consultorios médicos, clínicas y centros de salud.'),
        ('empresa',      'Web Empresarial',               'web5', 'Sitio completo con 5 páginas para cualquier negocio.'),
        ('restaurante',  'Restaurante / Gastronomía',     'web5', 'Para restaurantes, cafés, bares y negocios de comida.'),
        ('salon',        'Salón de Belleza / Spa',        'web5', 'Para salones, spas, centros de estética y bienestar.'),
        ('abogados',     'Bufete de Abogados / Legal',    'web5', 'Para bufetes legales, notarías y consultorios jurídicos.'),
    ]
    for clave, nombre, tipo, desc in _plantillas_seed:
        conn.execute("""
            INSERT OR IGNORE INTO plantillas (clave, nombre, tipo, descripcion, preview_img, campos_schema)
            VALUES (?, ?, ?, ?, '', ?)
        """, (clave, nombre, tipo, desc, _schema_completo))
        # Actualizar tipo y schema si la fila ya existía (migración)
        conn.execute("""
            UPDATE plantillas SET tipo=?, descripcion=?, campos_schema=?
            WHERE clave=? AND (tipo != ? OR campos_schema = '{}' OR campos_schema IS NULL)
        """, (tipo, desc, _schema_completo, clave, tipo))

    conn.commit()
    conn.close()


# ── Helpers de lectura ────────────────────────────────────────────────────────

def obtener_cliente(usuario: str):
    """Devuelve un Row del cliente o None si no existe."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM clientes WHERE usuario = ? AND activo = 1",
        (usuario,)
    ).fetchone()
    conn.close()
    return row


def obtener_plantillas_cliente(cliente_id: int) -> list[str]:
    """Lista de claves de plantilla a las que tiene acceso el cliente."""
    conn = get_db()
    rows = conn.execute(
        "SELECT plantilla_clave FROM accesos WHERE cliente_id = ?",
        (cliente_id,)
    ).fetchall()
    conn.close()
    return [r["plantilla_clave"] for r in rows]


def listar_clientes():
    """Todos los clientes activos (para panel de admin)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, usuario, nombre, plan, activo FROM clientes ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


# ── Helpers de escritura ──────────────────────────────────────────────────────

def crear_cliente(usuario: str, password: str, nombre: str = '', plan: str = 'landing'):
    """Inserta un cliente nuevo. Lanza sqlite3.IntegrityError si el usuario ya existe."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO clientes (usuario, password, nombre, plan) VALUES (?, ?, ?, ?)",
        (usuario, password, nombre, plan)
    )
    cliente_id = cur.lastrowid
    conn.commit()
    conn.close()
    return cliente_id


def asignar_plantilla(cliente_id: int, plantilla_clave: str):
    """Da acceso a una plantilla. Ignora duplicados."""
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO accesos (cliente_id, plantilla_clave) VALUES (?, ?)",
        (cliente_id, plantilla_clave)
    )
    conn.commit()
    conn.close()


def revocar_plantilla(cliente_id: int, plantilla_clave: str):
    """Quita acceso a una plantilla."""
    conn = get_db()
    conn.execute(
        "DELETE FROM accesos WHERE cliente_id = ? AND plantilla_clave = ?",
        (cliente_id, plantilla_clave)
    )
    conn.commit()
    conn.close()


def obtener_cliente_por_id(cliente_id: int):
    """Devuelve un Row del cliente por id o None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    conn.close()
    return row


def actualizar_cliente(cliente_id: int, nombre: str, password: str, plan: str):
    """Actualiza datos del cliente. No toca el campo usuario."""
    conn = get_db()
    conn.execute(
        "UPDATE clientes SET nombre = ?, password = ?, plan = ? WHERE id = ?",
        (nombre, password, plan, cliente_id)
    )
    conn.commit()
    conn.close()


def set_accesos(cliente_id: int, plantilla_claves: list[str]):
    """Reemplaza todos los accesos de un cliente por la lista dada."""
    conn = get_db()
    conn.execute("DELETE FROM accesos WHERE cliente_id = ?", (cliente_id,))
    for clave in plantilla_claves:
        conn.execute(
            "INSERT OR IGNORE INTO accesos (cliente_id, plantilla_clave) VALUES (?, ?)",
            (cliente_id, clave)
        )
    conn.commit()
    conn.close()


def eliminar_cliente(cliente_id: int):
    """Elimina el cliente y sus accesos (ON DELETE CASCADE)."""
    conn = get_db()
    conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    conn.commit()
    conn.close()


# ── Plantillas (CMS) ──────────────────────────────────────────────────────────

def listar_plantillas_activas() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM plantillas WHERE activo = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def obtener_plantilla_por_id(plantilla_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM plantillas WHERE id = ?", (plantilla_id,)
    ).fetchone()
    conn.close()
    return row


def listar_todas_plantillas() -> list:
    """Lista todas las plantillas (activas e inactivas) — para panel admin."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM plantillas ORDER BY activo DESC, id"
    ).fetchall()
    conn.close()
    return rows


def crear_plantilla(clave: str, nombre: str, tipo: str,
                    descripcion: str = '', preview_img: str = '',
                    campos_schema: str = '{}') -> int:
    """Inserta una plantilla nueva. Lanza IntegrityError si la clave ya existe."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO plantillas (clave, nombre, tipo, descripcion, preview_img, campos_schema)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (clave.strip().lower(), nombre.strip(), tipo, descripcion.strip(),
         preview_img.strip(), campos_schema)
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def actualizar_plantilla(plantilla_id: int, nombre: str, tipo: str,
                         descripcion: str, preview_img: str,
                         campos_schema: str):
    """Actualiza los metadatos de una plantilla. No toca la clave."""
    conn = get_db()
    conn.execute(
        "UPDATE plantillas SET nombre=?, tipo=?, descripcion=?, preview_img=?, campos_schema=?"
        " WHERE id=?",
        (nombre.strip(), tipo, descripcion.strip(),
         preview_img.strip(), campos_schema, plantilla_id)
    )
    conn.commit()
    conn.close()


def toggle_plantilla(plantilla_id: int):
    """Activa o desactiva una plantilla."""
    conn = get_db()
    conn.execute(
        "UPDATE plantillas SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END WHERE id=?",
        (plantilla_id,)
    )
    conn.commit()
    conn.close()


def contar_sitios_por_plantilla(plantilla_id: int) -> int:
    """Cuántos sitios activos usan esta plantilla."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as n FROM sitios WHERE plantilla_id=? AND activo=1",
        (plantilla_id,)
    ).fetchone()
    conn.close()
    return row['n'] if row else 0


def listar_mensajes_sitio(sitio_id: int, solo_no_leidos: bool = False) -> list:
    """Devuelve los mensajes de contacto de un sitio."""
    conn = get_db()
    q = "SELECT * FROM mensajes_contacto WHERE sitio_id=?"
    if solo_no_leidos:
        q += " AND leido=0"
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, (sitio_id,)).fetchall()
    conn.close()
    return rows


def marcar_mensaje_leido(mensaje_id: int):
    conn = get_db()
    conn.execute("UPDATE mensajes_contacto SET leido=1 WHERE id=?", (mensaje_id,))
    conn.commit()
    conn.close()


# ── Usuarios (CMS) ────────────────────────────────────────────────────────────

def crear_usuario(email: str, password_hash: str, nombre: str = '', plan: str = 'landing') -> int:
    """Inserta un usuario nuevo. Lanza sqlite3.IntegrityError si el email ya existe."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO usuarios (email, password, nombre, plan) VALUES (?, ?, ?, ?)",
        (email.lower().strip(), password_hash, nombre.strip(), plan)
    )
    uid = cur.lastrowid
    conn.commit()
    conn.close()
    return uid


def obtener_usuario_por_email(email: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email = ? AND activo = 1",
        (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return row


def obtener_usuario_por_id(uid: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,)
    ).fetchone()
    conn.close()
    return row


# ── Sitios (CMS) ──────────────────────────────────────────────────────────────

def slug_disponible(slug: str) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM sitios WHERE slug = ?", (slug,)
    ).fetchone()
    conn.close()
    return row is None


def crear_sitio(usuario_id: int, plantilla_id: int, slug: str, nombre: str, formato: str = 'web5') -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO sitios (usuario_id, plantilla_id, slug, nombre, formato) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, plantilla_id, slug.lower().strip(), nombre.strip(), formato)
    )
    sitio_id = cur.lastrowid
    conn.commit()
    conn.close()
    return sitio_id


def obtener_sitios_usuario(usuario_id: int) -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, p.nombre AS plantilla_nombre, p.clave AS plantilla_clave,
               p.tipo AS plantilla_tipo
        FROM sitios s
        JOIN plantillas p ON p.id = s.plantilla_id
        WHERE s.usuario_id = ? AND s.activo = 1
        ORDER BY s.created_at DESC
    """, (usuario_id,)).fetchall()
    conn.close()
    return rows


def obtener_sitio_por_slug(slug: str):
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, p.nombre AS plantilla_nombre, p.clave AS plantilla_clave, p.tipo AS plantilla_tipo
        FROM sitios s
        JOIN plantillas p ON p.id = s.plantilla_id
        WHERE s.slug = ? AND s.activo = 1
    """, (slug,)).fetchone()
    conn.close()
    return row


def obtener_sitio_por_id(sitio_id: int):
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, p.nombre AS plantilla_nombre, p.clave AS plantilla_clave
        FROM sitios s
        JOIN plantillas p ON p.id = s.plantilla_id
        WHERE s.id = ?
    """, (sitio_id,)).fetchone()
    conn.close()
    return row

def eliminar_sitio(sitio_id: int):
    """Elimina el sitio y todo su contenido (CASCADE)."""
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM sitios WHERE id = ?", (sitio_id,))
    conn.commit()
    conn.close()


# ── Configuración del sitio (CMS) ─────────────────────────────────────────────

def get_config_sitio(sitio_id: int) -> dict:
    """Devuelve todas las claves de configuración como dict {clave: valor}."""
    conn = get_db()
    rows = conn.execute(
        "SELECT clave, valor FROM configuracion_sitio WHERE sitio_id = ?", (sitio_id,)
    ).fetchall()
    conn.close()
    return {r['clave']: r['valor'] for r in rows}


def set_config_sitio(sitio_id: int, clave: str, valor: str):
    """Guarda o actualiza un valor de configuración."""
    conn = get_db()
    conn.execute(
        "INSERT INTO configuracion_sitio (sitio_id, clave, valor) VALUES (?, ?, ?)"
        " ON CONFLICT(sitio_id, clave) DO UPDATE SET valor = excluded.valor",
        (sitio_id, clave, valor)
    )
    conn.commit()
    conn.close()


def set_config_sitio_bulk(sitio_id: int, datos: dict):
    """Guarda múltiples valores de configuración de una vez."""
    conn = get_db()
    for clave, valor in datos.items():
        conn.execute(
            "INSERT INTO configuracion_sitio (sitio_id, clave, valor) VALUES (?, ?, ?)"
            " ON CONFLICT(sitio_id, clave) DO UPDATE SET valor = excluded.valor",
            (sitio_id, clave, str(valor))
        )
    conn.commit()
    conn.close()


# ── Secciones de contenido (CMS) ──────────────────────────────────────────────

def get_secciones_contenido(sitio_id: int, seccion: str) -> list:
    """Devuelve los items de una sección como lista de dicts."""
    import json
    conn = get_db()
    rows = conn.execute(
        "SELECT datos FROM secciones_contenido WHERE sitio_id = ? AND seccion = ? ORDER BY orden",
        (sitio_id, seccion)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            result.append(json.loads(r['datos']))
        except Exception:
            result.append({})
    return result


def guardar_mensaje_contacto(sitio_id: int, nombre: str, email: str, telefono: str, mensaje: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO mensajes_contacto (sitio_id, nombre, email, telefono, mensaje) VALUES (?,?,?,?,?)",
        (sitio_id, nombre, email, telefono, mensaje)
    )
    conn.commit()
    conn.close()


def set_secciones_contenido(sitio_id: int, seccion: str, items: list):
    """Reemplaza todos los items de una sección."""
    import json
    conn = get_db()
    conn.execute(
        "DELETE FROM secciones_contenido WHERE sitio_id = ? AND seccion = ?",
        (sitio_id, seccion)
    )
    for orden, item in enumerate(items):
        conn.execute(
            "INSERT INTO secciones_contenido (sitio_id, seccion, orden, datos) VALUES (?, ?, ?, ?)",
            (sitio_id, seccion, orden, json.dumps(item, ensure_ascii=False))
        )
    conn.commit()
    conn.close()

# ── Citas ─────────────────────────────────────────────────────────────────────

def verificar_disponibilidad(sitio_id: int, especialista: str, fecha: str, hora: str) -> bool:
    """Devuelve True si el slot está disponible (sin cita confirmada/pendiente)."""
    conn = get_db()
    row = conn.execute("""
        SELECT id FROM citas
        WHERE sitio_id=? AND especialista=? AND fecha=? AND hora=?
          AND estado IN ('pendiente','confirmada')
    """, (sitio_id, especialista, fecha, hora)).fetchone()
    conn.close()
    return row is None

def crear_cita(sitio_id: int, especialista: str, fecha: str, hora: str,
               paciente_nombre: str, paciente_email: str, paciente_tel: str, motivo: str) -> int:
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO citas (sitio_id, especialista, fecha, hora,
                           paciente_nombre, paciente_email, paciente_tel, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (sitio_id, especialista, fecha, hora,
          paciente_nombre, paciente_email, paciente_tel, motivo))
    conn.commit()
    cita_id = cur.lastrowid
    conn.close()
    return cita_id

def horas_ocupadas(sitio_id: int, especialista: str, fecha: str) -> list:
    """Devuelve lista de horas ocupadas para un especialista en una fecha."""
    conn = get_db()
    rows = conn.execute("""
        SELECT hora FROM citas
        WHERE sitio_id=? AND especialista=? AND fecha=?
          AND estado IN ('pendiente','confirmada')
    """, (sitio_id, especialista, fecha)).fetchall()
    conn.close()
    return [r['hora'] for r in rows]

def listar_citas_sitio(sitio_id: int) -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM citas WHERE sitio_id=? ORDER BY fecha, hora
    """, (sitio_id,)).fetchall()
    conn.close()
    return rows

def actualizar_estado_cita(cita_id: int, estado: str):
    conn = get_db()
    conn.execute("UPDATE citas SET estado=? WHERE id=?", (estado, cita_id))
    conn.commit()
    conn.close()


# ── Reset de contraseña ───────────────────────────────────────────────────────

def crear_reset_token(usuario_id: int) -> str:
    """Genera un token de reset, invalida los anteriores y lo guarda. Retorna el token."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    # Invalidar tokens anteriores del mismo usuario
    conn.execute("UPDATE reset_tokens SET used=1 WHERE usuario_id=?", (usuario_id,))
    conn.execute(
        "INSERT INTO reset_tokens (usuario_id, token, expires_at) VALUES (?, ?, ?)",
        (usuario_id, token, expires)
    )
    conn.commit()
    conn.close()
    return token


def obtener_usuario_por_reset_token(token: str):
    """Devuelve el usuario si el token es válido, no expiró y no fue usado."""
    conn = get_db()
    row = conn.execute("""
        SELECT u.* FROM usuarios u
        JOIN reset_tokens r ON r.usuario_id = u.id
        WHERE r.token = ?
          AND r.used = 0
          AND r.expires_at > datetime('now')
          AND u.activo = 1
    """, (token,)).fetchone()
    conn.close()
    return row


def invalidar_reset_token(token: str):
    conn = get_db()
    conn.execute("UPDATE reset_tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()


def actualizar_password_usuario(uid: int, password_hash: str):
    conn = get_db()
    conn.execute("UPDATE usuarios SET password=? WHERE id=?", (password_hash, uid))
    conn.commit()
    conn.close()


# ── Google OAuth ──────────────────────────────────────────────────────────────

def obtener_usuario_por_google_id(google_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE google_id=? AND activo=1", (google_id,)
    ).fetchone()
    conn.close()
    return row


def vincular_google_id(uid: int, google_id: str):
    conn = get_db()
    conn.execute("UPDATE usuarios SET google_id=? WHERE id=?", (google_id, uid))
    conn.commit()
    conn.close()


def crear_o_vincular_google(email: str, nombre: str, google_id: str) -> dict:
    """
    Si existe un usuario con ese google_id -> retorna el usuario.
    Si existe con ese email -> vincula google_id y retorna.
    Si no existe -> crea cuenta sin contraseña y retorna.
    """
    conn = get_db()
    # Buscar por google_id primero
    row = conn.execute(
        "SELECT * FROM usuarios WHERE google_id=? AND activo=1", (google_id,)
    ).fetchone()
    if row:
        conn.close()
        return dict(row)

    # Buscar por email
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email=? AND activo=1", (email.lower().strip(),)
    ).fetchone()
    if row:
        conn.execute("UPDATE usuarios SET google_id=? WHERE id=?", (google_id, row['id']))
        conn.commit()
        conn.close()
        return dict(row)

    # Crear cuenta nueva (sin password — solo acceso via Google)
    cur = conn.execute(
        "INSERT INTO usuarios (email, password, nombre, plan, google_id) VALUES (?, '', ?, 'landing', ?)",
        (email.lower().strip(), nombre.strip(), google_id)
    )
    uid = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    result = dict(row)
    conn.close()
    return result


# ── Reset contraseña admin/clientes ──────────────────────────────────────────

def obtener_cliente_por_email(email: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM clientes WHERE email=? AND activo=1", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return row


def actualizar_email_cliente(cliente_id: int, email: str):
    conn = get_db()
    conn.execute("UPDATE clientes SET email=? WHERE id=?", (email.lower().strip(), cliente_id))
    conn.commit()
    conn.close()


def crear_admin_reset_token(cliente_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute("UPDATE admin_reset_tokens SET used=1 WHERE cliente_id=?", (cliente_id,))
    conn.execute(
        "INSERT INTO admin_reset_tokens (cliente_id, token, expires_at) VALUES (?, ?, ?)",
        (cliente_id, token, expires)
    )
    conn.commit()
    conn.close()
    return token


def obtener_cliente_por_reset_token(token: str):
    conn = get_db()
    row = conn.execute("""
        SELECT c.* FROM clientes c
        JOIN admin_reset_tokens r ON r.cliente_id = c.id
        WHERE r.token = ?
          AND r.used = 0
          AND r.expires_at > datetime('now')
          AND c.activo = 1
    """, (token,)).fetchone()
    conn.close()
    return row


def invalidar_admin_reset_token(token: str):
    conn = get_db()
    conn.execute("UPDATE admin_reset_tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()


def actualizar_password_cliente(cliente_id: int, password_hash: str):
    conn = get_db()
    conn.execute("UPDATE clientes SET password=? WHERE id=?", (password_hash, cliente_id))
    conn.commit()
    conn.close()


# ── Editor de plantillas — Menu ───────────────────────────────────────────────

def get_menu_items(plantilla_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM menu_items WHERE plantilla_id=? ORDER BY orden", (plantilla_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_menu_item(plantilla_id: int, label: str, url: str, orden: int, parent_id) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO menu_items (plantilla_id,label,url,orden,parent_id) VALUES (?,?,?,?,?)",
        (plantilla_id, label, url, orden, parent_id)
    )
    iid = cur.lastrowid
    conn.commit(); conn.close()
    return iid

def update_menu_item(item_id: int, label: str, url: str, parent_id):
    conn = get_db()
    conn.execute("UPDATE menu_items SET label=?,url=?,parent_id=? WHERE id=?",
                 (label, url, parent_id, item_id))
    conn.commit(); conn.close()

def delete_menu_item(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM menu_items WHERE id=? OR parent_id=?", (item_id, item_id))
    conn.commit(); conn.close()

def reorder_menu_items(orden: list):
    conn = get_db()
    for i, iid in enumerate(orden):
        conn.execute("UPDATE menu_items SET orden=? WHERE id=?", (i, iid))
    conn.commit(); conn.close()


# ── Editor de plantillas — Slider ─────────────────────────────────────────────

def get_slider_data(plantilla_id: int) -> dict:
    conn = get_db()
    p = conn.execute("SELECT slider_config FROM plantillas WHERE id=?", (plantilla_id,)).fetchone()
    slides = conn.execute(
        "SELECT * FROM slider_slides WHERE plantilla_id=? ORDER BY orden", (plantilla_id,)
    ).fetchall()
    conn.close()
    import json
    cfg = {}
    if p and p['slider_config']:
        try: cfg = json.loads(p['slider_config'])
        except: pass
    return {'config': cfg, 'slides': [dict(s) for s in slides]}

def save_slider_config(plantilla_id: int, config: dict):
    import json
    conn = get_db()
    conn.execute("UPDATE plantillas SET slider_config=? WHERE id=?",
                 (json.dumps(config, ensure_ascii=False), plantilla_id))
    conn.commit(); conn.close()

def create_slide(plantilla_id: int, imagen_url: str, titulo: str, subtitulo: str, orden: int) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO slider_slides (plantilla_id,imagen_url,titulo,subtitulo,orden) VALUES (?,?,?,?,?)",
        (plantilla_id, imagen_url, titulo, subtitulo, orden)
    )
    iid = cur.lastrowid; conn.commit(); conn.close()
    return iid

def update_slide(slide_id: int, imagen_url: str, titulo: str, subtitulo: str, orden: int):
    conn = get_db()
    conn.execute("UPDATE slider_slides SET imagen_url=?,titulo=?,subtitulo=?,orden=? WHERE id=?",
                 (imagen_url, titulo, subtitulo, orden, slide_id))
    conn.commit(); conn.close()

def delete_slide(slide_id: int):
    conn = get_db()
    conn.execute("DELETE FROM slider_slides WHERE id=?", (slide_id,))
    conn.commit(); conn.close()


# ── Editor de plantillas — Footer ─────────────────────────────────────────────

def get_footer_config(plantilla_id: int) -> dict:
    import json
    conn = get_db()
    p = conn.execute("SELECT footer_config FROM plantillas WHERE id=?", (plantilla_id,)).fetchone()
    conn.close()
    if p and p['footer_config']:
        try: return json.loads(p['footer_config'])
        except: pass
    return {'columnas': 3, 'bg_color': '#012840', 'copyright': '© 2025 Mi Empresa.', 'cols': []}

def save_footer_config(plantilla_id: int, config: dict):
    import json
    conn = get_db()
    conn.execute("UPDATE plantillas SET footer_config=? WHERE id=?",
                 (json.dumps(config, ensure_ascii=False), plantilla_id))
    conn.commit(); conn.close()


# ── Editor de plantillas — Custom Code ───────────────────────────────────────

def get_custom_codes(plantilla_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM custom_code WHERE plantilla_id=? ORDER BY id", (plantilla_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_custom_code(plantilla_id: int, tipo: str, inject_in: str, seccion_target, codigo: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO custom_code (plantilla_id,tipo,inject_in,seccion_target,codigo) VALUES (?,?,?,?,?)",
        (plantilla_id, tipo, inject_in, seccion_target, codigo)
    )
    iid = cur.lastrowid; conn.commit(); conn.close()
    return iid

def toggle_custom_code(code_id: int):
    conn = get_db()
    conn.execute("UPDATE custom_code SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END WHERE id=?", (code_id,))
    conn.commit(); conn.close()

def delete_custom_code(code_id: int):
    conn = get_db()
    conn.execute("DELETE FROM custom_code WHERE id=?", (code_id,))
    conn.commit(); conn.close()


# ── Editor de plantillas — Secciones habilitadas ─────────────────────────────

def get_secciones_habilitadas(plantilla_id: int) -> list:
    import json
    conn = get_db()
    p = conn.execute("SELECT secciones_habilitadas FROM plantillas WHERE id=?", (plantilla_id,)).fetchone()
    conn.close()
    if p and p['secciones_habilitadas']:
        try: return json.loads(p['secciones_habilitadas'])
        except: pass
    return []

def save_secciones_habilitadas(plantilla_id: int, secciones: list):
    import json
    conn = get_db()
    conn.execute("UPDATE plantillas SET secciones_habilitadas=? WHERE id=?",
                 (json.dumps(secciones, ensure_ascii=False), plantilla_id))
    conn.commit(); conn.close()


# ── Estilos de plantilla ──────────────────────────────────────────────────────

_ESTILOS_DEFAULT = {
    'color_primary': '#185FA5', 'color_secondary': '#0A0F1E',
    'color_accent': '#0088CC', 'color_neutral': '#E8EAF0',
    'font_heading': 'system-ui, sans-serif', 'font_body': 'system-ui, sans-serif',
    'font_size_h1': 48, 'font_size_h2': 32, 'font_size_body': 16,
    'line_height': 1.6, 'radius_btn': 8, 'radius_card': 12, 'radius_input': 6,
    'section_padding': 80, 'gap_elements': 24, 'modo_tema': 'dark',
    'efectos_json': '{"entrada":true,"hover_btn":true,"parallax":false,"cursor":false,"velocidad":"400ms","easing":"ease-out"}',
    'header_json': '{}', 'hero_json': '{}', 'footer_json': '{}',
    'movil_json': '{"h1":32,"padding":40,"hamburguesa":true}',
    'preset_activo': 'oceano-oscuro',
    'layout_json': '{"hero":"fullscreen","services":"grid","projects":"grid","team":"cards"}',
    'defaults_json': '{}',
}

def get_estilos(plantilla_id: int) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM plantilla_estilos WHERE plantilla_id=?", (plantilla_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {**_ESTILOS_DEFAULT, 'plantilla_id': plantilla_id, 'id': None}

def upsert_estilos(plantilla_id: int, campos: dict):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM plantilla_estilos WHERE plantilla_id=?", (plantilla_id,)
    ).fetchone()
    if existing:
        sets = ', '.join(f"{k}=?" for k in campos)
        conn.execute(f"UPDATE plantilla_estilos SET {sets} WHERE plantilla_id=?",
                     list(campos.values()) + [plantilla_id])
    else:
        full = {**_ESTILOS_DEFAULT, **campos, 'plantilla_id': plantilla_id}
        cols = ', '.join(full.keys())
        vals = ', '.join('?' for _ in full)
        conn.execute(f"INSERT INTO plantilla_estilos ({cols}) VALUES ({vals})", list(full.values()))
    conn.commit()
    conn.close()


# ── Planes ────────────────────────────────────────────────────────────────────

def listar_planes() -> list:
    """Todos los planes activos."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM planes WHERE activo=1 ORDER BY precio").fetchall()
    conn.close()
    return rows


def listar_todos_planes() -> list:
    """Todos los planes (para panel admin)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM planes ORDER BY precio").fetchall()
    conn.close()
    return rows


def obtener_plan(plan_id: int):
    """Un plan por id."""
    conn = get_db()
    row = conn.execute("SELECT * FROM planes WHERE id=?", (plan_id,)).fetchone()
    conn.close()
    return row


def obtener_plan_por_clave(clave: str):
    """Un plan por clave."""
    conn = get_db()
    row = conn.execute("SELECT * FROM planes WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row


def asignar_plan_cliente(cliente_id: int, plan_id: int):
    """Actualiza plan_id del cliente."""
    conn = get_db()
    conn.execute("UPDATE clientes SET plan_id=? WHERE id=?", (plan_id, cliente_id))
    conn.commit()
    conn.close()


def plantillas_por_plan(tipo_acceso: str) -> list:
    """Plantillas que corresponden al tipo de acceso del plan."""
    plan = str(tipo_acceso or '').strip().lower()
    plan_map = {
        'basico': 'landing',
        'basic': 'landing',
        'landing': 'landing',
        'corporativo': 'web5',
        'corporate': 'web5',
        'web5': 'web5',
        'premium': 'ambos',
        'ambos': 'ambos',
    }
    tipo = plan_map.get(plan)

    conn = get_db()
    if tipo == 'ambos':
        rows = conn.execute(
            "SELECT * FROM plantillas WHERE activo=1 ORDER BY id"
        ).fetchall()
    elif tipo in ('landing', 'web5'):
        rows = conn.execute(
            "SELECT * FROM plantillas WHERE activo=1 AND tipo=? ORDER BY id",
            (tipo,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM plantillas WHERE activo=1 ORDER BY id"
        ).fetchall()
    conn.close()
    return rows


def registrar_cliente_publico(email: str, password_hash: str, nombre: str, plan_id: int) -> int:
    """Registra un usuario vía formulario público. activo=0 — pendiente de activación."""
    conn = get_db()
    # Verifica si ya existe por email en usuarios (CMS)
    existing = conn.execute(
        "SELECT id FROM usuarios WHERE email=?", (email.lower().strip(),)
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError('email_exists')
    cur = conn.execute(
        "INSERT INTO usuarios (email, password, nombre, activo) VALUES (?, ?, ?, 0)",
        (email.lower().strip(), password_hash, nombre.strip())
    )
    uid = cur.lastrowid
    conn.commit()
    conn.close()
    return uid


def activar_usuario(uid: int):
    """Activa la cuenta de un usuario."""
    conn = get_db()
    conn.execute("UPDATE usuarios SET activo=1 WHERE id=?", (uid,))
    conn.commit()
    conn.close()


def listar_usuarios_pendientes() -> list:
    """Usuarios con activo=0 pendientes de activación."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM usuarios WHERE activo=0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def contar_clientes_por_plan() -> dict:
    """Devuelve {plan_id: count} de usuarios activos por plan (tabla usuarios, campo plan)."""
    conn = get_db()
    # contamos por plan desde la tabla usuarios usando la columna 'plan'
    rows = conn.execute(
        "SELECT plan, COUNT(*) as n FROM usuarios WHERE activo=1 GROUP BY plan"
    ).fetchall()
    conn.close()
    return {r['plan']: r['n'] for r in rows}


def toggle_plan(plan_id: int):
    """Activa o desactiva un plan."""
    conn = get_db()
    conn.execute(
        "UPDATE planes SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END WHERE id=?",
        (plan_id,)
    )
    conn.commit()
    conn.close()


def crear_plan(clave: str, nombre: str, descripcion: str,
               precio: float, tipo_acceso: str, max_sitios: int) -> int:
    """Crea un plan nuevo."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO planes (clave, nombre, descripcion, precio, tipo_acceso, max_sitios) VALUES (?,?,?,?,?,?)",
        (clave.strip().lower(), nombre.strip(), descripcion.strip(), precio, tipo_acceso, max_sitios)
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def obtener_usuario_por_email_cualquier_estado(email: str):
    """Busca usuario activo O inactivo (para login con mensaje de pendiente)."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email=?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return row


def get_layout(plantilla_id: int) -> dict:
    """Retorna el dict de layout desde plantilla_estilos.layout_json."""
    import json as _json
    conn = get_db()
    row = conn.execute(
        "SELECT layout_json FROM plantilla_estilos WHERE plantilla_id=?", (plantilla_id,)
    ).fetchone()
    conn.close()
    _default = {"hero": "fullscreen", "services": "grid", "projects": "grid", "team": "cards"}
    if row and row['layout_json']:
        try:
            return _json.loads(row['layout_json'])
        except Exception:
            pass
    return _default
