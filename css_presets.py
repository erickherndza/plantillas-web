# css_presets.py
# Presets predefinidos para el CSS Builder
# Cada preset es un dict con design_tokens + section_variants listos para usar

PRESETS = {

    "modern_dark": {
        "label": "Modern dark",
        "description": "Navy + teal. Glassmorphism. Fraunces + Jakarta.",
        "design_tokens": {
            "colors": {"primary": "#00d4a0", "secondary": "#0a0f1e", "accent": "#0088cc", "neutral": "#e8eaf0", "mode": "dark"},
            "typography": {"display": "Fraunces", "body": "Plus Jakarta Sans", "scale": "normal", "weight_display": 300},
            "shape": {"radius": "rounded", "border_style": "subtle"},
            "spacing": {"density": "normal", "container_max": "1100px"},
            "effects": {"glass": True, "hero_glow": True, "card_hover": "lift", "animations": True}
        }
    },

    "clean_light": {
        "label": "Clean light",
        "description": "Blanco y carbón. Radio sharp. Inter.",
        "design_tokens": {
            "colors": {"primary": "#4f46e5", "secondary": "#f8f9fa", "accent": "#6366f1", "neutral": "#1a1f2e", "mode": "light"},
            "typography": {"display": "Inter", "body": "Inter", "scale": "normal", "weight_display": 600},
            "shape": {"radius": "sharp", "border_style": "subtle"},
            "spacing": {"density": "normal", "container_max": "1100px"},
            "effects": {"glass": False, "hero_glow": False, "card_hover": "border", "animations": True}
        }
    },

    "corporativo_axula": {
        "label": "Corporativo Axula",
        "description": "Paleta Axula lista para usar.",
        "design_tokens": {
            "colors": {"primary": "#038C8C", "secondary": "#024959", "accent": "#012840", "neutral": "#f0f4f8", "mode": "dark"},
            "typography": {"display": "Montserrat", "body": "Open Sans", "scale": "normal", "weight_display": 600},
            "shape": {"radius": "rounded", "border_style": "subtle"},
            "spacing": {"density": "normal", "container_max": "1100px"},
            "effects": {"glass": True, "hero_glow": True, "card_hover": "lift", "animations": True}
        }
    },

    "calido_profesional": {
        "label": "Cálido profesional",
        "description": "Naranja tierra + crema. Playfair + Lato.",
        "design_tokens": {
            "colors": {"primary": "#c45c26", "secondary": "#fff8f0", "accent": "#8b3a1a", "neutral": "#2d2d2d", "mode": "light"},
            "typography": {"display": "Playfair Display", "body": "Lato", "scale": "normal", "weight_display": 400},
            "shape": {"radius": "rounded", "border_style": "subtle"},
            "spacing": {"density": "airy", "container_max": "1100px"},
            "effects": {"glass": False, "hero_glow": False, "card_hover": "lift", "animations": True}
        }
    },

    "minimalista_bw": {
        "label": "Minimalista B&W",
        "description": "Solo negro y blanco. Sin efectos. DM Sans.",
        "design_tokens": {
            "colors": {"primary": "#111111", "secondary": "#fafafa", "accent": "#555555", "neutral": "#111111", "mode": "light"},
            "typography": {"display": "DM Sans", "body": "DM Sans", "scale": "normal", "weight_display": 400},
            "shape": {"radius": "sharp", "border_style": "strong"},
            "spacing": {"density": "airy", "container_max": "900px"},
            "effects": {"glass": False, "hero_glow": False, "card_hover": "none", "animations": False}
        }
    },

    "vibrante_caribeno": {
        "label": "Vibrante caribeño",
        "description": "Fucsia + violeta + cyan. Para negocios creativos RD.",
        "design_tokens": {
            "colors": {"primary": "#f72585", "secondary": "#7209b7", "accent": "#4cc9f0", "neutral": "#ffffff", "mode": "dark"},
            "typography": {"display": "Poppins", "body": "Poppins", "scale": "normal", "weight_display": 700},
            "shape": {"radius": "pill", "border_style": "none"},
            "spacing": {"density": "normal", "container_max": "1100px"},
            "effects": {"glass": True, "hero_glow": True, "card_hover": "glow", "animations": True}
        }
    },
}


def get_preset(name: str) -> dict:
    """Retorna el design_tokens de un preset por nombre."""
    p = PRESETS.get(name)
    if not p:
        raise ValueError(f"Preset '{name}' no existe. Disponibles: {list(PRESETS.keys())}")
    return p["design_tokens"]


def list_presets() -> list:
    """Retorna lista de presets con label y description."""
    return [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in PRESETS.items()
    ]


# Variantes de secciones por defecto (aplica a todos los presets)
DEFAULT_SECTION_VARIANTS = {
    "header":      {"variant": "centered", "sticky": True, "glass": True, "topbar": True, "active": True},
    "hero":        {"variant": "full",      "active": True},
    "services":    {"variant": "grid3",     "active": True},
    "about":       {"variant": "mvv",       "active": True},
    "team":        {"variant": "avatars",   "active": True},
    "portfolio":   {"variant": "grid",      "active": False},
    "testimonials":{"variant": "cards",     "active": False},
    "cta":         {"variant": "flex",      "active": True},
    "contact":     {"variant": "form_info", "active": True},
    "footer":      {"variant": "3col",      "active": True},
}
