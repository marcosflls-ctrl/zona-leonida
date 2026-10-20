"""Día del lanzamiento: rellena las guías preparadas en borrador y las propone para publicar.

Las plantillas del 19 de noviembre (draft: true) tienen huecos <!-- RELLENAR -->. A partir de la
fecha de feeds.json → "lanzamiento", cada pasada del radar:

1. Busca en las fuentes del radar (y en el Newswire de Rockstar) noticias de GTA VI que encajen con
   cada guía (controles, misiones, trofeos, notas...).
2. Cuando una guía tiene fuentes nuevas, la IA rellena la plantilla SOLO con lo que dicen esas fuentes.
3. Si la guía ya cumple lo que promete su título, pasa a draft: false con la fecha real y llega en la
   propuesta de borradores para que la revises. Si aún faltan datos, no se toca y se reintenta más tarde
   con más fuentes.

Para probar antes sin escribir nada: FORZAR_LANZAMIENTO=1 con --dry-run (lista qué fuentes encontraría).
"""
from __future__ import annotations

import calendar
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "src" / "content" / "posts"
MADRID = ZoneInfo("Europe/Madrid")
MAX_FUENTES = 5          # textos de fuente que se pasan a la IA en cada intento
REINTENTO_HORAS = 6      # sin fuentes nuevas, no se vuelve a intentar una guía hasta pasadas estas horas

# guía → (palabras que la identifican en titulares y entradillas, en español e inglés; qué debe tener para publicarse)
PLANTILLAS: dict[str, tuple[list[str], str]] = {
    "gta-6-ya-disponible": (
        ["ya disponible", "ya está disponible", "ya a la venta", "ya se puede jugar", "ya puedes jugar",
         "available now", "out now", "launch day", "día de lanzamiento", "is now available", "has launched",
         "lanzamiento de gta", "precarga", "preload", "parche del primer día", "day one patch"],
        "que el juego ya está disponible, en qué plataformas y desde qué hora, con datos de Rockstar o de un medio fiable",
    ),
    "gta-6-notas-analisis": (
        ["análisis", "review", "reviews", "reseña", "metacritic", "opencritic", "puntuación", "puntuaciones",
         "la crítica", "critics", "score"],
        "la nota media de Metacritic u OpenCritic, o al menos cinco notas de medios con su cifra",
    ),
    "gta-6-controles-ps5-xbox": (
        ["controles", "controls", "botones", "button", "mando", "controller", "ajustes", "settings", "configuración"],
        "los controles básicos a pie y conduciendo en PS5 o Xbox, con los botones concretos",
    ),
    "gta-6-lista-de-misiones": (
        ["misiones", "missions", "mission list", "lista de misiones", "capítulos", "chapters", "walkthrough",
         "historia principal", "main story"],
        "cuántas misiones o capítulos tiene la historia y una lista útil, sin desvelar la trama",
    ),
    "gta-6-mejores-coches": (
        ["coches", "cars", "vehículos", "vehicles", "fastest", "más rápido", "más rápidos", "garaje", "garage",
         "supercoche", "supercar"],
        "varios coches concretos con nombre y por qué destacan (velocidad, dónde encontrarlos o precio)",
    ),
    "gta-6-como-ganar-dinero": (
        ["dinero", "money", "ganar dinero", "make money", "golpes", "heists", "negocios", "businesses", "dólares rápidos"],
        "al menos tres métodos concretos para ganar dinero, explicados",
    ),
    "gta-6-secretos-easter-eggs": (
        ["secretos", "secreto", "easter egg", "easter eggs", "secret", "secrets", "hidden", "oculto", "escondido",
         "referencia a", "guiño"],
        "al menos tres secretos o easter eggs concretos, con dónde están",
    ),
    "gta-6-problemas-errores": (
        ["error", "errores", "fallo", "fallos", "bug", "bugs", "crash", "se cierra", "no carga", "no descarga",
         "servidores", "servers", "caído", "down", "parche", "patch", "hotfix", "solución", "fix"],
        "al menos tres problemas concretos (descarga, cierres, código de error o servidores) con su solución o lo que ha dicho Rockstar",
    ),
    "gta-6-consejos-primeras-horas": (
        ["consejos", "tips", "beginner", "principiantes", "primeras horas", "first hours", "things to know",
         "lo que debes saber", "antes de empezar", "trucos para empezar"],
        "al menos cinco consejos concretos para empezar, sacados de fuentes que ya han jugado",
    ),
    "gta-6-ajustes-calidad-rendimiento": (
        ["modo calidad", "modo rendimiento", "quality mode", "performance mode", "digital foundry", "fps",
         "resolución", "resolution", "ajustes gráficos", "graphics settings", "ps5 pro"],
        "qué modos gráficos tiene en al menos dos consolas, con resolución y FPS medidos por un análisis técnico",
    ),
    "gta-6-trofeos-logros": (
        ["trofeos", "trofeo", "trophies", "trophy", "logros", "achievements", "platino", "platinum"],
        "la lista de trofeos o logros (o al menos cuántos hay y los principales) con cómo conseguirlos",
    ),
}

