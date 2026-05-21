# DESIGN_TOKENS_SCHEMA.md
# Brief para Claude Code — Motor de generación CSS
# Proyecto: Sistema de plantillas web mini pymes RD
# Ejecutar desde: ~/plantillas-web/admin/

---

## CONTEXTO

El CMS genera landing pages y sitios de 5 páginas a partir de plantillas HTML.
Cada site tiene dos JSONs que definen su apariencia:
- `design_tokens`: paleta, tipografía, forma, espaciado, efectos
- `section_variants`: qué secciones están activas y qué variante usa cada una

El motor lee estos JSONs y genera el `custom_css` que se inyecta en el `<head>` de cada página.
El `custom_css` NUNCA se edita manualmente — siempre es regenerado por el motor.

---

## TAREA PRINCIPAL

Crear el archivo `~/plantillas-web/admin/css_engine.py` con todas las funciones descritas abajo.

---

## SCHEMA: design_tokens (JSON)

```json
{
  "colors": {
    "primary":   "#00d4a0",
    "secondary": "#0a0f1e",
    "accent":    "#0088cc",
    "neutral":   "#e8eaf0",
    "mode":      "dark"
  },
  "typography": {
    "display":        "Fraunces",
    "body":           "Plus Jakarta Sans",
    "scale":          "normal",
    "weight_display": 300
  },
  "shape": {
    "radius":       "rounded",
    "border_style": "subtle"
  },
  "spacing": {
    "density":       "normal",
    "container_max": "1100px"
  },
  "effects": {
    "glass":       true,
    "hero_glow":   true,
    "card_hover":  "lift",
    "animations":  true
  }
}
```

### Valores válidos por campo

| Campo | Valores válidos | Default |
|---|---|---|
| colors.mode | "dark" \| "light" | "dark" |
| typography.scale | "compact" \| "normal" \| "large" | "normal" |
| typography.weight_display | 300 \| 400 \| 600 | 300 |
| shape.radius | "sharp" \| "rounded" \| "pill" | "rounded" |
| shape.border_style | "none" \| "subtle" \| "strong" | "subtle" |
| spacing.density | "compact" \| "normal" \| "airy" | "normal" |
| spacing.container_max | "900px" \| "1100px" \| "1300px" | "1100px" |
| effects.card_hover | "lift" \| "glow" \| "border" \| "none" | "lift" |

### Mapeo de valores a CSS

**shape.radius:**
- "sharp"   → `--radius: 4px`
- "rounded" → `--radius: 12px`
- "pill"    → `--radius: 999px`

**spacing.density (padding de secciones):**
- "compact" → `--section-pad: 48px`
- "normal"  → `--section-pad: 72px`
- "airy"    → `--section-pad: 96px`

**typography.scale (font-size base del body):**
- "compact" → `15px`
- "normal"  → `16px`
- "large"   → `17px`

---

## SCHEMA: section_variants (JSON)

```json
{
  "header":      { "variant": "centered", "sticky": true, "glass": true, "topbar": true, "active": true },
  "hero":        { "variant": "full",     "active": true },
  "services":    { "variant": "grid3",    "active": true },
  "about":       { "variant": "mvv",      "active": true },
  "team":        { "variant": "avatars",  "active": true },
  "portfolio":   { "variant": "grid",     "active": false },
  "testimonials":{ "variant": "cards",    "active": false },
  "cta":         { "variant": "flex",     "active": true },
  "contact":     { "variant": "form_info","active": true },
  "footer":      { "variant": "3col",     "active": true }
}
```

Si `active: false`, la función del motor retorna `""` (string vacío).
`header` y `footer` siempre son `active: true` — ignorar su flag si llega false.

---

## CLASES HTML QUE GENERA EL TEMPLATE

El motor debe estilizar estas clases exactas (las genera Jinja en las plantillas):

