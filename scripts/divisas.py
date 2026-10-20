"""
Tipos de cambio del día frente al dólar, de la API abierta y gratuita de ExchangeRate-API
(https://www.exchangerate-api.com/docs/free), sin clave. Sirven para el comparador de precios
de GTA 6 en Latinoamérica (componente ComparadorPrecio).

Guarda en src/data/divisas.json las monedas que usa el comparador. La API actualiza una vez al día.

Uso: python scripts/divisas.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "data" / "divisas.json"
URL = "https://open.er-api.com/v6/latest/USD"
UA = "Mozilla/5.0 (compatible; ZonaLeonida/1.0; +https://zonaleonida.com)"
MONEDAS = ["EUR", "MXN", "ARS", "COP", "CLP", "PEN", "UYU", "BRL", "GTQ", "CRC", "DOP", "BOB", "PYG"]


def aviso(tipo: str, texto: str) -> None:
    print(texto)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{tipo} title=Divisas::{texto}")


def main() -> int:
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        d = r.json()
    except Exception as e:  # noqa: BLE001
        aviso("error", f"{type(e).__name__}: {str(e)[:300]}")
        return 1
    tasas = d.get("rates") or {}
    if d.get("result") != "success" or any(m not in tasas for m in MONEDAS):
        aviso("error", f"Respuesta incompleta ({d.get('result')}): no se cambia nada")
        return 1
    fecha = datetime.fromtimestamp(int(d.get("time_last_update_unix", 0)), tz=timezone.utc).astimezone(ZoneInfo("Europe/Madrid"))
    salida = {
        "fuente": "ExchangeRate-API",
        "fecha": fecha.date().isoformat(),
        "actualizado": datetime.now(ZoneInfo("Europe/Madrid")).replace(microsecond=0).isoformat(),
        "base": "USD",
        "tasas": {m: tasas[m] for m in MONEDAS},
    }
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    aviso("notice", f"{salida['fecha']}: 1 $ = {tasas['EUR']} € · {tasas['MXN']} MXN · {tasas['ARS']} ARS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
