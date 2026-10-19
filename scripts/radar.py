"""
Radar de noticias de GTA VI.

1. Lee los feeds de scripts/feeds.json
2. Se queda con las novedades sobre GTA VI que aún no ha procesado
3. Descarga cada artículo y le pide a Claude un artículo ORIGINAL en español
4. Lo guarda como .md en src/content/posts/

Uso:
  python scripts/radar.py            # normal (en GitHub usa la federación de identidades, sin clave;
                                     # en tu PC puedes usar ANTHROPIC_API_KEY=...)
  python scripts/radar.py --dry-run                      # solo lista lo que encontraría
Variables opcionales: MAX_PER_RUN (2), MODEL (claude-sonnet-5-5)
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
import calendar
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comunidad  # noqa: E402
import lanzamiento  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "scripts" / "feeds.json"
STATE_FILE = ROOT / "scripts" / "state" / "seen.json"
POSTS_DIR = ROOT / "src" / "content" / "posts"

MAX_AGE_HOURS = 48  # no se escriben noticias de fuentes con más de 2 días
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "2"))
MODEL = os.environ.get("MODEL", "claude-sonnet-5-5")
MIN_SOURCE_CHARS = 600          # si no hay texto suficiente, no se escribe (evita inventar)
SIMILARITY_SKIP = 0.62          # títulos muy parecidos = misma noticia ya cubierta
UA = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"
CATEGORIES = ["noticias", "guias", "trucos", "descubrimientos"]
IMG_DIR = ROOT / "public" / "img" / "radar"
BANCO_FILE = ROOT / "scripts" / "banco.json"
BANCO = json.loads(BANCO_FILE.read_text(encoding="utf-8"))["temas"] if BANCO_FILE.exists() else {}
BANCO_CREDIT = "ilustración de Zona Leonida"
GALERIA_FILE = ROOT / "scripts" / "galeria.json"
GALERIA = json.loads(GALERIA_FILE.read_text(encoding="utf-8"))["imagenes"] if GALERIA_FILE.exists() else []
GALERIA_DIR = ROOT / "public" / "img" / "oficial"
# Qué significa cada etiqueta de la galería oficial (para la IA y para detectar nombres en el titular)
GALERIA_REFS = {
    "jason": ("Jason Duval, protagonista", ["jason"]),
    "lucia": ("Lucía Caminos, protagonista", ["lucia", "lucía"]),
    "cal-hampton": ("Cal Hampton", ["cal hampton"]),
    "boobie-ike": ("Boobie Ike", ["boobie"]),
    "dre-quan-priest": ("Dre'Quan Priest", ["dre'quan", "drequan", "dre quan"]),
    "real-dimez": ("Real Dimez, dúo musical", ["real dimez"]),
    "raul-bautista": ("Raúl Bautista", ["raul bautista", "raúl bautista"]),
    "brian-heder": ("Brian Heder", ["brian heder"]),
    "vice-city": ("la ciudad de Vice City", ["vice city"]),
    "cayos-de-leonida": ("los Cayos de Leonida", ["cayos", "leonida keys"]),
    "port-gellhorn": ("Port Gellhorn", ["port gellhorn"]),
    "grassrivers": ("Grassrivers, los pantanos", ["grassrivers"]),
    "ambrosia": ("Ambrosía", ["ambrosia", "ambrosía"]),
    "monte-kalaga": ("el parque nacional del monte Kalaga", ["kalaga"]),
    "ultimate": ("la edición Ultimate", ["ultimate"]),
    "vintage": ("el pack Vintage Vice City (bonus de reserva)", ["vintage"]),
}

# Solo se reutilizan imágenes y vídeos OFICIALES (material promocional de Rockstar).
# Nunca se copian fotos de otros medios ni material filtrado.
OFFICIAL_IMAGE_DOMAINS = ("rockstargames.com",)
OFFICIAL_X_ACCOUNTS = {"rockstargames"}          # tuits que se pueden incrustar
OFFICIAL_YT_AUTHORS = {"rockstar games"}         # canales de YouTube que se pueden incrustar


# ---------- utilidades ----------
def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if len(text) > max_len:
        corte = text[:max_len + 1]
        # Cortar siempre en un guion para no dejar palabras a medias
        text = corte[:corte.rfind("-")] if "-" in corte else text[:max_len]
        # Y no terminar en palabras vacías ("...para-reclamar-el")
        vacias = {"a", "al", "con", "de", "del", "el", "en", "la", "las", "lo", "los",
                  "o", "para", "por", "que", "se", "su", "un", "una", "y"}
        partes = text.split("-")
        while len(partes) > 1 and partes[-1] in vacias:
            partes.pop()
        text = "-".join(partes)
    return text.rstrip("-") or "articulo"


def norm_title(t: str) -> str:
    return re.sub(r"\W+", " ", unicodedata.normalize("NFKD", t.lower())).strip()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"urls": [], "titles": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["urls"] = state["urls"][-3000:]
    state["titles"] = state["titles"][-1500:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def existing_posts() -> list[dict]:
    """Títulos y URLs de lo ya publicado, para evitar duplicados y sugerir enlaces internos."""
    out = []
    for f in POSTS_DIR.glob("*.md"):
        txt = f.read_text(encoding="utf-8")
        if re.search(r"^draft:\s*true", txt, re.M):
            continue  # las plantillas en borrador no existen aún en la web
        t = re.search(r'^title:\s*"?(.*?)"?\s*$', txt, re.M)
        c = re.search(r"^category:\s*(\w+)", txt, re.M)
        d = re.search(r"^date:\s*(\S+)", txt, re.M)
        if t and c:
            out.append({"title": t.group(1), "url": f"/{c.group(1)}/{f.stem}/", "_fecha": d.group(1) if d else ""})
    out.sort(key=lambda x: x["_fecha"], reverse=True)  # lo más reciente primero: es lo que más se puede repetir
    return [{"title": x["title"], "url": x["url"]} for x in out]


def is_similar(title: str, known: list[str]) -> bool:
    n = norm_title(title)
    return any(difflib.SequenceMatcher(None, n, k).ratio() >= SIMILARITY_SKIP for k in known)


# ---------- Newswire de Rockstar (su web ya no tiene RSS: se lee la misma API que usa la página) ----------
RS_GRAPH = "https://graph.rockstargames.com/"
RS_LIST_HASH = "7ec00215aecc70de257b0719a1dfcfa84fe57fdc7bf5c10ec2e8f377defede58"
RS_POST_HASH = "555658813abe5acc8010de1a1feddd6fd8fddffbdc35d3723d4dc0fe4ded6810"
RS_GTA6_TAG = 666


def _rs_query(operation: str, variables: dict, sha: str) -> dict:
    import requests

    r = requests.get(RS_GRAPH, timeout=20, headers={"User-Agent": UA}, params={
        "origin": "https://www.rockstargames.com",
        "operationName": operation,
        "variables": json.dumps(variables, separators=(",", ":")),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": sha}}, separators=(",", ":")),
    })
    r.raise_for_status()
    return r.json().get("data") or {}


def rockstar_entries() -> list[dict]:
    """Últimas noticias de GTA VI del Newswire, en español, con su imagen oficial."""
    data = _rs_query("NewswireList", {"tagIdHash": None, "page": 1, "metaUrl": "/newswire",
                                      "limit": 20, "locale": "es_es"}, RS_LIST_HASH)
    out = []
    for p in (data.get("posts") or {}).get("results") or []:
        if not any(t.get("id") == RS_GTA6_TAG for t in p.get("primary_tags") or []):
            continue
        try:  # "8/10/26 14:00" (día/mes/año con locale es_es): solo noticias de la última semana
            created = datetime.strptime(p.get("created", ""), "%d/%m/%y %H:%M").replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created).total_seconds() > MAX_AGE_HOURS * 3600:
                continue
        except ValueError:
            pass
        img = ((p.get("preview_images_parsed") or {}).get("newswire_block") or {}).get("d16x9")
        out.append({"title": p.get("title", ""), "link": "https://www.rockstargames.com/es" + p["url"],
                    "rockstar_id": p["id"], "official_img": img})
    return out


def rockstar_text(post_id: str) -> tuple[str, str]:
    """(json bruto, texto en español) de una noticia del Newswire."""
    data = _rs_query("NewswirePost", {"locale": "es_es", "id_hash": post_id}, RS_POST_HASH)
    tina = (data.get("post") or {}).get("tina") or {}
    parts: list[str] = []

    def walk(o):
        if isinstance(o, str):
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", o).replace("&nbsp;", " ")).strip()
            if len(t) >= 40 and " " in t and not re.match(r"^(https?:|/|var\()", t) and t not in parts:
                parts.append(t)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("alt", "style", "sources"):
                    walk(v)

    walk(tina.get("variables") or {})          # traducción al español
    if sum(map(len, parts)) < MIN_SOURCE_CHARS:  # si no está traducida, el original en inglés
        walk((tina.get("payload") or {}).get("content") or [])
    return json.dumps(tina, ensure_ascii=False), "\n\n".join(parts)


# ---------- 1-2. recoger candidatos ----------
def collect_candidates(cfg: dict, state: dict, posts: list[dict]) -> list[dict]:
    import feedparser

    kws = [k.lower() for k in cfg["keywords"]]
    known_titles = state["titles"] + [norm_title(p["title"]) for p in posts]
    found = []
    for feed in cfg["feeds"]:
        is_rs = feed.get("type") == "rockstar"
        try:
            entries = rockstar_entries() if is_rs else feedparser.parse(feed["url"], agent=UA).entries
        except Exception as e:  # noqa: BLE001
            print(f"  ! {feed['name']}: {e}")
            continue
        print(f"  · {feed['name']}: {len(entries)} entradas")
        # Fuente recién añadida ("arranque": true): la primera vez solo se apunta lo que ya tenía publicado,
        # para no escribir sobre noticias antiguas (algunas fuentes, como el INE, no ponen fecha a sus entradas)
        if feed.get("arranque") and feed["url"] not in state.setdefault("feeds_iniciados", []):
            state["urls"].extend(x.get("link", "") for x in entries if x.get("link"))
            state["feeds_iniciados"].append(feed["url"])
            print("    (fuente nueva: se apuntan sus entradas actuales y se empieza a vigilar desde ahora)")
            continue
        for e in entries[:40]:
            link, title = e.get("link", ""), e.get("title", "")
            # solo noticias recientes: lo antiguo ya no es noticia
            pub = e.get("published_parsed") or e.get("updated_parsed")
            if pub and (time.time() - calendar.timegm(pub)) > MAX_AGE_HOURS * 3600:
                continue
            blob = f"{title} {e.get('summary', '')}".lower()
            # las noticias de Rockstar ya vienen filtradas por la etiqueta de GTA VI
            if not link or link in state["urls"] or not (is_rs or any(k in blob for k in kws)):
                continue
            if is_similar(title, known_titles):
                state["urls"].append(link)
                continue
            item = {"source": feed["name"], "title": title, "url": link}
            if is_rs:
                item.update(rockstar_id=e["rockstar_id"], official_img=e.get("official_img"))
            found.append(item)
            known_titles.append(norm_title(title))
    return found


# ---------- 3. leer el artículo original ----------
def fetch_page(url: str) -> tuple[str, str]:
    """Devuelve (html, texto limpio) del artículo."""
    import requests
    import trafilatura

    try:
        html = requests.get(url, headers={"User-Agent": UA}, timeout=20).text
    except Exception:  # noqa: BLE001
        return "", ""
    return html, trafilatura.extract(html, include_comments=False, include_tables=True) or ""


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower().removeprefix("www.")


def official_image(html: str, page_url: str) -> str | None:
    """og:image solo si la propia página es de un dominio oficial."""
    if not any(_domain(page_url).endswith(d) for d in OFFICIAL_IMAGE_DOMAINS):
        return None
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html, re.I)
    return m.group(1) if m else None


def official_embeds(html: str) -> list[dict]:
    """Vídeos de YouTube y tuits que aparecen en la fuente y son de cuentas oficiales."""
    import requests

    out, seen = [], set()
    for vid in re.findall(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})", html):
        if vid in seen:
            continue
        seen.add(vid)
        try:
            meta = requests.get("https://www.youtube.com/oembed",
                                params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                                timeout=10).json()
        except Exception:  # noqa: BLE001
            continue
        if meta.get("author_name", "").lower() in OFFICIAL_YT_AUTHORS:
            out.append({"type": "youtube", "id": vid, "title": meta.get("title", "Vídeo")})
    for user, sid in re.findall(r"(?:twitter|x)\.com/(\w+)/status/(\d+)", html):
        if user.lower() in OFFICIAL_X_ACCOUNTS and sid not in seen:
            seen.add(sid)
            out.append({"type": "x", "user": user, "id": sid})
    return out[:2]


def download_image(url: str, slug: str) -> str | None:
    """Descarga, redimensiona a 1600 px y guarda en WebP. Devuelve la ruta pública."""
    import io
    import requests
    from PIL import Image

    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    img.thumbnail((1600, 1600))
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(IMG_DIR / f"{slug}.webp", "WEBP", quality=82)
    try:  # versiones pequeñas para móvil y tarjetas
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from miniaturas import make_variants
        make_variants(IMG_DIR / f"{slug}.webp")
    except Exception as e:  # noqa: BLE001
        print(f"  ! no se pudieron crear miniaturas: {e}")
    return f"/img/radar/{slug}.webp"


def embed_html(e: dict) -> str:
    if e["type"] == "youtube":
        return (f'<figure class="embed"><iframe src="https://www.youtube-nocookie.com/embed/{e["id"]}" '
                f'title="{e["title"].replace(chr(34), "")}" loading="lazy" allowfullscreen></iframe>'
                f'<figcaption>Vídeo: Rockstar Games</figcaption></figure>')
    return (f'<blockquote class="twitter-tweet" data-dnt="true" data-theme="dark">'
            f'<a href="https://twitter.com/{e["user"]}/status/{e["id"]}">Ver publicación de @{e["user"]}</a></blockquote>'
            '<script async src="https://platform.twitter.com/widgets.js"></script>')


# ---------- 3. redactar con IA ----------
_TEMAS_TXT = "; ".join(f"{k} ({v['desc']})" for k, v in BANCO.items()) or "ciudad"
SYSTEM_TEMPLATE = """Eres redactor de una web de fans de GTA VI en español para España y toda Latinoamérica. \
Escribes en español neutro, sin regionalismos ("videojuego", "computadora o PC", "celular o móvil" solo si es \
necesario), con tono cercano pero riguroso, como un buen medio de videojuegos. \
TRATO AL LECTOR: siempre de TÚ, en singular ("podrás", "te contamos", "tu consola"). Nunca "ustedes" ni "vosotros" \
para dirigirte al lector, y no lo trates de usted. Cuando hables del jugador dentro del juego, usa también tú \
("si la policía te identifica…"). \
Escribe siempre "Lucía" con tilde (también "Jason y Lucía"). \
Frases cortas y directas; evita muletillas como "cabe destacar", "en este sentido", "sin lugar a dudas" o "no cabe duda". \
Cuando des horarios o precios, si la fuente los da, indica la referencia (por ejemplo, hora de España o de México).