PROMPT = """Eres editor de Zona Leonida, una web de guías de GTA VI en español neutro para España y Latinoamérica. \
Trata siempre de TÚ al lector. Escribe "Lucía" con tilde. Frases cortas y claras, sin muletillas.

Te paso la PLANTILLA de una guía que aún no está publicada y TEXTOS DE FUENTES publicados después del lanzamiento del \
juego. Tu trabajo es completar la guía SOLO con datos que aparecen en esas fuentes.

NORMAS OBLIGATORIAS:
- No inventes nada: ni botones, ni nombres de coches, ni trofeos, ni cifras, ni notas, ni fechas. Si un dato no está \
en las fuentes, no lo pongas.
- Atribuye lo que no sea evidente ("según IGN", "Rockstar ha confirmado").
- SIN SPOILERS de la historia: nunca cuentes giros, muertes, traiciones ni el final. En la lista de misiones, da solo \
nombres o capítulos que no desvelen nada, y avisa arriba de que la guía no tiene spoilers.
- Conserva el texto de la plantilla que siga siendo válido y sus enlaces internos. Si existe la sección \
"## Últimos descubrimientos", consérvala intacta y al final.
- Borra TODOS los comentarios HTML de la plantilla (<!-- ... -->), incluidos los de RELLENAR, IMÁGENES y GRÁFICO.
- Nunca dejes tablas vacías ni huecos. Si una sección no se puede completar con las fuentes, sustitúyela por una frase \
breve y honesta (por ejemplo: "Aún no hay datos comprobados; lo añadiremos en cuanto se confirmen") o elimínala.
- Organiza la información mejor que las fuentes: tablas para botones, trofeos o coches; listas para métodos y pasos.
- No menciones imágenes ni vídeos.

¿SE PUEDE PUBLICAR YA? "publicable": true solo si la guía cumple lo que promete su título con datos sólidos. \
Para esta guía, lo mínimo es: {minimo}. Si no llega, "publicable": false y explica qué falta en "motivo".

Responde SOLO con un objeto JSON válido, sin texto alrededor:
{{"publicable": true | false, "motivo": "qué falta o por qué ya está lista",
  "title": "titular de 50-90 caracteres (puedes dejar el de la plantilla)",
  "description": "entradilla de 130-160 caracteres que ya dé el dato principal",
  "body": "la guía completa en Markdown, sin el título como # al principio",
  "sources": [{{"name": "Medio: título de la noticia", "url": "enlace de una de las fuentes que hayas usado"}}]}}"""


def config(cfg: dict) -> dict:
    return cfg.get("lanzamiento") or {}


