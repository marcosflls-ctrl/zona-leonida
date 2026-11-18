"""Modo lanzamiento: descubrimientos de la comunidad (trucos, secretos, ubicaciones...).

En vez de escribir un artículo por cada descubrimiento, el robot amplía las guías que ya
existen (secretos, trucos, coches, dinero...) con una entrada nueva que cita a quien lo
encontró, inserta su vídeo si lo hay y marca "Sin comprobar" lo que aún no está confirmado.

Se activa solo a partir de la fecha "desde" de feeds.json → "comunidad" (o con la variable
de entorno FORZAR_COMUNIDAD=1 para pruebas).
"""
from __future__ import annotations

import calendar
import html as htmllib
import json
import os
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "src" / "content" / "posts"
UA = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"

# Guías que se pueden ampliar: archivo → de qué tratan (lo lee la IA para elegir dónde va cada cosa)
GUIAS = {
    "gta-6-secretos-easter-eggs": "secretos, easter eggs, guiños a otros juegos, referencias, curiosidades escondidas",
    "gta-6-trucos-claves-ps5-xbox": "trucos y claves (combinaciones de botones o códigos) y cómo activarlos",
    "gta-6-como-ganar-dinero": "métodos para ganar dinero, golpes rentables, negocios",
    "gta-6-mejores-coches": "coches y vehículos: dónde encontrarlos, los más rápidos, exclusivos, personalización",
    "gta-6-lista-de-misiones": "misiones principales y secundarias (sin spoilers de la trama)",
    "gta-6-trofeos-logros": "trofeos y logros: cómo conseguirlos",
    "gta-6-controles-ps5-xbox": "controles, ajustes y opciones recomendadas",
    "gta-6-mapa-leonida": "lugares y ubicaciones del mapa de Leonida, zonas, interiores",
}
SECCION = "## Últimos descubrimientos"
DIRECTO = POSTS / "gta-6-lanzamiento-en-directo.md"
MARCA_DIRECTO = "<!-- Entradas nuevas arriba."
_TOKEN_REDDIT: dict = {}


def _reddit_oauth(url: str):
    """Reddit bloquea los feeds RSS pedidos desde servidores (devuelve 404 o 403). Con una app
    de Reddit (REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET en los secretos de GitHub) se usa su API
    oficial, que sí responde. Devuelve entradas con la misma forma que las de feedparser."""
    import requests

    cid, sec = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    m = re.search(r"reddit\.com/r/([\w]+)/(new|top|hot)", url)
    if not (cid and sec and m):
        return None
    if not _TOKEN_REDDIT.get("t"):
        r = requests.post("https://www.reddit.com/api/v1/access_token", auth=(cid, sec),
                          data={"grant_type": "client_credentials"}, headers={"User-Agent": UA}, timeout=25)
        r.raise_for_status()
        _TOKEN_REDDIT["t"] = r.json()["access_token"]
    sub, orden = m.group(1), m.group(2)
    params = {"limit": 100}
    if orden == "top":
        params["t"] = "day"
    r = requests.get(f"https://oauth.reddit.com/r/{sub}/{orden}", params=params, timeout=25,
                     headers={"User-Agent": UA, "Authorization": f"bearer {_TOKEN_REDDIT['t']}"})
    r.raise_for_status()
    out = []
    for c in r.json().get("data", {}).get("children", []):
        d = c.get("data", {})
        texto = d.get("selftext", "") or ""
        if d.get("url") and "reddit.com" not in d["url"]:
            texto = f"{texto} {d['url']}"
        out.append({"link": "https://www.reddit.com" + d.get("permalink", ""), "title": d.get("title", ""),
                    "summary": texto, "author": "u/" + d.get("author", ""),
                    "published_parsed": time.gmtime(d.get("created_utc", time.time()))})
    return out
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

