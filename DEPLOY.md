# DEPLOY — Plantillas Web RD

## Opciones de hosting

| Opción | Costo | Dificultad | Recomendado para |
|--------|-------|------------|-----------------|
| **PythonAnywhere** (free tier) | $0/mes | Bajo | Demo / staging |
| **Railway** | ~$5/mes | Bajo | Producción pequeña |
| **VPS Ubuntu** (DigitalOcean/Vultr) | ~$6/mes | Medio | Producción escalable |
| Banahosting (shared) | ❌ | — | No soporta Flask |

---

## Opción A — PythonAnywhere (más fácil, gratis)

1. Crear cuenta en pythonanywhere.com
2. En el panel → "Bash console":
   ```bash
   git clone <tu-repo> ~/plantillas-web
   cd ~/plantillas-web/admin
   pip3 install -r requirements.txt --user
   cp .env.example .env
   # Editar .env con tu SECRET_KEY real
   nano .env
   python3 -c "import app; print('OK')"
   ```
3. Web tab → Add new web app → Manual config → Python 3.10
4. WSGI file: reemplazar contenido con:
   ```python
   import sys
   sys.path.insert(0, '/home/TU_USUARIO/plantillas-web/admin')
   from app import app as application
   ```
5. Static files: URL `/static/` → Directory `/home/TU_USUARIO/plantillas-web/admin/static`
6. Reload → listo

---

## Opción B — VPS Ubuntu + Nginx (producción real)

### 1. Preparar el servidor

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv nginx
```

### 2. Clonar y configurar

```bash
git clone <tu-repo> /srv/plantillas-web
cd /srv/plantillas-web/admin
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # <-- pon tu SECRET_KEY real aquí
python3 -c "import app; print('OK')"
```

### 3. Systemd service

Crear `/etc/systemd/system/plantillas-web.service`:

```ini
[Unit]
Description=Plantillas Web RD
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/plantillas-web/admin
EnvironmentFile=/srv/plantillas-web/admin/.env
ExecStart=/srv/plantillas-web/admin/venv/bin/gunicorn app:app \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --threads 2 \
    --timeout 60 \
    --access-logfile /var/log/plantillas-web/access.log \
    --error-logfile /var/log/plantillas-web/error.log
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/plantillas-web
sudo chown www-data /var/log/plantillas-web
sudo systemctl enable plantillas-web
sudo systemctl start plantillas-web
```

### 4. Nginx config

Crear `/etc/nginx/sites-available/plantillas-web`:

```nginx
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;

    # Archivos estáticos servidos por Nginx (más rápido que Flask)
    location /static/ {
        alias /srv/plantillas-web/admin/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Todo lo demás va a Gunicorn
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        client_max_body_size 10M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/plantillas-web /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. HTTPS con Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com
```

---

## Checklist pre-deploy

- [ ] `.env` tiene `SECRET_KEY` real (no la de desarrollo)
- [ ] `FLASK_ENV=production` en `.env`
- [ ] `python3 -c "import app; print('OK')"` pasa sin errores
- [ ] Carpeta `static/uploads/` tiene permisos de escritura
- [ ] `plantillas.db` en ubicación con backup automático
- [ ] Firewall: solo puertos 80, 443, 22 abiertos

---

## Variables de entorno requeridas

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Clave de sesión Flask (obligatoria) | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | Entorno (development/production) | `production` |
