"""Vigila las noticias por si se publica la lista de trofeos/logros de GTA VI (o algo sobre el platino)
y avisa por Telegram en privado, para preparar la guía de trofeos al momento.

No visita webs de trofeos (bloquean a los robots): lee los feeds de noticias del radar y búsquedas
de Google News. Guarda lo ya avisado en scripts/state/trofeos.json. La primera vez solo memoriza lo que
ya existe, sin avisar.

Uso: python scripts/trofeos_vigia.py [--prueba]   (--prueba: muestra lo que encuentra, no avisa ni guarda)
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
ESTADO = ROOT / "scripts" / "state" / "trofeos.json"
UA = "Mozilla/5.0 (compatible; ZonaLeonidaRadar/1.0)"
GTA6 = re.compile(r"grand theft auto vi\b|grand theft auto 6\b|\bgta ?vi\b|\bgta ?6\b", re.I)
TROFEOS = re.compile(
    r"trofeos?\b|platino|lista de logros|logros y trofeos|trophy|trophies|platinum|"
    r"achievements? (list|revealed|leak)|(full|complete) (list of )?achievements|gamerscore", re.I)
BUSQUEDAS = [
    "GTA 6 trophy list", "GTA 6 trophies", "GTA 6 platinum trophy", "GTA 6 achievements list",
    "GTA 6 lista de trofeos", "GTA 6 trofeos platino",
]


def fuentes() -> list[str]:
    cfg = json.loads((ROOT / "scripts" / "feeds.json").read_text(encoding="utf-8"))
    urls = [f.get("url", "") if isinstance(f, dict) else f for f in cfg.get("feeds", [])]
    urls = [u for u in urls if u and u.startswith("http")]
    for q in BUSQUEDAS:
        es = "trofeos" in q
        hl, gl, ceid = ("es", "ES", "ES:es") if es else ("en-US", "US", "US:en")
        urls.append(f"https://news.google.com/rss/search?q={quote_plus(q)}+when:7d&hl={hl}&gl={gl}&ceid={ceid}")
    return urls


def main() -> int:
    prueba = "--prueba" in sys.argv
    primera = not ESTADO.exists()
    avisados = set() if primera else set(json.loads(ESTADO.read_text(encoding="utf-8")))
    nuevos, vistos = [], set()
    for url in fuentes():
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            feed = feedparser.parse(r.content)
            print(f"{r.status_code} {len(feed.entries):3d} entradas · {url[:90]}")
        except Exception as e:  # una fuente caída no debe parar el resto
            print(f"ERR {url[:90]}: {e}")
            continue
        for e in feed.entries:
            titulo = e.get("title", "")
            texto = f"{titulo} {e.get('summary', '')[:300]}"
            if not (GTA6.search(texto) and TROFEOS.search(titulo)):
                continue
            clave = re.sub(r"\W+", " ", titulo.lower()).strip()[:90]
            if clave in vistos:
                continue
            vistos.add(clave)
            print(f"   ★ {titulo}")
            if clave not in avisados:
                nuevos.append({"clave": clave, "titulo": titulo, "link": e.get("link", "")})

    print(f"Coincidencias: {len(vistos)} · nuevas: {len(nuevos)}{' (primera vez: solo se memorizan)' if primera else ''}")
    if prueba:
        return 0
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(sorted(avisados | {n["clave"] for n in nuevos}), ensure_ascii=False, indent=1),
                      encoding="utf-8")
    if primera or not nuevos:
        return 0
    token, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not (token and chat):
        print("Sin Telegram configurado")
        return 0
    lineas = "\n\n".join(f"• {n['titulo']}\n{n['link']}" for n in nuevos[:5])
    texto = ("🏆 Noticias sobre los TROFEOS de GTA VI:\n\n" + lineas +
             "\n\nSi es la lista oficial, pídeme que rellene la guía de trofeos y el platino (está preparada, oculta).")
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"}, timeout=30)
    print("Telegram:", r.status_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