PROMPT = """Eres editor de una web de guías de GTA VI en español neutro (para España y Latinoamérica). \
Te paso una publicación de la comunidad (Reddit, YouTube, un medio...). Decide si es un DESCUBRIMIENTO ÚTIL \
del juego ya publicado (un truco, un secreto, la ubicación de algo, un método de dinero, cómo conseguir un trofeo...) \
y, si lo es, redacta una entrada breve para añadirla a una de nuestras guías.

GUÍAS DISPONIBLES (usa el identificador exacto):
{guias}

NORMAS:
- Usa SOLO lo que dice la publicación. Si falta información concreta (dónde, cómo), descártala.
- Descarta: filtraciones o material anterior al lanzamiento, rumores, memes, fan art, quejas, preguntas sin respuesta, \
bugs sin interés, spoilers de la historia, cualquier cosa que no se pueda comprobar jugando.
- Redacción propia, 40-120 palabras, tono claro y práctico. Nada de inventar.
- "verificado": true solo si la publicación muestra pruebas claras (vídeo o captura) Y procede de una fuente \
reconocida (medio especializado o creador conocido). En caso de duda, false.
- Si en el texto hay un enlace de YouTube con el descubrimiento, pon su id (11 caracteres) en "video_id" y, si se \
indica el minuto, en "video_inicio" (formato m:ss). Si no, deja ambos vacíos.

Responde SOLO con JSON válido:
{{"skip": true, "reason": "..."}}
o
{{"skip": false, "guia": "<identificador>", "titulo": "título corto y concreto (máx. 70 caracteres)", \
"texto": "la entrada en Markdown", "autor": "quién lo descubrió (ej. u/usuario o nombre del canal)", \
"plataforma": "Reddit | YouTube | <medio>", "verificado": false, "video_id": "", "video_inicio": ""}}"""


def activo(cfg: dict) -> bool:
    if os.environ.get("FORZAR_COMUNIDAD") == "1":
        return True
    c = cfg.get("comunidad") or {}
    desde = c.get("desde")
    if not desde:
        return False
    try:
        return datetime.now(timezone.utc) >= datetime.fromisoformat(desde)
    except ValueError:
        return False


def _texto(entry) -> str:
    raw = ""
    if entry.get("content"):
        raw = " ".join(c.get("value", "") for c in entry["content"])
    raw = raw or entry.get("summary", "")
    return htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))).strip(), raw


def _leer_feed(url: str):
    """Descarga un feed. Reddit limita las peticiones seguidas desde la misma IP (responde 429
    o vacío), así que entre consultas a Reddit se hace una pausa y se reintenta si pide esperar."""
    import feedparser
    import requests

    es_reddit = "reddit.com" in url
    if es_reddit:
        try:
            api = _reddit_oauth(url)
            if api is not None:
                return api
        except Exception as e:  # noqa: BLE001
            print(f"    (API de Reddit: {type(e).__name__}; se prueba el RSS)")
    intentos = 3 if es_reddit else 1
    for n in range(intentos):
        if es_reddit:
            time.sleep(6 + 15 * n)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
        except Exception as e:  # noqa: BLE001
            print(f"    (error de conexión: {type(e).__name__})")
            continue
        if r.status_code == 200:
            entries = feedparser.parse(r.content).entries
            if entries or not es_reddit:
                return entries
            estado = "200 vacío"
        else:
            estado = str(r.status_code)
        if n < intentos - 1:
            print(f"    (respuesta {estado}, reintento)")
    return []


def _canal(feed: dict, state: dict) -> str | None:
    """URL del feed de un canal de YouTube a partir de su @nombre (se guarda el ID para no repetir)."""
    if feed.get("url"):
        return feed["url"]
    h = feed.get("youtube")
    if not h:
        return None
    ids = state.setdefault("canales_yt", {})
    if h not in ids:
        import requests
        try:
            r = requests.get(f"https://www.youtube.com/{h}", timeout=25,
                             headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "es-ES,es;q=0.9"},
                             cookies={"CONSENT": "YES+1"})
            m = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', r.text) or re.search(r'channel/(UC[\w-]{22})', r.text)
        except Exception as e:  # noqa: BLE001
            print(f"    ({h}: {type(e).__name__})")
            return None
        if not m:
            print(f"    ({h}: no se encuentra el canal)")
            return None
        ids[h] = m.group(1)
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={ids[h]}"


def recoger(cfg: dict, state: dict) -> list[dict]:
    """Publicaciones recientes de las fuentes de la comunidad que parecen descubrimientos."""
    c = cfg.get("comunidad") or {}
    kw_juego = [k.lower() for k in cfg.get("keywords", [])]
    kw = [k.lower() for k in c.get("keywords", [])]
    horas = c.get("max_horas", 24)
    out = []
    for feed in c.get("feeds", []):
        url = _canal(feed, state)
        if not url:
            print(f"  · {feed['name']}: sin canal")
            continue
        try:
            entries = _leer_feed(url)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {feed['name']}: {e}")
            continue
        print(f"  · {feed['name']}: {len(entries)} entradas")
        for e in entries[:100]:
            link, title = e.get("link", ""), e.get("title", "")
            if not link or link in state["urls"]:
                continue
            pub = e.get("published_parsed") or e.get("updated_parsed")
            if pub and (time.time() - calendar.timegm(pub)) > horas * 3600:
                continue
            texto, raw = _texto(e)
            blob = f"{title} {texto}".lower()
            if feed.get("solo_juego") and not any(k in blob for k in kw_juego):
                continue
            if not any(k in blob for k in kw):
                continue
            videos = re.findall(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})", f"{link} {raw}")
            if not texto and e.get("media_description"):
                texto = e["media_description"]
            out.append({"fuente": feed["name"], "title": title, "url": link, "texto": texto[:4000],
                        "autor": (e.get("author") or "").replace("/u/", "u/"), "videos": videos[:3]})
    return out