def _fecha(s: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def activa(cfg: dict, slug: str, ahora: datetime | None = None) -> bool:
    """¿Toca trabajar ya en esta guía? Cada guía puede tener su propia fecha (las notas salen antes)."""
    if os.environ.get("FORZAR_LANZAMIENTO") == "1":
        return True
    c = config(cfg)
    desde = _fecha((c.get("desde_por_guia") or {}).get(slug)) or _fecha(c.get("desde"))
    if not desde:
        return False
    ahora = ahora or datetime.now(timezone.utc)
    return desde <= ahora <= desde + timedelta(days=int(c.get("dias", 21)))


def es_borrador(path: Path) -> bool:
    return path.exists() and bool(re.search(r"^draft:\s*true", path.read_text(encoding="utf-8").split("\n---\n", 1)[0], re.M))


def pendientes(cfg: dict) -> list[str]:
    return [s for s in PLANTILLAS if es_borrador(POSTS / f"{s}.md") and activa(cfg, s)]


def buscar_fuentes(cfg: dict, slugs: list[str], rockstar_entries, max_horas: int = 72) -> dict[str, list[dict]]:
    """Noticias recientes de GTA VI que encajan con cada guía pendiente."""
    import feedparser

    kws_juego = [k.lower() for k in cfg.get("keywords", [])]
    ua = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"
    entradas: list[dict] = []
    for feed in cfg.get("feeds", []):
        try:
            if feed.get("type") == "rockstar":
                for e in rockstar_entries():
                    entradas.append({"fuente": "Rockstar Games (Newswire)", "title": e["title"], "url": e["link"],
                                     "texto": "", "rockstar_id": e["rockstar_id"], "oficial": True})
                continue
            if "reddit.com" in feed.get("url", ""):
                continue  # Reddit lo usa el modo comunidad; aquí solo medios y fuentes oficiales
            for e in feedparser.parse(feed["url"], agent=ua).entries[:60]:
                pub = e.get("published_parsed") or e.get("updated_parsed")
                if pub and time.time() - calendar.timegm(pub) > max_horas * 3600:
                    continue
                if e.get("link"):
                    entradas.append({"fuente": feed["name"], "title": e.get("title", ""), "url": e["link"],
                                     "texto": re.sub(r"<[^>]+>", " ", e.get("summary", "")), "oficial": bool(feed.get("oficial"))})
        except Exception as ex:  # noqa: BLE001
            print(f"  ! {feed.get('name')}: {type(ex).__name__}")
    out: dict[str, list[dict]] = {s: [] for s in slugs}
    for e in entradas:
        blob = f"{e['title']} {e['texto']}".lower()
        if e["fuente"] != "Rockstar Games (Newswire)" and not any(k in blob for k in kws_juego):
            continue
        for s in slugs:
            if any(k in blob for k in PLANTILLAS[s][0]):
                out[s].append(e)
    for s in out:  # lo oficial primero
        out[s].sort(key=lambda x: not x.get("oficial"))
    return out


def _yaml(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').strip() + '"'


def aplicar(path: Path, data: dict, urls_validas: set[str], ahora: datetime | None = None) -> bool:
    """Escribe la guía rellenada y la marca como publicable (draft: false). Devuelve False si algo no cuadra."""
    s = path.read_text(encoding="utf-8")
    head, _ = s.split("\n---\n", 1)
    body = re.sub(r"<!--.*?-->\s*", "", data.get("body", ""), flags=re.S).strip()
    if len(body) < 600 or "RELLENAR" in body:
        print("  ! la guía devuelta es demasiado corta o tiene huecos, no se publica")
        return False
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(MADRID).replace(microsecond=0)
    iso = ahora.isoformat()
    head = re.sub(r"^draft:\s*true\s*$", "draft: false", head, count=1, flags=re.M)
    head = re.sub(r"^date:.*$", f"date: {iso}", head, count=1, flags=re.M)
    head = re.sub(r"^updated:.*$", f"updated: {iso}", head, count=1, flags=re.M)
    t, d = (data.get("title") or "").strip(), (data.get("description") or "").strip()
    if 30 <= len(t) <= 110:
        head = re.sub(r"^title:.*$", f"title: {_yaml(t)}", head, count=1, flags=re.M)
    if 80 <= len(d) <= 170:
        head = re.sub(r"^description:.*$", f"description: {_yaml(d)}", head, count=1, flags=re.M)
    # fuentes: solo enlaces que de verdad se le pasaron a la IA
    nuevas = [x for x in data.get("sources") or [] if x.get("url") in urls_validas and x.get("name")]
    if nuevas:
        lineas = "".join(f"\n  - name: {_yaml(x['name'][:150])}\n    url: {_yaml(x['url'])}" for x in nuevas if x["url"] not in head)
        if re.search(r"^sources:\s*\[\]\s*$", head, re.M):
            head = re.sub(r"^sources:\s*\[\]\s*$", "sources:" + lineas, head, count=1, flags=re.M)
        elif re.search(r"^sources:\s*$", head, re.M):
            head = re.sub(r"^sources:\s*$", "sources:" + lineas, head, count=1, flags=re.M)
        else:
            head = head.rstrip() + "\nsources:" + lineas
    path.write_text(head + "\n---\n\n" + body + "\n", encoding="utf-8")
    return True


def run(cfg: dict, state: dict, get_client, model: str, fetch_page, rockstar_entries, rockstar_text,
        dry_run: bool = False, maximo: int = 2) -> list[Path]:
    slugs = pendientes(cfg)
    if not slugs:
        return []
    print(f"Lanzamiento: {len(slugs)} guías por rellenar")
    encontradas = buscar_fuentes(cfg, slugs, rockstar_entries)
    st = state.setdefault("lanzamiento", {})
    if dry_run:
        for s in slugs:
            print(f"  · {s}: {len(encontradas[s])} fuentes")
            for e in encontradas[s][:6]:
                print(f"      - [{e['fuente']}] {e['title'][:90]}")
        return []

    publicadas: list[Path] = []
    ahora = time.time()
    for s in slugs:
        if len(publicadas) >= maximo:
            break
        g = st.setdefault(s, {"fuentes": [], "ultimo": 0, "intentos": 0})
        nuevas = [e for e in encontradas[s] if e["url"] not in g["fuentes"]]
        g["fuentes"] = (g["fuentes"] + [e["url"] for e in nuevas])[-12:]
        if not g["fuentes"] or (not nuevas and ahora - g["ultimo"] < REINTENTO_HORAS * 3600):
            continue
        # textos: primero las nuevas (y lo oficial), luego las que ya se habían usado
        conocidas = {e["url"]: e for e in encontradas[s]}
        orden = [e["url"] for e in nuevas] + [u for u in reversed(g["fuentes"]) if u not in {e["url"] for e in nuevas}]
        textos, usadas = [], set()
        for u in orden:
            if len(textos) >= MAX_FUENTES:
                break
            e = conocidas.get(u, {"fuente": "", "title": "", "url": u})
            try:
                if e.get("rockstar_id"):
                    _, texto = rockstar_text(e["rockstar_id"])
                else:
                    _, texto = fetch_page(u)
            except Exception:  # noqa: BLE001
                texto = ""
            if len(texto) >= 400:
                textos.append(f"FUENTE: {e.get('fuente') or u}\nTÍTULO: {e.get('title', '')}\nURL: {u}\n\"\"\"\n{texto[:12000]}\n\"\"\"")
                usadas.add(u)
        g["ultimo"], g["intentos"] = ahora, g["intentos"] + 1
        if not textos:
            continue
        path = POSTS / f"{s}.md"
        print(f"→ Guía de lanzamiento: {s} ({len(textos)} fuentes)")
        try:
            msg = get_client().messages.create(
                model=model, max_tokens=16000, system=PROMPT.format(minimo=PLANTILLAS[s][1]),
                messages=[{"role": "user", "content": f"PLANTILLA:\n\"\"\"\n{path.read_text(encoding='utf-8')}\n\"\"\"\n\n" + "\n\n".join(textos)}],
            )
            raw = "".join(b.text for b in msg.content if b.type == "text").strip()
            data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip())
        except Exception as ex:  # noqa: BLE001
            print(f"  ! error: {type(ex).__name__}: {str(ex)[:200]}")
            continue
        if not data.get("publicable"):
            print(f"  – aún no: {data.get('motivo', '')[:200]}")
            continue
        if aplicar(path, data, usadas):
            publicadas.append(path)
            print(f"  ✓ lista para publicar: {path.name}")
    return publicadas
