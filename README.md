# Savia Raíz · Dev — Fábrica de contenido para Instagram

Sistema para producir y publicar carruseles de Instagram sobre **desarrollo de
software, IA y tooling (MCP/Skills)**, en español, con la identidad de Savia Raíz.

Cubre el flujo completo: encontrar el tema → generar las imágenes con marca →
escribir el caption → publicar (manual o automático vía API).

```
savia-raiz-dev/
├── generador_html/         Vista previa editable en el navegador + descarga PNG
│   └── carrusel-mcp.html
├── generador_imagenes/     Generación de PNG por lotes (Python + Pillow)
│   ├── generar.py
│   ├── contenido/          Contenido de cada carrusel en JSON (datos ≠ diseño)
│   │   └── mcp.json
│   └── salida/             PNG generados (ignorado por git)
├── publicar/               Publicación en Instagram vía Graph API
│   ├── publicar_instagram.py
│   └── captions/
│       └── mcp.txt
├── assets/
│   ├── logo.png            Logo original de Savia Raíz
│   └── logo-white.png      Versión clara para fondos oscuros
├── docs/
│   └── flujo.md            El flujo de trabajo (fuentes, Notion, cadencia)
├── requirements.txt
└── README.md
```

## Dos formas de generar las imágenes

**A) Rápida y visual — `generador_html/carrusel-mcp.html`**
Ábrelo en el navegador. Editas cualquier texto haciendo clic, ves el resultado
al instante y descargas cada diapositiva (o todas) en PNG 1080×1080. Ideal para
retoques y para ver antes de publicar. No requiere instalar nada.

**B) Por lotes — `generador_imagenes/generar.py`**
Define el contenido en un JSON y genera las 6 imágenes de una. Ideal para
producir varios carruseles en tanda o automatizar.

```bash
pip install -r requirements.txt
cd generador_imagenes
python generar.py contenido/mcp.json
# -> salida/mcp/mcp-01.png … mcp-06.png
# -> también genera ../generador_html/mcp.html para revisar antes de publicar
```

Para un carrusel nuevo, copia `contenido/mcp.json`, cámbiale el `slug` y los
textos, y vuelve a ejecutar. El diseño (marca Savia Raíz) se aplica solo.

Cada vez que `generar.py` produce las imágenes, genera automáticamente el
HTML de revisión equivalente en `generador_html/<slug>.html` (mismo motor
que la opción A, editable en el navegador). Es el punto de revisión antes
de publicar — no lo saltes. Para regenerarlo a mano: `python
generador_html/generar_html.py contenido/<slug>.json`.

## Paleta de color

Cada carrusel nuevo recibe la siguiente paleta en rotación (ver
`paletas.py` / `paletas_asignadas.json`), así que nunca coincide con la del
carrusel anterior. Esa asignación queda guardada para siempre: volver a
generar el mismo `slug` reproduce la misma paleta. La combinación de
tipografía/layout/marca se mantiene fija; solo alternan los tonos de fondo
y los dos colores de acento.

## Publicar en Instagram

Ver `publicar/` y la sección de API más abajo. Resumen:

```bash
pip install requests
export IG_USER_ID="…"; export IG_ACCESS_TOKEN="…"; export IMGBB_API_KEY="…"
cd publicar
python publicar_instagram.py --imagenes "../generador_imagenes/salida/mcp/*.png" \
                             --caption captions/mcp.txt --dry-run
```

Requisitos: cuenta de Instagram **Profesional** vinculada a una página de
Facebook, app de Meta con permiso `instagram_content_publish`, y las imágenes
alojadas en una URL pública (la API las descarga; el script puede subirlas a
imgbb). Detalle completo en el código y en `docs/flujo.md`. Límite: 50
publicaciones por cuenta cada 24 h (un carrusel = 1).

## Estética

Fondo navy con degradados azul→violeta, rejilla técnica, riel lateral con la
marca y sello de Savia Raíz al cierre. Tipografías: Space Grotesk (títulos),
Inter (cuerpo), JetBrains Mono (etiquetas). En el generador Python se usan
fuentes DejaVu por defecto; cámbialas por los `.ttf` reales si quieres paridad
exacta con el HTML.

## Licencia

MIT — ver `LICENSE`.
