"""Crea versiones pequeñas (-400 y -800 px de ancho) de las imágenes de la web,
para que en el móvil y en las tarjetas no se descargue la foto grande.
Se puede ejecutar cuantas veces haga falta: solo crea las que faltan."""
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIRS = ["oficial", "banco", "radar", "portadas"]
SIZES = (400, 800)


def make_variants(path: pathlib.Path) -> int:
    if path.stem.endswith(tuple(f"-{s}" for s in SIZES) + tuple(f"-{r}" for r in RECORTES)):
        return 0
    made = 0
    with Image.open(path) as im:
        im = im.convert("RGB")
        for w in SIZES:
            dest = path.with_name(f"{path.stem}-{w}.webp")
            if dest.exists() or im.width <= w:
                continue
            im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(dest, "WEBP", quality=78, method=6)
            made += 1
    return made


# Formatos extra para las portadas: Google recomienda dar la imagen principal de un artículo
# en 16:9, 4:3 y 1:1 para mostrarla bien en Discover y en los resultados con imagen.
RECORTES = {"4x3": (1200, 900), "1x1": (900, 900)}


def make_crops(path: pathlib.Path) -> int:
    made = 0
    with Image.open(path) as im:
        im = im.convert("RGB")
        for nombre, (w, h) in RECORTES.items():
            dest = path.with_name(f"{path.stem}-{nombre}.webp")
            if dest.exists():
                continue
            escala = max(w / im.width, h / im.height)          # cubre el recorte entero
            r = im.resize((round(im.width * escala), round(im.height * escala)), Image.LANCZOS)
            x, y = (r.width - w) // 2, (r.height - h) // 2      # recorte centrado
            r.crop((x, y, x + w, y + h)).save(dest, "WEBP", quality=78, method=6)
            made += 1
    return made


def portadas() -> int:
    """Crea los recortes 4:3 y 1:1 de las imágenes que son portada de algún artículo."""
    import re
    made = 0
    for f in (ROOT / "src" / "content" / "posts").glob("*.md"):
        m = re.search(r"^image:\s*(/img/\S+\.webp)\s*$", f.read_text(encoding="utf-8"), re.M)
        src = ROOT / "public" / m.group(1).lstrip("/") if m else None
        if src and src.exists():
            made += make_crops(src)
    return made


def main(paths=None) -> None:
    files = [pathlib.Path(p) for p in paths] if paths else [
        f for d in DIRS for f in sorted((ROOT / "public" / "img" / d).glob("*.webp"))]
    total = sum(make_variants(f) for f in files)
    print(f"Miniaturas nuevas: {total} · recortes de portada nuevos: {portadas()}")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
