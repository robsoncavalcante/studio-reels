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
import shutil
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


def chunks(words: list[dict], max_words=5, max_chars=40) -> list[list[dict]]:
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


def _brk(txt: list[str], line_chars: int = 20) -> int:
    """Índice da palavra que abre a 2ª linha (-1 = linha única). Linhas curtas (~20 caracteres), quebra no meio."""
    if len(" ".join(txt)) <= line_chars or len(txt) < 2:
        return -1
    best, bi = 10**9, -1
    for i in range(1, len(txt)):
        d = abs(len(" ".join(txt[:i])) - len(" ".join(txt[i:])))
        if d < best:
            best, bi = d, i
    return bi


def _join(parts: list[str], brk: int) -> str:
    return " ".join(parts[:brk]) + "\\N" + " ".join(parts[brk:]) if brk > 0 else " ".join(parts)


# ------------------------------------------------------------------ transcrição real e import (v4.3)
def transcribe(audio, lang="pt", model="small", out=None) -> list[dict]:
    """Transcreve com tempos reais por palavra. Tenta, na ordem: faster-whisper, openai-whisper (módulo `whisper`) e o comando
    `whisper` do terminal. Precisa de internet só na 1ª vez (baixa o modelo). Alternativa: importe um SRT/JSON com --words."""
    words, erros = None, []
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(model, device="cpu", compute_type="int8")
        seg, _ = m.transcribe(str(audio), language=lang, word_timestamps=True, vad_filter=True)
        words = [dict(w=w.word.strip(), t0=round(w.start, 3), t1=round(w.end, 3)) for s in seg for w in s.words if w.word.strip()]
    except ImportError:
        pass
    except Exception as e:
        erros.append(f"faster-whisper: {type(e).__name__}")
    if words is None:
        try:
            import whisper  # openai-whisper
            m = whisper.load_model(model)
            r = m.transcribe(str(audio), language=lang, word_timestamps=True, fp16=False)
            words = _words_from_segments(r.get("segments", []))
        except ImportError:
            pass
        except Exception as e:
            erros.append(f"openai-whisper: {type(e).__name__}")
    if words is None and shutil.which("whisper"):
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(["whisper", str(audio), "--model", model, "--language", lang, "--word_timestamps", "True",
                                "--output_format", "json", "--output_dir", td, "--fp16", "False"], capture_output=True, text=True)
            js = next(Path(td).glob("*.json"), None)
            if r.returncode == 0 and js:
                words = _words_from_segments(json.loads(js.read_text(encoding="utf-8")).get("segments", []))
            else:
                erros.append("whisper (terminal): " + (r.stderr or "")[-120:].strip())
    if not words:
        det = ("; ".join(erros)) if erros else "nenhum Whisper encontrado (pip install faster-whisper, ou openai-whisper)"
        raise SystemExit(f"Transcrição falhou: {det}. Importe um SRT/JSON com --words arquivo.")
    if out:
        Path(out).write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    return words


def _words_from_segments(segs) -> list[dict]:
    return [dict(w=(w.get("word") or "").strip(), t0=round(w["start"], 3), t1=round(w["end"], 3))
            for sg in segs for w in sg.get("words", []) if (w.get("word") or "").strip()]


def _srt_time(x: str) -> float:
    h, m, s = x.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def from_file(path, offset: float = 0.0) -> list[dict]:
    """Palavras com tempo a partir de: JSON do motor/Whisper ([{w,t0,t1}] ou {segments:[{words:[{word,start,end}]}]}) ou SRT
    (as palavras de cada legenda são distribuídas pelo tempo da legenda, ponderadas pelo tamanho)."""
    p = Path(path)
    txt = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        d = json.loads(txt)
        if isinstance(d, dict):
            d = [w for s in d.get("segments", []) for w in s.get("words", [])] or d.get("words", [])
        out = []
        for w in d:
            if "t0" in w:
                out.append(dict(w=w["w"], t0=w["t0"] + offset, t1=w["t1"] + offset))
            else:
                out.append(dict(w=(w.get("word") or w.get("text", "")).strip(), t0=w["start"] + offset, t1=w["end"] + offset))
        return [w for w in out if w["w"]]
    words = []
    for blk in re.split(r"\n\s*\n", txt.strip()):
        ln = [x for x in blk.strip().splitlines() if x.strip()]
        tm = next((x for x in ln if "-->" in x), None)
        if not tm:
            continue
        a, b = [_srt_time(x.strip().split(" ")[0]) for x in tm.split("-->")]
        toks = " ".join(ln[ln.index(tm) + 1:]).split()
        if not toks:
            continue
        wt = [len(t) + (4 if re.search(r"[.,;:!?…]$", t) else 0) + 1 for t in toks]
        tot, cur = sum(wt), a + offset
        for t, x in zip(toks, wt):
            d = (b - a) * x / tot
            words.append(dict(w=t, t0=round(cur, 3), t1=round(cur + d, 3)))
            cur += d
    return words


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
              fg="#FFFFFF", pos_y=.64, size=None, upper=False, max_words=5) -> tuple[Path, Path]:
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
        brk = _brk(txt)
        c0, c1 = ch[0]["t0"], ch[-1]["t1"] + .12
        if ci + 1 < len(chs):
            c1 = min(c1, chs[ci + 1][0]["t0"])  # nunca sobrepor a frase seguinte
        if style == "clean":
            ev.append((c0, c1, pos + "\\fad(160,140)}" + _join(txt, brk)))
            continue
        for k, w in enumerate(ch):
            a = w["t0"] if k else c0
            b = ch[k + 1]["t0"] if k + 1 < len(ch) else c1
            if style == "pop":
                shown = " ".join(txt[:k + 1])
                cur = f"{{\\1c{ac_}\\fscx118\\fscy118\\t(0,140,\\fscx100\\fscy100\\1c{fg_})}}{txt[k]}"
                body = _join(txt[:k] + [cur], brk if brk <= k else -1)
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
            ev.append((a, b, pos + "}" + _join(parts, brk)))
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
