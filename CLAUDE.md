# CLAUDE.md — plantillas-web CMS
# Constructor de sitios web para pymes RD — Erick Hernández
# Leer COMPLETO al inicio de cada sesión antes de cualquier acción.

---

## PROTOCOLO DE INICIO DE SESIÓN

1. Leer este archivo completo (ESTADO ACTUAL primero, luego ROADMAP)
2. Verificar que el panel admin levanta:
   `cd ~/plantillas-web/admin && python3 app.py` (puerto 5002)
3. Verificar importación sin errores:
   `cd ~/plantillas-web/admin && python3 -c "import app; print('OK')"`
4. Abrir con: "Retomamos desde [último_hecho]. Próximo paso: [top_pendiente]. ¿Arranco?"
5. Si hay error de importación → NO continuar hasta resolverlo

---

## VISIÓN DEL PRODUCTO

Un CMS SaaS que permite:

| Actor | Puede hacer |
|-------|------------|
| **Admin** | Crear y editar plantillas (landing + web 5 páginas), gestionar usuarios |
| **Usuario** | Registrarse, elegir plantilla, crear su sitio, personalizarlo |

### Personalización que debe soportar el sistema
- Logo (upload de imagen)
- Menú: renombrar ítems, reordenar, cambiar destino de enlace
- Colores: primario, secundario, fondo del header, fondo del footer, texto
- Tipografía: fuente del título, fuente del cuerpo (lista de Google Fonts)
- Hero: imagen de fondo, título, subtítulo, botón CTA
- Secciones del cuerpo: slider (múltiples imágenes), tarjetas de servicios, equipo, testimonios
- Páginas de una web 5: Inicio · Nosotros · Servicios · Proyectos · Contacto

---

## ESTADO ACTUAL (2026-05-16)

### Lo que existe y funciona
| Componente | Estado | Observación |
|------------|--------|-------------|
| Panel admin Flask (puerto 5002) | Funcional | Auth, CRUD clientes, editor |
| DB: clientes + accesos | Funcional | SQLite WAL |
| Editor de campos + repeaters | Funcional | BeautifulSoup sobre HTML |
| Upload de imágenes | Funcional | `/static/uploads/<plantilla_id>/` |
| Preview local `/local/<id>/` | Funcional | Sirve HTML desde disco |
| Deploy vía git push | Funcional | Cloudflare Workers (~30s) |
| Plantilla "arquitectura" | Completa | Landing page 1 sección |
| Plantilla "doctores" | Completa | Landing page 1 sección |

### Flaw crítico de la arquitectura actual
El sistema actual edita archivos HTML en disco con BeautifulSoup y hace git push.
**Esto rompe la multi-tenancia:** si dos usuarios eligen la misma plantilla "arquitectura",
ambos editan el MISMO `index.html` y se pisarían mutuamente.

El modelo actual funciona para 1 cliente por plantilla. NO escala a N clientes por plantilla.
Este es el problema central a resolver antes de seguir construyendo.

---

## DECISIÓN DE ARQUITECTURA — LEER ANTES DE CODEAR

### El problema raíz
Customizaciones guardadas EN el HTML (en disco) = no hay aislamiento por usuario.

### Tres opciones evaluadas

**Opción A — DB-first con renderizado dinámico (RECOMENDADA)**
- Cada customización se guarda en SQLite, no en el HTML
- Las plantillas son Jinja2 con variables: `{{ config.color_primario }}`
- Flask renderiza el sitio de cada usuario en tiempo real: `/s/<slug>/`
- Pros: Multi-tenancia real, cambios instantáneos, sin git por edición, limpio
- Contras: Hay que convertir los HTML actuales a Jinja2

**Opción B — Copia de archivos por usuario**
- Al crear un sitio, copiar los archivos de la plantilla a `/sites/<slug>/`
- El parser de BeautifulSoup edita la copia del usuario
- Deploy por usuario a Cloudflare (carpetas distintas)
- Pros: Reutiliza parser.py sin cambios
- Contras: El repo de git crece por cada usuario, deploy complejo, no escala

