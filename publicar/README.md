# Publicar en Instagram (Graph API)

Publica un carrusel con un comando. Ver el docstring de `publicar_instagram.py`
y `../docs/flujo.md` para el detalle.

## Configuración (una vez)

1. Cuenta de Instagram **Profesional** (Empresa o Creador) vinculada a una página de Facebook.
2. App de Meta (https://developers.facebook.com) con el producto Instagram y el
   permiso `instagram_content_publish`.
3. Consigue `IG_USER_ID` y un `IG_ACCESS_TOKEN` de larga duración (o de System User
   para que no expire).

> Para publicar en tu **propia** cuenta no necesitas App Review: basta con darte un
> rol (Admin/Tester) en la app. El review es solo para abrirlo a terceros.

## Uso

```bash
pip install requests
export IG_USER_ID="17841400000000000"
export IG_ACCESS_TOKEN="EAAG..."
export IMGBB_API_KEY="..."   # opcional: para que el script aloje las imágenes

# Verificar sin publicar:
python publicar_instagram.py --imagenes "../generador_imagenes/salida/mcp/*.png" \
                             --caption captions/mcp.txt --dry-run

# Publicar:
python publicar_instagram.py --imagenes "../generador_imagenes/salida/mcp/*.png" \
                             --caption captions/mcp.txt
```

La API descarga las imágenes desde una URL pública, así que deben estar alojadas
(imgbb, S3, Cloudinary, GitHub raw…). Nombra los PNG en orden (`mcp-01`…`mcp-06`).

> ⚠️ El token es una credencial: guárdalo en variables de entorno o `.env`
> (ya está en `.gitignore`), nunca en el código.
