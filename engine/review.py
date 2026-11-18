"""
Revisão de reels (ideias de método inspiradas no fluxo de revisão do HyperFrames, Apache-2.0; implementação própria).

1) folhas de contato: cenas (início + meio), faixa em volta de cada corte (-0.2 … +0.2 s) e quadros em 360 px (leitura no celular)
2) checagens medidas: leitura mínima por cena, trecho parado (> 3 s sem mudança), primeiro quadro preto, última cena curta
3) notas P0/P1/P2 em uma linha  «t=4.2s · onde · problema → mudança exata · o que fica»  e o REVIEW.md
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import core

PHONE_W = 360
DEAD_SECONDS = 3.0
SKIP_KEYS = {"photos", "photo", "image", "images", "logo", "src", "url", "bg", "color", "accent", "icon", "avatar", "video", "clips"}


def count_words(content) -> int:
    """Palavras visíveis de um content.json de cena (ignora caminhos, cores e mídia)."""
    if isinstance(content, str):
        s = content.strip()
        if not s or s.startswith(("#", "http", "/")) or "." in s.split()[0][-5:] and " " not in s:
            return 0
        return len(s.replace("*", "").split())
    if isinstance(content, dict):
        return sum(count_words(v) for k, v in content.items() if k not in SKIP_KEYS)
    if isinstance(content, (list, tuple)):
        return sum(count_words(v) for v in content)
    return 0


def need_seconds(words: int) -> float:
    """Tempo de leitura: 1–2 palavras = 0.4 s; depois 0.5 s + 0.3 s por palavra."""
    return 0.4 if words <= 2 else 0.5 + 0.3 * words


# ------------------------------------------------------------------ quadros
def _frame(video: str, t: float, width: int | None = None) -> Image.Image:
    cmd = [core._ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1"]
    if width:
        cmd += ["-vf", f"scale={width}:-2"]
    cmd += ["-f", "image2pipe", "-vcodec", "png", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout:
        return Image.new("RGB", (width or 320, int((width or 320) * 16 / 9)), (40, 40, 40))
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def _grid(tiles: list[tuple[Image.Image, str]], cols: int, pad=8, label_h=18) -> Image.Image:
    if not tiles:
        return Image.new("RGB", (10, 10), (20, 20, 20))
    tw, th = tiles[0][0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + label_h + pad) + pad), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(tiles):
        x, y = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + label_h + pad)
        sheet.paste(im.resize((tw, th)), (x, y + label_h))
        d.text((x + 2, y + 2), lab, fill=(235, 235, 235))
    return sheet


def sheets(video: str, tl: dict, outdir: Path) -> dict:
    """Gera sheet_cenas.png, sheet_cortes.png e sheet_celular.png."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    total = tl["total"]
    tw = 200
    cenas, cel = [], []
    for s in tl["scenes"]:
        a, b = s["start"], s["start"] + s["dur"]
        for tag, t in (("início", min(a + .35, b - .05)), ("meio", (a + b) / 2)):
            cenas.append((_frame(video, min(t, total - .05), tw), f"cena {s['i'] + 1} {tag} {t:.1f}s"))
        cel.append((_frame(video, min((a + b) / 2, total - .05), PHONE_W), f"cena {s['i'] + 1} · {PHONE_W}px"))
    out = {}
    p = outdir / "sheet_cenas.png"
    _grid(cenas, 6).save(p)
    out["cenas"] = str(p)
    p = outdir / "sheet_celular.png"
    _grid(cel, 4).save(p)
    out["celular"] = str(p)
    # faixa de corte: -0.2 -0.1 0 +0.1 +0.2 em cada emenda
    rows = []
    for tr in tl["transitions"]:
        t0 = tr["at"]
        strip = [(_frame(video, min(max(t0 + dt, 0), total - .05), 130), f"{dt:+.1f}s") for dt in (-.2, -.1, 0, .1, .2)]
        rows.append((_grid(strip, 5, pad=4, label_h=14), f"{tr.get('type', '')} @ {t0:.1f}s"))
    if rows:
        w = max(r[0].width for r in rows)
        h = sum(r[0].height + 16 for r in rows)
        sh = Image.new("RGB", (w, h), (24, 24, 28))
        d, y = ImageDraw.Draw(sh), 0
        for im, lab in rows:
            d.text((4, y + 2), lab, fill=(255, 220, 120))
            sh.paste(im, (0, y + 16))
            y += im.height + 16
        p = outdir / "sheet_cortes.png"
        sh.save(p)
        out["cortes"] = str(p)
    return out


