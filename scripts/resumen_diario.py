"""Resumen diario del robot, enviado en privado por Telegram.

Cuenta las ejecuciones de las últimas 24 horas (radar, galería, Telegram), las propuestas
pendientes de revisar y avisa si el robot ha fallado o casi no ha funcionado.
Necesita: GITHUB_TOKEN, GITHUB_REPOSITORY, TELEGRAM_BOT_TOKEN, TELEGRAM_AVISOS_CHAT_ID.
"""
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

REPO = os.environ["GITHUB_REPOSITORY"]
API = f"https://api.github.com/repos/{REPO}"
GH = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
FLUJOS = {"radar.yml": "Radar de noticias", "galeria-auto.yml": "Galería oficial", "telegram.yml": "Canal de Telegram",
          "redes.yml": "Carruseles de redes"}


def ejecuciones(flujo: str, desde: datetime) -> list[dict]:
    r = requests.get(f"{API}/actions/workflows/{flujo}/runs", headers=GH, timeout=30,
                     params={"per_page": 100, "created": f">={desde.strftime('%Y-%m-%dT%H:%M:%SZ')}"})
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json().get("workflow_runs", [])


def main() -> int:
    desde = datetime.now(timezone.utc) - timedelta(hours=24)
    lineas, alertas = [], []
    for flujo, nombre in FLUJOS.items():
        runs = [r for r in ejecuciones(flujo, desde) if r.get("status") == "completed"]
        c = Counter(r.get("conclusion") for r in runs)
        ok, mal = c.get("success", 0), c.get("failure", 0) + c.get("timed_out", 0)
        if not runs:
            lineas.append(f"• {nombre}: sin ejecuciones")
            continue
        lineas.append(f"• {nombre}: {ok} bien" + (f", {mal} con fallo" if mal else ""))
        if mal:
            ultimo = next(r for r in runs if r.get("conclusion") in ("failure", "timed_out"))
            alertas.append(f"❌ {nombre} ha fallado {mal} {'vez' if mal == 1 else 'veces'}. Último fallo: {ultimo['html_url']}")
        if flujo == "radar.yml" and len([r for r in runs if r.get("event") == "schedule"]) < 12:
            alertas.append("⚠️ El radar ha funcionado menos de lo normal (GitHub se ha saltado ejecuciones programadas).")

    prs = requests.get(f"{API}/pulls", headers=GH, timeout=30, params={"state": "open", "per_page": 50}).json()
    pendientes = [p for p in prs if any(l["name"] == "radar" for l in p.get("labels", []))]

    texto = "🤖 <b>Resumen del día de Zona Leonida</b>\n\n" + "\n".join(lineas)
    texto += f"\n\n📝 Propuestas pendientes de revisar: <b>{len(pendientes)}</b>"
    if pendientes:
        texto += "\n" + "\n".join(f"  · <a href=\"{p['html_url']}\">{p['title']}</a>" for p in pendientes[:5])
    texto += "\n\n" + ("\n".join(alertas) if alertas else "✅ Todo ha funcionado bien.")

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_AVISOS_CHAT_ID")
    if not token or not chat:
        print("Falta TELEGRAM_AVISOS_CHAT_ID (o el token): no se envía. Resumen que se habría enviado:\n")
        print(texto)
        return 0
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                      data={"chat_id": chat, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": "true"})
    print("Enviado" if r.ok else f"Error de Telegram: {r.status_code} {r.text[:200]}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
