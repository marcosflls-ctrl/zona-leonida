import math
from playwright.sync_api import sync_playwright

def fronda(x0, y0, ang, largo, curva, n=16, hoja=0.42, grosor=1.0):
    """Hoja de palmera: un nervio curvo con foliolos triangulares a ambos lados."""
    pts = []
    cx, cy = x0 + math.cos(ang)*largo*0.5 - math.sin(ang)*curva, y0 + math.sin(ang)*largo*0.5 + math.cos(ang)*curva
    x1, y1 = x0 + math.cos(ang)*largo, y0 + math.sin(ang)*largo
    def p(t):
        return ((1-t)**2*x0 + 2*(1-t)*t*cx + t*t*x1, (1-t)**2*y0 + 2*(1-t)*t*cy + t*t*y1)
    def d(t):
        dx = 2*(1-t)*(cx-x0) + 2*t*(x1-cx); dy = 2*(1-t)*(cy-y0) + 2*t*(y1-cy)
        L = math.hypot(dx, dy) or 1; return dx/L, dy/L
    paths = []
    for i in range(1, n):
        t = i/n
        bx, by = p(t); tx, ty = d(t)
        L = largo*hoja*math.sin(math.pi*min(1, t*1.15))*grosor
        for s in (1, -1):
            nx, ny = -ty*s, tx*s
            # foliolo inclinado hacia la punta
            px, py = bx + (nx*0.8 + tx*0.6)*L, by + (ny*0.8 + ty*0.6)*L
            b2x, b2y = p(min(1, t + 1/n*1.1))
            paths.append(f"M{bx:.1f},{by:.1f} L{px:.1f},{py:.1f} L{b2x:.1f},{b2y:.1f} Z")
    # nervio
    paths.append(f"M{x0:.1f},{y0:.1f} Q{cx:.1f},{cy:.1f} {x1:.1f},{y1:.1f}")
    return " ".join(paths)

def palmeras(col):
    fr = [
        (1180, -40, math.radians(160), 620, -90, 1.0), (1180, -40, math.radians(195), 560, 80, 0.9),
        (1150, 120, math.radians(215), 520, 60, 0.85), (1120, 380, math.radians(230), 420, 40, 0.7),
        (-120, 1180, math.radians(-20), 640, -80, 1.0), (-120, 1180, math.radians(-50), 560, 70, 0.9),
        (-80, 980, math.radians(-5), 520, -60, 0.85),
    ]
    out = ""
    for x, y, a, l, c, g in fr:
        out += f'<path d="{fronda(x, y, a, l, c, grosor=g)}" fill="{col}" stroke="{col}" stroke-width="5" stroke-linejoin="round"/>'
    return out

HOJA = "M0,0 C30,-60 110,-90 170,-80 C120,-60 70,-30 0,0 Z M8,-2 C40,-40 90,-62 150,-72"  # no se usa
def estrella(cx, cy, r):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r*0.42
        a = -math.pi/2 + i*math.pi/5
        pts.append(f"{cx+rr*math.cos(a):.1f},{cy+rr*math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="none" stroke="#fff" stroke-width="20" stroke-linejoin="miter" filter="url(#brillo)"/>'

def hoja_palmera(cx, cy, s):
    # pequeña hoja de palmera neón (verde menta) como la del logo actual
    return f'<g transform="translate({cx},{cy}) rotate(-35) scale({s})" filter="url(#brillo2)"><path d="{fronda(0,0,0,230,-30,n=11,hoja=0.36)}" fill="#7dffb0" stroke="#7dffb0" stroke-width="4" stroke-linejoin="round"/></g>'

def svg(adorno):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">
<defs>
 <linearGradient id="fondo" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#1f3fd6"/><stop offset=".45" stop-color="#7a4ad8"/><stop offset="1" stop-color="#ff4fa6"/>
 </linearGradient>
 <filter id="brillo" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14" result="b"/>
  <feFlood flood-color="#ffffff" flood-opacity=".75"/><feComposite in2="b" operator="in" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="brillo2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10" result="b"/>
  <feFlood flood-color="#7dffb0" flood-opacity=".9"/><feComposite in2="b" operator="in" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="1080" height="1080" fill="url(#fondo)"/>
<g opacity=".38">{palmeras("#3b1e8f")}</g>
<text x="530" y="690" text-anchor="middle" font-family="Inter" font-weight="900" font-style="italic" font-size="430" letter-spacing="-18" fill="#fff" filter="url(#brillo)">ZL</text>
{adorno}
</svg>'''

variantes = {"logo-hoja": hoja_palmera(790, 400, 1.15), "logo-estrella": estrella(830, 720, 130)}
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width":1080,"height":1080})
    for n, a in variantes.items():
        open(f"{n}.svg","w").write(svg(a))
        pg.set_content(f"<html><body style='margin:0'>{svg(a)}</body></html>"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{n}.png")
    b.close()
