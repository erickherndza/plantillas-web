# CONTEXT.md — CSS Builder / plantillas-web
# Para: Claude Code (VS Code)
# Proyecto: Sistema de plantillas web para mini pymes RD
# Autor: Erick Hernández Arias — negocios@erickhernandezarias.net
# Stack: Python/Flask · SQLite · HTML/CSS/Vanilla JS · Big Sur compatible

---

## QUÉ ES ESTE PROYECTO

CMS para crear landing pages y sitios de 5 páginas a través de plantillas HTML.
Cada site tiene contenido editable vía panel admin (puerto 5002, Flask + BeautifulSoup).

El CSS de cada site se guarda en la columna `custom_css` de la tabla `sites` en SQLite
y se inyecta directamente en el `<head>` de cada página.

**Nuevo módulo que estamos construyendo:** un generador de CSS personalizado (CSS Builder)
que reemplaza la edición manual del `custom_css` por un sistema de tokens + variantes.

---

## ARQUITECTURA DEL CSS BUILDER

### El problema que resuelve
Antes: el `custom_css` se editaba a mano, campo de texto libre, sin estructura.
Ahora: el usuario elige colores, tipografía y variante de cada sección desde un panel visual.
El motor genera el CSS automáticamente. El `custom_css` pasa a ser un campo **derivado**.

### Las 5 capas del sistema

```
1. Panel editor (css_builder_panel.html)
   └── UI con 8 paneles: colores, tipografía, forma, efectos,
       header, hero, secciones, footer
   └── Preview en vivo reactivo al cambiar tokens
   └── Botón "Generar CSS" → llama al endpoint Flask

2. Token engine (generate_root en css_engine.py)
   └── Convierte los inputs del usuario a variables CSS :root
   └── Nunca hardcodea colores — SIEMPRE usa var(--color-primary) etc.

3. Generador por sección (dispatch_section en css_engine.py)
   └── Router: sección + variante → función CSS correcta
   └── 31 variantes en total (ver catálogo abajo)
   └── Si active=False → retorna ""

4. Output
   └── CSS final → sites.custom_css en BD
   └── sites.css_version++ para cache-busting

5. Cloudflare Pages
   └── git push → redeploy automático (no cambia nada aquí)
```

### Flujo de una sesión de trabajo
```
VS Code abre ~/plantillas-web/admin/
→ Terminal integrada: python3 app.py (puerto 5002)
→ Claude Code lee este CONTEXT.md + DESIGN_TOKENS_SCHEMA.md
→ Edita css_engine.py en el workspace
→ Browser: localhost:5002/admin/sites/1/css-builder
→ Clic "Generar CSS" → llama /api/sites/1/css/rebuild
→ CSS actualizado en BD → visible en el site cliente
```

---

## ARCHIVOS DEL MÓDULO

```
~/plantillas-web/admin/
├── css_engine.py              ← Motor principal (CREAR/EDITAR)
├── css_presets.py             ← 6 presets predefinidos (YA EXISTE)
├── DESIGN_TOKENS_SCHEMA.md    ← Schema completo + reglas (YA EXISTE)
├── CONTEXT.md                 ← Este archivo
├── app.py                     ← Agregar 2 rutas al final (NO tocar lo existente)
└── templates/
    └── css_builder.html       ← Panel admin (YA EXISTE)
```

---

