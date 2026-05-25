# INSTRUCCIONES PARA CLAUDE CODE
# Proyecto: ~/plantillas-web/admin/
# Tarea: Aplicar fix del scraper — blueprint real + defaults_json

## CONTEXTO DEL PROBLEMA

El scraper detectaba colores y fuentes correctamente pero:
1. `_layoutDetectado` en el frontend solo guardaba 4 valores genéricos (hero/services/projects/team)
   basados en el estilo CSS — nunca analizaba el DOM para detectar secciones reales.
2. `admin_scraper_crear_url()` en app.py guardaba `defaults_json = '{}'` siempre.
   Sin defaults, el generador no sabía qué secciones renderizar → todas las plantillas
   salían iguales.

## FIX 1 — scraper_plantillas.html

REEMPLAZA el archivo completo:
```
cp ~/Downloads/scraper_plantillas.html \
   ~/plantillas-web/admin/templates/admin/scraper_plantillas.html
```

Qué cambió:
- Nueva función `extractBlueprint(html, estilo)` que analiza el DOM real
  y detecta hasta 10 tipos de secciones (topbar, header, hero, features_strip,
  about, why_us, impact, services, newsletter, footer) con su layout y propiedades.
- Nueva UI "Estructura detectada" que muestra las secciones encontradas en orden.
- Nuevos toggles "Componentes opcionales": WhatsApp, newsletter, redes, topbar, citas, tipo de hero.
- El payload al backend ahora incluye `blueprint` (objeto completo) y `componentes`
  en lugar del viejo `layout` genérico.

## FIX 2 — app.py

En ~/plantillas-web/admin/app.py, REEMPLAZA la función `admin_scraper_crear_url()`
con la versión en app_scraper_fix.py, Y AGREGA las dos funciones helper
`_blueprint_to_layout()` y `_blueprint_to_defaults()` después de ella.

### Pasos exactos:

1. Abre ~/plantillas-web/admin/app.py
2. Busca la línea:
   `@app.route('/admin/scraper/crear-desde-url', methods=['POST'])`
3. Reemplaza toda la función `admin_scraper_crear_url()` (hasta su `return jsonify`)
   con el contenido de app_scraper_fix.py — desde la línea del @app.route hasta
   el fin de `_blueprint_to_defaults()`.
4. NO toques `_CATEGORIAS`, `admin_scraper()`, ni `admin_scraper_crear_categoria()`.

Qué cambió en app.py:
- Recibe `blueprint` y `componentes` del payload (antes ignorados).
- `_blueprint_to_layout()`: convierte secciones detectadas → layout_json real.
  Ya no devuelve siempre `{'hero':'split','services':'grid',...}` genérico.
- `_blueprint_to_defaults()`: genera `defaults_json` con ~20 campos derivados
  del blueprint — antes siempre era `'{}'`.
- El generador ahora tiene contexto real para renderizar la estructura correcta.

## DEPLOY

```bash
cd ~/plantillas-web
git add admin/templates/admin/scraper_plantillas.html admin/app.py
git commit -m "fix(scraper): blueprint real + defaults_json desde DOM analizado"
git push github master
```

Luego en PythonAnywhere:
```bash
cd ~/plantillas-web && git pull
```
Y Reload en Web tab.

## PRUEBA

1. Ve a /admin/scraper
2. Pega: https://jdsfibers.com/es/
3. Click "Analizar →"
4. Debes ver:
   - Badge: "10 secciones detectadas"
   - Sección "Estructura detectada" con badges: topbar, header, hero, features_strip,
     about, why_us, impact, services, newsletter, footer — en ese orden
5. Activa WhatsApp + newsletter
6. Elige "Hero estático"
7. Click "Crear plantilla"
8. Verifica en DB que defaults_json NO está vacío:
   python3 -c "
   import sqlite3, json
   db = sqlite3.connect('plantillas.db')
   row = db.execute('SELECT defaults_json FROM estilos_plantilla ORDER BY id DESC LIMIT 1').fetchone()
   d = json.loads(row[0])
   print('Secciones:', d.get('_detected_sections'))
   print('WhatsApp:', d.get('comp_whatsapp'))
   print('Newsletter:', d.get('comp_newsletter'))
   "

## NOTA IMPORTANTE

El `defaults_json` ahora tiene la estructura pero el generador de plantillas
(la función que construye el HTML final) aún necesita LEER estos valores
para renderizar las secciones correctas. Si el generador no lee `defaults_json`,
el siguiente paso es actualizarlo para que use estos datos.

Ese es el siguiente fix — pero primero valida que los datos llegan correctos a la DB.
y luego adapta el archivo app_scraper_fix.py al archivo plantillas_editor.py
