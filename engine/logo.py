"""
Logo que sempre aparece: ajusta a logo ao fundo onde ela vai ficar.

Logos de site costumam ser claras (nome em branco) para o cabeçalho escuro. Sobre fundo claro o nome some e só sobra o símbolo colorido.
`fit(path, bg)` mede o contraste dos pixels opacos contra o fundo; se a maior parte estiver ilegível, recolore só os pixels neutros
(branco/cinza/preto) para a tinta certa (escura sobre fundo claro, branca sobre escuro) e mantém os pixels coloridos (o símbolo).
Gera um arquivo novo em cache; o original nunca é alterado.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np
from PIL import Image

CACHE = Path(__file__).resolve().parent.parent / ".cache" / "logos"


def _lum(rgb: np.ndarray) -> np.ndarray:
    v = rgb / 255.0
    v = np.where(v <= 0.03928, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2]


def _hex(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _open(path) -> Image.Image:
    im = Image.open(path)
    return im.convert("RGBA")


def _bg_to_alpha(im: Image.Image) -> Image.Image:
    """Logo opaca (print do elemento): o fundo liso das bordas vira transparente."""
    a = np.asarray(im).astype(np.float32)
    if (a[..., 3] < 250).mean() > 0.02:
        return im
    edge = np.concatenate([a[0, :, :3], a[-1, :, :3], a[:, 0, :3], a[:, -1, :3]])
    med = np.median(edge, axis=0)
    if edge.std(axis=0).max() > 14:
        return im
    d = np.abs(a[..., :3] - med).max(axis=-1)
    a[..., 3] = np.clip((d - 8) / 40, 0, 1) * 255
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def analyze(path, bg: str) -> dict:
    """Quanto da logo é legível sobre `bg` (fração dos pixels opacos com contraste ≥ 3:1)."""
    im = _bg_to_alpha(_open(path))
    a = np.asarray(im).astype(np.float32)
    m = a[..., 3] > 128
    if m.sum() < 20:
        return dict(ok=False, readable=0.0, opaque=int(m.sum()), reason="logo vazia")
    lb = float(_lum(_hex(bg)[None, None, :])[0, 0])
    lt = _lum(a[..., :3])[m]
    ratio = (np.maximum(lt, lb) + .05) / (np.minimum(lt, lb) + .05)
    readable = float((ratio >= 3.0).mean())
    return dict(ok=readable >= .8, readable=round(readable, 2), opaque=int(m.sum()))


def fit(path, bg: str, ink: str = "#111111", paper: str = "#FFFFFF") -> str:
    """Devolve o caminho de uma versão da logo legível sobre `bg` (o próprio arquivo se já for legível)."""
    path = str(path).replace("file://", "")
    info = analyze(path, bg)
    if info.get("ok"):
        return path
    im = _bg_to_alpha(_open(path))
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3]
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    neutral = (mx - mn) < 40
    dark_bg = float(_lum(_hex(bg)[None, None, :])[0, 0]) < 0.35
    target = _hex(paper if dark_bg else ink)
    lb = float(_lum(_hex(bg)[None, None, :])[0, 0])
    lt = _lum(rgb)
    bad = ((np.maximum(lt, lb) + .05) / (np.minimum(lt, lb) + .05)) < 3.0
    sel = neutral & bad & (al > 0)
    out = rgb.copy()
    out[sel] = target
    res = np.dstack([out, al]).astype(np.uint8)
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5((path + bg + ink + paper + str(Path(path).stat().st_mtime)).encode()).hexdigest()[:10]
    dst = CACHE / f"{Path(path).stem}_{key}.png"
    Image.fromarray(res, "RGBA").save(dst)
    return str(dst)


def avatar(path, dst, bg: str, ink: str = "#111111", size: int = 512, pad: float = 0.16) -> str:
    """Quadrado para avatar: usa o símbolo (a parte à esquerda) quando a logo é horizontal; ajustado ao fundo."""
    fitted = fit(path, bg, ink)
    im = _open(fitted)
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    w, h = im.size
    if w > h * 1.6:  # logo horizontal: o símbolo costuma ser o primeiro bloco colorido/conectado à esquerda
        a = np.asarray(im)[..., 3] > 40
        cols = a.any(axis=0)
        gap = None
        run = 0
        for x in range(int(h * .4), w):
            run = run + 1 if not cols[x] else 0
            if run >= max(3, int(h * .08)):
                gap = x - run
                break
        if gap and gap > h * .5:
            im = im.crop((0, 0, gap, h))
    s = int(size * (1 - 2 * pad))
    im.thumbnail((s, s), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)
    return str(dst)
