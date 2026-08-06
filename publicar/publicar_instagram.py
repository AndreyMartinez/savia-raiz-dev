#!/usr/bin/env python3
"""
Publica un carrusel en Instagram usando la Graph API (content publishing).

Flujo (modelo de contenedores de Meta):
  1. Sube cada imagen a un host público -> obtiene una URL.
  2. Crea un contenedor "hijo" por cada imagen (is_carousel_item=true).
  3. Crea un contenedor "padre" tipo CAROUSEL con los hijos + el caption.
  4. Espera a que el contenedor esté FINISHED y publica.

Requisitos:
  - Cuenta de Instagram PROFESIONAL (Empresa o Creador) vinculada a una página de Facebook.
  - App de Meta con permiso instagram_content_publish (ver README).
  - Variables de entorno:
      IG_USER_ID          -> ID de la cuenta profesional de Instagram
      IG_ACCESS_TOKEN     -> token de acceso (de larga duración o de system user)
      IG_GRAPH_VERSION    -> opcional, por defecto v22.0 (Meta va en v25.0 en 2026; sube si hace falta)
      IMGBB_API_KEY       -> opcional, solo si dejas que el script aloje las imágenes en imgbb

Uso:
  export IG_USER_ID="17841400000000000"
  export IG_ACCESS_TOKEN="EAAG..."
  export IMGBB_API_KEY="tu_clave"      # si usas imgbb para alojar
  python publicar_instagram.py --imagenes "carrusel-mcp/*.png" --caption caption_mcp.txt

  # o si ya tienes las imágenes alojadas y solo pasas URLs:
  python publicar_instagram.py --urls https://.../1.png https://.../2.png --caption caption_mcp.txt
"""

import os
import sys
import time
import glob
import argparse
import requests

VERSION = os.environ.get("IG_GRAPH_VERSION", "v22.0")
HOST = f"https://graph.facebook.com/{VERSION}"
IG_USER_ID = os.environ.get("IG_USER_ID")
TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")


# ----------------------------------------------------------------------
# Utilidades de la Graph API
# ----------------------------------------------------------------------
def _post(path, data):
    r = requests.post(f"{HOST}/{path}", params={"access_token": TOKEN}, data=data, timeout=60)
    _check(r)
    return r.json()


def _get(path, params):
    params = {**params, "access_token": TOKEN}
    r = requests.get(f"{HOST}/{path}", params=params, timeout=60)
    _check(r)
    return r.json()


def _check(r):
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
        except Exception:
            err = {"message": r.text}
        raise SystemExit(
            f"\n[ERROR Graph API] {r.status_code}: {err.get('message')}\n"
            f"  type={err.get('type')} code={err.get('code')} "
            f"subcode={err.get('error_subcode')}\n"
            f"  Revisa el token, los permisos y que la cuenta sea profesional.\n"
        )


# ----------------------------------------------------------------------
# Alojamiento de imágenes (la API necesita URLs públicas)
# ----------------------------------------------------------------------
def subir_a_imgbb(path):
    """Sube una imagen local a imgbb y devuelve su URL pública."""
    if not IMGBB_API_KEY:
        raise SystemExit(
            "Falta IMGBB_API_KEY. La API de Instagram necesita URLs públicas.\n"
            "Opciones: define IMGBB_API_KEY, o aloja tú las imágenes (S3, Cloudinary, "
            "GitHub raw, tu CDN) y pásalas con --urls."
        )
    with open(path, "rb") as f:
        r = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": f},
            timeout=120,
        )
    r.raise_for_status()
    url = r.json()["data"]["url"]
    print(f"  · subida: {os.path.basename(path)} -> {url}")
    return url


# ----------------------------------------------------------------------
# Publicación del carrusel
# ----------------------------------------------------------------------
def esperar_finished(container_id, intentos=20, espera=3):
    """Sondea el estado del contenedor hasta que esté FINISHED."""
    for _ in range(intentos):
        estado = _get(container_id, {"fields": "status_code"}).get("status_code")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise SystemExit(f"El contenedor {container_id} terminó en estado {estado}.")
        time.sleep(espera)
    raise SystemExit(f"Tiempo agotado esperando al contenedor {container_id}.")


def crear_hijo(image_url):
    res = _post(f"{IG_USER_ID}/media", {"image_url": image_url, "is_carousel_item": "true"})
    return res["id"]


def crear_padre(hijos, caption):
    res = _post(
        f"{IG_USER_ID}/media",
        {"media_type": "CAROUSEL", "children": ",".join(hijos), "caption": caption},
    )
    return res["id"]


def publicar(creation_id):
    res = _post(f"{IG_USER_ID}/media_publish", {"creation_id": creation_id})
    return res["id"]


def limite_restante():
    try:
        q = _get(f"{IG_USER_ID}/content_publishing_limit", {"fields": "quota_usage,config"})
        d = q["data"][0]
        print(f"  · publicaciones usadas en 24h: {d.get('quota_usage')}/"
              f"{d.get('config', {}).get('quota_total', 50)}")
    except Exception:
        pass  # informativo, no crítico


def publicar_carrusel(urls, caption):
    if not (IG_USER_ID and TOKEN):
        raise SystemExit("Faltan IG_USER_ID y/o IG_ACCESS_TOKEN en el entorno.")
    if not 2 <= len(urls) <= 10:
        raise SystemExit(f"Un carrusel necesita entre 2 y 10 imágenes (tienes {len(urls)}).")

    print(f"\nInstagram Graph API {VERSION}")
    limite_restante()

    print("\n[1/3] Creando contenedores por imagen…")
    hijos = [crear_hijo(u) for u in urls]

    print("[2/3] Creando el contenedor del carrusel…")
    padre = crear_padre(hijos, caption)
    esperar_finished(padre)

    print("[3/3] Publicando…")
    media_id = publicar(padre)
    print(f"\n✅ Publicado. Media ID: {media_id}\n")
    return media_id


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Publica un carrusel en Instagram (Graph API).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--imagenes", help="Patrón glob de imágenes locales, p.ej. 'carrusel/*.png'")
    g.add_argument("--urls", nargs="+", help="URLs públicas ya alojadas, en orden")
    ap.add_argument("--caption", required=True, help="Ruta a un archivo .txt con el caption")
    ap.add_argument("--dry-run", action="store_true", help="Prepara todo pero NO publica")
    args = ap.parse_args()

    with open(args.caption, encoding="utf-8") as f:
        caption = f.read().strip()

    if args.urls:
        urls = args.urls
    else:
        paths = sorted(glob.glob(args.imagenes))
        if not paths:
            raise SystemExit(f"No se encontraron imágenes con el patrón: {args.imagenes}")
        print(f"Imágenes ({len(paths)}): {[os.path.basename(p) for p in paths]}")
        print("Alojando imágenes…")
        urls = [subir_a_imgbb(p) for p in paths]

    if args.dry_run:
        print("\n[dry-run] URLs listas y caption cargado; no se publica nada.")
        print("Caption:\n" + caption)
        return

    publicar_carrusel(urls, caption)


if __name__ == "__main__":
    main()
