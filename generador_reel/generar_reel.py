#!/usr/bin/env python3
"""
Convierte un carrusel ya generado (PNG de generador_imagenes/salida/<slug>/)
en un Reel de video: zoom lento (Ken Burns) por diapositiva, transición de
deslizamiento entre diapositivas (el gesto de "swipe" que ya sugiere la
portada) y un fondo musical ambiental generado por síntesis (sin voz, sin
depender de ninguna librería de música con licencia).

Importante sobre el audio: esto es un pad sintetizado con osciladores
simples (ffmpeg lavfi), no una canción real — no hay ningún modelo de
generación musical conectado en esta sesión. Suena a fondo ambiental
discreto, no a producción musical. Si al publicar quieres algo con más
calidad real, la opción recomendada es usar el audio con licencia que
ofrece el propio Instagram al subir el Reel (además ayuda al alcance).
Usa --sin-musica para dejar el video mudo si prefieres agregarle audio ahí.

Requiere ffmpeg (brew install ffmpeg).

Uso:
  python generar_reel.py ../generador_imagenes/contenido/mcp.json
  python generar_reel.py ../generador_imagenes/contenido/mcp.json --duracion 3.5 --sin-musica
"""
import os
import sys
import json
import glob
import shutil
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 1080
FPS = 30
XFADE = 0.5             # duración de la transición de deslizamiento entre diapositivas
ACORDE = [110.00, 130.81, 164.81, 196.00]  # A2 C3 E3 G3 — Am7, cálido y discreto


def _clip(png_path, out_path, duracion, zoom_max):
    zoom_rate = (zoom_max - 1) / (duracion * FPS)
    vf = (
        f"scale={W*3}:{H*3},"
        f"zoompan=z='min(zoom+{zoom_rate:.6f},{zoom_max})':d=1:s={W}x{H}:fps={FPS},"
        f"format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", png_path,
        "-t", f"{duracion:.3f}", "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _armar_video(clips, duracion_clip, salida_muda, transicion="slideleft"):
    inputs = []
    for c in clips:
        inputs += ["-i", c]

    partes = []
    prev_v = "0:v"
    acumulado = duracion_clip
    for i in range(1, len(clips)):
        offset = acumulado - XFADE
        acumulado = acumulado + duracion_clip - XFADE
        v_out = f"v{i}"
        partes.append(f"[{prev_v}][{i}:v]xfade=transition={transicion}:duration={XFADE}:offset={offset:.3f}[{v_out}]")
        prev_v = v_out

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(partes),
        "-map", f"[{prev_v}]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        salida_muda,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return acumulado


def _musica_fondo(duracion, out_path):
    """Pad ambiental sintetizado (osciladores simples + trémolo + filtro
    pasabajos), no una pista real. Volumen bajo a propósito: es fondo, no
    protagonista."""
    inputs = []
    for f in ACORDE:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={duracion:.3f}"]
    pesos = " ".join(["1", "0.8", "0.7", "0.6"][:len(ACORDE)])
    fade_out_st = max(duracion - 1.5, 0)
    filtro = (
        f"amix=inputs={len(ACORDE)}:duration=longest:weights={pesos},"
        f"tremolo=f=0.15:d=0.4,"
        f"lowpass=f=2000,"
        f"volume=0.2,"
        f"afade=t=in:d=1.2,"
        f"afade=t=out:st={fade_out_st:.3f}:d=1.5"
    )
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filtro, "-c:a", "aac", out_path]
    subprocess.run(cmd, check=True, capture_output=True)


def generar(contenido_path, duracion=3.2, zoom_max=1.08, musica=True, salida=None):
    with open(contenido_path, encoding="utf-8") as f:
        data = json.load(f)
    slug = data.get("slug", "carrusel")

    png_dir = os.path.join(HERE, "..", "generador_imagenes", "salida", slug)
    pngs = sorted(glob.glob(os.path.join(png_dir, f"{slug}-*.png")))
    if not pngs:
        raise SystemExit(f"No hay PNG en {png_dir} — corre antes generador_imagenes/generar.py")

    tmp = os.path.join(HERE, f".tmp_{slug}")
    os.makedirs(tmp, exist_ok=True)
    try:
        clips = []
        for i, png in enumerate(pngs):
            clip_path = os.path.join(tmp, f"clip_{i:02d}.mp4")
            _clip(png, clip_path, duracion, zoom_max)
            clips.append(clip_path)
            print(f"ok clip {i + 1}/{len(pngs)}: {os.path.basename(png)}")

        muda = os.path.join(tmp, "muda.mp4")
        total = _armar_video(clips, duracion, muda)

        salida = salida or os.path.join(HERE, f"{slug}.mp4")
        if musica:
            audio_path = os.path.join(tmp, "musica.aac")
            _musica_fondo(total, audio_path)
            subprocess.run(
                ["ffmpeg", "-y", "-i", muda, "-i", audio_path,
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", salida],
                check=True, capture_output=True,
            )
        else:
            shutil.copy(muda, salida)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"Listo: {salida} (~{total:.1f}s, {len(pngs)} diapositivas{'' if musica else ', sin audio'})")
    return salida


def main():
    ap = argparse.ArgumentParser(description="Convierte un carrusel en Reel de video con transición de deslizamiento y fondo musical sintetizado.")
    ap.add_argument("contenido", help="Ruta al JSON de contenido del carrusel (ya debe tener sus PNG generados)")
    ap.add_argument("--duracion", type=float, default=3.2, help="Segundos por diapositiva (default 3.2)")
    ap.add_argument("--zoom", type=float, default=1.08, help="Zoom máximo por diapositiva (default 1.08)")
    ap.add_argument("--sin-musica", action="store_true", help="Deja el video mudo (para agregarle audio con licencia al publicar)")
    ap.add_argument("--salida", default=None, help="Ruta del .mp4 de salida (default ./<slug>.mp4)")
    args = ap.parse_args()
    generar(args.contenido, args.duracion, args.zoom, not args.sin_musica, args.salida)


if __name__ == "__main__":
    main()