NORMAS OBLIGATORIAS:
- Usa SOLO los hechos que aparecen en el texto fuente. Si algo no está, no lo afirmes. Nada de inventar cifras, fechas ni citas.
- Redacción 100 % propia: no copies frases ni la estructura del original. Reformula y aporta contexto útil para el lector.
- Atribuye la información ("según informa {fuente}", "Rockstar ha confirmado...").
- Distingue claramente rumores/filtraciones de información oficial. Si es un rumor, dilo en el título y en la entradilla.
- FILTRACIONES Y RUMORES:
  · Puedes informar de que existen y de lo que dicen, describiéndolo SOLO con tus palabras y atribuyéndolo al medio que lo publica.
  · Pon "rumor": true, deja claro en el título que es un rumor o filtración y recuerda en el texto que Rockstar no lo ha confirmado.
  · No enlaces NUNCA a archivos, imágenes o vídeos filtrados, ni a quien los difunde, ni expliques cómo conseguirlos.
  · No describas el material filtrado como si lo hubieras visto ni lo compares con imágenes oficiales ("en esta imagen se ve…").
  · No presentes ningún material oficial de Rockstar como prueba o confirmación de una filtración.
  · Si la filtración procede de un hackeo o robo de datos (por ejemplo, el de septiembre de 2022), limítate a informar de que \
