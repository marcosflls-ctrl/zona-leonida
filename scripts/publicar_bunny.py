"""
Publica la web construida (dist/) en Bunny.net: almacenamiento (Storage Zone) + distribución (Pull Zone).

- Sube solo los archivos que han cambiado desde la última publicación (guarda una lista con sus huellas
  en el propio almacenamiento) y borra los que ya no existen.
- Convierte las redirecciones de public/_redirects en reglas de Bunny (Edge Rules) que responden con una
  redirección 301 de verdad, y deja además una página que redirige por si las reglas fallan.
- Redirige con 301 los otros dominios (www y b-cdn.net) al principal, el primero de BUNNY_HOSTNAME.
- Limpia la caché de las direcciones que han cambiado para que se vean al momento.

Variables de entorno (secretos de GitHub):
  BUNNY_STORAGE_ZONE      nombre del almacenamiento (p. ej. zona-leonida)
  BUNNY_STORAGE_PASSWORD  contraseña del almacenamiento (FTP & API access)
  BUNNY_API_KEY           clave de la cuenta (para limpiar la caché y crear las reglas de redirección)
  BUNNY_PULLZONE_ID       número de la distribución
  BUNNY_HOSTNAME          dominios públicos separados por comas, el principal primero (p. ej. zonaleonida.com), para limpiar la caché por dirección
  BUNNY_STORAGE_HOST      opcional, por defecto storage.bunnycdn.com (Fráncfort)
  INDEXNOW_KEY            clave pública de IndexNow (su archivo está en public/<clave>.txt). Con ella se avisa a
                          Bing, Yandex y otros buscadores de las páginas nuevas o cambiadas en cuanto se publican.
Uso: python scripts/publicar_bunny.py [carpeta]   (por defecto dist)
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
ZONE = os.environ["BUNNY_STORAGE_ZONE"]
PASSWORD = os.environ["BUNNY_STORAGE_PASSWORD"]
HOST = os.environ.get("BUNNY_STORAGE_HOST", "storage.bunnycdn.com")
API_KEY = os.environ.get("BUNNY_API_KEY", "")
PULLZONE = os.environ.get("BUNNY_PULLZONE_ID", "")
HOSTNAMES = [h.strip() for h in os.environ.get("BUNNY_HOSTNAME", "").split(",") if h.strip()]
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "").strip()
MANIFIESTO = ".publicado.json"
BASE = f"https://{HOST}/{ZONE}/"
S = requests.Session()
S.headers["AccessKey"] = PASSWORD


def leer_redirecciones() -> list[tuple[str, str]]:
    """Pares (origen, destino) de _redirects; se ignoran comodines y direcciones con dominio."""
    f = DIST / "_redirects"
    if not f.exists():
        return []
    pares = []
    for linea in f.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if len(partes) < 2 or linea.lstrip().startswith("#") or "*" in partes[0] or ":" in partes[0]:
            continue
        pares.append((partes[0], partes[1]))
    return pares


PREFIJO = "auto:"  # las reglas que gestiona este script; las demás de Bunny no se tocan


def igual(e: dict, cuerpo: dict) -> bool:
    """¿La regla que ya está en Bunny coincide con la que queremos?"""
    def condiciones(r: dict) -> list:
        return sorted((t.get("Type"), tuple(sorted(t.get("PatternMatches") or []))) for t in r.get("Triggers") or [])
    return (e.get("ActionType") == cuerpo["ActionType"]
            and str(e.get("ActionParameter1") or "") == cuerpo["ActionParameter1"]
            and str(e.get("ActionParameter2") or "") == cuerpo["ActionParameter2"]
            and e.get("TriggerMatchingType") == cuerpo["TriggerMatchingType"]
            and e.get("Enabled") and condiciones(e) == condiciones(cuerpo))


def reglas(pares: list[tuple[str, str]]) -> bool:
    """Sincroniza las Edge Rules de la distribución (redirecciones y caché del navegador). Devuelve False si algo falla."""
    if not API_KEY or not PULLZONE or not HOSTNAMES:
        print("· Sin clave de API: no se actualizan las reglas de redirección")
        return True
    dominio = HOSTNAMES[0]
    base = f"https://{dominio}"
    deseadas: dict[str, dict] = {}

    def regla(nombre: str, destino: str, patrones: list[str]) -> None:
        deseadas[f"{PREFIJO} {nombre}"] = {
            "ActionType": 1,  # redirección
            "ActionParameter1": destino,
            "ActionParameter2": "301",
            "TriggerMatchingType": 0,
            "Enabled": True,
            # Bunny admite como mucho 5 patrones por condición: se reparten en varias condiciones (Type 0 = URL)
            "Triggers": [{"Type": 0, "PatternMatchingType": 0, "PatternMatches": patrones[i:i + 5]}
                         for i in range(0, len(patrones), 5)],
        }

    # Páginas y feeds: el navegador las guarda solo 1 minuto, para que quien vuelve vea la versión nueva.
    # La CDN sigue guardándolas (se limpian al publicar) y las imágenes, CSS y JS mantienen sus 30 días.
    deseadas[f"{PREFIJO} páginas siempre frescas en el navegador"] = {
        "ActionType": 16,  # Override Browser Cache Time (segundos)
        "ActionParameter1": "60",
        "ActionParameter2": "",
        "TriggerMatchingType": 0,  # basta con que se cumpla una condición
        "Enabled": True,
        "Triggers": [
            {"Type": 0, "PatternMatchingType": 0, "PatternMatches": [f"*://{dominio}/", f"*://{dominio}/*/"]},
            {"Type": 3, "PatternMatchingType": 0, "PatternMatches": ["html", "xml", "json", "txt"]},
        ],
    }

    otros = HOSTNAMES[1:]
    if otros:
        regla(f"otros dominios a {dominio}", base + "{{path}}", [f"*://{h}/*" for h in otros])
    por_destino: dict[str, list[str]] = {}
    for origen, destino in pares:
        destino = destino if destino.startswith("http") else base + destino
        pats = por_destino.setdefault(destino, [])
        for o in {origen, origen.rstrip("/")} - {""}:
            pats.append(f"*://{dominio}{o}")
    for destino, pats in por_destino.items():
        pats = sorted(set(pats))
        for i in range(0, len(pats), 20):  # hasta 4 condiciones de 5 patrones por regla
            regla(f"{destino[len(base):] or '/'} #{i // 20 + 1}", destino, pats[i:i + 20])

    h = {"AccessKey": API_KEY}
    r = requests.get(f"https://api.bunny.net/pullzone/{PULLZONE}", headers=h, timeout=60)
    if r.status_code != 200:
        print(f"::warning title=Reglas de Bunny::No se pudo leer la distribución ({r.status_code}): {r.text[:200]}")
        return False
    existentes = {e.get("Description") or "": e for e in r.json().get("EdgeRules") or []}
    ok, cambios = True, 0
    for nombre, cuerpo in deseadas.items():
        e = existentes.get(nombre)
        if e and igual(e, cuerpo):
            continue
        datos = dict(cuerpo, Description=nombre)
        if e:
            datos["Guid"] = e["Guid"]
        r = requests.post(f"https://api.bunny.net/pullzone/{PULLZONE}/edgerules/addOrUpdate", headers=h, json=datos, timeout=60)
        if r.status_code not in (200, 201, 204):
            ok = False
            print(f"::warning title=Reglas de Bunny::No se pudo guardar «{nombre}» ({r.status_code}): {r.text[:200]}")
        else:
            cambios += 1
    for nombre, e in existentes.items():
        if nombre.startswith(PREFIJO) and nombre not in deseadas:
            r = requests.delete(f"https://api.bunny.net/pullzone/{PULLZONE}/edgerules/{e['Guid']}", headers=h, timeout=60)
            cambios += r.status_code in (200, 204)
    print(f"Reglas de Bunny: {len(deseadas)} ({cambios} cambiadas)")
    if cambios:
        requests.post(f"https://api.bunny.net/pullzone/{PULLZONE}/purgeCache", headers=h, timeout=60)
        print("· Caché limpiada entera por cambio de reglas")
    return ok


def redirecciones() -> int:
    """Crea una página de redirección por cada línea de _redirects (origen destino [código])."""
    # Bunny no hace redirecciones 301 desde el almacenamiento: se crea una página con redirección inmediata
    # (meta refresh 0) y canonical al destino, que Google trata como una redirección permanente. Sin noindex,
    # para que la dirección antigua pase su valor a la nueva.
    f = DIST / "_redirects"
    if not f.exists():
        return 0
    n = 0
    for linea in f.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if len(partes) < 2 or linea.lstrip().startswith("#") or "*" in partes[0] or ":" in partes[0]:
            continue
        origen, destino = partes[0], partes[1]
        dest = DIST / origen.strip("/") / "index.html" if origen.endswith("/") else DIST / origen.lstrip("/")
        if dest.exists():
            continue
        d = html.escape(destino, quote=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Redirigiendo…</title>'
            f'<link rel="canonical" href="{d}">'
            f'<meta http-equiv="refresh" content="0; url={d}"><script>location.replace("{d}")</script></head>'
            f'<body><p>Esta página se ha movido a <a href="{d}">{d}</a>.</p></body></html>', encoding="utf-8")
        n += 1
    f.unlink()
    return n


def huella(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def subir(ruta: str) -> tuple[str, bool]:
    with open(DIST / ruta, "rb") as fh:
        r = S.put(BASE + quote(ruta), data=fh, timeout=120)
    return ruta, r.status_code in (200, 201)


def borrar(ruta: str) -> tuple[str, bool]:
    r = S.delete(BASE + quote(ruta), timeout=60)
    return ruta, r.status_code in (200, 404)


def purgar(rutas: list[str]) -> None:
    if not API_KEY or not PULLZONE:
        print("· Sin clave de API: no se limpia la caché")
        return
    h = {"AccessKey": API_KEY}
    if len(rutas) > 300 or not HOSTNAMES:
        r = requests.post(f"https://api.bunny.net/pullzone/{PULLZONE}/purgeCache", headers=h, timeout=60)
        print(f"· Caché limpiada entera ({r.status_code})")
        return
    urls = set()
    for ruta in rutas:
        web = "/" + ruta
        if web.endswith("/index.html"):
            urls.add(web[: -len("index.html")])
        urls.add(web)
    total = 0
    for host in HOSTNAMES:
        for u in urls:
            r = requests.post("https://api.bunny.net/purge", params={"url": f"https://{host}{quote(u)}"}, headers=h, timeout=30)
            total += r.status_code in (200, 204)
    print(f"· Caché limpiada en {total} direcciones")


def indexnow(rutas: list[str]) -> None:
    """Avisa a los buscadores que usan IndexNow (Bing, Yandex, Seznam...) de las páginas nuevas o cambiadas.
    Nunca hace fallar la publicación: si no responde, se avisa con un warning y ya está."""
    if not INDEXNOW_KEY or not HOSTNAMES:
        return
    dominio = HOSTNAMES[0]
    urls = []
    for r in rutas:
        if r.endswith("index.html") and not r.startswith("404"):
            urls.append(f"https://{dominio}/{r[: -len('index.html')]}")
        elif r.endswith(".xml") and "sitemap" in r:
            urls.append(f"https://{dominio}/{r}")
    if not urls:
        return
    try:
        resp = requests.post("https://api.indexnow.org/indexnow", timeout=60, json={
            "host": dominio, "key": INDEXNOW_KEY, "keyLocation": f"https://{dominio}/{INDEXNOW_KEY}.txt",
            "urlList": urls[:10000],
        })
        if resp.status_code in (200, 202):
            print(f"· IndexNow: avisadas {len(urls[:10000])} direcciones")
        else:
            print(f"::warning title=IndexNow::Respuesta {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"::warning title=IndexNow::{type(e).__name__}: {e}")


def main() -> int:
    if not DIST.is_dir():
        print(f"! No existe {DIST}")
        return 1
    pares = leer_redirecciones()
    print(f"Redirecciones convertidas: {redirecciones()}")
    local = {p.relative_to(DIST).as_posix(): huella(p) for p in DIST.rglob("*") if p.is_file()}
    r = S.get(BASE + MANIFIESTO, timeout=60)
    remoto = r.json() if r.status_code == 200 else {}
    cambiados = sorted(k for k, v in local.items() if remoto.get(k) != v)
    sobran = sorted(k for k in remoto if k not in local)
    print(f"{len(local)} archivos · {len(cambiados)} por subir · {len(sobran)} por borrar")

    fallos = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for ruta, ok in ex.map(subir, cambiados):
            if not ok:
                fallos.append(ruta)
    if fallos:
        print(f"! Fallaron {len(fallos)} subidas, p. ej. {fallos[:5]}")
        # se guarda el manifiesto sin los fallidos, para reintentarlos la próxima vez
        for f in fallos:
            local.pop(f, None)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(borrar, sobran))
    S.put(BASE + MANIFIESTO, data=json.dumps(local).encode(), timeout=60)

    # Solo hace falta limpiar la caché de lo que ya existía (lo nuevo aún no está en caché)
    purgar([c for c in cambiados if c in remoto and c not in fallos] + sobran)
    indexnow([c for c in cambiados if c not in fallos])
    reglas_ok = reglas(pares)
    if fallos:
        return 1
    print("✓ Publicado")
    if not reglas_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
