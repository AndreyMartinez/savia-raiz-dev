#!/usr/bin/env python3
"""Narración del Reel con Gemini TTS: un WAV por escena, en varios estilos de voz.

La voz manda el ritmo del Reel: cada escena dura lo que dura su narración
(más un respiro), así que el video no se siente cortado a destiempo. Por eso
este módulo se ejecuta antes de renderizar un solo cuadro.

Cada llamada a Gemini cuesta cuota, así que todo se guarda en `.voz/` con un
hash de (modelo, voz, dirección, texto): volver a generar el mismo Reel no
vuelve a pagar la voz, y cambiar solo la animación no toca la API.

Necesita `GEMINI_API_KEY` en el `.env` del proyecto (o en el entorno) y
`ffmpeg`. Los tiempos palabra por palabra de los subtítulos los saca
whisper.cpp si está instalado; si no, los reparte por largo de palabra.
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROYECTO = HERE.parent

MODELO = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
ACENTO = "Narra en español de México, con acento mexicano natural."
LUFS = -18  # mismo nivel que las audioguías: deja aire para la música de fondo

WHISPER = Path(os.environ.get(
    "WHISPER_CLI", Path.home() / ".cache/whisper/whisper.cpp/build/bin/whisper-cli"))
WHISPER_MODELO = Path(os.environ.get(
    "WHISPER_MODEL", Path.home() / ".cache/whisper/ggml-small.bin"))

# ---- estilos de narración -------------------------------------------------
# Cada estilo es una voz de Gemini + la dirección de actuación. La voz sola no
# define el tono: la dirección es la que cambia el ritmo y la intención. Para
# escuchar cómo suena cada uno antes de gastar cuota en el Reel completo:
#   python3 generar_short.py <json> --muestras
ESTILOS = {
    "noticia": {
        "voz": "Charon",
        "direccion": "Locutor de noticias de tecnología: claro y firme, ritmo ágil, "
                     "pausas cortas, cero adornos. Dice los datos con seguridad.",
    },
    "explicativo": {
        "voz": "Kore",
        "direccion": "Alguien que te explica algo técnico de forma sencilla: cercano y "
                     "paciente, ritmo tranquilo, carga el énfasis en las palabras clave.",
    },
    "energico": {
        "voz": "Puck",
        "direccion": "Entusiasta y con energía, ritmo rápido, como quien acaba de "
                     "descubrir algo y te lo quiere contar ya. Sin gritar.",
    },
    "cercano": {
        "voz": "Enceladus",
        "direccion": "Voz suave y cercana, como si te lo contara de cerca en voz baja: "
                     "ritmo pausado, tono confidencial.",
    },
    "suspenso": {
        "voz": "Algenib",
        "direccion": "Tensión que crece antes de la revelación: voz baja, ritmo pausado, "
                     "silencios que pesan. El dato final cae seco.",
    },
    "motivacional": {
        "voz": "Orus",
        "direccion": "Firme y cálido, con convicción pero sin grandilocuencia: frases con "
                     "peso, pausas que dejan aire para pensar.",
    },
}
ESTILO_POR_DEFECTO = "explicativo"


def estilo(nombre):
    """Devuelve (voz, direccion) del estilo. Acepta 'Charon:mi dirección libre'."""
    if ":" in nombre:
        voz, direccion = nombre.split(":", 1)
        return voz.strip(), direccion.strip()
    if nombre not in ESTILOS:
        raise SystemExit(
            f"Estilo de voz desconocido: {nombre}. Hay: {', '.join(ESTILOS)}\n"
            f"  (o pasa 'Voz:dirección libre', p. ej. 'Charon:Locutor serio y pausado.')")
    e = ESTILOS[nombre]
    return e["voz"], e["direccion"]


# ---- llave ---------------------------------------------------------------
def leer_llave(env=None):
    """GEMINI_API_KEY del entorno o del .env. Nunca se imprime ni se registra."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    candidatos = [Path(env)] if env else [PROYECTO / ".env", Path.cwd() / ".env"]
    for ruta in candidatos:
        if ruta.is_file():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                if linea.strip().startswith("GEMINI_API_KEY"):
                    valor = linea.split("=", 1)[1].strip().strip('"').strip("'")
                    if valor:
                        return valor
    raise SystemExit(
        "Falta GEMINI_API_KEY. Ponla en " + str(PROYECTO / ".env") +
        " (GEMINI_API_KEY=...) o pásale --env <ruta/.env>.\n"
        "  Consíguela en aistudio.google.com/apikey. No la pegues en un archivo del repo.")


