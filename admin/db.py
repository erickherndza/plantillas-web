"""
db.py — Capa de datos para el panel admin de plantillas-web
Tablas:
  clientes  — usuarios del panel (admin y clientes finales)
  accesos   — qué plantillas puede editar cada cliente (many-to-many)
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
        CREATE TABLE IF NOT EXISTS clientes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario  TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            nombre   TEXT    DEFAULT '',
            plan     TEXT    DEFAULT 'landing',   -- 'admin' | 'landing' | 'web5'
            activo   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS accesos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            plantilla_clave TEXT    NOT NULL,
            UNIQUE(cliente_id, plantilla_clave)
        );
    """)
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