```
Header:    .topbar  .site-header  .header-brand  .header-contact  .navbar  .nav-list  .nav-toggle
Hero:      .hero-section  .hero-bg  .hero-content  .hero-eyebrow  .hero-title  .hero-subtitle  .hero-actions
Breadcrumb:.breadcrumb
Secciones: .section-inner  .section-header  .section-label  .section-title  .section-subtitle
Servicios: .services-section  .services-grid  .service-card  .service-icon  .service-title  .service-desc
Nosotros:  .about-section  .mvv-grid  .mvv-card  .mvv-icon  .mvv-card-title
Equipo:    .team-section  .team-grid  .team-card  .team-avatar  .team-name  .team-role
Portfolio: .portfolio-section  .portfolio-grid  .portfolio-card  .portfolio-title  .portfolio-category
CTA:       .cta-section  .cta-strip  .cta-inner
Contacto:  .contact-section  .contact-grid  .contact-info  .contact-item  .contact-form  .form-group  .form-feedback
Footer:    .site-footer  .footer-inner  .footer-brand  .footer-desc  .footer-nav  .footer-col  .footer-bottom
Botones:   .btn-primary  .btn-secondary  .btn-outline
Utilidades:.fade-in-up  .is-visible  .navbar--scrolled  .container
```

---

## FUNCIONES A IMPLEMENTAR

### Obligatorias (fase 1)

```python
generate_css(site_id: int, db) -> str
    # Punto de entrada. Lee JSONs de BD, llama todas las funciones, guarda resultado.
    # Actualiza custom_css y css_version en la tabla sites.

generate_root(tokens: dict) -> str
    # Retorna bloque :root { } con todas las variables CSS.
    # Incluye @import de Google Fonts (display + body).

generate_base(tokens: dict) -> str
    # Reset, body, a, img, .container, .section-inner, .section-header,
    # .section-title, .section-subtitle, .section-label.
    # Usa las variables del :root, nunca hardcodea colores.

generate_breadcrumb(tokens: dict) -> str
    # Estilo completo del breadcrumb.
    # Separador › como pseudo-elemento ::after en li:not(:last-child).
    # Último item en color primary.

generate_buttons(tokens: dict) -> str
    # .btn-primary, .btn-secondary, .btn-outline, estados :hover.
    # card_hover "lift" = translateY(-2px) + box-shadow en hover de btn-primary.

dispatch_section(section: str, variants: dict, tokens: dict) -> str
    # Router. Si active=False → return "". 
    # Llama a la función correcta según section + variant.

generate_responsive(tokens: dict, variants: dict) -> str
    # Un único bloque @media (max-width: 768px) al final.
    # Header colapsa a logo + hamburguesa.
    # nav-list pasa a flex-direction:column cuando tiene clase .is-open.
    # Grids pasan a 1 columna.
    # footer-inner pasa a 1 columna.

generate_animations(tokens: dict) -> str
    # Si effects.animations=True: .fade-in-up y .is-visible.
    # Si effects.animations=False: retorna "".
```

### Header (6 variantes)

```python
header_centered(cfg, tokens) -> str
    # display:grid; grid-template-columns:1fr auto 1fr
    # .header-brand → grid-column:1; justify-self:start
    # .navbar       → grid-column:2 (centrado matemáticamente)
    # .header-contact → grid-column:3; justify-self:end

header_left(cfg, tokens) -> str
    # display:flex; gap:32px
    # .navbar → flex:0 (no crece)
    # .header-contact → margin-left:auto

header_boxed(cfg, tokens) -> str
    # El .site-header es transparente.
    # Un div interno .header-inner con border:1px solid + border-radius
    # tiene el nav. Flota con margin-top:16px.

header_stacked(cfg, tokens) -> str
    # 2 filas. Fila 1: logo centrado. Fila 2: nav-list centrado.
    # flex-direction:column; align-items:center.

header_minimal(cfg, tokens) -> str
    # Solo logo + .nav-toggle visible siempre (no solo en móvil).
    # .navbar oculto por defecto, overlay fullscreen cuando .is-open.

header_split(cfg, tokens) -> str
    # Logo centrado. Nav dividida: primeros links izq, últimos links der.
    # grid-template-columns: 1fr auto 1fr
    # .nav-left → justify-self:end  .nav-right → justify-self:start
```

### Hero (4 variantes)

