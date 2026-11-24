# generador_short — Reel vertical animado con voz e imagen

Reel en formato short (1080×1920, 9:16) con **animación real**, **narración de
Gemini TTS**, **fondo de imagen generada en movimiento** y **música de Lyria**.
Es otro producto que `generador_reel/`:

|                       | `generador_reel/`                  | `generador_short/`                          |
|-----------------------|------------------------------------|---------------------------------------------|
| Formato               | 4:5 (1080×1350)                    | 9:16 (1080×1920), pantalla completa          |
| Cómo se hace          | zoom sobre los PNG del carrusel    | cada cuadro se dibuja desde cero             |
| Movimiento            | Ken Burns + deslizamiento          | texto que entra, barras que crecen, números que suben |
| Fondo                 | el PNG del carrusel                | una imagen generada por escena, con cámara y paralaje |
| Audio                 | colchón sintetizado                | voz narrada + música real (Lyria) + soplo en los cortes |
| Ritmo                 | 7.5 s fijos por diapositiva        | lo que dura la narración de cada escena      |
| Subtítulos            | no                                 | sí, abajo y chicos para no robar el foco     |
| Cuesta API            | no                                 | sí: voz, imagen por escena y una pista de música |

Los dos sirven: el 4:5 es el Reel "carrusel en movimiento" que no gasta nada;
este es el que compite de verdad en la pestaña de Reels, donde el video ocupa
toda la pantalla y casi todo el mundo lo ve en silencio (de ahí los
subtítulos).

## La imagen es un objeto, no un fondo

Cada escena lleva **una cosa física en estudio que demuestra la idea** — una
balanza que se vence, una pila que crece — sobre ciclorama, con luz lateral y
sombra larga. Estética de negocio clásico, materiales con peso: metal pulido,
piedra, cerámica mate.

Se probó antes con fondos abstractos (partículas, nebulosas): se ven bien pero
no dicen nada, y el Reel acaba siendo un telón detrás del texto. `"familia":
"atmosfera"` en la escena vuelve a eso si alguna vez conviene.

**El segundo estado.** Si el dato de la escena *es* un cambio, el objeto cambia
dentro de la toma:

```json
"imagen": {
  "base": "A classic brass balance scale: one small polished cube outweighs a much larger hollow block",
  "despues": "Tip the balance further, so the small cube settles decisively at the bottom"
}
```

El `despues` **edita la imagen base** en vez de generar otra: así es el mismo
objeto moviéndose. Dos generaciones del mismo prompt darían dos objetos
distintos y el plano solo parpadearía. Los dos estados se funden mientras la
cámara sigue avanzando, así que se ve como una sola toma.

**Paralaje real.** Cuando hay un objeto recortable, la máscara la da Vision de
macOS (`mascara.swift`) y el objeto se mueve contra su fondo de verdad; el
hueco que deja se rellena con el propio fondo muy difuminado, que en un
ciclorama es exacto. Si Vision no encuentra objeto, se cae a un mapa de
profundidad por luminancia. La máscara queda junto a la imagen, y `.sinobjeto`
marca las que no tienen.

## Sobre el video: por qué imagen y no Veo

**Veo no está disponible en esta llave de Gemini.** Los modelos `veo-*`
devuelven 404 y no aparecen entre los 65 que lista la API; Veo es de pago, así
que con una llave con facturación activada probablemente sí aparezca. Lo que sí
hay es generación de imagen en 9:16 a 2K.

Así que el movimiento no viene de un modelo de video: viene de animar la imagen
como una toma de cámara, que es lo mismo que hacen las audioguías de este mismo
usuario con las fotos. Por escena:

- **Cámara**: un acercamiento lento con deriva lateral, distinto en cada escena.
- **Paralaje**: la luminancia de la imagen hace de mapa de profundidad (en una
  imagen así lo brillante está cerca y la sombra lejos), y el frente se acerca
  más rápido que el fondo. Eso es lo que separa "video" de "PNG con zoom".
- **Barrido de luz** que cruza en diagonal, y **partículas** que suben.
- **Velo** de degradado en el color de la paleta, para que el texto se lea
  encima sin cajas.
- El fondo **se funde** en cada cambio de escena, así que el corte se siente
  como un plano que cambia.

El día que la llave tenga Veo, el único archivo que hay que tocar es
`imagenes.py`: el resto del generador solo pide "el fondo de la escena N".

## Uso

```bash
cd savia-raiz-dev
./.venv/bin/python3 generador_short/generar_short.py \
    generador_imagenes/contenido/<slug>.json
```

Pasos del flujo, en orden:

