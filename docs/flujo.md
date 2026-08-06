# Flujo de trabajo

El sistema tiene cuatro etapas: **descubrir → capturar → producir → publicar**.

## 1. Descubrir (fuentes oficiales)

Prioriza siempre la fuente de primera mano (blog oficial, changelog, RFC) sobre
resúmenes de terceros. Centraliza los feeds en un lector RSS (Feedly / Inoreader).

Tres verticales:

- **Dev**: React, Next.js, Rust, Thoughtworks Technology Radar, Refactoring Guru,
  microservices.io.
- **IA**: Anthropic News, OpenAI News, Hugging Face Blog, The Batch (curado).
- **MCP/Skills**: MCP Registry (registry.modelcontextprotocol.io), repo
  modelcontextprotocol/servers, PulseMCP (newsletter semanal), anthropics/skills,
  agentskills.io.

## 2. Capturar (inbox)

Cada hallazgo se guarda en un inbox (base de datos de Notion "Inbox de Contenido")
con: tema, vertical, tipo, **fuente oficial (URL)**, estado y fecha de publicación.
Estados: Por revisar → Idea → En carrusel → Publicado.

## 3. Producir (este repo)

Cada 3 días se elige un tema del inbox y se convierte en carrusel:

1. Escribe el contenido en `generador_imagenes/contenido/<slug>.json`.
2. Genera imágenes:
   - Retoque visual → abre `generador_html/` y descarga.
   - Por lotes → `python generar.py contenido/<slug>.json`.
3. Escribe el caption en `publicar/captions/<slug>.txt`.

### Estructura recomendada de un carrusel

Portada (hook) → Qué es → Piezas/puntos clave → Ejemplo o código →
Cuándo usarlo → Resumen + CTA (Guarda / Sígueme). 6 diapositivas funciona bien;
Instagram admite hasta 10.

## 4. Publicar

- **Manual**: sube los PNG y pega el caption en la app.
- **Programado sin intervención**: Meta Business Suite (planificador nativo) o un
  scheduler (Later / Metricool).
- **Automático por código**: `publicar/publicar_instagram.py` (Graph API). Envuélvelo
  en un cron o GitHub Action (`on: schedule:`) con el token en *Secrets* para que
  publique en la fecha del calendario editorial.

## Buenas prácticas de contenido

- Optimiza para **guardar** y **compartir**, no para likes: es contenido educativo.
- El **hook** de la portada decide si deslizan. Que prometa algo concreto.
- Cita la fuente oficial en el caption: te distingue y evita imprecisiones.
- Constancia > frecuencia. Mantén 2-3 temas listos en el inbox.
