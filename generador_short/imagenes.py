#!/usr/bin/env python3
"""Imagen de fondo de cada escena, generada con Gemini (Nano Banana Pro).

Por qué imagen y no video: **Veo no está disponible en esta llave** (los
modelos `veo-*` devuelven 404 y no aparecen en ListModels; es un modelo de
pago). Lo que sí hay es generación de imagen en 9:16 a 2K, y una imagen fija
con cámara, paralaje y efectos —lo que hace `fondos.py`— se ve como video
real, que es lo que hacen las audioguías de este mismo usuario con las fotos.
Si algún día la llave tiene Veo, el lugar donde se enchufaría es aquí: el
resto del generador solo pide "el fondo de la escena N".

Cada imagen se paga, así que todo se guarda en `.imagenes/` con un hash del
prompt: volver a generar el Reel no vuelve a pagar, y cambiar el texto o la
animación tampoco. Solo se pide de nuevo lo que cambió de prompt (o todo, con
`--force`).
"""
import base64
import hashlib
import io
import json
import shutil
import subprocess
import os
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


def _diagnostico(codigo, detalle):
    """Mismo criterio que en voz.py: un 429 por tope de gasto no se arregla
    reintentando, y conviene decirlo con todas sus letras."""
    import voz
    claro = voz.explicar_429(detalle) if codigo == 429 else None
    return claro or f"Gemini (imagen) {codigo}: {detalle}"


