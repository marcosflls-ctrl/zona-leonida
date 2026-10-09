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
    if path.stem.endswith(tuple(f"-{s}" for s in SIZES)):
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


def main(paths=None) -> None:
    files = [pathlib.Path(p) for p in paths] if paths else [
        f for d in DIRS for f in sorted((ROOT / "public" / "img" / d).glob("*.webp"))]
    total = sum(make_variants(f) for f in files)
    print(f"Miniaturas nuevas: {total}")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
