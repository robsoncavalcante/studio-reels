"""
Legendas por palavra (estilo Reels/TikTok) com tempo ajustado à locução, sem depender de serviço externo.

- Tempo: distribui as palavras do roteiro nos trechos de fala detectados na voz (ffmpeg silencedetect) proporcionalmente
  ao tamanho de cada palavra; pausas de pontuação ganham peso extra. Sem voz, distribui no tempo total informado.
  (Para sincronia palavra a palavra exata de uma gravação humana, rode um alinhador externo e passe o .json em `words`.)
- Saída: .ass (queimado pelo ffmpeg com as fontes da marca) e .srt (para importar no Premiere/After Effects/CapCut).
- Estilos: karaoke (palavra ativa em destaque + pulo), pop (palavras aparecem uma a uma), box (caixa atrás da frase), clean.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "ttf"
STYLES = {
    "karaoke": "frase inteira; palavra ativa na cor de destaque com pulinho; as próximas ficam apagadas",
    "pop": "palavras surgem uma a uma com pulinho (estilo trend)",
    "box": "frase dentro de uma caixa escura arredondada; palavra ativa na cor de destaque",
    "clean": "frase inteira com entrada/saída suaves, sem destaque por palavra (institucional)",
}


# ------------------------------------------------------------------ tempo das palavras
def speech_runs(audio: str, total: float | None = None) -> list[tuple[float, float]]:
    """Trechos com fala (complemento dos silêncios) em segundos."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "silencedetect=noise=-38dB:d=0.22", "-f", "null", "-"],
                       capture_output=True, text=True)
    dur = _dur(audio) or total or 0.0
    sil, cur = [], None
    for ln in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", ln)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", ln)
        if m and cur is not None:
            sil.append((cur, float(m.group(1))))
            cur = None
    if cur is not None:
        sil.append((cur, dur))
    runs, t = [], 0.0
    for a, b in sil:
        if a - t > .12:
            runs.append((t, a))
        t = b
    if dur - t > .12:
        runs.append((t, dur))
    return runs or [(0.0, dur)]


