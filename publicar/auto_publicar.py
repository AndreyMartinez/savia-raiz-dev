#!/usr/bin/env python3
"""
Publica sin intervención el carrusel que dejó en cola la rutina de las 8:10.

Lo lanza launchd (dev.saviaraiz.publicar) los martes y jueves a las 10:05,
hora del Mac (Ciudad de México). No lo corre Claude: la rutina programada
solo genera el carrusel y escribe publicar/pendiente.json; este script es
el que publica.

Reglas:
  - Solo publica si pendiente.json es de HOY. Un pendiente viejo (el Mac
    estuvo apagado, la rutina falló a medias) se descarta y queda en el log;
    no se publica un carrusel de otro día por sorpresa.
  - Nunca publica dos veces el mismo slug (publicados.json).
  - Verifica que existan los 6 PNG y el caption antes de subir nada.
  - Credenciales en savia-raiz-dev/.env (gitignored): IG_USER_ID,
    IG_ACCESS_TOKEN, IMGBB_API_KEY. Ver .env.example.

Uso manual:
  ./.venv/bin/python3 publicar/auto_publicar.py --verificar   # revisa todo, no sube nada
  ./.venv/bin/python3 publicar/auto_publicar.py               # lo que corre launchd
"""

import os
import sys
import json
import glob
import argparse
import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PENDIENTE = os.path.join(AQUI, "pendiente.json")
PUBLICADOS = os.path.join(AQUI, "publicados.json")
ENV = os.path.join(RAIZ, ".env")
CLAVES = ("IG_USER_ID", "IG_ACCESS_TOKEN", "IMGBB_API_KEY")


def log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def cargar_env():
    """Carga .env en os.environ sin pisar lo que ya venga definido."""
    if not os.path.exists(ENV):
        return
    with open(ENV, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def leer_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def preparar(solo_lectura=False):
    """Devuelve (slug, pngs, caption) listos para publicar, o sale con motivo."""
    pend = leer_json(PENDIENTE, None)
    if not pend:
        log("No hay pendiente.json: nada que publicar hoy.")
        sys.exit(0)

    slug, fecha = pend.get("slug"), pend.get("fecha")
    hoy = datetime.date.today().isoformat()
    if fecha != hoy:
        log(f"pendiente.json es del {fecha}, no de hoy ({hoy}): se descarta sin publicar '{slug}'.")
        if not solo_lectura:
            os.rename(PENDIENTE, PENDIENTE + f".descartado-{fecha}")
        sys.exit(0)

    if slug in leer_json(PUBLICADOS, {}):
        log(f"'{slug}' ya se publicó antes: no se repite.")
        if not solo_lectura:
            os.remove(PENDIENTE)
        sys.exit(0)

    pngs = sorted(glob.glob(os.path.join(RAIZ, "generador_imagenes", "salida", slug, f"{slug}-0*.png")))
    caption_ruta = os.path.join(AQUI, "captions", f"{slug}.txt")
    if len(pngs) != 6:
        sys.exit(f"Esperaba 6 PNG de '{slug}' y hay {len(pngs)}. No se publica.")
    if not os.path.exists(caption_ruta):
        sys.exit(f"Falta el caption {caption_ruta}. No se publica.")
    with open(caption_ruta, encoding="utf-8") as f:
        caption = f.read().strip()
    if "@savia.raiz" in caption:
        sys.exit("El caption menciona @savia.raiz, que no existe. No se publica.")
    return slug, pngs, caption


def main():
    ap = argparse.ArgumentParser(description="Publica el carrusel en cola (launchd).")
    ap.add_argument("--verificar", action="store_true",
                    help="Revisa cola, archivos y credenciales sin subir ni publicar nada")
    args = ap.parse_args()

    cargar_env()
    faltan = [k for k in CLAVES if not os.environ.get(k)]

    if args.verificar:
        log(f".env: {'encontrado' if os.path.exists(ENV) else 'NO existe'} ({ENV})")
        for k in CLAVES:
            log(f"  {k}: {'definida' if os.environ.get(k) else 'FALTA'}")
        if not os.path.exists(PENDIENTE):
            log("Cola vacía (no hay pendiente.json): la rutina de las 8:10 aún no dejó nada.")
            return

    slug, pngs, caption = preparar(solo_lectura=args.verificar)
    log(f"Listo para publicar '{slug}': {len(pngs)} PNG, caption de {len(caption)} caracteres.")

    if faltan:
        sys.exit(f"Faltan credenciales en {ENV}: {', '.join(faltan)}. No se publica.")
    if args.verificar:
        log("--verificar: todo en orden; no se sube ni se publica nada.")
        return

    # Importar después de cargar .env: publicar_instagram lee las variables al importarse.
    sys.path.insert(0, AQUI)
    import publicar_instagram as ig

    log("Alojando imágenes en imgbb…")
    urls = [ig.subir_a_imgbb(p) for p in pngs]
    media_id = ig.publicar_carrusel(urls, caption)

    publicados = leer_json(PUBLICADOS, {})
    publicados[slug] = {"media_id": media_id, "publicado": datetime.datetime.now().isoformat(timespec="seconds")}
    with open(PUBLICADOS, "w", encoding="utf-8") as f:
        json.dump(publicados, f, ensure_ascii=False, indent=2)
    os.remove(PENDIENTE)
    log(f"Publicado '{slug}' (media {media_id}).")


if __name__ == "__main__":
    main()
