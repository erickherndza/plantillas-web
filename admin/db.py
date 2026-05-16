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

    # Migración: columna campos_schema en plantillas (idempotente)
    try:
        conn.execute("ALTER TABLE plantillas ADD COLUMN campos_schema TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass  # ya existe

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


def crear_sitio(usuario_id: int, plantilla_id: int, slug: str, nombre: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO sitios (usuario_id, plantilla_id, slug, nombre) VALUES (?, ?, ?, ?)",
        (usuario_id, plantilla_id, slug.lower().strip(), nombre.strip())
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
