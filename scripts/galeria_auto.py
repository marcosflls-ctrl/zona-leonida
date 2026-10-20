"""Revisa el kit de prensa de Rockstar y añade a scripts/galeria.json las capturas nuevas.

- Lee https://www.rockstargames.com/VI/media/screenshots (los nombres de archivo vienen en el HTML).
- Solo cuenta capturas con nombre tipo "Nombre_01.xxxx.jpg" (ignora portadas de caja, miniaturas, etc.).
- Compara por "Nombre_01", no por el archivo completo: si Rockstar cambia el código del final,
  se actualiza el archivo en vez de duplicar la imagen.
- Clasifica cada imagen con el grupo de las que ya tenemos del mismo tipo; si es un tipo nuevo
  (un personaje nuevo, por ejemplo), crea un grupo nuevo.
Escribe en GITHUB_OUTPUT: nuevas=<n> y resumen=<texto>.
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GAL = ROOT / "scripts" / "galeria.json"
URL = "https://www.rockstargames.com/VI/media/screenshots"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
PAT = re.compile(r"_next/static/media/(([A-Za-z][A-Za-z0-9_]*?)_(\d{2})\.[A-Za-z0-9_.~-]+?\.jpg)")
LIMITE = 60  # si aparecen más de golpe, algo raro pasa: no se toca nada


def slugify(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def humanize(prefix: str) -> str:
    p = re.sub(r"^(ULTIMATE_EDITION|VINTAGE_VICE_CITY(_PACK)?)_", "", prefix)
    return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in p.split("_"))


def base(archivo: str) -> str:
    m = re.match(r"([A-Za-z][A-Za-z0-9_]*?_\d{2})\.", archivo)
    return m.group(1) if m else archivo


def main() -> int:
    data = json.loads(GAL.read_text(encoding="utf-8"))
    imgs = data["imagenes"]
    by_base = {base(g["archivo"]): g for g in imgs}

    # cómo clasificamos cada prefijo, aprendido de lo que ya está en la galería
    tipos = {}
    for g in imgs:
        pref = base(g["archivo"]).rsplit("_", 1)[0]
        tipos.setdefault(pref, {"grupo": g["grupo"], "refs": g["refs"], "label": g["alt"].replace(", imagen oficial de GTA 6", "")})

    r = requests.get(URL, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}, timeout=40)
    r.raise_for_status()
    encontrados = {}
    for archivo, pref, num in PAT.findall(r.text):
        encontrados.setdefault(f"{pref}_{num}", (archivo, pref))
    print(f"Capturas en la web de Rockstar: {len(encontrados)} · en nuestra galería: {len(imgs)}")
    if len(encontrados) < 50:
        print("La página no tiene la lista esperada (¿ha cambiado su diseño?). No se toca nada.")
        return 0

    cambiados, nuevas = 0, []
    for b, (archivo, pref) in sorted(encontrados.items()):
        if b in by_base:
            if by_base[b]["archivo"] != archivo:  # mismo archivo, código nuevo
                by_base[b]["archivo"] = archivo
                cambiados += 1
            continue
        nuevas.append((b, archivo, pref))

    if len(nuevas) > LIMITE:
        print(f"Aparecen {len(nuevas)} capturas nuevas de golpe; parece un cambio de la web, no se añaden.")
        nuevas = []

    cuenta = Counter(g["grupo"] for g in imgs)
    usados = {g["slug"] for g in imgs}
    grupos_nuevos = Counter()
    for b, archivo, pref in nuevas:
        t = tipos.get(pref)
        if not t:
            refs = ["ultimate"] if pref.startswith("ULTIMATE_EDITION") else ["vintage"] if pref.startswith("VINTAGE") else ["nuevas"]
            t = {"grupo": slugify(humanize(pref)), "refs": refs, "label": humanize(pref)}
            tipos[pref] = t
        n = cuenta[t["grupo"]] + 1
        while f"{t['grupo']}-{n}" in usados:
            n += 1
        cuenta[t["grupo"]] = n
        slug = f"{t['grupo']}-{n}"
        usados.add(slug)
        imgs.append({"slug": slug, "grupo": t["grupo"], "refs": t["refs"], "archivo": archivo,
                     "alt": f"{t['label']}, imagen oficial de GTA 6"})
        grupos_nuevos[t["label"]] += 1
        print(f"  + {slug}  ({archivo})")

    if nuevas or cambiados:
        GAL.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    resumen = ", ".join(f"{v} de {k}" for k, v in grupos_nuevos.most_common())
    print(f"Nuevas: {len(nuevas)} · Archivos actualizados: {cambiados}" + (f" · {resumen}" if resumen else ""))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            primera = imgs[-len(nuevas)]["slug"] if nuevas else ""
            fh.write(f"nuevas={len(nuevas)}\ncambios={len(nuevas) + cambiados}\nresumen={resumen}\nprimera={primera}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