```bash
# 1. borrador del guion a partir del carrusel (no gasta API)
./.venv/bin/python3 generador_short/generar_short.py <json> --guion

# 2. revisar los prompts de imagen antes de pagarlos (no gasta API)
./.venv/bin/python3 generador_short/generar_short.py <json> --prompts

# 3. (opcional) escuchar los estilos de voz antes de decidir
./.venv/bin/python3 generador_short/generar_short.py <json> --muestras

# 4. revisar un PNG por escena antes de renderizar 1600 cuadros
./.venv/bin/python3 generador_short/generar_short.py <json> --revisar

# 5. el video
./.venv/bin/python3 generador_short/generar_short.py <json>
```

Opciones: `--estilo <nombre>`, `--sin-voz`, `--sin-imagenes` (fondo de marca,
sin gastar API), `--sin-musica`, `--musica-simple` (colchón sintetizado en vez
de Lyria), `--sin-subtitulos`, `--paleta-clara`, `--cuadro <segundo>`,
`--force` (vuelve a pedir voz, imagen y música), `--env <ruta/.env>`,
`--salida <mp4>`.

El render va a ~21 cuadros por segundo: un Reel de 50 s tarda poco más de un
minuto. Si se modifica `fondos.py`, ojo con los filtros de reescalado — ahí
está casi todo el tiempo de render (ver los comentarios de `_recorte`).

## El guion vive en el JSON del carrusel

En la llave `"reel"`. Si no está, se deriva del carrusel y el script lo avisa:
sirve para arrancar, pero queda largo, porque el texto del carrusel está
escrito para leerse, no para decirse.

```json
"reel": {
  "estilo": "noticia",
  "escenas": [
    {"tipo": "gancho", "kicker": "CLAUDE · IA",
     "titulo": "La IA de centavos|ya usa una computadora",
     "texto": "De 15.7% a 72.4% en manejar una computadora real.",
     "voz": "La inteligencia artificial más barata de Anthropic acaba de pasar de quince a setenta y dos por ciento… en una prueba de manejar una computadora real."}
  ]
}
```

- `titulo` — `|` parte renglones a mano. Si un renglón no cabe, el cuerpo baja
  solo hasta que entre (no se corta contra el borde como en el carrusel).
- `voz` — lo que se dice, que **no** es lo que se ve: los números van en
  palabras ("setenta y dos por ciento", no "72.4%") y `…` marca una pausa
  corta. Si falta, la escena va muda y dura su mínimo de lectura.
- `pie` — fuente, abajo y discreta.
- `imagen` — el **motivo visual** del fondo, en inglés y concreto. El estilo de
  la casa (paleta, profundidad, "sin texto", iluminación según la paleta) lo
  añade `imagenes.py`; aquí va solo la idea. Una idea concreta siempre gana:
  `"A swarm of small particles migrating from a sparse cluster to a dense one"`
  rinde mucho más que `"artificial intelligence"`. Si falta, se deriva del
  kicker y el título, que sale genérico.

Y en el bloque `"reel"`, además de `estilo`, se puede poner `"musica"` con una
descripción libre de la pista; si no, se elige según el estilo de voz.

### Tipos de escena

**Los visuales** son los que se usan: la imagen ocupa la pantalla y el texto es
un titular o un número. Meter el carrusel dentro del video no funciona — cinco
renglones por escena no se leen mientras alguien escucha.

| `tipo`           | Qué pone en pantalla                  | Campos                                              |
|------------------|---------------------------------------|-----------------------------------------------------|
| `frase`          | un titular, palabra por palabra       | `kicker`, `titulo`, `texto`                          |
| `numero`         | una cifra enorme que sube             | `etiqueta`, `valor`, `antes`, `unidad`, `nota`, `texto`, `vlabel` |
| `comparacion`    | dos cifras frente a frente            | `etiqueta`, `a:{label,valor}`, `b:{label,valor}`, `unidad`, `contra` |
| `muda`           | **nada**: la llevan el objeto y la voz | `kicker` opcional                                   |
| `cierre-visual`  | una frase, el handle y nada más       | `titulo`, `cta`, `handle`                            |

Un dato por escena: tres cifras son tres escenas `numero`, no una con tres
barras. En `numero` y `comparacion`, `antes` hace que la cifra suba **desde**
ese valor en vez de desde cero.

**Los informativos** quedan para cuando se quiere la versión "carrusel en
movimiento":

| `tipo`   | Para qué                     | Campos                                               |
|----------|------------------------------|------------------------------------------------------|
| `gancho` | abrir                        | `kicker`, `titulo`, `texto`                           |
| `dato`   | una idea                     | `kicker`, `titulo`, `texto`, `pie`                    |
| `lista`  | 2-3 puntos                   | `kicker`, `titulo`, `items: [[etiqueta, resto]]`      |
| `barras` | números comparables          | `kicker`, `titulo`, `unidad`, `max`, `barras`, `pie`  |
| `cita`   | una frase que pesa           | `texto`, `autor`                                      |
| `cierre` | resumen + llamada a la acción| `kicker`, `titulo`, `cta: []`, `handle`               |

