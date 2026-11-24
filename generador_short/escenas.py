#!/usr/bin/env python3
"""Motor de animación del Reel vertical (1080×1920): escenas, elementos y fondo.

A diferencia de `generador_reel/` —que toma los PNG 4:5 del carrusel y les hace
zoom— aquí cada cuadro se dibuja desde cero, así que el texto puede entrar,
las barras crecer y los números subir. El precio es tiempo de CPU, y por eso
cada elemento se dibuja UNA vez en su propia capa RGBA y cada cuadro solo la
pega con un desplazamiento y una opacidad: lo caro (medir y rasterizar texto)
no se repite 1500 veces.

Zonas seguras de Reels: Instagram tapa la franja de arriba (~120 px) y el
cuarto de abajo (~480 px: descripción, audio y botones). Todo lo que se tiene
que leer vive entre y=290 y y=1420.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import paletas  # noqa: E402
from paletas import hex_a_rgb  # noqa: E402

# Las dos cuentas tienen su propio paletas.py y no definen los mismos tonos de
# texto: Savia Raíz trae los cuatro (ink/muted/body/strong) y Ciencia del Ánimo
# solo ink/muted. Lo que falte se deriva, para que este motor sirva igual en las
# dos sin tener dos versiones del archivo.
INK_HEX = paletas.INK
MUTED_HEX = paletas.MUTED
BODY_HEX = getattr(paletas, "BODY", None)
STRONG_HEX = getattr(paletas, "STRONG", None)

W, H, FPS = 1080, 1920, 30
MARGEN = 84
ANCHO = W - MARGEN * 2
BANDA_Y0, BANDA_Y1 = 330, 1170      # donde vive el contenido de la escena
SUB_Y = 1390                         # banda de subtítulos, abajo y discreta
BANDA_VISUAL = (240, 860)            # el texto vive arriba; el objeto, debajo
REJILLA = 90                         # periodo de la rejilla del fondo (px)
HOLGURA = 120                        # margen extra del fondo, para el vaivén

# La paleta se fija por Reel en configurar(); estos son los valores por defecto.
BG = hex_a_rgb("#0B1326")
ACCENT = hex_a_rgb("#5B8CFF")
ACCENT2 = hex_a_rgb("#9B6BFF")
INK = hex_a_rgb(INK_HEX)
MUTED = hex_a_rgb(MUTED_HEX)


def _entre(a, b, k):
    """Color intermedio: sirve para el tono de párrafo cuando la paleta no lo
    define (entre el texto principal y el secundario)."""
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def _luminancia(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


BODY = hex_a_rgb(BODY_HEX) if BODY_HEX else _entre(INK, MUTED, 0.45)
STRONG = hex_a_rgb(STRONG_HEX) if STRONG_HEX else INK
MARCA = "SAVIA · RAÍZ"
LOGO = None
CLARO = False  # paleta de fondo claro: cambia el contraste de los subtítulos


def _primera(*rutas):
    for r in rutas:
        if os.path.isfile(r):
            return r
    raise FileNotFoundError("No se encontró ninguna fuente de: " + ", ".join(rutas))


SANS = _primera("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf")
BOLD = _primera("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
MONO = _primera("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/System/Library/Fonts/Supplemental/Andale Mono.ttf")

# Tipografía en vertical: más grande que en el carrusel, porque el Reel se ve
# en movimiento y a veces de lejos.
F_GANCHO = ImageFont.truetype(BOLD, 100)
F_H = ImageFont.truetype(BOLD, 70)
F_H2 = ImageFont.truetype(BOLD, 60)
F_TEXTO = ImageFont.truetype(SANS, 44)
F_TEXTOB = ImageFont.truetype(BOLD, 44)
F_ITEM = ImageFont.truetype(SANS, 42)
F_ITEMB = ImageFont.truetype(BOLD, 42)
F_KICKER = ImageFont.truetype(MONO, 28)
F_PIE = ImageFont.truetype(MONO, 24)
F_ETIQUETA = ImageFont.truetype(SANS, 34)
F_VALOR = ImageFont.truetype(BOLD, 54)
F_NOTA = ImageFont.truetype(MONO, 24)
F_CITA = ImageFont.truetype(BOLD, 62)
F_CTA = ImageFont.truetype(SANS, 40)
F_HANDLE = ImageFont.truetype(MONO, 36)
F_SUB = ImageFont.truetype(BOLD, 44)
F_MARCA = ImageFont.truetype(MONO, 22)
# Escenas visuales: la imagen es la protagonista y el texto es un titular, no
# un párrafo. Por eso son cuerpos enormes y pocas palabras.
F_FRASE = ImageFont.truetype(BOLD, 112)
F_NUM = ImageFont.truetype(BOLD, 230)
F_NUM2 = ImageFont.truetype(BOLD, 150)
F_NUM3 = ImageFont.truetype(BOLD, 104)
F_ETQ = ImageFont.truetype(MONO, 30)
F_NOTA2 = ImageFont.truetype(SANS, 34)
F_LINEA = ImageFont.truetype(SANS, 40)


def configurar(paleta, marca=None, logo=None):
    """Fija los colores del Reel (la paleta que le tocó al slug) y la marca."""
    global BG, ACCENT, ACCENT2, INK, MUTED, BODY, STRONG, MARCA, LOGO, CLARO
    BG = hex_a_rgb(paleta["bg"])
    ACCENT = hex_a_rgb(paleta["accent"])
    ACCENT2 = hex_a_rgb(paleta["accent2"])
    INK = hex_a_rgb(paleta.get("ink", INK_HEX))
    MUTED = hex_a_rgb(paleta.get("muted", MUTED_HEX))
    BODY = hex_a_rgb(paleta["body"]) if paleta.get("body") else (
        hex_a_rgb(BODY_HEX) if BODY_HEX else _entre(INK, MUTED, 0.45))
    STRONG = hex_a_rgb(paleta["strong"]) if paleta.get("strong") else (
        hex_a_rgb(STRONG_HEX) if STRONG_HEX else INK)
    # Fondo claro: se decide por el color, no por una bandera, porque no todas
    # las paletas la traen (las de Ciencia del Ánimo son todas claras).
    CLARO = bool(paleta.get("claro")) or _luminancia(BG) > 140
    globals()["_MARCA_CAPA"] = None   # la filigrana se rasteriza con la paleta nueva
    _MEMO_SUB.clear()
    if marca:
        MARCA = marca
    LOGO = _logo(logo) if logo else None


def _logo(ruta):
    """Silueta del logo recoloreada con el INK activo (igual que en el carrusel)."""
    if not ruta or not os.path.isfile(ruta):
        return None
    im = Image.open(ruta).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    out = np.zeros_like(arr)
    out[:, :, 0], out[:, :, 1], out[:, :, 2] = INK
    out[:, :, 3] = np.clip((255 - lum) * 1.5, 0, 255)
    im = Image.fromarray(out.astype(np.uint8), "RGBA")
    return im.crop(im.getbbox())


# ---- curvas de animación --------------------------------------------------
def recortar(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def suave(p):
    """ease-out cúbico: entra rápido y frena. Es la que se siente natural
    cuando algo 'aterriza' en su lugar."""
    return 1 - (1 - p) ** 3


def muy_suave(p):
    """ease-out exponencial, para lo que debe sentirse decidido (barras)."""
    return 1.0 if p >= 1 else 1 - 2 ** (-9 * p)


# ---- utilidades de texto --------------------------------------------------
_REGLA = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def ancho_de(texto, font):
    return _REGLA.textlength(texto, font=font)


def envolver(texto, font, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if ancho_de(prueba, font) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _lienzo(ancho, alto):
    return Image.new("RGBA", (max(1, int(ancho)), max(1, int(alto))), (0, 0, 0, 0))


def capa_parrafo(texto, font, color, ancho, lh, negritas=None):
    """Capa con el texto envuelto. `negritas` resalta esas palabras con STRONG."""
    lineas = envolver(texto, font, ancho) if isinstance(texto, str) else list(texto)
    capa = _lienzo(ancho, lh * len(lineas) + 12)
    d = ImageDraw.Draw(capa)
    for i, linea in enumerate(lineas):
        d.text((0, i * lh), linea, font=font, fill=color)
    if negritas:
        pass  # el resaltado por palabra se resuelve con capa_mixta
    return capa


def capa_mixta(trozos, ancho, lh, font_reg, font_neg, color, color_neg):
    """Párrafo con trozos [(texto, negrita?)] que se envuelven juntos."""
    palabras = []
    for texto, neg in trozos:
        for p in texto.split():
            palabras.append((p, neg))
    lineas, actual, ancho_actual = [], [], 0.0
    espacio = ancho_de(" ", font_reg)
    for p, neg in palabras:
        f = font_neg if neg else font_reg
        w = ancho_de(p, f)
        if actual and ancho_actual + espacio + w > ancho:
            lineas.append(actual)
            actual, ancho_actual = [], 0.0
        if actual:
            ancho_actual += espacio
        actual.append((p, neg, w))
        ancho_actual += w
    if actual:
        lineas.append(actual)
    capa = _lienzo(ancho, lh * len(lineas) + 12)
    d = ImageDraw.Draw(capa)
    for i, linea in enumerate(lineas):
        x = 0
        for p, neg, w in linea:
            d.text((x, i * lh), p, font=font_neg if neg else font_reg,
                   fill=color_neg if neg else color)
            x += w + espacio
    return capa


def capa_espaciada(texto, font, color, sep=4, borde=True):
    """Texto con tracking abierto (kickers y etiquetas en mono).

    Sobre una imagen generada, el texto chico en color de acento se pierde en
    cuanto la foto tiene una zona clara: por eso lleva un contorno del color
    del fondo. En el texto grande no hace falta."""
    ancho = int(sum(ancho_de(c, font) + sep for c in texto)) + 12
    capa = _lienzo(ancho, font.size + 18)
    d = ImageDraw.Draw(capa)
    extra = {"stroke_width": 3, "stroke_fill": (*BG, 190)} if borde else {}
    x = 2
    for c in texto:
        d.text((x, 2), c, font=font, fill=color, **extra)
        x += ancho_de(c, font) + sep
    return capa


def degradado(ancho, alto, c1, c2, redondeo=None):
    """Barra con degradado accent→accent2, el gesto de marca del carrusel."""
    ancho, alto = max(1, int(ancho)), max(1, int(alto))
    t = np.linspace(0, 1, ancho, dtype=np.float32)[None, :, None]
    arr = (np.array(c1, np.float32)[None, None, :] * (1 - t) +
           np.array(c2, np.float32)[None, None, :] * t)
    arr = np.repeat(arr, alto, axis=0)
    capa = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    if redondeo:
        mascara = Image.new("L", (ancho, alto), 0)
        ImageDraw.Draw(mascara).rounded_rectangle(
            [0, 0, ancho - 1, alto - 1], radius=min(redondeo, alto // 2), fill=255)
        capa.putalpha(mascara)
    return capa


def pegar(base, capa, pos, op=1.0):
    """Pega una capa RGBA con opacidad. El atajo cuando op≈1 importa: es la
    mayoría de los cuadros de un Reel."""
    if op <= 0.004 or capa is None:
        return
    x, y = int(round(pos[0])), int(round(pos[1]))
    if op < 0.996:
        alfa = capa.getchannel("A").point(lambda v: int(v * op))
        capa = capa.copy()
        capa.putalpha(alfa)
    base.paste(capa, (x, y), capa)


# ---- elementos ------------------------------------------------------------
class Elemento:
    """Una capa con entrada (sube y aparece) y una deriva lenta mientras dura
    la escena, para que ningún cuadro quede completamente quieto."""

    def __init__(self, capa, pos, retardo=0.0, dur=0.55, dy=46, deriva=10.0):
        self._capa = capa
        self.x, self.y = pos
        self.retardo, self.dur, self.dy, self.deriva = retardo, dur, dy, deriva

    @property
    def alto(self):
        return self._capa.height if self._capa else 0

    def capa_en(self, p):
        return self._capa

    def dibujar(self, base, t, p_escena, dy_extra=0.0, op_extra=1.0):
        p = recortar((t - self.retardo) / self.dur) if self.dur > 0 else 1.0
        if p <= 0:
            return
        e = suave(p)
        y = self.y + self.dy * (1 - e) - self.deriva * p_escena + dy_extra
        pegar(base, self.capa_en(p), (self.x, y), e * op_extra)


class Dinamico(Elemento):
    """Elemento que se redibuja según su progreso: barras que crecen, números
    que suben. Se memoriza por paso para no rasterizar el mismo cuadro dos
    veces (una barra solo tiene ~70 estados visibles distintos)."""

    def __init__(self, hacer, pos, retardo=0.0, dur=0.9, dy=46, deriva=10.0, pasos=70):
        super().__init__(None, pos, retardo, dur, dy, deriva)
        self.hacer, self.pasos, self._memo = hacer, pasos, {}
        self._alto = hacer(1.0).height

    @property
    def alto(self):
        return self._alto

    def capa_en(self, p):
        k = round(p * self.pasos)
        if k not in self._memo:
            self._memo[k] = self.hacer(k / self.pasos)
        return self._memo[k]


class Escena:
    def __init__(self, elementos, dur, narracion="", palabras=None, inicio_voz=0.0):
        self.elementos = elementos
        self.dur = dur
        self.narracion = narracion
        self.palabras = palabras or []
        self.inicio_voz = inicio_voz

    def dibujar(self, base, t, dy=0.0, op=1.0):
        p = recortar(t / self.dur) if self.dur else 1.0
        for e in self.elementos:
            e.dibujar(base, t, p, dy, op)


# ---- fondo ----------------------------------------------------------------
def fondo_base():
    """Fondo de marca (resplandores + rejilla) un poco más grande que el
    cuadro: el vaivén se consigue recortándolo en distinta posición, que es
    mucho más barato que volver a calcularlo cada cuadro."""
    aw, ah = W + HOLGURA, H + HOLGURA
    yy, xx = np.mgrid[0:ah, 0:aw].astype(np.float32)
    arr = np.zeros((ah, aw, 3), np.float32)
    arr[:] = BG

    def resplandor(cx, cy, r, color, fuerza):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        fac = np.clip(1 - d / r, 0, 1) ** 2 * fuerza
        for i in range(3):
            arr[:, :, i] += color[i] * fac

    resplandor(aw * 0.86, -80, 1150, ACCENT, 0.20)
    resplandor(-80, ah * 0.78, 1250, ACCENT2, 0.17)
    resplandor(aw * 0.5, ah * 1.08, 900, ACCENT, 0.10)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

    rejilla = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
    gd = ImageDraw.Draw(rejilla)
    for x in range(0, aw, REJILLA):
        gd.line([(x, 0), (x, ah)], fill=(120, 150, 220, 16), width=1)
    for y in range(0, ah, REJILLA):
        gd.line([(0, y), (aw, y)], fill=(120, 150, 220, 16), width=1)
    return Image.alpha_composite(img.convert("RGBA"), rejilla).convert("RGB")


def cuadro_fondo(base, t):
    """Recorte del fondo con deriva: la rejilla sube a un periodo exacto (así
    el ciclo no se nota) y el conjunto se mece de lado muy despacio."""
    dy = int((t * 7) % REJILLA)
    dx = int(HOLGURA / 2 + math.sin(t * 0.09) * (HOLGURA / 2 - 4))
    return base.crop((dx, dy, dx + W, dy + H)).copy()


# ---- cromo (barra de avance, marca, contador) -----------------------------
_MARCA_CAPA = None


def _chrome():
    """La filigrana de marca se rasteriza una vez: dibujarla letra por letra en
    cada cuadro costaba 5 ms de los 46 que tarda un cuadro completo."""
    global _MARCA_CAPA
    if _MARCA_CAPA is not None:
        return
    ancho = int(sum(ancho_de(c, F_MARCA) + 3 for c in MARCA)) + 40
    _MARCA_CAPA = _lienzo(ancho, 44)
    d = ImageDraw.Draw(_MARCA_CAPA)
    d.ellipse([0, 5, 11, 16], fill=(*ACCENT, 190))
    x = 24
    for c in MARCA:
        d.text((x, 0), c, font=F_MARCA, fill=(*MUTED, 165))
        x += ancho_de(c, F_MARCA) + 3


def dibujar_marca(base):
    """Solo la filigrana, arriba a la izquierda.

    Antes había además una barra de avance y un contador "03/06". Los dos se
    quitaron a propósito: son el lenguaje de un carrusel —decirle al
    espectador en qué lámina va y cuántas faltan— y hacían que el Reel se
    leyera como un carrusel en movimiento. Un short no anuncia su estructura,
    y la plataforma ya dibuja su propia barra de progreso encima."""
    _chrome()
    pegar(base, _MARCA_CAPA, (MARGEN, 104))


# ---- subtítulos -----------------------------------------------------------
def bloques(palabras, maximo=30):
    """Agrupa las palabras en frases cortas: en el Reel se lee de un golpe, así
    que el subtítulo cambia cada 2-4 palabras, no palabra por palabra."""
    salida, actual = [], []
    for p in palabras:
        texto = " ".join(x[2] for x in actual + [p])
        if actual and len(texto) > maximo:
            salida.append(actual)
            actual = []
        actual.append(p)
        if actual[-1][2].rstrip()[-1:] in ".?!…,;:":
            salida.append(actual)
            actual = []
    if actual:
        salida.append(actual)
    return salida


_MEMO_SUB = {}


def _capa_subtitulo(bloque, activa):
    """Frase centrada, con la palabra que se está diciendo en color de acento."""
    llave = (tuple(p[2] for p in bloque), activa)
    if llave in _MEMO_SUB:
        return _MEMO_SUB[llave]
    palabras = [p[2] for p in bloque]
    lineas, actual = [], []
    for i, p in enumerate(palabras):
        prueba = " ".join([x[1] for x in actual] + [p])
        if actual and ancho_de(prueba, F_SUB) > ANCHO - 40:
            lineas.append(actual)
            actual = []
        actual.append((i, p))
        actual_ancho = ancho_de(" ".join(x[1] for x in actual), F_SUB)
        if actual_ancho > ANCHO - 40 and len(actual) == 1:
            lineas.append(actual)
            actual = []
    if actual:
        lineas.append(actual)

    lh = 56
    capa = _lienzo(W, lh * len(lineas) + 24)
    d = ImageDraw.Draw(capa)
    espacio = ancho_de(" ", F_SUB)
    for fila, linea in enumerate(lineas):
        total = sum(ancho_de(p, F_SUB) for _, p in linea) + espacio * (len(linea) - 1)
        x = (W - total) / 2
        for i, p in linea:
            # En la paleta clara el blanco con borde negro se pierde contra el
            # fondo: se invierte el contraste (texto oscuro, borde claro).
            normal = (*INK, 255) if CLARO else (255, 255, 255, 255)
            borde = (255, 255, 255, 230) if CLARO else (0, 0, 0, 215)
            d.text((x, fila * lh), p, font=F_SUB,
                   fill=(*ACCENT, 255) if i == activa else normal,
                   stroke_width=4, stroke_fill=borde)
            x += ancho_de(p, F_SUB) + espacio
    if len(_MEMO_SUB) > 600:
        _MEMO_SUB.clear()
    _MEMO_SUB[llave] = capa
    return capa


def dibujar_subtitulo(base, bloques_escena, t, op=1.0):
    for bloque in bloques_escena:
        ini, fin = bloque[0][0], max(bloque[-1][1], bloque[0][0] + 0.3)
        if not (ini <= t < fin + 0.12):
            continue
        activa = next((i for i, p in enumerate(bloque) if p[0] <= t < p[1]), -1)
        capa = _capa_subtitulo(bloque, activa)
        pegar(base, capa, (0, SUB_Y), op)
        return


# ---- construcción de escenas ---------------------------------------------
_MEMO_TITULO = {}


def titulo_ajustado(texto, tam, ancho=ANCHO):
    """(fuente, renglones, interlínea) de un título. El '|' parte renglones a
    mano; si alguno no cabe, se baja el cuerpo hasta que entre —un título
    cortado contra el borde es el error más fácil de cometer al escribir el
    guion, y en video ni siquiera hay HTML donde verlo antes."""
    llave = (texto, tam, ancho)
    if llave in _MEMO_TITULO:
        return _MEMO_TITULO[llave]
    minimo = max(20, int(tam * 0.66))
    font = ImageFont.truetype(BOLD, tam)
    lineas = []
    for t in range(tam, minimo - 1, -2):
        font = ImageFont.truetype(BOLD, t)
        lineas = ([l.strip() for l in texto.split("|") if l.strip()]
                  if "|" in texto else envolver(texto, font, ancho))
        if all(ancho_de(l, font) <= ancho for l in lineas):
            break
    else:  # ni en el cuerpo mínimo cabe el corte a mano: se reparte solo
        lineas = envolver(texto, font, ancho)
    r = (font, lineas, int(font.size * 1.16))
    _MEMO_TITULO[llave] = r
    return r


def capas_palabras(lineas, font, color, lh):
    """(capa, x, y) por palabra. Un titular que entra palabra por palabra se
    lee como animación; el mismo titular apareciendo entero se lee como un
    cartel. Con poco texto en pantalla, esa diferencia es casi todo el Reel."""
    capas = []
    espacio = ancho_de(" ", font)
    for fila, linea in enumerate(lineas):
        x = 0.0
        for palabra in linea.split():
            w = ancho_de(palabra, font)
            capa = _lienzo(w + 14, lh + 24)
            ImageDraw.Draw(capa).text((0, 0), palabra, font=font, fill=color)
            capas.append((capa, x, fila * lh))
            x += w + espacio
    return capas


def _capas_titulo(lineas, font, color, lh):
    """Una capa por renglón, para que el título entre escalonado."""
    capas = []
    for linea in lineas:
        capa = _lienzo(ANCHO, lh + 20)
        ImageDraw.Draw(capa).text((0, 0), linea, font=font, fill=color)
        capas.append(capa)
    return capas


def _titulo_de(esc):
    return esc.get("titulo") or esc.get("h") or ""


def _encabezado(esc, elementos, y, tam, retardo=0.0):
    """Kicker + título: el bloque con el que abren casi todas las escenas."""
    if esc.get("kicker"):
        capa = capa_espaciada(esc["kicker"].upper(), F_KICKER, ACCENT)
        elementos.append(Elemento(capa, (MARGEN, y), retardo, 0.5, 34, 6))
        y += 58
        retardo += 0.1
    titulo = _titulo_de(esc)
    if titulo:
        font, lineas, lh = titulo_ajustado(titulo, tam)
        for i, capa in enumerate(_capas_titulo(lineas, font, INK, lh)):
            elementos.append(Elemento(capa, (MARGEN, y), retardo + i * 0.09, 0.6, 52, 10))
            y += lh
        y += 26
    return y, retardo


def _alto_encabezado(esc, tam):
    alto = 58 if esc.get("kicker") else 0
    titulo = _titulo_de(esc)
    if titulo:
        _, lineas, lh = titulo_ajustado(titulo, tam)
        alto += lh * len(lineas) + 26
    return alto


def _pie(esc, elementos, y, retardo):
    if esc.get("pie") or esc.get("foot"):
        texto = esc.get("pie") or esc.get("foot")
        capa = capa_parrafo(envolver(texto, F_PIE, ANCHO), F_PIE, MUTED, ANCHO, 32)
        elementos.append(Elemento(capa, (MARGEN, y + 18), retardo + 0.3, 0.5, 24, 5))


def _gancho(esc):
    """Escena de apertura: el título enorme decide si alguien se queda."""
    elementos = []
    font, renglones, lh = titulo_ajustado(_titulo_de(esc), F_GANCHO.size)
    lineas = _capas_titulo(renglones, font, INK, lh)
    texto = esc.get("texto") or esc.get("sub") or ""
    lineas_texto = envolver(texto, F_TEXTO, ANCHO) if texto else []
    alto = (58 if esc.get("kicker") else 0) + lh * len(lineas) + \
           (len(lineas_texto) * 58 + 36 if lineas_texto else 0)
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2) - 30
    retardo = 0.12

    if esc.get("kicker"):
        elementos.append(Elemento(capa_espaciada(esc["kicker"].upper(), F_KICKER, ACCENT),
                                  (MARGEN, y), 0.0, 0.5, 30, 6))
        y += 58
    for i, capa in enumerate(lineas):
        elementos.append(Elemento(capa, (MARGEN, y), retardo + i * 0.13, 0.7, 64, 14))
        y += lh
    if lineas_texto:
        y += 36
        capa = capa_parrafo(lineas_texto, F_TEXTO, BODY, ANCHO, 58)
        elementos.append(Elemento(capa, (MARGEN, y), retardo + len(lineas) * 0.13 + 0.1,
                                  0.6, 40, 10))
        y += len(lineas_texto) * 58
    # subrayado de acento que se abre bajo el bloque
    ancho_regla = 180
    elementos.append(Dinamico(
        lambda p, a=ancho_regla: degradado(max(2, int(a * muy_suave(p))), 6, ACCENT, ACCENT2, 3),
        (MARGEN, y + 30), retardo + 0.25, 0.8, 18, 6))
    return elementos


def _dato(esc):
    elementos = []
    texto = esc.get("texto") or esc.get("body") or ""
    lineas = envolver(texto, F_TEXTO, ANCHO) if texto else []
    alto = _alto_encabezado(esc, F_H.size) + len(lineas) * 60
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2)
    y, retardo = _encabezado(esc, elementos, y, F_H.size)
    if lineas:
        # el párrafo entra renglón por renglón: se lee como se escribe
        for i, linea in enumerate(lineas):
            capa = _lienzo(ANCHO, 60)
            ImageDraw.Draw(capa).text((0, 0), linea, font=F_TEXTO, fill=BODY)
            elementos.append(Elemento(capa, (MARGEN, y), retardo + 0.2 + i * 0.07,
                                      0.5, 34, 8))
            y += 60
    _pie(esc, elementos, y, retardo)
    return elementos


def _lista(esc):
    elementos = []
    items = []
    for it in esc.get("items", []):
        if isinstance(it, (list, tuple)):
            items.append((str(it[0]), " ".join(str(x) for x in it[1:])))
        elif ":" in str(it):
            etiqueta, resto = str(it).split(":", 1)
            items.append((etiqueta + ":", resto.strip()))
        else:
            items.append(("", str(it)))

    capas = [capa_mixta([(e, True), (r, False)], ANCHO - 54, 54, F_ITEM, F_ITEMB,
                         BODY, STRONG) for e, r in items]
    alto = _alto_encabezado(esc, F_H2.size) + sum(c.height + 30 for c in capas)
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2)
    y, retardo = _encabezado(esc, elementos, y, F_H2.size)

    punto = _lienzo(18, 18)
    ImageDraw.Draw(punto).ellipse([0, 0, 17, 17], fill=ACCENT)
    for i, capa in enumerate(capas):
        r = retardo + 0.25 + i * 0.22
        elementos.append(Elemento(punto, (MARGEN + 4, y + 18), r, 0.4, 0, 8))
        elementos.append(Elemento(capa, (MARGEN + 54, y), r + 0.06, 0.55, 40, 8))
        y += capa.height + 30
    _pie(esc, elementos, y, retardo + len(capas) * 0.22)
    return elementos


def _formato(valor, unidad, vlabel=None):
    if vlabel:
        return vlabel
    texto = f"{valor:.1f}".rstrip("0").rstrip(".") if isinstance(valor, float) else str(valor)
    return f"{texto}{unidad or ''}"


def _barras(esc):
    """Barras que crecen con el número subiendo: es lo que mejor funciona en
    video, porque el dato se entiende sin leer nada."""
    elementos = []
    barras = esc.get("barras") or esc.get("bars") or []
    unidad = esc.get("unidad", esc.get("unit", ""))
    valores = [float(b.get("valor", b.get("value", 0))) for b in barras]
    tope = float(esc.get("max") or (max(valores) if valores else 1)) or 1
    ancho_pista = ANCHO
    alto_barra = 26

    alto = _alto_encabezado(esc, F_H2.size) + len(barras) * 176 - 26
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2)
    y, retardo = _encabezado(esc, elementos, y, F_H2.size)

    pista = _lienzo(ancho_pista, alto_barra)
    ImageDraw.Draw(pista).rounded_rectangle(
        [0, 0, ancho_pista - 1, alto_barra - 1], radius=alto_barra // 2, fill=(*INK, 30))

    for i, b in enumerate(barras):
        valor = float(b.get("valor", b.get("value", 0)))
        etiqueta = b.get("label") or b.get("etiqueta") or ""
        nota = b.get("nota") or b.get("note") or ""
        antes = b.get("antes", b.get("before"))
        vlabel = b.get("vlabel")
        r = retardo + 0.25 + i * 0.3

        capa_et = _lienzo(ANCHO, 44)
        ImageDraw.Draw(capa_et).text((0, 0), etiqueta, font=F_ETIQUETA, fill=MUTED)
        elementos.append(Elemento(capa_et, (MARGEN, y), r, 0.45, 28, 8))

        completa = degradado(ancho_pista, alto_barra, ACCENT, ACCENT2,
                             redondeo=alto_barra // 2)
        frac = recortar(valor / tope, 0.02, 1.0)

        def crecer(p, completa=completa, frac=frac):
            capa = pista.copy()
            w = int(ancho_pista * frac * muy_suave(p))
            if w > 4:
                capa.paste(completa.crop((0, 0, w, alto_barra)), (0, 0),
                           completa.crop((0, 0, w, alto_barra)))
            return capa

        elementos.append(Dinamico(crecer, (MARGEN, y + 54), r + 0.08, 0.95, 24, 8))

        def contar(p, valor=valor, vlabel=vlabel, nota=nota, antes=antes):
            capa = _lienzo(ANCHO, 64)
            d = ImageDraw.Draw(capa)
            e = muy_suave(p)
            if vlabel and p > 0.97:
                texto = vlabel
            elif antes is not None:
                texto = _formato(float(antes) + (valor - float(antes)) * e, unidad)
            else:
                texto = _formato(valor * e, unidad)
            d.text((0, 0), texto, font=F_VALOR, fill=STRONG)
            x = ancho_de(texto, F_VALOR) + 18
            extra = nota or (f"antes {_formato(float(antes), unidad)}" if antes is not None else "")
            if extra:
                d.text((x, 20), "· " + extra, font=F_NOTA, fill=MUTED)
            return capa

        elementos.append(Dinamico(contar, (MARGEN, y + 88), r + 0.08, 0.95, 24, 8))
        y += 176

    _pie(esc, elementos, y + 6, retardo + len(barras) * 0.3)
    return elementos


def _cita(esc):
    elementos = []
    texto = esc.get("texto") or esc.get("cita") or ""
    lineas = envolver(texto, F_CITA, ANCHO - 60)
    lh = int(F_CITA.size * 1.22)
    alto = len(lineas) * lh + 90
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2)

    comilla = _lienzo(120, 150)
    ImageDraw.Draw(comilla).text((0, -40), "“", font=ImageFont.truetype(BOLD, 190),
                                 fill=(*ACCENT, 140))
    elementos.append(Elemento(comilla, (MARGEN - 10, y - 90), 0.0, 0.6, 30, 10))

    regla = Dinamico(lambda p: degradado(6, max(2, int((len(lineas) * lh) * muy_suave(p))),
                                         ACCENT, ACCENT2, 3),
                     (MARGEN, y), 0.1, 0.8, 16, 8)
    elementos.append(regla)
    for i, linea in enumerate(lineas):
        capa = _lienzo(ANCHO, lh + 10)
        ImageDraw.Draw(capa).text((0, 0), linea, font=F_CITA, fill=INK)
        elementos.append(Elemento(capa, (MARGEN + 46, y), 0.18 + i * 0.1, 0.6, 46, 12))
        y += lh
    autor = esc.get("autor") or esc.get("fuente")
    if autor:
        elementos.append(Elemento(capa_espaciada(autor.upper(), F_PIE, MUTED),
                                  (MARGEN + 46, y + 24), 0.5, 0.5, 26, 6))
    return elementos


def _cierre(esc):
    """Cierre: la frase que resume, la llamada a la acción y el handle."""
    elementos = []
    frase = esc.get("titulo") or esc.get("una") or esc.get("one") or ""
    font_frase, lineas, lh = titulo_ajustado(frase, F_H2.size) if frase else (F_H2, [], 70)
    cta = esc.get("cta") or []
    if isinstance(cta, str):
        cta = [cta]
    handle = esc.get("handle")
    if cta and str(cta[-1]).startswith("@") and not handle:
        handle, cta = cta[-1], cta[:-1]

    alto = (58 if esc.get("kicker") else 0) + len(lineas) * lh + 40 + len(cta) * 56 + \
           (120 if handle else 0)
    y = BANDA_Y0 + max(0, (BANDA_Y1 - BANDA_Y0 - alto) / 2) - 20

    if esc.get("kicker"):
        elementos.append(Elemento(capa_espaciada(esc["kicker"].upper(), F_KICKER, ACCENT),
                                  (MARGEN, y), 0.0, 0.5, 30, 6))
        y += 58
    for i, linea in enumerate(lineas):
        capa = _lienzo(ANCHO, lh + 12)
        ImageDraw.Draw(capa).text((0, 0), linea, font=font_frase, fill=INK)
        elementos.append(Elemento(capa, (MARGEN, y), 0.1 + i * 0.1, 0.6, 50, 12))
        y += lh
    y += 40
    for i, linea in enumerate(cta):
        capa = _lienzo(ANCHO, 56)
        d = ImageDraw.Draw(capa)
        d.ellipse([0, 20, 12, 32], fill=ACCENT)
        d.text((30, 0), str(linea), font=F_CTA, fill=BODY)
        elementos.append(Elemento(capa, (MARGEN, y), 0.5 + i * 0.18, 0.5, 34, 8))
        y += 56
    if handle:
        y += 34
        elementos.append(Elemento(capa_espaciada(handle, F_HANDLE, ACCENT, 3),
                                  (MARGEN, y), 0.5 + len(cta) * 0.18 + 0.1, 0.6, 36, 10))
        y += 70
    if LOGO is not None:
        logo = LOGO.copy()
        logo.thumbnail((190, 190), Image.LANCZOS)
        elementos.append(Elemento(logo, (W - MARGEN - logo.width, y - 150),
                                  0.9, 0.8, 24, 8))
    return elementos


# ---- escenas visuales ----------------------------------------------------
# Estas son las del Reel "de verdad": la imagen ocupa la pantalla y el texto es
# un titular o un número, nunca un párrafo. Las de arriba (dato, lista, barras)
# siguen existiendo para cuando se quiere la versión informativa, pero meter un
# carrusel dentro de un video es justo lo que no funciona en la pestaña de
# Reels: nadie lee cinco renglones mientras escucha.

def _bloque_visual(alto, arriba=-40):
    """Y inicial para centrar un bloque en la banda visual, un poco por encima
    del centro: debajo queda la imagen a la vista y la transcripción."""
    y0, y1 = BANDA_VISUAL
    return y0 + max(0, (y1 - y0 - alto) / 2) + arriba


def _frase(esc):
    """Un titular y nada más. Entra palabra por palabra."""
    elementos = []
    font, lineas, lh = titulo_ajustado(_titulo_de(esc), F_FRASE.size)
    pie = esc.get("texto") or ""
    lineas_pie = envolver(pie, F_LINEA, ANCHO) if pie else []
    alto = ((58 if esc.get("kicker") else 0) + lh * len(lineas) +
            (len(lineas_pie) * 54 + 34 if lineas_pie else 0) + 40)
    y = _bloque_visual(alto)
    retardo = 0.0

    if esc.get("kicker"):
        elementos.append(Elemento(capa_espaciada(esc["kicker"].upper(), F_ETQ, ACCENT),
                                  (MARGEN, y), 0.0, 0.5, 30, 6))
        y += 58
        retardo = 0.12
    for capa, dx, dy in capas_palabras(lineas, font, INK, lh):
        elementos.append(Elemento(capa, (MARGEN + dx, y + dy),
                                  retardo + len(elementos) * 0.075, 0.55, 46, 12))
    y += lh * len(lineas)
    if lineas_pie:
        y += 34
        capa = capa_parrafo(lineas_pie, F_LINEA, BODY, ANCHO, 54)
        elementos.append(Elemento(capa, (MARGEN, y), retardo + len(lineas) * 0.2 + 0.2,
                                  0.6, 36, 10))
        y += len(lineas_pie) * 54
    if lineas or lineas_pie:   # la regla subraya algo; sola se ve como un error
        elementos.append(Dinamico(
            lambda p: degradado(max(2, int(190 * muy_suave(p))), 6, ACCENT, ACCENT2, 3),
            (MARGEN, y + 30), retardo + 0.35, 0.8, 18, 6))
    return elementos


def _texto_numero(valor, unidad, vlabel=None):
    if vlabel:
        return vlabel
    if abs(valor - round(valor)) < 0.05:
        return f"{round(valor):d}{unidad or ''}"
    return f"{valor:.1f}{unidad or ''}"


def _numero(esc):
    """Un número enorme que sube. Es la forma visual de dar un dato: se
    entiende sin leer, que es de lo que se trata cuando casi nadie lee."""
    elementos = []
    valor = float(esc.get("valor", esc.get("value", 0)))
    antes = esc.get("antes")
    desde = float(antes) if antes is not None else 0.0
    unidad = esc.get("unidad", esc.get("unit", ""))
    etiqueta = esc.get("etiqueta") or esc.get("kicker") or ""
    nota = esc.get("nota") or (f"antes {_texto_numero(desde, unidad)}"
                               if antes is not None else "")
    pie = esc.get("texto") or ""

    alto = (58 if etiqueta else 0) + 250 + (56 if nota else 0) + (60 if pie else 0)
    y = _bloque_visual(alto)
    if etiqueta:
        elementos.append(Elemento(capa_espaciada(etiqueta.upper(), F_ETQ, ACCENT),
                                  (MARGEN, y), 0.0, 0.5, 30, 6))
        y += 58

    def pintar(p, valor=valor, desde=desde, unidad=unidad, vlabel=esc.get("vlabel")):
        e = muy_suave(p)
        texto = vlabel if (vlabel and p > 0.97) else _texto_numero(
            desde + (valor - desde) * e, unidad)
        capa = _lienzo(ANCHO, 250)
        ImageDraw.Draw(capa).text((0, 0), texto, font=F_NUM, fill=STRONG)
        return capa

    elementos.append(Dinamico(pintar, (MARGEN, y), 0.12, 1.1, 50, 16))
    y += 250
    if nota:
        capa_n = _lienzo(ANCHO, 52)
        ImageDraw.Draw(capa_n).text((0, 0), nota, font=F_NOTA2, fill=MUTED,
                                    stroke_width=3, stroke_fill=(*BG, 180))
        elementos.append(Elemento(capa_n, (MARGEN + 6, y), 0.8, 0.5, 26, 8))
        y += 56
    if pie:
        lineas = envolver(pie, F_LINEA, ANCHO)
        elementos.append(Elemento(capa_parrafo(lineas, F_LINEA, BODY, ANCHO, 54),
                                  (MARGEN, y + 10), 0.95, 0.55, 32, 10))
    return elementos


def _comparacion(esc):
    """Dos cifras lado a lado. Apiladas ocupaban media pantalla y se metían
    encima del objeto; en dos columnas el bloque es la mitad de alto, cabe en
    la zona de texto y además se lee como lo que es: una contra otra."""
    elementos = []
    unidad = esc.get("unidad", esc.get("unit", ""))
    a = esc.get("a") or {}
    b = esc.get("b") or {}
    etiqueta = esc.get("etiqueta") or esc.get("kicker") or ""
    col = ANCHO // 2
    f_a, f_b = ImageFont.truetype(BOLD, 128), ImageFont.truetype(BOLD, 92)

    alto = (58 if etiqueta else 0) + 46 + int(f_a.size * 1.25)
    y = _bloque_visual(alto)
    if etiqueta:
        elementos.append(Elemento(capa_espaciada(etiqueta.upper(), F_ETQ, ACCENT),
                                  (MARGEN, y), 0.0, 0.5, 30, 6))
        y += 58

    def columna(datos, font, color, x, retardo, destacado):
        if datos.get("label"):
            capa = _lienzo(col, 46)
            ImageDraw.Draw(capa).text((0, 0), datos["label"], font=F_NOTA2,
                                      fill=BODY if destacado else MUTED,
                                      stroke_width=3, stroke_fill=(*BG, 180))
            elementos.append(Elemento(capa, (x, y), retardo, 0.45, 26, 8))
        valor = float(datos.get("valor", datos.get("value", 0)))

        def pintar(p, valor=valor, font=font, color=color, vlabel=datos.get("vlabel")):
            texto = vlabel if (vlabel and p > 0.97) else _texto_numero(
                valor * muy_suave(p), unidad)
            capa = _lienzo(col, int(font.size * 1.25))
            ImageDraw.Draw(capa).text((0, 0), texto, font=font, fill=color)
            return capa

        elementos.append(Dinamico(pintar, (x, y + 46), retardo + 0.06, 1.0, 40, 14))

    columna(a, f_a, STRONG, MARGEN, 0.12, True)
    columna(b, f_b, MUTED, MARGEN + col, 0.5, False)
    # filo vertical entre las dos columnas, que crece de arriba abajo
    alto_filo = 46 + int(f_a.size * 1.25) - 10
    elementos.append(Dinamico(
        lambda p, h=alto_filo: degradado(2, max(2, int(h * muy_suave(p))),
                                         ACCENT, ACCENT2),
        (MARGEN + col - 28, y + 8), 0.34, 0.7, 16, 8))
    return elementos


def _muda(esc):
    """Una escena sin texto: la llevan el objeto que se mueve y la narración.

    Es la mejor escena que tiene este formato cuando la animación ya dice lo
    que diría el titular. Una balanza que se vence no necesita que encima
    escribamos "pesa más"; ponerlo es repetir en texto lo que la imagen ya
    demostró, y en un short eso cansa. Admite un `kicker` si hace falta
    situar al espectador, y nada más."""
    if not esc.get("kicker"):
        return []
    return [Elemento(capa_espaciada(esc["kicker"].upper(), F_ETQ, ACCENT),
                     (MARGEN, _bloque_visual(58)), 0.0, 0.5, 30, 6)]


def _cierre_visual(esc):
    """Cierre del Reel visual: el handle grande y una línea. Nada más."""
    elementos = []
    frase = _titulo_de(esc) or esc.get("una") or ""
    font, lineas, lh = titulo_ajustado(frase, F_H.size) if frase else (F_H, [], 80)
    handle = esc.get("handle") or ""
    cta = esc.get("cta") or []
    if isinstance(cta, str):
        cta = [cta]
    if cta and str(cta[-1]).startswith("@") and not handle:
        handle, cta = cta[-1], cta[:-1]

    alto = lh * len(lineas) + (110 if handle else 0) + len(cta) * 54 + 50
    y = _bloque_visual(alto)
    for capa, dx, dy in capas_palabras(lineas, font, INK, lh):
        elementos.append(Elemento(capa, (MARGEN + dx, y + dy),
                                  len(elementos) * 0.07, 0.55, 44, 12))
    y += lh * len(lineas) + 50
    for i, linea in enumerate(cta):
        capa = _lienzo(ANCHO, 54)
        d = ImageDraw.Draw(capa)
        d.ellipse([0, 19, 12, 31], fill=ACCENT)
        d.text((30, 0), str(linea), font=F_LINEA, fill=BODY)
        elementos.append(Elemento(capa, (MARGEN, y), 0.6 + i * 0.16, 0.5, 32, 8))
        y += 54
    if handle:
        y += 26
        elementos.append(Elemento(capa_espaciada(handle, ImageFont.truetype(MONO, 46),
                                                 ACCENT, 3),
                                  (MARGEN, y), 0.75 + len(cta) * 0.16, 0.6, 36, 10))
        y += 80
    if LOGO is not None:
        logo = LOGO.copy()
        logo.thumbnail((170, 170), Image.LANCZOS)
        elementos.append(Elemento(logo, (W - MARGEN - logo.width, y - 140),
                                  1.0, 0.8, 24, 8))
    return elementos


CONSTRUCTORES = {
    "gancho": _gancho, "cover": _gancho, "portada": _gancho,
    "dato": _dato, "text": _dato, "texto": _dato,
    "lista": _lista, "list": _lista,
    "barras": _barras, "chart": _barras, "grafico": _barras,
    "cita": _cita, "quote": _cita,
    "cierre": _cierre, "end": _cierre, "final": _cierre,
    # visuales (poco texto, la imagen manda)
    "frase": _frase, "titular": _frase,
    "numero": _numero, "número": _numero, "dato-grande": _numero,
    "comparacion": _comparacion, "comparación": _comparacion, "vs": _comparacion,
    "cierre-visual": _cierre_visual, "final-visual": _cierre_visual,
    "muda": _muda, "solo-objeto": _muda,
}


def construir(esc, dur, palabras=None):
    tipo = (esc.get("tipo") or esc.get("kind") or "dato").lower()
    if tipo not in CONSTRUCTORES:
        raise SystemExit(f"Tipo de escena desconocido: {tipo}. "
                         f"Hay: {', '.join(sorted(set(CONSTRUCTORES)))}")
    elementos = CONSTRUCTORES[tipo](esc)
    return Escena(elementos, dur, esc.get("voz", ""), palabras)
