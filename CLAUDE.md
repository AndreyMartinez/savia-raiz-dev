# Reglas del proyecto — Savia Raíz · Dev

- **Nunca generar imágenes de un carrusel sin su HTML de revisión.**
  `generador_imagenes/generar.py contenido/<slug>.json` genera los PNG y
  automáticamente el HTML editable en `generador_html/<slug>.html` (llama a
  `generador_html/generar_html.py` al final). Ese HTML es el punto de
  revisión antes de publicar — ábrelo (o descríbelo) antes de dar por
  terminado un carrusel nuevo.
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
- El Python del sistema en macOS está gestionado por Homebrew
  (externally-managed-environment); usa el venv del proyecto (`.venv/`,
  `pip install -r requirements.txt`) en vez de `pip install --break-system-packages`.
