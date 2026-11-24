#!/usr/bin/env python3
"""Colchón musical del Reel, generado con Lyria.

Antes era síntesis con ffmpeg (cuatro osciladores y un trémolo): sonaba a
fondo discreto, pero a fondo sintetizado. `lyria-3-pro-preview` entrega una
pista real de ~62 s, que alcanza para un Reel entero sin empalmes; si se usa el
modelo de 30 s (`lyria-3-clip-preview`, vía GEMINI_MUSIC_MODEL) la pista se
encadena consigo misma con un cruce largo, y en música ambiental sin estructura
marcada no se oye el empalme.

Si Lyria falla o no está disponible, se vuelve solo a la síntesis: quedarse sin
música por un error de red sería peor que un pad sencillo.
"""
import base64
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

MODELO = os.environ.get("GEMINI_MUSIC_MODEL", "lyria-3-pro-preview")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
CRUCE = 3.0          # cruce entre una vuelta y la siguiente
VOLUMEN = 0.16       # el colchón va debajo de la voz, no al lado

# Qué música le queda a cada estilo de narración. El error clásico es pedir
# algo "épico": compite con la voz y cansa en quince segundos.
POR_ESTILO = {
    "noticia": "Minimal modern electronic underscore, steady subtle pulse, clean low "
               "synth bass, restrained, no vocals, no melody in the foreground.",
    "explicativo": "Warm minimal ambient bed, soft analog pads, gentle movement, "
                   "calm and unhurried, no vocals, no drums in the foreground.",
    "energico": "Upbeat minimal electronic groove, light percussion, forward momentum, "
                "bright but not busy, no vocals.",
    "cercano": "Intimate warm ambient texture, soft felt piano far in the background, "
               "slow, close and quiet, no vocals.",
    "suspenso": "Dark minimal ambient tension, low drone, sparse pulses, restrained, "
                "no vocals, no impacts.",
    "motivacional": "Warm uplifting minimal underscore, soft sustained strings and pads, "
                    "patient build, dignified, no vocals.",
}
BASE = (" Instrumental background music for a short vertical video: it sits under a "
        "narrator's voice, so keep the midrange clear and nothing attention-grabbing. "
        "Loopable, consistent texture from start to end.")


def prompt_de(estilo, pedido=None):
    if pedido:
        return pedido.strip().rstrip(".") + "." + BASE
    return POR_ESTILO.get(estilo, POR_ESTILO["explicativo"]) + BASE


def _pedir(key, prompt):
    cuerpo = {"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseModalities": ["AUDIO"]}}
    req = urllib.request.Request(
        ENDPOINT.format(MODELO), data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
    for c in data.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            datos = (p.get("inlineData") or {}).get("data")
            if datos:
                return base64.b64decode(datos)
    raise RuntimeError("Lyria respondió sin audio")


def generar(prompt, cache, key, force=False):
    """Ruta de la pista de un prompt (la pide solo si no está en caché)."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    firma = hashlib.sha1(f"{MODELO}|{prompt}".encode()).hexdigest()[:16]
    destino = cache / f"{firma}.mp3"
    if destino.exists() and not force:
        return destino, False
    destino.write_bytes(_pedir(key, prompt))
    (cache / f"{firma}.txt").write_text(prompt, encoding="utf-8")
    return destino, True


def _duracion(ruta):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", str(ruta)])
    return float(out.decode().strip())


def a_medida(pista, total, salida, volumen=VOLUMEN):
    """Estira la pista hasta `total` encadenándola consigo misma con un cruce,
    y la deja al volumen de colchón con entrada y salida."""
    dur = _duracion(pista)
    vueltas = max(1, int((total - CRUCE) // max(1.0, dur - CRUCE)) + 1)
    entradas, filtros = [], []
    for i in range(vueltas):
        entradas += ["-i", str(pista)]
        filtros.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono[a{i}]")
    actual = "a0"
    for i in range(1, vueltas):
        nuevo = f"x{i}"
        filtros.append(f"[{actual}][a{i}]acrossfade=d={CRUCE}:c1=tri:c2=tri[{nuevo}]")
        actual = nuevo
    filtros.append(
        f"[{actual}]volume={volumen},atrim=duration={total:.3f},"
        f"afade=t=in:d=1.5,afade=t=out:st={max(0, total - 2.0):.3f}:d=2.0,"
        f"apad=whole_dur={total:.3f}[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas,
                    "-filter_complex", ";".join(filtros), "-map", "[out]",
                    "-ac", "1", "-ar", "48000", str(salida)], check=True)
    return salida