existe y de lo más general; no detalles su contenido.
  · Ten en cuenta si la fuente que la recoge es fiable y menciónalo si no lo es.
  · VÍDEOS O VERSIONES FILTRADAS DEL JUEGO (Cyberleek o cualquier otro filtrador): es nuestra línea editorial no \
difundirlas. Informa del hecho (que se ha publicado material, cuándo, quién, cuánto dura) y del contexto (respuesta de \
Rockstar/Take-Two, acciones legales, polémica). Puedes añadir UNA descripción breve y general de lo que muestra, siempre \
atribuida al medio que lo ha visto ("según Dexerto, muestra a Lucía conduciendo y en combate por Vice City"). NUNCA cuentes \
nada de la historia ni de las misiones (ni giros, ni personajes nuevos, ni escenas concretas, ni el final), ni detalles \
escabrosos o sexuales. Avisa de que no lo enlazamos para no hacer spoilers y enlaza nuestra postura: \
/guias/gta-6-filtraciones-cyberleek-que-ha-pasado/
- No menciones imágenes ni vídeos en el texto: si hay material oficial se añade automáticamente.
- ENLAZA LAS GUÍAS DE REFERENCIA cuando la noticia toque su tema: precio/ediciones → /guias/gta-6-precio-ediciones-reservas/, \
PC → /guias/gta-6-pc/, tamaño/precarga → /guias/gta-6-cuanto-ocupa/, mapa/zonas → /guias/gta-6-mapa-leonida/, \
personajes → /guias/gta-6-personajes/, hora de salida por país → /guias/gta-6-a-que-hora-sale/, tráilers → /trailers/, online/multijugador → /guias/gta-6-modo-online/, edición Ultimate → /guias/gta-6-merece-la-pena-edicion-ultimate/, precios en Latinoamérica → /guias/gta-6-precio-latinoamerica/, FPS/PS5 Pro/rendimiento → /guias/gta-6-ps5-pro-fps-resolucion/, coches → /guias/gta-6-coches-vehiculos-confirmados/, idiomas/doblaje/subtítulos → /guias/gta-6-idiomas-espanol-doblaje/, PEGI/ESRB/edad → /guias/gta-6-pegi-edad-recomendada/, edición física/disco/código → /guias/gta-6-trae-disco-edicion-fisica/, preparativos del lanzamiento → /guias/gta-6-checklist-lanzamiento/, retrasos/historia del desarrollo → /guias/gta-6-como-se-hizo-desarrollo-retrasos/ y /guias/gta-6-cronologia/, mecánicas de juego (policía, dinero, robos, Jason y Lucía) → /guias/gta-6-jugabilidad-todo-lo-confirmado/, filtraciones → /guias/gta-6-filtraciones-cyberleek-que-ha-pasado/, campaña de promoción y merchandising → /guias/gta-6-campana-marketing-miami-y-fiebre-del-lanzamiento/, comparativas con GTA Vice City de 2002 → /guias/gta-6-vice-city-2002-vs-gta-6/, duración/horas de juego → /guias/gta-6-cuanto-dura/, trucos/claves → /trucos/gta-6-trucos-claves-ps5-xbox/. Para un resumen general, enlaza /guias/gta-6-todo-lo-que-sabemos/. Si la noticia habla de un personaje, enlaza su ficha: /personajes/jason-duval/, /personajes/lucia-caminos/, /personajes/cal-hampton/, /personajes/boobie-ike/, /personajes/dre-quan-priest/, /personajes/real-dimez/, /personajes/raul-bautista/, /personajes/brian-heder/.
- NO REPITAS TEMAS: si la noticia trata básicamente de lo mismo que alguno de los "artículos ya publicados" \
(aunque la cuente otro medio o con otro enfoque), responde {"skip": true, "reason": "tema ya cubierto: <artículo>"}. \
Solo escribe si aporta un dato nuevo relevante, y en ese caso céntrate en lo nuevo. \
Cuenta como repetición aunque el título sea distinto: el mismo informe, entrevista o reportaje contado por \
otro medio (por ejemplo, el mismo reportaje de Bloomberg o las mismas declaraciones de un directivo), o un \
detalle secundario de una noticia ya publicada. Revisa sobre todo los primeros de la lista, que son los más recientes.
- APORTA ALGO PROPIO (obligatorio): no te limites a resumir la fuente. El artículo debe responder también a "¿y esto qué significa para mí como jugador?" con al menos una de estas aportaciones, siempre sin inventar: (a) relacionarlo con lo que ya está confirmado y enlazar la guía o el artículo nuestro que lo amplía; (b) explicar qué cambia respecto a GTA 5, RDR 2 u otra entrega, solo si la fuente o nuestros artículos lo permiten; (c) dejar claro qué ha confirmado Rockstar y qué no; (d) una tabla o lista que ordene la información mejor que el original. Si la noticia es tan menor que solo podrías resumirla (una opinión, una anécdota, otro medio que comenta o analiza algo que ya hemos publicado), descártala con {"skip": true, "reason": "sin valor propio: ..."}.
- MENOS NOTICIAS, MÁS COMPLETAS: la web se valora por su contenido propio, no por el número de noticias. Descarta con {"skip": true, "reason": "menor: ..."} las acciones de marketing sueltas (un cartel, un coche, un anuncio), las anécdotas de famosos o fans, los comentarios de otros medios y los detalles menores de jugabilidad que ya cubre una de nuestras guías (jugabilidad, cómo se hizo, filtraciones, campaña de promoción): esos datos se añaden a la guía, no se publican como noticia. Publica solo novedades oficiales de Rockstar o Take-Two, datos nuevos importantes o temas que den para un artículo completo.
- Si la fuente NO trata realmente de GTA VI, o es un refrito sin novedad, o es solo una opinión, responde {"skip": true, "reason": "..."}.