**Opción C — JSON config por usuario + Jinja2**
- Similar a A pero la config es un JSON por sitio en la DB
- La plantilla Jinja2 recibe el JSON y lo inyecta como variables CSS + contenido
- Para sliders y repeaters: tabla `secciones_contenido` con datos JSON
- Pros: Más simple que A, evita schema rígido, flexible para campos nuevos
- Contras: Menos tipado que A

### DECISIÓN TOMADA: Opción A (DB-first)
Razón: Es la única que escala bien, elimina la dependencia de git para contenido,
y permite preview instantáneo sin recargar desde disco.
La conversión de HTML → Jinja2 es trabajo de una sesión por plantilla.

---

## ARQUITECTURA OBJETIVO

```
~/plantillas-web/
├── admin/
│   ├── app.py              ← Panel admin (gestión de plantillas + usuarios)
│   ├── db.py               ← Capa de datos — EXTENDER con nuevas tablas
│   ├── plantillas.db       ← SQLite WAL (datos de todos los sitios)
│   ├── templates/          ← Jinja2 del panel admin
│   └── static/
│       └── uploads/        ← Logos y fotos subidas por usuarios
│
├── templates_jinja/        ← Plantillas Jinja2 (base de los sitios)
│   ├── arquitectura/
│   │   ├── base.html       ← Layout compartido (header, nav, footer)
│   │   ├── inicio.html
│   │   ├── nosotros.html
│   │   ├── servicios.html
│   │   ├── proyectos.html
│   │   └── contacto.html
│   └── doctores/
│       └── ... (misma estructura)
│
└── site_app/               ← Mini-app Flask que sirve los sitios de usuarios
    └── app.py              ← Rutas: /s/<slug>/ y /s/<slug>/<pagina>/
```

### Cómo se sirve un sitio de usuario
```
Usuario visita: /s/clinica-san-rafael/servicios/
  → site_app busca el sitio por slug
  → carga su configuracion_sitio desde DB (colores, fuentes, textos)
  → carga sus secciones_contenido (slider, servicios, equipo...)
  → renderiza templates_jinja/doctores/servicios.html con ese contexto
  → devuelve HTML personalizado al visitante
```

---

## SCHEMA DE BASE DE DATOS (objetivo)

```sql
-- Definición de plantillas disponibles (solo admin puede crear)
CREATE TABLE plantillas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    clave        TEXT UNIQUE NOT NULL,     -- 'arquitectura', 'doctores', 'legal'
    nombre       TEXT NOT NULL,            -- nombre legible
    tipo         TEXT DEFAULT 'landing',   -- 'landing' | 'web5'
    descripcion  TEXT DEFAULT '',
    preview_img  TEXT DEFAULT '',          -- URL imagen de preview
    activo       INTEGER DEFAULT 1
);

-- Usuarios del CMS (clientes finales)
CREATE TABLE usuarios (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT UNIQUE NOT NULL,
    password     TEXT NOT NULL,            -- bcrypt hash (werkzeug)
    nombre       TEXT DEFAULT '',
    plan         TEXT DEFAULT 'landing',   -- 'landing' | 'web5'
    activo       INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Cada sitio creado por un usuario
CREATE TABLE sitios (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    plantilla_id INTEGER NOT NULL REFERENCES plantillas(id),
    slug         TEXT UNIQUE NOT NULL,     -- URL del sitio: /s/<slug>/
    nombre       TEXT NOT NULL,            -- nombre del negocio
    dominio_custom TEXT DEFAULT '',        -- para el futuro
    activo       INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Valores de configuración (colores, fuentes, textos, logos)
CREATE TABLE configuracion_sitio (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sitio_id INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
    clave    TEXT NOT NULL,
    valor    TEXT NOT NULL DEFAULT '',
    UNIQUE(sitio_id, clave)
);

-- Contenido repetible: slider, servicios, proyectos, equipo, testimonios
CREATE TABLE secciones_contenido (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sitio_id INTEGER NOT NULL REFERENCES sitios(id) ON DELETE CASCADE,
    seccion  TEXT NOT NULL,               -- 'slider', 'servicios', 'equipo', etc.
    orden    INTEGER DEFAULT 0,
    datos    TEXT NOT NULL DEFAULT '{}'   -- JSON con los campos del item
);

-- Accesos admin (tabla existente — se mantiene para el panel admin)
-- clientes tabla existente se migra a usuarios con plan='admin'
```