def _luminancia(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b

MODELO = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
TAMANO = "2K"   # 1536×2752: suficiente para 1080×1920 con margen para el acercamiento

# El mismo motivo se ilumina al revés según la paleta: en las oscuras el objeto
# brilla contra la sombra, y en la paleta clara nada puede ser oscuro o el texto
# (que ahí va en tinta) deja de leerse.
LUZ_OSCURA = ("Dark scene: the subject is lit against deep shadow, high contrast, "
              "luminous highlights, the backdrop falling to near-black at the edges.")
LUZ_CLARA = ("Bright airy scene on a near-white ground: soft daylight, delicate "
             "shadows, pale tints. Nothing dark or heavy, no black, no night.")

# Dos familias de imagen. `objeto` es la buena para un Reel: una cosa física en
# un estudio, que *demuestra* la idea (una balanza que se vence, una pila que
# crece). Un fondo abstracto se ve bonito pero no dice nada, y acaba siendo un
# telón detrás del texto — que es justo lo que no queremos.
OBJETO = (
    "Studio product photograph on a seamless infinite backdrop in {bg}. One soft "
    "directional key light from the upper left, a long soft shadow falling to the "
    "lower right, a faint cool rim light picking out the edges in {accent}. Minimal "
    "classic business aesthetic — quiet, premium, expensive-looking. Real physical "
    "materials with weight: brushed metal, matte ceramic, stone, glass. Shallow depth "
    "of field, the object crisp against a softly falling-off backdrop. "
    "The object sits in the LOWER TWO THIRDS of a vertical 9:16 frame, with clean "
    "empty backdrop above it for a headline. Accents strictly {accent} and {accent2}. "
    "Absolutely no text, no letters, no numbers, no logos, no screens, no user "
    "interfaces, no charts, no people, no hands."
)

ATMOSFERA = (
    "Abstract cinematic background, premium and restrained, shallow depth of field, "
    "volumetric light, fine particles and soft bokeh, subtle film grain. "
    "Strict color palette: deep background {bg}, light accents {accent} and {accent2}; "
    "no other hues. The center of the frame stays calm and uncluttered — the visual "
    "interest lives in the top and bottom thirds. "
    "Vertical 9:16. Absolutely no text, no letters, no numbers, no logos, no "
    "watermarks, no user interfaces, no charts, no recognizable faces."
)

FAMILIAS = {"objeto": OBJETO, "atmosfera": ATMOSFERA, "atmósfera": ATMOSFERA}
POR_DEFECTO = "objeto"


def _motivo(esc):
    """El motivo visual de la escena. Puede ser texto, o un dict con `base` y
    `despues` (ver `secuencia_de`)."""
    m = esc.get("imagen") or esc.get("visual")
    if isinstance(m, dict):
        return m.get("base") or m.get("imagen") or ""
    return m


def prompt_de(escena, paleta, motivo=None, familia=None):
    """Prompt de una escena: su motivo visual + el estilo de la casa.

    El motivo lo escribe quien hace el guion (`"imagen"` en la escena) y debe
    ser **una cosa física que demuestre la idea**, no un ambiente: "una balanza
    donde el cubo chico vence al grande" en vez de "poder y eficiencia"."""
    if motivo is None:
        motivo = _motivo(escena)
    if not motivo:
        tema = " ".join(x for x in (escena.get("etiqueta", ""), escena.get("kicker", ""),
                                    (escena.get("titulo") or "").replace("|", " ")) if x)
        motivo = f"A single physical object that stands as a metaphor for: {tema}"
    familia = familia or escena.get("familia") or POR_DEFECTO
    if familia not in FAMILIAS:
        raise SystemExit(f"Familia de imagen desconocida: {familia}. "
                         f"Hay: {', '.join(sorted(set(FAMILIAS)))}")
    claro = _luminancia(paleta["bg"]) > 140
    luz = LUZ_CLARA if claro else LUZ_OSCURA
    cuerpo = FAMILIAS[familia].format(bg=paleta["bg"], accent=paleta["accent"],
                                      accent2=paleta["accent2"])
    return motivo.strip().rstrip(".") + ". " + luz + " " + cuerpo


def secuencia_de(escena):
    """Instrucción de cambio para el segundo estado del objeto, si la hay.

    Dos generaciones distintas del mismo prompt dan dos objetos distintos, así
    que el "después" no se genera de cero: se EDITA la imagen ya hecha. Así es
    literalmente el mismo objeto en otro estado, que es lo que hace que el
    plano demuestre algo en vez de solo ilustrarlo."""
    m = escena.get("imagen") or escena.get("visual")
    return m.get("despues") if isinstance(m, dict) else None


def _pedir(key, prompt):
    cuerpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "9:16", "imageSize": TAMANO},
        },
    }
    req = urllib.request.Request(
        ENDPOINT.format(MODELO), data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")[:400]
        raise SystemExit(_diagnostico(e.code, detalle))
    for c in data.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            datos = (p.get("inlineData") or {}).get("data")
            if datos:
                return base64.b64decode(datos)
    motivo = (data.get("candidates") or [{}])[0].get("finishReason", "")
    raise SystemExit(f"Gemini respondió sin imagen{(' (' + motivo + ')') if motivo else ''}. "
                     "Suele ser el filtro de seguridad: cambia el motivo de esa escena.")


def generar(prompt, cache, key, force=False):
    """Ruta de la imagen de un prompt, generándola solo si no está en caché."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    firma = hashlib.sha1(f"{MODELO}|{TAMANO}|{prompt}".encode()).hexdigest()[:16]
    destino = cache / f"{firma}.jpg"
    if destino.exists() and not force:
        return destino, False
    crudo = _pedir(key, prompt)
    Image.open(io.BytesIO(crudo)).convert("RGB").save(destino, "JPEG", quality=92)
    (cache / f"{firma}.txt").write_text(prompt, encoding="utf-8")
    return destino, True


def _pedir_edicion(key, base, instruccion):
    """Edita una imagen ya generada. Es la única forma de tener EL MISMO objeto
    en dos estados: dos generaciones del mismo prompt dan dos objetos
    distintos, y entonces el plano no demuestra nada, solo parpadea."""
    datos = base64.b64encode(Path(base).read_bytes()).decode()
    cuerpo = {
        "contents": [{"parts": [
            {"inlineData": {"mimeType": "image/jpeg", "data": datos}},
            {"text": instruccion.strip().rstrip(".") +
             ". Keep the exact same object, materials, camera, framing and lighting; "
             "change only what is described. No text, no letters, no numbers."},
        ]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": "9:16", "imageSize": TAMANO}},
    }
    req = urllib.request.Request(
        ENDPOINT.format(MODELO), data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")[:400]
        raise SystemExit(_diagnostico(e.code, detalle))
    for c in data.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            datos = (p.get("inlineData") or {}).get("data")
            if datos:
                return base64.b64decode(datos)
    raise SystemExit("Gemini no devolvió la imagen editada.")


def editar(base, instruccion, cache, key, force=False):
    """Segundo estado del objeto, a partir de la imagen ya generada."""
    cache = Path(cache)
    firma = hashlib.sha1(f"{MODELO}|{TAMANO}|{Path(base).name}|{instruccion}".encode()
                         ).hexdigest()[:16]
    destino = cache / f"{firma}.jpg"
    if destino.exists() and not force:
        return destino, False
    crudo = _pedir_edicion(key, base, instruccion)
    Image.open(io.BytesIO(crudo)).convert("RGB").save(destino, "JPEG", quality=92)
    (cache / f"{firma}.txt").write_text(f"[edición de {Path(base).name}]\n{instruccion}",
                                        encoding="utf-8")
    return destino, True


# ---- máscara del objeto (Vision de macOS) --------------------------------
def mascara(ruta):
    """Máscara del objeto en primer plano (L, blanco = objeto), o None si
    Vision no encuentra ninguno —lo normal en una imagen abstracta—.

    Con ella el paralaje deja de ser un truco de luminancia: el objeto se
    mueve de verdad contra su fondo, que es lo que hace que una foto de
    estudio se vea como una toma con cámara."""
    ruta = Path(ruta)
    cache = ruta.with_suffix(".mascara.png")
    nada = ruta.with_suffix(".sinobjeto")
    if nada.exists():
        return None
    if cache.exists():
        return Image.open(cache).convert("L")
    script = Path(__file__).resolve().parent / "mascara.swift"
    if not script.exists() or not shutil.which("swift"):
        return None
    r = subprocess.run(["swift", str(script), str(ruta), str(cache)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        nada.touch()
        return None
    if r.returncode or not cache.exists():
        print(f"  ⚠ sin máscara para {ruta.name}: "
              f"{(r.stdout or r.stderr or '').strip()[-160:]}", flush=True)
        return None
    return Image.open(cache).convert("L")


def faltantes(prompts, cache, force=False):
    """Cuántas imágenes habría que pagar. Se dice antes de empezar: seis
    imágenes a 2K no son gratis y el usuario decide si vale la pena."""
    cache = Path(cache)
    if force:
        return len(prompts)
    n = 0
    for p in prompts:
        firma = hashlib.sha1(f"{MODELO}|{TAMANO}|{p}".encode()).hexdigest()[:16]
        if not (cache / f"{firma}.jpg").exists():
            n += 1
    return n
