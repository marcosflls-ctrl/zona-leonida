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
Variables opcionales: MAX_PER_RUN (3), MODEL (claude-sonnet-5-5)
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "scripts" / "feeds.json"
STATE_FILE = ROOT / "scripts" / "state" / "seen.json"
POSTS_DIR = ROOT / "src" / "content" / "posts"

MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "3"))
MODEL = os.environ.get("MODEL", "claude-sonnet-5-5")
MIN_SOURCE_CHARS = 600          # si no hay texto suficiente, no se escribe (evita inventar)
SIMILARITY_SKIP = 0.62          # títulos muy parecidos = misma noticia ya cubierta
UA = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"
CATEGORIES = ["noticias", "guias", "trucos", "descubrimientos"]
IMG_DIR = ROOT / "public" / "img" / "radar"

# Solo se reutilizan imágenes y vídeos OFICIALES (material promocional de Rockstar).
# Nunca se copian fotos de otros medios ni material filtrado.
OFFICIAL_IMAGE_DOMAINS = ("rockstargames.com",)
OFFICIAL_X_ACCOUNTS = {"rockstargames"}          # tuits que se pueden incrustar
OFFICIAL_YT_AUTHORS = {"rockstar games"}         # canales de YouTube que se pueden incrustar


# ---------- utilidades ----------
def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:max_len].rstrip("-") or "articulo"


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
        t = re.search(r'^title:\s*"?(.*?)"?\s*$', txt, re.M)
        c = re.search(r"^category:\s*(\w+)", txt, re.M)
        if t and c:
            out.append({"title": t.group(1), "url": f"/{c.group(1)}/{f.stem}/"})
    return out


def is_similar(title: str, known: list[str]) -> bool:
    n = norm_title(title)
    return any(difflib.SequenceMatcher(None, n, k).ratio() >= SIMILARITY_SKIP for k in known)


# ---------- 1-2. recoger candidatos ----------
def collect_candidates(cfg: dict, state: dict, posts: list[dict]) -> list[dict]:
    import feedparser

    kws = [k.lower() for k in cfg["keywords"]]
    known_titles = state["titles"] + [norm_title(p["title"]) for p in posts]
    found = []
    for feed in cfg["feeds"]:
        try:
            parsed = feedparser.parse(feed["url"], agent=UA)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {feed['name']}: {e}")
            continue
        print(f"  · {feed['name']}: {len(parsed.entries)} entradas")
        for e in parsed.entries[:40]:
            link, title = e.get("link", ""), e.get("title", "")
            blob = f"{title} {e.get('summary', '')}".lower()
            if not link or link in state["urls"] or not any(k in blob for k in kws):
                continue
            if is_similar(title, known_titles):
                state["urls"].append(link)
                continue
            found.append({"source": feed["name"], "title": title, "url": link})
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
SYSTEM = """Eres redactor de una web de fans de GTA VI en español para España y toda Latinoamérica. \
Escribes en español neutro: sin vosotros ni regionalismos (usa "ustedes", "videojuego", "computadora o PC", \
"celular o móvil" solo si es necesario), con tono cercano pero riguroso, como un buen medio de videojuegos. \
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
- No menciones imágenes ni vídeos en el texto: si hay material oficial se añade automáticamente.
- Si la fuente NO trata realmente de GTA VI, o es un refrito sin novedad, o es solo una opinión, responde {"skip": true, "reason": "..."}.

FORMATO DE RESPUESTA: solo un objeto JSON válido, sin texto alrededor:
{
  "skip": false,
  "category": "noticias" | "guias" | "trucos" | "descubrimientos",
  "rumor": true | false,
  "image_alt": "descripción genérica de una imagen promocional oficial de GTA VI (por si hay imagen oficial); nunca la relaciones con la filtración",
  "title": "titular SEO de 50-70 caracteres que empiece por 'GTA 6' o 'GTA VI' cuando suene natural",
  "description": "entradilla/meta description de 130-160 caracteres",
  "tags": ["3-5 etiquetas en minúsculas"],
  "body": "artículo en Markdown, 350-700 palabras, con 2-4 subtítulos ## que respondan dudas que la gente buscaría en Google. Incluye 1-2 enlaces internos a artículos relacionados de la lista si encajan de forma natural. No pongas el título como # al principio."
}"""


def write_article(item: dict, source_text: str, posts: list[dict]) -> dict | None:
    import anthropic

    client = anthropic.Anthropic()
    related = "\n".join(f"- {p['title']} → {p['url']}" for p in posts[:60]) or "(ninguno aún)"
    user = (
        f"FUENTE: {item['source']}\nTÍTULO ORIGINAL: {item['title']}\nURL: {item['url']}\n\n"
        f"TEXTO FUENTE:\n\"\"\"\n{source_text[:12000]}\n\"\"\"\n\n"
        f"ARTÍCULOS YA PUBLICADOS EN NUESTRA WEB (para enlaces internos):\n{related}"
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=3000, system=SYSTEM,
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
    img_url = official_image(html, item["url"]) if html else None
    local = download_image(img_url, slug) if img_url else None
    if local:
        alt = data.get("image_alt") or data["title"]
        credit = ("Rockstar Games (imagen promocional oficial, no forma parte de la filtración)"
                  if data.get("rumor") else "Rockstar Games")
        image_lines = f"image: {local}\nimageAlt: {yaml_str(alt[:150])}\nimageCredit: {yaml_str(credit)}\n"
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
    args = ap.parse_args()

    cfg = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    state = load_state()
    posts = existing_posts()

    print("Buscando novedades…")
    candidates = collect_candidates(cfg, state, posts)
    print(f"{len(candidates)} candidatas nuevas")
    if args.dry_run:
        for c in candidates:
            print(f"  - [{c['source']}] {c['title']}\n    {c['url']}")
        return 0
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE")):
        print("Faltan credenciales: ANTHROPIC_API_KEY o la federación de identidades (ANTHROPIC_IDENTITY_TOKEN_FILE)")
        return 1

    written = []
    for item in candidates:
        if len(written) >= MAX_PER_RUN:
            break
        print(f"→ {item['title']}")
        state["urls"].append(item["url"])
        state["titles"].append(norm_title(item["title"]))
        html, text = fetch_page(item["url"])
        if len(text) < MIN_SOURCE_CHARS:
            print("  – texto insuficiente, se omite")
            continue
        data = write_article(item, text, posts)
        if data:
            p = save_post(data, item, html)
            written.append(p)
            posts.append({"title": data["title"], "url": f"/{data['category']}/{p.stem}/"})
            print(f"  ✓ {p.relative_to(ROOT)}")

    save_state(state)
    summary = "\n".join(f"- {p.stem}" for p in written)
    print(f"\nArtículos nuevos: {len(written)}\n{summary}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"count={len(written)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