### Claves de configuracion_sitio
```
color_primario      → #0bb180
color_secundario    → #024959
color_header_bg     → #ffffff
color_footer_bg     → #1a202c
color_texto         → #334155
fuente_titulo       → Montserrat
fuente_cuerpo       → Open Sans
logo_url            → /static/uploads/<sitio_id>/logo.png
hero_titulo         → Mi Empresa
hero_subtitulo      → Tu descripción aquí
hero_imagen         → /static/uploads/<sitio_id>/hero.jpg
hero_cta_texto      → Contáctanos
hero_cta_href       → #contacto
menu_item_1_texto   → Inicio
menu_item_1_href    → #inicio
... (hasta 7 ítems)
nosotros_descripcion → Somos...
nosotros_mision     → ...
nosotros_vision     → ...
contacto_direccion  → ...
contacto_telefono   → ...
contacto_email      → ...
```

---

## ROADMAP DE DESARROLLO

### FASE 1 — Fundamento multi-usuario (sin esto nada más funciona) ✅ COMPLETA
- [x] 1.1 Extender db.py con tablas: plantillas, usuarios, sitios, configuracion_sitio, secciones_contenido
- [x] 1.2 Auth de usuarios: /registro, /entrar, /salir (separado del auth admin en /login)
- [ ] 1.3 Migrar tabla `clientes` existente → tabla `usuarios` (pendiente — clientes.json legacy)
- [x] 1.4 Flujo de onboarding: usuario se registra → elige plantilla → crea su sitio (slug)

### FASE 2 — Renderizado de sitios ✅ COMPLETA (arquitectura)
- [x] 2.1 Ruta `/s/<slug>/` y `/s/<slug>` en admin/app.py (sin app separada — más simple)
- [x] 2.2 Plantilla "arquitectura" convertida a Jinja2 (admin/templates/sites/arquitectura/index.html)
- [x] 2.3 CSS vars inyectadas desde DB: --c-primary, --c-dark, --c-text en bloque <style>
- [x] 2.4 Secciones dinámicas: servicios, proyectos, equipo con loops Jinja2
- [ ] 2.5 Plantilla "doctores" — pendiente (misma estructura, diferente contenido)

### FASE 3 — Editor de usuario ✅ COMPLETA
- [x] 3.1 /mi-panel muestra sitios con botón "Personalizar" activo
- [x] 3.2 Editor de apariencia: 3 color pickers con preview en tiempo real
- [x] 3.3 Editor de marca: logo upload (AJAX a /upload-sitio/<id>), nombre del negocio
- [ ] 3.4 Editor de menú — pendiente (menú hardcodeado en Jinja2 por ahora)
- [x] 3.5 Editor de hero: imagen (upload+URL), eyebrow, título, subtítulo, 2 CTAs
- [x] 3.6 Editor de secciones: servicios/proyectos/equipo con add/remove dinámico + upload por item
- [x] 3.7 Preview: botón "Ver sitio" abre /s/<slug>/ en nueva pestaña (cambios instantáneos)
- [x] Naming convention: cfg__clave para config, rep__seccion__idx__campo para repeaters
- [x] Test completo: GET 200, POST guardado en DB, sitio renderiza nuevos valores

### FASE 4 — Web de 5 páginas (plan web5) ✅ COMPLETA
- [x] 4.1 Diseñar layout base con navegación entre 5 páginas (no one-page)
- [x] 4.2 Plantilla Jinja2 con inicio/nosotros/servicios/proyectos/contacto
- [x] 4.3 Editor por página: contenido independiente por sección
- [x] 4.4 Galería de proyectos: grid de fotos con título y descripción + filtros por categoría
- [x] 4.5 Formulario de contacto funcional (AJAX JSON → guardar en mensajes_contacto)