## SCHEMA: design_tokens (JSON guardado en sites.design_tokens)

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
    "glass":      true,
    "hero_glow":  true,
    "card_hover": "lift",
    "animations": true
  }
}
```

### Mapeos de valores a CSS
| Token | Valor | CSS resultante |
|---|---|---|
| shape.radius | "sharp" | `--radius: 4px` |
| shape.radius | "rounded" | `--radius: 12px` |
| shape.radius | "pill" | `--radius: 999px` |
| spacing.density | "compact" | `--section-pad: 48px` |
| spacing.density | "normal" | `--section-pad: 72px` |
| spacing.density | "airy" | `--section-pad: 96px` |
| typography.scale | "compact" | `font-size: 15px` en body |
| typography.scale | "normal" | `font-size: 16px` en body |
| typography.scale | "large" | `font-size: 17px` en body |

---

## SCHEMA: section_variants (JSON guardado en sites.section_variants)

```json
{
  "header":      { "variant": "centered", "sticky": true, "glass": true, "topbar": true, "active": true },
  "hero":        { "variant": "full",      "active": true },
  "services":    { "variant": "grid3",     "active": true },
  "about":       { "variant": "mvv",       "active": true },
  "team":        { "variant": "avatars",   "active": true },
  "portfolio":   { "variant": "grid",      "active": false },
  "testimonials":{ "variant": "cards",     "active": false },
  "cta":         { "variant": "flex",      "active": true },
  "contact":     { "variant": "form_info", "active": true },
  "footer":      { "variant": "3col",      "active": true }
}
```

---

## CATÁLOGO COMPLETO DE VARIANTES (31 total)

### Header (6 variantes)
| variant | descripción | CSS clave |
|---|---|---|
| `centered` | logo izq · nav centro · CTA der | `grid-template-columns: 1fr auto 1fr` |
| `left` | logo + nav pegados izquierda | `display: flex; gap: 32px` |
| `boxed` | nav en contenedor con borde | `.header-inner` con border + border-radius |
| `stacked` | logo arriba · nav abajo (2 filas) | `flex-direction: column; align-items: center` |
| `minimal` | solo logo + hamburguesa | `.navbar` en overlay fullscreen |
| `split` | logo centrado · links divididos | grid + `.nav-left` y `.nav-right` |

### Hero (4 variantes)
| variant | descripción |
|---|---|
| `full` | min-height 100vh · texto centrado · glow si effects.hero_glow |
| `compact` | padding 56px · para páginas internas |
| `split` | grid 50/50 · texto izq · imagen der |
| `video` | overlay rgba sobre `<video>` · texto siempre blanco |

### Servicios (4 variantes)
| variant | descripción |
|---|---|
| `grid3` | `repeat(auto-fit, minmax(220px, 1fr))` |
| `grid2` | `repeat(auto-fit, minmax(320px, 1fr))` |
| `list` | flex-direction column · icono circular + texto |
| `tabs` | `.tab-btn` + `.service-panel` |

### Nosotros (3 variantes)
| variant | descripción |
|---|---|
| `mvv` | 3 cards: Misión · Visión · Valores |
| `text_photo` | grid 50/50 · texto izq · imagen redondeada der |
| `timeline` | línea vertical · hitos con año + descripción |

### Equipo (3 variantes)
| variant | descripción |
|---|---|
| `avatars` | avatar circular + nombre + rol · auto-fit minmax(180px) |
| `list` | fila compacta · avatar pequeño inline |
| `cards_large` | foto + bio corta · grid de 2 |

### CTA Strip (3 variantes)
| variant | descripción |
|---|---|
| `flex` | `justify-content: space-between` · fondo gradiente primary→accent |
| `centered` | todo centrado · card con borde primary rgba |
| `bg_image` | overlay rgba(secondary, 0.7) · texto siempre blanco |

### Contacto (3 variantes)
| variant | descripción |
|---|---|
| `form_info` | grid 2 col · info izq · formulario der |
| `form_only` | formulario centrado max-width 560px |
| `map_form` | iframe mapa izq · formulario der |

### Footer (4 variantes)
| variant | descripción |
|---|---|
| `3col` | `grid-template-columns: 1.6fr 1fr 1fr` |
| `2col` | `grid-template-columns: 1fr 1fr` |
| `1col` | todo centrado en columna |
| `minimal` | una sola línea flex · logo + copyright + links |

---

## CLASES HTML QUE GENERAN LOS TEMPLATES JINJA

El motor estiliza **estas clases exactas** — no inventar otras:

```
Header:    .topbar  .site-header  .header-brand  .header-contact
           .navbar  .nav-list  .nav-toggle  .navbar--scrolled
Hero:      .hero-section  .hero-bg  .hero-content  .hero-eyebrow
           .hero-title  .hero-subtitle  .hero-actions
