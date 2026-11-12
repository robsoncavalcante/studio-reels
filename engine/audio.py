"""
Áudio 100% local e original (sem direitos autorais): trilhas sintetizadas + efeitos sonoros (SFX) + mix.
Nada é baixado nem copiado de bibliotecas; para música comercial use as fontes de library/audio_sources.json
(com a licença de cada uma) e passe o arquivo em --audio.

Estilos: lofi, house, pop, corporate, cinematic, hype, ambient   (BPM e tonalidade ajustáveis)
SFX:     whoosh, pop, click, riser, impact, shimmer, swipe, tick
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 44100
ROOT = Path(__file__).resolve().parent.parent

STYLES = {
    "lofi": dict(bpm=78, desc="beat suave com swing, acordes quentes, chiado de vinil", mood="calmo, lifestyle, café, bem-estar"),
    "house": dict(bpm=122, desc="bumbo na pulsação, hi-hat no contratempo, baixo pulsante", mood="moda, evento, festa, promoção"),
    "pop": dict(bpm=104, desc="bumbo/caixa limpos, arpejo brilhante", mood="geral, varejo, lançamento"),
    "corporate": dict(bpm=100, desc="pluck leve + pad, discreto e confiante", mood="negócios, institucional, serviços"),
    "cinematic": dict(bpm=84, desc="pad de cordas sintetizadas, subida e impacto", mood="luxo, imobiliário, storytelling"),
    "hype": dict(bpm=140, desc="808, hi-hats rápidos, energia máxima", mood="esporte, black friday, urgência"),
    "ambient": dict(bpm=70, desc="texturas longas e etéreas", mood="saúde, mindfulness, fundo discreto"),
}
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
PROGS = {  # graus em semitons sobre a tônica (tríades menores/maiores simples)
    "lofi": [(0, "m7"), (5, "m7"), (3, "maj7"), (7, "7")],
    "house": [(0, "m"), (8, "maj"), (3, "maj"), (10, "maj")],
    "pop": [(0, "maj"), (7, "maj"), (9, "m"), (5, "maj")],
    "corporate": [(0, "maj"), (5, "maj"), (9, "m"), (7, "maj")],
    "cinematic": [(0, "m"), (8, "maj"), (3, "maj"), (10, "maj")],
    "hype": [(0, "m"), (0, "m"), (8, "maj"), (7, "maj")],
    "ambient": [(0, "maj7"), (9, "m7"), (5, "maj7"), (7, "sus")],
}
CH = {"maj": [0, 4, 7], "m": [0, 3, 7], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11], "7": [0, 4, 7, 10], "sus": [0, 5, 7]}


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(n, a=.005, d=.1, s=.6, r=.1):
    a_, d_, r_ = int(a * SR), int(d * SR), int(r * SR)
    e = np.ones(n) * s
    a_ = min(a_, n)
    e[:a_] = np.linspace(0, 1, a_)
    dd = min(d_, max(0, n - a_))
    e[a_:a_ + dd] = np.linspace(1, s, dd)
    r_ = min(r_, n)
    e[n - r_:] *= np.linspace(1, 0, r_)
    return e


def _tone(freq, dur, wave_="saw", detune=0.0, amp=1.0, **env):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for dt in ([0] if not detune else [-detune, 0, detune]):
        f = freq * 2 ** (dt / 1200)
        ph = 2 * np.pi * f * t
        if wave_ == "saw":
            out += signal.sawtooth(ph)
        elif wave_ == "square":
            out += signal.square(ph)
        elif wave_ == "tri":
            out += signal.sawtooth(ph, .5)
        else:
            out += np.sin(ph)
    out /= (1 if not detune else 3)
    return out * _env(n, **env) * amp


def _lp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def _hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def _kick(vol=1.0, dur=.28):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) * vol


def _snare(vol=.7, dur=.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = _hp(np.random.randn(n), 1200) * np.exp(-t * 22)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28)
    return (noise * .8 + body * .5) * vol


def _hat(vol=.3, dur=.06, open_=False):
    d = .22 if open_ else dur
    n = int(d * SR)
    t = np.arange(n) / SR
    return _hp(np.random.randn(n), 7000, 3) * np.exp(-t * (14 if open_ else 70)) * vol


def _808(freq, dur=.5, vol=.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1 + .6 * np.exp(-t * 30))
    return np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 4.5) * vol


def _place(buf, snd, pos):
    i = int(pos * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(snd))
    buf[i:j] += snd[:j - i]


def _reverb(x, mix=.22, decay=.5):
    ir = np.random.randn(int(decay * SR)) * np.exp(-np.linspace(0, 7, int(decay * SR)))
    ir = _lp(ir, 5000)
    ir /= np.max(np.abs(ir))
    wet = signal.fftconvolve(x, ir)[:len(x)]
    wet /= (np.max(np.abs(wet)) + 1e-9) / (np.max(np.abs(x)) + 1e-9)
    return x * (1 - mix) + wet * mix


def music(style: str = "pop", dur: float = 30.0, bpm: float | None = None, key: str = "A", seed: int = 7) -> np.ndarray:
    """Retorna estéreo float32 (N,2) com `dur` segundos (já com fade de entrada/saída)."""
    if style not in STYLES:
        raise SystemExit(f"Estilo '{style}' não existe: {', '.join(STYLES)}")
    rng = np.random.default_rng(seed)
    np.random.seed(seed)
    bpm = float(bpm or STYLES[style]["bpm"])
    beat = 60.0 / bpm
    n = int((dur + 1.5) * SR)
    drums, bass, harm, lead = (np.zeros(n) for _ in range(4))
    root = 45 + NOTE[key]  # A2 ≈ 45
    prog = PROGS[style]
    bars = int((dur + 1.5) / (beat * 4)) + 1
    swing = .16 * beat if style == "lofi" else 0.0
    for bar in range(bars):
        t0 = bar * beat * 4
        deg, qual = prog[bar % len(prog)]
        chord = [root + 12 + deg + c for c in CH[qual]]
        # harmonia
        if style in ("cinematic", "ambient"):
            for m in chord:
                _place(harm, _tone(mtof(m), beat * 4.2, "saw", detune=9, amp=.10, a=.9 if style == "cinematic" else 1.5, d=.5, s=.7, r=1.0), t0)
            harm_lp = True
        elif style == "lofi":
            for k_, m in enumerate(chord):
                _place(harm, _tone(mtof(m), beat * 2.0, "sine", amp=.16, a=.01, d=.5, s=.3, r=.3), t0 + (0 if k_ % 2 else .02))
                _place(harm, _tone(mtof(m + 12), beat * 1.8, "tri", amp=.05, a=.01, d=.4, s=.2, r=.3), t0 + beat * 2 + .03)
        elif style in ("house", "hype"):
            for hit in (beat * .75, beat * 2.25):
                for m in chord:
                    _place(harm, _tone(mtof(m + 12), beat * .4, "saw", detune=7, amp=.07 if style == "house" else .05, a=.004, d=.1, s=.3, r=.1), t0 + hit)
        else:  # pop / corporate arpejo
            step = beat / 2
            for i in range(8):
                m = chord[i % len(chord)] + (12 if i % 4 >= 2 else 0) + 12
                _place(lead, _tone(mtof(m), step * 1.4, "tri" if style == "corporate" else "saw", amp=.11 if style == "pop" else .08, a=.004, d=.12, s=.25, r=.12), t0 + i * step)
            for m in chord:
                _place(harm, _tone(mtof(m), beat * 4, "sine", amp=.07, a=.3, d=.5, s=.8, r=.5), t0)
        # baixo
        b = root - 12 + deg
        if style in ("house", "pop", "corporate"):
            for i in range(8):
                _place(bass, _tone(mtof(b), beat * .45, "saw", amp=.5, a=.004, d=.1, s=.4, r=.08), t0 + i * beat / 2 + (beat / 4 if style == "house" else 0))
        elif style == "lofi":
            for pos in (0, beat * 1.5, beat * 2.5):
                _place(bass, _tone(mtof(b), beat * 1.0, "sine", amp=.7, a=.01, d=.3, s=.5, r=.2), t0 + pos)
        elif style == "hype":
            for pos in (0, beat * 1.5, beat * 2.75):
                _place(bass, _808(mtof(b), beat * 1.1), t0 + pos)
        elif style == "cinematic":
            _place(bass, _tone(mtof(b), beat * 4, "sine", amp=.8, a=.6, d=.5, s=.8, r=.8), t0)
        # bateria
        if style == "lofi":
            for q in range(4):
                if q in (0, 2):
                    _place(drums, _kick(.8), t0 + q * beat)
                if q in (1, 3):
                    _place(drums, _snare(.45), t0 + q * beat + .01)
                _place(drums, _hat(.18), t0 + q * beat + beat / 2 + swing)
        elif style == "house":
            for q in range(4):
                _place(drums, _kick(1.0), t0 + q * beat)
                _place(drums, _hat(.28, open_=True), t0 + q * beat + beat / 2)
                if q in (1, 3):
                    _place(drums, _snare(.5), t0 + q * beat)
        elif style == "pop":
            for q in range(4):
                if q in (0, 2):
                    _place(drums, _kick(.9), t0 + q * beat)
                if q in (1, 3):
                    _place(drums, _snare(.6), t0 + q * beat)
                _place(drums, _hat(.22), t0 + q * beat + beat / 2)
        elif style == "corporate":
            for q in (0, 2):
                _place(drums, _kick(.6), t0 + q * beat)
            for q in range(8):
                _place(drums, _hat(.12), t0 + q * beat / 2)
        elif style == "hype":
            for q in (0, 1.75, 2.5):
                _place(drums, _kick(1.0), t0 + q * beat)
            for q in (1, 3):
                _place(drums, _snare(.7), t0 + q * beat)
            for i in range(16):
                _place(drums, _hat(.2 + .1 * (i % 4 == 0), dur=.04), t0 + i * beat / 4)
        elif style == "cinematic":
            if bar % 2 == 0:
                _place(drums, _kick(.6, .5) * .8, t0)
    # filtragem / mix
    harm = _lp(harm, 2600 if style in ("cinematic", "ambient") else 4200)
    if style == "lofi":
        harm = _lp(harm, 2200)
        lead = _lp(lead, 2200)
    mix = drums * .95 + bass * .85 + harm * 1.0 + lead * 1.0
    if style in ("lofi", "ambient", "cinematic"):
        mix = _reverb(mix, .28, .8)
    else:
        mix = _reverb(mix, .12, .35)
    if style == "lofi":
        mix += _hp(np.random.randn(n), 3000) * .004 * (1 + .5 * np.sin(np.arange(n) / SR * 3))
    # sidechain leve (bumbo abaixa harmonia) em house/hype
    if style in ("house", "hype"):
        duck = np.ones(n)
        for bar in range(bars):
            for q in range(4):
                i = int((bar * 4 + q) * beat * SR)
                L = int(.18 * SR)
                if i + L < n:
                    duck[i:i + L] *= np.linspace(.45, 1, L)
        mix = (harm * duck * 1.0 + lead * duck + bass * .85 + drums * .95)
    mix = mix[:int(dur * SR)]
    # estéreo sutil
    L = mix + np.roll(mix, int(.0007 * SR)) * .08
    R = mix + np.roll(mix, -int(.0007 * SR)) * .08
    st = np.stack([L, R], 1)
    st = _fades(st, 1.2 if style in ("ambient", "cinematic") else .4, 1.8)
    return _norm(st, .8).astype(np.float32)


def _fades(st, fi, fo):
    n = len(st)
    a, b = min(int(fi * SR), n), min(int(fo * SR), n)
    st = st.copy()
    st[:a] *= np.linspace(0, 1, a)[:, None]
    st[n - b:] *= np.linspace(1, 0, b)[:, None]
    return st


def _norm(x, peak=.9):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


# ---------------------------------------------------------------- SFX
def sfx(kind: str, vol: float = 1.0) -> np.ndarray:
    """Efeitos curtos (mono → estéreo)."""
    np.random.seed(3)
    if kind == "whoosh":
        d = .6
        n = int(d * SR)
        t = np.arange(n) / SR
        x = np.random.randn(n)
        out = np.zeros(n)
        chunks = 24
        for i in range(chunks):
            a, b = int(i * n / chunks), int((i + 1) * n / chunks)
            fc = 300 + 5200 * np.sin(np.pi * (i + .5) / chunks) ** 1.5
            bb, aa = signal.butter(2, [max(80, fc * .55) / (SR / 2), min(fc * 1.3, 18000) / (SR / 2)], "band")
            out[a:b] = signal.lfilter(bb, aa, x[a:b])
        env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
        y = out * env
        y = _norm(y, .5)
    elif kind == "swipe":
        d = .35
        n = int(d * SR)
        t = np.arange(n) / SR
        y = _hp(np.random.randn(n), 1800) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
        y = _norm(y, .35)
    elif kind == "pop":
        d = .18
        n = int(d * SR)
        t = np.arange(n) / SR
        f = 220 + 700 * np.exp(-t * 35)
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 26) * .6
    elif kind == "click":
        n = int(.05 * SR)
        t = np.arange(n) / SR
        y = _hp(np.random.randn(n), 2500) * np.exp(-t * 180) * .5
    elif kind == "tick":
        n = int(.04 * SR)
        t = np.arange(n) / SR
        y = np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 150) * .4
    elif kind == "riser":
        d = 1.6
        n = int(d * SR)
        t = np.arange(n) / SR
        x = _hp(np.random.randn(n), 600) * (t / d) ** 2
        tone = np.sin(2 * np.pi * np.cumsum(200 + 1400 * (t / d) ** 2) / SR) * (t / d) ** 2 * .25
        y = _norm(x * .6 + tone, .5)
    elif kind == "impact":
        d = 1.2
        n = int(d * SR)
        t = np.arange(n) / SR
        thump = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t * 3) + 35) / SR) * np.exp(-t * 4.5)
        crack = _lp(np.random.randn(n), 4000) * np.exp(-t * 18) * .6
        y = _reverb(_norm(thump + crack, .85), .3, .9)
    elif kind == "shimmer":
        d = 1.0
        n = int(d * SR)
        t = np.arange(n) / SR
        y = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (3 + i)) * .12 for i, f in enumerate((1568, 1976, 2349, 3136)))
        y = _reverb(y, .3, .6)
    else:
        raise SystemExit(f"SFX '{kind}' não existe: whoosh swipe pop click tick riser impact shimmer")
    y = y * vol
    return np.stack([y, y], 1).astype(np.float32)


SFX_KINDS = ["whoosh", "swipe", "pop", "click", "tick", "riser", "impact", "shimmer"]


def write_wav(path, st):
    st = np.clip(st, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    return Path(path)


SFX_PACK = ROOT / "library" / "audio" / "sfx"   # solte aqui whoosh.wav, pop.wav... (Magnific/ElevenLabs/Freesound) e eles substituem os sintéticos


def load_audio(path, duration: float | None = None) -> np.ndarray:
    """Qualquer arquivo de áudio -> float32 estéreo (N,2) a 44,1 kHz."""
    tmp = Path(str(path) + ".tmp.wav")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.2f}"]
    subprocess.run(cmd + ["-ar", str(SR), "-ac", "2", str(tmp)], check=True)
    with wave.open(str(tmp)) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32768
    tmp.unlink(missing_ok=True)
    return raw.astype(np.float32)


def loop_to(m: np.ndarray, n: int, xfade: float = 1.5) -> np.ndarray:
    """Estende a trilha até n amostras repetindo com crossfade (trilhas de 30 s em vídeos de 60 s)."""
    if len(m) >= n or len(m) < SR * 4:
        return m[:n]
    x = int(min(xfade, len(m) / 4 / SR) * SR)
    out = m.copy()
    while len(out) < n:
        a, b = out[-x:], m[:x]
        w = np.linspace(0, 1, x)[:, None]
        out = np.concatenate([out[:-x], a * (1 - w) + b * w, m[x:]])
    return out[:n]


def duck_envelope(voice: np.ndarray, depth: float = .6, attack: float = .06, release: float = .35) -> np.ndarray:
    """Ganho (0..1) a aplicar na trilha enquanto a voz fala (ducking suave, calculado a 100 Hz)."""
    blk = SR // 100
    lvl = np.abs(voice).max(axis=1)
    m = len(lvl) // blk
    env = lvl[:m * blk].reshape(m, blk).max(axis=1)
    on = (np.convolve((env > .02).astype(np.float32), np.ones(8) / 8, "same") > .1).astype(np.float32)
    a, r = np.exp(-1 / (attack * 100)), np.exp(-1 / (release * 100))
    g = np.zeros(m, np.float32)
    cur = 0.0
    for i in range(m):
        cur = on[i] + (cur - on[i]) * (a if on[i] > cur else r)
        g[i] = cur
    full = np.interp(np.arange(len(lvl)) / blk, np.arange(m), g)
    return (1 - depth * full).astype(np.float32)


def sfx_any(kind: str, vol: float = 1.0) -> np.ndarray:
    pack = SFX_PACK / f"{kind}.wav"
    if pack.exists():
        s = load_audio(pack)
        return s * vol
    return sfx(kind, vol)


def build_track(duration: float, style: str | None, bpm: float | None, events: list[dict], out: Path,
                music_file: str | None = None, music_vol: float = .75, key: str = "A", sfx_vol: float = .8,
                voice_file: str | None = None, voice_vol: float = 1.0, duck: float = .6, voice_start: float = 0.0,
                solo: str | None = None) -> Path:
    """Mix: música (gerada ou arquivo, com loop) + voz com ducking + SFX nos instantes de `events`
    [{t, kind|file, vol?}] -> wav estéreo. SFX usa o pacote em library/audio/sfx quando existir."""
    n = int(duration * SR)
    mix = np.zeros((n, 2), np.float32)
    voice = None
    if voice_file:
        v = load_audio(voice_file)
        i0 = int(voice_start * SR)
        voice = np.zeros((n, 2), np.float32)
        seg = v[:max(0, n - i0)]
        voice[i0:i0 + len(seg)] = seg
        if len(v) + i0 > n:
            print(f"  ! a voz ({len(v) / SR + voice_start:.1f}s) é mais longa que o vídeo ({duration:.1f}s): ela será cortada")
    m = None
    if music_file:
        m = load_audio(music_file)
        m = loop_to(m, n)
        m = _fades(m[:n], .3, 1.2)
    elif style:
        m = music(style, duration, bpm, key)
    if m is not None and solo in (None, "music"):
        g = duck_envelope(voice, duck)[:len(m), None] if voice is not None and duck > 0 else 1.0
        mix[:len(m)] += m[:n] * music_vol * g
    if voice is not None and solo in (None, "voice"):
        mix += voice * voice_vol
    if solo in (None, "sfx"):
        for k, ev in enumerate(events):
            s = load_audio(ev["file"]) * ev.get("vol", 1.0) * sfx_vol if ev.get("file") else sfx_any(ev["kind"], ev.get("vol", 1.0) * sfx_vol)
            if ev.get("vary"):  # humaniza: cada disparo com altura e volume ligeiramente diferentes
                rng = np.random.default_rng(100 + k)
                rate = rng.uniform(.93, 1.07)
                idx = np.arange(0, len(s) - 1, rate)
                s = np.stack([np.interp(idx, np.arange(len(s)), s[:, c]) for c in range(2)], 1).astype(np.float32)
                s *= 10 ** (rng.uniform(-1.4, 1.0) / 20)
            i = int(ev["t"] * SR)
            if i >= n:
                continue
            j = min(n, i + len(s))
            mix[i:j] += s[:j - i]
    mix = np.tanh(mix * 1.05)
    return write_wav(out, mix)


def remix_video(video, out, *, music_file=None, voice_file=None, style=None, bpm=None, music_vol=.75, voice_vol=1.0, duck=.6,
                events=None, sfx_vol=.8, keep_original=False, voice_start=0.0) -> Path:
    """Troca (ou acrescenta) o áudio de um vídeo pronto: ideal para refazer o som de um reel já renderizado."""
    video, out = Path(video), Path(out)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    dur = float(r.stdout.strip())
    wav = out.with_suffix(".mix.wav")
    build_track(dur, style, bpm, events or [], wav, music_file=music_file, music_vol=music_vol, voice_file=voice_file,
                voice_vol=voice_vol, duck=duck, sfx_vol=sfx_vol, voice_start=voice_start)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-af", f"afade=t=in:d=0.3,afade=t=out:st={max(0, dur - 1):.2f}:d=1,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.84:level=disabled",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out)]
    subprocess.run(cmd, check=True)
    wav.unlink(missing_ok=True)
    return out


def sources() -> list[dict]:
    return json.loads((ROOT / "library" / "audio_sources.json").read_text(encoding="utf-8"))["sources"]
