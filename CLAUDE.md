# Reglas del proyecto — Savia Raíz · Dev

- **Nunca generar imágenes de un carrusel sin su HTML de revisión.**
  `generador_imagenes/generar.py contenido/<slug>.json` genera los PNG y
  automáticamente el HTML editable en `generador_html/<slug>.html` (llama a
  `generador_html/generar_html.py` al final). Ese HTML es el punto de
  revisión antes de publicar — ábrelo (o descríbelo) antes de dar por
  terminado un carrusel nuevo.
- **El mismo comando también genera el Reel.** `generar.py` llama al final
  a `generador_reel/generar_reel.py`, que convierte los PNG recién creados
  en `generador_reel/<slug>.mp4` (zoom Ken Burns, transición de
  deslizamiento entre diapositivas, música de fondo sintetizada por
  ffmpeg — no es una pista con licencia real). Requiere `ffmpeg` (`brew
  install ffmpeg`); si falta, el script avisa y omite solo el Reel, sin
  romper la generación de PNG/HTML. Usa `--sin-reel` para saltarlo a
  propósito.
- **La paleta de color alterna por carrusel.** Cada `slug` nuevo recibe la
  siguiente paleta en rotación (`paletas.py`, función `elegir_paleta`) y
  esa asignación queda fija en `paletas_asignadas.json` — nunca coincide
  con la del carrusel inmediatamente anterior, y regenerar el mismo `slug`
  después reproduce la misma paleta. No la fijes a mano ni edites
  `paletas_asignadas.json` salvo para corregir un caso puntual; si se
  agrega una paleta nueva, se hace en `paletas.py` (única fuente de
  verdad para PNG y HTML).
- **No tocar `assets/logo.png` / `assets/logo-white.png`.** El logo de
  mascotas con el lema "Sin amor imposible" es intencional y fue
  confirmado por el usuario — no es un error a corregir.
- **Los carruseles son 4:5 (1080×1350), no cuadrados.** Instagram muestra el
  4:5 a altura completa en el feed; el cuadrado cede ~25% de pantalla y con
  ello tiempo de visualización, que es la señal de ranking más fuerte. La
  constante vive en `generador_imagenes/generar.py` (`W, H`) y está duplicada
  en `generador_html/generar_html.py` (alto del `.slide` y del `.slide-wrap`,
  más `windowHeight` de html2canvas) y en `generador_reel/generar_reel.py`.
  Si se cambia, se cambia en los tres o el HTML de revisión deja de
  corresponder al PNG.
- **El encabezado de las diapositivas de contenido va anclado a `ANCLA`
  (230), no centrado.** Se probó centrar cada bloque verticalmente y el
  kicker saltaba ~150px entre diapositivas, lo que se nota feo al deslizar.
  `anclar()` mantiene la altura fija y solo sube el bloque si el contenido no
  cabría. La portada sí va centrada (`centrar()`) porque no lleva kicker y se
  ve sola en el feed.
- **Hay dos Reels y no son el mismo producto.** `generador_reel/` hace el 4:5
  (el carrusel con zoom, sin voz, gratis) y sale solo al correr `generar.py`.
  `generador_short/` hace el **vertical 1080×1920 animado y narrado**: dibuja
  cada cuadro desde cero (el texto entra, las barras crecen, los números
  suben), la voz la genera Gemini TTS y lleva subtítulos palabra por palabra.
  Ese **no** se dispara solo: cada escena es una llamada a la API, así que es
  un paso aparte y explícito (`generador_short/generar_short.py <json>`).
  Flujo y reglas de guion: skill `reel-vertical` y
  `generador_short/README.md`.