Breadcrumb:.breadcrumb
Secciones: .section-inner  .section-header  .section-label
           .section-title  .section-subtitle
Servicios: .services-section  .services-grid  .service-card
           .service-icon  .service-title  .service-desc
Nosotros:  .about-section  .mvv-grid  .mvv-card  .mvv-icon  .mvv-card-title
Equipo:    .team-section  .team-grid  .team-card  .team-avatar
           .team-name  .team-role
Portfolio: .portfolio-section  .portfolio-grid  .portfolio-card
           .portfolio-title  .portfolio-category
CTA:       .cta-section  .cta-strip  .cta-inner
Contacto:  .contact-section  .contact-grid  .contact-info  .contact-item
           .contact-form  .form-group  .form-feedback
Footer:    .site-footer  .footer-inner  .footer-brand  .footer-desc
           .footer-nav  .footer-col  .footer-bottom
Botones:   .btn-primary  .btn-secondary  .btn-outline
Utilidades:.fade-in-up  .is-visible  .container
```

---

## REGLAS DE IMPLEMENTACIÓN (no negociables)

1. **Nunca hardcodear colores** en funciones de variante.
   Único lugar con valores reales: `generate_root()`.
   En todo lo demás: `var(--color-primary)`, `var(--color-secondary)`, etc.

2. **Orden del CSS final** (importante para cascada):
   ```
   :root + @import Google Fonts
   → base (reset, body, .container)
   → breadcrumb
   → buttons
   → header
   → hero
   → services · about · team · portfolio · testimonials
   → cta
   → contact
   → footer
   → @media (max-width: 768px)
   → animations (.fade-in-up / .is-visible)
   ```

3. **Responsive siempre incluye:**
   ```css
   .nav-toggle { display: flex; }
   .navbar { display: none; }
   .navbar.is-open { display: block; }
   .nav-list { flex-direction: column; }
   ```

4. **glass effect:**
   ```python
   glass = "backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);"
   glass_css = glass if cfg.get('glass') else ""
   ```

5. **card_hover helper** (usar en todas las cards):
   ```python
   def card_hover_css(tokens):
       ch = tokens['effects']['card_hover']
       if ch == 'lift':   return "transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.25);"
       if ch == 'glow':   return "box-shadow:0 0 0 2px var(--color-primary);"
       if ch == 'border': return "border-color:var(--color-primary);"
       return ""
   ```

6. **header.sticky:**
   ```python
   pos = "sticky;top:0;z-index:100" if cfg.get('sticky') else "relative"
   ```

7. **dispatch_section retorna "" si active=False.**
   Excepción: header y footer siempre activos.

---

## RUTAS FLASK A AGREGAR EN app.py

```python
# Agregar al FINAL de app.py — no tocar nada existente
from css_engine import generate_css
import json

@app.route('/admin/sites/<int:site_id>/css-builder')
def css_builder(site_id):
    site = db.execute("SELECT * FROM sites WHERE id=?", [site_id]).fetchone()
    return render_template('css_builder.html', site=site)

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
    version = db.execute(
        "SELECT css_version FROM sites WHERE id=?", [site_id]
    ).fetchone()[0]
    return jsonify({'ok': True, 'css_length': len(css), 'version': version})
```

---

## MIGRACIÓN SQL

```python
# Ejecutar UNA VEZ en la BD existente
import sqlite3
db = sqlite3.connect('plantillas.db')  # ajustar nombre real
db.execute('ALTER TABLE sites ADD COLUMN design_tokens TEXT DEFAULT NULL')
db.execute('ALTER TABLE sites ADD COLUMN section_variants TEXT DEFAULT NULL')
db.execute('ALTER TABLE sites ADD COLUMN css_version INTEGER DEFAULT 0')
db.commit()
```

---

## DATOS DE PRUEBA — site "kreando"

```python
KREANDO_TOKENS = {
    "colors": {"primary":"#00d4a0","secondary":"#0a0f1e",
               "accent":"#0088cc","neutral":"#e8eaf0","mode":"dark"},
    "typography": {"display":"Fraunces","body":"Plus Jakarta Sans",
                   "scale":"normal","weight_display":300},
    "shape": {"radius":"rounded","border_style":"subtle"},
    "spacing": {"density":"normal","container_max":"1100px"},
    "effects": {"glass":True,"hero_glow":True,"card_hover":"lift","animations":True}
}

