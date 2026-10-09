"""Descarga la galería oficial de Rockstar (kit de prensa de GTA VI).

Lee scripts/galeria.json y guarda cada imagen en public/img/oficial/<slug>.webp
(1600 px de ancho). Solo descarga las que faltan, así que se puede ejecutar
cuantas veces haga falta.
"""
import io
import json
import pathlib
import sys
import time

import requests
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "scripts" / "galeria.json").read_text(encoding="utf-8"))
OUT = ROOT / "public" / "img" / "oficial"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Referer": "https://www.rockstargames.com/VI/media/screenshots",
}


def main():
    nuevas, fallos = 0, []
    for img in DATA["imagenes"]:
        dest = OUT / f"{img['slug']}.webp"
        if dest.exists():
            continue
        url = DATA["base"] + img["archivo"] + "?imwidth=1920"
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            im.save(dest, "WEBP", quality=80, method=6)
            nuevas += 1
            print(f"OK  {img['slug']}  ({dest.stat().st_size // 1024} KB)")
        except Exception as e:  # noqa: BLE001
            fallos.append(img["slug"])
            print(f"ERR {img['slug']}: {e}")
        time.sleep(0.5)
    print(f"\nNuevas: {nuevas}. Fallos: {len(fallos)} {fallos}")
    if fallos and not nuevas:
        sys.exit(1)


if __name__ == "__main__":
    main()
