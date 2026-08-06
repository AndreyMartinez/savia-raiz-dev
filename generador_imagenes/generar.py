#!/usr/bin/env python3
"""
Genera un carrusel de Instagram (6 PNG de 1080x1080) a partir de un archivo
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
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from paletas import INK as INK_HEX, MUTED as MUTED_HEX, hex_a_rgb, elegir_paleta

W = H = 1080

# ---- paleta de marca ----
# INK/MUTED (texto) son fijos; BG/ACCENT/ACCENT2 se asignan por carrusel en
# main(), según la paleta que le toque al slug (ver paletas.py).
INK     = hex_a_rgb(INK_HEX)
MUTED   = hex_a_rgb(MUTED_HEX)
BG      = None
ACCENT  = None
ACCENT2 = None

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
F_SWIPE   = _font(MONO, 27)
F_RAIL    = _font(MONO, 20)
F_NUMBIG  = _font(BOLD, 46)
F_NUMSM   = _font(MONO, 22)

RAIL_X = 118
CX     = 176
CW     = W - CX - 84


def cargar_logo_claro():
    """Convierte el logo negro-sobre-blanco en blanco-sobre-transparente."""
    im = Image.open(LOGO_PATH).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    alpha = np.clip((255 - lum) * 1.5, 0, 255)
    out = np.zeros_like(arr)
    out[:, :, 0], out[:, :, 1], out[:, :, 2] = INK
    out[:, :, 3] = alpha
    w = Image.fromarray(out.astype(np.uint8), "RGBA")
    return w.crop(w.getbbox())


LOGO = cargar_logo_claro()


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
    glow(-40, 1120, 820, ACCENT2, 0.14)
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


def kicker(d, txt, y=120):
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
        d.text((CX, 150), slide["eyebrow"], font=F_EYEBROW, fill=MUTED)
        y = draw_para(d, slide["title"], F_TITLE, INK, CX, 300, CW, 104)
        draw_para(d, slide["sub"], F_BODY, MUTED, CX, y + 26, CW - 40, 48)
        d.text((CX, H - 150), "Desliza  \u2192", font=F_SWIPE, fill=ACCENT)

    elif k == "text":
        y = kicker(d, slide["kicker"])
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        draw_para(d, slide["body"], F_BODY, (211, 220, 240), CX, y + 30, CW, 52)

    elif k == "list":
        y = kicker(d, slide["kicker"])
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y += 44
        for label, rest in slide["items"]:
            bullet(d, CX, y + 12)
            segs = [(label + " ", F_BODYB, (255, 255, 255)), (rest, F_BODY, (211, 220, 240))]
            y = draw_mixed(d, segs, CX + 46, y, CW - 46, 50) + 22
        if slide.get("foot"):
            d.text((CX, H - 132), slide["foot"], font=F_FOOT, fill=ACCENT)

    elif k == "chart":
        y = kicker(d, slide["kicker"])
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y += 46
        bars = slide["bars"]
        maxv = slide.get("max") or max(b["value"] for b in bars)
        unit = slide.get("unit", "")
        bar_h = 34
        for b in bars:
            d.text((CX, y), b["label"], font=F_BODYB, fill=(255, 255, 255))
            y += 46
            draw_bar(img, CX, y, CW, bar_h, b["value"] / maxv)
            note = f'{b["value"]:g}{unit}'
            if b.get("note"):
                note += f'  ·  {b["note"]}'
            d.text((CX, y + bar_h + 12), note, font=F_FOOT, fill=MUTED)
            y += bar_h + 12 + 30 + 28
        if slide.get("foot"):
            d.text((CX, H - 132), slide["foot"], font=F_FOOT, fill=ACCENT)

    elif k == "end":
        y = kicker(d, slide["kicker"])
        y = draw_para(d, slide["h"], F_H, INK, CX, y + 8, CW, 72)
        y = draw_para(d, slide["one"], F_ONE, (255, 255, 255), CX, y + 30, CW - 20, 62)
        d.line([(CX, H - 336), (W - 84, H - 336)], fill=(120, 150, 220, 70), width=2)
        seal_h = 210
        seal = LOGO.resize((int(LOGO.width * seal_h / LOGO.height), seal_h), Image.LANCZOS)
        sy = H - 262
        img.alpha_composite(seal, (CX, sy))
        tx = CX + seal.width + 44
        d.text((tx, sy + 42), "Guarda este post", font=F_BODY, fill=(211, 220, 240))
        d.text((tx, sy + 96), "Un concepto cada 3 d\u00edas", font=F_BODY, fill=(211, 220, 240))
        d.text((tx, sy + 152), slide["cta"][-1], font=F_FOOT, fill=ACCENT)

    return img.convert("RGB")


def main():
    global BG, ACCENT, ACCENT2

    ap = argparse.ArgumentParser(description="Genera un carrusel PNG desde un JSON de contenido.")
    ap.add_argument("contenido", help="Ruta al archivo JSON de contenido")
    ap.add_argument("--salida", default=None, help="Carpeta de salida (por defecto ./salida/<slug>)")
    ap.add_argument("--sin-html", action="store_true", help="No generar el HTML de revisión")
    args = ap.parse_args()

    with open(args.contenido, encoding="utf-8") as f:
        data = json.load(f)

    slug = data.get("slug", "carrusel")
    paleta = elegir_paleta(slug)
    BG, ACCENT, ACCENT2 = hex_a_rgb(paleta["bg"]), hex_a_rgb(paleta["accent"]), hex_a_rgb(paleta["accent2"])

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


if __name__ == "__main__":
    main()
