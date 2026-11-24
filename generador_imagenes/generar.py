#!/usr/bin/env python3
"""
Genera un carrusel de Instagram (6 PNG de 1080x1350, formato 4:5) a partir de un archivo
de contenido JSON. El diseño (marca Savia Raíz) está separado del contenido.

Uso:
  python generar.py contenido/mcp.json                 # -> salida/mcp/mcp-01.png ...
  python generar.py contenido/mcp.json --salida ./out  # carpeta de salida distinta

El logo se toma de ../assets/logo.png y se convierte a versión clara para el
fondo oscuro automáticamente.
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from paletas import (
    INK as INK_HEX, MUTED as MUTED_HEX, BODY as BODY_HEX, STRONG as STRONG_HEX,
    hex_a_rgb, elegir_paleta,
)

# 4:5 (1080x1350) — Instagram muestra este formato a altura completa en el
# feed; el cuadrado cede ~25% de pantalla y con ello tiempo de visualizacion.
W, H = 1080, 1350

# ---- paleta de marca ----
# Todo (fondo, acentos y los 4 tonos de texto) se asigna por carrusel en
# main(), según la paleta que le toque al slug (ver paletas.py). Los HEX de
# arriba son solo el valor por defecto (paletas oscuras) para paletas que no
# definan su propia jerarquía de texto.
BG      = None
ACCENT  = None
ACCENT2 = None
INK     = hex_a_rgb(INK_HEX)
MUTED   = hex_a_rgb(MUTED_HEX)
BODY    = hex_a_rgb(BODY_HEX)
STRONG  = hex_a_rgb(STRONG_HEX)

LOGO_PATH = os.path.join(HERE, "..", "assets", "logo.png")

# ---- fuentes (DejaVu viene con la mayoría de sistemas Linux; en macOS se usa
#      Arial/Andale Mono como respaldo. Cambia aquí si quieres Space Grotesk /
#      Inter / JetBrains Mono descargando los .ttf) ----
def _first_existing(*candidates):
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "No se encontró ninguna fuente de: " + ", ".join(candidates)
    )


SANS = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
BOLD = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
MONO = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
)


def _font(path, size):
    return ImageFont.truetype(path, size)


F_EYEBROW = _font(MONO, 25)
F_KICKER  = _font(MONO, 25)
F_TITLE   = _font(BOLD, 96)
F_H       = _font(BOLD, 62)
F_BODY    = _font(SANS, 35)
F_BODYB   = _font(BOLD, 35)
F_ONE     = _font(BOLD, 46)
F_FOOT    = _font(MONO, 24)
F_SUB     = _font(SANS, 42)
F_SWIPE   = _font(MONO, 27)
F_RAIL    = _font(MONO, 20)
F_NUMBIG  = _font(BOLD, 46)
F_NUMSM   = _font(MONO, 22)

# Altura fija del encabezado en las diapositivas de contenido: mantiene el
# ritmo al deslizar. La portada va centrada aparte (no lleva kicker).
ANCLA  = 230

RAIL_X = 118
CX     = 176
CW     = W - CX - 84


def cargar_logo_recoloreado():
    """Extrae la silueta del logo negro-sobre-blanco (por luminancia) y la
    recolorea con el INK activo — blanco/claro para paletas oscuras, oscuro
    para la paleta "blanco". Se llama en main(), después de fijar INK según
    la paleta del carrusel, no al importar el módulo."""
    im = Image.open(LOGO_PATH).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    alpha = np.clip((255 - lum) * 1.5, 0, 255)
    out = np.zeros_like(arr)
    out[:, :, 0], out[:, :, 1], out[:, :, 2] = INK
    out[:, :, 3] = alpha
    w = Image.fromarray(out.astype(np.uint8), "RGBA")
    return w.crop(w.getbbox())


LOGO = None


def background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    arr = np.zeros((H, W, 3), np.float32)
    arr[:] = BG

    def glow(cx, cy, r, color, strength):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        fac = np.clip(1 - d / r, 0, 1) ** 2 * strength
        for i in range(3):
            arr[:, :, i] += color[i] * fac

    glow(880, -40, 780, ACCENT, 0.16)
    glow(-40, H + 40, 820, ACCENT2, 0.14)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, 90):
        gd.line([(x, 0), (x, H)], fill=(120, 150, 220, 13), width=1)
    for y in range(0, H, 90):
        gd.line([(0, y), (W, y)], fill=(120, 150, 220, 13), width=1)
    return Image.alpha_composite(img, grid)


def draw_rail(d, img, num, total):
    d.line([(RAIL_X, 0), (RAIL_X, H)], fill=(120, 150, 220, 60), width=2)
    cx, cy = RAIL_X // 2 + 4, 72
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=ACCENT)
    brand = "SAVIA \u00b7 RA\u00cdZ"
    tw = int(d.textlength(brand, font=F_RAIL))
    tag = Image.new("RGBA", (tw + 8, 30), (0, 0, 0, 0))
    ImageDraw.Draw(tag).text((0, 2), brand, font=F_RAIL, fill=MUTED)
    tag = tag.rotate(90, expand=True)
    img.alpha_composite(tag, (RAIL_X // 2 - tag.width // 2, 200))
    d.text((RAIL_X // 2 + 4, H - 118), num, font=F_NUMBIG, fill=ACCENT, anchor="ma")
    d.text((RAIL_X // 2 + 4, H - 66), f"/{total:02d}", font=F_NUMSM, fill=MUTED, anchor="ma")


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def alto_para(d, text, font, width, lh):
    """Alto que ocupara el parrafo, sin dibujarlo. Permite centrar el bloque
    de contenido verticalmente: en 4:5 sobra alto y anclar todo arriba deja
    un hueco muerto en el medio."""
    return len(wrap(d, text, font, width)) * lh


def centrar(top, bot, alto):
    """Y inicial para un bloque de `alto` centrado entre top y bot."""
    return top + max((bot - top - alto) // 2, 0)


def anclar(bot, alto, ancla=ANCLA, top=150):
    """Y inicial del bloque de contenido. Se ancla siempre a la misma altura
    para que el encabezado no salte al deslizar entre diapositivas, y solo
    sube si el bloque no cabria (contenido denso)."""
    return max(top, min(ancla, bot - alto))


def draw_para(d, text, font, fill, x, y, width, lh):
    for ln in wrap(d, text, font, width):
        d.text((x, y), ln, font=font, fill=fill)
        y += lh
    return y


def draw_mixed(d, segs, x, y, width, lh):
    space = d.textlength(" ", font=segs[0][1])
    cxp, cyp = x, y
    for text, font, fill in segs:
        for word in text.split():
            wlen = d.textlength(word, font=font)
            if cxp + wlen > x + width and cxp > x:
                cxp = x
                cyp += lh
            d.text((cxp, cyp), word, font=font, fill=fill)
            cxp += wlen + space
    return cyp + lh


def kicker(d, txt, y=150):
    d.line([(CX, y + 14), (CX + 34, y + 14)], fill=ACCENT, width=3)
    d.text((CX + 48, y), txt, font=F_KICKER, fill=ACCENT)
    return y + 58


def bullet(d, x, y):
    d.rounded_rectangle([x, y, x + 15, y + 15], radius=4, fill=ACCENT)


def draw_bar(img, x, y, width, height, frac):
    """Barra horizontal con degradado ACCENT->ACCENT2, recortada a `frac` (0-1)."""
    ImageDraw.Draw(img).rounded_rectangle(
        [x, y, x + width, y + height], radius=height // 2, fill=(120, 150, 220, 30)
    )
    w = max(int(width * min(max(frac, 0), 1)), height)
    grad = Image.new("RGB", (w, 1))
    for px in range(w):
        t = px / max(w - 1, 1)
        grad.putpixel((px, 0), tuple(int(ACCENT[i] + (ACCENT2[i] - ACCENT[i]) * t) for i in range(3)))
    grad = grad.resize((w, height))
    mask = Image.new("L", (w, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, height - 1], radius=height // 2, fill=255)
    img.paste(grad, (x, y), mask)


def render(slide, total):
    img = background()
    d = ImageDraw.Draw(img)
    draw_rail(d, img, slide["num"], total)
    k = slide["kind"]

    if k == "cover":
        d.text((CX, 190), slide["eyebrow"], font=F_EYEBROW, fill=MUTED)
        alto = (alto_para(d, slide["title"], F_TITLE, CW, 104)
                + 30 + alto_para(d, slide["sub"], F_SUB, CW - 40, 56))
        y = centrar(300, H - 210, alto)
        y = draw_para(d, slide["title"], F_TITLE, INK, CX, y, CW, 104)
        draw_para(d, slide["sub"], F_SUB, MUTED, CX, y + 30, CW - 40, 56)
        d.text((CX, H - 150), "Desliza  \u2192", font=F_SWIPE, fill=ACCENT)

    elif k == "text":
        alto = (58 + alto_para(d, slide["h"], F_H, CW, 72) + 8
                + 30 + alto_para(d, slide["body"], F_BODY, CW, 52))
        y = kicker(d, slide["kicker"], anclar(H - 150, alto))
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        draw_para(d, slide["body"], F_BODY, BODY, CX, y + 30, CW, 52)

    elif k == "list":
        alto = 58 + alto_para(d, slide["h"], F_H, CW, 72) + 8 + 44
        for label, rest in slide["items"]:
            alto += alto_para(d, label + " " + rest, F_BODY, CW - 46, 50) + 22
        reservado = 190 if slide.get("foot") else 150
        y = kicker(d, slide["kicker"], anclar(H - reservado, alto))
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y += 44
        for label, rest in slide["items"]:
            bullet(d, CX, y + 12)
            segs = [(label + " ", F_BODYB, STRONG), (rest, F_BODY, BODY)]
            y = draw_mixed(d, segs, CX + 46, y, CW - 46, 50) + 22
        if slide.get("foot"):
            d.text((CX, H - 132), slide["foot"], font=F_FOOT, fill=ACCENT)

    elif k == "chart":
        bars = slide["bars"]
        bar_h = 34
        alto = (58 + alto_para(d, slide["h"], F_H, CW, 72) + 8 + 46
                + len(bars) * (46 + bar_h + 12 + 30 + 28))
        reservado = 190 if slide.get("foot") else 150
        y = kicker(d, slide["kicker"], anclar(H - reservado, alto))
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y += 46
        maxv = slide.get("max") or max(b["value"] for b in bars)
        unit = slide.get("unit", "")
        for b in bars:
            d.text((CX, y), b["label"], font=F_BODYB, fill=STRONG)
            y += 46
            draw_bar(img, CX, y, CW, bar_h, b["value"] / maxv)
            # `vlabel` reemplaza la cifra impresa sin cambiar el largo de la
            # barra: sirve para rangos ("20-25%"), aproximados o multiplos.
            note = b.get("vlabel") or f'{b["value"]:g}{unit}'
            if b.get("note"):
                note += f'  \u00b7  {b["note"]}'
            d.text((CX, y + bar_h + 12), note, font=F_FOOT, fill=MUTED)
            y += bar_h + 12 + 30 + 28
        if slide.get("foot"):
            d.text((CX, H - 132), slide["foot"], font=F_FOOT, fill=ACCENT)

    elif k == "end":
        alto = (58 + alto_para(d, slide["h"], F_H, CW, 72) + 8
                + 30 + alto_para(d, slide["one"], F_ONE, CW - 20, 62))
        y = kicker(d, slide["kicker"], anclar(H - 396, alto))
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y = draw_para(d, slide["one"], F_ONE, STRONG, CX, y + 30, CW - 20, 62)
        d.line([(CX, H - 336), (W - 84, H - 336)], fill=(120, 150, 220, 70), width=2)
        seal_h = 210
        seal = LOGO.resize((int(LOGO.width * seal_h / LOGO.height), seal_h), Image.LANCZOS)
        sy = H - 262
        img.alpha_composite(seal, (CX, sy))
        tx = CX + seal.width + 44
        d.text((tx, sy + 42), "Guarda este post", font=F_BODY, fill=BODY)
        d.text((tx, sy + 96), "Un concepto cada 3 d\u00edas", font=F_BODY, fill=BODY)
        d.text((tx, sy + 152), slide["cta"][-1], font=F_FOOT, fill=ACCENT)

    return img.convert("RGB")


def main():
    global BG, ACCENT, ACCENT2, INK, MUTED, BODY, STRONG, LOGO

    ap = argparse.ArgumentParser(description="Genera un carrusel PNG desde un JSON de contenido.")
    ap.add_argument("contenido", help="Ruta al archivo JSON de contenido")
    ap.add_argument("--salida", default=None, help="Carpeta de salida (por defecto ./salida/<slug>)")
    ap.add_argument("--sin-html", action="store_true", help="No generar el HTML de revisión")
    ap.add_argument("--sin-reel", action="store_true", help="No generar el Reel de video")
    args = ap.parse_args()

    with open(args.contenido, encoding="utf-8") as f:
        data = json.load(f)

    slug = data.get("slug", "carrusel")
    paleta = elegir_paleta(slug)
    BG, ACCENT, ACCENT2 = hex_a_rgb(paleta["bg"]), hex_a_rgb(paleta["accent"]), hex_a_rgb(paleta["accent2"])
    INK    = hex_a_rgb(paleta.get("ink", INK_HEX))
    MUTED  = hex_a_rgb(paleta.get("muted", MUTED_HEX))
    BODY   = hex_a_rgb(paleta.get("body", BODY_HEX))
    STRONG = hex_a_rgb(paleta.get("strong", STRONG_HEX))
    LOGO   = cargar_logo_recoloreado()

    out = args.salida or os.path.join(HERE, "salida", slug)
    os.makedirs(out, exist_ok=True)

    total = len(data["slides"])
    for s in data["slides"]:
        p = os.path.join(out, f"{slug}-{s['num']}.png")
        render(s, total).save(p, "PNG")
        print("ok", p)
    print(f"Listo: {total} imágenes en {out} (paleta: {paleta['nombre']})")

    if not args.sin_html:
        sys.path.insert(0, os.path.join(HERE, "..", "generador_html"))
        import generar_html
        html_path = generar_html.generar(args.contenido, paleta=paleta)
        print(f"Revisión HTML: {html_path}")

    if not args.sin_reel:
        if shutil.which("ffmpeg") is None:
            print("Reel omitido: instala ffmpeg (brew install ffmpeg) para generarlo automáticamente.")
        else:
            sys.path.insert(0, os.path.join(HERE, "..", "generador_reel"))
            import generar_reel
            try:
                reel_path = generar_reel.generar(args.contenido)
                print(f"Reel: {reel_path}")
            except subprocess.CalledProcessError as e:
                print(f"Reel omitido: ffmpeg falló ({e}).")


if __name__ == "__main__":
    main()
