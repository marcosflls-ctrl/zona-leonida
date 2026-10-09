"""
Publica en el canal de Telegram los artículos nuevos.

Uso: python scripts/telegram.py src/content/posts/a.md [src/content/posts/b.md ...]
Variables: TELEGRAM_BOT_TOKEN (secreto), TELEGRAM_CHAT (por defecto @zonaleonida), SITE_URL.
Espera a que la página esté publicada en la web antes de enviarla.
"""
from __future__ import annotations

import html
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

SITE = os.environ.get("SITE_URL", "https://zonaleonida.com").rstrip("/")
CHAT = os.environ.get("TELEGRAM_CHAT", "@zonaleonida")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CAT_EMOJI = {"noticias": "📰", "guias": "🗺️", "trucos": "🎮", "descubrimientos": "🔍"}


def frontmatter(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    data = {}
    if not m:
        return data
    for line in m.group(1).splitlines():
        mm = re.match(r'^(\w+):\s*(.*)$', line)
        if mm:
            v = mm.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] == '"':
                v = v[1:-1].replace('\\"', '"')
            data[mm.group(1)] = v
    return data


def wait_online(url: str, timeout: int = 420) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.get(url, timeout=15).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(15)
    return False


def send(path: Path) -> None:
    d = frontmatter(path)
    if d.get("draft") == "true":
        print(f"– {path.name}: borrador, no se publica")
        return
    try:
        date = datetime.fromisoformat(d["date"].replace("Z", "+00:00"))
        if date > datetime.now(timezone.utc):
            print(f"– {path.name}: fecha futura, no se publica todavía")
            return
    except (KeyError, ValueError):
        pass
    cat = d.get("category", "noticias")
    url = f"{SITE}/{cat}/{path.stem}/"
    if not wait_online(url):
        print(f"! {path.name}: la página no responde todavía, se omite")
        return
    rumor = " · <b>RUMOR</b>" if d.get("rumor") == "true" else ""
    caption = (
        f"{CAT_EMOJI.get(cat, '📰')} <b>{html.escape(d.get('title', ''))}</b>{rumor}\n\n"
        f"{html.escape(d.get('description', ''))}\n\n"
        f"👉 <a href=\"{url}\">Leer en Zona Leonida</a>"
    )
    img = d.get("image") or f"/img/portadas/{cat}.webp"
    api = f"https://api.telegram.org/bot{TOKEN}"
    r = requests.post(f"{api}/sendPhoto", data={
        "chat_id": CHAT, "photo": SITE + img, "caption": caption, "parse_mode": "HTML",
    }, timeout=30)
    if not r.ok:  # si la imagen falla, se envía solo el texto con vista previa del enlace
        r = requests.post(f"{api}/sendMessage", data={
            "chat_id": CHAT, "text": caption, "parse_mode": "HTML",
        }, timeout=30)
    print(("✓ " if r.ok else "! ") + f"{path.name}: {r.status_code}" + ("" if r.ok else f" {r.text[:200]}"))


def main(paths: list[str]) -> int:
    if not TOKEN:
        print("Falta TELEGRAM_BOT_TOKEN: no se publica nada")
        return 0
    for p in paths:
        path = Path(p)
        if path.suffix == ".md" and path.exists():
            send(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