# ---- Gemini --------------------------------------------------------------
def explicar(codigo, detalle):
    """Traduce los errores de cuota y cobro de Gemini, que no significan lo mismo.

    - 402 créditos agotados: no se arregla esperando ni mañana. Hay que
      recargar el proyecto.
    - 429 tope de gasto: el proyecto tiene un límite mensual y lo alcanzó;
      hay que subirlo.
    - 429 cuota diaria: se reinicia a medianoche del Pacífico.
    - el resto: congestión pasajera, y ahí sí vale reintentar."""
    if codigo == 402 or re.search(r"prepayment|credits are depleted", detalle, re.I):
        return ("Se acabaron los créditos de prepago del proyecto de Gemini.\n"
                "  Esto no se destraba esperando: hay que recargar en "
                "ai.studio/projects (Facturación).\n"
                "  Lo ya generado queda en caché y no se vuelve a pedir, así que al "
                "recargar se sigue donde se quedó.\n"
                "  Mientras tanto se puede armar el Reel sin gastar: --sin-voz "
                "--sin-imagenes --musica-simple (sale mudo y con el fondo de marca, "
                "pero deja ver la estructura y los tiempos).")
    if codigo != 429:
        return None
    return _explicar_429(detalle)


def _explicar_429(detalle):
    """Traduce los 429 de Gemini, que no todos significan lo mismo.

    - tope de gasto: el proyecto tiene un límite mensual y lo alcanzó. No se
      arregla esperando un rato largo ni reintentando: hay que subir el tope.
    - cuota diaria: se reinicia a medianoche del Pacífico.
    - el resto: congestión pasajera, y ahí sí vale reintentar."""
    if re.search(r"spend|spending cap|budget", detalle, re.I):
        return ("El proyecto de Gemini llegó a su tope de gasto mensual y la API está "
                "limitando las peticiones.\n"
                "  Lo ya generado queda en caché y no se vuelve a pedir.\n"
                "  Para seguir: sube el tope en console.cloud.google.com → Facturación → "
                "Presupuestos, o en aistudio.google.com/apikey si la llave es de ahí.\n"
                "  Mientras tanto, el Reel se puede armar sin gastar: --sin-imagenes "
                "y --musica-simple, o --sin-voz.")
    if re.search(r"per day|daily", detalle, re.I):
        return ("Se acabó la cuota diaria de Gemini. Lo ya generado queda en caché: "
                "corre el mismo comando mañana y sigue donde se quedó.")
    return None


def _pedir(key, texto, voz, direccion):
    """Pide la lectura a Gemini y devuelve los bytes del audio (WAV o PCM crudo).

    Reintenta un par de veces si el 429 es por congestión; si es por tope de
    gasto o cuota diaria, se detiene y lo dice, porque reintentar no arregla
    ninguno de los dos."""
    cuerpo = {
        "model": MODELO,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": texto,
                "annotations": [{"type": "speech_metadata", "style": f"{direccion} {ACENTO}"}],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voz}]},
    }
    for intento in range(1, 4):
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(cuerpo).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors="replace")[:400]
            claro = explicar(e.code, detalle)
            if claro:
                raise SystemExit(claro)
            if e.code != 402 and (e.code == 429 or e.code >= 500) and intento < 3:
                print(f"  … Gemini {e.code}, reintento {intento} en {intento * 20} s",
                      flush=True)
                time.sleep(intento * 20)
                continue
            raise SystemExit(f"Gemini {e.code}: {detalle}")
    for paso in data.get("steps", []):
        if paso.get("type") != "model_output":
            continue
        for c in paso.get("content", []):
            if c.get("type") == "audio" and c.get("data"):
                import base64
                return base64.b64decode(c["data"])
    raise SystemExit("Gemini respondió sin audio.")


def _a_wav(crudo, destino):
    """Deja el audio de Gemini como WAV. Si viene como PCM crudo, lo envuelve
    (24 kHz mono, el formato que entrega el modelo de voz)."""
    if crudo[:4] == b"RIFF":
        destino.write_bytes(crudo)
        return
    pcm = destino.with_suffix(".pcm")
    pcm.write_bytes(crudo)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", "24000",
                    "-ac", "1", "-i", str(pcm), str(destino)], check=True)
    pcm.unlink()