- **El Reel vertical NO es el carrusel en movimiento.** Se probó así y no
  funciona: cinco renglones por escena no se leen en la pestaña de Reels y el
  video se siente "puro texto". Los tipos de escena que se usan son los
  visuales —`frase` (un titular), `numero` (una cifra enorme que sube),
  `comparacion` (dos cifras frente a frente) y `cierre-visual`—, con la imagen
  ocupando la pantalla. Un dato por escena: tres cifras son tres escenas, no
  una con tres barras. Los tipos informativos (`dato`, `lista`, `barras`)
  siguen ahí, pero solo si el usuario pide esa versión.
- **Si la animación ya lo dice, no se escribe.** Antes de poner un titular o
  un número, mira si el objeto ya lo demuestra: una balanza que se vence no
  necesita que encima diga "pesa más". Cuando lo demuestra, la escena va sin
  texto (`"tipo": "muda"`) y la llevan el objeto y la voz. Repetir en texto lo
  que la imagen acaba de mostrar es lo que hace que un short se sienta un
  carrusel.
- **El Reel vertical no lleva barra de avance ni contador "03/06".** Se
  quitaron a propósito: son el lenguaje de un carrusel —anunciarle al
  espectador en qué lámina va y cuántas faltan— y hacían que el Reel se
  leyera como un carrusel en movimiento. Un short no anuncia su estructura,
  y la plataforma dibuja su propia barra encima. Queda solo una filigrana de
  marca discreta arriba a la izquierda (`escenas.dibujar_marca`). Si alguien
  las vuelve a poner, se pierde justo lo que se estaba buscando.
- **El cuadro está partido en dos: arriba el texto, abajo el objeto.** El
  bloque de texto vive entre y=240 y y=860 y el velo oscurece progresivamente
  hasta los ~980 px cuando hay objeto, dejándolo limpio debajo. Si el texto
  baja o el objeto sube, se enciman y el texto deja de leerse — pasó con los
  primeros objetos altos.
- **La comparación va en dos columnas, no apilada.** Apilada ocupaba media
  pantalla y caía sobre el objeto; en columnas el bloque es la mitad de alto y
  las dos cifras quedan encima de las dos cosas que compara.
- **Los subtítulos van abajo (y=1390) y chicos (44 px), a propósito.** Lo
  principal es el titular y la imagen; la transcripción acompaña. Subirlos o
  agrandarlos es volver al problema de que el texto se come el foco.