```python
hero_full(cfg, tokens) -> str
    # min-height: 100vh o 640px. Texto centrado.
    # Si effects.hero_glow: gradiente radial con color primary al 13%.

hero_compact(cfg, tokens) -> str
    # padding: 56px 32px 48px. Para páginas internas.
    # Sin gradiente de fondo elaborado.

hero_split(cfg, tokens) -> str
    # display:grid; grid-template-columns:1fr 1fr
    # Texto izquierda, imagen (.hero-image) derecha con border-radius.

hero_video(cfg, tokens) -> str
    # position:relative. .hero-bg con video/img en absolute inset:0.
    # Overlay rgba(secondary, 0.65) sobre el fondo.
    # Texto siempre blanco.
```

### Servicios (4 variantes)

```python
services_grid3(cfg, tokens) -> str
    # grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))
    # .service-card con card_hover según tokens.

services_grid2(cfg, tokens) -> str
    # grid-template-columns: repeat(auto-fit, minmax(320px, 1fr))

services_list(cfg, tokens) -> str
    # flex-direction:column. Icono circular + texto en fila.

services_tabs(cfg, tokens) -> str
    # .services-tabs con flex. .tab-btn activo con border-bottom primary.
    # .service-panel con display:none / display:block.
```

### Nosotros, Equipo, CTA, Contacto, Footer

```python
about_mvv(cfg, tokens) -> str
about_text_photo(cfg, tokens) -> str
about_timeline(cfg, tokens) -> str

team_avatars(cfg, tokens) -> str
team_list(cfg, tokens) -> str
team_cards_large(cfg, tokens) -> str

cta_flex(cfg, tokens) -> str
    # background: linear-gradient(135deg, primary, accent).
    # display:flex justify-content:space-between.
    # .btn-primary con colores invertidos (secondary bg, primary text).

cta_centered(cfg, tokens) -> str
    # Card con border: 1px solid primary rgba(0.25).
    # Todo centrado. Fondo semitransparente.

cta_bg_image(cfg, tokens) -> str
    # Clase base. El color del texto siempre blanco.
    # Overlay rgba(secondary, 0.7) para legibilidad.

contact_form_info(cfg, tokens) -> str
contact_form_only(cfg, tokens) -> str
contact_map_form(cfg, tokens) -> str

footer_3col(cfg, tokens) -> str
    # .footer-inner: max-width container, grid 1.6fr 1fr 1fr, gap:48px.
    # .footer-bottom: border-top, padding, text-align:center.

footer_2col(cfg, tokens) -> str
footer_1col(cfg, tokens) -> str
footer_minimal(cfg, tokens) -> str
    # Una sola línea: display:flex, justify-content:space-between.
```

---

## REGLAS DE IMPLEMENTACIÓN

1. **Nunca hardcodear colores** en las funciones de variante.
   Siempre usar `var(--color-primary)`, `var(--color-secondary)`, etc.
   Solo en `generate_root()` se ponen los valores reales.

2. **Las funciones reciben `tokens` completo** aunque no usen todo.
   Así pueden acceder a cualquier token sin cambiar la firma.

3. **Cada función retorna solo su bloque CSS**, sin :root ni @import.
   El ensamblaje final lo hace `generate_css()`.

4. **card_hover** se aplica con una helper:
   ```python
   def card_hover_css(tokens) -> str:
       ch = tokens['effects']['card_hover']
       if ch == 'lift':   return "transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.25);"
       if ch == 'glow':   return "box-shadow:0 0 0 2px var(--color-primary);"
       if ch == 'border': return "border-color:var(--color-primary);"
       return ""
   ```

5. **glass effect** en header:
   ```python
   glass_css = "backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);" if cfg.get('glass') else ""
   ```

6. **El responsive SIEMPRE incluye:**
   ```css
   .nav-toggle { display: flex; }
   .navbar { display: none; }
   .navbar.is-open { display: block; }
   .nav-list { flex-direction: column; }
   ```

7. **Orden del CSS final** (importante para cascada correcta):
   ```
   :root + @import
   → base (reset, body, container)
   → breadcrumb
   → buttons
   → header
   → hero
   → services / about / team / portfolio / testimonials
   → cta
   → contact
   → footer
   → @media responsive
   → animations
   ```

---

## RUTA FLASK (agregar en admin/app.py)