KREANDO_VARIANTS = {
    "header":      {"variant":"centered","sticky":True,"glass":True,
                    "topbar":True,"active":True},
    "hero":        {"variant":"full","active":True},
    "services":    {"variant":"grid3","active":True},
    "about":       {"variant":"mvv","active":True},
    "team":        {"variant":"avatars","active":True},
    "portfolio":   {"variant":"grid","active":False},
    "testimonials":{"variant":"cards","active":False},
    "cta":         {"variant":"flex","active":True},
    "contact":     {"variant":"form_info","active":True},
    "footer":      {"variant":"3col","active":True}
}
```

---

## PRESETS DISPONIBLES (en css_presets.py)

| key | label | paleta |
|---|---|---|
| `modern_dark` | Modern dark | navy + teal #00d4a0 |
| `clean_light` | Clean light | blanco + índigo |
| `corporativo_axula` | Corporativo Axula | #024959 + #038C8C |
| `calido_profesional` | Cálido profesional | naranja tierra + crema |
| `minimalista_bw` | Minimalista B&W | negro + blanco puro |
| `vibrante_caribeno` | Vibrante caribeño | fucsia + violeta + cyan |

---

## TEST DE VERIFICACIÓN

Correr después de implementar `css_engine.py`:

```bash
cd ~/plantillas-web/admin
python3 -c "
from css_engine import generate_root, generate_base, header_centered, footer_3col
tokens = {
  'colors':{'primary':'#00d4a0','secondary':'#0a0f1e',
            'accent':'#0088cc','neutral':'#e8eaf0','mode':'dark'},
  'typography':{'display':'Fraunces','body':'Plus Jakarta Sans',
                'scale':'normal','weight_display':300},
  'shape':{'radius':'rounded','border_style':'subtle'},
  'spacing':{'density':'normal','container_max':'1100px'},
  'effects':{'glass':True,'hero_glow':True,'card_hover':'lift','animations':True}
}
css  = generate_root(tokens)
css += generate_base(tokens)
css += header_centered({'sticky':True,'glass':True,'topbar':True}, tokens)
css += footer_3col({}, tokens)
print(f'OK — {len(css)} chars')
assert '--color-primary' in css, 'Falta --color-primary en :root'
assert 'grid-template-columns:1fr auto 1fr' in css, 'Falta header centered'
assert '.footer-inner' in css, 'Falta footer-inner'
print('Todos los assertions pasaron')
"
```

Criterios:
- [ ] Sin errores de import
- [ ] Output > 2000 chars
- [ ] `--color-primary: #00d4a0` en el :root
- [ ] `grid-template-columns:1fr auto 1fr` en header centered
- [ ] `.footer-inner` con grid-template-columns

---

## CONTEXTO DEL ENTORNO

- MacBook Pro 2015 · macOS Big Sur 11.6.1
- Python 3 (siempre `python3`, nunca `python`)
- SQLite (path relativo desde dentro de `admin/`)
- Claude Code via extensión VS Code
- Cloudflare Pages para deploy (git push → auto-deploy)
- Sin npm, sin node_modules en este módulo

---

## ESTADO ACTUAL DEL MÓDULO

- [x] Schema de tokens diseñado y documentado
- [x] Catálogo de 31 variantes definido
- [x] DESIGN_TOKENS_SCHEMA.md creado
- [x] css_presets.py creado (6 presets)
- [x] css_builder_panel.html creado (panel admin completo)
- [ ] css_engine.py — **PENDIENTE DE IMPLEMENTAR**
- [ ] Migración SQL — pendiente
- [ ] Rutas en app.py — pendientes
- [ ] Test de verificación — pendiente

---

*Contexto generado con Claude (claude.ai) · Mayo 2026*
*Sesión de diseño: workflow CSS Builder completo*
