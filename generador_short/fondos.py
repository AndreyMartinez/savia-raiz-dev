#!/usr/bin/env python3
"""El fondo de cada escena, en movimiento.

Dos clases con la misma interfaz, `cuadro(t, z)`:

- `FondoMarca`  — el degradado de marca con rejilla. Gratis, sobrio, el de antes.
- `FondoImagen` — una imagen generada (ver `imagenes.py`) convertida en toma de
  video: la cámara avanza, el frente se separa del fondo, un barrido de luz
  cruza y suben partículas.

La idea del paralaje viene de `animar.py` de las audioguías, pero el truco de
separar el sujeto con Vision no sirve aquí: estas imágenes son abstractas y no
tienen "sujeto". Lo que sí tienen es **luz**: en una imagen así los puntos
brillantes son lo que está cerca y el fondo oscuro lo que está lejos, así que
la luminancia sirve de mapa de profundidad. El frente (lo brillante) se acerca
más rápido que el fondo, y eso es lo que hace que una foto fija se vea como una
toma de cámara y no como un PNG con zoom.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import escenas as E
import imagenes as IM

W, H = E.W, E.H
MARGEN_FUENTE = 1.42        # la imagen se guarda a 1.42× el cuadro: margen para la cámara
Z_FONDO, Z_FRENTE = 0.13, 0.27   # cuánto se acerca cada capa a lo largo de la escena
Z_OBJETO = 0.34             # con máscara real el objeto puede adelantarse más
DERIVA = 0.032              # desplazamiento lateral de la cámara (fracción del encuadre)
VELO_BASE = 72              # opacidad del velo de marca: con poco texto se puede ver más imagen
POLVO = 34                  # motas de luz que suben


def _recorte(capa, z, zoom, dx, dy, filtro=Image.BILINEAR):
    """Encuadre de una capa: acercamiento `zoom` recorrido según z (0→1) y la
    cámara desplazada (dx, dy) en fracciones del encuadre.

    El filtro importa más de lo que parece: reescalar a 1080×1920 cuesta ~22 ms
    con BILINEAR y ~3 ms con NEAREST. En una capa ya difuminada NEAREST no se
    nota (no hay detalle fino que destruir), así que ahí se usa ese; el detalle
    real solo lo lleva la capa de frente."""
    gw, gh = capa.size
    f = 1.08 + zoom * z
    cw, ch = gw / f, gh / f
    cx = gw / 2 + dx * gw
    cy = gh / 2 + dy * gh
    cx = min(max(cx, cw / 2), gw - cw / 2)
    cy = min(max(cy, ch / 2), gh - ch / 2)
    return capa.resize((W, H), filtro,
                       box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))


class FondoImagen:
    """Toma de video a partir de una imagen generada."""

    def __init__(self, ruta, paleta, semilla=0, dur=6.0):
        self.rnd = random.Random(semilla)
        self.dur = max(0.5, dur)
        bg = E.hex_a_rgb(paleta["bg"])
        acc = E.hex_a_rgb(paleta["accent"])
        claro = E._luminancia(bg) > 140

        base = Image.open(ruta).convert("RGB")
        base = self._cubrir(base, int(W * MARGEN_FUENTE), int(H * MARGEN_FUENTE))
        # Unifica el conjunto: un 12% hacia el fondo de la paleta hace que seis
        # imágenes distintas se sientan del mismo Reel.
        base = Image.blend(base, Image.new("RGB", base.size, bg), 0.12)

        # Profundidad. Con un objeto de verdad, Vision lo recorta y el paralaje
        # es real: el objeto se mueve contra su fondo. Sin objeto (una imagen
        # abstracta) se cae a la luminancia, que es un sustituto decente porque
        # ahí lo brillante suele estar cerca.
        m = IM.mascara(ruta)
        self.con_objeto = m is not None
        if self.con_objeto:
            m = self._cubrir(m.convert("L"), *base.size)
            self.frente_mascara = m.filter(ImageFilter.GaussianBlur(2.5))
            # El hueco que deja el objeto se rellena con el propio fondo muy
            # difuminado. En un ciclorama de estudio eso es exacto: detrás del
            # objeto no hay nada que inventar, solo más fondo.
            hueco = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8))
            relleno = base.filter(ImageFilter.GaussianBlur(70))
            detras = Image.composite(relleno, base, hueco)
            self.zoom_frente = Z_OBJETO
        else:
            lum = base.convert("L").filter(ImageFilter.GaussianBlur(12))
            if claro:   # en paleta clara lo que destaca es lo oscuro
                lum = Image.eval(lum, lambda v: 255 - v)
            self.frente_mascara = lum.point(
                lambda v: int(255 * min(1.0, max(0.0, (v / 255 - 0.24) / 0.52)) ** 1.35))
            detras = base
            self.zoom_frente = Z_FRENTE
        # Un desenfoque de 0.9 px permite reescalar el frente con NEAREST sin
        # que se vea el aliasing: la diferencia contra BILINEAR es de 0.6/255
        # por canal (invisible) y cuesta 2.6 ms en vez de 34 ms por cuadro, que
        # en 1600 cuadros son 50 segundos de render.
        self.frente = base.filter(ImageFilter.GaussianBlur(0.9))
        # El fondo se guarda a media resolución: va borroso de todas formas y
        # así cada cuadro reescala la cuarta parte de los píxeles. Es la
        # diferencia entre renderizar a 9 fps y a 20.
        borroso = Image.eval(detras.filter(ImageFilter.GaussianBlur(5)),
                             lambda v: int(v * (1.06 if claro else 0.88)))
        self.fondo = borroso.resize((base.width // 2, base.height // 2), Image.BILINEAR)

        # Con un objeto sobre ciclorama limpio hace falta menos velo: el fondo
        # ya es liso y el texto se lee sin ayuda.
        self.velo = self._velo(bg, claro, VELO_BASE - (22 if self.con_objeto else 0),
                               con_objeto=self.con_objeto)
        self.brillo = self._brillo(acc)
        self.polvo = [(self.rnd.random(), self.rnd.random(),
                       self.rnd.uniform(0.012, 0.045), self.rnd.uniform(1.6, 4.2),
                       self.rnd.uniform(0, 6.28)) for _ in range(POLVO)]
        self.color_polvo = (255, 255, 255) if not claro else acc
        # Cada escena entra con la cámara en otro lado: si todas empiezan
        # centradas y se acercan igual, el Reel se siente repetido.
        self.dx0 = self.rnd.uniform(-DERIVA, DERIVA)
        self.dy0 = self.rnd.uniform(-DERIVA, DERIVA)
        self.dx1 = self.rnd.uniform(-DERIVA, DERIVA)
        self.dy1 = self.rnd.uniform(-DERIVA, DERIVA)

    @staticmethod
    def _cubrir(img, w, h):
        """Recorta al 9:16 exacto sin deformar."""
        gw, gh = img.size
        if gw / gh > w / h:
            nw = int(gh * w / h)
            img = img.crop(((gw - nw) // 2, 0, (gw + nw) // 2, gh))
        else:
            nh = int(gw * h / w)
            img = img.crop((0, (gh - nh) // 2, gw, (gh + nh) // 2))
        return img.resize((w, h), Image.LANCZOS)

    @staticmethod
    def _velo(bg, claro, base=VELO_BASE, con_objeto=False):
        """Degradado del color de fondo de la paleta: sin él el texto se pierde
        contra la parte clara de la imagen. Es degradado y no caja porque una
        caja se ve como un parche.

        Con un objeto, el cuadro está partido en dos: arriba vive el texto y
        abajo el objeto. Entonces el velo baja hasta los ~980 px y deja el
        objeto limpio, en vez de oscurecer solo la franja de arriba."""
        velo = Image.new("RGBA", (W, H), (*bg, 0))
        col = Image.new("L", (1, H))
        for y in range(H):
            if con_objeto:
                arriba = max(0.0, 1 - y / 980) ** 1.25 * 125
            else:
                arriba = max(0.0, 1 - y / 420) ** 1.5 * 95
            abajo = max(0.0, (y - 980) / 940) ** 1.3 * 120
            col.putpixel((0, y), int(min(240, base + arriba + abajo)))
        velo.putalpha(col.resize((W, H)))
        return velo

    @staticmethod
    def _brillo(acc):
        """Mancha de luz suave que cruza la toma: el 'barrido' que tienen los
        fondos de video y que una imagen fija no trae."""
        r = 400
        capa = Image.new("RGBA", (r * 2, r * 2), (*acc, 0))
        a = Image.new("L", (r * 2, r * 2), 0)
        d = ImageDraw.Draw(a)
        for i in range(22):
            k = i / 21
            d.ellipse([r - r * (1 - k), r - r * (1 - k), r + r * (1 - k), r + r * (1 - k)],
                      fill=int(52 * k ** 2))
        capa.putalpha(a)
        return capa

    def cuadro(self, t, z):
        z = min(1.0, max(0.0, z))
        s = z * z * (3 - 2 * z)          # el acercamiento arranca y frena suave
        dx = self.dx0 + (self.dx1 - self.dx0) * s
        dy = self.dy0 + (self.dy1 - self.dy0) * s
        img = _recorte(self.fondo, s, Z_FONDO, dx * 0.45, dy * 0.45, Image.NEAREST)
        frente = _recorte(self.frente, s, self.zoom_frente, dx, dy, Image.NEAREST)
        mascara = _recorte(self.frente_mascara, s, self.zoom_frente, dx, dy, Image.NEAREST)
        img.paste(frente, (0, 0), mascara)

        # barrido de luz: cruza en diagonal una vez por escena
        p = (t / self.dur) % 1.0
        bx = int(-self.brillo.width * 0.6 + (W + self.brillo.width * 0.2) * p)
        by = int(H * 0.72 - H * 0.5 * p)
        img.paste(self.brillo, (bx, by), self.brillo)

        # El polvo se dibuja sobre una copia del velo: una sola capa que pegar
        # en vez de dos, que a 1080×1920 y 30 cuadros por segundo se nota.
        capa = self.velo.copy()
        d = ImageDraw.Draw(capa)
        for px, py, vel, rad, fase in self.polvo:
            y = (py - t * vel) % 1.0
            x = px + math.sin(t * 0.5 + fase) * 0.012
            a = int(100 * (0.45 + 0.55 * math.sin(t * 1.5 + fase)) ** 2)
            cx, cy = x * W, y * H
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(*self.color_polvo, a))
        img.paste(capa, (0, 0), capa)
        return img


class FondoSecuencia:
    """El mismo objeto en dos o tres estados, que se suceden DENTRO de la toma
    mientras la cámara sigue avanzando. Es lo que hace que el plano demuestre
    algo —la balanza se vence, la pila crece— en vez de solo ilustrarlo.

    La cámara no se reinicia en cada estado: todos comparten el mismo avance y
    solo se funde el contenido, así que se ve como una sola toma."""

    CRUCE = 0.45

    def __init__(self, rutas, paleta, semilla=0, dur=6.0):
        self.capas = [FondoImagen(r, paleta, semilla=semilla, dur=dur) for r in rutas]
        self.dur = max(0.5, dur)

    def cuadro(self, t, z):
        n = len(self.capas)
        if n == 1:
            return self.capas[0].cuadro(t, z)
        tramo = self.dur / n
        i = min(n - 1, int(t / tramo))
        img = self.capas[i].cuadro(t, z)
        dentro = t - i * tramo
        if i + 1 < n and dentro > tramo - self.CRUCE:
            p = (dentro - (tramo - self.CRUCE)) / self.CRUCE
            img = Image.blend(img, self.capas[i + 1].cuadro(t, z), min(1.0, p))
        return img


class FondoMarca:
    """El fondo de siempre (degradado + rejilla), sin costo de API."""

    def __init__(self, paleta=None, semilla=0, dur=6.0):
        self.base = E.fondo_base()
        self.t0 = semilla * 3.1

    def cuadro(self, t, z):
        return E.cuadro_fondo(self.base, self.t0 + t)