def redactar(client, model: str, item: dict) -> dict | None:
    guias = "\n".join(f"- {k}: {v}" for k, v in GUIAS.items())
    user = (f"FUENTE: {item['fuente']}\nAUTOR: {item['autor'] or 'desconocido'}\nTÍTULO: {item['title']}\n"
            f"ENLACE: {item['url']}\nVÍDEOS ENLAZADOS: {', '.join(item['videos']) or 'ninguno'}\n\n"
            f"TEXTO:\n\"\"\"\n{item['texto']}\n\"\"\"")
    msg = client.messages.create(model=model, max_tokens=6000, system=PROMPT.format(guias=guias),
                                 messages=[{"role": "user", "content": user}])
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("  ! respuesta no válida de la IA")
        return None
    if data.get("skip"):
        print(f"  – descartada: {data.get('reason', '')}")
        return None
    if data.get("guia") not in GUIAS or not data.get("titulo") or not data.get("texto"):
        print("  ! faltan campos o guía desconocida")
        return None
    if data.get("video_id") and not re.fullmatch(r"[\w-]{11}", data["video_id"]):
        data["video_id"] = ""
    return data


def _yaml(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').strip() + '"'


def aplicar(data: dict, item: dict, ahora: datetime | None = None) -> Path | None:
    """Añade la entrada a la guía elegida. Devuelve la ruta modificada (o None si ya estaba)."""
    path = POSTS / f"{data['guia']}.md"
    if not path.exists():
        print(f"  ! no existe la guía {path.name}")
        return None
    s = path.read_text(encoding="utf-8")
    # Si la guía sigue oculta (draft), el descubrimiento no lo vería nadie: va al directo del lanzamiento
    if re.search(r"^draft: true\s*$", s.split("\n---\n", 1)[0], re.M) and DIRECTO.exists():
        directo = DIRECTO.read_text(encoding="utf-8")
        if MARCA_DIRECTO in directo and not re.search(r"^draft: true\s*$", directo.split("\n---\n", 1)[0], re.M):
            print(f"  · {path.name} aún está oculta: se añade al directo")
            return _al_directo(data, item, ahora)
    head, body = s.split("\n---\n", 1)

    # ¿ya tenemos algo muy parecido en esta guía?
    for t in re.findall(r"^### (.+)$", body, re.M):
        if SequenceMatcher(None, t.lower(), data["titulo"].lower()).ratio() > 0.8:
            print(f"  – ya está en la guía: {t}")
            return None

    ahora = ahora or datetime.now(timezone.utc)
    fecha = f"{ahora.day} de {MESES[ahora.month - 1]}"
    autor = data.get("autor") or item.get("autor") or "la comunidad"
    plataforma = data.get("plataforma") or item["fuente"]
    estado = "✅ Comprobado" if data.get("verificado") else "⚠️ Sin comprobar"
    partes = [f"### {data['titulo'].strip()}", "", data["texto"].strip(), ""]
    vid = data.get("video_id") or ""
    if vid:
        ini = data.get("video_inicio") or ""
        attr_ini = f' data-inicio="{ini}"' if re.fullmatch(r"\d{1,3}:\d{2}", ini or "") else ""
        partes += [f'<figure class="yt-guia" data-id="{vid}"{attr_ini} data-autor="{htmllib.escape(autor, quote=True)}"></figure>', ""]
    partes += [f"*Descubierto por {autor} en [{plataforma}]({item['url']}) · {fecha} · {estado}*", ""]
    entrada = "\n".join(partes)

    if SECCION in body:
        body = body.replace(SECCION + "\n", SECCION + "\n\n" + entrada, 1)
    else:
        bloque = (f"{SECCION}\n\n<!-- El robot añade aquí lo que descubre la comunidad, lo más nuevo arriba. "
                  f"Revisa y pasa a su sección lo que se confirme. -->\n\n{entrada}\n")
        m = re.search(r"^## ", body, re.M)
        body = body[:m.start()] + bloque + body[m.start():] if m else body.rstrip() + "\n\n" + bloque

    # fecha de actualización y fuente
    iso = ahora.astimezone().replace(microsecond=0).isoformat()
    head = re.sub(r"^updated: .*$", f"updated: {iso}", head, count=1, flags=re.M)
    fuente = f'  - name: {_yaml(f"{plataforma}: {data["titulo"]}")}\n    url: {_yaml(item["url"])}'
    if item["url"] not in head:
        if re.search(r"^sources: \[\]\s*$", head, re.M):
            head = re.sub(r"^sources: \[\]\s*$", "sources:\n" + fuente, head, count=1, flags=re.M)
        elif re.search(r"^sources:\s*$", head, re.M):
            head = re.sub(r"^sources:\s*$", "sources:\n" + fuente, head, count=1, flags=re.M)
        else:
            head = head.rstrip() + "\nsources:\n" + fuente
    path.write_text(head + "\n---\n" + body, encoding="utf-8")
    return path


def _al_directo(data: dict, item: dict, ahora: datetime | None = None) -> Path | None:
    s = DIRECTO.read_text(encoding="utf-8")
    head, body = s.split("\n---\n", 1)
    for t in re.findall(r"^### .*?· (.+)$", body, re.M):
        if SequenceMatcher(None, t.lower(), data["titulo"].lower()).ratio() > 0.8:
            print(f"  – ya está en el directo: {t}")
            return None
    ahora = ahora or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        local = ahora.astimezone(ZoneInfo("Europe/Madrid"))
    except Exception:  # noqa: BLE001
        local = ahora.astimezone()
    autor = data.get("autor") or item.get("autor") or "la comunidad"
    plataforma = data.get("plataforma") or item["fuente"]
    estado = "✅ Comprobado" if data.get("verificado") else "⚠️ Sin comprobar"
    partes = [f"### {local:%H:%M} · {data['titulo'].strip()}", "", data["texto"].strip(), ""]
    vid = data.get("video_id") or ""
    if vid:
        ini = data.get("video_inicio") or ""
        attr_ini = f' data-inicio="{ini}"' if re.fullmatch(r"\d{1,3}:\d{2}", ini or "") else ""
        partes += [f'<figure class="yt-guia" data-id="{vid}"{attr_ini} data-autor="{htmllib.escape(autor, quote=True)}"></figure>', ""]
    partes += [f"*Descubierto por {autor} en [{plataforma}]({item['url']}) · {estado}*", ""]
    entrada = "\n".join(partes)
    i = body.index(MARCA_DIRECTO)
    j = body.index("\n", i) + 1
    body = body[:j] + "\n" + entrada + body[j:]
    iso = local.replace(microsecond=0).isoformat()
    head = re.sub(r"^updated: .*$", f"updated: {iso}", head, count=1, flags=re.M)
    if item["url"] not in head:
        fuente = f'  - name: {_yaml(f"{plataforma}: {data["titulo"]}")}\n    url: {_yaml(item["url"])}'
        head = re.sub(r"^sources:\s*$", "sources:\n" + fuente, head, count=1, flags=re.M)
    DIRECTO.write_text(head + "\n---\n" + body, encoding="utf-8")
    return DIRECTO


def run(cfg: dict, state: dict, get_client, model: str, dry_run: bool = False, maximo: int = 5) -> list[Path]:
    if not activo(cfg):
        return []
    print("Modo lanzamiento: buscando descubrimientos de la comunidad…")
    items = recoger(cfg, state)
    print(f"{len(items)} posibles descubrimientos")
    if dry_run:
        for it in items:
            print(f"  - [{it['fuente']}] {it['title']}\n    {it['url']}")
        return []
    cambiados: list[Path] = []
    errores = 0
    for it in items:
        if len(cambiados) >= maximo:
            break
        print(f"→ {it['title']}")
        state["urls"].append(it["url"])
        try:
            data = redactar(get_client(), model, it)
        except Exception as e:  # noqa: BLE001
            print(f"  ! error: {type(e).__name__}: {str(e)[:200]}")
            state["urls"].remove(it["url"])
            errores += 1
            if errores >= 2:
                break
            continue
        if data:
            p = aplicar(data, it)
            if p:
                cambiados.append(p)
                print(f"  ✓ añadido a {p.name}")
    return cambiados