```python
from css_engine import generate_css
import json

@app.route('/api/sites/<int:site_id>/css/rebuild', methods=['POST'])
def rebuild_css(site_id):
    data = request.get_json()
    if 'design_tokens' in data:
        db.execute("UPDATE sites SET design_tokens=? WHERE id=?",
                   [json.dumps(data['design_tokens']), site_id])
    if 'section_variants' in data:
        db.execute("UPDATE sites SET section_variants=? WHERE id=?",
                   [json.dumps(data['section_variants']), site_id])
    db.commit()
    css = generate_css(site_id, db)
    version = db.execute("SELECT css_version FROM sites WHERE id=?",
                         [site_id]).fetchone()[0]
    return jsonify({'ok': True, 'css_length': len(css), 'version': version})
```

---

## SQL — MIGRACIÓN

```sql
-- Ejecutar en la BD de ~/plantillas-web/admin/ (SQLite)
ALTER TABLE sites ADD COLUMN design_tokens    TEXT DEFAULT 'null';
ALTER TABLE sites ADD COLUMN section_variants TEXT DEFAULT 'null';
ALTER TABLE sites ADD COLUMN css_version      INTEGER DEFAULT 0;

-- custom_css ya existe — ahora es solo derivado, no se edita directo
```

---

## DATOS DE PRUEBA (site "kreando")

```python
KREANDO_TOKENS = {
  "colors": {"primary":"#00d4a0","secondary":"#0a0f1e","accent":"#0088cc","neutral":"#e8eaf0","mode":"dark"},
  "typography": {"display":"Fraunces","body":"Plus Jakarta Sans","scale":"normal","weight_display":300},
  "shape": {"radius":"rounded","border_style":"subtle"},
  "spacing": {"density":"normal","container_max":"1100px"},
  "effects": {"glass":True,"hero_glow":True,"card_hover":"lift","animations":True}
}

KREANDO_VARIANTS = {
  "header":   {"variant":"centered","sticky":True,"glass":True,"topbar":True,"active":True},
  "hero":     {"variant":"full","active":True},
  "services": {"variant":"grid3","active":True},
  "about":    {"variant":"mvv","active":True},
  "team":     {"variant":"avatars","active":True},
  "portfolio":{"variant":"grid","active":False},
  "testimonials":{"variant":"cards","active":False},
  "cta":      {"variant":"flex","active":True},
  "contact":  {"variant":"form_info","active":True},
  "footer":   {"variant":"3col","active":True}
}
```

---

## PRUEBA RÁPIDA (al terminar)

```bash
cd ~/plantillas-web/admin
python3 -c "
from css_engine import generate_root, generate_base, header_centered, footer_3col
import json

tokens = json.loads(open('test_tokens.json').read()) if __import__('os').path.exists('test_tokens.json') else {
  'colors':{'primary':'#00d4a0','secondary':'#0a0f1e','accent':'#0088cc','neutral':'#e8eaf0','mode':'dark'},
  'typography':{'display':'Fraunces','body':'Plus Jakarta Sans','scale':'normal','weight_display':300},
  'shape':{'radius':'rounded','border_style':'subtle'},
  'spacing':{'density':'normal','container_max':'1100px'},
  'effects':{'glass':True,'hero_glow':True,'card_hover':'lift','animations':True}
}

css = generate_root(tokens)
css += generate_base(tokens)
css += header_centered({'sticky':True,'glass':True,'topbar':True}, tokens)
css += footer_3col({}, tokens)
print(f'CSS generado: {len(css)} chars')
print(css[:500])
"
```

Criterio de aprobación:
- [ ] Sin errores de import
- [ ] Output > 2000 caracteres
- [ ] Contiene `--color-primary: #00d4a0` en el :root
- [ ] Contiene `grid-template-columns:1fr auto 1fr` (header centered)
- [ ] Contiene `.footer-inner` con `grid-template-columns`

---

## ARCHIVOS A CREAR

| Archivo | Descripción |
|---|---|
| `~/plantillas-web/admin/css_engine.py` | Motor principal (OBLIGATORIO) |
| `~/plantillas-web/admin/css_presets.py` | 6 presets predefinidos como dicts Python |

## NO TOCAR

- Ningún archivo HTML de plantilla
- El `app.py` existente — solo agregar el endpoint nuevo al final
- La BD existente — solo agregar columnas con ALTER TABLE

---

*Schema generado por: Claude (claude.ai) para Erick Hernández Arias*
*Proyecto: Sistema de plantillas web mini pymes RD*
*Módulo: CSS Builder — Fase 1*