LONGITUD Y ESTRUCTURA: la longitud la marca lo que hay que contar, no una cifra fija. Nunca rellenes ni repitas \
ideas para alargar, y nunca recortes algo importante para acortar.
- Noticia de un solo dato (una fecha, un precio, una declaración breve): solo si es una novedad oficial importante, y con el contexto que necesita el lector: 400-500 palabras como mínimo.
- Noticia normal con varios detalles y contexto: 400-700 palabras.
- Tema con mucha información (entrevista larga, avance con muchos detalles de jugabilidad, ficha técnica, \
explicación de un sistema del juego): 800 palabras o más, SIN LÍMITE: si la fuente da para 2000, escribe 2000. \
Cúbrelo todo, bien explicado y ordenado.
- Ante la duda, quédate largo antes que corto: es preferible explicar un detalle de más que dejar al lector con \
una duda que la fuente sí resolvía.
- REVISIÓN FINAL OBLIGATORIA antes de responder: repasa el texto fuente de principio a fin y comprueba que has \
incluido TODOS los datos relevantes para el lector (cifras, fechas, nombres, mecánicas, declaraciones, matices y \
lo que se confirma o se descarta). Si falta algo, añádelo.
- Usa los subtítulos ## que el tema pida (de 0 a 6): preguntas que la gente buscaría en Google, no secciones de relleno.
- Elige el formato según el contenido: listas para enumerar novedades, una tabla si comparas datos (precios, \
fechas, plataformas), una sección "Preguntas frecuentes" solo si responde dudas reales. No uses siempre el mismo esquema.
- Primer párrafo: lo esencial de la noticia (qué, quién, cuándo) en 2-3 frases. Último párrafo: contexto útil o \
qué falta por saber, sin frases hechas de cierre.