def _normalizar(entrada, salida):
    """Voz a 48 kHz mono y -18 LUFS, para que todas las escenas suenen igual."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(entrada),
         "-af", f"loudnorm=I={LUFS}:TP=-2:LRA=11,aresample=48000",
         "-ac", "1", "-ar", "48000", str(salida)], check=True)


def duracion(ruta):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(ruta)])
    return float(out.decode().strip())


def narrar(texto, nombre_estilo, cache, key=None, force=False):
    """WAV normalizado de una escena. Reusa `.voz/<hash>.wav` si ya existe.

    El `…` se manda tal cual (Gemini hace una pausa corta ahí)."""
    voz, direccion = estilo(nombre_estilo)
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    firma = hashlib.sha1(
        f"{MODELO}|{voz}|{direccion}|{texto}".encode()).hexdigest()[:16]
    final = cache / f"{firma}.wav"
    if final.exists() and not force:
        return final
    crudo = cache / f"{firma}.crudo.wav"
    _a_wav(_pedir(key or leer_llave(), texto, voz, direccion), crudo)
    _normalizar(crudo, final)
    crudo.unlink(missing_ok=True)
    return final


# ---- tiempos palabra por palabra (subtítulos) ----------------------------
def _llave(palabra):
    sin_acento = unicodedata.normalize("NFD", palabra.lower())
    sin_acento = sin_acento.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sin_acento)


def _whisper(wav, tmp):
    """[(ini, fin, token)] de whisper.cpp; None si no está instalado."""
    if not (WHISPER.exists() and WHISPER_MODELO.exists()):
        return None
    tmp = Path(tmp)
    w16 = tmp / "w16.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ar", "16000",
                    "-ac", "1", str(w16)], check=True)
    r = subprocess.run(
        [str(WHISPER), "-m", str(WHISPER_MODELO), "-l", "es", "-ml", "1", "-sow",
         "-oj", "-of", str(tmp / "w"), "-np", "-f", str(w16)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode or not (tmp / "w.json").exists():
        return None
    salida = []
    for x in json.loads((tmp / "w.json").read_text())["transcription"]:
        t = x["text"].strip()
        if t:
            salida.append((x["offsets"]["from"] / 1000, x["offsets"]["to"] / 1000, t))
    return salida or None


def _por_largo(palabras_guion, total):
    """Reparto proporcional al largo de cada palabra: sin whisper, es lo más
    cercano a cómo se lee en voz alta."""
    pesos = [len(p) + 2 for p in palabras_guion]
    suma = sum(pesos) or 1
    tiempos, t = [], 0.0
    for p, w in zip(palabras_guion, pesos):
        d = total * w / suma
        tiempos.append((t, t + d, p))
        t += d
    return tiempos


def tiempos(wav, texto, tmp):
    """[(ini, fin, palabra)] del guion de la escena, alineado al audio real.

    El resultado se guarda junto al WAV: pasar whisper por seis escenas tarda
    casi un minuto, y se repetía en cada corrida aunque la voz ya estuviera en
    caché (al revisar un cuadro, al re-renderizar…).

    Las palabras siempre salen del guion (no de whisper): así los subtítulos
    nunca escriben mal un nombre propio ni se comen un acento. De whisper se
    usan solo los tiempos, emparejados con el guion por similitud; las palabras
    que no empatan se interpolan entre las que sí."""
    guion = texto.split()
    total = duracion(wav)
    if not guion:
        return []
    memo = Path(wav).with_suffix(".tiempos.json")
    if memo.exists():
        guardado = json.loads(memo.read_text(encoding="utf-8"))
        if guardado.get("texto") == texto:
            return [tuple(x) for x in guardado["palabras"]]
    salida = _alinear(guion, total, wav, tmp)
    memo.write_text(json.dumps({"texto": texto, "palabras": salida},
                               ensure_ascii=False), encoding="utf-8")
    return salida


def _alinear(guion, total, wav, tmp):
    oidas = _whisper(wav, tmp)
    if not oidas:
        return _por_largo(guion, total)

    a = [_llave(p) for p in guion]
    b = [_llave(t) for _, _, t in oidas]
    ancla = {}
    for bloque in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloque.size):
            ancla[bloque.a + k] = oidas[bloque.b + k][:2]
    if not ancla:
        return _por_largo(guion, total)

    # interpola los huecos entre anclas y extiende los extremos
    conocidos = sorted(ancla)
    salida = []
    for i, palabra in enumerate(guion):
        if i in ancla:
            salida.append((ancla[i][0], ancla[i][1], palabra))
            continue
        antes = [k for k in conocidos if k < i]
        despues = [k for k in conocidos if k > i]
        if antes and despues:
            k0, k1 = antes[-1], despues[0]
            t0, t1 = ancla[k0][1], ancla[k1][0]
            paso = (t1 - t0) / (k1 - k0)
            ini = t0 + paso * (i - k0 - 1)
            salida.append((max(0.0, ini), min(total, ini + paso), palabra))
        elif antes:
            t0 = ancla[antes[-1]][1]
            paso = max(0.18, (total - t0) / max(1, len(guion) - antes[-1]))
            ini = t0 + paso * (i - antes[-1] - 1)
            salida.append((ini, min(total, ini + paso), palabra))
        else:
            k1 = despues[0]
            t1 = ancla[k1][0]
            paso = max(0.18, t1 / max(1, k1))
            ini = max(0.0, t1 - paso * (k1 - i))
            salida.append((ini, ini + paso, palabra))
    return salida


def hay_whisper():
    return WHISPER.exists() and WHISPER_MODELO.exists()


def revisar_entorno():
    """Avisa de lo que falta antes de empezar (no corta: whisper es opcional)."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("Falta ffmpeg (brew install ffmpeg).")
    if not hay_whisper():
        print("  ⚠ sin whisper.cpp: los subtítulos se reparten por largo de palabra "
              "(se nota un poco menos sincronizado)", file=sys.stderr)
