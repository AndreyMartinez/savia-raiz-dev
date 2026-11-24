#!/usr/bin/env python3
"""
Genera la vista previa HTML editable de un carrusel a partir del mismo JSON
de contenido que usa generador_imagenes/generar.py, con la misma paleta de
color (ver ../paletas.py) para que PNG y HTML luzcan igual.

Uso:
  python generar_html.py ../generador_imagenes/contenido/mcp.json
  python generar_html.py ../generador_imagenes/contenido/mcp.json --salida ./out.html

Normalmente no hace falta llamarlo a mano: generar.py lo invoca automáticamente
después de generar los PNG, para que cada carrusel tenga su HTML de revisión.
"""
import os
import sys
import json
import html
import base64
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from paletas import INK, MUTED, BODY, STRONG, elegir_paleta

LOGO_OSCURO = os.path.join(HERE, "..", "assets", "logo.png")
LOGO_CLARO = os.path.join(HERE, "..", "assets", "logo-white.png")
CAPTIONS_DIR = os.path.join(HERE, "..", "publicar", "captions")


def _esc(txt):
    return html.escape(str(txt), quote=False)


def _logo_base64(paleta):
    # Paletas oscuras (fondo oscuro) usan el logo ya convertido a blanco;
    # la paleta "blanco" (fondo claro) usa el logo original, oscuro.
    path = LOGO_OSCURO if paleta.get("claro") else LOGO_CLARO
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _leer_caption(slug):
    path = os.path.join(CAPTIONS_DIR, f"{slug}.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return "(Pega aquí el caption + hashtags — ver publicar/captions/)"


def _slide_html(slide, slug, total, paleta):
    num = slide["num"]
    kind = slide["kind"]
    rail = (
        '<div class="rail"><div class="top"><span class="r-dot"></span>'
        '<span class="r-brand">SAVIA · RAÍZ</span></div>'
        f'<div class="r-num"><b>{num}</b><span>/{total:02d}</span></div></div>'
    )

    if kind == "cover":
        body = f'''<div class="body cover">
          <div class="eyebrow" contenteditable>{_esc(slide["eyebrow"])}</div>
          <h2 contenteditable>{_esc(slide["title"])}</h2>
          <div class="sub" contenteditable>{_esc(slide["sub"])}</div>
          <div class="swipe" contenteditable>Desliza →</div>
        </div>'''
        clase = "slide cover"
    elif kind == "text":
        body = f'''<div class="body content">
          <div class="kicker" contenteditable>{_esc(slide["kicker"])}</div>
          <h2 contenteditable>{_esc(slide["h"])}</h2>
          <p contenteditable>{_esc(slide["body"])}</p>
        </div>'''
        clase = "slide"
    elif kind == "list":
        items = "\n".join(
            f'            <li contenteditable><b>{_esc(label)}</b> {_esc(rest)}</li>'
            for label, rest in slide["items"]
        )
        foot = f'\n          <div class="foot" contenteditable>{_esc(slide["foot"])}</div>' if slide.get("foot") else ""
        body = f'''<div class="body content">
          <div class="kicker" contenteditable>{_esc(slide["kicker"])}</div>
          <h2 contenteditable>{_esc(slide["h"])}</h2>
          <ul class="pts">
{items}
          </ul>{foot}
        </div>'''
        clase = "slide"
    elif kind == "chart":
        maxv = slide.get("max") or max(b["value"] for b in slide["bars"])
        unit = slide.get("unit", "")
        rows = []
        for b in slide["bars"]:
            pct = round(min(max(b["value"] / maxv, 0), 1) * 100, 1)
            note = _esc(b["vlabel"]) if b.get("vlabel") else f'{b["value"]:g}{unit}'
            if b.get("note"):
                note += f'  ·  {_esc(b["note"])}'
            rows.append(f'''          <div class="bar-row">
            <div class="bar-label" contenteditable>{_esc(b["label"])}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
            <div class="bar-note" contenteditable>{note}</div>
          </div>''')
        foot = f'\n          <div class="foot" contenteditable>{_esc(slide["foot"])}</div>' if slide.get("foot") else ""
        body = f'''<div class="body content">
          <div class="kicker" contenteditable>{_esc(slide["kicker"])}</div>
          <h2 contenteditable>{_esc(slide["h"])}</h2>
          <div class="chart">
{chr(10).join(rows)}
          </div>{foot}
        </div>'''
        clase = "slide"
    elif kind == "end":
        cta = slide["cta"]
        body = f'''<div class="body end">
          <div class="kicker" contenteditable>{_esc(slide["kicker"])}</div>
          <h2 contenteditable>{_esc(slide["h"])}</h2>
          <div class="one" contenteditable>{_esc(slide["one"])}</div>
          <div class="sign">
            <img src="data:image/png;base64,{_logo_base64(paleta)}" alt="Savia Raíz">
            <div class="cta">
              <div contenteditable>{_esc(cta[0])}</div>
              <div contenteditable>{_esc(cta[1])}</div>
              <div class="handle" contenteditable>{_esc(cta[2])}</div>
            </div>
          </div>
        </div>'''
        clase = "slide end"
    else:
        raise ValueError(f"kind de slide desconocido: {kind}")

    return f'''    <div class="slide-wrap">
      <div class="{clase}" data-name="{slug}-{num}">
        {rail}
        {body}
      </div><button class="dl">⬇ PNG</button>
    </div>'''


TEMPLATE = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carrusel {titulo} · Savia Raíz</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
  :root{{
    --bg:{bg}; --panel:#0C1326; --slide-a:{slide_a}; --slide-b:{slide_b};
    --ink:{ink}; --muted:{muted}; --body:{body}; --strong:{strong}; --line:rgba(120,150,220,0.14);
    --accent:{accent}; --accent2:{accent2}; --chip:rgba(91,140,255,0.12);
    --scale:0.42;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
  .bar{{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:16px;flex-wrap:wrap;
    padding:14px 20px;background:rgba(8,13,26,.86);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
  .bar h1{{font-family:'Space Grotesk';font-size:16px;font-weight:600;margin:0;display:flex;align-items:center;gap:9px}}
  .bar h1 .dot{{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}}
  .bar .hint{{color:var(--muted);font-size:12.5px;margin-right:auto}}
  .btn{{font-family:'JetBrains Mono';font-size:12px;font-weight:500;color:var(--ink);background:var(--chip);
    border:1px solid var(--line);padding:9px 14px;border-radius:8px;cursor:pointer;transition:.15s}}
  .btn:hover{{border-color:var(--accent);background:rgba(91,140,255,.18)}}
  .btn.primary{{background:linear-gradient(90deg,var(--accent),var(--accent2));border:none;color:#fff;font-weight:600}}
  .wrap{{max-width:560px;margin:0 auto;padding:26px 16px 80px}}
  .slides{{display:flex;flex-direction:column;gap:30px;align-items:center}}
  .slide-wrap{{position:relative;width:calc(1080px*var(--scale));height:calc(1350px*var(--scale));
    border-radius:14px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.55)}}
  .dl{{position:absolute;bottom:9px;right:9px;z-index:5;font-family:'JetBrains Mono';font-size:11px;
    background:rgba(8,13,26,.72);color:var(--ink);border:1px solid var(--line);border-radius:7px;
    padding:6px 10px;cursor:pointer;backdrop-filter:blur(4px)}}
  .dl:hover{{border-color:var(--accent);color:#fff}}
  .slide{{width:1080px;height:1350px;transform:scale(var(--scale));transform-origin:top left;position:relative;overflow:hidden;
    background:
      radial-gradient(1200px 600px at 78% -10%, rgba(91,140,255,.10), transparent 60%),
      radial-gradient(900px 700px at -10% 110%, rgba(155,107,255,.09), transparent 55%),
      linear-gradient(160deg,var(--slide-a),var(--slide-b));display:flex}}
  .slide::before{{content:"";position:absolute;inset:0;pointer-events:none;
    background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
    background-size:90px 90px;
    -webkit-mask-image:radial-gradient(circle at 60% 40%,#000 30%,transparent 88%);
            mask-image:radial-gradient(circle at 60% 40%,#000 30%,transparent 88%);opacity:.5}}
  .rail{{width:118px;flex:0 0 118px;position:relative;z-index:2;border-right:1px solid var(--line);
    display:flex;flex-direction:column;justify-content:space-between;padding:64px 0 60px}}
  .rail .top{{display:flex;flex-direction:column;align-items:center;gap:20px}}
  .rail .r-dot{{width:12px;height:12px;border-radius:50%;
    background:conic-gradient(from 0deg,var(--accent),var(--accent2),var(--accent));box-shadow:0 0 18px rgba(91,140,255,.7)}}
  .rail .r-brand{{font-family:'JetBrains Mono';font-size:17px;color:var(--muted);writing-mode:vertical-rl;letter-spacing:4px}}
  .rail .r-num{{font-family:'Space Grotesk';font-weight:700;text-align:center}}
  .rail .r-num b{{display:block;font-size:40px;background:linear-gradient(90deg,var(--accent),var(--accent2));
    -webkit-background-clip:text;background-clip:text;color:transparent}}
  .rail .r-num span{{font-family:'JetBrains Mono';font-weight:400;font-size:18px;color:var(--muted)}}
  .body{{flex:1;position:relative;z-index:2;padding:78px 76px 70px;display:flex;flex-direction:column}}
  .kicker{{font-family:'JetBrains Mono';font-size:21px;letter-spacing:3px;color:var(--accent);
    margin-bottom:26px;display:inline-flex;align-items:center;gap:12px}}
  .kicker::before{{content:"";width:34px;height:2px;background:linear-gradient(90deg,var(--accent),var(--accent2))}}
  h2{{font-family:'Space Grotesk';font-weight:700;line-height:1.04;margin:0}}
  p,li{{font-size:34px;line-height:1.42;color:var(--body);margin:0}}
  .cover .eyebrow{{font-family:'JetBrains Mono';font-size:22px;letter-spacing:4px;color:var(--muted)}}
  .cover h2{{font-size:104px;margin:34px 0 0;letter-spacing:-1px}}
  .cover .sub{{font-size:38px;color:var(--muted);margin-top:26px;max-width:640px}}
  .cover .swipe{{margin-top:auto;font-family:'JetBrains Mono';font-size:26px;color:var(--accent)}}
  .content h2{{font-size:66px;margin-bottom:30px}}
  .content p{{max-width:720px}}
  ul.pts{{list-style:none;padding:0;margin:8px 0 0;display:flex;flex-direction:column;gap:26px}}
  ul.pts li{{position:relative;padding-left:44px;max-width:730px}}
  ul.pts li::before{{content:"";position:absolute;left:0;top:15px;width:14px;height:14px;border-radius:4px;
    background:linear-gradient(135deg,var(--accent),var(--accent2))}}
  ul.pts li b{{color:var(--strong);font-weight:600}}
  .foot{{font-family:'JetBrains Mono';font-size:24px;color:var(--accent);margin-top:auto}}
  .chart{{display:flex;flex-direction:column;gap:36px;margin-top:6px}}
  .bar-label{{font-family:'Space Grotesk';font-weight:600;font-size:32px;color:var(--strong);margin-bottom:14px}}
  .bar-track{{width:100%;height:34px;border-radius:17px;background:rgba(120,150,220,.14);overflow:hidden}}
  .bar-fill{{height:100%;border-radius:17px;background:linear-gradient(90deg,var(--accent),var(--accent2))}}
  .bar-note{{font-family:'JetBrains Mono';font-size:22px;color:var(--muted);margin-top:10px}}
  .end h2{{font-size:60px}}
  .end .one{{font-size:44px;color:var(--strong);line-height:1.38;max-width:730px;font-family:'Space Grotesk';font-weight:500;margin-top:24px}}
  .end .sign{{margin-top:auto;border-top:1px solid var(--line);padding-top:34px;display:flex;align-items:center;gap:34px}}
  .end .sign img{{height:150px;width:auto;opacity:.95}}
  .end .sign .cta{{display:flex;flex-direction:column;gap:12px}}
  .end .sign .cta div{{font-size:30px;color:var(--body)}}
  .end .sign .cta .handle{{font-family:'JetBrains Mono';font-size:28px;color:var(--accent)}}
  [contenteditable]{{outline:none;border-radius:6px;transition:box-shadow .15s}}
  [contenteditable]:hover{{box-shadow:0 0 0 2px rgba(91,140,255,.25)}}
  [contenteditable]:focus{{box-shadow:0 0 0 2px var(--accent)}}
  .cap{{max-width:560px;margin:44px auto 0;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px}}
  .cap h3{{font-family:'Space Grotesk';font-size:14px;margin:0 0 12px;display:flex;align-items:center;gap:9px}}
  .cap h3 .dot{{width:7px;height:7px;border-radius:50%;background:var(--accent2)}}
  .cap textarea{{width:100%;min-height:280px;resize:vertical;background:#0A1020;border:1px solid var(--line);
    border-radius:10px;color:#D3DCF0;font-family:'Inter';font-size:13.5px;line-height:1.6;padding:14px}}
  .cap .footc{{display:flex;justify-content:flex-end;margin-top:10px}}
</style>

<div class="bar">
  <h1><span class="dot"></span>Carrusel {titulo} · Savia Raíz</h1>
  <span class="hint">Haz clic en cualquier texto para editarlo · vista previa aquí · descarga en PNG 1080×1350 · paleta: {paleta_nombre}</span>
  <button class="btn primary" id="all">⬇ Descargar todas</button>
</div>

<div class="wrap">
  <div class="slides" id="slides">
{slides}
  </div>

  <div class="cap">
    <h3><span class="dot"></span>Descripción (caption + hashtags)</h3>
    <textarea id="caption">{caption}</textarea>
    <div class="footc"><button class="btn" id="copy">Copiar descripción</button></div>
  </div>
</div>

<script>
  function setScale(){{
    const w = Math.min(480, document.getElementById('slides').clientWidth);
    document.documentElement.style.setProperty('--scale', (w/1080).toFixed(4));
  }}
  window.addEventListener('resize', setScale); setScale();

  async function capture(slide){{
    await document.fonts.ready;
    const prev = slide.style.transform;
    slide.style.transform = 'none';
    const canvas = await html2canvas(slide, {{backgroundColor:'{slide_a}', width:1080, height:1080,
      windowWidth:1080, windowHeight:1350, scale:1, useCORS:true}});
    slide.style.transform = prev;
    return canvas;
  }}
  function save(canvas, name){{
    const a=document.createElement('a'); a.href=canvas.toDataURL('image/png'); a.download=name+'.png'; a.click();
  }}
  document.querySelectorAll('.slide-wrap').forEach(w=>{{
    const btn=w.querySelector('.dl'), slide=w.querySelector('.slide');
    btn.addEventListener('click', async ()=>{{ btn.textContent='…'; save(await capture(slide), slide.dataset.name); btn.textContent='⬇ PNG'; }});
  }});
  // Los navegadores bloquean varias descargas automáticas seguidas (solo dejan
  // pasar la primera), así que "Descargar todas" empaqueta las 6 en un único
  // ZIP en vez de disparar 6 descargas sueltas.
  document.getElementById('all').addEventListener('click', async (e)=>{{
    const b=e.target; b.textContent='Generando…'; b.disabled=true;
    const zip = new JSZip();
    for(const s of document.querySelectorAll('.slide')){{
      const canvas = await capture(s);
      const blob = await new Promise(res=>canvas.toBlob(res,'image/png'));
      zip.file(s.dataset.name+'.png', blob);
    }}
    const content = await zip.generateAsync({{type:'blob'}});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(content); a.download='{slug}.zip'; a.click();
    URL.revokeObjectURL(a.href);
    b.textContent='⬇ Descargar todas'; b.disabled=false;
  }});
  document.getElementById('copy').addEventListener('click', (e)=>{{
    navigator.clipboard.writeText(document.getElementById('caption').value)
      .then(()=>{{ e.target.textContent='¡Copiado!'; setTimeout(()=>e.target.textContent='Copiar descripción',1500); }});
  }});
</script>
"""


def generar(contenido_path, paleta=None, salida=None):
    with open(contenido_path, encoding="utf-8") as f:
        data = json.load(f)

    slug = data.get("slug", "carrusel")
    paleta = paleta or elegir_paleta(slug)
    slides = data["slides"]
    total = len(slides)

    slides_html = "\n\n".join(_slide_html(s, slug, total, paleta) for s in slides)

    doc = TEMPLATE.format(
        titulo=_esc(slug.upper()),
        slug=slug,
        bg=paleta["bg"], slide_a=paleta["slide_a"], slide_b=paleta["slide_b"],
        ink=paleta.get("ink", INK), muted=paleta.get("muted", MUTED),
        body=paleta.get("body", BODY), strong=paleta.get("strong", STRONG),
        accent=paleta["accent"], accent2=paleta["accent2"],
        paleta_nombre=paleta["nombre"],
        slides=slides_html,
        caption=_esc(_leer_caption(slug)),
    )

    salida = salida or os.path.join(HERE, f"{slug}.html")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(doc)
    return salida


def main():
    ap = argparse.ArgumentParser(description="Genera el HTML de revisión de un carrusel desde su JSON de contenido.")
    ap.add_argument("contenido", help="Ruta al archivo JSON de contenido")
    ap.add_argument("--salida", default=None, help="Ruta del HTML de salida (por defecto ./<slug>.html)")
    args = ap.parse_args()
    path = generar(args.contenido, salida=args.salida)
    print(f"ok {path}")


if __name__ == "__main__":
    main()