FORMATO DE RESPUESTA: solo un objeto JSON válido, sin texto alrededor:
{
  "skip": false,
  "category": "noticias" | "guias" | "trucos" | "descubrimientos",
  "rumor": true | false,
  "image_theme": "uno de estos temas de ilustración: {temas}",
  "official_refs": ["0-2 etiquetas de esta lista SOLO si son el tema central de la noticia (si no, lista vacía): {refs}"],
  "image_alt": "descripción genérica de una imagen promocional oficial de GTA VI (por si hay imagen oficial); nunca la relaciones con la filtración",
  "title": "titular SEO de 50-70 caracteres que empiece por 'GTA 6' o 'GTA VI' cuando suene natural. Concreto y con el dato clave (una cifra, una fecha, la plataforma o la pregunta que se hace la gente, con sus signos ¿?). Mayúscula solo al principio y en nombres propios. Nunca exagerado ni engañoso: debe cumplir exactamente lo que promete. NUNCA pongas en el título el medio de origen ni «según X»: la atribución va en el texto",
  "description": "entradilla/meta description de 130-160 caracteres que dé la respuesta o el dato principal y empiece con un verbo o con el hecho, no con 'En este artículo'",
  "tags": ["3-5 etiquetas en minúsculas"],
  "body": "artículo en Markdown (ver LONGITUD Y ESTRUCTURA). Incluye 1-3 enlaces internos a artículos relacionados de la lista si encajan de forma natural. No pongas el título como # al principio."
}"""
_REFS_TXT = "; ".join(f"{k} = {v[0]}" for k, v in GALERIA_REFS.items())
SYSTEM = SYSTEM_TEMPLATE.replace("{temas}", _TEMAS_TXT).replace("{refs}", _REFS_TXT)



_CLIENT = None


def refresh_github_identity() -> None:
    """En GitHub Actions, pide a GitHub un "pase" de identidad nuevo y lo guarda en el archivo
    que lee el SDK. Cada pase solo se puede canjear una vez (y caduca en ~5 min), así que se
    renueva antes de cada artículo; el SDK lo vuelve a leer cuando necesita renovar su acceso."""
    import requests

    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    req_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    path = os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
    if not (url and req_token and path):
        return
    r = requests.get(url, params={"audience": "https://api.anthropic.com"},
                     headers={"Authorization": f"Bearer {req_token}"}, timeout=15)
    r.raise_for_status()
    Path(path).write_text(r.json()["value"], encoding="utf-8")


def get_client():
    """Una única conexión con Claude para toda la ejecución (reutiliza el acceso ya concedido)."""
    global _CLIENT
    if _CLIENT is None:
        import anthropic
        refresh_github_identity()
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def write_article(item: dict, source_text: str, posts: list[dict]) -> dict | None:
    client = get_client()
    refresh_github_identity()  # deja preparado un pase nuevo por si el SDK necesita renovar
    related = "\n".join(f"- {p['title']} → {p['url']}" for p in posts[:200]) or "(ninguno aún)"
    user = (
        f"FUENTE: {item['source']}\nTÍTULO ORIGINAL: {item['title']}\nURL: {item['url']}\n\n"
        f"TEXTO FUENTE:\n\"\"\"\n{source_text[:25000]}\n\"\"\"\n\n"
        f"ARTÍCULOS YA PUBLICADOS EN NUESTRA WEB (para enlaces internos):\n{related}"
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=20000, system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("  ! respuesta no válida de la IA, se omite")
        return None
    if data.get("skip"):
        print(f"  – descartada: {data.get('reason', '')}")
        return None
    if data.get("category") not in CATEGORIES or not data.get("title") or not data.get("body"):
        print("  ! faltan campos, se omite")
        return None
    return data


def yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').strip() + '"'


_BANCO_STATE = ROOT / "scripts" / "state" / "banco-uso.json"


def pick_banco_image(theme: str, rumor: bool) -> tuple[str, str] | None:
    """Elige una ilustración del banco para el tema, rotando para no repetir la última usada."""
    theme = (theme or "").strip().lower()
    if rumor:
        theme = "misterio"
    if theme not in BANCO:
        theme = "ciudad" if "ciudad" in BANCO else next(iter(BANCO))
    t = BANCO[theme]
    try:
        uso = json.loads(_BANCO_STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        uso = {}
    i = (uso.get(theme, -1) + 1) % len(t["imagenes"])
    uso[theme] = i
    _BANCO_STATE.parent.mkdir(parents=True, exist_ok=True)
    _BANCO_STATE.write_text(json.dumps(uso, indent=1), encoding="utf-8")
    return f"/img/banco/{t['imagenes'][i]}.webp", t["alt"]


NO_PORTADA = {"vice-city-6", "vice-city-7", "vice-city-8"}


def _portada_usada(img: str) -> bool:
    """True si algún artículo ya usa esa imagen como portada."""
    for f in (ROOT / "src" / "content" / "posts").glob("*.md"):
        if re.search(rf"^image:\s*{re.escape(img)}\s*$", f.read_text(encoding="utf-8"), re.M):
            return True
    return False


def pick_galeria_image(refs: list, title: str) -> tuple[str, str] | None:
    """Elige una imagen oficial de Rockstar de la galería según los personajes o lugares
    de la noticia. Primero las etiquetas que da la IA y, si no hay, nombres en el titular."""
    if not GALERIA:
        return None
    wanted = [r for r in (refs or []) if r in GALERIA_REFS]
    if not wanted:
        t = title.lower()
        wanted = [k for k, (_, words) in GALERIA_REFS.items() if any(w in t for w in words)]
    try:
        uso = json.loads(_BANCO_STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        uso = {}
    # portadas que ya usa algún artículo: Discover muestra menos las imágenes repetidas
    usadas = set()
    for f in (ROOT / "src" / "content" / "posts").glob("*.md"):
        m = re.search(r"^image:\s*/img/oficial/([\w-]+)\.webp", f.read_text(encoding="utf-8"), re.M)
        if m:
            usadas.add(m.group(1))
    for ref in wanted:
        # imágenes de esa etiqueta ya descargadas; primero las que tratan solo de ella
        opts = [g for g in GALERIA if ref in g["refs"] and (GALERIA_DIR / f"{g['slug']}.webp").exists()]
        opts.sort(key=lambda g: len(g["refs"]))
        # nunca de portada: imágenes con tono sugerente (Discover las muestra menos)
        opts = [g for g in opts if g["slug"] not in NO_PORTADA]
        libres = [g for g in opts if g["slug"] not in usadas]
        if libres:
            opts = libres
        if not opts:
            continue
        key = f"oficial:{ref}"
        i = (uso.get(key, -1) + 1) % len(opts)
        uso[key] = i
        _BANCO_STATE.parent.mkdir(parents=True, exist_ok=True)
        _BANCO_STATE.write_text(json.dumps(uso, indent=1), encoding="utf-8")
        g = opts[i]
        return f"/img/oficial/{g['slug']}.webp", g["alt"]
    return None


def save_post(data: dict, item: dict, html: str = "") -> Path:
    slug = slugify(data["title"])
    path = POSTS_DIR / f"{slug}.md"
    i = 2
    while path.exists():
        path = POSTS_DIR / f"{slug}-{i}.md"
        i += 1
    slug = path.stem

    # Imagen oficial (solo si la fuente es Rockstar) y vídeos/tuits oficiales
    image_lines = ""
    img_url = item.get("official_img") or (official_image(html, item["url"]) if html else None)
    local = download_image(img_url, slug) if img_url else None
    if local:
        alt = data.get("image_alt") or data["title"]
        credit = ("Rockstar Games (imagen promocional oficial, no forma parte de la filtración)"
                  if data.get("rumor") else "Rockstar Games")
        image_lines = f"image: {local}\nimageAlt: {yaml_str(alt[:150])}\nimageCredit: {yaml_str(credit)}\n"
    # Sin imagen en la fuente: imagen oficial de la galería si la noticia habla de un
    # personaje o lugar concreto (nunca en rumores, para no parecer una confirmación)
    if not image_lines and not data.get("rumor"):
        pick = pick_galeria_image(data.get("official_refs", []), data["title"])
        if pick:
            img, alt = pick
            image_lines = f"image: {img}\nimageAlt: {yaml_str(alt)}\nimageCredit: {yaml_str('Rockstar Games')}\n"
    # Si la noticia no es un rumor y no habla de nadie en concreto, una imagen oficial genérica
    # (Vice City, Leonida, Jason y Lucía…) que no use ya otro artículo: así las portadas no se repiten
    if not image_lines and not data.get("rumor"):
        for ref in ["vice-city", "jason", "lucia", "cayos-de-leonida", "grassrivers", "port-gellhorn", "ambrosia", "monte-kalaga"]:
            pick = pick_galeria_image([ref], "")
            if pick and not _portada_usada(pick[0]):
                img, alt = pick
                image_lines = f"image: {img}\nimageAlt: {yaml_str(alt)}\nimageCredit: {yaml_str('Rockstar Games')}\n"
                break
    if not image_lines and BANCO:
        pick = pick_banco_image(data.get("image_theme", ""), bool(data.get("rumor")))
        if pick:
            img, alt = pick
            image_lines = f"image: {img}\nimageAlt: {yaml_str(alt)}\nimageCredit: {yaml_str(BANCO_CREDIT)}\n"
    body = data["body"].strip()
    # En artículos de rumores no se incrustan vídeos ni tuits, para que no parezcan una confirmación
    embeds = official_embeds(html) if html and not data.get("rumor") else []
    if embeds:
        blocks = "\n\n".join(embed_html(e) for e in embeds)
        parts = body.split("\n\n", 1)          # tras el primer párrafo
        body = parts[0] + "\n\n" + blocks + ("\n\n" + parts[1] if len(parts) > 1 else "")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tags = ", ".join(slugify(t, 30) for t in data.get("tags", [])[:5])
    fm = (
        "---\n"
        f"title: {yaml_str(data['title'][:110])}\n"
        f"description: {yaml_str(data['description'][:170])}\n"
        f"date: {now}\n"
        f"category: {data['category']}\n"
        f"tags: [{tags}]\n"
        f"rumor: {'true' if data.get('rumor') else 'false'}\n"
        f"{image_lines}"
        "sources:\n"
        f"  - name: {yaml_str(item['source'] + ': ' + item['title'][:90])}\n"
        f"    url: {yaml_str(item['url'])}\n"
        "---\n\n"
    )
    path.write_text(fm + body + "\n", encoding="utf-8")
    return path


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="solo listar candidatos, sin IA ni escritura")
    ap.add_argument("--url", default="", help="redactar solo esta noticia (enlace), sin esperar a la revisión de fuentes")
    args = ap.parse_args()

    cfg = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    state = load_state()
    posts = existing_posts()
    # también los borradores de ejecuciones anteriores que aún esperan aprobación (no están publicados)
    vistos_urls = {x["url"] for x in posts}
    for e in reversed(state.get("escritos", [])):
        if e["url"] not in vistos_urls:
            posts.insert(0, e)

    print("Buscando novedades…")
    url_forzada = (args.url or os.environ.get("RADAR_URL", "")).strip()
    if url_forzada:
        # Noticia urgente: se redacta directamente desde el enlace indicado
        print(f"Noticia indicada a mano: {url_forzada}")
        item = {"source": _domain(url_forzada) or "fuente", "title": "", "url": url_forzada}
        m = re.search(r"rockstargames\.com/(?:[a-z]{2}/)?newswire/article/(\w+)", url_forzada)
        if m:
            item.update(source="Rockstar Games (Newswire)", rockstar_id=m.group(1))
        else:
            html_tmp, _ = fetch_page(url_forzada)
            t = re.search(r"<title[^>]*>(.*?)</title>", html_tmp or "", re.I | re.S)
            item["title"] = re.sub(r"\s+", " ", t.group(1)).strip() if t else url_forzada
        candidates = [item]
    else:
        candidates = collect_candidates(cfg, state, posts)
    print(f"{len(candidates)} candidatas nuevas")
    if args.dry_run:
        for c in candidates:
            print(f"  - [{c['source']}] {c['title']}\n    {c['url']}")
        if not url_forzada:
            comunidad.run(cfg, state, None, MODEL, dry_run=True)
            lanzamiento.run(cfg, state, None, MODEL, fetch_page, rockstar_entries, rockstar_text, dry_run=True)
        return 0
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE")):
        print("Faltan credenciales: ANTHROPIC_API_KEY o la federación de identidades (ANTHROPIC_IDENTITY_TOKEN_FILE)")
        return 1

    written = []
    errors = 0
    for item in candidates:
        if len(written) >= MAX_PER_RUN:
            break
        print(f"→ {item['title']}")
        state["urls"].append(item["url"])
        state["titles"].append(norm_title(item["title"]))
        if item.get("rockstar_id"):
            try:
                html, text = rockstar_text(item["rockstar_id"])
                if not item["title"] and text:
                    item["title"] = text.split("\n", 1)[0][:160]
            except Exception as e:  # noqa: BLE001
                print(f"  ! no se pudo leer la noticia de Rockstar: {e}")
                html, text = "", ""
        else:
            html, text = fetch_page(item["url"])
        if len(text) < MIN_SOURCE_CHARS:
            print("  – texto insuficiente, se omite")
            continue
        try:
            data = write_article(item, text, posts)
        except Exception as e:  # noqa: BLE001 — un fallo no debe tirar toda la ejecución
            print(f"  ! error al redactar: {type(e).__name__}: {str(e)[:200]}")
            # no se marca como vista, para reintentarla en la próxima ejecución
            state["urls"].remove(item["url"])
            state["titles"].pop()
            errors += 1
            if errors >= 2:
                print("  ! dos errores seguidos, se detiene esta ejecución")
                break
            continue
        if data:
            p = save_post(data, item, html)
            written.append(p)
            # al principio de la lista: el modelo solo ve los primeros, y así sabe lo que acaba de escribir
            nuevo = {"title": data["title"], "url": f"/{data['category']}/{p.stem}/"}
            posts.insert(0, nuevo)
            state.setdefault("escritos", []).append(nuevo)
            state["escritos"] = state["escritos"][-80:]
            print(f"  ✓ {p.relative_to(ROOT)}")

    # Modo lanzamiento: descubrimientos de la comunidad que amplían las guías (activo desde la fecha de feeds.json)
    guias = []
    if not url_forzada:
        def cliente():
            refresh_github_identity()
            return get_client()
        try:
            guias = comunidad.run(cfg, state, cliente, os.environ.get("MODELO_COMUNIDAD", "claude-haiku-5-5"), maximo=int(os.environ.get("MAX_COMUNIDAD", "5")))
        except Exception as e:  # noqa: BLE001
            print(f"  ! modo lanzamiento: {type(e).__name__}: {str(e)[:200]}")

    # Día del lanzamiento: rellena las guías preparadas en borrador y las propone para publicar
    preparadas = []
    if not url_forzada:
        try:
            preparadas = lanzamiento.run(cfg, state, cliente, MODEL, fetch_page, rockstar_entries, rockstar_text,
                                         maximo=int(os.environ.get("MAX_LANZAMIENTO", "2")))
        except Exception as e:  # noqa: BLE001
            print(f"  ! guías del lanzamiento: {type(e).__name__}: {str(e)[:200]}")

    save_state(state)
    summary = "\n".join(f"- {p.stem}" for p in written)
    print(f"\nArtículos nuevos: {len(written)}\n{summary}")
    if guias:
        print(f"Guías ampliadas con descubrimientos: {len(guias)}\n" + "\n".join(f"- {p.stem}" for p in guias))
    if preparadas:
        print(f"Guías del lanzamiento listas para publicar: {len(preparadas)}\n" + "\n".join(f"- {p.stem}" for p in preparadas))
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"count={len(written) + len(guias) + len(preparadas)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