- **El guion del Reel vertical vive en la llave `"reel"` del mismo JSON del
  carrusel.** Si no está, se deriva del carrusel y el script lo avisa: sirve
  para arrancar pero queda en 60-80 s, porque el texto del carrusel está
  escrito para leerse, no para decirse. Lo que se ve y lo que se dice son
  textos distintos, y en la `voz` los números van en palabras ("setenta y dos
  por ciento", no "72.4%"): Gemini lee cifras de forma impredecible.
- **El Reel vertical se revisa con `--revisar` antes de renderizar.** Deja un
  PNG por escena e imprime la tabla de duraciones. Si una escena dice
  `motivo: lectura` es que hay más texto en pantalla del que la narración
  alcanza a cubrir — se quita texto o se dice más. Es el control equivalente
  al HTML del carrusel.
- **La imagen de cada escena es un OBJETO FÍSICO en estudio, no un fondo
  abstracto.** Se probó con fondos de partículas y nebulosas: se ven bien pero
  no dicen nada y el Reel se siente un telón detrás del texto. Lo que funciona
  es una cosa con peso que demuestre la idea (una balanza que se vence, una
  pila que crece), sobre ciclorama, luz lateral y sombra larga — estética de
  negocio clásico. Es la familia `objeto` de `imagenes.py`, la de por defecto;
  `"familia": "atmosfera"` vuelve a lo abstracto si una escena lo pide.
- **El segundo estado del objeto se EDITA, no se vuelve a generar.** En la
  escena, `"imagen": {"base": "...", "despues": "..."}`: el `despues` es una
  instrucción de edición sobre la imagen base, así que es el mismo objeto
  moviéndose. Dos generaciones del mismo prompt dan dos objetos distintos y el
  plano solo parpadea. Los dos estados se funden dentro de la toma mientras la
  cámara sigue avanzando (`fondos.FondoSecuencia`).
- **El paralaje usa la máscara de Vision de macOS** (`mascara.swift`, copiado
  de audioguías) cuando hay un objeto recortable: el objeto se mueve contra su
  fondo de verdad, y el hueco que deja se rellena con el propio fondo muy
  difuminado (en un ciclorama no hay nada que inventar detrás). Si Vision no
  encuentra objeto —una imagen abstracta— se cae a un mapa de profundidad por
  luminancia. La máscara se guarda junto a la imagen; `.sinobjeto` marca las
  que no tienen.
- **El fondo del Reel vertical es una imagen generada por escena, animada como
  toma de cámara.** Veo no está en la llave (los modelos `veo-*` dan 404, es de
  pago), así que el movimiento sale de animar una imagen: acercamiento,
  paralaje por luminancia, barrido de luz y partículas (`fondos.py`). El motivo
  de cada imagen va en `"imagen"` dentro de la escena, en inglés y concreto; el
  estilo de la casa lo pone `imagenes.py`. Revisa los prompts con `--prompts`
  antes de pagarlos. La música la genera Lyria (`musica.py`), con el colchón
  sintetizado como respaldo si falla.
- **El Reel vertical va sobre fondo oscuro aunque al carrusel le haya tocado
  una paleta clara**, conservando los acentos del slug. A pantalla completa y
  con la interfaz de Instagram encima, el blanco sobre blanco se lava. El
  script lo avisa; `--paleta-clara` respeta la paleta tal cual.
- **No cambies los filtros de reescalado de `fondos.py` "por calidad".** Las
  capas difuminadas usan NEAREST a propósito: es 13× más rápido y la diferencia
  contra BILINEAR es de 0.6/255 por canal. Ahí está casi todo el tiempo de
  render (46 ms por cuadro de los que ~9 son fondo).
- **Renderiza el Reel vertical en segundo plano.** Tarda poco más de un minuto
  y si el proceso muere a media escritura el MP4 queda sin índice y es
  inservible.
- **La caché de voz vive en `generador_short/.voz/`** (hash de modelo, voz,
  dirección y texto), las imágenes en `.imagenes/` y la música en `.musica/`,
  todas en `.gitignore`. Regenerar por un cambio de
  animación o de color no vuelve a gastar cuota; solo cambia lo que cambió de
  texto o de estilo. `--force` la ignora.
- **Los 429 de Gemini no son todos iguales.** `voz.explicar_429()` los separa:
  tope de gasto mensual del proyecto (no se arregla esperando ni reintentando —
  hay que subir el tope en la consola de facturación), cuota diaria (se
  reinicia a medianoche del Pacífico) y congestión pasajera (ahí sí reintenta
  solo, hasta tres veces). Si aparece el del tope de gasto, lo que ya está en
  caché sirve: se puede seguir con `--sin-imagenes --musica-simple` o
  `--sin-voz` sin gastar nada.
- **`GEMINI_API_KEY` va en el `.env` de esta cuenta** (o se pasa `--env`).
  Nunca la imprimas: para comprobar que está, `grep -c GEMINI_API_KEY .env`.
- **El handle es `@saviaraiz.dev`.** Es la cuenta real. No escribir
  `@savia.raiz`: esa no existe y era la única CTA del carrusel.
- **`.venv/bin/activate` no funciona**: el venv se creó cuando la carpeta del
  proyecto se llamaba `código` (con tilde) y hoy es `codigo`, así que las
  rutas internas no resuelven. Llama al binario directo:
  `./.venv/bin/python3 generador_imagenes/generar.py ...`

- El Python del sistema en macOS está gestionado por Homebrew
  (externally-managed-environment); usa el venv del proyecto (`.venv/`,
  `pip install -r requirements.txt`) en vez de `pip install --break-system-packages`.
