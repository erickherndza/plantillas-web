"""
migrar.py — Script de migración única: clientes.json → SQLite
Ejecutar UNA sola vez:  python3 migrar.py
Si la DB ya tiene datos no vuelve a insertar (INSERT OR IGNORE).
"""

import json
import os
import sys

# Asegurar que db.py sea importable desde este directorio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import init_db, get_db

CLIENTES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clientes.json')


def migrar():
    # 1. Crear tablas si no existen
    init_db()
    print("[migrar] Tablas verificadas/creadas.")

    # 2. Leer clientes.json
    if not os.path.exists(CLIENTES_JSON):
        print(f"[migrar] No se encontró {CLIENTES_JSON}. Nada que migrar.")
        return

    with open(CLIENTES_JSON, 'r', encoding='utf-8') as f:
        clientes = json.load(f)

    conn = get_db()
    migrados = 0
    omitidos = 0

    for usuario, datos in clientes.items():
        # Verificar si ya existe
        existe = conn.execute(
            "SELECT id FROM clientes WHERE usuario = ?", (usuario,)
        ).fetchone()

        if existe:
            print(f"  [omitido] '{usuario}' ya existe en la DB.")
            omitidos += 1
            continue

        # Insertar cliente
        cur = conn.execute(
            "INSERT INTO clientes (usuario, password, nombre, plan) VALUES (?, ?, ?, ?)",
            (
                usuario,
                datos.get('password', ''),
                datos.get('nombre', usuario),
                datos.get('plan', 'landing'),
            )
        )
        cliente_id = cur.lastrowid

        # Insertar accesos
        for plantilla_clave in datos.get('plantillas', []):
            conn.execute(
                "INSERT OR IGNORE INTO accesos (cliente_id, plantilla_clave) VALUES (?, ?)",
                (cliente_id, plantilla_clave)
            )
            print(f"  [acceso] '{usuario}' → '{plantilla_clave}'")

        print(f"  [ok] '{usuario}' (plan={datos.get('plan', 'landing')}) migrado con id={cliente_id}.")
        migrados += 1

    conn.commit()
    conn.close()

    print(f"\n[migrar] Listo. {migrados} cliente(s) migrado(s), {omitidos} omitido(s).")
    print("[migrar] Puedes borrar clientes.json cuando confirmes que todo funciona.")


if __name__ == '__main__':
    migrar()
