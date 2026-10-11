"""Vigila el canal oficial de Rockstar Games en YouTube y añade a src/data/trailers.json
los vídeos nuevos de GTA VI (tráilers, miradas extendidas…), para que la página de Tráilers
se actualice sola. Escribe en GITHUB_OUTPUT: nuevos=<n> y lista=<títulos>.

Uso: python scripts/trailers_auto.py [--prueba]   (--prueba: solo muestra lo que ve, no escribe)
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "src" / "data" / "trailers.json"
CANAL = "UC6VcWc1rAoWdBCM0JxrRQ3A"  # Rockstar Games
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CANAL}"
UA = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"
ES_GTA6 = re.compile(r"grand theft auto vi\b|\bgta vi\b|\bgta 6\b", re.I)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def traducir(titulo: str) -> str:
    t = re.sub(r"\s*[|·-]\s*Rockstar Games\s*$", "", titulo).strip()
    t = re.sub(r"Grand Theft Auto VI", "GTA VI", t, flags=re.I)
    t = re.sub(r"Launch Trailer", "Tráiler de lanzamiento", t, flags=re.I)
    t = re.sub(r"Official Trailer", "Tráiler oficial", t, flags=re.I)
    t = re.sub(r"Trailer\s*(\d+)", r"Tráiler \1", t, flags=re.I)
    t = re.sub(r"\bTrailer\b", "Tráiler", t, flags=re.I)
    t = re.sub(r"Gameplay", "Gameplay", t, flags=re.I)
    if not t.lower().startswith("gta vi"):
        t = f"GTA VI: {t}"
    return t


def main() -> int:
    prueba = "--prueba" in sys.argv
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    conocidos = {v["id"] for v in datos}
    ultima = max(v["fecha"] for v in datos)
    r = requests.get(FEED, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    print(f"Canal: {feed.feed.get('title', '?')} · {len(feed.entries)} vídeos recientes · último que tenemos: {ultima}")
    nuevos = []
    for e in feed.entries:
        vid = e.get("yt_videoid") or ""
        titulo = e.get("title", "")
        fecha = (e.get("published") or "")[:10]
        es_short = "/shorts/" in e.get("link", "")
        print(f"  {'·' if ES_GTA6.search(titulo) else ' '} {fecha} {vid} {titulo}{' (short)' if es_short else ''}")
        if not vid or vid in conocidos or es_short or not ES_GTA6.search(titulo) or fecha <= ultima:
            continue
        d = datetime.fromisoformat(fecha)
        nuevos.append({
            "id": vid,
            "titulo": traducir(titulo),
            "fecha": fecha,
            "fechaTxt": f"{d.day} de {MESES[d.month - 1]} de {d.year}",
            "texto": "Nuevo vídeo oficial publicado por Rockstar Games en su canal de YouTube.",
        })
    print(f"Nuevos: {len(nuevos)}")
    if nuevos and not prueba:
        DATOS.write_text(json.dumps(nuevos + datos, ensure_ascii=False, indent=1), encoding="utf-8")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"nuevos={0 if prueba else len(nuevos)}\n")
            fh.write("lista=" + " | ".join(f"{v['titulo']} (https://youtu.be/{v['id']})" for v in nuevos) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