def _dur(path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _weight(w: str) -> float:
    base = max(2, len(re.sub(r"\W", "", w))) + .6
    if re.search(r"[.!?…]$", w):
        base += 3.0
    elif re.search(r"[,;:]$", w):
        base += 1.6
    return base


def align(text: str, audio: str | None = None, total: float | None = None, offset: float = 0.0) -> list[dict]:
    """[{w, t0, t1}] — tempos em segundos desde o início do vídeo."""
    words = text.split()
    if not words:
        return []
    runs = speech_runs(audio, total) if audio else [(0.0, total or max(2.0, len(words) * .38))]
    wts = [_weight(w) for w in words]
    run_len = [b - a for a, b in runs]
    tot_len = sum(run_len)
    tot_w = sum(wts)
    out, idx = [], 0
    for k, (a, b) in enumerate(runs):
        share = tot_w * (run_len[k] / tot_len)
        acc, grp = 0.0, []
        while idx < len(words) and (acc < share * .98 or k == len(runs) - 1 or not grp):
            grp.append(idx)
            acc += wts[idx]
            idx += 1
            if k < len(runs) - 1 and acc >= share * .98:
                break
        gw = sum(wts[i] for i in grp) or 1
        t = a
        for i in grp:
            d = (b - a) * wts[i] / gw
            out.append(dict(w=words[i], t0=round(offset + t, 3), t1=round(offset + t + d, 3)))
            t += d
    while idx < len(words):  # sobras
        last = out[-1]["t1"] if out else offset
        out.append(dict(w=words[idx], t0=last, t1=round(last + .3, 3)))
        idx += 1
    return out


def chunks(words: list[dict], max_words=4, max_chars=26) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        n = len(" ".join(x["w"] for x in cur))
        if len(cur) >= max_words or n >= max_chars or re.search(r"[.!?…]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


# ------------------------------------------------------------------ fontes (woff2 -> ttf para o libass)
def ttf_for(family_slug: str, weight: int = 700) -> tuple[Path, str]:
    """Converte a fonte da marca (woff2 do Fontsource) em TTF e devolve (pasta, nome da família)."""
    from fontTools.ttLib import TTFont
    src = ROOT / "fonts" / f"{family_slug}-latin-{weight}-normal.woff2"
    if not src.exists():
        cands = sorted((ROOT / "fonts").glob(f"{family_slug}-latin-*-normal.woff2"))
        if not cands:
            cands = sorted((ROOT / "fonts").glob("space-grotesk-latin-*-normal.woff2"))
        src = cands[-1]
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / (src.stem + ".ttf")
    f = TTFont(str(src))
    fam = f["name"].getDebugName(1) or family_slug
    if not dst.exists():
        f.flavor = None
        f.save(str(dst))
    return CACHE, fam


# ------------------------------------------------------------------ ASS / SRT
def _c(hexcolor: str, alpha: int = 0) -> str:
    h = hexcolor.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper().replace("&H", "&H", 1)


def _ts(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_ass(words: list[dict], out: Path, *, style="karaoke", W=1080, H=1920, font_slug="space-grotesk", weight=700, accent="#FB2C36",
              fg="#FFFFFF", pos_y=.74, size=None, upper=False, max_words=4) -> tuple[Path, Path]:
    fontsdir, fam = ttf_for(font_slug, weight)
    size = size or int(W * .078)
    fg_, ac_, dim_ = _c(fg), _c(accent), _c(fg, 0x90)
    box = style == "box"
    out = Path(out)
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
             "[V4+ Styles]",
             "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
             f"Style: Cap,{fam},{size},{fg_},{fg_},{_c('#000000', 0x10) if not box else _c('#0C090C', 0x28)},{_c('#000000', 0x80)},"
             f"{-1 if weight >= 600 else 0},0,0,0,100,100,0,0,{3 if box else 1},{int(size * .22) if box else int(size * .12)},{0 if box else int(size * .05)},5,60,60,0,1",
             "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
    pos = f"{{\\an5\\pos({W // 2},{int(H * pos_y)})"
    ev = []
    chs = chunks(words, max_words=max_words)
    for ci, ch in enumerate(chs):
        txt = [(w["w"].upper() if upper else w["w"]) for w in ch]
        c0, c1 = ch[0]["t0"], ch[-1]["t1"] + .12
        if ci + 1 < len(chs):
            c1 = min(c1, chs[ci + 1][0]["t0"])  # nunca sobrepor a frase seguinte
        if style == "clean":
            ev.append((c0, c1, pos + "\\fad(160,140)}" + " ".join(txt)))
            continue
        for k, w in enumerate(ch):
            a = w["t0"] if k else c0
            b = ch[k + 1]["t0"] if k + 1 < len(ch) else c1
            if style == "pop":
                shown = " ".join(txt[:k + 1])
                prefix = " ".join(txt[:k])
                body = (prefix + " " if prefix else "") + f"{{\\1c{ac_}\\fscx118\\fscy118\\t(0,140,\\fscx100\\fscy100\\1c{fg_})}}{txt[k]}"
                ev.append((a, b, pos + "}" + body))
                continue
            parts = []
            for j, t_ in enumerate(txt):
                if j < k:
                    parts.append(f"{{\\1c{fg_}}}{t_}")
                elif j == k:
                    parts.append(f"{{\\1c{ac_}\\fscx116\\fscy116\\t(0,130,\\fscx100\\fscy100)}}{t_}{{\\fscx100\\fscy100}}")
                else:
                    parts.append(f"{{\\1c{dim_}}}{t_}")
            ev.append((a, b, pos + "}" + " ".join(parts)))
    for a, b, t in ev:
        lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{t}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    srt = out.with_suffix(".srt")
    n = []
    for i, ch in enumerate(chunks(words, max_words=7, max_chars=42), 1):
        def st(t):
            return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round((t % 1) * 1000)):03d}"
        n.append(f"{i}\n{st(ch[0]['t0'])} --> {st(ch[-1]['t1'] + .1)}\n{' '.join(w['w'] for w in ch)}\n")
    srt.write_text("\n".join(n), encoding="utf-8")
    out.with_suffix(".words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, fontsdir
