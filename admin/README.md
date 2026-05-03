# Admin — Panel de Plantillas Web RD

## Instalar
```bash
cd ~/plantillas-web/admin
pip3 install -r requirements.txt --break-system-packages
```

## Correr
```bash
python3 app.py
# Abre: http://localhost:5002
```

## Usuarios de prueba
| Usuario | Contraseña | Acceso |
|---|---|---|
| admin | admin2026 | Todas las plantillas |
| demo_medico | demo123 | Solo doctores |
| demo_arq | demo123 | Solo arquitectura |

## Publicar cambios
Automático al guardar desde el panel (git push → Cloudflare Pages ~30 seg).

## Notas
- `clientes.json` está en `.gitignore` — no se sube a GitHub
- Puerto 5002 para no colisionar con otros proyectos (TecnoAuladom: 5001)
