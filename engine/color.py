"""
Estudo de cor: contraste WCAG, harmonias, paleta a partir de foto, e geração de tema acessível.
Regras aplicadas: contraste de texto >= 4.5:1 (corpo) / 3:1 (texto grande >= 24px); proporção 60-30-10;
acento sempre com saturação alta e não competir com o fundo.
"""
from __future__ import annotations

import colorsys
from pathlib import Path


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_hex(r, g, b) -> str:
    return "#%02x%02x%02x" % (max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b))))


def luminance(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hsl(h: str):
    r, g, b = (v / 255 for v in hex_rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, s, l


def from_hsl(hh, s, l) -> str:
    r, g, b = colorsys.hls_to_rgb((hh % 360) / 360, max(0, min(1, l)), max(0, min(1, s)))
    return rgb_hex(r * 255, g * 255, b * 255)


def on_color(bg: str, light="#ffffff", dark="#111111") -> str:
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def ensure_contrast(fg: str, bg: str, ratio: float = 4.5) -> str:
    """Ajusta a luminosidade de `fg` (mantendo o matiz) até atingir o contraste mínimo contra `bg`."""
    if contrast(fg, bg) >= ratio:
        return fg
    h, s, l = hsl(fg)
    go_light = luminance(bg) < 0.5
    for _ in range(60):
        l += 0.02 if go_light else -0.02
        c = from_hsl(h, s, l)
        if contrast(c, bg) >= ratio:
            return c
    return "#ffffff" if go_light else "#111111"


def harmony(seed: str, scheme: str = "analogous") -> list[str]:
    h, s, l = hsl(seed)
    off = {"complementary": [0, 180], "analogous": [-30, 0, 30], "triadic": [0, 120, 240],
           "split": [0, 150, 210], "tetradic": [0, 90, 180, 270], "mono": [0, 0, 0]}[scheme]
    if scheme == "mono":
        return [from_hsl(h, s, x) for x in (max(.12, l - .3), l, min(.92, l + .3))]
    return [from_hsl(h + o, s, l) for o in off]


SCHEMES = ["complementary", "analogous", "triadic", "split", "tetradic", "mono"]


def palette_from_image(path: str | Path, n: int = 6) -> list[dict]:
    """Cores dominantes [{hex, share, sat, light}] ordenadas por participação."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((200, 200))
    q = im.quantize(colors=max(n, 8), method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, idx in counts[:n * 2]:
        r, g, b = pal[idx * 3:idx * 3 + 3]
        hx = rgb_hex(r, g, b)
        h, s, l = hsl(hx)
        out.append(dict(hex=hx, share=round(c / total, 3), sat=round(s, 2), light=round(l, 2)))
    # funde cores quase iguais
    merged = []
    for c in out:
        for m in merged:
            if sum(abs(a - b) for a, b in zip(hex_rgb(c["hex"]), hex_rgb(m["hex"]))) < 40:
                m["share"] = round(m["share"] + c["share"], 3)
                break
        else:
            merged.append(c)
    return sorted(merged, key=lambda d: -d["share"])[:n]


def theme_from_palette(pal: list[dict], mode: str = "auto") -> dict:
    """Monta cores de marca (bg, bg2, fg, accent, accent2) legíveis a partir de uma paleta de foto."""
    dom = pal[0]["hex"]
    sat = sorted(pal, key=lambda d: -(d["sat"] * (1 - abs(d["light"] - .5))))
    accent = sat[0]["hex"]
    h, s, l = hsl(accent)
    accent = from_hsl(h, max(s, .6), min(max(l, .45), .62))
    if mode == "auto":
        mode = "dark" if luminance(dom) < .35 else "light"
    hd, sd, ld = hsl(dom)
    if mode == "dark":
        bg, bg2, fg = from_hsl(hd, min(sd, .45), .08), from_hsl(hd, min(sd, .4), .15), "#f6f4ef"
    else:
        bg, bg2, fg = from_hsl(hd, min(sd, .25), .96), from_hsl(hd, min(sd, .3), .90), "#141414"
    accent = ensure_contrast(accent, bg, 3.0)
    cands = [p["hex"] for p in sat[1:] if p["sat"] > .25 and contrast(p["hex"], bg) >= 3.0 and p["hex"] != accent]
    accent2 = cands[0] if cands else ensure_contrast(harmony(accent, "split")[1], bg, 3.0)
    return dict(bg=bg, bg2=bg2, fg=fg, accent=accent, accent2=accent2, mode=mode)


def report(colors: dict) -> list[str]:
    """Checagens de contraste de um conjunto de cores de tema."""
    msgs = []
    bg, fg, ac = colors.get("bg"), colors.get("fg"), colors.get("accent")
    if bg and fg:
        c = contrast(fg, bg)
        msgs.append(f"texto/fundo {c:.1f}:1 " + ("✓" if c >= 4.5 else "✗ (<4.5)"))
    if bg and ac:
        c = contrast(ac, bg)
        msgs.append(f"acento/fundo {c:.1f}:1 " + ("✓" if c >= 3 else "✗ (<3, só decoração)"))
    if ac:
        on = on_color(ac)
        msgs.append(f"texto sobre acento {contrast(on, ac):.1f}:1 ({on})")
    return msgs
