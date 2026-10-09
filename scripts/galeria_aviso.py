"""Avisa en el canal de Telegram de que hay imágenes oficiales nuevas en la galería.
Uso: python scripts/galeria_aviso.py <n_nuevas> <slug_primera> "<resumen>"
Espera a que la web publicada sirva la imagen antes de enviar el mensaje."""
import os
import sys
import time

import requests

SITE = os.environ.get("SITE_URL", "https://zonaleonida.com")
CHAT = os.environ.get("TELEGRAM_CHAT", "@zonaleonida")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def main() -> int:
    n, primera, resumen = int(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
    if not TOKEN or n < 1 or n > 30 or not primera:
        print("Nada que avisar.")
        return 0
    foto = f"{SITE}/img/oficial/{primera}.webp"
    for _ in range(20):  # hasta ~10 min esperando a que Cloudflare publique
        try:
            if requests.head(foto, timeout=15).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(30)
    texto = "imagen nueva" if n == 1 else "imágenes nuevas"
    caption = (f"📸 <b>Rockstar ha publicado {n} {texto} de GTA 6</b>"
               + (f"\n{resumen}" if resumen else "")
               + f"\n\n👉 <a href=\"{SITE}/imagenes-oficiales/\">Verlas en Zona Leonida</a>")
    api = f"https://api.telegram.org/bot{TOKEN}"
    r = requests.post(f"{api}/sendPhoto", data={"chat_id": CHAT, "photo": foto, "caption": caption, "parse_mode": "HTML"}, timeout=30)
    if not r.ok:
        r = requests.post(f"{api}/sendMessage", data={"chat_id": CHAT, "text": caption, "parse_mode": "HTML"}, timeout=30)
    print("Telegram:", r.status_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