### FASE 5 — Admin: creador de plantillas ✅ COMPLETA
- [x] 5.1 Panel admin CRUD de plantillas: /admin/plantillas (listar, crear, editar, toggle activo)
- [x] 5.2 Schema de campos por plantilla: JSON {secciones:[]} en columna campos_schema — editor lo respeta
- [ ] 5.3 Upload de plantilla HTML base desde el panel (pospuesto — plantillas viven en el repo)
- [x] 5.4 Vista previa: enlace a /s/<slug>/ desde admin_plantillas

### FASE 6 — Producción ✅ COMPLETA
- [x] 6.1 Hash de contraseñas: admin login re-hashea contraseñas planas en caliente — DT-001
- [x] 6.2 SECRET_KEY desde .env (lector manual sin dependencias extra) — DT-002
- [x] 6.3 Magic bytes en uploads: verifica firma real del archivo (PNG/JPG/WebP/GIF) — DT-003
- [x] 6.4 Rate limiting: 5 fallos → bloqueo 15 min por IP, aplica a /login y /entrar — DT-004
- [x] 6.5 Deploy: DEPLOY.md con PythonAnywhere + VPS+Nginx+Gunicorn+Certbot — DT-005

---

## LO QUE SE CONSERVA DEL CÓDIGO ACTUAL

| Componente | Decisión | Razón |
|-----------|----------|-------|
| `admin/app.py` estructura Flask | Conservar y extender | Rutas auth admin, CRUD clientes funcionales |
| `admin/db.py` `get_db()`, `init_db()` | Conservar y extender | Patrón limpio, agregar nuevas tablas |
| `admin/templates/` login, dashboard | Conservar | UI del panel admin funciona |
| `admin/static/admin.css` | Conservar | Estilos del panel |
| `admin/image_processor.py` | Conservar | Upload + resize de imágenes sigue siendo útil |
| HTML de arquitectura + doctores | Convertir a Jinja2 | El diseño es bueno, solo cambiar syntax |
| `parser.py` | Descartar | Ya no se editan archivos HTML directamente |
| `site-schema.json` | Descartar | Reemplazado por tabla `plantillas` en DB |
| `git_push()` | Descartar para contenido | Solo se usa para deploy de código, no de datos |

---

## COMANDOS CLAVE

### Iniciar panel admin (actual)
```bash
cd ~/plantillas-web/admin
python3 app.py
# → http://localhost:5002
```

### Verificar importación
```bash
cd ~/plantillas-web/admin
python3 -c "import app; print('OK')"
```

### Consultar clientes/usuarios actuales
```bash
cd ~/plantillas-web/admin
python3 -c "from db import listar_clientes; [print(dict(r)) for r in listar_clientes()]"
```

### Backup de DB antes de cambios
```bash
cp ~/plantillas-web/admin/plantillas.db ~/plantillas-web/admin/plantillas_$(date +%Y%m%d_%H%M).db
```

---

## WORKFLOW DE CAMBIOS — SECUENCIA OBLIGATORIA

```
1. Leer el archivo ANTES de editar (nunca editar a ciegas)
2. Backup de plantillas.db si el cambio toca schema o migración
3. Hacer el cambio mínimo (un archivo a la vez)
4. Verificar importación sin errores
5. Probar el flujo específico en el browser
6. Actualizar LOG DE SESIONES y ESTADO DE ROADMAP en este CLAUDE.md
7. Commit descriptivo
```

**Señales de parar:**
- Fix tiene +20 líneas → problema de diseño más profundo
- Arreglar X rompe Y → solución en lugar equivocado
- Mismo error 3 veces → cambiar enfoque

---

## REGISTRO DE ERRORES — LECCIONES APRENDIDAS

### E-001: Repeaters — nombres de campos del form
**Error:** Datos de repeater no llegaban al servidor.
**Causa raíz:** Los campos se nombran `rep__<rep_id>__<idx>__<campo_id>`. Cualquier variación rompe el parser.
**Fix:** Imprimir `list(request.form.keys())` en el POST para confirmar los nombres antes de parsear.
**Prevención:** Al agregar repeater nuevo, verificar keys antes de parsear.

