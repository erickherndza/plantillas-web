"""
image_processor.py — Optimización de imágenes con Pillow
Día 4: resize + conversión WebP + control de peso máximo

Tipos y límites:
  logo    → 400×120 px   · 100 KB max
  hero    → 1600×900 px  · 400 KB max
  general → 1200×1200 px · 200 KB max
"""

from PIL import Image, ImageOps
import io

# ── Configuración por tipo ────────────────────────────────────────────────────

PRESETS = {
    'logo': {
        'max_w':    400,
        'max_h':    120,
        'max_kb':   100,
        'label':    'Logo',
        'sugerencia': '200×60 px · PNG/WebP transparente · máx 100 KB',
    },
    'hero': {
        'max_w':    1600,
        'max_h':    900,
        'max_kb':   400,
        'label':    'Hero',
        'sugerencia': '1600×900 px · JPG/WebP · máx 400 KB',
    },
    'general': {
        'max_w':    1200,
        'max_h':    1200,
        'max_kb':   200,
        'label':    'Imagen',
        'sugerencia': 'máx 1200×1200 px · 200 KB',
    },
}

CALIDADES_WEBP = [85, 75, 65, 55, 45]   # intentos de calidad descendentes


# ── Función principal ─────────────────────────────────────────────────────────

def procesar_imagen(archivo_bytes: bytes, tipo: str = 'general') -> dict:
    """
    Recibe bytes del archivo original y devuelve:
    {
        'ok': bool,
        'bytes': bytes,          # WebP procesado
        'ext': '.webp',
        'size_kb': float,        # peso final en KB
        'dimensiones': (w, h),   # píxeles finales
        'mensaje': str,          # descripción para el usuario
        'error': str | None,
    }
    """
    preset = PRESETS.get(tipo, PRESETS['general'])
    max_w  = preset['max_w']
    max_h  = preset['max_h']
    max_kb = preset['max_kb']

    try:
        img = Image.open(io.BytesIO(archivo_bytes))
        orig_w, orig_h = img.size
        orig_mode     = img.mode

        # 1. Corregir orientación EXIF (fotos de móvil giradas)
        img = ImageOps.exif_transpose(img)

        # 2. Convertir modo para WebP:
        #    - Logo (imagen_src): mantener RGBA (transparencia PNG)
        #    - Hero / general:    convertir a RGB
        if tipo == 'logo':
            if orig_mode not in ('RGBA', 'RGB'):
                img = img.convert('RGBA')
        else:
            if img.mode == 'RGBA':
                # Aplanar sobre fondo blanco para JPG/hero
                fondo = Image.new('RGB', img.size, (255, 255, 255))
                fondo.paste(img, mask=img.split()[3])
                img = fondo
            elif img.mode != 'RGB':
                img = img.convert('RGB')

        # 3. Reducir tamaño manteniendo proporción
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        final_w, final_h = img.size

        # 4. Guardar como WebP ajustando calidad hasta alcanzar el límite de KB
        output = None
        final_kb = 0.0
        final_quality = CALIDADES_WEBP[0]

        for quality in CALIDADES_WEBP:
            buffer = io.BytesIO()
            save_kwargs = {
                'format': 'WEBP',
                'quality': quality,
                'method': 4,    # balance entre velocidad y compresión
            }
            # Preservar alpha para logos
            if img.mode == 'RGBA':
                save_kwargs['lossless'] = False

            img.save(buffer, **save_kwargs)
            size_bytes = buffer.tell()
            final_kb   = size_bytes / 1024

            if final_kb <= max_kb:
                output        = buffer.getvalue()
                final_quality = quality
                break

        if output is None:
            # Si ninguna calidad logró el objetivo, usar la mínima de todas formas
            output        = buffer.getvalue()
            final_quality = CALIDADES_WEBP[-1]

        # 5. Construir mensaje informativo
        reduccion = round((1 - final_kb / (len(archivo_bytes) / 1024)) * 100)
        reduccion = max(0, reduccion)   # evitar negativo si el WebP es mayor

        msg = (
            f"{final_w}×{final_h} px · "
            f"{final_kb:.0f} KB · "
            f"WebP q{final_quality}"
        )
        if reduccion > 0:
            msg += f" · {reduccion}% más liviana"
        if orig_w > max_w or orig_h > max_h:
            msg += f" (redimensionada de {orig_w}×{orig_h})"

        return {
            'ok':          True,
            'bytes':       output,
            'ext':         '.webp',
            'size_kb':     round(final_kb, 1),
            'dimensiones': (final_w, final_h),
            'mensaje':     msg,
            'error':       None,
        }

    except Exception as e:
        return {
            'ok':          False,
            'bytes':       None,
            'ext':         None,
            'size_kb':     0,
            'dimensiones': (0, 0),
            'mensaje':     '',
            'error':       str(e),
        }
