#!/usr/bin/env python3
"""Reel vertical animado (1080×1920) con narración de Gemini TTS.

Es otra cosa que `generador_reel/`: ese toma los PNG 4:5 del carrusel y les
hace zoom; aquí el video se dibuja desde cero en formato short, el texto entra
animado, las barras crecen, los números suben y **la voz manda el ritmo** —
cada escena dura lo que dura su narración, no un número fijo de segundos.

Cada escena tiene además su propio fondo en movimiento: una imagen generada con
Gemini a la que se le hace cámara, paralaje y efectos (`imagenes.py` +
`fondos.py`), y la música es una pista real de Lyria (`musica.py`). Veo no está
disponible en esta llave —los modelos `veo-*` dan 404—, así que el video se
construye a partir de imágenes; el lugar donde se enchufaría Veo el día que
esté es `imagenes.py`, porque el resto solo pide "el fondo de la escena N".

El guion del Reel vive en el mismo JSON del carrusel, en la llave "reel":

  "reel": {
    "estilo": "noticia",
    "escenas": [
      {"tipo": "gancho", "kicker": "CLAUDE · IA",
       "titulo": "La IA de centavos|ya usa una computadora",
       "texto": "De 15.7% a 72.4% en manejar una computadora real.",
       "voz": "El modelo más barato de Anthropic pasó de quince a setenta y dos por ciento…"}
    ]
  }

Tipos de escena: gancho, dato, lista, barras, cita, cierre (ver escenas.py).
Si el JSON no trae "reel", se arma un guion a partir del carrusel; `--guion`
lo imprime para revisarlo y pegarlo ya corregido (no gasta API).

Uso:
  python3 generar_short.py ../generador_imagenes/contenido/<slug>.json
  python3 generar_short.py <json> --guion            # borrador del guion, sin API
  python3 generar_short.py <json> --muestras         # una frase en cada estilo de voz
  python3 generar_short.py <json> --revisar          # un PNG por escena, sin render
  python3 generar_short.py <json> --estilo energico --sin-musica

Requiere ffmpeg y GEMINI_API_KEY (en ../.env). whisper.cpp es opcional: con él
los subtítulos quedan sincronizados palabra por palabra.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import escenas as E          # noqa: E402
import fondos as FD          # noqa: E402
import imagenes as IM        # noqa: E402
import musica as MU          # noqa: E402
import voz as V              # noqa: E402
from paletas import elegir_paleta  # noqa: E402

CRUCE = 0.50        # lo que tarda en irse la escena que sale
ANTES = 0.28        # cuánto antes empieza a entrar la que sigue
ENTRADA = 0.30      # silencio antes de la voz: deja que el texto aterrice
SALIDA = 0.55       # respiro después de la voz, antes del corte
ACORDE = [110.00, 130.81, 164.81, 196.00]  # A2 C3 E3 G3 — Am7, igual que el Reel 4:5
# Mínimos por tipo: aunque la voz sea corta, el ojo necesita este tiempo.
MINIMO = {"gancho": 2.6, "dato": 3.2, "lista": 4.2, "barras": 4.6,
          "cita": 3.2, "cierre": 3.6,
          # las visuales llevan poco texto: no hace falta dejarlas tanto en
          # pantalla, y cortar antes es lo que mantiene el ritmo
          "frase": 2.4, "numero": 2.8, "comparacion": 3.4, "cierre-visual": 3.0}


# ---- guion ---------------------------------------------------------------
def _frases(texto, n=2):
    partes = re.split(r"(?<=[.!?…])\s+", (texto or "").strip())
    return " ".join(partes[:n]).strip()


def guion_desde_carrusel(data):
    """Borrador del guion a partir de las diapositivas. Es un punto de partida:
    el texto del carrusel está escrito para leerse, no para decirse en voz
    alta (los números van en cifras y los párrafos son largos)."""
    escenas = []
    for s in data.get("slides", []):
        kind = s.get("kind")
        if kind == "cover":
            escenas.append({"tipo": "gancho", "kicker": s.get("eyebrow", ""),
                            "titulo": s.get("title", ""), "texto": s.get("sub", ""),
                            "voz": _frases(f"{s.get('title','')}. {s.get('sub','')}")})
        elif kind == "list":
            items = [[a, b] for a, b in s.get("items", [])]
            escenas.append({"tipo": "lista", "kicker": s.get("kicker", ""),
                            "titulo": s.get("h", ""), "items": items,
                            "pie": s.get("foot", ""),
                            "voz": _frases(" ".join(f"{a} {b}" for a, b in items), 3)})
        elif kind == "chart":
            barras = [{"label": b.get("label"), "valor": b.get("value"),
                       "nota": b.get("note", ""), **({"vlabel": b["vlabel"]} if b.get("vlabel") else {})}
                      for b in s.get("bars", [])]
            escenas.append({"tipo": "barras", "kicker": s.get("kicker", ""),
                            "titulo": s.get("h", ""), "unidad": s.get("unit", ""),
                            "max": s.get("max"), "barras": barras,
                            "pie": s.get("foot", ""),
                            "voz": _frases(s.get("h", "") + ". " +
                                           ", ".join(str(b.get("label")) for b in barras))})
        elif kind == "end":
            cta = list(s.get("cta", []))
            escenas.append({"tipo": "cierre", "kicker": s.get("kicker", ""),
                            "titulo": s.get("one", s.get("h", "")), "cta": cta,
                            "voz": _frases(s.get("one", ""))})
        else:
            escenas.append({"tipo": "dato", "kicker": s.get("kicker", ""),
                            "titulo": s.get("h", ""), "texto": _frases(s.get("body", "")),
                            "voz": _frases(s.get("body", ""))})
    return {"estilo": V.ESTILO_POR_DEFECTO, "escenas": escenas}


def leer_guion(data):
    reel = data.get("reel")
    if not reel:
        return guion_desde_carrusel(data), True
    if isinstance(reel, list):
        reel = {"escenas": reel}
    reel.setdefault("estilo", V.ESTILO_POR_DEFECTO)
    if not reel.get("escenas"):
        raise SystemExit('La llave "reel" no tiene "escenas".')
    return reel, False


# ---- audio ---------------------------------------------------------------
def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _pista_voz(wavs, duraciones, tmp):
    """Una sola pista con cada escena en su lugar: silencio de entrada, la voz
    y el silencio que completa la escena. Así el video y el audio no se pueden
    desfasar: las dos líneas de tiempo salen del mismo número."""
    partes = []
    for i, (wav, dur) in enumerate(zip(wavs, duraciones)):
        salida = tmp / f"escena_{i:02d}.wav"
        if wav is None:
            _ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono",
                     "-t", f"{dur:.3f}", str(salida)])
        else:
            _ffmpeg(["-i", str(wav), "-af",
                     f"adelay={int(ENTRADA*1000)},apad=whole_dur={dur:.3f},"
                     f"atrim=duration={dur:.3f}",
                     "-ac", "1", "-ar", "48000", str(salida)])
        partes.append(salida)
    lista = tmp / "lista.txt"
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
    pista = tmp / "voz_total.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", "lista.txt", "-c", "copy", "voz_total.wav"],
                   cwd=tmp, check=True)
    return pista


def _sintetizado(total, tmp):
    """Respaldo: cuatro osciladores con trémolo y pasabajos. Suena a fondo
    discreto, no a música. Se usa si Lyria falla o si se pide a propósito."""
    entradas, filtros = [], []
    for f in ACORDE:
        entradas += ["-f", "lavfi", "-i",
                     f"sine=frequency={f}:duration={total:.3f}:sample_rate=48000"]
    pesos = " ".join(["1", "0.8", "0.7", "0.6"])
    filtros.append(
        "".join(f"[{i}:a]" for i in range(len(ACORDE))) +
        f"amix=inputs={len(ACORDE)}:weights={pesos}:duration=longest:normalize=0,"
        f"tremolo=f=0.13:d=0.35,lowpass=f=1700,volume=0.10,"
        f"afade=t=in:d=1.8,afade=t=out:st={max(0, total-1.8):.3f}:d=1.8[out]")
    salida = tmp / "pad.wav"
    _ffmpeg([*entradas, "-filter_complex", ";".join(filtros), "-map", "[out]",
             "-ac", "1", "-ar", "48000", str(salida)])
    return salida


def _colchon(total, cortes, tmp, key, estilo, pedido, simple, force):
    """Pista de fondo + un soplo corto en cada cambio de escena.

    El soplo no es decoración: marca el corte y hace que el cambio de escena se
    oiga, no solo se vea."""
    bed = None
    if not simple and key:
        try:
            pista, nueva = MU.generar(MU.prompt_de(estilo, pedido), HERE / ".musica",
                                      key, force=force)
            if nueva:
                print("  música: pista nueva de Lyria", flush=True)
            bed = MU.a_medida(pista, total, tmp / "bed.wav")
        except Exception as e:                       # red, cuota, modelo retirado
            print(f"  ⚠ Lyria no respondió ({str(e)[:80]}): se usa el colchón "
                  f"sintetizado", flush=True)
    if bed is None:
        bed = _sintetizado(total, tmp)

    entradas, filtros, mezcla = ["-i", str(bed)], [], ["[0:a]"]
    for j, c in enumerate(cortes):
        entradas += ["-f", "lavfi", "-i", "anoisesrc=color=brown:duration=0.8:sample_rate=48000"]
        filtros.append(
            f"[{j+1}:a]highpass=f=250,lowpass=f=3200,volume=0.055,"
            f"afade=t=in:d=0.2,afade=t=out:st=0.25:d=0.5,"
            f"adelay={int(max(0.0, c - 0.28) * 1000)}[w{j}]")
        mezcla.append(f"[w{j}]")
    filtros.append("".join(mezcla) +
                   f"amix=inputs={len(mezcla)}:duration=first:normalize=0,"
                   f"atrim=duration={total:.3f},aresample=48000[out]")
    salida = tmp / "musica.wav"
    _ffmpeg([*entradas, "-filter_complex", ";".join(filtros), "-map", "[out]",
             "-ac", "1", "-ar", "48000", str(salida)])
    return salida


def _mezclar(pista_voz, musica, tmp):
    if musica is None:
        return pista_voz
    salida = tmp / "audio.wav"
    _ffmpeg(["-i", str(pista_voz), "-i", str(musica), "-filter_complex",
             "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "[a]", "-ac", "1", "-ar", "48000", str(salida)])
    return salida


# ---- paleta --------------------------------------------------------------
# Fondo del Reel cuando la paleta del carrusel es clara. No es un color nuevo:
# es el fondo oscuro de la casa, y los acentos siguen siendo los que le tocaron
# al slug, así que el Reel y el carrusel se reconocen como el mismo post.
OSCURO = {"bg": "#0C1222", "ink": "#EAF0FB", "muted": "#8A99BC",
          "body": "#D3DCF0", "strong": "#FFFFFF"}


def paleta_reel(paleta, forzar_clara=False):
    """El Reel va sobre fondo oscuro aunque el carrusel sea claro.

    En el feed un carrusel claro funciona; en la pestaña de Reels, a pantalla
    completa y con la interfaz de Instagram encima, el blanco sobre blanco se
    lava y el texto pierde fuerza. Se conservan los acentos del slug, que son
    los que identifican el post. `--paleta-clara` deja la paleta tal cual."""
    if forzar_clara or E._luminancia(E.hex_a_rgb(paleta["bg"])) <= 140:
        return paleta, False
    return {**paleta, **OSCURO, "claro": False}, True


# ---- fondos --------------------------------------------------------------
def preparar_fondos(guion, duraciones, paleta, opciones, key):
    """Un fondo por escena. Con imágenes se avisa antes cuántas habría que
    generar: cada una a 2K se paga, y el usuario decide.

    Si la escena trae `imagen.despues`, se genera el estado base y luego se
    EDITA esa misma imagen para el segundo estado — el mismo objeto moviéndose,
    no dos objetos distintos."""
    if opciones.sin_imagenes:
        return [FD.FondoMarca(paleta, semilla=i) for i in range(len(duraciones))]
    prompts = [IM.prompt_de(e, paleta) for e in guion["escenas"]]
    faltan = IM.faltantes(prompts, HERE / ".imagenes", opciones.force)
    cambios = sum(1 for e in guion["escenas"] if IM.secuencia_de(e))
    if faltan or cambios:
        print(f"  imágenes: {faltan} por generar, {len(prompts) - faltan} en caché"
              + (f", {cambios} con segundo estado" if cambios else ""), flush=True)
    fondos_ = []
    for i, (esc, prompt, dur) in enumerate(zip(guion["escenas"], prompts, duraciones)):
        ruta, nueva = IM.generar(prompt, HERE / ".imagenes", key, opciones.force)
        if nueva:
            print(f"  imagen {i+1}/{len(prompts)}", flush=True)
        rutas = [ruta]
        cambio = IM.secuencia_de(esc)
        if cambio:
            otra, nueva2 = IM.editar(ruta, cambio, HERE / ".imagenes", key, opciones.force)
            if nueva2:
                print(f"  imagen {i+1}/{len(prompts)} · segundo estado", flush=True)
            rutas.append(otra)
        fondos_.append(FD.FondoSecuencia(rutas, paleta, semilla=i * 7 + 3,
                                         dur=dur + ANTES))
    return fondos_


# ---- línea de tiempo -----------------------------------------------------
def _palabras_en_pantalla(esc):
    partes = [esc.get("titulo", ""), esc.get("texto", ""), esc.get("h", ""),
              esc.get("etiqueta", ""), str(esc.get("nota", ""))]
    partes += [" ".join(map(str, it)) if isinstance(it, (list, tuple)) else str(it)
               for it in esc.get("items", [])]
    partes += [str(b.get("label", "")) for b in (esc.get("barras") or esc.get("bars") or [])]
    partes += [str((esc.get(k) or {}).get("label", "")) for k in ("a", "b")]
    partes += [str(c) for c in (esc.get("cta") or [])]
    if esc.get("valor") is not None or esc.get("a"):
        partes.append("000")          # el número cuenta como una palabra más
    return len(" ".join(partes).split())


def minimo_de(esc):
    """Lo que tarda alguien en leer lo que hay en pantalla (~3.2 palabras/s),
    con el piso de cada tipo de escena."""
    tipo = (esc.get("tipo") or esc.get("kind") or "dato").lower()
    piso = MINIMO.get(tipo, 3.2)
    return max(piso, 1.3 + _palabras_en_pantalla(esc) / 3.2)


def construir_linea(guion, opciones, key=None):
    """Genera la voz de cada escena y devuelve las escenas ya con su duración."""
    estilo = opciones.estilo or guion.get("estilo") or V.ESTILO_POR_DEFECTO
    # La caché vive siempre aquí, no junto a la salida: cambiar --salida-dir no
    # debe hacer que se vuelva a pagar la voz que ya se generó.
    cache = HERE / ".voz"
    if opciones.sin_voz:
        key = None
    tmp = Path(tempfile.mkdtemp(prefix="short-voz-"))
    lista, wavs, duraciones = [], [], []
    try:
        for i, esc in enumerate(guion["escenas"]):
            texto = (esc.get("voz") or "").strip()
            wav, palabras = None, []
            if texto and not opciones.sin_voz:
                print(f"  voz {i+1}/{len(guion['escenas'])} ({estilo})…", flush=True)
                wav = V.narrar(texto, estilo, cache, key=key, force=opciones.force)
                palabras = V.tiempos(wav, texto, tmp)
                dur = max(minimo_de(esc), V.duracion(wav) + ENTRADA + SALIDA)
            else:
                dur = esc.get("dur") or minimo_de(esc)
            lista.append(E.construir(esc, dur, E.bloques(
                [(a + ENTRADA, b + ENTRADA, t) for a, b, t in palabras])))
            wavs.append(wav)
            duraciones.append(dur)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return lista, wavs, duraciones, estilo


def dibujar_en(fondos_, escenas_, duraciones, t, subtitulos=True):
    """Cuadro completo en el segundo `t` de la línea de tiempo.

    El cambio de escena no es un fundido cruzado del texto: la que sale se va
    primero (sube y se apaga) y la que entra empieza ANTES segundos antes del
    corte, durante la cola en silencio. El **fondo** sí se funde, y a lo largo
    de todo el cruce: es lo que hace que el corte se sienta como un plano que
    cambia y no como una diapositiva que avanza."""
    total = sum(duraciones)
    inicios = [sum(duraciones[:i]) for i in range(len(duraciones))]
    i = max(j for j in range(len(escenas_)) if inicios[j] <= min(t, total - 1e-6))
    local = t - inicios[i]
    restante = duraciones[i] - local
    hay_siguiente = i + 1 < len(escenas_)
    entrando = hay_siguiente and restante <= ANTES

    visual = local + (ANTES if i > 0 else 0)   # su animación arrancó antes del corte
    img = fondos_[i].cuadro(visual, visual / (duraciones[i] + ANTES))
    if hay_siguiente and restante <= CRUCE:
        q = E.suave(1 - restante / CRUCE)
        siguiente = max(0.0, ANTES - restante)
        img = Image.blend(img, fondos_[i + 1].cuadro(
            siguiente, siguiente / (duraciones[i + 1] + ANTES)), q)
        escenas_[i].dibujar(img, visual, dy=-120 * q, op=(1 - q) ** 2)
    else:
        escenas_[i].dibujar(img, visual)
    E.dibujar_marca(img)
    if entrando:
        escenas_[i + 1].dibujar(img, ANTES - restante)
    if subtitulos:
        E.dibujar_subtitulo(img, escenas_[i].palabras, local)
    return img


# ---- render --------------------------------------------------------------
def render(escenas_, duraciones, audio, destino, fondos_, subs=True):
    total = sum(duraciones)
    n = int(total * E.FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{E.W}x{E.H}", "-r", str(E.FPS),
         "-i", "-", *(["-i", str(audio)] if audio else []),
         "-map", "0:v", *(["-map", "1:a"] if audio else []),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         *(["-c:a", "aac", "-b:a", "160k", "-ar", "48000"] if audio else []),
         "-t", f"{total:.3f}", "-movflags", "+faststart", str(destino)],
        stdin=subprocess.PIPE)
    t0 = time.time()
    for k in range(n):
        ff.stdin.write(
            dibujar_en(fondos_, escenas_, duraciones, k / E.FPS, subs).tobytes())
        if k % (E.FPS * 5) == 0 and k:
            hechos = k / n
            falta = (time.time() - t0) / hechos * (1 - hechos)
            print(f"  {hechos*100:4.0f}%  (faltan ~{falta:.0f}s)", flush=True)
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg falló al armar el video")
    return total


# ---- principal -----------------------------------------------------------
def generar(contenido, opciones):
    data = json.loads(Path(contenido).read_text(encoding="utf-8"))
    slug = data.get("slug", Path(contenido).stem)
    guion, derivado = leer_guion(data)

    if opciones.guion:
        print(json.dumps({"reel": guion}, ensure_ascii=False, indent=2))
        return None

    paleta_previa = elegir_paleta(slug)
    if opciones.prompts:
        vista, _ = paleta_reel(paleta_previa, opciones.paleta_clara)
        for i, esc in enumerate(guion["escenas"], 1):
            propio = "  (del guion)" if esc.get("imagen") else "  (derivado)"
            print(f"\n--- escena {i}: {esc.get('tipo', 'dato')}{propio}")
            print(IM.prompt_de(esc, vista))
        return None

    V.revisar_entorno()
    paleta, oscurecida = paleta_reel(paleta_previa, opciones.paleta_clara)
    if oscurecida:
        print(f"  paleta {paleta_previa['nombre']} es clara: el Reel va sobre fondo "
              f"oscuro con sus mismos acentos (--paleta-clara para dejarla igual)")
    logo = HERE.parent / "assets" / "logo.png"
    E.configurar(paleta, marca=opciones.marca, logo=str(logo) if logo.is_file() else None)
    salida_dir = Path(opciones.salida_dir or HERE)
    salida_dir.mkdir(parents=True, exist_ok=True)

    if derivado:
        print("  ⚠ el JSON no trae \"reel\": se usó un guion derivado del carrusel.\n"
              "    Revísalo con --guion y pégalo corregido (la voz dice los números "
              "en palabras, no en cifras).")

    if opciones.muestras:
        return muestras(guion, salida_dir, opciones)

    key = None if (opciones.sin_voz and opciones.sin_imagenes) else V.leer_llave(opciones.env)
    escenas_, wavs, duraciones, estilo = construir_linea(guion, opciones, key)
    total = sum(duraciones)
    tabla(guion["escenas"], duraciones, wavs, total)
    fondos_ = preparar_fondos(guion, duraciones, paleta, opciones, key)

    if opciones.revisar:
        destino = salida_dir / "revision" / slug
        destino.mkdir(parents=True, exist_ok=True)
        inicios = [sum(duraciones[:i]) for i in range(len(duraciones))]
        for i, (ini, dur) in enumerate(zip(inicios, duraciones)):
            img = dibujar_en(fondos_, escenas_, duraciones, ini + dur * 0.88,
                             not opciones.sin_subtitulos)
            img.save(destino / f"{slug}-{i+1:02d}.png")
        print(f"Revisión: {destino} ({len(escenas_)} escenas, ~{total:.1f}s)")
        return destino

    if opciones.cuadro is not None:
        destino = salida_dir / f"{slug}-cuadro.png"
        dibujar_en(fondos_, escenas_, duraciones, opciones.cuadro,
                   not opciones.sin_subtitulos).save(destino)
        print(f"Cuadro: {destino}")
        return destino

    tmp = Path(tempfile.mkdtemp(prefix="short-"))
    try:
        audio = None
        if any(w for w in wavs) or not opciones.sin_musica:
            pista = _pista_voz(wavs, duraciones, tmp)
            cortes = [sum(duraciones[:i]) for i in range(1, len(duraciones))]
            musica = None if opciones.sin_musica else _colchon(
                total, cortes, tmp, key, estilo, guion.get("musica"),
                opciones.musica_simple, opciones.force)
            audio = _mezclar(pista, musica, tmp)
        destino = Path(opciones.salida) if opciones.salida else salida_dir / f"{slug}.mp4"
        print(f"  render {int(total*E.FPS)} cuadros ({total:.1f}s)…", flush=True)
        render(escenas_, duraciones, audio, destino, fondos_,
               not opciones.sin_subtitulos)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    aviso = ""
    if total > 60:
        aviso = "  ⚠ pasa de 60s: para Reels conviene 30-50s, acorta la narración.\n"
    fondo_txt = "fondo de marca" if opciones.sin_imagenes else "imágenes generadas"
    print(f"{aviso}Listo: {destino}  ({total:.1f}s, {len(escenas_)} escenas, "
          f"voz {estilo}, {fondo_txt}, paleta {paleta_previa['nombre']}"
          f"{' oscurecida' if oscurecida else ''})")
    return destino


def tabla(escs, duraciones, wavs, total):
    """Qué tan larga quedó cada escena y por qué: si una dura su mínimo en vez
    de lo que dura la voz, es que hay demasiado texto en pantalla para lo poco
    que dice la narración (o al revés)."""
    print(f"\n  {'escena':<28} {'voz':>6} {'dura':>6}  motivo")
    for esc, dur, wav in zip(escs, duraciones, wavs):
        tipo = (esc.get("tipo") or esc.get("kind") or "dato").lower()
        titulo = (esc.get("titulo") or esc.get("etiqueta")
                  or "").replace("|", " ")[:20]
        v = V.duracion(wav) if wav else 0.0
        motivo = "voz" if wav and dur <= v + ENTRADA + SALIDA + 0.01 else "lectura"
        print(f"  {tipo[:7]:<7} {titulo:<20} {v:5.1f}s {dur:5.1f}s  {motivo}")
    print(f"  {'':<28} {'':>6} {total:5.1f}s  total"
          + ("   ⚠ para Reels conviene 30-50s" if total > 60 else ""))


def muestras(guion, salida_dir, opciones):
    """Una misma frase en cada estilo, para elegir voz sin pagar el Reel entero."""
    texto = next((e.get("voz") for e in guion["escenas"] if e.get("voz")), None)
    if not texto:
        raise SystemExit("No hay texto de voz en el guion para hacer muestras.")
    texto = _frases(texto, 1) or texto   # una frase basta para juzgar una voz
    destino = salida_dir / "muestras"
    destino.mkdir(parents=True, exist_ok=True)
    key = V.leer_llave(opciones.env)
    for nombre in V.ESTILOS:
        print(f"  {nombre}…", flush=True)
        wav = V.narrar(texto, nombre, HERE / ".voz", key=key)
        mp3 = destino / f"{nombre}.mp3"
        _ffmpeg(["-i", str(wav), "-b:a", "160k", str(mp3)])
    print(f"Muestras en {destino}. Pon el que te guste en \"reel\".\"estilo\".")
    return destino


def main():
    ap = argparse.ArgumentParser(
        description="Reel vertical animado (1080×1920) con narración de Gemini TTS.")
    ap.add_argument("contenido", help='JSON de contenido del carrusel (con o sin llave "reel")')
    ap.add_argument("--estilo", default=None,
                    help=f"estilo de voz: {', '.join(V.ESTILOS)} (o 'Voz:dirección libre')")
    ap.add_argument("--guion", action="store_true",
                    help="imprime el guion derivado del carrusel y sale (no gasta API)")
    ap.add_argument("--muestras", action="store_true",
                    help="genera la misma frase en todos los estilos de voz")
    ap.add_argument("--revisar", action="store_true",
                    help="un PNG por escena en revision/<slug>/, sin render de video")
    ap.add_argument("--cuadro", type=float, default=None,
                    help="guarda solo el cuadro de ese segundo, para revisar")
    ap.add_argument("--sin-voz", action="store_true", help="sin narración (solo animación)")
    ap.add_argument("--sin-imagenes", action="store_true",
                    help="fondo de marca en vez de imágenes generadas (no gasta API)")
    ap.add_argument("--prompts", action="store_true",
                    help="imprime el prompt de imagen de cada escena y sale (no gasta API)")
    ap.add_argument("--paleta-clara", action="store_true",
                    help="respeta la paleta clara del carrusel en vez de oscurecer el Reel")
    ap.add_argument("--musica-simple", action="store_true",
                    help="colchón sintetizado en vez de la pista de Lyria")
    ap.add_argument("--sin-musica", action="store_true", help="sin colchón de fondo")
    ap.add_argument("--sin-subtitulos", action="store_true",
                    help="sin subtítulos (la mayoría ve los Reels en silencio: piénsalo)")
    ap.add_argument("--force", action="store_true", help="vuelve a pedir la voz a Gemini")
    ap.add_argument("--marca", default=None, help="texto de la marca arriba a la izquierda")
    ap.add_argument("--env", default=None, help="ruta del .env con GEMINI_API_KEY")
    ap.add_argument("--salida", default=None, help="ruta del .mp4 (default ./<slug>.mp4)")
    ap.add_argument("--salida-dir", default=None, help="carpeta de trabajo (default esta)")
    args = ap.parse_args()
    generar(args.contenido, args)


if __name__ == "__main__":
    main()
