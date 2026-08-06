"""Paleta de marca Savia Raíz: fondo oscuro + degradado de dos acentos.

Se define una sola vez aquí y la usan tanto generador_imagenes/generar.py
(PNG) como generador_html/generar_html.py (preview editable), para que un
mismo carrusel luzca igual en ambos formatos.

La primera vez que se genera un carrusel, se le asigna la siguiente paleta
en rotación (round-robin) — así nunca coincide con la del carrusel anterior.
Esa asignación queda guardada en `paletas_asignadas.json` y es fija para
siempre: volver a generar el mismo carrusel más adelante no le cambia el
color.
"""
import os
import json

INK = "#EAF0FB"
MUTED = "#8A99BC"

PALETTES = [
    {"nombre": "indigo",    "bg": "#0B1326", "slide_a": "#0D1730", "slide_b": "#090F1F", "accent": "#5B8CFF", "accent2": "#9B6BFF"},
    {"nombre": "esmeralda", "bg": "#081A16", "slide_a": "#0C231D", "slide_b": "#061410", "accent": "#34D399", "accent2": "#2DD4BF"},
    {"nombre": "vino",      "bg": "#1A0E14", "slide_a": "#241019", "slide_b": "#170A0F", "accent": "#FB7185", "accent2": "#FDBA74"},
    {"nombre": "cian",      "bg": "#071722", "slide_a": "#0B222F", "slide_b": "#050F17", "accent": "#22D3EE", "accent2": "#818CF8"},
]

_ASIGNACIONES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paletas_asignadas.json")


def hex_a_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _leer_asignaciones():
    if os.path.isfile(_ASIGNACIONES):
        with open(_ASIGNACIONES, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _guardar_asignaciones(datos):
    with open(_ASIGNACIONES, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, sort_keys=True)


def elegir_paleta(slug):
    asignaciones = _leer_asignaciones()
    if slug in asignaciones:
        nombre = asignaciones[slug]
        return next(p for p in PALETTES if p["nombre"] == nombre)

    paleta = PALETTES[len(asignaciones) % len(PALETTES)]
    asignaciones[slug] = paleta["nombre"]
    _guardar_asignaciones(asignaciones)
    return paleta