### E-002: BeautifulSoup selector no coincide con HTML real
**Error:** `aplicar_cambios()` no modifica nada aunque el campo existe.
**Causa raíz:** Selector CSS en schema no coincide exactamente con HTML (clases extra, nesting diferente).
**Fix:** `soup.select(selector)` en sesión Python para verificar antes de usar en schema.
**Prevención:** Verificar cada selector contra el HTML actual antes de agregarlo al schema.

### E-003: git_push() falla silenciosamente
**Error:** Flash muestra "Guardado localmente" en vez de éxito.
**Causa raíz:** Credenciales git no disponibles o remote mal configurado.
**Fix:** `git remote -v` para verificar. `git config credential.helper store`.
**Prevención:** Probar `git push` manual una vez antes de confiar en git_push().

### E-004: Multi-tenancia rota — arquitectura actual (crítico)
**Error:** Todos los usuarios de la misma plantilla editan el mismo HTML.
**Causa raíz:** Customizaciones guardadas en archivo en disco, no en DB.
**Fix:** Migrar a arquitectura DB-first (Fase 1 del roadmap).
**Prevención:** No agregar más features sobre el sistema BeautifulSoup actual — resolver esto primero.

### E-005: Conflicto de nombres — función de ruta vs función de DB
**Error:** `crear_sitio() takes 0 positional arguments but 4 were given`
**Causa raíz:** La ruta Flask `def crear_sitio()` shadea el import `from db import crear_sitio`. Dentro de la ruta, llamar a `crear_sitio(args)` ejecuta la función Flask, no la de DB.
**Fix:** Importar con alias: `from db import crear_sitio as db_crear_sitio`.
**Prevención:** Cuando un nombre de ruta Flask coincide con un helper de DB, SIEMPRE importar el helper con alias `db_` al inicio del archivo.

---

## DEUDAS TÉCNICAS

| ID | Deuda | Riesgo | Cuándo |
|----|-------|--------|--------|
| DT-001 | Contraseñas texto plano en DB | Alto | Antes de clientes reales |
| DT-002 | SECRET_KEY hardcodeada | Medio | Antes de producción |
| DT-003 | Sin validación magic bytes en uploads | Medio | Antes de producción |
| DT-004 | Sin rate limiting en login | Medio | Antes de producción |
| DT-005 | Sin hash en passwords admin | Alto | Fase 6 |

---

## LOG DE SESIONES

### 2026-05-16
- CLAUDE.md refactorizado con visión completa del producto
- Análisis de arquitectura: detectado flaw crítico multi-tenancia
- Decisión: DB-first (Opción A)
- Fase 1 completada:
  - db.py extendido: 5 tablas nuevas + 15 funciones (usuarios, sitios, config, secciones)
  - Seed automático de 2 plantillas (arquitectura, doctores)
  - Auth usuarios con werkzeug hash: /registro, /entrar, /salir
  - Onboarding: crear_sitio con selector de plantilla, nombre y slug (con validación)
  - Config inicial por defecto al crear sitio (colores, fuentes, textos hero)
  - 4 templates HTML: registro, entrar, mi_panel, crear_sitio
  - Session keys separadas de admin: uid, u_email, u_nombre
- Fase 2 completada (arquitectura):
  - Ruta /s/<slug>/ en app.py — renderiza Jinja2 + config desde DB
  - Template arquitectura convertido (admin/templates/sites/arquitectura/index.html)
  - CSS vars dinámicas: color_primario, color_footer_bg, color_texto
  - Secciones dinámicas: servicios, proyectos, equipo
  - CSS/JS copiados a admin/static/sites/arquitectura/
  - Test completo: 200 OK, nombre/servicios/equipo/color verificados