# ------------------------------------------------------------------ medições
def activity(video: str, fps: int = 6, size=(48, 84)) -> tuple[np.ndarray, np.ndarray]:
    """Mudança média entre quadros consecutivos (0–255) a `fps` quadros/s, e o 1º quadro em cinza."""
    w, h = size
    r = subprocess.run([core._ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    n = len(r.stdout) // (w * h)
    if n < 2:
        return np.zeros(0), np.zeros((h, w))
    a = np.frombuffer(r.stdout[: n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.int16)
    return np.abs(np.diff(a, axis=0)).mean(axis=(1, 2)), a[0]


def measure(tl: dict, video: str | None) -> list[dict]:
    """Problemas medidos. Cada item: level (blocker/warn/info), code, t, where, msg, fix, keep."""
    out = []

    def add(level, code, t, where, msg, fix, keep="o restante da cena"):
        out.append(dict(level=level, code=code, t=round(t, 2), where=where, msg=msg, fix=fix, keep=keep, box=None, text=None))

    sc = tl["scenes"]
    for s in sc:
        if "words" not in s:
            continue
        need = need_seconds(s["words"])
        if s["dur"] < need * 0.85:
            add("warn", "line_unread", s["start"], f"cena {s['i'] + 1}", f"{s['words']} palavras em {s['dur']:.1f}s: leitura pede ≈{need:.1f}s",
                f"cena para {need:.1f}s ou cortar para {max(1, int((s['dur'] - .5) / .3))} palavras", "layout e movimento")
    if sc:
        last = sc[-1]
        if last["dur"] < 2.0 and last.get("words", 3) > 2:
            add("warn", "last_short", last["start"], f"cena {last['i'] + 1}", f"última cena com {last['dur']:.1f}s: o fechamento (CTA) some antes de ser lido",
                "última cena ≥ 2.0s", "texto do CTA")
    if video and Path(video).exists():
        act, first = activity(video)
        if first.size and first.mean() < 6 and first.std() < 3:
            add("warn", "first_frame_black", 0, "quadro 0", "o primeiro quadro é preto: a miniatura e o gancho nascem vazios", "começar já com título, rosto ou resultado", "a entrada do movimento")
        thr, fps, run0 = 0.25, 6, None
        for i, v in enumerate(list(act) + [99.0]):
            if v < thr and run0 is None:
                run0 = i
            elif v >= thr and run0 is not None:
                a, b = run0 / fps, i / fps
                if b - a > DEAD_SECONDS:
                    add("warn", "dead_stretch", a, f"{a:.1f}–{b:.1f}s", f"{b - a:.1f}s sem mudança visual", "trocar o plano, acrescentar movimento ou cortar o trecho", "o áudio e a legenda")
                run0 = None
    return out


# ------------------------------------------------------------------ notas
PRIO = {"blocker": "P0", "warn": "P1", "info": "P2"}


def note(i: dict) -> str:
    t = f"t={i['t']:.1f}s" if i.get("t") is not None else "t=—"
    where = i.get("where") or "peça"
    return f"{PRIO[i['level']]} · {t} · {where} · {i['msg']} → {i.get('fix') or 'rever'} · fica: {i.get('keep') or 'o restante'}"


def write_review(rep: dict, outdir: Path, sheets_out: dict | None = None) -> Path:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    order = ["blocker", "warn", "info"]
    iss = sorted(rep["issues"], key=lambda x: order.index(x["level"]))
    lines = [f"# Revisão · {rep['name']}", "", f"{rep['blockers']} P0 · {rep['warnings']} P1 · {sum(i['level'] == 'info' for i in iss)} P2", "",
             "P0 quebra a leitura ou o contrato · P1 enfraquece a peça · P2 acabamento. Formato: prioridade · tempo · onde · problema → mudança · o que fica.", ""]
    lines += [f"- {note(i)}" for i in iss] or ["- Nenhum problema medido."]
    if sheets_out:
        lines += ["", "## Folhas de contato", *[f"- {k}: {Path(v).name}" for k, v in sheets_out.items()]]
    lines += ["", "## Olhar humano (o que a medição não pega)", "- Descreva cada quadro de beat em uma frase como um estranho: se precisa explicar um objeto, é P0.",
              "- O sujeito se separa do fundo? Há dois focos competindo?", "- Com as palavras cobertas, as imagens ainda contam a história?",
              "- Cada linha a ser lida se lê na folha de 360 px?", "- Há \"cara de gerado\"? (veja agents/motion-designer.md)"]
    p = outdir / "REVIEW.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
