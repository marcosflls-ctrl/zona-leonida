"""Filtro previo barato para el radar.

Antes de que el modelo redactor (Sonnet) lea el texto completo de cada noticia, una sola consulta
a Haiku revisa SOLO los títulos de todas las candidatas y quita las que claramente no darían
artículo (fuera de tema, menores o repetidas). Así no se paga una lectura completa por cada
noticia que al final se descarta.

Si el filtro falla por lo que sea, no se pierde nada: se dejan pasar todas las candidatas y el
redactor decide como antes.
"""
from __future__ import annotations

import json
import os
import re

MODELO_FILTRO = os.environ.get("MODELO_FILTRO", "claude-haiku-5-5")
MAX_TITULOS = 60  # candidatas que se revisan en una consulta

_INSTRUCCIONES = """Eres el editor de una web de noticias. Recibes las NORMAS que sigue el redactor de la web, \
la lista de ARTÍCULOS YA PUBLICADOS y una lista de NOTICIAS CANDIDATAS (solo su título y su fuente).

Tu trabajo es ahorrar: quita las candidatas que, según las normas, el redactor descartaría con seguridad \
solo por el título (fuera de tema, menores, opinión, promocionales, o la misma noticia que un artículo ya \
publicado o que otra candidata de la lista).

- ANTE LA DUDA, DÉJALA PASAR: el redactor leerá el texto completo y decidirá. Solo quitas lo evidente.
- Si dos candidatas son la misma noticia contada por medios distintos, deja pasar solo la de la fuente \
más oficial o completa.
- No inventes números: usa los de la lista.

Responde SOLO con JSON, sin nada más:
{"pasan": [0, 3, 5], "fuera": {"1": "motivo breve", "2": "motivo breve", "4": "motivo breve"}}"""


def prefiltrar(client, candidates: list[dict], posts: list[dict], normas: str):
    """Devuelve (las que pasan, [(candidata, motivo), ...] las quitadas)."""
    # las que no tienen título (p. ej. una noticia de Rockstar aún sin leer) siempre pasan
    revisables = [c for c in candidates[:MAX_TITULOS] if c.get("title")]
    if len(revisables) < 2:
        return candidates, []
    lista = "\n".join(f"{i}. [{c.get('source', '')}] {c['title'][:200]}" for i, c in enumerate(revisables))
    publicados = "\n".join(f"- {p['title']}" for p in posts[:60]) or "(ninguno aún)"
    try:
        msg = client.messages.create(
            model=MODELO_FILTRO,
            max_tokens=3000,
            system=[
                {"type": "text", "text": _INSTRUCCIONES},
                {"type": "text", "text": "NORMAS DEL REDACTOR:\n" + normas, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": (
                f"ARTÍCULOS YA PUBLICADOS (los primeros son los más recientes):\n{publicados}\n\n"
                f"NOTICIAS CANDIDATAS:\n{lista}"
            )}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
        data = json.loads(raw)
        fuera = {int(k): str(v) for k, v in (data.get("fuera") or {}).items()}
    except Exception as e:  # noqa: BLE001 — si el filtro falla, pasan todas
        print(f"  ! filtro previo no disponible ({type(e).__name__}: {str(e)[:150]}); pasan todas")
        return candidates, []

    quitadas = [(c, fuera[i]) for i, c in enumerate(revisables) if i in fuera]
    ids_fuera = {id(c) for c, _ in quitadas}
    pasan = [c for c in candidates if id(c) not in ids_fuera]
    print(f"Filtro previo: pasan {len(pasan)} de {len(candidates)}")
    for c, motivo in quitadas:
        print(f"  – fuera: {c['title'][:90]} ({motivo})")
    return pasan, quitadas