En `barras`, cada barra es `{"label", "valor", "nota", "antes", "vlabel"}`.
Con `"antes"` el número **sube desde ese valor** en vez de desde cero: es la
animación que mejor cuenta un "antes y después" sin decir una palabra.

### Estilos de voz

`noticia`, `explicativo`, `energico`, `cercano`, `suspenso`, `motivacional`
(ver `voz.py`). También se puede pasar `"Voz:dirección libre"`, p. ej.
`--estilo "Charon:Locutor serio, ritmo lento."`. `--muestras` genera la misma
frase en todos para elegir con el oído.

## Qué necesita

- `ffmpeg` (`brew install ffmpeg`).
- `GEMINI_API_KEY` en `savia-raiz-dev/.env` (o `--env <ruta>`). Se consigue en
  aistudio.google.com/apikey. El `.env` está en `.gitignore`. La misma llave
  sirve para voz, imagen y música.
- whisper.cpp, **opcional**: con él los subtítulos quedan sincronizados
  palabra por palabra; sin él se reparten por largo de palabra y se nota un
  poco menos ajustado. Las palabras del subtítulo salen siempre del guion, no
  de whisper, así que nunca escribe mal un nombre.

## Dónde va cada cosa en pantalla

Instagram tapa la franja de arriba y el cuarto de abajo, y además hay que
decidir qué manda. El reparto:

| Zona | Qué va | Por qué |
|---|---|---|
| y 104-148 | filigrana de marca | discreta; **sin barra de avance ni contador**, que es lenguaje de carrusel |
| y 300-1010 | **el titular o el número** | es lo principal; va alto para dejar ver la imagen debajo |
| y 1390-1500 | la transcripción, 44 px | abajo y chica: acompaña, no compite |
| y 1550+ | nada | ahí van los botones y la descripción de Instagram |

Si los subtítulos suben o se agrandan, vuelven a comerse el foco del titular.
Fue el problema de la primera versión.

## El Reel va sobre fondo oscuro

Aunque al carrusel le haya tocado una paleta clara. En el feed un carrusel
claro funciona; en la pestaña de Reels, a pantalla completa y con la interfaz
de Instagram encima, el blanco sobre blanco se lava. Se conservan los **acentos
del slug**, que son los que identifican el post, y se cambia solo el fondo y la
jerarquía de texto. El script lo avisa cuando pasa. `--paleta-clara` respeta la
paleta tal cual.

## Caché de voz, imagen y música

Todo lo que se paga se guarda con un hash de lo que lo produjo:

| Qué | Dónde | Hash de |
|---|---|---|
| voz | `.voz/` | modelo, voz, dirección, texto |
| imagen | `.imagenes/` | modelo, tamaño, prompt completo |
| música | `.musica/` | modelo, prompt |

Volver a generar el mismo Reel no vuelve a pagar nada; cambiar la animación,
ajustar tiempos o re-renderizar tampoco. Solo se pide de nuevo lo que cambió
(o todo, con `--force`). Junto a cada imagen y pista queda su `.txt` con el
prompt, para saber qué la produjo.

Un Reel nuevo de 6 escenas cuesta **6 lecturas de voz + 6 imágenes 2K + 1
pista de música**. El script dice cuántas imágenes va a generar antes de
empezar.

## Duración

El objetivo son **30-50 s**. Cada escena dura lo que dura su narración más un
respiro, con un mínimo por tipo y por cantidad de texto en pantalla; el script
imprime una tabla con el motivo de cada duración:

```
  escena                          voz   dura  motivo
  gancho  La IA de centavos      8.4s   9.2s  voz
  lista   Hasta 90% menos        6.8s   9.7s  lectura
```

`voz` = la narración manda. `lectura` = hay más texto en pantalla del que la
narración alcanza a cubrir; o se dice más, o se pone menos.

## Música

La pista la genera **Lyria** (`lyria-3-clip-preview`), que entrega 30 s: como
un Reel dura más, se encadena consigo misma con un cruce de 3 s hasta cubrir la
duración — en música ambiental sin estructura marcada el empalme no se oye.
Encima van los soplos de cada cambio de escena, que hacen que el corte se oiga
y no solo se vea.

Si Lyria falla, se cae solo al colchón sintetizado de antes (osciladores +
trémolo + pasabajos): quedarse sin música por un error de red sería peor.
`--musica-simple` lo fuerza, `--sin-musica` deja solo la voz.

Nada de esto es una pista con licencia de Instagram: al publicar conviene
además ponerle el audio que ofrece la app, que ayuda al alcance.
