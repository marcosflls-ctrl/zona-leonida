"""Carruseles para Instagram y TikTok (1080x1350) con el diseño de Zona Leonida.

Modos:
  python scripts/redes.py noticia src/content/posts/<archivo>.md [...]   → carrusel de cada artículo
  python scripts/redes.py cuenta-atras [--dias N] [--forzar]                 → portada de cuenta atrás
Opciones: --sin-ia (textos sacados del artículo, para pruebas), --no-enviar (solo genera los PNG).

Los PNG se guardan en redes-salida/ y, si hay TELEGRAM_BOT_TOKEN y TELEGRAM_AVISOS_CHAT_ID,
se envían por Telegram en privado (como archivos, sin pérdida de calidad) junto con el texto
y los hashtags listos para copiar.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUENTES = ROOT / "scripts" / "redes" / "fuentes"
SALIDA = ROOT / "redes-salida"
PUBLIC = ROOT / "public"
LANZAMIENTO = date(2026, 11, 19)
# Días en los que sale una portada de cuenta atrás (además, todos los días de la última semana)
HITOS = {60, 50, 45, 40, 35, 30, 25, 21, 20, 15, 14, 12, 10}

W, H = 1080, 1350

# Paletas neón Vice City por sección: (color 1, color 2, color 3) del degradado
PALETAS = {
    "noticias": ("#b45cff", "#ff4fa6", "#ffb36e"),         # atardecer rosa (la de la marca)
    "guias": ("#3ff0e0", "#4fa8ff", "#b45cff"),             # turquesa Ocean Drive
    "trucos": ("#7dff8f", "#3ff0e0", "#4fa8ff"),            # verde palmera neón
    "descubrimientos": ("#ffd25e", "#ff9b4f", "#ff4fa6"),   # dorado de puesta de sol
}
ETIQUETAS = {"OFICIAL", "ÚLTIMA HORA", "RUMOR", "FILTRACIÓN", "GUÍA", "TRUCO", "DESCUBRIMIENTO", "ANÁLISIS", "DESMENTIDO"}
ETIQUETA_SECCION = {"noticias": "NOTICIA", "guias": "GUÍA", "trucos": "TRUCO", "descubrimientos": "DESCUBRIMIENTO"}

CSS = f"""
@font-face {{ font-family: Anton; src: url('{(FUENTES / "anton.woff2").as_uri()}'); }}
@font-face {{ font-family: Montserrat; font-weight: 400; src: url('{(FUENTES / "montserrat-400.woff2").as_uri()}'); }}
@font-face {{ font-family: Montserrat; font-weight: 500; src: url('{(FUENTES / "montserrat-500.woff2").as_uri()}'); }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {W}px; height: {H}px; background: #000; overflow: hidden; }}
body {{ position: relative; font-family: Montserrat, sans-serif; color: #fff; }}
.g {{ background: linear-gradient(90deg, var(--c1) 0%, var(--c2) 55%, var(--c3) 100%);
      -webkit-background-clip: text; background-clip: text; color: transparent;
      -webkit-box-decoration-break: clone; box-decoration-break: clone; }}
.foto {{ position: absolute; left: 0; top: 0; width: {W}px; object-fit: cover; }}
.fundido {{ position: absolute; left: 0; width: {W}px; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 45%, #000 100%); }}
.marca {{ display: flex; align-items: center; gap: 22px; padding: 0 56px; }}
.marca i {{ flex: 1; height: 3px; border-radius: 3px; }}
.marca i:first-child {{ background: linear-gradient(90deg, transparent, var(--c1)); }}
.marca i:last-child {{ background: linear-gradient(90deg, var(--c2), transparent); }}
.marca b {{ font: 400 50px/1 Anton, sans-serif; letter-spacing: .5px; }}
.titular {{ font-family: Anton, sans-serif; font-weight: 400; text-transform: uppercase; text-align: center; line-height: 1.02; color: #fff; }}
.credito {{ position: absolute; right: 34px; top: 30px; font: 500 21px/1 Montserrat; color: rgba(255,255,255,.6); text-shadow: 0 1px 6px rgba(0,0,0,.8); }}
.pagina {{ position: absolute; left: 0; right: 0; bottom: 46px; display: flex; justify-content: space-between; padding: 0 60px; font: 500 26px/1 Montserrat; color: rgba(255,255,255,.55); letter-spacing: 2px; }}
.etiqueta {{ display: inline-block; padding: 13px 26px 11px; border-radius: 999px; border: 3px solid var(--c2);
  font: 500 28px/1 Montserrat; letter-spacing: 7px; color: #fff; background: rgba(0,0,0,.55);
  box-shadow: 0 0 22px var(--c2), inset 0 0 14px color-mix(in srgb, var(--c2) 45%, transparent);
  text-shadow: 0 0 10px var(--c2); }}
.marco {{ position: absolute; padding: 4px; border-radius: 36px; background: linear-gradient(135deg, var(--c1), var(--c2), var(--c3));
  box-shadow: 0 0 40px color-mix(in srgb, var(--c2) 55%, transparent); }}
.marco img {{ display: block; width: 100%; height: 100%; object-fit: cover; border-radius: 32px; }}
.brillo {{ position: absolute; inset: 0; background:
  radial-gradient(700px 520px at 100% 0%, color-mix(in srgb, var(--c1) 24%, transparent), transparent 70%),
  radial-gradient(700px 520px at 0% 100%, color-mix(in srgb, var(--c2) 20%, transparent), transparent 70%); }}
"""

# Ajusta el tamaño de letra hasta que el bloque quepa en su caja
AJUSTE = """
for (const el of document.querySelectorAll('[data-ajustar]')) {
  const maxH = +el.dataset.alto, maxW = el.clientWidth;
  let f = +el.dataset.max;
  el.style.fontSize = f + 'px';
  while ((el.scrollHeight > maxH || el.scrollWidth > maxW + 1) && f > 20) { f -= 2; el.style.fontSize = f + 'px'; }
}
"""


def marcar(texto: str) -> str:
    """'Texto con *palabras destacadas*' → HTML con degradado en lo destacado (y saltos de línea)."""
    t = html.escape(texto.strip())
    t = re.sub(r"\*(.+?)\*", r'<span class="g">\1</span>', t)
    return t.replace("\n", "<br>")


def marca_html(texto: str = "ZONALEONIDA") -> str:
    return f'<div class="marca"><i></i><b class="g">{texto}</b><i></i></div>'


def etiqueta_html(etiqueta: str) -> str:
    return f'<span class="etiqueta">{html.escape(etiqueta)}</span>' if etiqueta else ""


def img_uri(ruta: str | None) -> str:
    if ruta:
        p = PUBLIC / ruta.lstrip("/")
        if p.exists():
            return p.as_uri()
    return (PUBLIC / "img" / "marca" / "banner-movil.webp").as_uri()


def pagina(cuerpo: str, seccion: str = "noticias") -> str:
    c1, c2, c3 = PALETAS.get(seccion, PALETAS["noticias"])
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body style='--c1:{c1};--c2:{c2};--c3:{c3}'>{cuerpo}</body></html>")


def portada(titular: str, foto: str | None, credito: str = "", grande: bool = False,
            seccion: str = "noticias", etiqueta: str = "", diseno: int = 0) -> str:
    """Tres composiciones: 0 = foto arriba y titular abajo (la plantilla), 1 = foto enmarcada en neón
    y titular debajo, 2 = foto a pantalla completa con el titular encima y la marca al pie."""
    cred = f'<div class="credito">{html.escape(credito)}</div>' if credito else ""
    if diseno == 1:
        return pagina(f"""
<div class="brillo"></div>
<div style="position:absolute;left:0;right:0;top:58px">{marca_html()}</div>
<div class="marco" style="left:56px;top:140px;width:968px;height:640px"><img src="{img_uri(foto)}"></div>
{cred.replace('class="credito"', 'class="credito" style="right:80px;top:740px"')}
<div style="position:absolute;left:70px;right:70px;top:830px;text-align:center">
  {etiqueta_html(etiqueta)}
  <div class="titular" data-ajustar data-max="100" data-alto="{360 if etiqueta else 430}" style="margin-top:{26 if etiqueta else 0}px">{marcar(titular)}</div>
</div>""", seccion)
    if diseno == 2:
        return pagina(f"""
<img class="foto" src="{img_uri(foto)}" style="height:{H}px">
<div class="fundido" style="top:420px;height:930px;background:linear-gradient(180deg,transparent 0%,rgba(0,0,0,.6) 35%,rgba(0,0,0,.92) 70%,#000 100%)"></div>
{cred}
<div style="position:absolute;left:70px;right:70px;bottom:170px;text-align:center">
  {etiqueta_html(etiqueta)}
  <div class="titular" data-ajustar data-max="108" data-alto="330" style="margin-top:{28 if etiqueta else 0}px;text-shadow:0 4px 24px rgba(0,0,0,.6)">{marcar(titular)}</div>
</div>
<div style="position:absolute;left:0;right:0;bottom:62px">{marca_html()}</div>""", seccion)
    alto_foto = 1060
    max_f, alto_txt = (170, 330) if grande else (104, 300)
    eti = f'<div style="position:absolute;left:0;right:0;top:{alto_foto - 230}px;text-align:center">{etiqueta_html(etiqueta)}</div>' if etiqueta else ""
    return pagina(f"""
<img class="foto" src="{img_uri(foto)}" style="height:{alto_foto}px">
<div class="fundido" style="top:{alto_foto - 420}px;height:420px"></div>
{cred}{eti}
<div style="position:absolute;left:0;right:0;bottom:64px">
  {marca_html()}
  <div class="titular" data-ajustar data-max="{max_f}" data-alto="{alto_txt}" style="margin:26px 70px 0;max-height:{alto_txt + 40}px">{marcar(titular)}</div>
</div>""", seccion)


def interior(n: int, total: int, texto: str, foto: str | None, credito: str = "", seccion: str = "noticias") -> str:
    cred = f'<div class="credito" style="right:84px;top:582px">{html.escape(credito)}</div>' if credito else ""
    return pagina(f"""
<div class="brillo"></div>
<img class="foto" src="{img_uri(foto)}" style="left:60px;top:150px;width:960px;height:470px;border-radius:30px;border:2px solid rgba(255,255,255,.08)">
{cred}
<div style="position:absolute;left:0;right:0;top:62px">{marca_html()}</div>
<div style="position:absolute;left:70px;right:70px;top:660px">
  <div class="g" style="font:400 120px/1 Anton;display:inline-block">{n - 1:02d}</div>
  <div class="titular" data-ajustar data-max="96" data-alto="470" style="text-align:left;margin-top:22px;max-height:500px">{marcar(texto)}</div>
</div>
<div class="pagina"><span>{n} / {total}</span><span>ZONALEONIDA.COM</span></div>""", seccion)


def final(foto: str | None, seccion: str = "noticias") -> str:
    frase = {"guias": "LEE LA GUÍA<br><span class='g'>COMPLETA</span>",
             "trucos": "TODOS LOS TRUCOS<br><span class='g'>EN LA WEB</span>",
             "descubrimientos": "MÁS SECRETOS<br><span class='g'>EN LA WEB</span>"}.get(seccion, "LEE LA NOTICIA<br><span class='g'>COMPLETA</span>")
    return pagina(f"""
<img class="foto" src="{img_uri(foto)}" style="height:{H}px;opacity:.32;filter:saturate(1.2)">
<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.2),#000 85%)"></div>
<div style="position:absolute;left:0;right:0;top:330px;text-align:center">
  <div class="titular" data-ajustar data-max="118" data-alto="260" style="margin:0 70px">{frase}</div>
  <div style="font:500 40px/1 Montserrat;letter-spacing:10px;margin-top:46px;color:rgba(255,255,255,.85)">ENLACE EN LA BIO</div>
</div>
<div style="position:absolute;left:0;right:0;bottom:250px">{marca_html("ZONALEONIDA.COM")}</div>
<div style="position:absolute;left:0;right:0;bottom:150px;text-align:center;font:500 32px/1 Montserrat;letter-spacing:6px;color:rgba(255,255,255,.7)">SÍGUENOS · @ZONALEONIDA</div>""", seccion)


def renderizar(paginas: list[str], carpeta: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--allow-file-access-from-files"])
        pag = nav.new_page(viewport={"width": W, "height": H})
        for i, contenido in enumerate(paginas, 1):
            tmp = carpeta / f"_{i}.html"
            tmp.write_text(contenido, encoding="utf-8")
            pag.goto(tmp.as_uri())
            pag.evaluate("document.fonts.ready")
            pag.wait_for_load_state("networkidle")
            pag.evaluate(AJUSTE)
            ruta = carpeta / f"{i:02d}.png"
            pag.screenshot(path=str(ruta))
            tmp.unlink()
            rutas.append(ruta)
        nav.close()
    return rutas


# ---------- textos ----------

def leer_post(path: Path) -> dict:
    s = path.read_text(encoding="utf-8")
    head, body = s.split("\n---\n", 1)
    get = lambda k: (re.search(rf'^{k}:\s*"?(.*?)"?\s*$', head, re.M) or [None, ""])[1]
    imgs = re.findall(r'(/img/[\w/.-]+\.webp)', body)
    return {"slug": path.stem, "title": get("title"), "description": get("description"), "category": get("category"),
            "image": get("image") or f"/img/portadas/{get('category')}.webp", "credit": get("imageCredit"),
            "body": body, "imagenes": [i for i in dict.fromkeys(imgs) if not re.search(r"-(400|800)\.webp$", i)]}


PROMPT = """Eres el community manager de Zona Leonida, una web de noticias de GTA VI en español neutro \
(España y Latinoamérica). Con el artículo que te paso, prepara un carrusel para Instagram y TikTok.

NORMAS:
- Usa SOLO información del artículo. No inventes ni exageres. Nada de clickbait engañoso.
- "titular": máx. 9 palabras, directo e impactante, en español neutro. Marca entre asteriscos 1-3 \
palabras clave para destacarlas en color (ej. "Rockstar confirma *el precio* de GTA 6").
- "puntos": exactamente 3 frases cortas (máx. 18 palabras cada una) con los datos clave, en orden lógico. \
Puedes destacar 1-2 palabras por frase con asteriscos.
- "texto": pie de publicación de 2-4 frases: empieza con un gancho, resume la noticia y termina con una \
pregunta para que la gente comente. Sin enlaces (di "enlace en la bio" si hace falta). Algún emoji, sin abusar.
- "hashtags": 8-12 hashtags relevantes (#GTA6 #GTAVI #GTA6Noticias, y otros según el tema).
- "etiqueta": UNA de estas, la que mejor describa el artículo: OFICIAL (lo confirma Rockstar/Take-Two), ÚLTIMA HORA (novedad importante e inesperada), RUMOR (no confirmado), FILTRACIÓN, DESMENTIDO (aclara un bulo), ANÁLISIS, GUÍA, TRUCO, DESCUBRIMIENTO. Si hay dudas entre OFICIAL y RUMOR, elige RUMOR.
- "tuit": tuit para X de máx. 240 caracteres, SIN enlace: el dato principal contado de forma directa y con gancho, 1-2 hashtags como mucho (#GTA6). Tono de medio informativo cercano, no de bot.
- "respuesta": respuesta al propio tuit, de máx. 120 caracteres, que invite a leer más (el enlace se añade después).

Responde SOLO con JSON válido: {"titular": "...", "puntos": ["...", "...", "..."], "texto": "...", "hashtags": ["#..."], \
"etiqueta": "...", "tuit": "...", "respuesta": "..."}"""


def textos_ia(post: dict) -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import radar  # reutiliza la conexión con Claude del radar

    client = radar.get_client()
    user = f"TÍTULO: {post['title']}\nRESUMEN: {post['description']}\n\nARTÍCULO:\n{post['body'][:9000]}"
    msg = client.messages.create(model=radar.MODEL, max_tokens=1200, system=PROMPT,
                                 messages=[{"role": "user", "content": user}])
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    data = json.loads(raw)
    if not data.get("titular") or len(data.get("puntos", [])) < 2:
        raise ValueError("faltan campos en la respuesta de la IA")
    return data


def textos_simples(post: dict) -> dict:
    """Sin IA (pruebas): titular del artículo y las primeras frases como puntos."""
    palabras = post["title"].split()
    titular = " ".join(palabras[:2]).join("**") + " " + " ".join(palabras[2:]) if len(palabras) > 2 else post["title"]
    plano = re.sub(r"<[^>]+>|\[([^\]]+)\]\([^)]+\)|[#*>|_`]", lambda m: m.group(1) or "", post["body"])
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", plano) if 40 < len(f.strip()) < 160][:3]
    return {"titular": titular, "puntos": frases or [post["description"]], "texto": post["description"],
            "hashtags": ["#GTA6", "#GTAVI", "#GTA6Noticias", "#Rockstar", "#ViceCity"],
            "tuit": f"{post['title']} #GTA6", "respuesta": "Toda la información aquí 👇"}


# ---------- envío ----------

def enviar_telegram(rutas: list[Path], texto: str, extra: str = "") -> None:
    import requests

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_AVISOS_CHAT_ID")
    if not token or not chat:
        print("Sin TELEGRAM_AVISOS_CHAT_ID: no se envía (los PNG están en redes-salida/)")
        return
    api = f"https://api.telegram.org/bot{token}"
    media, files = [], {}
    for i, r in enumerate(rutas):
        files[f"f{i}"] = (r.name, r.read_bytes(), "image/png")
        media.append({"type": "document", "media": f"attach://f{i}"})
    res = requests.post(f"{api}/sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)}, files=files, timeout=120)
    print("Imágenes:", res.status_code, "" if res.ok else res.text[:200])
    res = requests.post(f"{api}/sendMessage", data={"chat_id": chat, "text": texto}, timeout=30)
    print("Texto:", res.status_code, "" if res.ok else res.text[:200])
    res.raise_for_status()
    if extra:
        res = requests.post(f"{api}/sendMessage", data={"chat_id": chat, "text": extra, "disable_web_page_preview": "true"}, timeout=30)
        print("Tuit:", res.status_code, "" if res.ok else res.text[:200])


# ---------- modos ----------

def carrusel_noticia(path: Path, sin_ia: bool, enviar: bool, diseno_forzado: int | None = None) -> None:
    post = leer_post(path)
    print(f"→ {post['title']}")
    t = textos_simples(post) if sin_ia else textos_ia(post)
    puntos = t["puntos"][:3]
    fotos = [post["image"]] + [i for i in post["imagenes"] if i != post["image"]]
    oficial = lambda f: "Imagen: Rockstar Games" if f and "/oficial/" in f else ""
    cred_portada = f"Imagen: {post['credit']}" if post["credit"] else oficial(post["image"])
    total = len(puntos) + 2
    sec = post["category"] if post["category"] in PALETAS else "noticias"
    eti = (t.get("etiqueta") or "").upper().strip()
    if eti not in ETIQUETAS:
        eti = ETIQUETA_SECCION.get(sec, "")
    diseno = diseno_forzado if diseno_forzado is not None else sum(post["slug"].encode()) % 3  # alterna las composiciones de portada
    print(f"  sección {sec} · etiqueta {eti} · composición {diseno}")
    paginas = [portada(t["titular"], post["image"], cred_portada, seccion=sec, etiqueta=eti, diseno=diseno)]
    for i, p in enumerate(puntos):
        f = fotos[(i + 1) % len(fotos)] if len(fotos) > 1 else post["image"]
        paginas.append(interior(i + 2, total, p, f, oficial(f) or (cred_portada if f == post["image"] else ""), sec))
    paginas.append(final(fotos[-1], sec))
    rutas = renderizar(paginas, SALIDA / post["slug"])
    pie = f"{t['texto']}\n\n{' '.join(t['hashtags'])}"
    print(f"  {len(rutas)} imágenes en {SALIDA / post['slug']}\n  Texto:\n{pie}")
    url = f"https://zonaleonida.com/{post['category']}/{post['slug']}/"
    tuit = ""
    if t.get("tuit"):
        tuit = (f"🐦 Para X (con la imagen 01 de portada)\n\n— Tuit —\n\n{t['tuit']}\n\n"
                f"— Respuesta al tuit —\n\n{t.get('respuesta', 'Toda la información aquí 👇')} {url}")
        print(tuit)
    if enviar:
        enviar_telegram(rutas, f"📲 Carrusel listo: {post['title']}\n\n— Texto para Instagram y TikTok —\n\n{pie}", tuit)


def galeria_aleatoria() -> tuple[str, str]:
    data = json.loads((ROOT / "scripts" / "galeria.json").read_text(encoding="utf-8"))
    ok = [g for g in data["imagenes"] if (PUBLIC / "img" / "oficial" / f"{g['slug']}.webp").exists()
          and g["grupo"] in ("vice-city", "jason-y-lucia", "cayos-de-leonida", "jason-duval", "lucia-caminos", "grassrivers")]
    g = random.Random(date.today().toordinal()).choice(ok)
    return f"/img/oficial/{g['slug']}.webp", "Imagen: Rockstar Games"


def cuenta_atras(dias: int | None, forzar: bool, enviar: bool) -> None:
    hoy = datetime.now(timezone.utc).astimezone().date()
    d = dias if dias is not None else (LANZAMIENTO - hoy).days
    if not forzar and not (d in HITOS or 0 <= d <= 7):
        print(f"Faltan {d} días: hoy no toca portada de cuenta atrás.")
        return
    if d > 1:
        titular, pie = f"SOLO *{d} DÍAS*\nPARA *EL DÍA X*", f"⏳ Faltan {d} días para GTA 6. ¿Ya lo tienes reservado? 👇"
    elif d == 1:
        titular, pie = "*MAÑANA*\nSALE *GTA 6*", "🔥 Mañana sale GTA 6. ¿A qué hora vas a empezar a jugar? 👇"
    else:
        titular, pie = "*HOY* SALE\n*GTA 6*", "🌴 ¡Hoy sale GTA 6! Bienvenidos a Leonida. ¿Qué es lo primero que vas a hacer? 👇"
    foto, cred = galeria_aleatoria()
    rutas = renderizar([portada(titular, foto, cred, grande=True)], SALIDA / f"cuenta-atras-{d}")
    pie += "\n\n#GTA6 #GTAVI #CuentaAtras #ViceCity #Leonida #Rockstar #GTA6Noticias"
    print(f"  {rutas[0]}\n{pie}")
    if enviar:
        enviar_telegram(rutas, f"📲 Cuenta atrás: faltan {d} días\n\n— Texto para copiar —\n\n{pie}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["noticia", "cuenta-atras"])
    ap.add_argument("archivos", nargs="*")
    ap.add_argument("--dias", type=int)
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--sin-ia", action="store_true")
    ap.add_argument("--no-enviar", action="store_true")
    ap.add_argument("--diseno", type=int, choices=[0, 1, 2], help="forzar una composición de portada (pruebas)")
    a = ap.parse_args()
    if a.modo == "cuenta-atras":
        cuenta_atras(a.dias, a.forzar, not a.no_enviar)
        return 0
    errores = 0
    for f in a.archivos:
        p = ROOT / f if not Path(f).is_absolute() else Path(f)
        if not p.exists():
            print(f"! no existe {f}")
            continue
        try:
            carrusel_noticia(p, a.sin_ia, not a.no_enviar, a.diseno)
        except Exception as e:  # noqa: BLE001
            errores += 1
            print(f"! error con {f}: {type(e).__name__}: {e}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