- Fase 3 completada:
  - /editar/<sitio_id> — GET carga editor, POST guarda cfg__ y rep__ a DB
  - /upload-sitio/<sitio_id> — upload AJAX de imágenes por sitio
  - editor_sitio.html: 8 secciones (apariencia, marca, hero, nosotros, servicios, proyectos, equipo, contacto)
  - JS inline: nav secciones, color picker live, upload logo/hero/repeater, add/remove repeater, spinner
  - mi_panel.html: botón "Personalizar" activo → /editar/<sitio_id>
  - Test: POST guarda en DB, /s/<slug>/ renderiza nuevos valores inmediatamente
- Fase 4 completada:
  - base.html: layout compartido con navbar 5 páginas, active state, logo dinámico, footer
  - inicio.html: hero + highlights (primeros 3 servicios) + nosotros preview + CTA
  - nosotros.html: descripción + MVV cards (misión, visión, valores) + team grid
  - servicios.html: intro + services grid con imagen/icono/precio opcionales
  - proyectos.html: portfolio grid con filtros por categoría (JS initPortfolioFilters)
  - contacto.html: info + formulario AJAX (fetch JSON → /s/<slug>/enviar-contacto)
  - style.css extendido: MVV grid, team grid, services grid, portfolio grid, contact layout
  - script.js extendido: initPortfolioFilters() para filtrado dinámico
  - enviar_contacto() actualizado: acepta JSON (fetch) y form-data
- Fase 5 completada:
  - db.py: columna campos_schema en plantillas (migración idempotente con ALTER TABLE)
  - db.py: helpers nuevos: listar_todas_plantillas, crear_plantilla, actualizar_plantilla, toggle_plantilla, contar_sitios_por_plantilla, listar_mensajes_sitio, marcar_mensaje_leido
  - app.py: rutas /admin/plantillas (GET lista), /nueva (GET/POST), /<id>/editar (GET/POST), /<id>/toggle (POST)
  - _SECCIONES_DISPONIBLES: 8 secciones disponibles para asignar por plantilla
  - admin_plantillas.html: tabla con estado, tipo, conteo de sitios, badges, botones
  - admin_plantilla_form.html: form con checkboxes para elegir secciones del editor
  - editor_sitio.html: nav de secciones renderizado dinámico según secciones_editor del schema
  - editor_sitio.html: JS activa primer panel correcto al cargar (fix race condition con hidden)
  - dashboard.html: botón "Gestionar plantillas" en banner admin
- Fase 6 completada:
  - app.py: werkzeug import al tope (elimina duplicado), rate limiter en memoria (_check_rate/_register_fail/_clear_rate)
  - app.py: admin /login — compatibilidad hash/texto-plano + re-hash automático en caliente
  - app.py: /entrar (CMS) — rate limiting aplicado
  - app.py: crear_cliente hash, editar_cliente hash (campo vacío conserva la actual)
  - app.py: _es_imagen_valida() — verifica magic bytes reales (PNG/JPG/WebP/GIF)
  - app.py: SECRET_KEY desde .env sin python-dotenv (lector propio de 8 líneas)
  - admin/.env + admin/.env.example creados
  - admin/start.sh — gunicorn en producción (2 workers, 2 threads, logs)
  - requirements.txt: agregado werkzeug y gunicorn explícitos
  - DEPLOY.md: instrucciones completas PythonAnywhere + VPS Ubuntu
- Estado: TODAS LAS FASES COMPLETADAS — sistema listo para prueba browser y deploy

### 2026-05-16 (sesión 2 — mejoras post-prueba)
- Fix logo: header-brand ahora usa if/else sin nodos de texto sueltos + usa nombre_negocio del config
- Mapa de ubicación en contacto: 3 modos (ninguno / coords OpenStreetMap / embed Google Maps)
- Editor: tabs de mapa, preview con iframe, instrucciones para obtener coordenadas
- Fix conflicto nombre función: crear_sitio → db_crear_sitio (alias en import)
- Tipografía: 12 Google Fonts seleccionables (titulos + cuerpo), preview en vivo en editor, link dinámico en templates
- Colores completos: +3 variables (acento, navbar, fondo secciones) → total 6 colores controlables
- Navbar: color independiente del primary (default = primary si no se configura)
- Pendiente: estilos de cards (paso 4), renombrar menú (paso 5), botones/hero (paso 6)
